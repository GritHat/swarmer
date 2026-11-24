#!/usr/bin/env python3
"""The generator of swarmer: from the database, the documents of the language and the local overrides it
generates, in the project root, the catalog, the agents, the skills and the documents in the chosen language, for
every active target (the coding agents that read them: Claude Code, Codex, Antigravity, Gemini CLI, and the open
standard AGENTS.md + Agent Skills that many other tools read).

The sources:
- `<swarm>/db/`: the single database of the professionals and sub-professionals;
- `<swarm>/docs/<language>/`: the documents (PREAMBLE, PIPELINE, COORDINATOR_INSTRUCTIONS, JURY, ENVIRONMENT,
  HYPOTHESIS_CARD, README), under their canonical names; the generated copy takes the name of the language;
- `<swarm>/i18n/<language>.json`: the texts of the generator and of the commands (fallback: en.json);
- the local overrides (`<swarm>/local/AGENTS.md`, or the folder of `config.json`): a local card always replaces the
  generic role with the same id, and a local-only role is added;
- the local translations (`<swarm>/local/translations/<language>/<id>.json`, K.3): the texts of an entry that the
  database does not have in the language of the installation; without one, the agent is generated from the English
  text and carries the sign `translation-pending: <language>` (K.2);
- the enabled extensions (`<swarm>/extensions/<name>/`, 5.2): their documents, their skills and the coordinator block
  they append to every strategy skill (extensions.py).

What it writes always carries the GENERATED note: a file without the note (for instance an agent of the project) is
never touched nor deleted, in every target. Agents and skills take the prefix of `prefix_of` (D). Used by
`engine/swarmer.py`; standard library only.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# 5.3.2 (K-100, S18): compat is compiled from its source, never from a .pyc, and its engine_path puts this folder right
# after the standard library, every module of it compiled from its source
if not hasattr(sys.modules.get("compat"), "engine_path"):
    _c = type(sys)("compat")
    _c.__file__ = str(HERE / "compat.py")
    exec(compile((HERE / "compat.py").read_bytes(), _c.__file__, "exec", dont_inherit=True), _c.__dict__)
    sys.modules["compat"] = _c
sys.modules["compat"].engine_path(HERE)
import compat as C  # noqa: E402
import extensions as E  # noqa: E402
import paths as S  # noqa: E402
import professionals as P  # noqa: E402

# The version of swarmer, written here only (ENG-14): the swarm's VERSION, the catalog, the manifest of a convening
# and `convene --help` read it from here; plugin.json (N.M.patch, the package) and the documents agree with it, as
# tests/test_robustness.py checks. N.M: the form of a database entry's «since version» and of an extension's
# requirement.
VERSION = "5.3"
STRATEGIES = P.STRATEGIES
# The costly strategies start only on an explicit request of the user.
ONLY_USER = {"full", "plenary"}
DOCUMENTS = ("PREAMBLE.md", "PIPELINE.md", "COORDINATOR_INSTRUCTIONS.md", "JURY.md", "ENVIRONMENT.md",
             "HYPOTHESIS_CARD.md", "README.md")
BLOCK = re.compile(r"<!-- ([a-z-]+(?::[a-z-]+)?) -->\n(.*?)\n<!-- /\1 -->", re.S)
GENERATED = S.GENERATED
MODEL_RE = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
AGENTS_DIR = ".claude/agents"
SKILLS_DIR = ".claude/skills"
# The targets: the coding agents the swarm generates for. For each: the folder and the extension of its agents (None:
# the target has no agents of its own), the folder of its skills, the file of its project instructions, its command.
# Codex, Antigravity, Gemini CLI and the generic target share one copy of the skills, in the open Agent Skills
# format (.agents/skills/<name>/SKILL.md).
SHARED_SKILLS_DIR = ".agents/skills"
TARGETS = {
    "claude": {"agents": (AGENTS_DIR, ".md"), "skills": SKILLS_DIR, "instructions": "CLAUDE.md", "cli": "claude"},
    "codex": {"agents": (".codex/agents", ".toml"), "skills": SHARED_SKILLS_DIR, "instructions": "AGENTS.md",
              "cli": "codex"},
    "antigravity": {"agents": (".agents/agents", ".md"), "skills": SHARED_SKILLS_DIR, "instructions": "AGENTS.md",
                    "cli": "agy"},
    "gemini": {"agents": (".gemini/agents", ".md"), "skills": SHARED_SKILLS_DIR, "instructions": "GEMINI.md",
               "cli": "gemini"},
    "agents": {"agents": None, "skills": SHARED_SKILLS_DIR, "instructions": "AGENTS.md", "cli": None},
}
# The command line tools `start` knows, in the order in which the first one found in the PATH is chosen.
CLIS = {"claude": "claude", "codex": "codex", "agy": "antigravity", "gemini": "gemini"}
# An installation that exists and does not name its targets is a Claude Code one (4.0, 5.0): it stays as it was.
DEFAULT_TARGETS = ("claude",)
INSTRUCTION_FILES = tuple(dict.fromkeys(v["instructions"] for v in TARGETS.values()))
SWARM_STATE = ("catalog.json", "VERSION")


class Error(C.Error):
    pass


class _Keep(dict):
    """For str.format_map: a missing placeholder stays as it is instead of failing."""

    def __missing__(self, k):
        return "{" + k + "}"


def fmt(template: str, **kw) -> str:
    try:
        return str(template).format_map(_Keep(kw))
    except (ValueError, IndexError):
        return str(template)


def i18n(swarm: Path, lang: str) -> dict:
    """The texts of the language over the English ones (en.json is the fallback of every key)."""
    swarm = Path(swarm)
    base = {}
    en = swarm / "i18n" / "en.json"
    if en.is_file():
        base = json.loads(en.read_text(encoding="utf-8"))
    p = swarm / "i18n" / f"{lang}.json"
    if lang != "en" and p.is_file():
        for k, v in json.loads(p.read_text(encoding="utf-8")).items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                base[k] = {**base[k], **v}
            else:
                base[k] = v
    return base


def available_languages(swarm: Path) -> list[str]:
    swarm = Path(swarm)
    docs = swarm / "docs"
    found = {p.name for p in docs.iterdir() if p.is_dir()} if docs.is_dir() else set()
    return sorted(l for l in found if (swarm / "i18n" / f"{l}.json").is_file())


def strategy_name(strategy: str, lang: str) -> str:
    """The localized name of a strategy (values.strategy)."""
    return strategy if lang == "en" else C.VALUES["strategy"].get(strategy, strategy)


def skill_names(lang: str, prefix: str) -> dict[str, str]:
    """strategy → skill name: <prefix>-<localized strategy>, auto → <prefix>."""
    return {s: prefix if s == "auto" else f"{prefix}-{strategy_name(s, lang)}" for s in STRATEGIES}


def all_skill_names() -> set[str]:
    """Every skill name the swarm may have generated (both prefixes, every language), those of every available
    extension included: so targets --remove, extensions --remove and remove clean them up."""
    out = set()
    for p in C.AGENT_PREFIXES:
        for l in C.LANGUAGES:
            out |= set(skill_names(l, p).values())
    for name, ids in extension_skill_ids(HERE.parent).items():
        for p in C.AGENT_PREFIXES:
            for l in C.LANGUAGES:
                out |= {f"{p}-{x}" for x in ids.get(l, {}).values()}
    return out


def extension_skill_ids(swarm: Path) -> dict:
    """extension → language → {skill id: localized skill id} (the i18n key skill_names of the extension)."""
    out = {}
    for name, m in E.manifests(swarm)[0].items():
        out[name] = {}
        for l in C.LANGUAGES:
            t = E.i18n(swarm, name, l)
            out[name][l] = {sid: t.get("skill_names", {}).get(sid, sid) for sid in m.get("skills", {})}
    return out


def extension_doc_names(swarm: Path) -> list[str]:
    """The canonical names of the documents of every available extension."""
    return sorted({d for m in E.manifests(swarm)[0].values() for d in m.get("documents", [])})


def extensions_data(swarm: Path, lang: str, names) -> list[dict]:
    """The enabled extensions as the generator uses them: texts, documents, skills, coordinator block."""
    ms = E.available(swarm)
    E.check_requires(ms, names, VERSION)
    out = []
    for name in names:
        m = ms[name]
        t = E.i18n(swarm, name, lang)
        docs = Path(swarm) / E.FOLDER / name / "docs"
        dl = lang if (docs / lang).is_dir() else "en"
        documents = {n: (docs / dl / n).read_text(encoding="utf-8") for n in m.get("documents", [])}
        skills = {}
        for sid, f in m.get("skills", {}).items():
            skills[sid] = {"name": t.get("skill_names", {}).get(sid, sid), "body": (docs / dl / f).read_text(encoding="utf-8"),
                           "description": t.get("skill_description", {}).get(sid, ""),
                           "arguments": t.get("skill_arguments", {}).get(sid, "")}
        out.append({"name": name, "version": m["version"], "documents": documents, "skills": skills,
                    "coordinator": E.block(swarm, name, dl, m["coordinator"]) if m.get("coordinator") else "",
                    "texts": t})
    return out


def parse_targets(value) -> list[str] | None:
    """A list of targets (a comma-separated text or a list) in the canonical order; None for «auto». An unknown name
    is an error."""
    items = value if isinstance(value, (list, tuple)) else str(value or "").split(",")
    items = [str(x).strip() for x in items if str(x).strip()]
    if items == ["auto"]:
        return None
    bad = [x for x in items if x not in TARGETS]
    if bad or not items:
        raise Error(f"unknown target «{', '.join(bad) or value}»: the targets are {', '.join(TARGETS)} (or auto)")
    return [x for x in TARGETS if x in items]


def detect_targets(root: Path) -> list[str]:
    """The targets of a project, from what it already has: .claude/ or CLAUDE.md → claude; .codex/ → codex;
    .agents/agents/ or .agents/rules/ → antigravity; .gemini/ or GEMINI.md → gemini; and always the generic target.
    A project with none of these (nor .agents/ or AGENTS.md) gets every target."""
    root = Path(root)
    signs = {"claude": (".claude", "CLAUDE.md"), "codex": (".codex",), "antigravity": (".agents/agents", ".agents/rules"),
             "gemini": (".gemini", "GEMINI.md"), "agents": (".agents", "AGENTS.md")}
    found = [t for t, names in signs.items() if any((root / n).exists() for n in names)]
    if not found:
        return list(TARGETS)
    return [t for t in TARGETS if t in found or t == "agents"]


def targets_of(root: Path) -> list[str]:
    """The active targets: the key of config.json; without it, Claude Code only (an installation 4.0 or 5.0)."""
    cfg = S.config(root)
    if cfg.get("targets") is None:
        return list(DEFAULT_TARGETS)
    out = parse_targets(cfg["targets"])
    if out is None:
        raise Error("config.json: targets «auto» is resolved at installation: write the list of the targets")
    return out


def agent_dirs() -> list[tuple[str, str]]:
    """(folder, extension) of the agents of every target, active or not."""
    return [v["agents"] for v in TARGETS.values() if v["agents"]]


def skill_dirs() -> list[str]:
    return list(dict.fromkeys(v["skills"] for v in TARGETS.values()))


def _unmarked_agents(root: Path, prefix: str) -> bool:
    d = Path(root) / AGENTS_DIR
    return d.is_dir() and any(not S.is_generated(p) for p in d.glob(f"{prefix}-*.md"))


def prefix_of(root: Path, lang: str) -> str:
    """The prefix of agents and skills (D): config.prefix; otherwise the 4.0 prefix if the language is it, or if the
    project manages its own agents and has 4.0-prefixed agents without the note; otherwise «swarmer»."""
    cfg = S.config(root)
    if cfg.get("prefix"):
        p = str(cfg["prefix"])
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", p):
            raise Error(f"prefix «{p}»: a lower-case name is needed")
        return p
    old = C.AGENT_PREFIXES[1]
    if lang == "it" or (cfg.get("project_managed") and _unmarked_agents(root, old)):
        return old
    return C.AGENT_PREFIXES[0]


def blocks(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2).strip() for m in BLOCK.finditer(text)}


def profiles(text: str, ids: set[str]) -> dict[str, dict]:
    """The profile table of PIPELINE.md: `| `id` | [shown name |] for | A | B | translates | f3 | f4 |`."""
    found = {}
    for line in text.splitlines():
        m = re.match(r"^\| `([a-z-]+)` \|(.*)\|\s*$", line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).split("|")]
        if len(cells) == 7:
            cells = cells[1:]   # the localized name shown in a column
        if len(cells) != 6:
            raise Error(f"profile {m.group(1)}: {len(cells)} columns instead of 6")
        for_, a, b, translates, f3, f4 = cells

        def roles_of(cell):
            names = re.findall(r"[a-z]+(?:-[a-z]+)*", cell)
            return [n for n in dict.fromkeys(names) if n in ids]
        if m.group(1) in found:
            raise Error(f"two profiles named {m.group(1)}")
        found[m.group(1)] = {"for": for_, "A": roles_of(a), "B": roles_of(b), "translates": roles_of(translates),
                             "f3": roles_of(f3), "f4": roles_of(f4)}
    if "general" not in found:
        raise Error("the general profile is missing")
    return found


# --- the local translations (K.2, K.3) ---

def translations_dir(swarm: Path, lang: str) -> Path:
    """<swarm>/local/translations/<lang>/ under the names of the language of the installation (or the ones that
    exist, A.4). Never distributed nor published: it is inside the fixed local folder."""
    loc = S.fixed_local(swarm)
    return S.find_project_file(loc, "translations", S.installed_language(swarm), swarm) / lang


def translation_sha(texts: dict) -> str:
    """The fingerprint of the texts of a translation, as `translate` writes them."""
    return hashlib.sha256(json.dumps({k: texts.get(k) for k in P.TEXT_FIELDS}, ensure_ascii=False,
                                     sort_keys=True).encode("utf-8")).hexdigest()


def read_translation(p: Path) -> tuple[dict, bool]:
    """A file of the overlay: (the texts in canonical form, whether it was modified by hand after `translate`)."""
    if p.is_symlink():
        raise Error(f"{p} is a symbolic link")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise Error(f"{p}: an object is needed")
        obj = C.to_canonical(raw, C.TRANSLATION_SCHEMA, str(p))
    except (OSError, json.JSONDecodeError) as e:
        raise Error(f"{p}: not readable: {e}")
    texts = {k: obj.get(k) for k in P.TEXT_FIELDS}
    return texts, obj.get("written_sha256") != translation_sha(texts)


def translations(swarm: Path, lang: str) -> dict[str, tuple[dict, bool]]:
    """The local translations of the language: id → (texts, modified by hand). An invalid one is an error."""
    d = translations_dir(swarm, lang)
    out = {}
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.json")):
        texts, modified = read_translation(p)
        errors = P.text_problems(texts, f"{p.name}", lang)
        if errors:
            raise Error(f"local translation {p}: " + "; ".join(errors[:5]))
        out[p.stem] = (texts, modified)
    return out


def with_translations(d: dict, swarm: Path, lang: str) -> tuple[dict, list[str]]:
    """The database as the installation generates it in `lang`, and the ids still waiting for a translation. A local
    translation fills a language the database does not have; when the public database brings its own, the public one
    wins, unless the local one was modified by hand (K.3). The database on disk does not change."""
    local = translations(swarm, lang)
    entries, pending = [], []
    for v in d["entries"]:
        texts = dict(v.get("texts", {}))
        o = local.get(v.get("id"))
        if o and (o[1] or lang not in texts):
            texts[lang] = o[0]
        if lang not in texts and v.get("status", "active") == "active":
            pending.append(v["id"])
        entries.append(dict(v, texts=texts))
    return dict(d, entries=entries), pending


def doc_name(swarm: Path, canonical: str, lang: str) -> str:
    return S.localized_name(swarm, canonical, lang)


def catalog(swarm: Path, root: Path, lang: str, extensions=None) -> dict:
    """Everything needed to generate: roles (generic and local, local first), profiles, texts, the enabled
    extensions (`extensions`: those names instead of the ones of config.json, for verify)."""
    swarm, root = Path(swarm), Path(root)
    cfg = S.config(root)
    ext = extensions_data(swarm, lang, E.enabled(root) if extensions is None else list(extensions))
    d = P.load(swarm / "db")
    # the installation generates also the entries without its language (K.2): English is checked by verify and propose
    errors = P.validate(d, [lang], existing=[v.get("id") for v in d["entries"]], required=())
    d, pending = with_translations(d, swarm, lang)
    if errors:
        raise Error("invalid database:\n  " + "\n  ".join(errors[:20]))
    t = i18n(swarm, lang)
    docs = swarm / "docs" / lang
    if not docs.is_dir():
        raise Error(f"language «{lang}» without documents: the languages are {', '.join(available_languages(swarm))}")
    texts = {n: (docs / n).read_text(encoding="utf-8") for n in DOCUMENTS if (docs / n).is_file()}
    for n in DOCUMENTS:
        if n not in texts:
            raise Error(f"docs/{lang}/{n} is missing")
    pre, pipe, instr, envb = (blocks(texts[n]) for n in ("PREAMBLE.md", "PIPELINE.md", "COORDINATOR_INSTRUCTIONS.md",
                                                          "ENVIRONMENT.md"))
    for key, where in (("rules-in-short", pre), ("profiles", pipe), ("brief", pipe), ("coordinator", instr),
                       ("delegation", instr), ("environment:project", instr), ("environment", envb)):
        if key not in where:
            raise Error(f"docs/{lang}: the block «{key}» is missing")
    for s in STRATEGIES:
        if f"strategy:{s}" not in pipe:
            raise Error(f"docs/{lang}/PIPELINE.md: the block strategy:{s} is missing")
    prefix = prefix_of(root, lang)
    targets = targets_of(root)
    local_file = S.local_agents_file(root, swarm)
    locals_ = P.local_cards(local_file)
    rules = pre["rules-in-short"]
    roles = []
    for v in P.ordered(d):
        tv = P.text(v, lang)
        r = {"n": v["number"], "id": v["id"], "name": tv["name"], "core": v["core"], "type": v["type"],
             "parent": v.get("parent"), "short": tv["short"], "keywords": tv["keywords"],
             "card": P.card(d, v, lang, prefix).strip(), "origin": "generic"}
        if v["id"] in pending:
            r["translation_pending"] = lang
        if v["id"] in locals_:
            loc = locals_.pop(v["id"])
            r.update({"name": loc["name"], "short": loc["short"] or r["short"], "card": loc["card"], "origin": "local"})
            r.pop("translation_pending", None)   # the local card is the project's text
        roles.append(r)
    for cid, loc in locals_.items():   # the local-only roles
        roles.append({"n": f"L{loc['number']}", "id": cid, "name": loc["name"], "core": "local",
                      "type": "professional", "parent": None, "short": loc["short"], "keywords": [],
                      "card": loc["card"], "origin": "local-only"})
    ids = {r["id"] for r in roles}
    core_names = {n["id"]: P.core_name(d, n["id"], lang) for n in d["cores"]}
    core_names["local"] = t.get("local_core", "local")
    for r in roles:
        r["description"] = description(dict(r, core=core_names.get(r["core"], r["core"]).lower()), t, prefix)
        r["prompt"] = role_prompt(r, rules, t)
    table = profiles(pipe["profiles"], ids)
    fingerprint = hashlib.sha256(json.dumps([d["entries"], d["cores"], sorted(texts.items()),
                                             [(r["id"], r["card"]) for r in roles if r["origin"] != "generic"]]
                                            + ([[(x["name"], x["version"], sorted(x["documents"].items()),
                                                  sorted((k, v["body"]) for k, v in x["skills"].items()))
                                                 for x in ext]] if ext else []),
                                            ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    cores = [{"id": n["id"], "name": P.core_name(d, n["id"], lang)} for n in d["cores"]]
    if any(r["core"] == "local" for r in roles):
        cores.append({"id": "local", "name": core_names["local"]})
    for who, m in cfg.get("models", {}).items():
        if not MODEL_RE.match(str(m)) or not re.match(r"^[a-z0-9*][a-z0-9-]*$", str(who)):
            raise Error(f"models: «{who}={m}» is not a valid role and model name")
    default_folder = S.localized_name(swarm, "swarmer", lang)
    try:
        folder = swarm.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        folder = default_folder
    try:
        loc = S.local_folder(root, swarm).resolve().relative_to(root.resolve()).as_posix()
        loc_file = local_file.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        lf = S.localized_name(swarm, "local", lang)
        loc, loc_file = f"{folder}/{lf}", f"{folder}/{lf}/{S.localized_name(swarm, 'AGENTS.md', lang)}"
    return {
        "folder": folder, "local_folder": loc, "local_file": loc_file,
        "version": VERSION, "language": lang, "fingerprint": fingerprint, "prefix": prefix, "targets": targets,
        "cores": cores,
        "roles": roles, "profiles": table, "models": cfg.get("models", {}),
        "translation_pending": [r["id"] for r in roles if r.get("translation_pending")],
        "project_managed": bool(cfg.get("project_managed", False)),
        "texts": {"rules": rules, "brief": pipe["brief"], "coordinator": instr["coordinator"],
                  "strategies": {s: pipe[f"strategy:{s}"] for s in STRATEGIES}, "profiles": pipe["profiles"],
                  "delegation": instr["delegation"], "environment": envb["environment"],
                  "environments": {"project": instr["environment:project"]},
                  "agent_environments": {"project": t.get("agent_environment", ""),
                                         "without-tools": t.get("environment_without_tools", "")}},
        "documents": texts, "agents_head": t.get("agents_head", ""), "i18n": t, "db": d,
        "extensions": ext,
        "names": {"swarm": default_folder, "local": S.localized_name(swarm, "local", lang),
                  "agents": S.localized_name(swarm, "AGENTS.md", lang),
                  "docs": {n: doc_name(swarm, n, lang) for n in DOCUMENTS + ("AGENTS.md",)}},
    }


def description(r: dict, t: dict, prefix: str) -> str:
    kind = fmt(t.get("sub_of", ""), parent=f"{r['parent']}", prefix=prefix) if r["type"] == "subprofessional" else ""
    return f"{r['name']}: {r['short']}{kind} {fmt(t.get('description_tail', ''), core=r['core'])}"


def role_prompt(r: dict, rules: str, t: dict) -> str:
    return (fmt(t.get("role_prompt", ""), name=r["name"], n=r["n"], short=r["short"])
            + f"\n\n{rules}\n\n## {t.get('your_card', 'your_card')}\n\n{r['card']}\n")


def adapt(data: dict, text: str) -> str:
    """The texts speak of `<default folder>/` and of `<default folder>/<local>/` (swarmer/ and swarmer/local/ in
    English, their localized names in another language): in an installation in another folder they become the real
    ones."""
    names = data.get("names", {})
    dflt = names.get("swarm", "swarmer")
    dlocal = f"{dflt}/{names.get('local', 'local')}"
    dfile = f"{dlocal}/{names.get('agents', 'AGENTS.md')}"
    if data.get("folder", dflt) == dflt and data.get("local_folder", dlocal) == dlocal \
            and data.get("local_file", dfile) == dfile:
        return text
    text = text.replace(dfile, "\0LOCALF\0").replace(dlocal + "/", "\0LOCALD\0")
    text = re.sub(r"(?<![A-Za-z0-9_.-])" + re.escape(dflt) + r"/(?=[A-Za-z_.`])", data["folder"] + "/", text)
    return text.replace("\0LOCALF\0", data["local_file"]).replace("\0LOCALD\0", data["local_folder"] + "/")


def model(data: dict, r: dict) -> str:
    m = data["models"]
    return m.get(r["id"]) or m.get(r["core"]) or m.get("*") or "inherit"


def toml_string(s: str) -> str:
    """A TOML multi-line basic string: backslashes and quotes escaped, the control characters as \\uXXXX (TOML 1.0)."""
    out = []
    for ch in s:
        o = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch in "\n\t":
            out.append(ch)
        elif o < 0x20 or o == 0x7F:
            out.append(f"\\u{o:04X}")
        else:
            out.append(ch)
    return '"""\n' + "".join(out) + '"""'


def toml_line(s: str) -> str:
    """A TOML basic string on one line."""
    return toml_string(s)[4:-3].replace("\n", "\\n").join('""')


def yaml_str(s: str) -> str:
    """A YAML double-quoted scalar: the JSON form, with the characters YAML 1.1 reads as line breaks (NEL, LS, PS)
    escaped, so that a head never breaks."""
    out = json.dumps(s, ensure_ascii=False)
    for ch in ("\x85", " ", " "):
        out = out.replace(ch, f"\\u{ord(ch):04x}")
    return out


def agent_note(data: dict, r: dict) -> str:
    t = data["i18n"]
    text = fmt(t.get("agent_note", ""), n=r["n"], name=" ".join(r["name"].split()))
    if r.get("translation_pending"):
        text += f"; {C.TRANSLATION_PENDING}: {r['translation_pending']}"
    return text


def agent(data: dict, r: dict, target: str = "claude") -> str:
    """The agent of a role for a target: Claude Code, Antigravity and Gemini CLI read a Markdown file with a YAML
    head (the body is the system prompt); Codex a TOML file with name, description and developer_instructions."""
    name = f"{data['prefix']}-{r['id']}"
    body = adapt(data, f"{r['prompt']}\n{data['texts']['agent_environments']['project']}\n")
    if target == "codex":
        return (S.toml_note(agent_note(data, r), data["language"]) + "\n"
                f"name = {toml_line(name)}\ndescription = {toml_line(r['description'])}\n"
                f"developer_instructions = {toml_string(body)}\n")
    head = [f"name: {name}", f"description: {yaml_str(r['description'])}"]
    if target == "claude":
        head.append(f"model: {model(data, r)}")
    elif target == "antigravity":
        head += ["subagent: true", "mainAgent: false"]
    note = S.note(agent_note(data, r), data["language"])
    return "---\n" + "\n".join(head) + f"\n---\n\n{note}\n\n" + body


def roles_index(data: dict) -> str:
    t = data["i18n"]
    names = {n["id"]: n["name"] for n in data["cores"]}
    lines = [f"## {t.get('roles_title', '')}", "", t.get("index_explains", ""), "", t.get("index_head", ""),
             "|---|---|---|---|---|"]
    for r in data["roles"]:
        kind = (fmt(t.get("type_sub", ""), parent=r["parent"], prefix=data["prefix"]) if r["type"] == "subprofessional"
                else t.get("type_professional", ""))
        if r["origin"] != "generic":
            kind += f" ({t.get('origin_' + r['origin'].replace('-', '_'), r['origin'])})"
        if r.get("translation_pending"):
            kind += f" ({C.TRANSLATION_PENDING}: {r['translation_pending']})"
        lines.append(f"| `{data['prefix']}-{r['id']}` | {r['name']} | {names.get(r['core'], r['core']).lower()} | {kind} | "
                     f"{', '.join(r['keywords'])} |")
    return "\n".join(lines)


def skill(data: dict, strategy: str, target: str = "claude") -> str:
    """The skill of a strategy. Claude Code (.claude/skills) has its own fields (argument-hint,
    disable-model-invocation, $ARGUMENTS); the shared copy (.agents/skills) keeps to the open Agent Skills format:
    name and description only."""
    t, x = data["i18n"], data["texts"]
    name = skill_names(data["language"], data["prefix"])[strategy]
    head = ["---", f"name: {name}",
            f"description: {yaml_str(t.get('skill_description', {}).get(strategy, ''))}"]
    if target == "claude":
        head.append(f"argument-hint: {yaml_str(t.get('skill_arguments', ''))}")
        if strategy in ONLY_USER:
            head.append("disable-model-invocation: true")
    head.append("---")
    parts = ["\n".join(head), S.note(t.get("skill_note", ""), data["language"]),
             f"# {t.get('skill_title', {}).get(strategy, strategy)}", x["coordinator"]]
    parts += [e["coordinator"] for e in data.get("extensions", []) if e["coordinator"]]
    parts += [x["brief"], x["environment"]]
    st = x["strategies"]
    if strategy == "auto":
        parts += [t.get("auto_preamble", "")] + [st[s] for s in ("auto", "single", "fan-out", "classic", "jury",
                                                                 "light-jury", "full", "plenary", "expert")]
    elif strategy == "full":
        parts += [t.get("full_preamble", ""), st["full"], st["classic"]]
    elif strategy == "plenary":
        parts += [t.get("plenary_preamble", ""), st["plenary"], st["full"], st["jury"]]
    else:
        parts += [fmt(t.get("strategy_is", ""), strategy=strategy_name(strategy, data["language"])), st[strategy]]
    if strategy not in ("single", "expert"):
        parts.append(x["profiles"])
    request = t.get("the_request", "") if target == "claude" else t.get("the_request_generic", "")
    parts += [roles_index(data), x["delegation"], x["environments"]["project"], request]
    text = "\n\n".join(parts) + "\n"
    yaml_head, _, body = text.partition("\n---\n")
    return yaml_head + "\n---\n" + adapt(data, body)


def extension_skill(data: dict, sk: dict, target: str = "claude") -> str:
    """The skill of an extension: name and description (argument-hint in Claude Code), the note, the body."""
    name = f"{data['prefix']}-{sk['name']}"
    head = ["---", f"name: {name}", f"description: {yaml_str(sk['description'])}"]
    if target == "claude":
        head.append(f"argument-hint: {yaml_str(sk['arguments'])}")
    head.append("---")
    body = sk["body"] if sk["body"].endswith("\n") else sk["body"] + "\n"
    return "\n".join(head) + "\n" + S.note(data["i18n"].get("skill_note", ""), data["language"]) + "\n\n" + adapt(data, body)


def project_owned(data: dict, r: dict, target: str) -> bool:
    """The agent of a role that the project itself generates: with `project_managed`, the overrides in Claude Code."""
    return bool(data.get("project_managed")) and r["origin"] != "generic" and target == "claude"


def generated_files(data: dict) -> dict[str, str]:
    """Path relative to the project root → text. With `project_managed` the project generates the agents of its
    overrides for Claude Code only (.claude/agents): there they are not written; in the other targets the swarm
    writes them from the local cards (a file of the project without the note still wins, see `write`)."""
    files = {}
    targets = data.get("targets", list(DEFAULT_TARGETS))
    for tg in targets:
        if not TARGETS[tg]["agents"]:
            continue
        folder, ext = TARGETS[tg]["agents"]
        for r in data["roles"]:
            if project_owned(data, r, tg):
                continue
            files[f"{folder}/{data['prefix']}-{r['id']}{ext}"] = agent(data, r, tg)
    for tg in targets:
        kind = "claude" if TARGETS[tg]["skills"] == SKILLS_DIR else "shared"
        for s, name in skill_names(data["language"], data["prefix"]).items():
            rel = f"{TARGETS[tg]['skills']}/{name}/SKILL.md"
            if rel not in files:
                files[rel] = skill(data, s, kind)
        for e in data.get("extensions", []):
            for sk in e["skills"].values():
                rel = f"{TARGETS[tg]['skills']}/{data['prefix']}-{sk['name']}/SKILL.md"
                if rel not in files:
                    files[rel] = extension_skill(data, sk, kind)
    return files


def catalog_json(data: dict) -> dict:
    cat = {k: v for k, v in data.items() if k not in ("documents", "i18n", "agents_head", "roles", "names", "db",
                                                      "extensions")}
    cat["roles"] = [dict(r) for r in data["roles"]]
    if data.get("extensions"):
        cat["extensions"] = [{"name": e["name"], "version": e["version"]} for e in data["extensions"]]
    return cat


def swarm_files(data: dict, swarm: Path) -> dict[str, str]:
    """The files generated inside the swarm folder: catalog, version, documents in the language, AGENTS.md."""
    out = {"catalog.json": json.dumps(catalog_json(data), ensure_ascii=False, indent=1) + "\n",
           "VERSION": f"{data['version']} {data['fingerprint'][:12]} {data['language']}\n"}
    note = S.note(data["i18n"].get("document_note", ""), data["language"]) + "\n"
    for n, text in data["documents"].items():
        out[data["names"]["docs"][n]] = note + adapt(data, text)
    d = data.get("db") or P.load(Path(swarm) / "db")
    out[data["names"]["docs"]["AGENTS.md"]] = note + adapt(data, P.agents_md(d, data["language"], data["agents_head"],
                                                                             data["prefix"]))
    for e in data.get("extensions", []):
        for n, text in e["documents"].items():
            out[S.localized_name(swarm, n, data["language"])] = note + adapt(data, text)
    return out


def other_doc_names(swarm: Path, data: dict) -> set[str]:
    """The names the generated documents have in the other languages (and in the 4.0), not used now."""
    now = set(data["names"]["docs"].values()) | {S.localized_name(swarm, n, data["language"])
                                                 for e in data.get("extensions", []) for n in e["documents"]}
    out = set()
    for n in DOCUMENTS + ("AGENTS.md",) + tuple(extension_doc_names(swarm)):
        out |= set(S.all_names(swarm, n))
        if n in C.OLD_DOCS:
            out.add(C.OLD_DOCS[n])
    return out - now


def _safe(base: Path, rel: str) -> Path:
    try:
        return S.no_links(base, Path(base) / rel)
    except S.Error as e:
        raise Error(str(e))


def scanned(targets, clean=()) -> tuple[list[tuple[str, str]], list[str]]:
    """The agent folders (with their extension) and the skill folders the swarm looks into: those of the active
    targets and of the targets removed explicitly (`clean`). The other targets are neither touched nor examined."""
    tgs = [t for t in TARGETS if t in set(targets) | set(clean)]
    agents = list(dict.fromkeys(TARGETS[t]["agents"] for t in tgs if TARGETS[t]["agents"]))
    skills = list(dict.fromkeys(TARGETS[t]["skills"] for t in tgs))
    return agents, skills


def _stale_agents(root: Path, dirs=None) -> list[Path]:
    """The agents of the swarm's prefixes in the given folders (default: every target)."""
    out = []
    for folder, ext in (agent_dirs() if dirs is None else dirs):
        d = Path(root) / folder
        if d.is_dir() and not d.is_symlink():
            out += sorted(p for pre in C.AGENT_PREFIXES for p in d.glob(f"{pre}-*{ext}"))
    return out


def _stale_skills(root: Path, dirs=None) -> list[Path]:
    return [Path(root) / d / n / "SKILL.md" for d in (skill_dirs() if dirs is None else dirs)
            for n in sorted(all_skill_names())]


def preflight(root: Path, targets, clean=(), rels=()) -> None:
    """Before any write: no symbolic link in the folders of the active targets and of those removed explicitly, nor
    in their files of the swarm, nor in the paths `rels` (relative to the root). A link elsewhere (an inactive
    target) is not looked at."""
    root = Path(root)
    agents, skills = scanned(targets, clean)
    paths = [root / f for f, _e in agents] + [root / d for d in skills]
    for folder, ext in agents:
        d = root / folder
        if d.is_dir() and not d.is_symlink():
            paths += [p for pre in C.AGENT_PREFIXES for p in d.glob(f"{pre}-*")]
    for d in skills:
        if (root / d).is_dir() and not (root / d).is_symlink():
            for n in sorted(all_skill_names()):
                paths += [root / d / n, root / d / n / "SKILL.md"]
    paths += [root / r for r in rels]
    for p in paths:
        _safe(root, p.relative_to(root).as_posix())


def _shadowed(root: Path, rel: str, replaceable: frozenset = frozenset()) -> bool:
    """An agent <prefix>-<id> whose id the project already has under the other prefix, without the note: the
    project's agent stands for the role (as an override), and a second definition of the same juror is not written."""
    folder = Path(rel).parent.as_posix()
    if folder not in {f for f, _e in agent_dirs()}:
        return False
    d = Path(root) / folder
    name = Path(rel).name
    for pre in C.AGENT_PREFIXES:
        if name.startswith(pre + "-"):
            for other in C.AGENT_PREFIXES:
                q = d / (other + name[len(pre):])
                if (other != pre and q.is_file() and not S.is_generated(q)
                        and q.relative_to(root).as_posix() not in replaceable):
                    return True
    return False


def write(swarm: Path, root: Path, data: dict, replaceable: frozenset = frozenset(), clean=()) -> list[str]:
    """Writes what it generates. Never overwrites a file that does not carry the GENERATED note; removes only its own
    files that are no longer needed (also those of the other prefix or language, if they carry the note), in the
    folders of the active targets and of the targets removed explicitly (`clean`). Every path is checked before the
    first write."""
    swarm, root = Path(swarm), Path(root)
    done, skipped = [], []
    files = generated_files(data)
    agent_d, skill_d = scanned(data.get("targets", DEFAULT_TARGETS), clean)
    preflight(root, data.get("targets", DEFAULT_TARGETS), clean, rels=list(files))
    sw = swarm_files(data, swarm)
    for rel in list(sw) + sorted(other_doc_names(swarm, data)):
        _safe(swarm, rel)
    for rel, text in files.items():
        p = _safe(root, rel)
        if (p.exists() and not S.is_generated(p) and rel not in replaceable) or _shadowed(root, rel, replaceable):
            skipped.append(rel)
            continue
        S.write(root, p, text)
        done.append(rel)
    for p in _stale_agents(root, agent_d) + _stale_skills(root, skill_d):
        rel = p.relative_to(root).as_posix()
        if ((rel not in files or _shadowed(root, rel, replaceable)) and p.is_file()
                and (S.is_generated(p) or rel in replaceable)):
            S.remove_file(root, p)
            done.append(f"-{rel}")
            if p.parent.parent.name == "skills" and p.parent.is_dir() and not any(p.parent.iterdir()):
                p.parent.rmdir()
            _prune_empty(root, p.parent)
    for rel, text in sw.items():
        p = _safe(swarm, rel)
        if p.exists() and not S.is_generated(p) and rel not in SWARM_STATE and f"@swarm/{rel}" not in replaceable:
            skipped.append(f"{swarm.name}/{rel}")
            continue
        S.write(swarm, p, text)
    for rel in sorted(other_doc_names(swarm, data)):
        p = swarm / rel
        if p.is_file() and not p.is_symlink() and (S.is_generated(p) or f"@swarm/{rel}" in replaceable):
            S.remove_file(swarm, p)
            done.append(f"-{swarm.name}/{rel}")
    return done + [f"skipped: {s}" for s in skipped]


def _prune_empty(root: Path, d: Path) -> None:
    """The folders of a target left empty by a removal (.codex/agents, .codex, …), up to the project root. The
    folders of Claude Code stay, as before 5.1."""
    root = Path(root)
    if d == root or root not in d.parents or d.relative_to(root).parts[0] == ".claude":
        return
    while not d.exists() and d != root:   # a skill folder already removed
        d = d.parent
    while d != root and root in d.parents and d.is_dir() and not d.is_symlink() and not any(d.iterdir()):
        d.rmdir()
        d = d.parent


def check(swarm: Path, root: Path, data: dict) -> list[str]:
    """What differs from what `write` would produce, in the active targets only. With `project_managed`, an agent
    of an override that the project has not generated in .claude/agents is reported as missing too."""
    different = []
    files = generated_files(data)
    agent_d, skill_d = scanned(data.get("targets", DEFAULT_TARGETS))
    for p in _stale_agents(root, agent_d) + _stale_skills(root, skill_d):
        rel = p.relative_to(root).as_posix()
        if rel not in files and S.is_generated(p):
            different.append(f"extra {rel}")   # of a role, a language or a target no longer generated
    if "claude" in data.get("targets", DEFAULT_TARGETS):
        for r in data["roles"]:
            if project_owned(data, r, "claude") and not any(
                    (Path(root) / AGENTS_DIR / f"{pre}-{r['id']}.md").is_file() for pre in C.AGENT_PREFIXES):
                different.append(f"missing {AGENTS_DIR}/{data['prefix']}-{r['id']}.md (project_managed: the project "
                                 "generates it)")
    for rel, text in files.items():
        p = Path(root) / rel
        if _shadowed(root, rel):
            if p.is_file() and S.is_generated(p):
                different.append(f"different {rel}")   # a second definition of the role: regenerate removes it
            continue
        if not p.is_file():
            different.append(f"missing {rel}")
        elif S.is_generated(p) and p.read_text(encoding="utf-8") != text:
            different.append(f"different {rel}")
    for rel, text in swarm_files(data, swarm).items():
        p = Path(swarm) / rel
        if p.is_file() and (S.is_generated(p) or rel in SWARM_STATE) and p.read_text(encoding="utf-8") != text:
            different.append(f"different {Path(swarm).name}/{rel}")
    return different


def override_notes(root: Path, data: dict) -> list[str]:
    """The agents of .claude/agents without the note that stand for a generic role (a hand-written override): the
    other active targets get the generic text. Only a notice, never a failure."""
    root = Path(root)
    targets = data.get("targets", DEFAULT_TARGETS)
    others = [t for t in targets if t != "claude" and TARGETS[t]["agents"]]
    if "claude" not in targets or not others:
        return []
    out = []
    for r in data["roles"]:
        if r["origin"] != "generic":
            continue
        for pre in C.AGENT_PREFIXES:
            p = root / AGENTS_DIR / f"{pre}-{r['id']}.md"
            if p.is_file() and not p.is_symlink() and not S.is_generated(p):
                out.append(f"override only in {AGENTS_DIR}: {p.name} ({', '.join(others)}: the generic text; "
                           f"a local card reaches every target)")
                break
    return out


def replaceable_31(swarm: Path, root: Path) -> frozenset:
    """The files of a 3.x installation to replace: the agents of the ids of its catalog with the note of the 3.x,
    its four skills and its documents. Never a file for the note alone: other generators use the same note."""
    n = C.NOTES_31
    v = Path(swarm) / n["version"]
    if not v.is_file() or not v.read_text(encoding="utf-8").startswith("3."):
        return frozenset()
    try:
        cat = json.loads((Path(swarm) / n["catalog"]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return frozenset()
    out = set()
    old = C.AGENT_PREFIXES[1]
    for r in cat.get(n["roles"], []):
        rel = f"{AGENTS_DIR}/{old}-{r[n['id']]}.md"
        p = Path(root) / rel
        if p.is_file() and n["agent"] in p.read_text(encoding="utf-8")[:800] \
                and r.get("prompt", "")[:80] in p.read_text(encoding="utf-8"):
            out.add(rel)
    for name in n["skills"]:
        rel = f"{SKILLS_DIR}/{name}/SKILL.md"
        p = Path(root) / rel
        if p.is_file() and n["skill"] in p.read_text(encoding="utf-8")[:800]:
            out.add(rel)
    for d in n["docs"]:
        out.add(f"@swarm/{d}")
    return frozenset(out)


def remove(root: Path) -> list[str]:
    """The explicit removal: the generated files of every target, active or not, after checking every folder."""
    removed = []
    root = Path(root)
    preflight(root, list(TARGETS))
    for p in _stale_agents(root):
        if S.is_generated(p):
            S.remove_file(root, p)
            removed.append(p.relative_to(root).as_posix())
    for p in _stale_skills(root):
        if S.is_generated(p):
            S.remove_file(root, p)
            removed.append(p.relative_to(root).as_posix())
            if not any(p.parent.iterdir()):
                p.parent.rmdir()
    for rel in removed:
        _prune_empty(root, (root / rel).parent)
    return removed
