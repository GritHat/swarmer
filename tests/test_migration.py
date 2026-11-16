#!/usr/bin/env python3
"""Test battery of the migration from the 4.0 swarm to swarmer 5.0: python3 -I -B tests/test_migration.py

The checks M1–M3, M6–M10, M14, M15 of the specification (M4, M5, M11–M13 are in tests/test_jury.py), the four checks
K.4 of the translations (English public database, local overlay) and the check of the Italian words left in the code. The 4.0 installations are made with tests/fixtures/sciame-4.0.sh (the sciame.sh
of the 4.0, byte for byte); the 4.0 convening comes from tests/fixtures/convening-4.0/. An installed copy does not
carry the fixtures: the checks that need them are skipped, saying so. The Italian strings of this file are test data
(the names a 4.0 project has on disk). Exits with 1 if a check fails.
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent
ENGINE = SOURCE / "engine" / "swarmer.py"
FIXTURES = HERE / "fixtures"
OLD_SH = FIXTURES / "sciame-4.0.sh"
COPY_IGNORE = shutil.ignore_patterns(".git", "_work", "_lavoro", "_v31", "__pycache__")
results = []
sys.dont_write_bytecode = True
sys.path.insert(0, str(SOURCE / "engine"))
import compat as C  # noqa: E402
import paths as S  # noqa: E402
import professionals as P  # noqa: E402


def i18n(lang):
    out = json.loads((SOURCE / "i18n" / "en.json").read_text(encoding="utf-8"))
    p = SOURCE / "i18n" / f"{lang}.json"
    if p.is_file():
        out.update(json.loads(p.read_text(encoding="utf-8")))
    return out


EN, IT = i18n("en"), i18n("it")


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("ok   " if ok else "FAILED ") + name + ("" if ok or not detail else f"\n     {str(detail)[:700]}"))


def skip(name, why):
    print(f"skipped {name}: {why}")


def clean_env(**extra):
    """The environment without the variables of the swarm and without claude on the PATH: no check of this battery
    may open a Claude session."""
    e = {k: v for k, v in os.environ.items() if not k.startswith(("SWARMER_", "SCIAME_"))}
    e["PATH"] = os.pathsep.join(d for d in e.get("PATH", "").split(os.pathsep)
                                if d and not os.path.exists(os.path.join(d, "claude")))
    e.update(extra)
    return e


def py(*arg, cwd=None, env=None):
    p = subprocess.run([sys.executable, "-I", "-B", *map(str, arg)], capture_output=True, text=True, cwd=cwd,
                       stdin=subprocess.DEVNULL, env=env or clean_env())
    return p.returncode, p.stdout + p.stderr


def bash(*arg, cwd=None, env=None):
    p = subprocess.run(["bash", *map(str, arg)], capture_output=True, text=True, cwd=cwd, stdin=subprocess.DEVNULL,
                       env=env or clean_env())
    return p.returncode, p.stdout + p.stderr


def tree(root: Path, skip_dir: str | None = None) -> dict[str, bytes]:
    root = Path(root)
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and not p.is_symlink() and (skip_dir is None or p.relative_to(root).parts[0] != skip_dir)}


def names(d: Path) -> set[str]:
    return {p.name for p in Path(d).iterdir()} if Path(d).is_dir() else set()


def aligned(out):
    return any(t["cli_aligned"].split("{profiles}")[1].strip() in out for t in (EN, IT))


def text_part(template: str) -> str:
    """The longest literal part of an i18n template (between the placeholders)."""
    return max(re.split(r"\{[a-z_]+\}", template), key=len).strip()


def install5(root: Path, *extra):
    root.mkdir(parents=True, exist_ok=True)
    return py(ENGINE, "install", "--from", SOURCE, "--root", root, *extra)


def update5(root: Path, *extra):
    return bash(SOURCE / "swarmer.sh", "-C", root, "update", *extra)


def install40(root: Path, *extra):
    root.mkdir(parents=True, exist_ok=True)
    return bash(OLD_SH, "-C", root, "installa", *extra)


def entry40(rid):
    """An entry in the format 1 of the 4.0 (Italian keys), as the 4.0 approva wanted it."""
    return {"sigla": rid, "tipo": "professionista", "nucleo": "critico",
            "testi": {l: {"nome": f"Voce {l}", "breve": "una voce di prova.", "parole": ["prova"],
                          "corpo": "**Missione.** Provare.\n"} for l in ("it", "en")}}


def project40(base: Path, name: str) -> Path:
    """An Italian 4.0 installation as a real project has it: .sciame/config.json with the three 4.0 keys, a local
    override, an agent of the project without the note, the expert request register with rows, locale/VIETATE.txt,
    an entry approved in the database and the 4.0 paragraph in CLAUDE.md."""
    r = base / name
    rc, out = install40(r)
    assert rc == 0, out
    s = r / "sciame"
    (r / ".sciame").mkdir(exist_ok=True)
    (r / ".sciame" / "config.json").write_text(json.dumps({"cartella": "sciame", "locale": "sciame/locale",
                                                           "gestiti_dal_progetto": False}, ensure_ascii=False) + "\n")
    (s / "locale").mkdir(exist_ok=True)
    (s / "locale" / "AGENTI.md").write_text("# schede locali\n\n### 1. Garante del progetto — `sciame-garante`\n\n"
                                            "- **In breve:** garante con i dettagli del progetto.\n- **Nucleo:** decisione.\n\n"
                                            "Scheda locale del progetto.\n", encoding="utf-8")
    (s / "locale" / "VIETATE.txt").write_text("parolafinta\n", encoding="utf-8")
    (r / ".claude" / "agents" / "sciame-proprio.md").write_text("---\nname: sciame-proprio\ndescription: x\n---\n"
                                                               "agente scritto a mano dal progetto\n", encoding="utf-8")
    reg = s / "RICHIESTE_ESPERTI.md"
    reg.write_text(reg.read_text(encoding="utf-8") + "| 2026-11-16 | G1 | logico | `alfa` | x | nessuno dei ruoli la copre |\n",
                   encoding="utf-8")
    f = base / f"{name}_entry.json"
    f.write_text(json.dumps(entry40("voce-approvata"), ensure_ascii=False))
    rc, out = py(s / "motore" / "sciame.py", "--sciame", s, "approva", f)
    assert rc == 0, out
    rc, out = py(s / "motore" / "sciame.py", "--sciame", s, "rigenera")
    assert rc == 0, out
    (r / "CLAUDE.md").write_text("# Il progetto\n\nRegole del progetto.\n", encoding="utf-8")
    rc, out = py(s / "motore" / "sciame.py", "--sciame", s, "istruzioni")
    assert rc == 0, out
    return r


def migration(base: Path):
    if not OLD_SH.is_file():
        skip("M1, M2, M6 (part), M7, M14, M15", "tests/fixtures/sciame-4.0.sh is not here")
        return
    # M1: an Italian 4.0 installation updated with swarmer.sh update
    r = project40(base, "m1")
    s = r / "sciame"
    keep = [".sciame/config.json", "sciame/locale/AGENTI.md", "sciame/RICHIESTE_ESPERTI.md", "sciame/locale/VIETATE.txt",
            ".claude/agents/sciame-proprio.md", "CLAUDE.md"]
    before_bytes = {k: (r / k).read_bytes() for k in keep}
    before_agents, before_skills = names(r / ".claude" / "agents"), names(r / ".claude" / "skills")
    before_outside = tree(r, skip_dir="sciame")
    shutil.copytree(r, base / "m2", symlinks=True)
    shutil.copytree(r, base / "m14_before", symlinks=True)
    shutil.copytree(r, base / "m15", symlinks=True)
    rc, out = update5(r)
    update_out = out
    check("M1: swarmer.sh update of an Italian 4.0", rc == 0, out)
    check("M1: the names in .claude/agents are the same", names(r / ".claude" / "agents") == before_agents,
          names(r / ".claude" / "agents") ^ before_agents)
    check("M1: the names in .claude/skills are the same", names(r / ".claude" / "skills") == before_skills,
          names(r / ".claude" / "skills") ^ before_skills)
    changed = [k for k in keep if (r / k).read_bytes() != before_bytes[k]]
    check("M1: config, override, register, VIETATE.txt, agent of the project and CLAUDE.md byte for byte", not changed,
          changed)
    after_outside = tree(r, skip_dir="sciame")
    outside = sorted(k for k in set(before_outside) | set(after_outside)
                     if before_outside.get(k) != after_outside.get(k) and not S.is_generated(r / k))
    check("M1: no file outside the swarm folder changes, except the generated ones with the note", not outside, outside)
    db = json.loads((s / "db" / "professionals.json").read_text(encoding="utf-8"))
    check("M1: the approved entry is in the database, format 2", db.get("format") == 2
          and any(v["id"] == "voce-approvata" for v in db["entries"]) and not (s / "db" / "professionisti.json").exists())
    rc, out = bash(s / "swarmer.sh", "check", cwd=r)
    check("M1: check aligned after the update", rc == 0 and aligned(out), out)
    rc, out = bash(s / "sciame.sh", "controlla", cwd=r)
    check("M1: the 4.0 command bash sciame/sciame.sh controlla still works", rc == 0 and aligned(out), out)
    check("M1: no unretouched motore/ left", not (s / "motore").exists() and not (s / "prove").exists()
          and not (s / "documenti").exists())
    check("M1: the internal state has the 5.0 names", all((s / n).is_file() for n in ("ROOT", "LANGUAGE", "FACTORY.json",
                                                                                      "VERSION"))
          and not any((s / n).exists() for n in C.STATE_NAMES.values()) and not (s / C.MIGRATING).exists())
    check("M1: the Italian documents keep their 4.0 names", (s / "PREAMBOLO.md").is_file() and (s / "GIURIA.md").is_file()
          and not (s / "PREAMBLE.md").exists())
    check("M1: the migration is announced (cli_migrated)", text_part(IT["cli_migrated"]) in update_out
          or text_part(EN["cli_migrated"]) in update_out, update_out)
    rc, out = py(s / "convoca.py", "ruoli", "--domanda", "un filtro di Kalman")
    check("M1: the 4.0 wrapper convoca.py still works", rc == 0 and "sciame-kalman" in out, out)
    after = tree(r)
    rc, out = update5(r)
    check("M1: a second update changes nothing", rc == 0 and tree(r) == after, out)

    # M2: a retouched file of motore/ stays and is listed
    r2 = base / "m2"
    j = r2 / "sciame" / "motore" / "giuria.py"
    j.write_text(j.read_text(encoding="utf-8") + "\n# ritocco del progetto\n", encoding="utf-8")
    rc, out = update5(r2)
    left = text_part(IT["cli_left_modified"])
    check("M2: a retouched motore/giuria.py stays and is listed in cli_left_modified",
          rc == 0 and j.is_file() and left in out and "motore/giuria.py" in out
          and not (r2 / "sciame" / "motore" / "sciame.py").exists(), out)

    # M15: a reserved id already in a 4.0 local card → warning; new with approve → error
    r15 = base / "m15"
    (r15 / "sciame" / "locale" / "AGENTI.md").write_text(
        "### 1. Esperto del progetto — `sciame-expert`\n\n- **In breve:** una sigla che la 5.0 riserva.\n\nTesto.\n",
        encoding="utf-8")
    rc, out = update5(r15)
    warn = IT["cli_reserved_warning"].split("{")[0].strip()
    check("M15: a reserved id (expert) in a 4.0 local card gives a warning, not an error",
          rc == 0 and warn in out and (r15 / ".claude" / "agents" / "sciame-expert.md").is_file(), out)
    f = base / "m15.json"
    f.write_text(json.dumps(entry40("plenary"), ensure_ascii=False))
    rc, out = py(r15 / "sciame" / "engine" / "swarmer.py", "--swarm", r15 / "sciame", "approve", f)
    check("M15: a new entry with a reserved id is refused by approve", rc == 1, out)

    # M14: a migration interrupted after each step of §E; update completes it
    m14(base)

    # M7: an English 4.0 installation moves to swarmer-* and to the English names
    r7 = base / "m7"
    rc, out = install40(r7, "--lingua", "en")
    check("M7: the 4.0 installs in English", rc == 0, out)
    s7 = r7 / "sciame"
    old_docs = [n for n in ("PREAMBOLO.md", "GIURIA.md", "AMBIENTE.md") if (s7 / n).is_file()]
    shutil.copytree(r7, base / "m7b", symlinks=True)
    shutil.copytree(r7, base / "m7c", symlinks=True)
    shutil.copytree(r7, base / "m7d", symlinks=True)
    rc, out = update5(r7)
    check("M7: update of an English 4.0", rc == 0, out)
    agents = names(r7 / ".claude" / "agents")
    skills = names(r7 / ".claude" / "skills")
    check("M7: the agents become swarmer-*", agents and all(a.startswith("swarmer-") for a in agents), sorted(agents)[:5])
    check("M7: the skills become swarmer-*", skills == {"swarmer"} | {f"swarmer-{x}" for x in
                                                                     ("single", "fan-out", "classic", "jury", "light-jury",
                                                                      "full", "plenary", "expert")}, skills)
    check("M7: the documents take the English names, the 4.0 ones with the note are removed",
          (s7 / "PREAMBLE.md").is_file() and (s7 / "JURY.md").is_file() and not any((s7 / n).exists() for n in old_docs),
          old_docs)
    check("M7: the Italian stubs are there", all((s7 / n).is_file() for n in ("sciame.sh", "convoca.py", "giuria.py")))
    rc, out = bash(s7 / "sciame.sh", "check", cwd=r7)
    check("M7: the sciame.sh stub works", rc == 0 and aligned(out), out)
    rc, out = py(s7 / "convoca.py", "roles", "--question", "a Kalman filter")
    check("M7: the convoca.py stub works", rc == 0 and "swarmer-kalman" in out, out)
    rc, out = py(s7 / "giuria.py", "requests")
    check("M7: the giuria.py stub works", rc == 0, out)
    for name, cfg in (("m7b", {"prefisso": "sciame"}), ("m7c", {"prefix": "sciame"})):
        rr = base / name
        (rr / ".sciame").mkdir(exist_ok=True)
        (rr / ".sciame" / "config.json").write_text(json.dumps(cfg) + "\n")
        rc, out = update5(rr)
        agents = names(rr / ".claude" / "agents")
        skills = names(rr / ".claude" / "skills")
        check(f"M7: with {list(cfg)[0]}: \"sciame\" the agents stay sciame-*, the strategy names English",
              rc == 0 and agents and all(a.startswith("sciame-") for a in agents) and "sciame-single" in skills, out)
    # B6: an agent of the project with the other prefix and without the note stands for the role: swarmer-<id> is not
    # written next to it (two definitions of the same juror)
    rd = base / "m7d"
    own = rd / ".claude" / "agents" / "sciame-garante.md"
    own.write_text("---\nname: sciame-garante\ndescription: x\n---\nthe guarantor of the project\n", encoding="utf-8")
    rc, out = update5(rd)
    check("M7 (B6): update does not write swarmer-garante next to the project's sciame-garante without the note",
          rc == 0 and own.is_file() and not (rd / ".claude" / "agents" / "swarmer-garante.md").exists(), out)
    rc, out = bash(rd / "sciame" / "swarmer.sh", "check", cwd=rd)
    check("M7 (B6): and check is aligned", rc == 0 and aligned(out), out)


def m14(base: Path):
    """The states of §E built from the 4.0 tree (before) and the migrated one (after): each one, given to update,
    must end in the same tree as an uninterrupted migration."""
    before = base / "m14_before"
    done = base / "m14_done"
    shutil.copytree(before, done, symlinks=True)
    rc, out = update5(done)
    if rc != 0:
        check("M14: the reference migration", False, out)
        return
    ref = tree(done)
    b, a = tree(before), ref
    old_dirs = tuple(f"sciame/{x}/" for x in C.OLD_TREE.values()) + ("sciame/db/professionisti.json",
                                                                     "sciame/db/nuclei.json")
    new_state = {f"sciame/{n}" for n in C.STATE_NAMES}
    old_state = {f"sciame/{n}" for n in C.STATE_NAMES.values()}
    mig = f"sciame/{C.MIGRATING}"

    factory_dirs = tuple(f"sciame/{x}/" for x in (*C.OLD_TREE, "db", "i18n")) + ("sciame/swarmer.sh", "sciame/UPSTREAM")
    stubs = {f"sciame/{x}" for x in ("convene.py", "jury.py", "generate_agents.py", *C.ALIAS_STUBS)}
    s1 = dict(b)
    s1[mig] = b"4.0\n"
    s2 = dict(s1)   # step 2: the 5.0 factory files written over and beside the 4.0 ones
    s2.update({k: v for k, v in a.items() if k.startswith(factory_dirs)})
    s3 = {k: v for k, v in s2.items() if not k.startswith(old_dirs)}   # step 3: the 4.0 factory files removed
    s4 = dict(s3)   # step 4: wrappers, alias stubs, swarmer.sh
    s4.update({k: v for k, v in a.items() if k in stubs})
    s5 = dict(a)    # step 5 and the first half of 6: regenerated files and the new state, the old state still there
    s5.update({k: v for k, v in b.items() if k in old_state})
    s5[mig] = b"4.0\n"
    s6 = dict(a)    # the old state removed, MIGRATING left
    s6[mig] = b"4.0\n"
    for label, files in (("after step 1 (MIGRATING written)", s1), ("after step 2 (new factory files)", s2),
                         ("after step 3 (old factory files removed)", s3), ("after step 4 (wrappers and stubs)", s4),
                         ("after step 5 (new state, old state too)", s5),
                         ("after step 6 (old state removed, MIGRATING left)", s6)):
        r = base / ("m14_" + re.sub(r"\W+", "_", label)[:30])
        shutil.copytree(before, r, symlinks=True)
        for p in sorted(r.rglob("*"), reverse=True):
            if p.is_file() and p.relative_to(r).as_posix() not in files:
                p.unlink()
        for k, v in files.items():
            (r / k).parent.mkdir(parents=True, exist_ok=True)
            (r / k).write_bytes(v)
        sh = r / "sciame" / "swarmer.sh"
        if sh.is_file():
            sh.chmod(0o755)
            rc, out = bash(sh, "help", cwd=r)
            check(f"M14: head.sh of the installed copy recognizes the state {label}", rc == 0 and "install" in out, out)
        rc, out = update5(r)
        got = tree(r)
        diff = sorted(k for k in set(got) | set(ref) if got.get(k) != ref.get(k))
        check(f"M14: update completes the migration interrupted {label}", rc == 0 and not diff, (out, diff[:8]))


def commands(base: Path):
    """M3: every command and every option of i18n, canonical and alias, with the same effect in an English and an
    Italian installation; abbreviations refused."""
    al_it = IT.get("commands", {})
    opt_it = IT.get("options", {})
    used_cmd, used_opt = USED_CMD, USED_OPT
    vals = {}
    for cat, m in IT.get("values", {}).items():
        for canon, alias in m.items():
            for a in ([alias] if isinstance(alias, str) else alias):
                vals[canon] = a
                break

    def alias_args(args):
        out = []
        for i, t in enumerate(args):
            if i == 0 and t in al_it and al_it[t]:
                out.append(al_it[t][0])
                used_cmd.add(t)
            elif t in opt_it and opt_it[t]:
                out.append(opt_it[t][0])
                used_opt.add(t)
            elif t in vals and i > 0 and args[i - 1] in ("--profile", "--strategy", "--form", "--rule"):
                out.append(vals[t])
            else:
                out.append(t)
        return out

    def norm(out, *roots):
        for x in roots:
            out = out.replace(str(x), "<R>")
        return out

    for lang in ("en", "it"):
        ra, rb = base / f"m3_{lang}_a", base / f"m3_{lang}_b"
        for r in (ra, rb):
            rc, out = install5(r, "--language", lang)
            assert rc == 0, out
        folder = "swarmer" if lang == "en" else "sciame"
        sa, sb = ra / folder, rb / folder

        def same(label, args, extra_a=(), extra_b=(), program="swarmer", compare_trees=False, cwd=False, env=None):
            args = [str(x) for x in args]
            if program == "swarmer":
                ca = [sa / "engine" / "swarmer.py", "--swarm", sa, *args]
                cb = [sb / "engine" / "swarmer.py", "--sciame", sb, *alias_args(args)]
                used_opt.add("--swarm")
            else:
                ca = [sa / program, *args]
                cb = [sb / program, *alias_args(args)]
            x = py(*ca, *extra_a, cwd=ra if cwd else None, env=env)
            y = py(*cb, *extra_b, cwd=rb if cwd else None, env=env)
            ok = x[0] == y[0] and norm(x[1], sa, ra) == norm(y[1], sb, rb)
            if compare_trees:
                ta, tb = tree(ra), tree(rb)
                ok = ok and set(ta) == set(tb)
            check(f"M3 [{lang}]: {label}: canonical and alias give the same effect", ok, (x, y))
            return x
        for a in (["help"], ["language"], ["roles", "a Kalman filter"], ["professionals"], ["check"], ["regenerate"],
                  ["models"], ["requests"]):
            same(" ".join(a[:1]), a, compare_trees=a[0] == "regenerate")
        for s in ("single", "fan-out", "classic", "jury", "light-jury", "full", "plenary", "expert"):
            same(f"{s} --show", [s, "--show", "--profile", "code", "--roles", "logico", "--language", "en", "x"])
        same("single --show --print --model", ["single", "--show", "--print", "--model", "opus", "x"])
        req = base / f"m3_request_{lang}.txt"
        req.write_text("a request from a file\n")
        same("single --from-file", ["single", "--show", "--from-file", req])
        same("models --all", ["models", "--all", "inherit"], compare_trees=True)
        same("instructions", ["instructions"], compare_trees=True)
        same("instructions --remove", ["instructions", "--remove"], compare_trees=True)
        entry = base / f"m3_entry_{lang}.json"
        entry.write_text(json.dumps({"id": "m3-entry", "type": "professional", "core": "critico",
                                     "texts": {l: {"name": "M3", "short": "an entry.", "keywords": ["m3"],
                                                   "body": "**Mission.** x.\n"} for l in ("en", "it")}}))
        same("approve --without-script", ["approve", entry, "--without-script"], compare_trees=True)
        entry2 = base / f"m3_entry2_{lang}.json"
        (sa / ("locale" if lang == "it" else "local") / ("AGENTI.md" if lang == "it" else "AGENTS.md")).write_text(
            "### 1. Local — `swarmer-m3-local`\n\n- **In short:** local.\n\nLocal text.\n")
        (sb / ("locale" if lang == "it" else "local") / ("AGENTI.md" if lang == "it" else "AGENTS.md")).write_text(
            "### 1. Local — `swarmer-m3-local`\n\n- **In short:** local.\n\nLocal text.\n")
        entry2.write_text(json.dumps({"id": "m3-local", "type": "professional", "core": "critico",
                                      "texts": {l: {"name": "M3 generic", "short": "generic.", "keywords": ["m3"],
                                                    "body": "**Mission.** generic.\n"} for l in ("en", "it")}}))
        same("approve --generic-from-local", ["approve", entry2, "--generic-from-local"], compare_trees=True)
        same("propose", ["propose", "m3-entry"], compare_trees=True)
        same("propose --send --language", ["propose", "m3-entry", "--send", "--language", "it"])
        cards = base / f"m3_cards_{lang}.md"
        cards.write_text("### 9. Private — `swarmer-m3-private`\n\n- **In short:** of the project.\n")
        same("import-cards", ["import-cards", cards], compare_trees=True)
        tr = base / f"m3_translation_{lang}.json"
        tr.write_text(json.dumps({"name": "M3", "short": "an entry.", "keywords": ["m3"], "body": "**Mission.** x.\n"}))
        same("translate --language", ["translate", "m3-entry", tr, "--language", lang], compare_trees=True)
        same("build --output", ["build", "--output", base / f"m3_{lang}.sh"])
        same("build --check", ["build", "--check"])
        same("verify", ["verify"])
        same("verify --publication", ["verify", "--publication"])
        # count, on a 5.0 jury in the dialect of the installation
        jdir = make_jury(base / f"m3_jury_{lang}", lang)
        same("count", ["count", jdir, "0"])
        # the convene and jury programs and generate_agents
        same("convene roles --question", ["roles", "--question", "a Kalman filter"], program="convene.py")
        same("generate_agents --check", ["--check"], program="generate_agents.py")
        same("generate_agents --list", ["--list"], program="generate_agents.py")
        same("generate_agents --instructions", ["--instructions"], program="generate_agents.py", compare_trees=True)
        same("generate_agents --remove-instructions", ["--remove-instructions"], program="generate_agents.py",
             compare_trees=True)
        same("jury count", ["count", jdir, "0"], program="jury.py")
        same("jury requests", ["requests"], program="jury.py")
        convening(base, lang, sa, sb, same)
        # tests (on a copy whose tests are a single trivial file), remove, install, update
        for s in (sa, sb):
            for t in (s / "tests").glob("test_*.py"):
                t.unlink()
            (s / "tests" / "test_trivial.py").write_text("print('trivial ok')\n")
        same("tests", ["tests"])
        same("generate_agents --remove", ["--remove"], program="generate_agents.py", compare_trees=True)
        same("generate_agents --install", ["--install"], program="generate_agents.py", compare_trees=True)
        same("remove", ["remove"], compare_trees=True)
        x = py(ENGINE, "install", "--from", SOURCE, "--root", base / f"m3i_{lang}_a", "--folder", "sw", "--language",
               lang, "--local", "sw/loc", "--project-managed", "--instructions", "--force")
        y = py(ENGINE, *alias_args(["install", "--from", SOURCE, "--root", base / f"m3i_{lang}_b", "--folder", "sw",
                                    "--language", lang, "--local", "sw/loc", "--project-managed", "--instructions",
                                    "--force"]))
        ta, tb = tree(base / f"m3i_{lang}_a"), tree(base / f"m3i_{lang}_b")
        diff = sorted(k for k in set(ta) | set(tb) if ta.get(k) != tb.get(k))
        check(f"M3 [{lang}]: install and all its options: canonical and alias give the same tree",
              x[0] == 0 and y[0] == 0 and not diff, (x, y, diff[:5]))
        x = py(ENGINE, "update", "--from", SOURCE, "--root", base / f"m3i_{lang}_a")
        y = py(ENGINE, *alias_args(["update", "--from", SOURCE, "--root", base / f"m3i_{lang}_b"]))
        ta, tb = tree(base / f"m3i_{lang}_a"), tree(base / f"m3i_{lang}_b")
        check(f"M3 [{lang}]: update and its alias give the same tree", x[0] == 0 and y[0] == 0 and set(ta) == set(tb)
              and all(ta[k] == tb[k] for k in ta), (x, y))
        rc, out = bash(sa.parent / folder / "swarmer.sh", "help") if (sa / "swarmer.sh").is_file() else (0, "")
        rc1, out1 = bash(base / f"m3i_{lang}_a" / "sw" / "swarmer.sh", "help")
        rc2, out2 = bash(base / f"m3i_{lang}_b" / "sw" / "swarmer.sh", "aiuto")
        check(f"M3 [{lang}]: bash swarmer.sh help and aiuto", rc1 == 0 and rc2 == 0 and out1 == out2, (out1[:200], out2[:200]))
        rc, out = py(ENGINE, "--swarm", base / f"m3i_{lang}_a" / "sw", "check", "--ist")
        rc2, out2 = py(ENGINE, "install", "--fro", SOURCE, "--root", base / "m3_abbrev")
        check(f"M3 [{lang}]: an abbreviation (--ist, --fro) is refused", rc != 0 and rc2 != 0, (out, out2))
    # --yes is never executed (it would open a pull request): the parser must give the same namespace
    import swarmer as W
    import aliases as A
    p = W.build_parser(A.load(SOURCE))
    a = p.parse_args(["propose", "x", "--send", "--yes", "--language", "it"])
    for yes in opt_it.get("--yes", []):
        b = p.parse_args(["proponi", "x", "--invia", yes, "--lingua", "it"])
        check(f"M3: propose --yes and {yes} parse the same", vars(a) == {**vars(b), "_command": a._command}, (a, b))
        used_opt.add("--yes")
    missing_c = sorted(c for c, v in al_it.items() if v and c not in used_cmd)
    missing_o = sorted(o for o, v in opt_it.items() if v and o not in used_opt)
    check("M3: every command with an alias was exercised", not missing_c, missing_c)
    check("M3: every option with an alias was exercised", not missing_o, missing_o)


def make_jury(c: Path, lang: str) -> Path:
    """A G2 recommendation jury of five, all yes, in the dialect of the language, with the roles of the swarm."""
    import hashlib
    it = lang == "it"
    c.mkdir()
    roles = ["garante", "avversario", "logico", "debugger", "statistico"]
    g = ({"oggetto": "x", "relatore": "formalista", "cancelliere": "arbitro", "tocca_codice": True, "tocca_numeri": True,
          "autorita": "raccomandazione", "delega": "-", "classificazione": "ordinaria",
          "giurati": [{"ruolo": r, "nuovo_sull_oggetto": True} for r in roles]} if it else
         {"subject": "x", "rapporteur": "formalista", "clerk": "arbitro", "touches_code": True, "touches_numbers": True,
          "authority": "recommendation", "delegation": "-", "classification": "ordinary",
          "jurors": [{"role": r, "fresh_on_subject": True} for r in roles]})
    jf, sf, rd, pf, vf, sw = (("giuria.json", "SIGILLI.md", "giro_0", "PROPOSTA.md", "VOTO_{}.md", "SIGILLO") if it else
                              ("jury.json", "SEALS.md", "round_0", "PROPOSAL.md", "VOTE_{}.md", "SEAL"))
    tail = "sha256 dei byte che precedono questa riga: " if it else "sha256 of the bytes before this line: "

    def sealed(t):
        return t + tail + hashlib.sha256(t.encode()).hexdigest() + "\n"
    (c / jf).write_text(json.dumps(g))
    lines = [f"{sw} {jf} {hashlib.sha256((c / jf).read_bytes()).hexdigest()}"]
    (c / rd).mkdir()
    (c / rd / pf).write_text(sealed("OPTION D1 (a)\nOPTIONS D1 (a) | (b)\nOPERATIVE D1 do (a)\n"))
    lines.append(f"{sw} {rd}/{pf} {(c / rd / pf).read_text().rstrip().rsplit(' ', 1)[1]}")
    for r in roles:
        (c / rd / vf.format(r)).write_text(sealed("VOTE D1 yes\nCONDITION D1 none\nCLASS D1 ordinary\n"))
        lines.append(f"{sw} {rd}/{vf.format(r)} {(c / rd / vf.format(r)).read_text().rstrip().rsplit(' ', 1)[1]}")
    (c / sf).write_text("\n".join(lines) + "\n")
    return c


USED_CMD, USED_OPT = set(), set()   # the commands and options of i18n exercised by M3 through an alias


def mark(args):
    for i, t in enumerate(args):
        t = str(t)
        if i == 0 and not t.startswith("-"):
            USED_CMD.add(t)
        elif t.startswith("--"):
            USED_OPT.add(t)


def shape(c: Path) -> set[str]:
    """The relative names of a convening, with the random folder names of the blind lanes masked."""
    return {re.sub(r"(?<![0-9a-f])[0-9a-f]{12}(?![0-9a-f])", "<lane>", k) for k in tree(c)}


def convening(base: Path, lang: str, sa: Path, sb: Path, same):
    """A classic convening in lockstep up to f3, canonical commands on one side and aliases on the other."""
    da, db = base / f"m3_conv_{lang}_a", base / f"m3_conv_{lang}_b"
    x = py(sa / "convene.py", "prepare", "--name", "k", "--strategy", "classic", "--profile", "code", "--question", "q",
           "--roles", "logico,architetto", "--seed", "3", "--dest", da)
    y = py(sb / "convene.py", "prepara", "--nome", "k", "--strategia", "classica", "--profilo", "codice", "--domanda", "q",
           "--ruoli", "logico,architetto", "--seme", "3", "--dest", db)
    mark(["prepare", "--name", "--strategy", "--profile", "--question", "--roles", "--seed", "--n", "--form", "--rule"])
    check(f"M3 [{lang}]: convene prepare and prepara", x[0] == 0 and y[0] == 0, (x, y))
    if x[0] or y[0]:
        return
    ca = next(p for p in da.iterdir() if not p.name.startswith("."))
    cb = next(p for p in db.iterdir() if not p.name.startswith("."))
    check(f"M3 [{lang}]: prepare and prepara write the same names", shape(ca) == shape(cb))
    it = lang == "it"
    N = (lambda a, b: a if it else b)
    contract = N("CONTRATTO.md", "CONTRACT.md")
    hole = N("<da compilare>", "<to fill in>")
    for c in (ca, cb):
        (c / contract).write_text((c / contract).read_text().replace(hole, "filled"))

    def both(label, canon, alias, expect=0):
        mark(canon)
        x = py(sa / "convene.py", *canon)
        y = py(sb / "convene.py", *alias)
        check(f"M3 [{lang}]: convene {label}: canonical and alias give the same effect (exit {expect})",
              x[0] == y[0] == expect, (x, y))
    both("gate --notes", ["gate", ca, "f0", "--notes", "ok"], ["cancello", cb, "f0", "--note", "ok"])
    both("status", ["status", ca], ["stato", cb])
    for d in (da, db):
        lanes = next(p for p in d.iterdir() if p.name.startswith("."))
        mp = json.loads(next(lanes.glob("*.json")).read_text())
        for role, v in mp.items():
            folder = v.get("folder") or v.get("cartella")
            canary = v.get("canary") or v.get("canarino")
            Path(folder, N("CONSEGNA.md", "DELIVERABLE.md")).write_text(f"{N('Canarino', 'Canary')}: {canary}\n"
                                                                        f"{N('FATTO', 'DONE')}\nidea of {role}\n")
    both("gate before the snapshot", ["gate", ca, "f1", "--notes", "x"], ["cancello", cb, "f1", "--note", "x"], expect=1)
    both("snapshot", ["snapshot", ca], ["fotografa", cb])
    both("gate --verify", ["gate", ca, "f1", "--notes", "x", "--verify"], ["cancello", cb, "f1", "--note", "x", "--verifica"])
    both("gate --not-delivered", ["gate", ca, "f1", "--notes", "x", "--not-delivered", "nobody"],
         ["cancello", cb, "f1", "--note", "x", "--non-consegnati", "nobody"])
    for c in (ca, cb):
        f2 = c / "f2"
        (f2 / N("01-traduzione", "01-translation") / N("SCHEDE.md", "CARDS.md")).write_text("cards\n")
        (f2 / "03-triage" / "TRIAGE.md").write_text("H-001 TEST\nH-002 TEST\n")
    both("seal", ["seal", ca, ca / "f2" / "03-triage" / "TRIAGE.md"],
         ["sigilla", cb, cb / "f2" / "03-triage" / "TRIAGE.md"])
    for c in (ca, cb):
        f2 = c / "f2"
        sig = f2 / N("02-firme", "02-signatures") / "logico.md"
        sig.write_text("faithful\n")
        os.utime(sig, (1, 1))
        (f2 / N("04-torneo", "04-tournament") / N("TORNEO.md", "TOURNAMENT.md")).write_text("H-001 ok\n")
        (f2 / N("05-selezione", "05-selection") / N("SELEZIONE.md", "SELECTION.md")).write_text(
            f"H-001 H-002\n{N('Controfirma', 'Countersign')}: arbitro\n")
    both("gate f2", ["gate", ca, "f2", "--notes", "x"], ["cancello", cb, "f2", "--note", "x"])
    both("select --radical --owner", ["select", ca, "H-001", "--radical", "H-002", "--owner", "architetto"],
         ["seleziona", cb, "H-001", "--radicale", "H-002", "--responsabile", "architetto"])
    check(f"M3 [{lang}]: select and seleziona write the same names", shape(ca) == shape(cb))
    both("close-branch --reason", ["close-branch", ca, "H-002", "--reason", "no time"],
         ["chiudi-ramo", cb, "H-002", "--motivo", "no time"])
    both("status at the end", ["status", ca], ["stato", cb])
    # prepare of a fan-out with --n, --form and --rule
    x = py(sa / "convene.py", "prepare", "--name", "f", "--strategy", "fan-out", "--profile", "code", "--question", "q",
           "--n", "2", "--form", "race", "--rule", "first", "--dest", da / "f")
    y = py(sb / "convene.py", "prepara", "--nome", "f", "--strategia", "ventaglio", "--profilo", "codice", "--domanda", "q",
           "--n", "2", "--forma", "gara", "--regola", "primo", "--dest", db / "f")
    check(f"M3 [{lang}]: convene prepare of a fan-out with --form and --rule, and its aliases", x[0] == 0 and y[0] == 0,
          (x, y))


def dialects_m6():
    """M6: the 4.0 database (format 1, from the 4.0 sciame.sh) and the tables of compat."""
    if not OLD_SH.is_file():
        skip("M6 (format 1 database)", "tests/fixtures/sciame-4.0.sh is not here")
    else:
        text = OLD_SH.read_text(encoding="utf-8")
        found = {}
        for name in ("professionisti.json", "nuclei.json"):
            mark = f"#==== sciame.sh: file db/{name} ====\n"
            found[name] = json.loads(text.split(mark)[1].split("\n#==== sciame.sh:")[0])
        with tempfile.TemporaryDirectory() as t:
            for name, d in found.items():
                (Path(t) / name).write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            check("M6: load of the 4.0 database = db/professionals.json and db/cores.json of 5.0",
                  P.load(t) == P.load(SOURCE / "db"))
        for name, d in found.items():
            check(f"M6: db_to_v1(db_from_v1(x)) == x for the 4.0 {name}", C.db_to_v1(C.db_from_v1(d)) == d)
    for name, tab in C.VALUES.items():
        check(f"M6: the table of values {name} is injective", len(set(tab.values())) == len(tab))
    check("M6: the states are injective", len(set(C.STATES.values())) == len(C.STATES))
    e = {"giro": 0, "giurati": ["round", "motivo"], "decisioni": {"D1": {"opzione": "APPROVATA", "stato": "APPROVATA",
                                                                      "si": ["round"], "no": ["motivo"]}}}
    can = C.to_canonical(e, C.OUTCOME_SCHEMA)
    check("M6: to_canonical leaves the roles «round» and «motivo» and the option text «APPROVATA» alone",
          can["jurors"] == ["round", "motivo"] and can["decisions"]["D1"]["option"] == "APPROVATA"
          and can["decisions"]["D1"]["state"] == "APPROVED" and can["decisions"]["D1"]["yes"] == ["round"])
    check("M6: to_dialect gives back the same outcome", C.to_dialect(can, C.OUTCOME_SCHEMA, "it") == e)
    try:
        C.to_canonical({"cartella": "a", "folder": "b"}, C.CONFIG_SCHEMA)
        check("M6: the same concept in two languages is an error", False)
    except C.Error:
        check("M6: the same concept in two languages is an error", True)
    try:
        C.to_canonical({"unknown_key": 1}, C.CONFIG_SCHEMA)
        check("M6: an unknown key is an error", False)
    except C.Error:
        check("M6: an unknown key is an error", True)


def variables_m8_m9(base: Path):
    """M8: SCIAME_VIETATE and SWARMER_FORBIDDEN stop build; SCIAME_LINGUA counts as SWARMER_LANGUAGE, after the
    LANGUAGE file (B.0). M9: a colliding alias makes verify fail."""
    rep = base / "m8_rep"
    shutil.copytree(SOURCE, rep, ignore=COPY_IGNORE)
    fw = base / "m8_forbidden.txt"
    fw.write_text("kalman\n")
    for var in ("SWARMER_FORBIDDEN", "SCIAME_VIETATE"):
        rc, out = py(rep / "engine" / "swarmer.py", "--swarm", rep, "build", "--output", base / "m8.sh",
                     env=clean_env(**{var: str(fw)}))
        check(f"M8: {var} stops build", rc == 1 and "forbidden" in out, out)
    r = base / "m8_install"
    install5(r)
    current_it = IT["cli_language_current"].split("{")[0]
    for var in ("SWARMER_LANGUAGE", "SCIAME_LINGUA"):
        rc, out = py(rep / "engine" / "swarmer.py", "--swarm", rep, "language", env=clean_env(**{var: "it"}))
        check(f"M8: {var}=it sets the language where there is no LANGUAGE", rc == 0 and current_it in out, out)
        rc, out = py(r / "swarmer" / "engine" / "swarmer.py", "--swarm", r / "swarmer", "language",
                     env=clean_env(**{var: "it"}))
        check(f"M8: {var}=it does not win over LANGUAGE (en)", rc == 0 and current_it not in out
              and EN["cli_language_current"].split("{")[0] in out, out)
    # B1: the variable never renames: an it installation with SWARMER_LANGUAGE=en keeps sciame-* and stays aligned
    ri = base / "m8_install_it"
    ri.mkdir()
    rc, out = py(ENGINE, "install", "--from", SOURCE, "--root", ri, "--language", "it",
                 env=clean_env(SWARMER_LANGUAGE="en"))
    agents = names(ri / ".claude" / "agents")
    check("M8 (B1): SWARMER_LANGUAGE=en install --language it writes sciame-* agents",
          rc == 0 and agents and all(n.startswith("sciame-") for n in agents), out)
    eng = ri / "sciame" / "engine" / "swarmer.py"
    rc, out = py(eng, "--swarm", ri / "sciame", "check", env=clean_env(SWARMER_LANGUAGE="en"))
    check("M8 (B1): and check is aligned with the variable still set", rc == 0 and aligned(out), out)
    before = tree(ri)
    rc, out = py(eng, "--swarm", ri / "sciame", "regenerate", env=clean_env(SCIAME_LINGUA="en"))
    check("M8 (B1): SCIAME_LINGUA=en regenerate renames nothing", rc == 0 and tree(ri) == before,
          sorted(set(tree(ri)) ^ set(before))[:6] or out)
    t = json.loads((rep / "i18n" / "it.json").read_text(encoding="utf-8"))
    for label, change in (("an alias equal to another canonical", {"check": ["verify"]}),
                          ("the same alias for two commands", {"regenerate": ["controlla"]}),
                          ("an option alias equal to another canonical option", None)):
        tt = json.loads(json.dumps(t))
        if change:
            tt["commands"].update(change)
        else:
            tt["options"]["--folder"] = ["--local"]
        (rep / "i18n" / "it.json").write_text(json.dumps(tt, ensure_ascii=False), encoding="utf-8")
        rc, out = py(rep / "engine" / "swarmer.py", "--swarm", rep, "verify")
        check(f"M9: {label} (injected in a copy of it.json) makes verify fail, without a traceback",
              rc == 1 and "Traceback" not in out and ("the canonical name of another" in out or "is used for" in out),
              out)
    (rep / "i18n" / "it.json").write_text(json.dumps(t, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def unknown_config_b2(base: Path):
    """B2: a 4.0 config.json with a key the schema does not know (the 4.0 read a free dictionary) does not stop the
    migration: the key is kept, with a warning; a configuration that cannot be read stops update before any write."""
    if not OLD_SH.is_file():
        skip("B2", "tests/fixtures/sciame-4.0.sh is not here")
        return
    r = project40(base, "b2")
    cp = r / ".sciame" / "config.json"
    cfg = json.loads(cp.read_text(encoding="utf-8"))
    shutil.copytree(r, base / "b2_bad", symlinks=True)
    cp.write_text(json.dumps(dict(cfg, nota="mia"), ensure_ascii=False) + "\n", encoding="utf-8")
    before = cp.read_bytes()
    rc, out = update5(r)
    s = r / "sciame"
    check("B2: update of a 4.0 with a key more in config.json completes, with a warning",
          rc == 0 and "nota" in out and not (s / C.MIGRATING).exists() and (s / "LANGUAGE").is_file()
          and not any((s / n).exists() for n in C.STATE_NAMES.values()), out)
    check("B2: the configuration stays byte for byte, the key kept", cp.read_bytes() == before)
    rc, out = bash(s / "swarmer.sh", "check", cwd=r)
    check("B2: check aligned after the update", rc == 0 and aligned(out), out)
    rb = base / "b2_bad"
    cb = rb / ".sciame" / "config.json"
    cb.write_text(json.dumps(dict(cfg, folder="sciame"), ensure_ascii=False) + "\n", encoding="utf-8")
    snap = tree(rb)
    rc, out = update5(rb)
    check("B2: a configuration that cannot be read (cartella and folder) stops update with the tree byte for byte",
          rc == 1 and tree(rb) == snap, sorted(set(tree(rb)) ^ set(snap))[:6] or out)


def italian_messages_c3(base: Path):
    """C3: an Italian installation says in Italian what the 4.0 said in Italian (bash, models, the commands it
    suggests, the prefix of the errors of the first update)."""
    r = base / "c3_it"
    install5(r, "--language", "it")
    sh = r / "sciame" / "sciame.sh"
    rc, out = bash(sh, "modelli", cwd=r)
    check("C3: models with no assignment, in Italian (cli_models_none)", rc == 0 and IT["cli_models_none"] in out, out)
    rc, out = bash(sh, "installa", "--pippo", cwd=r)
    want = IT["sh_unknown_option"].format(command="installa", option="--pippo")
    check("C3: bash: an unknown option of installa in Italian, with the name typed", rc == 1 and want in out, out)
    rc, out = bash(sh, "installa", "--cartella", cwd=r)
    check("C3: bash: an option without its value in Italian", rc == 1
          and IT["sh_needs_value"].format(option="--cartella") in out, out)
    rc, out = bash(sh, "-C", cwd=r)
    check("C3: bash: -C without a folder in Italian", rc == 1 and IT["sh_needs_folder"] in out, out)
    if not OLD_SH.is_file():
        skip("C3 (4.0)", "tests/fixtures/sciame-4.0.sh is not here")
        return
    r4 = base / "c3_40"
    rc, out = install40(r4)
    broken = r4 / "sciame" / "locale" / "traduzioni" / "it" / "garante.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("{ not json\n", encoding="utf-8")
    rc, out = update5(r4)
    check("C3: the first update of an Italian 4.0: the error has the prefix of the installation (sciame: )",
          rc == 1 and IT["cli_prefix"] + str(broken) in out and EN["cli_prefix"] not in out, out)
    broken.unlink()
    rc, out = update5(r4)
    check("C3: cli_migrated suggests the command of the installation (sciame.sh istruzioni)",
          rc == 0 and "bash sciame/sciame.sh istruzioni" in out, out)


def convening_m10(base: Path):
    """M10: the 4.0 fan-out of the fixtures, half way through f1, carried to f5 by 5.0 in the Italian dialect."""
    src = FIXTURES / "convening-4.0"
    if not src.is_dir():
        skip("M10", "tests/fixtures/convening-4.0/ is not here")
        return
    work = base / "m10"
    for p in sorted(src.rglob("*")):
        q = work / p.relative_to(src)
        if p.is_dir():
            q.mkdir(parents=True, exist_ok=True)
        else:
            q.parent.mkdir(parents=True, exist_ok=True)
            q.write_text(p.read_text(encoding="utf-8").replace("@FIXTURE_ROOT@", str(work)), encoding="utf-8")
    c = next(p for p in work.iterdir() if p.is_dir() and not p.name.startswith("."))
    r = base / "m10_install"
    install5(r, "--language", "it")
    conv = r / "sciame" / "convoca.py"
    rc, out = py(conv, "stato", c)
    check("M10: 5.0 reads the 4.0 manifest (stato)", rc == 0 and "f0" in out
          and IT["convene"]["status_approved"].format(phase="f0").strip() in out, out)
    rc, out = py(conv, "cancello", c, "f1", "--note", "x")
    check("M10: gate f1 refused while agente-2 has not delivered", rc == 1 and "agente-2" in out, out)
    (c / "f1" / "agente-2" / "CONSEGNA.md").write_text("FATTO\nconsegna della fetta 2\n", encoding="utf-8")
    rc, out = py(conv, "cancello", c, "f1", "--note", "x")
    check("M10: gate f1 with the two deliverables", rc == 0, out)
    (c / "f5").mkdir(exist_ok=True)
    (c / "f5" / "CHIUSURA.md").write_text("Esito: chiuso\n", encoding="utf-8")
    rc, out = py(conv, "sigilla", c, c / "f5" / "CHIUSURA.md")
    check("M10: seal in the Italian dialect (SIGILLI.jsonl, key «ora»)", rc == 0 and (c / "SIGILLI.jsonl").is_file()
          and '"ora"' in (c / "SIGILLI.jsonl").read_text(), out)
    rc, out = py(conv, "seleziona", c, "H-001")
    check("M10: select is refused for a fan-out (no f2)", rc != 0, out)
    rc, out = py(conv, "cancello", c, "f5", "--note", "fine")
    check("M10: gate f5 of a 4.0 convening", rc == 0, out)
    g = json.loads((c / "GATE_f5.json").read_text())
    check("M10: the gate is written in the Italian dialect", "impronte" in g and "fase" in g, g)
    m = json.loads((c / "MANIFESTO.json").read_text())
    check("M10: the manifest stays Italian", m.get("strategia") == "ventaglio" and not (c / "MANIFEST.json").exists(), m)
    rc, out = py(conv, "stato", c)
    check("M10: stato after f5 (a fan-out lists f0 and f1)", rc == 0 and IT["convene"]["status_approved"].format(phase="f1").strip() in out, out)


# --- K.4: the English public database and the local translations ---

CALIBRATOR = {"en": {"name": "Calibrator", "short": "calibrates the instruments and states the uncertainty.",
                     "keywords": ["calibration", "uncertainty"],
                     "body": "**Mission.** Calibrate the instruments and state the uncertainty of every reading.\n"},
              "it": {"name": "Calibratore pubblico", "short": "tara gli strumenti e dichiara l'incertezza.",
                     "keywords": ["taratura", "incertezza"],
                     "body": "**Missione.** Tarare gli strumenti e dichiarare l'incertezza di ogni lettura.\n"}}


def source_with(base: Path, name: str, langs: list[str]) -> Path:
    """A copy of the repository whose database has the entry «calibratore» with the texts in `langs`."""
    src = base / name
    if not src.exists():
        shutil.copytree(SOURCE, src, ignore=COPY_IGNORE)
    p = src / "db" / "professionals.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    e = next((v for v in d["entries"] if v["id"] == "calibratore"), None)
    if e is None:
        e = {"id": "calibratore", "type": "professional", "parent": None, "core": "sperimentale", "version": "5.0",
             "status": "active", "texts": {}}
        d["entries"].append(e)
    e["texts"] = {l: CALIBRATOR[l] for l in langs}
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return src


def translations_k4(base: Path):
    """K.4: (a) propose of an entry without English is refused, and the CI refuses it; (b) a public database with an
    English-only entry installed in Italian: generation succeeds, the agent carries translation-pending: it; (c)
    translate registers, regenerates, removes the sign, and an update does not lose the translation (the public one
    wins only over an unmodified local one); (d) the local translation enters neither swarmer.sh nor verify
    --publication."""
    src = source_with(base, "k4_src", ["en"])
    eng = src / "engine" / "swarmer.py"
    root = base / "k4_project"
    root.mkdir()
    rc, out = py(eng, "install", "--from", src, "--root", root, "--language", "it")
    s = root / "sciame"
    agent = root / ".claude" / "agents" / "sciame-calibratore.md"
    head = agent.read_text(encoding="utf-8")[:900] if agent.is_file() else ""
    cat = json.loads((s / "catalog.json").read_text(encoding="utf-8")) if (s / "catalog.json").is_file() else {}
    check("K.4b: an English-only entry installed in Italian: the generation succeeds", rc == 0 and agent.is_file(), out)
    check("K.4b: the agent is generated from the English text with translation-pending: it",
          f"{C.TRANSLATION_PENDING}: it -->" in head and "Calibrator:" in head, head)
    check("K.4b: the catalog lists the entries waiting for a translation", cat.get("translation_pending") == ["calibratore"]
          and any(r["id"] == "calibratore" and r.get("translation_pending") == "it" for r in cat.get("roles", [])),
          cat.get("translation_pending"))
    rc, out = py(eng, "--swarm", s, "check")
    check("K.4b: check lists the pending translations and does not fail",
          rc == 0 and text_part(IT["cli_translation_pending"]) in out and "calibratore" in out and aligned(out), out)
    rc, out = py(s / "convoca.py", "prepara", "--nome", "k4", "--strategia", "singolo", "--profilo", "generale",
                 "--domanda", "tarare il sensore", "--ruoli", "calibratore")
    check("K.4b: a convening with the role says that its translation is pending",
          rc == 0 and text_part(IT["convene"]["translation_pending"]) in out and "sciame-calibratore" in out, out)
    # (c) translate, with the Italian keys of the file
    tr = base / "k4_translation.json"
    tr.write_text(json.dumps({"sigla": "calibratore", "nome": "Calibratore locale", "breve": CALIBRATOR["it"]["short"],
                              "parole": CALIBRATOR["it"]["keywords"], "corpo": CALIBRATOR["it"]["body"]},
                             ensure_ascii=False), encoding="utf-8")
    bad = base / "k4_bad.json"
    bad.write_text(json.dumps({"nome": "Calibratore", "breve": "x", "parole": ["x"], "corpo": "# a heading\n"}))
    rc, out = py(eng, "--swarm", s, "traduci", "calibratore", bad)
    check("K.4c: an invalid translation is refused (the rules of the cards)", rc == 1 and not (s / "locale" / "traduzioni").exists(), out)
    rc, out = py(eng, "--swarm", s, "traduci", "calibratore", tr)
    over = s / "locale" / "traduzioni" / "it" / "calibratore.json"
    head = agent.read_text(encoding="utf-8")[:900]
    check("K.4c: translate registers the translation in <swarm>/locale/traduzioni/it/<id>.json",
          rc == 0 and over.is_file() and text_part(IT["cli_translated"]) in out, out)
    check("K.4c: translate regenerates the agent and removes the sign",
          C.TRANSLATION_PENDING not in head and "Calibratore locale:" in head, head)
    cat = json.loads((s / "catalog.json").read_text(encoding="utf-8"))
    rc, out = py(eng, "--swarm", s, "check")
    check("K.4c: catalog and check have nothing pending any more", cat.get("translation_pending") == [] and rc == 0
          and text_part(IT["cli_translation_pending"]) not in out, out)
    before_over, before_agent = over.read_bytes(), agent.read_bytes()
    rc, out = py(eng, "update", "--from", src, "--root", root)
    check("K.4c: an update does not lose the translation", rc == 0 and over.read_bytes() == before_over
          and agent.read_bytes() == before_agent, out)
    src2 = source_with(base, "k4_src", ["en", "it"])
    rc, out = py(eng, "update", "--from", src2, "--root", root)
    check("K.4c: the public translation arriving later wins over an unmodified local one",
          rc == 0 and "Calibratore pubblico:" in agent.read_text(encoding="utf-8")[:900] and over.is_file(), out)
    # built here, so that this file (distributed with swarmer.sh) does not contain it
    touched = " ".join(["Calibratore", "ritoccato", "a", "mano"])
    over.write_text(over.read_text(encoding="utf-8").replace("Calibratore locale", touched), encoding="utf-8")
    rc, out = py(eng, "--swarm", s, "regenerate")
    rc2, out2 = py(eng, "update", "--from", src2, "--root", root)
    check("K.4c: a local translation modified by hand wins over the public one, also after an update",
          rc == 0 and rc2 == 0 and f"{touched}:" in agent.read_text(encoding="utf-8")[:900], (out, out2))
    # (d) neither swarmer.sh nor verify --publication
    built = base / "k4_built.sh"
    rc, out = py(eng, "--swarm", s, "build", "--output", built)
    text = built.read_text(encoding="utf-8") if built.is_file() else ""
    sha = json.loads(over.read_text(encoding="utf-8"))["sha256_scritto"]
    check("K.4d: the local translation does not enter swarmer.sh", rc == 0 and text and touched not in text
          and sha not in text and touched not in (s / "swarmer.sh").read_text(encoding="utf-8"), out)
    rc, out = py(eng, "--swarm", s, "verify", "--publication")
    check("K.4d: verify --publication does not take the local translation as public material",
          "traduzioni" not in out and "calibratore.json" not in out, out)
    repo = base / "k4_repo"
    shutil.copytree(SOURCE, repo, ignore=COPY_IGNORE)
    (repo / "local" / "translations" / "it").mkdir(parents=True)
    (repo / "local" / "translations" / "it" / "logico.json").write_text(over.read_text(encoding="utf-8"), encoding="utf-8")
    rc, out = py(repo / "engine" / "swarmer.py", "--swarm", repo, "verify", "--publication")
    rc2, out2 = py(repo / "engine" / "swarmer.py", "--swarm", repo, "build", "--output", base / "k4_repo.sh")
    check("K.4d: in the repository a local translation is a folder that must not be published, and build leaves it out",
          rc == 1 and "local: must not be in the tree to publish" in out and rc2 == 0
          and touched not in (base / "k4_repo.sh").read_text(encoding="utf-8"), (out, out2))
    # (a) an entry approved in Italian only stays local: propose refuses it until translate --language en
    entry = base / "k4_entry.json"
    entry.write_text(json.dumps({"sigla": "misuratore", "tipo": "professionista", "nucleo": "sperimentale",
                                 "testi": {"it": {"nome": "Misuratore", "breve": "misura.", "parole": ["misura"],
                                                  "corpo": "**Missione.** Misurare.\n"}}}, ensure_ascii=False))
    rc, out = py(eng, "--swarm", s, "approva", entry, "--senza-sciame-sh")
    check("K.1: a local approve in Italian only is accepted, and says the entry stays local",
          rc == 0 and text_part(IT["cli_local_until_english"]) in out, out)
    props = s / "proposte"
    rc, out = py(eng, "--swarm", s, "proponi", "misuratore")
    check("K.4a: propose of an entry without English is refused", rc == 1 and text_part(IT["cli_needs_english"]) in out
          and not list(props.glob("PR-*")), out)
    en = base / "k4_en.json"
    en.write_text(json.dumps({"name": "Measurer", "short": "measures.", "keywords": ["measurement"],
                              "body": "**Mission.** Measure.\n"}))
    rc, out = py(eng, "--swarm", s, "traduci", "misuratore", en, "--lingua", "en")
    prop = json.loads((props / "misuratore.json").read_text(encoding="utf-8"))
    check("K.1: translate --language en adds the English texts to the database and to the proposal",
          rc == 0 and prop.get("texts", {}).get("en", {}).get("name") == "Measurer"
          and not (s / "locale" / "traduzioni" / "en").exists(), out)
    rc, out = py(eng, "--swarm", s, "proponi", "misuratore", "--lingua", "it")
    pr = (props / "PR-misuratore.md").read_text(encoding="utf-8") if (props / "PR-misuratore.md").is_file() else ""
    en_tpl = (SOURCE / "docs" / "en" / "_PR_PROPOSAL.md").read_text(encoding="utf-8").split("{entries}")[0]
    check("K.1: with English the proposal is accepted, and its text is English whatever the language",
          rc == 0 and pr.startswith(en_tpl) and "Measurer" in pr, (out, pr[:300]))
    # the CI: a public database with an entry without English is refused
    d = json.loads((repo / "db" / "professionals.json").read_text(encoding="utf-8"))
    d["entries"].append({"id": "only-it", "type": "professional", "parent": None, "core": "sperimentale",
                         "version": "5.0", "status": "active", "texts": {"it": CALIBRATOR["it"]}})
    (repo / "db" / "professionals.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    rc, out = py(repo / "engine" / "professionals.py", "validate", repo / "db")
    rc2, out2 = py(repo / "engine" / "swarmer.py", "--swarm", repo, "verify")
    check("K.1: the CI refuses a public entry without English (validate and verify)",
          rc == 1 and rc2 == 1 and "only-it" in out and "«en»" in out2, (out, out2[:400]))


# --- I.5: the Italian words in the code ---
WORDS = ["della", "delle", "degli", "dello", "nella", "nelle", "nello", "sono", "questo", "questa", "perché", "anche",
         "quando", "oppure", "deve", "viene", "ogni", "già", "più", "cioè", "senza", "alla", "alle", "agli", "sulla",
         "dalla", "manca", "mancano", "errore", "giuria", "convocazione", "consegna", "cartella", "voto", "esito",
         "sigillo", "scheda", "schede", "fabbrica", "radice", "motore", "lingua", "prove", "aggiorna", "installa"]
# a word that is part of a file name (giuria.json, motore/) or of an argument (lingua=) is a 4.0 name, not prose
# the Italian names of the commands and options (installa, prove, …) are aliases: data, not prose
ALIASES = {a.lstrip("-") for sec in ("commands", "options") for v in IT.get(sec, {}).values()
           for a in ([v] if isinstance(v, str) else v)}
WORD_RE = re.compile(r"(?i)(?<![\w/.-])(" + "|".join(re.escape(w) for w in WORDS if w not in ALIASES)
                     + r")(?![\w/=-])(?!\.\w)")
EXEMPT = ("engine/compat.py", "i18n/it.json", "docs/it/", "skills/sciame-installa/", "tests/fixtures/", "db/",
          ".github/PULL_REQUEST_TEMPLATE/nuova_lingua.md", ".github/PULL_REQUEST_TEMPLATE/nuovo_professionista.md",
          ".github/ISSUE_TEMPLATE/professional_request.yml",   # bilingual, as in 4.0
          "swarmer.sh", "sciame.sh", "LICENSE")


def italian_hits(rel: str, text: str) -> list[str]:
    if rel == "engine/head.sh":   # the generated block is exempt
        text = re.sub(r"# @aliases-begin\n.*?# @aliases-end\n", "", text, flags=re.S)
    if rel.startswith("tests/") and rel.endswith(".py"):
        # in the batteries only comments, docstrings and names count: the strings are test data
        out = []
        try:
            toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
        except (tokenize.TokenError, SyntaxError):
            toks = []
        prev = None
        for t in toks:
            doc = t.type == tokenize.STRING and (prev is None or prev in (tokenize.INDENT, tokenize.NEWLINE,
                                                                          tokenize.DEDENT))
            if t.type in (tokenize.COMMENT, tokenize.NAME) or doc:
                for m in WORD_RE.finditer(t.string):
                    if not m.group(1).isupper():
                        out.append(f"{rel}:{t.start[0]}: «{m.group(1)}»")
            if t.type not in (tokenize.COMMENT, tokenize.NL):
                prev = t.type
        return out
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        if not rel.endswith((".py", ".sh", ".json")):
            line = re.sub(r"`[^`]*`", "", line)   # in prose, a code span quotes a name (an Italian line or file): data
        for m in WORD_RE.finditer(line):
            if not m.group(1).isupper():
                hits.append(f"{rel}:{n}: «{m.group(1)}»")
    return hits


def italian_words():
    files = []
    for p in sorted(SOURCE.rglob("*")):
        rel = p.relative_to(SOURCE).as_posix()
        if not p.is_file() or ".git/" in rel or "__pycache__" in rel or rel.startswith(("_work", "_lavoro")):
            continue
        if rel.startswith(EXEMPT) or rel.endswith(".it.md") or rel == "UPSTREAM":
            continue
        if p.suffix not in (".py", ".sh", ".json", ".md", ".txt", ".yml", ".yaml", "") or p.name.startswith(".") and \
                p.name != ".gitignore":
            continue
        files.append((rel, p))
    hits = []
    for rel, p in files:
        try:
            hits += italian_hits(rel, p.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            continue
    check(f"I.5: no frequent Italian word in the code and the English material ({len(files)} files)", not hits,
          "; ".join(hits[:15]))


def main():
    with tempfile.TemporaryDirectory() as b:
        base = Path(b)
        dialects_m6()
        variables_m8_m9(base)
        convening_m10(base)
        migration(base)
        unknown_config_b2(base)
        italian_messages_c3(base)
        commands(base)
        translations_k4(base)
        italian_words()
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
