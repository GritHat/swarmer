#!/usr/bin/env python3
"""Test battery of the targets of swarmer 5.1: python3 -I -B tests/test_targets.py

The swarm is universal: it generates its agents and skills for Claude Code (.claude/), Codex (.codex/agents/*.toml),
Antigravity (.agents/agents/), Gemini CLI (.gemini/agents/) and the open standard (AGENTS.md, .agents/skills/). In
temporary folders it checks, for every target: the files generated and their format (the TOML of Codex read with
tomllib where Python has it, otherwise with a structural reader), the precedence of the local overrides and of the
project's agents without the note, the removal of a target (only the generated files go), the update of a 5.0
installation that stays Claude Code only and changes nothing, `start` with every --cli as a dry run (--show: no tool
is ever started), and `instructions` in CLAUDE.md, AGENTS.md and GEMINI.md. Exits with 1 if a check fails.
"""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent
ENGINE = SOURCE / "engine" / "swarmer.py"
FIXTURES = HERE / "fixtures"
SH50 = FIXTURES / "swarmer-5.0.sh"
results = []
sys.dont_write_bytecode = True
sys.path.insert(0, str(SOURCE / "engine"))
import compat as C  # noqa: E402
import generate as G  # noqa: E402
import paths as S  # noqa: E402

try:
    import tomllib
except ImportError:   # Python 3.10: the structural reader below
    tomllib = None


def i18n(lang):
    out = json.loads((SOURCE / "i18n" / "en.json").read_text(encoding="utf-8"))
    p = SOURCE / "i18n" / f"{lang}.json"
    if lang != "en" and p.is_file():
        out.update(json.loads(p.read_text(encoding="utf-8")))
    return out


EN, IT = i18n("en"), i18n("it")
ALL = ["claude", "codex", "antigravity", "gemini", "agents"]
MD_DIRS = {"claude": ".claude/agents", "antigravity": ".agents/agents", "gemini": ".gemini/agents"}


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("ok   " if ok else "FAILED ") + name + ("" if ok or not detail else f"\n     {str(detail)[:700]}"))


def clean_env(**extra):
    e = {k: v for k, v in os.environ.items() if not k.startswith(("SWARMER_", "SCIAME_"))}
    e.update(extra)
    return e


def py(*arg, env=None, cwd=None):
    p = subprocess.run([sys.executable, "-I", "-B", *map(str, arg)], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, env=env or clean_env(), cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def bash(*arg, env=None):
    p = subprocess.run(["bash", *map(str, arg)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                       env=env or clean_env())
    return p.returncode, p.stdout + p.stderr


def install(root: Path, *extra):
    root.mkdir(parents=True, exist_ok=True)
    return py(ENGINE, "install", "--from", SOURCE, "--root", root, *extra)


def sw(root: Path, *arg, folder="swarmer", env=None):
    s = root / folder
    return py(s / "engine" / "swarmer.py", "--swarm", s, *arg, env=env)


def tree(root: Path, skip=("swarmer", "sciame")) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and p.relative_to(root).parts[0] not in skip}


def aligned(out):
    return any(t["cli_aligned"].split("{profiles}")[1].strip() in out for t in (EN, IT))


def config(root: Path, state=".swarmer") -> dict:
    p = root / state / "config.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def yaml_head(text: str) -> dict:
    """The simple YAML head the generator writes: key: value, the value as JSON when it is quoted."""
    assert text.startswith("---\n"), text[:40]
    head = text[4:text.index("\n---\n", 4)]
    out = {}
    for line in head.splitlines():
        k, _, v = line.partition(": ")
        out[k] = json.loads(v) if v.startswith('"') else v
    return out


def md_body(text: str) -> str:
    return text[text.index("\n---\n", 4) + 5:]


def toml_unescape(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        ch = s[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        nxt = s[i + 1]
        if nxt == "u":
            out.append(chr(int(s[i + 2:i + 6], 16)))
            i += 6
        else:
            out.append({"\\": "\\", '"': '"', "n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f"}[nxt])
            i += 2
    return "".join(out)


def read_toml(text: str) -> dict:
    """tomllib if there is one; otherwise a structural reader of the three fields the generator writes (comment,
    name, description on one line each, developer_instructions as a multi-line basic string to the end)."""
    if tomllib:
        return tomllib.loads(text)
    return read_toml_structural(text)


def read_toml_structural(text: str) -> dict:
    lines = text.split("\n")
    assert lines[0].startswith("# "), "the first line is the comment of the note"
    out = {}
    for line, key in ((lines[1], "name"), (lines[2], "description")):
        m = re.fullmatch(rf'{key} = "((?:[^"\\]|\\.)*)"', line)
        assert m, line
        out[key] = toml_unescape(m.group(1))
    rest = "\n".join(lines[3:])
    m = re.fullmatch(r'developer_instructions = """\n((?:[^"\\]|\\.|"(?!""))*)"""\n', rest, re.S)
    assert m, "developer_instructions is not one multi-line basic string"
    out["developer_instructions"] = toml_unescape(m.group(1))
    return out


def fake_tools(d: Path, *names):
    d.mkdir(parents=True, exist_ok=True)
    for n in names:
        p = d / n
        p.write_text("#!/bin/sh\necho never started >&2\nexit 9\n")
        p.chmod(p.stat().st_mode | stat.S_IXUSR)
    return d


def battery(base: Path):
    roles_n = None

    # T0. the tables of the targets agree
    check("T0: the agent folders of generate.TARGETS are those of compat.AGENT_DIRS (jury.py)",
          tuple(G.TARGETS[t]["agents"] for t in G.TARGETS if G.TARGETS[t]["agents"]) == C.AGENT_DIRS)
    check("T0: the five targets and the four tools", list(G.TARGETS) == ALL
          and list(G.CLIS) == ["claude", "codex", "agy", "gemini"])

    # T1. a new installation in an empty project: every target
    r = base / "all"
    rc, out = install(r)
    check("T1: new installation in an empty project", rc == 0, out)
    check("T1: auto in an empty project gives every target, written in config.json", config(r).get("targets") == ALL,
          config(r))
    ids = sorted(p.stem[len("swarmer-"):] for p in (r / ".claude" / "agents").glob("swarmer-*.md"))
    roles_n = len(ids)
    for tg, d in MD_DIRS.items():
        names = sorted(p.stem[len("swarmer-"):] for p in (r / d).glob("swarmer-*.md"))
        check(f"T1: {tg}: one agent per role in {d}", names == ids and roles_n > 50, (len(names), roles_n))
    tomls = sorted(p.stem[len("swarmer-"):] for p in (r / ".codex" / "agents").glob("swarmer-*.toml"))
    check("T1: codex: one TOML agent per role in .codex/agents", tomls == ids, len(tomls))
    rid = "avversario" if "avversario" in ids else ids[0]
    claude = (r / ".claude" / "agents" / f"swarmer-{rid}.md").read_text(encoding="utf-8")
    ch = yaml_head(claude)
    check("T1: claude: name, description, model", set(ch) == {"name", "description", "model"}
          and ch["name"] == f"swarmer-{rid}", ch)
    ag = (r / ".agents" / "agents" / f"swarmer-{rid}.md").read_text(encoding="utf-8")
    ah = yaml_head(ag)
    check("T1: antigravity: name, description, subagent: true, mainAgent: false",
          ah == {"name": f"swarmer-{rid}", "description": ch["description"], "subagent": "true", "mainAgent": "false"},
          ah)
    gm = (r / ".gemini" / "agents" / f"swarmer-{rid}.md").read_text(encoding="utf-8")
    gh = yaml_head(gm)
    check("T1: gemini: name and description only", gh == {"name": f"swarmer-{rid}", "description": ch["description"]},
          gh)
    check("T1: gemini: the name has only lower-case letters, digits, - and _",
          all(re.fullmatch(r"[a-z0-9_-]+", f"swarmer-{x}") for x in ids))
    check("T1: claude, antigravity and gemini carry the same body (note and prompt)",
          md_body(claude) == md_body(ag) == md_body(gm))
    for p in (r / ".claude" / "agents" / f"swarmer-{rid}.md", r / ".agents" / "agents" / f"swarmer-{rid}.md",
              r / ".gemini" / "agents" / f"swarmer-{rid}.md", r / ".codex" / "agents" / f"swarmer-{rid}.toml"):
        check(f"T1: {p.relative_to(r).parts[0]}: the agent carries the GENERATED note", S.is_generated(p))
    ct = (r / ".codex" / "agents" / f"swarmer-{rid}.toml").read_text(encoding="utf-8")
    try:
        doc = read_toml(ct)
        ok = (set(doc) == {"name", "description", "developer_instructions"} and doc["name"] == f"swarmer-{rid}"
              and doc["description"] == ch["description"]
              and doc["developer_instructions"] == md_body(claude).split("\n\n", 1)[1].lstrip("\n"))
        check(f"T1: codex: valid TOML ({'tomllib' if tomllib else 'structural reader'}) with name, description, "
              "developer_instructions = the prompt of the role", ok, sorted(doc))
    except Exception as e:   # noqa: BLE001
        check("T1: codex: valid TOML", False, repr(e))
    check("T1: codex: the note is the comment of the first line",
          ct.startswith(f"# {C.GENERATED_NOTES['en']}: ") and "<!--" not in ct.split("\n")[0])
    sk_c = sorted(p.parent.name for p in (r / ".claude" / "skills").glob("*/SKILL.md"))
    sk_a = sorted(p.parent.name for p in (r / ".agents" / "skills").glob("*/SKILL.md"))
    check("T1: nine skills in .claude/skills and one shared copy in .agents/skills", len(sk_c) == 9 and sk_a == sk_c,
          (sk_c, sk_a))
    check("T1: no other copy of the skills (.codex/skills, .gemini/skills)",
          not (r / ".codex" / "skills").exists() and not (r / ".gemini" / "skills").exists())
    shared = (r / ".agents" / "skills" / "swarmer-plenary" / "SKILL.md").read_text(encoding="utf-8")
    own = (r / ".claude" / "skills" / "swarmer-plenary" / "SKILL.md").read_text(encoding="utf-8")
    check("T1: the shared skill keeps to the Agent Skills format (name and description)",
          set(yaml_head(shared)) == {"name", "description"}, yaml_head(shared))
    check("T1: the Claude Code skill keeps its own fields", {"argument-hint", "disable-model-invocation"}
          <= set(yaml_head(own)))
    check("T1: $ARGUMENTS only in the Claude Code skill", "$ARGUMENTS" in own and "$ARGUMENTS" not in shared)
    check("T1: every skill tells how to delegate in each tool",
          all(w in shared and w in own for w in ("invoke_subagent", "subagent_type", ".codex/agents", "@swarmer-")))
    check("T1: the shared skill carries the GENERATED note",
          S.is_generated(r / ".agents" / "skills" / "swarmer-plenary" / "SKILL.md"))
    rc, out = sw(r, "check")
    check("T1: check of every target: aligned", rc == 0 and aligned(out) and "claude, codex" in out, out)
    cat = json.loads((r / "swarmer" / "catalog.json").read_text(encoding="utf-8"))
    check("T1: the catalog names the targets and the delegation text", cat.get("targets") == ALL
          and "invoke_subagent" in cat["texts"].get("delegation", ""))
    (r / ".codex" / "agents" / f"swarmer-{rid}.toml").write_text(ct.replace('description = "', 'description = "X', 1), encoding="utf-8")
    rc, out = sw(r, "check")
    check("T1: check sees a retouched Codex agent", rc == 1 and f".codex/agents/swarmer-{rid}.toml" in out, out)
    rc, out = sw(r, "regenerate")
    check("T1: regenerate restores it", rc == 0 and (r / ".codex" / "agents" / f"swarmer-{rid}.toml").read_text() == ct)

    # T2. TOML escapes: quotes, backslashes, triple quotes, tab and control characters in a local card
    (r / "swarmer" / "local" / "AGENTS.md").write_text(
        "# Local cards\n\n### 1. Tricky — `swarmer-tricky`\n\n- **In short:** quotes \" and a back\\slash.\n\n"
        "Body with \"\"\" and \\\"\"\" and a literal \\n, a tab\there, a DEL \x7f, a bell \x07 and a last quote \"\n",
        encoding="utf-8")
    rc, out = sw(r, "regenerate")
    tp = r / ".codex" / "agents" / "swarmer-tricky.toml"
    check("T2: a local-only role with quotes, backslashes and control characters", rc == 0 and tp.is_file(), out)
    try:
        doc = read_toml(tp.read_text(encoding="utf-8"))
        di = doc["developer_instructions"]
        check("T2: the TOML reads back exactly",
              '"""' in di and '\\"""' in di and "\\n" in di and "\t" in di and "\x7f" in di and "\x07" in di
              and 'quotes " and a back\\slash' in doc["description"], repr(doc["description"]))
        body = md_body((r / ".claude" / "agents" / "swarmer-tricky.md").read_text(encoding="utf-8"))
        check("T2: the instructions of Codex are the body of the Claude Code agent",
              di == body.split("\n\n", 1)[1].lstrip("\n"))
    except Exception as e:   # noqa: BLE001
        check("T2: the TOML reads back", False, repr(e))
    if tomllib is None:
        check("T2: tomllib missing (Python < 3.11): the structural reader was used", True)
    else:
        try:
            same = all(read_toml_structural(q.read_text(encoding="utf-8")) == tomllib.loads(q.read_text(encoding="utf-8"))
                       for q in (tp, r / ".codex" / "agents" / f"swarmer-{rid}.toml"))
        except Exception as e:   # noqa: BLE001
            same = repr(e)
        check("T2: the structural reader (used without tomllib) agrees with tomllib", same is True, same)

    # T3. detection (auto) in a project that already uses some tools
    r = base / "detect"
    (r / ".codex").mkdir(parents=True)
    (r / "GEMINI.md").write_text("# rules\n")
    rc, out = install(r)
    check("T3: auto: .codex/ and GEMINI.md give codex, gemini and the generic target",
          rc == 0 and config(r).get("targets") == ["codex", "gemini", "agents"], (out, config(r)))
    check("T3: no folder of an inactive target is created", not (r / ".claude").exists()
          and not (r / ".agents" / "agents").exists() and (r / ".gemini" / "agents").is_dir()
          and (r / ".agents" / "skills" / "swarmer" / "SKILL.md").is_file())
    check("T3: GEMINI.md untouched (instructions only on request)", (r / "GEMINI.md").read_text() == "# rules\n")
    rc, out = sw(r, "check")
    check("T3: check of a project without Claude Code: aligned (jury roles from .codex and .gemini)",
          rc == 0 and aligned(out), out)
    r = base / "detect2"
    (r / ".claude").mkdir(parents=True)
    rc, out = install(r)
    check("T3: a Claude Code project gets claude and the generic target", config(r).get("targets") == ["claude", "agents"],
          config(r))
    r = base / "explicit"
    rc, out = install(r, "--targets", "gemini, claude")
    check("T3: --targets, in any order and with spaces, is kept in the canonical order",
          rc == 0 and config(r).get("targets") == ["claude", "gemini"], (out, config(r)))
    rc, out = install(base / "bad", "--targets", "claude,cursor")
    check("T3: an unknown target is refused", rc == 1 and "cursor" in out, out)
    (base / "viabash").mkdir()
    (base / "viabash_it").mkdir()
    rc, out = bash(SOURCE / "swarmer.sh", "-C", base / "viabash", "install", "--targets", "antigravity")
    check("T3: bash swarmer.sh install --targets", rc == 0 and config(base / "viabash").get("targets") == ["antigravity"]
          and (base / "viabash" / ".agents" / "agents").is_dir() and not (base / "viabash" / ".claude").exists(), out)
    rc, out = bash(SOURCE / "swarmer.sh", "-C", base / "viabash_it", "installa", "--destinazioni", "codex",
                   "--lingua", "it")
    check("T3: bash sciame alias --destinazioni, in Italian", rc == 0 and config(base / "viabash_it", ".sciame")
          .get("destinazioni") == ["codex"] and (base / "viabash_it" / ".codex" / "agents" / "sciame-garante.toml")
          .is_file(), out)

    # T4. precedence of the local overrides and of the project's agents, in every target
    r = base / "prec"
    r.mkdir()
    own = {".claude/agents/swarmer-own.md": "---\nname: swarmer-own\ndescription: mine\n---\n\nmine\n",
           ".agents/agents/swarmer-arbitro.md": "---\nname: swarmer-arbitro\ndescription: mine\n---\n\nmy arbiter\n",
           ".gemini/agents/sciame-logico.md": "---\nname: sciame-logico\ndescription: mine\n---\n\nmy logician\n",
           ".codex/agents/swarmer-debugger.toml": 'name = "swarmer-debugger"\ndescription = "mine"\n'
                                                  'developer_instructions = "mine"\n',
           ".agents/skills/swarmer-single/SKILL.md": "---\nname: swarmer-single\ndescription: mine\n---\n\nmine\n"}
    for rel, text in own.items():
        (r / rel).parent.mkdir(parents=True, exist_ok=True)
        (r / rel).write_text(text)
    rc, out = install(r, "--targets", ",".join(ALL))
    check("T4: installation next to the project's own agents in every target", rc == 0, out)
    check("T4: no project file without the note is touched, in any target",
          all((r / rel).read_text() == text for rel, text in own.items()))
    check("T4: an unmarked agent of the other prefix stands for the role in its own target only",
          not (r / ".gemini" / "agents" / "swarmer-logico.md").exists()
          and (r / ".claude" / "agents" / "swarmer-logico.md").is_file()
          and (r / ".codex" / "agents" / "swarmer-logico.toml").is_file())
    rc, out = sw(r, "check")
    check("T4: check: aligned, with the project's files standing for their roles", rc == 0 and aligned(out), out)
    (r / "swarmer" / "local" / "AGENTS.md").write_text(
        "# Local cards\n\n### 1. Guarantor of the project — `swarmer-garante`\n\n- **In short:** local guarantor.\n\n"
        "LOCAL-CARD-TEXT of the project.\n", encoding="utf-8")
    rc, out = sw(r, "regenerate")
    loc = {tg: (r / d / "swarmer-garante.md").read_text() for tg, d in MD_DIRS.items()}
    loc["codex"] = read_toml((r / ".codex" / "agents" / "swarmer-garante.toml").read_text())["developer_instructions"]
    check("T4: a local card replaces the generic role in every target",
          rc == 0 and all("LOCAL-CARD-TEXT" in v for v in loc.values()), {k: "LOCAL-CARD-TEXT" in v for k, v in loc.items()})
    rc, out = install(base / "prec_managed", "--targets", ",".join(ALL), "--local", "mine", "--project-managed")
    (base / "prec_managed" / "mine").mkdir(exist_ok=True)
    (base / "prec_managed" / "mine" / "AGENTS.md").write_text(
        "# Local cards\n\n### 1. Only here — `swarmer-only-here`\n\n- **In short:** of the project.\n\nText.\n")
    rc, out = sw(base / "prec_managed", "regenerate")
    pm = base / "prec_managed"
    check("T4 (G-A): project_managed: the swarm does not write the overrides in .claude/agents (the project does)",
          rc == 0 and not (pm / ".claude" / "agents" / "swarmer-only-here.md").exists(), out)
    check("T4 (G-A): project_managed: the overrides are generated from the local cards in codex, antigravity, gemini",
          all((pm / d / f"swarmer-only-here{e}").is_file() for d, e in C.AGENT_DIRS if d != ".claude/agents")
          and "Text." in read_toml((pm / ".codex" / "agents" / "swarmer-only-here.toml").read_text())
          ["developer_instructions"])
    shared_sk = (pm / ".agents" / "skills" / "swarmer" / "SKILL.md").read_text(encoding="utf-8")
    check("T4 (G-A): the shared skill lists the role, and the role exists in every target that reads it",
          "swarmer-only-here" in shared_sk)
    rc, out = sw(pm, "check")
    check("T4 (G-A): check tells the truth: the project has not generated its Claude Code agent yet",
          rc == 1 and "missing .claude/agents/swarmer-only-here.md (project_managed" in out, out)
    (pm / ".claude" / "agents" / "swarmer-only-here.md").write_text(
        "---\nname: swarmer-only-here\ndescription: of the project\n---\n\nProject text.\n")
    (pm / ".gemini" / "agents" / "swarmer-only-here.md").write_text(
        "---\nname: swarmer-only-here\ndescription: mine\n---\n\nMy gemini text.\n")
    rc, out = sw(pm, "regenerate")
    check("T4 (G-A): a file of the project without the note wins in every target (claude and gemini untouched)",
          rc == 0 and "Project text." in (pm / ".claude" / "agents" / "swarmer-only-here.md").read_text()
          and "My gemini text." in (pm / ".gemini" / "agents" / "swarmer-only-here.md").read_text(), out)
    rc, out = sw(pm, "check")
    check("T4 (G-A): check: aligned once the project has its agent", rc == 0 and aligned(out), out)
    (pm / ".codex" / "agents" / "swarmer-only-here.toml").unlink()
    rc, out = sw(pm, "check")
    check("T4 (G-A): check sees the local role missing in codex", rc == 1
          and "missing .codex/agents/swarmer-only-here.toml" in out, out)
    # M-4: a hand-written override in .claude/agents is reported for the other targets
    (pm / ".claude" / "agents" / "swarmer-garante.md").write_text(
        "---\nname: swarmer-garante\ndescription: mine\n---\n\nmy guarantor\n")
    rc, out = sw(pm, "regenerate")
    rc, out = sw(pm, "check")
    check("T4 (M-4): check notices an override written by hand only in .claude/agents",
          rc == 0 and "override only in .claude/agents: swarmer-garante.md" in out, out)

    # T5. a target removed: only its generated files go
    r = base / "all"
    (r / ".codex" / "agents" / "my-own.toml").write_text('name = "my-own"\n')
    (r / ".gemini" / "settings.json").write_text("{}\n")
    rc, out = sw(r, "targets", "--remove", "codex")
    check("T5: targets --remove codex", rc == 0 and config(r).get("targets") == [t for t in ALL if t != "codex"], out)
    check("T5: the generated Codex agents are gone, the project's file stays",
          not list((r / ".codex" / "agents").glob("swarmer-*.toml")) and (r / ".codex" / "agents" / "my-own.toml").is_file())
    check("T5: the other targets are untouched", (r / ".agents" / "agents" / f"swarmer-{rid}.md").is_file()
          and (r / ".agents" / "skills" / "swarmer" / "SKILL.md").is_file())
    rc, out = sw(r, "targets", "claude,antigravity")
    check("T5: targets LIST: gemini and agents go; the skills shared with antigravity stay",
          rc == 0 and config(r).get("targets") == ["claude", "antigravity"]
          and not list((r / ".gemini").glob("agents/*"))
          and (r / ".agents" / "skills" / "swarmer-classic" / "SKILL.md").is_file(), out)
    check("T5: an empty folder of a removed target goes, one with project files stays",
          not (r / ".gemini" / "agents").exists() and (r / ".gemini" / "settings.json").is_file())
    (r / ".agents" / "skills" / "theirs").mkdir(parents=True)
    (r / ".agents" / "skills" / "theirs" / "SKILL.md").write_text("---\nname: theirs\ndescription: x\n---\n\nx\n")
    rc, out = sw(r, "targets", "--remove", "antigravity")
    check("T5: with Claude Code only, the shared skills and the Antigravity agents go",
          rc == 0 and not (r / ".agents" / "agents").exists()
          and not (r / ".agents" / "skills" / "swarmer-classic").exists()
          and (r / ".agents" / "skills" / "theirs" / "SKILL.md").is_file(), out)
    rc, out = sw(r, "check")
    check("T5: check after the removals: aligned", rc == 0 and aligned(out), out)
    (r / ".gemini" / "agents").mkdir(parents=True)
    (r / ".gemini" / "agents" / f"swarmer-{rid}.md").write_text(gm)
    rc, out = sw(r, "check")
    check("T5 (G-B): check does not examine an inactive target", rc == 0 and ".gemini" not in out, out)
    rc, out = sw(r, "regenerate")
    check("T5 (G-B): regenerate does not touch an inactive target",
          rc == 0 and (r / ".gemini" / "agents" / f"swarmer-{rid}.md").is_file(), out)
    rc, out = sw(r, "targets", "--remove", "gemini")
    check("T5 (G-B): the explicit removal of an inactive target takes its generated files away",
          rc == 0 and not (r / ".gemini" / "agents" / f"swarmer-{rid}.md").exists()
          and config(r).get("targets") == ["claude"], out)
    rc, out = sw(r, "targets", "--remove", "auto")
    check("T5: targets --remove auto is refused, not silently ignored", rc == 1 and "auto" in out, out)
    (r / ".agents" / "skills").rename(r / "elsewhere")   # the project's own skills, now behind a link
    (r / ".agents" / "skills").symlink_to(r / "elsewhere")
    before = tree(r)
    rc, out = sw(r, "regenerate")
    check("T5 (G-B): a link in the folder of an inactive target does not stop regenerate", rc == 0, out)
    rc, out = sw(r, "check")
    check("T5 (G-B): nor check", rc == 0 and aligned(out), out)
    rc, out = sw(r, "targets", "--add", "codex")
    check("T5 (G-B): adding a target that would write through the link is refused before any write",
          rc == 1 and "symbolic link" in out and config(r).get("targets") == ["claude"] and tree(r) == before
          and not (r / ".codex" / "agents" / f"swarmer-{rid}.toml").exists(), out)
    rc, out = sw(r, "remove")
    check("T5 (G-B): remove (explicit, every target) stops on the link before writing anything",
          rc == 1 and "symbolic link" in out and tree(r) == before, out)
    (r / ".agents" / "skills").unlink()
    (r / "elsewhere").rename(r / ".agents" / "skills")
    rc, out = sw(r, "targets", "--remove", "claude")
    check("T5: the last target cannot be removed", rc == 1 and config(r).get("targets") == ["claude"], out)
    rc, out = sw(r, "targets", "--add", "codex,gemini")
    check("T5: targets --add", rc == 0 and config(r).get("targets") == ["claude", "codex", "gemini"]
          and (r / ".codex" / "agents" / f"swarmer-{rid}.toml").is_file(), out)
    rc, out = sw(r, "targets")
    check("T5: targets alone shows them and what the project has", rc == 0 and "claude, codex, gemini" in out
          and EN["cli_targets_detected"].split("{targets}")[0] in out, out)
    rc, out = sw(r, "regenerate", "--targets", "auto")
    check("T5: regenerate --targets auto: the targets of the project", rc == 0
          and config(r).get("targets") == ["claude", "codex", "gemini", "agents"], (out, config(r)))
    rc, out = sw(r, "remove")
    check("T5: remove takes away the generated files of every target, not the project's",
          rc == 0 and not list((r / ".codex" / "agents").glob("swarmer-*"))
          and not (r / ".agents" / "skills" / "swarmer").exists()
          and (r / ".codex" / "agents" / "my-own.toml").is_file()
          and (r / ".agents" / "skills" / "theirs" / "SKILL.md").is_file(), out)

    # T6. the update of a 5.0 installation: Claude Code only, nothing changes
    if SH50.is_file():
        r = base / "from50"
        r.mkdir()
        (r / "CLAUDE.md").write_text("# The project\n")
        rc, out = bash(SH50, "-C", r, "install")
        check("T6: a 5.0 installation (fixture)", rc == 0, out)
        before = tree(r)
        cfg_before = (r / ".swarmer" / "config.json").read_bytes() if (r / ".swarmer" / "config.json").is_file() else None
        rc, out = bash(SOURCE / "swarmer.sh", "-C", r, "update")
        after = tree(r)
        check("T6: update of the 5.0 with the 5.1", rc == 0, out)
        check("T6: the same files in the project (names), and no folder of another target",
              set(after) == set(before) and not any((r / d).exists() for d in (".codex", ".gemini", ".agents")),
              sorted(set(after) ^ set(before))[:5])
        check("T6: the agents byte for byte", all(after[k] == before[k] for k in before if k.startswith(".claude/agents/")),
              [k for k in before if k.startswith(".claude/agents/") and after.get(k) != before[k]][:3])
        check("T6: config.json and CLAUDE.md as they were", after["CLAUDE.md"] == before["CLAUDE.md"]
              and ((r / ".swarmer" / "config.json").read_bytes() if cfg_before is not None else None) == cfg_before
              and not ((r / ".swarmer" / "config.json").is_file() and cfg_before is None))
        rc, out = sw(r, "check")
        check("T6: check: aligned, targets: claude", rc == 0 and aligned(out)
              and EN["cli_targets"].format(targets="claude") in out, out)
        rc, out = bash(SOURCE / "swarmer.sh", "-C", r, "update", "--targets", "claude,codex")
        check("T6: update --targets adds a target on request", rc == 0 and config(r).get("targets") == ["claude", "codex"]
              and (r / ".codex" / "agents").is_dir(), out)
    else:
        check("T6: skipped: tests/fixtures/swarmer-5.0.sh is missing", True)

    # T7. start with every tool, as a dry run (--show): nothing is ever started
    r = base / "start"
    rc, out = install(r)
    tools = fake_tools(base / "bin_none")
    env0 = clean_env(PATH=str(tools))
    shows = {
        "claude": ["claude", "/swarmer-classic profile=code x"],
        "codex": ["codex", "Use the skill swarmer-classic (.agents/skills/swarmer-classic/SKILL.md)"],
        "agy": ["agy -i", "Use the skill swarmer-classic"],
        "gemini": ["gemini -i", "Use the skill swarmer-classic"],
    }
    for cli, words in shows.items():
        rc, out = sw(r, "classic", "--show", "--cli", cli, "--profile", "code", "x", env=env0)
        check(f"T7: classic --show --cli {cli}", rc == 0 and all(w in out for w in words), out)
    prints = {"claude": "claude -p", "codex": "codex exec", "agy": "agy -p", "gemini": "gemini -p"}
    for cli, word in prints.items():
        rc, out = sw(r, "single", "--show", "--print", "--cli", cli, "x", env=env0)
        check(f"T7: single --show --print --cli {cli}: without interaction", rc == 0 and word in out, out)
    rc, out = sw(r, "single", "--show", "--cli", "codex", "--model", "gpt-x", "x", env=env0)
    check("T7: --model with codex", rc == 0 and "codex --model gpt-x" in out, out)
    rc, out = sw(r, "single", "--show", "--cli", "agy", "--model", "m", "x", env=env0)
    check("T7: --model with agy is refused", rc == 1, out)
    rc, out = sw(r, "single", "--show", "--cli", "cursor", "x", env=env0)
    check("T7: an unknown tool is refused", rc == 1 and "cursor" in out, out)
    rc, out = sw(r, "single", "--show", "x", env=clean_env(PATH=str(fake_tools(base / "bin_ag", "agy", "gemini"))))
    check("T7: without --cli: the first tool in the PATH in the order claude, codex, agy, gemini",
          rc == 0 and "agy -i" in out, out)
    rc, out = sw(r, "single", "--show", "x", env=env0)
    check("T7: without --cli and without tools: claude", rc == 0 and " claude " in f" {out}", out)
    cp = r / ".swarmer" / "config.json"
    cp.write_text(json.dumps(dict(config(r), cli="gemini")))
    rc, out = sw(r, "single", "--show", "x", env=clean_env(PATH=str(fake_tools(base / "bin_cl", "claude"))))
    check("T7: the key cli of config.json comes before the PATH", rc == 0 and "gemini -i" in out, out)
    rc, out = sw(r, "single", "--cli", "codex", "x", env=env0)
    check("T7: without --show and without the tool: refused, nothing started", rc == 1 and "never started" not in out, out)
    rc, out = sw(base / "explicit", "single", "--show", "--cli", "codex", "x", env=env0)
    check("T7: a tool whose target is not active is refused, with the command that adds it",
          rc == 1 and "targets --add codex" in out, out)
    # G-C: the options of the swarm after the request, as README and help write them; only «--» passes to the tool
    cp.write_text(json.dumps({k: v for k, v in config(r).items() if k != "cli"}))
    rc, out = sw(r, "single", "x", "--cli", "codex", "--show", env=env0)
    check("T7 (G-C): options after the request are options of the swarm", rc == 0 and out.startswith("cd ")
          and " codex " in out and "--cli" not in out and "--show" not in out, out)
    rc, out = sw(r, "classic", "x", "--profile", "code", "--print", "--show", "--cli", "gemini", env=env0)
    check("T7 (G-C): --profile and --print after the request", rc == 0 and "gemini -p" in out
          and "profile=code x" in out and "--profile" not in out, out)
    rc, out = sw(r, "single", "x", "--show", "--cli", "claude", "--", "--permission-mode", "plan", env=env0)
    check("T7 (G-C): what follows -- goes to the tool, after the request", rc == 0
          and out.rstrip().endswith("'/swarmer-single x' --permission-mode plan"), out)
    rc, out = sw(r, "single", "x", "stray", "--show", env=env0)
    check("T7 (G-C): a stray word is an error, never passed to the tool", rc != 0 and "stray" in out
          and "cd " not in out, out)
    # M-1: without --cli, the first tool in the PATH whose target is active
    rc, out = install(base / "only_codex", "--targets", "codex")
    rc, out = sw(base / "only_codex", "single", "--show", "x",
                 env=clean_env(PATH=str(fake_tools(base / "bin_cc", "claude", "codex"))))
    check("T7 (M-1): claude and codex in the PATH, only codex active: codex", rc == 0 and " codex " in out
          and "claude" not in out.split("&&", 1)[1], out)
    rc, out = sw(base / "only_codex", "single", "--show", "x", env=env0)
    check("T7 (M-1): no tool in the PATH: the first whose target is active", rc == 0 and " codex " in out, out)

    # T8. instructions in the files of the active targets
    r = base / "instr"
    r.mkdir()
    (r / "AGENTS.md").write_text("# Our agents rules\n\nKeep them.\n")
    rc, out = install(r, "--targets", "claude,codex,gemini")
    check("T8: no instruction file written without the request", rc == 0 and not (r / "CLAUDE.md").exists()
          and not (r / "GEMINI.md").exists() and (r / "AGENTS.md").read_text() == "# Our agents rules\n\nKeep them.\n")
    rc, out = sw(r, "instructions")
    begin = C.CLAUDE_MARKS["en"][0]
    check("T8: instructions writes CLAUDE.md, AGENTS.md and GEMINI.md", rc == 0 and all(
        begin in (r / n).read_text() for n in ("CLAUDE.md", "AGENTS.md", "GEMINI.md")), out)
    check("T8: AGENTS.md keeps the project's text, the paragraph once",
          (r / "AGENTS.md").read_text().startswith("# Our agents rules\n\nKeep them.\n")
          and (r / "AGENTS.md").read_text().count(begin) == 1)
    rc, out = sw(r, "instructions")
    check("T8: instructions again: in place, not duplicated", rc == 0
          and all((r / n).read_text().count(begin) == 1 for n in ("CLAUDE.md", "AGENTS.md", "GEMINI.md")), out)
    rc, out = sw(r, "targets", "--remove", "gemini")
    check("T8: removing a target takes its paragraph out of the file no other target reads (a file left empty goes)",
          rc == 0 and not (r / "GEMINI.md").exists() and begin in (r / "AGENTS.md").read_text(), out)
    rc, out = sw(r, "targets", "--remove", "codex")
    check("T8: AGENTS.md: the paragraph goes with the last target that reads it, the project's text stays",
          (r / "AGENTS.md").read_text() == "# Our agents rules\n\nKeep them.\n", (r / "AGENTS.md").read_text())
    rc, out = sw(r, "targets", "--add", "agents")
    rc, out = sw(r, "instructions", "--remove")
    check("T8: instructions --remove: out of every file; CLAUDE.md, which held only the paragraph, goes",
          rc == 0 and not (r / "CLAUDE.md").exists() and not (r / "GEMINI.md").exists()
          and (r / "AGENTS.md").read_text() == "# Our agents rules\n\nKeep them.\n", out)
    rc, out = install(base / "instr2", "--targets", "gemini", "--instructions")
    check("T8: install --instructions with gemini only: GEMINI.md", rc == 0 and begin in
          (base / "instr2" / "GEMINI.md").read_text() and not (base / "instr2" / "CLAUDE.md").exists(), out)
    par = (base / "instr2" / "GEMINI.md").read_text()
    check("T8: the paragraph names the agents of every tool, not only the slash commands",
          ".gemini/agents/" in par and ".agents/skills/" in par)

    # T9. Italian: prefix, note, dialect of the configuration, aliases
    r = base / "it"
    r.mkdir()
    rc, out = install(r, "--language", "it", "--targets", "codex,antigravity")
    check("T9: Italian installation for codex and antigravity", rc == 0 and config(r, ".sciame").get("destinazioni")
          == ["codex", "antigravity"], (out, config(r, ".sciame")))
    tp = r / ".codex" / "agents" / "sciame-garante.toml"
    check("T9: Italian prefix and note in the Codex agent", tp.is_file()
          and tp.read_text().startswith(f"# {C.GENERATED_NOTES['it']}: ") and S.is_generated(tp))
    check("T9: Italian names of the shared skills", (r / ".agents" / "skills" / "sciame-singolo" / "SKILL.md").is_file()
          and (r / ".agents" / "agents" / "sciame-garante.md").is_file())
    rc, out = sw(r, "destinazioni", "--aggiungi", "gemini", folder="sciame")
    check("T9: the alias destinazioni --aggiungi", rc == 0 and config(r, ".sciame").get("destinazioni")
          == ["codex", "antigravity", "gemini"] and "targets" not in config(r, ".sciame"), out)
    rc, out = sw(r, "singolo", "--mostra", "--cli", "gemini", "x", folder="sciame", env=env0)
    check("T9: the Italian prompt for gemini", rc == 0 and "Usa la skill sciame-singolo" in out, out)
    rc, out = sw(r, "singolo", "x", "--mostra", "--cli", "gemini", folder="sciame", env=env0)
    check("T9 (G-C): the Italian options after the request too", rc == 0 and "gemini -i" in out, out)
    rc, out = sw(r, "controlla", folder="sciame")
    check("T9: controlla: aligned", rc == 0 and aligned(out) and IT["cli_targets"].split("{")[0] in out, out)

    # T10. a role waiting for its translation: the sign in every target
    d = json.loads((r / "sciame" / "db" / "professionals.json").read_text(encoding="utf-8"))
    e = json.loads(json.dumps(next(v for v in d["entries"] if v["id"] == "garante")))
    e.update(id="solo-inglese", number=max(int(str(v.get("number", 0)).split(".")[0]) for v in d["entries"]
                                          if str(v.get("number", "0")).split(".")[0].isdigit()) + 1)
    e["texts"] = {"en": e["texts"]["en"]}
    d["entries"].append(e)
    (r / "sciame" / "db" / "professionals.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                                                             encoding="utf-8")
    rc, out = sw(r, "rigenera", folder="sciame")
    pend = f"{C.TRANSLATION_PENDING}: it"
    check("T10: translation-pending in the TOML note and in the Markdown agents",
          rc == 0 and pend in (r / ".codex" / "agents" / "sciame-solo-inglese.toml").read_text().split("\n")[0]
          and pend in (r / ".gemini" / "agents" / "sciame-solo-inglese.md").read_text()
          and pend in (r / ".agents" / "agents" / "sciame-solo-inglese.md").read_text(), out)

    # T11. the small ones: NEL in a YAML head, targets --add auto, check without the path of the tools
    r = base / "small"
    rc, out = install(r, "--targets", "claude,gemini")
    dbp = r / "swarmer" / "db" / "professionals.json"
    d = json.loads(dbp.read_text(encoding="utf-8"))
    e = next(v for v in d["entries"] if v["id"] == "garante")
    e["texts"]["en"]["short"] = "a\x85---\x85b " + e["texts"]["en"]["short"]
    dbp.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    rc, out = sw(r, "regenerate")
    heads = [(r / d / "swarmer-garante.md").read_text(encoding="utf-8").split("\n---\n", 1)[0]
             for d in (".claude/agents", ".gemini/agents")]
    check("T11: NEL never raw in a YAML head (escaped)", rc == 0 and all(
        "\x85" not in h and "\\u0085" in h for h in heads), heads)
    check("T11: LS and PS escaped too", G.yaml_str("a\u2028b\u2029c") == '"a\\u2028b\\u2029c"', G.yaml_str("a\u2028b"))
    check("T11: the escaped head reads back as JSON", all(
        "a\x85---\x85b" in yaml_head(h + "\n---\n")["description"] for h in heads))
    rc, out = sw(r, "targets", "--add", "auto")
    check("T11: targets --add auto adds the targets detected in the project, not every target",
          rc == 0 and config(r).get("targets") == ["claude", "gemini", "agents"], (out, config(r)))
    rc, out = sw(r, "check", env=clean_env(PATH=str(fake_tools(base / "bin_g", "gemini"))))
    check("T11: check says that a tool is found, without its path", rc == 0 and "gemini: " in out
          and str(base / "bin_g") not in out, out)


def main():
    tmp = os.environ.get("TMPDIR")
    with tempfile.TemporaryDirectory(dir=tmp if tmp and Path(tmp).is_dir() else None) as base:
        battery(Path(base))
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
