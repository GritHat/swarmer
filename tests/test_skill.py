#!/usr/bin/env python3
"""Test battery of the swarmer 5.0 installation: python3 -I -B tests/test_skill.py

In temporary folders it checks the installation, the generation, the languages, the local overrides, the coexistence
with a swarm of the project (no file of the project touched or deleted), the update from a 3.x and between two 5.0
with the protected files, the approval of a new professional with the rebuild of swarmer.sh, the checks before
publishing (secrets, forbidden words, local files) and swarmer.sh from start to end. The installations are the
default one (English); the Italian names are checked by tests/test_migration.py. Exits with 1 if a check fails.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent
ENGINE = SOURCE / "engine" / "swarmer.py"
COPY_IGNORE = shutil.ignore_patterns(".git", "_work", "_lavoro", "_v31", "__pycache__")
results = []


def i18n(lang):
    out = json.loads((SOURCE / "i18n" / "en.json").read_text(encoding="utf-8"))
    p = SOURCE / "i18n" / f"{lang}.json"
    if p.is_file():
        out.update(json.loads(p.read_text(encoding="utf-8")))
    return out


EN, IT = i18n("en"), i18n("it")
STRATEGIES = ["single", "fan-out", "classic", "jury", "light-jury", "full", "plenary", "expert"]


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("ok   " if ok else "FAILED ") + name + ("" if ok or not detail else f"\n     {detail[:600]}"))


def clean_env(**extra):
    e = {k: v for k, v in os.environ.items() if not k.startswith(("SWARMER_", "SCIAME_"))}
    e.update(extra)
    return e


def py(*arg, cwd=None, env=None):
    p = subprocess.run([sys.executable, "-I", "-B", *map(str, arg)], capture_output=True, text=True, cwd=cwd,
                       stdin=subprocess.DEVNULL, env=env or clean_env())
    return p.returncode, p.stdout + p.stderr


def bash(*arg, cwd=None, env=None):
    p = subprocess.run(["bash", *map(str, arg)], capture_output=True, text=True, cwd=cwd, stdin=subprocess.DEVNULL,
                       env=env or clean_env())
    return p


def swarmer(s: Path, *arg, env=None):
    return py(s / "engine" / "swarmer.py", "--swarm", s, *arg, env=env)


def install(root: Path, *extra):
    root.mkdir(parents=True, exist_ok=True)
    return py(ENGINE, "install", "--from", SOURCE, "--root", root, *extra)


def languages():
    return sorted(p.stem for p in (SOURCE / "i18n").glob("*.json") if (SOURCE / "docs" / p.stem).is_dir())


def tree(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8", errors="replace")
            for p in sorted(root.rglob("*")) if p.is_file()}


def repo_copy(dst: Path, src: Path = SOURCE) -> None:
    """A copy of the repository as a ZIP of it holds it: in a git checkout, the files git tracks or would track (never
    an ignored one, such as the .claude/ an installation writes at the root of the checkout); without git, the tree
    without COPY_IGNORE."""
    q = None
    if (src / ".git").exists() and shutil.which("git"):
        q = subprocess.run(["git", "-C", str(src), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                           capture_output=True, stdin=subprocess.DEVNULL)
    if q is None or q.returncode != 0:
        shutil.copytree(src, dst, ignore=COPY_IGNORE)
        return
    dst.mkdir(parents=True)
    for rel in sorted(set(os.fsdecode(x) for x in q.stdout.split(b"\0") if x)):
        s, d = src / rel, dst / rel
        if not (s.is_file() or s.is_symlink()) or "__pycache__" in Path(rel).parts:
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        if s.is_symlink():
            d.symlink_to(os.readlink(s))
        else:
            shutil.copy2(s, d)


def repo_copy_check(base: Path) -> None:
    """repo_copy on a toy checkout: the ignored .claude/ and _work/ stay out, a tracked and an untracked file go in."""
    r = base / "toy-checkout"
    (r / ".claude" / "agents").mkdir(parents=True)
    (r / ".claude" / "agents" / "mine.md").write_text("private\n")
    (r / "_work").mkdir()
    (r / "_work" / "x.txt").write_text("x\n")
    (r / ".gitignore").write_text("/.claude/\n_work/\n")
    (r / "tracked.txt").write_text("t\n")
    env = dict(clean_env(), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null")
    for a in (["init", "-q"], ["add", "tracked.txt", ".gitignore"]):
        subprocess.run(["git", "-C", str(r), *a], check=True, env=env, capture_output=True)
    (r / "untracked.txt").write_text("u\n")
    c = base / "toy-copy"
    repo_copy(c, r)
    got = sorted(p.relative_to(c).as_posix() for p in c.rglob("*") if p.is_file())
    check("repo_copy copies what git tracks or would track, never an ignored file (.claude/, _work/)",
          got == [".gitignore", "tracked.txt", "untracked.txt"], got)


def aligned(out):
    return any(t["cli_aligned"].split("{profiles}")[1].strip() in out for t in (EN, IT))


def battery(base: Path):
    d = json.loads((SOURCE / "db" / "professionals.json").read_text(encoding="utf-8"))
    active = [v for v in d["entries"] if v.get("status", "active") == "active"]
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(SOURCE / "engine"))
    import paths as S

    # 1. simple installation
    r = base / "simple"
    rc, out = install(r)
    check("simple installation", rc == 0, out)
    agents = sorted((r / ".claude" / "agents").glob("swarmer-*.md"))
    check(f"one agent per active entry ({len(active)})", len(agents) == len(active), str(len(agents)))
    skills = sorted(p.parent.name for p in (r / ".claude" / "skills").glob("*/SKILL.md"))
    check("nine skills", skills == sorted(["swarmer"] + [f"swarmer-{x}" for x in STRATEGIES]), str(skills))
    rc, out = swarmer(r / "swarmer", "check")
    check("check after the installation: aligned", aligned(out), out)
    rc, out = py(r / "swarmer" / "generate_agents.py", "--check")
    check("generate_agents.py --check at the root works", aligned(out), out)
    rc, out = py(r / "swarmer" / "convene.py", "roles", "--question", "a Kalman filter")
    check("convene.py roles at the root works", rc == 0 and "swarmer-kalman" in out, out)
    rc, out = swarmer(r / "swarmer", "classic", "--show", "--profile", "code", "test")
    check("launch with --show (as in 3.1)", rc == 0 and "/swarmer-classic profile=code test" in out, out)
    rc, out = swarmer(r / "swarmer", "fan-out", "--show", "--roles", "sviluppatore", "--language", "en", "x")
    check("launch of the fan-out with roles and language", rc == 0 and "roles=sviluppatore language=en" in out, out)
    rc, out = swarmer(r / "swarmer", "light-jury", "--show", "x")
    check("launch of the light jury", rc == 0 and "/swarmer-light-jury x" in out, out)
    lj = (r / ".claude" / "skills" / "swarmer-light-jury" / "SKILL.md").read_text()
    check("the skill of the light jury carries the test before the vote", "TEST-OUTCOME" in lj and "TO_JURY" in lj)
    rc, out = swarmer(r / "swarmer", "single", "--show", "--roles", "nonexistent", "x")
    check("an unknown role is refused before opening Claude", rc == 1, out)
    plen = (r / ".claude" / "skills" / "swarmer-plenary" / "SKILL.md").read_text()
    check("plenary and full only on request of the user", "disable-model-invocation: true" in plen and
          "disable-model-invocation: true" in (r / ".claude" / "skills" / "swarmer-full" / "SKILL.md").read_text()
          and "disable-model-invocation" not in (r / ".claude" / "skills" / "swarmer-single" / "SKILL.md").read_text())
    sub = [v for v in active if v["type"] == "subprofessional"]
    if sub:
        t = (r / ".claude" / "agents" / f"swarmer-{sub[0]['id']}.md").read_text()
        check("a sub-professional names its parent", f"swarmer-{sub[0]['parent']}" in t)
    rc, out = py(r / "swarmer" / "convene.py", "prepare", "--name", "v", "--strategy", "fan-out", "--profile", "code",
                 "--question", "q", "--n", "3", "--form", "race", "--rule", "first", "--dest", base / "conv")
    check("convene.py prepares the fan-out (race, 3 agents)", rc == 0 and out.count("agent-") >= 3, out)
    rc, out = py(r / "swarmer" / "convene.py", "prepare", "--name", "v2", "--strategy", "fan-out", "--profile", "code",
                 "--question", "q", "--n", "3", "--form", "race", "--dest", base / "conv")
    check("the fan-out race without a choice rule is refused", rc != 0, out)

    # 2. the languages, back and forth
    before = tree(r / ".claude")
    for lang in languages():
        rc, out = swarmer(r / "swarmer", "language", lang)
        check(f"language {lang}", rc == 0, out)
        rc, out = swarmer(r / "swarmer", "check")
        check(f"check in {lang}", aligned(out), out)
    rc, _ = swarmer(r / "swarmer", "language", "en")
    check("going back to English regenerates exactly the same files", tree(r / ".claude") == before)
    rc, out = swarmer(r / "swarmer", "language", "xx")
    check("a language that does not exist is refused", rc == 1, out)

    # 3. local overrides: priority, local-only roles, no file of the project touched
    r = base / "local"
    (r / ".claude" / "agents").mkdir(parents=True)
    project_agent = "---\nname: swarmer-own\ndescription: x\n---\nagent written by hand by the project\n"
    (r / ".claude" / "agents" / "swarmer-own.md").write_text(project_agent)
    rc, out = install(r)
    check("installation with an agent of the project", rc == 0, out)
    check("the agent of the project is not touched", (r / ".claude" / "agents" / "swarmer-own.md").read_text() == project_agent)
    (r / "swarmer" / "local" / "AGENTS.md").write_text(
        "# local cards\n\n### 1. Guarantor of project X — `swarmer-garante`\n\n- **In short:** guarantor with the details "
        "of the project.\n- **Core:** decision.\n\nReserved local card.\n\n### 2. Local-only expert — `swarmer-only-here`\n\n"
        "- **In short:** exists only in the project.\n\nNothing else.\n")
    rc, out = swarmer(r / "swarmer", "regenerate")
    t = (r / ".claude" / "agents" / "swarmer-garante.md").read_text()
    check("the local card has priority over the generic role", "Reserved local card" in t and "Guarantor of project X" in t, t[:300])
    check("a local-only role becomes an agent", (r / ".claude" / "agents" / "swarmer-only-here.md").is_file())
    rc, out = swarmer(r / "swarmer", "check")
    check("check with the overrides", aligned(out), out)
    (r / "swarmer" / "local" / "AGENTS.md").write_text("# no card\n")
    swarmer(r / "swarmer", "regenerate")
    check("override removed, the generic role is back",
          "Reserved local card" not in (r / ".claude" / "agents" / "swarmer-garante.md").read_text())
    check("local-only role removed, its generated agent disappears", not (r / ".claude" / "agents" / "swarmer-only-here.md").exists())
    check("the agent of the project is still there", (r / ".claude" / "agents" / "swarmer-own.md").read_text() == project_agent)

    # 4. a project with a swarm of its own (its own swarmer/ folder, agents generated by itself with a similar note)
    r = base / "project"
    (r / "swarmer").mkdir(parents=True)
    (r / ".claude" / "agents").mkdir(parents=True)
    own = ("# The cards of the project\n\n### 1. Formalist — `swarmer-formalista`\n\n- **In short:** proves things of "
           "the project.\n- **Core:** theoretical.\n\nDetails of the project.\n")
    (r / "swarmer" / "AGENTS.md").write_text(own)
    for x in ("formalista", "dlm"):
        (r / ".claude" / "agents" / f"swarmer-{x}.md").write_text(
            f"---\nname: swarmer-{x}\ntools: Read\n---\n<!-- Generated by swarmer/generate_agents.py from the card «1. X» "
            "of swarmer/AGENTS.md: do not edit by hand. -->\nproject\n")
    before_project = tree(r)
    rc, out = install(r, "--folder", "swarmer/skill", "--local", "swarmer", "--project-managed")
    check("installation on top of a project with a swarm of its own", rc == 0, out)
    after = tree(r)
    touched = [k for k, v in before_project.items() if after.get(k) != v]
    check("no file of the project touched or deleted", not touched, str(touched))
    check("the overrides managed by the project are not written",
          (r / ".claude" / "agents" / "swarmer-formalista.md").read_text() == before_project[".claude/agents/swarmer-formalista.md"])
    check("the extra generic roles are added", (r / ".claude" / "agents" / "swarmer-architetto.md").is_file())
    rc, out = swarmer(r / "swarmer" / "skill", "check")
    check("check in the overlapping project", aligned(out), out)
    rc, out = swarmer(r / "swarmer" / "skill", "remove")
    after = tree(r)
    check("remove takes away only the files of the swarm", all(after.get(k) == v for k, v in before_project.items())
          and not (r / ".claude" / "agents" / "swarmer-architetto.md").exists(), out)

    # 5. update from a 3.x (Italian, as every 3.x): its cards and agents are replaced, those of the project are not
    r = base / "from31"
    (r / "sciame").mkdir(parents=True)
    (r / ".claude" / "agents").mkdir(parents=True)
    (r / ".claude" / "skills" / "sciame-singolo").mkdir(parents=True)
    (r / "sciame" / "VERSIONE").write_text("3.1 abcdef\n")
    (r / "sciame" / "AGENTI.md").write_text("### 1. Formalista — `sciame-formalista`\n")
    prompt31 = "Sei il ruolo «Formalista» (scheda 1) dello sciame di agenti: rende precisi gli enunciati"
    (r / "sciame" / "catalogo.json").write_text(json.dumps({"ruoli": [{"sigla": "formalista", "prompt": prompt31}]}))
    note31 = "<!-- Generato da sciame/genera_agenti.py dalla scheda «{}» di sciame/AGENTI.md: non modificare a mano. -->"
    (r / ".claude" / "agents" / "sciame-formalista.md").write_text(
        "---\nname: sciame-formalista\n---\n\n" + note31.format("1. Formalista") + "\n\n" + prompt31 + "\n")
    (r / ".claude" / "agents" / "sciame-mio.md").write_text("---\nname: sciame-mio\n---\n" + note31.format("9. Mio") + "\nother\n")
    (r / ".claude" / "skills" / "sciame-singolo" / "SKILL.md").write_text(
        "<!-- Generato da sciame/genera_agenti.py dai documenti di sciame/: non modificare a mano. -->\n")
    rc, out = install(r, "--folder", "sciame", "--language", "it")
    check("update from a 3.x, with the backup copy", rc == 0 and "backup" in out, out)
    check("the agent of the 3.x is replaced", S.is_generated(r / ".claude" / "agents" / "sciame-formalista.md"))
    check("the skill of the 3.x is replaced", S.is_generated(r / ".claude" / "skills" / "sciame-singolo" / "SKILL.md"))
    check("an agent with the same note but outside the 3.x catalog is not touched",
          "other" in (r / ".claude" / "agents" / "sciame-mio.md").read_text())
    check("the backup copy of the 3.x is there", any(p.name.startswith("sciame.before-") for p in r.iterdir()))

    # 6. update between two 5.0: protected files and merged database
    r = base / "simple"
    s = r / "swarmer"
    card = s / "docs" / "en" / "HYPOTHESIS_CARD.md"
    card.write_text(card.read_text() + "\nA line of the project.\n")
    rc, out = install(r)
    check("update: a file changed in the project is protected", rc == 0 and "A line of the project." in card.read_text()
          and (card.parent / "HYPOTHESIS_CARD.md.new").is_file(), out)

    # 7. approval of a new professional: database, agents, swarmer.sh, requests closed
    entry = {"id": "test-new", "type": "subprofessional", "parent": "statistico", "core": "sperimentale",
             "texts": {l: {"name": f"Test {l}", "short": "a test entry.", "keywords": ["test"],
                           "body": "**Mission.** Test.\n"} for l in languages()}}
    f = base / "entry.json"
    f.write_text(json.dumps(entry))
    reg = s / "EXPERT_REQUESTS.md"
    check("the expert request register is created at the installation", reg.is_file())
    rc, out = swarmer(s, "approve", f)
    check("approve a new sub-professional", rc == 0, out)
    check("the new agent is there", (r / ".claude" / "agents" / "swarmer-test-new.md").is_file())
    check("swarmer.sh rebuilt with the new entry", (s / "swarmer.sh").is_file() and "test-new" in (s / "swarmer.sh").read_text())
    check("the proposal for the repository is there", (s / "proposals" / "test-new.json").is_file())
    rc, out = swarmer(s, "approve", f)
    check("the same id twice is refused", rc == 1, out)
    entry2 = dict(entry, id="test-secret")
    fake = "gh" + "p_" + "a1B2" * 9  # built here, so that the file itself does not contain a fake secret
    entry2["texts"] = {l: dict(t, body=f"key {fake}\n") for l, t in entry["texts"].items()}
    f.write_text(json.dumps(entry2))
    rc, out = swarmer(s, "approve", f)
    check("an entry with a secret is refused", rc == 1 and "secret" in out, out)
    reserved = " ".join(["project", "reserved", "zeta"])  # built here, as the fake secret
    (s / "local" / "FORBIDDEN.txt").write_text(reserved + "\n")
    entry3 = dict(entry, id="test-forbidden")
    entry3["texts"] = {l: dict(t, short=f"works on the {reserved.title()}.") for l, t in entry["texts"].items()}
    f.write_text(json.dumps(entry3))
    rc, out = swarmer(s, "approve", f)
    check("an entry with a word forbidden by the project is refused", rc == 1 and "forbidden" in out, out)
    entry4 = dict(entry, id="test-orphan", parent="does-not-exist")
    f.write_text(json.dumps(entry4))
    rc, out = swarmer(s, "approve", f)
    check("a sub-professional with a parent that does not exist is refused", rc == 1, out)
    if len(languages()) > 1:
        # K.1: English is mandatory, the other languages are optional; in an English installation an entry with only
        # another language is refused
        entry5 = dict(entry, id="test-one-language")
        entry5["texts"] = {"it": entry["texts"]["it"]}
        f.write_text(json.dumps(entry5))
        rc, out = swarmer(s, "approve", f)
        check("K.1: an entry without English in an English installation is refused", rc == 1 and "English" in out, out)
        entry5["texts"] = {"en": entry["texts"]["en"]}
        entry5["texts"]["en"] = dict(entry5["texts"]["en"], body="")
        f.write_text(json.dumps(entry5))
        rc, out = swarmer(s, "approve", f)
        check("K.1: an entry with incomplete English texts is refused", rc == 1, out)

    # 8. swarmer.sh from start to end
    sh = s / "swarmer.sh"
    new = base / "from_sh"
    new.mkdir()
    p = bash(sh, "-C", new, "install")
    check("swarmer.sh installs in a new project", p.returncode == 0, p.stdout + p.stderr)
    check("the project installed by swarmer.sh has the approved professional",
          (new / ".claude" / "agents" / "swarmer-test-new.md").is_file())
    check("swarmer.sh carries neither the local folder nor the forbidden words",
          reserved not in sh.read_text().lower()
          and not any(x.startswith("#==== swarmer.sh: file local/") for x in sh.read_text().splitlines()))
    p = bash(new / "swarmer" / "swarmer.sh", "check", cwd=new)
    check("swarmer.sh check from the installed copy", aligned(p.stdout), p.stdout + p.stderr)
    p = bash(new / "swarmer" / "swarmer.sh", "singolo", "--mostra", "x", cwd=new)
    check("the Italian aliases of the commands (singolo --mostra)", p.returncode == 0 and "/swarmer-single" in p.stdout,
          p.stdout + p.stderr)

    # 10. the checks of the validation pass
    # B1: a swarmer/ folder that is not a swarm is not touched
    r = base / "b1"
    (r / "swarmer").mkdir(parents=True)
    (r / "swarmer" / "convene.py").write_text("of the project\n")
    before = tree(r)
    rc, out = install(r)
    check("B1: a foreign swarmer/ folder is refused and stays intact", rc == 1 and tree(r) == before, out)
    rc, out = install(r, "--folder", "swarmer/skill")
    check("B1: with --folder swarmer/skill it installs alongside", rc == 0
          and (r / "swarmer" / "convene.py").read_text() == "of the project\n", out)
    # B2: -C … update respects the folder of config.json
    sh = SOURCE / "swarmer.sh"
    q = bash(sh, "-C", r, "update")
    after = tree(r / "swarmer")
    check("B2: -C <project> update writes in swarmer/skill, not in swarmer/",
          q.returncode == 0 and after.get("convene.py") == "of the project\n" and not (r / "swarmer" / "engine").exists(),
          q.stdout + q.stderr)
    # B4: the forbidden words of the configured local folder
    r = base / "b4"
    (r / "proj").mkdir(parents=True)
    (r / "proj" / "AGENTS.md").write_text("### 1. Mine — `swarmer-mine`\n\n- **In short:** local.\n")
    (r / "proj" / "FORBIDDEN.txt").write_text("secretword\n")
    rc, out = install(r, "--folder", "skill", "--local", "proj")
    entry = {"id": "check-b4", "type": "professional", "core": "critico",
             "texts": {l: {"name": "Check", "short": "talks about SecretWord.", "keywords": ["x"], "body": "**Mission.** x.\n"}
                       for l in languages()}}
    f = base / "b4.json"
    f.write_text(json.dumps(entry))
    rc, out = swarmer(r / "skill", "approve", f)
    check("B4: FORBIDDEN.txt of the configured local folder stops approve", rc == 1 and "forbidden" in out, out)
    (r / "proj" / "FORBIDDEN.txt").unlink()
    entry["texts"] = {l: dict(x, short="clean.") for l, x in entry["texts"].items()}
    f.write_text(json.dumps(entry))
    rc, out = swarmer(r / "skill", "approve", f)
    check("B4: with local overrides and without FORBIDDEN.txt approve stops", rc == 1 and "FORBIDDEN" in out, out)
    # G1: import-cards brings the cards into the local overrides, never into the database
    db_before = (r / "skill" / "db" / "professionals.json").read_text()
    old = base / "agents31.md"
    old.write_text("### 9. Private — `swarmer-private`\n\n- **In short:** of the project.\n- **Core:** critico e divergente.\n")
    (r / "proj" / "FORBIDDEN.txt").write_text("# nothing\n")
    rc, out = swarmer(r / "skill", "import-cards", old)
    check("G1: import-cards goes into the local overrides and the database does not change",
          rc == 0 and (r / "skill" / "db" / "professionals.json").read_text() == db_before
          and "swarmer-private" in (r / "proj" / "AGENTS.md").read_text(), out)
    entry2 = dict(entry, id="private")
    f.write_text(json.dumps(entry2))
    rc, out = swarmer(r / "skill", "approve", f)
    check("G1: approve refuses the id of a local card", rc == 1 and "local card" in out, out)
    # G11: atomic approve
    entry3 = dict(entry, id="check-g11", parent="does-not-exist", type="subprofessional")
    f.write_text(json.dumps(entry3))
    rc, out = swarmer(r / "skill", "approve", f)
    check("G11: a failed approve leaves the database as it was",
          rc == 1 and (r / "skill" / "db" / "professionals.json").read_text() == db_before, out)
    # G12: the generated texts name the true folder
    sk = (r / ".claude" / "skills" / "swarmer-classic" / "SKILL.md").read_text()
    check("G12: in the installation in skill/ the skills name skill/convene.py, not swarmer/convene.py",
          "skill/convene.py" in sk and "swarmer/convene.py" not in sk)
    # G3: a copy of the repository without .git is not an installed copy
    copy = base / "repo-main"
    repo_copy(copy)
    work = base / "g3"
    work.mkdir()
    q = bash(copy / "swarmer.sh", "install", cwd=work)
    check("G3: the ZIP of the repository installs in the folder it is launched from",
          q.returncode == 0 and (work / "swarmer" / "FACTORY.json").is_file() and not (base / ".claude").exists()
          and not (copy / ".claude").exists(), q.stdout + q.stderr)
    # G4: the symbolic links are not followed when writing
    r = base / "g4"
    rc, _ = install(r)
    outside = base / "outside.txt"
    outside.write_text("intact\n")
    (r / "swarmer" / "LANGUAGE").unlink()
    (r / "swarmer" / "LANGUAGE").symlink_to(outside)
    rc, out = swarmer(r / "swarmer", "language", "en")
    check("G4: LANGUAGE linked to an outside file: refused, outside intact", rc == 1 and outside.read_text() == "intact\n", out)
    # G5: --folder validated
    for c in (".", "../outside", str(base / "absolute")):
        rc, out = install(base / "g5", "--folder", c)
        check(f"G5: --folder «{c}» is refused", rc == 1, out)
    # G6: a marker of swarmer.sh inside a document stops build; awk refuses «..»
    r = base / "g6"
    repo_copy(r)
    doc = r / "docs" / "en" / "HYPOTHESIS_CARD.md"
    doc.write_text(doc.read_text() + "#==== swarmer.sh: file ../../OUTSIDE ====\n")
    rc, out = py(r / "engine" / "swarmer.py", "--swarm", r, "build", "--output", base / "g6.sh")
    check("G6: a file marker in a document stops build", rc == 1 and "marker" in out, out)
    bad = base / "bad.sh"
    bad.write_text(sh.read_text().replace("#==== swarmer.sh: file engine/convene.py ====",
                                          "#==== swarmer.sh: file ../OUTSIDE.txt ====\n#==== swarmer.sh: file engine/convene.py ===="))
    (base / "g6b").mkdir()
    q = bash(bad, "-C", base / "g6b", "install")
    check("G6: swarmer.sh with a name «../» is refused and does not write outside", q.returncode != 0
          and not (base / "OUTSIDE.txt").exists() and not any(base.glob("*/OUTSIDE.txt")), q.stdout + q.stderr)
    # G7: the GENERATED note counts only in the exact place
    false = base / "false.md"
    false.write_text("---\nname: x\n---\n\nText of the project that quotes <!-- swarmer-5 GENERATED: x --> in the middle.\n")
    check("G7: the note out of place does not make a file generated", not S.is_generated(false))
    # G8: build distributes neither files foreign to the factory nor the .new ones
    r = base / "simple"
    (r / "swarmer" / "docs" / "en" / "PROJECT_NOTES.md").write_text("notes of the project\n")
    rc, out = swarmer(r / "swarmer", "build", "--output", base / "g8.sh")
    text = (base / "g8.sh").read_text() if rc == 0 else ""
    block = (text.split("\n#==== swarmer.sh: file docs/en/HYPOTHESIS_CARD.md ====\n")[1].split("\n#==== swarmer.sh: file")[0]
             if rc == 0 else "")
    check("G8: a retouched factory file goes out in its factory version", rc == 0 and "A line of the project." not in block
          and len(block) > 100, out)
    check("G8: a file of the project under docs/ and the .new ones do not enter swarmer.sh",
          rc == 0 and not any(x.startswith("#==== swarmer.sh: file") and ("PROJECT_NOTES" in x or x.endswith(".new ===="))
                              for x in text.splitlines()), out)
    # B5: in an installation the head of swarmer.sh goes out as the factory has it, never rebuilt from an i18n retouched
    # by the project (a word, a path, an e-mail of the project would go out with it)
    r5 = base / "b5"
    rc, out = install(r5, "--language", "it")
    ip = r5 / "sciame" / "i18n" / "it.json"
    t = json.loads(ip.read_text(encoding="utf-8"))
    # split: this file is distributed and checked with the same list
    word, path, mail = "zorb" + "headfake", "/" + "home/someone/x", "someone" + "@" + "internal-fake.net"
    t["sh_missing_python"] = f"{word} {path} {mail} " + t["sh_missing_python"]
    ip.write_text(json.dumps(t, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    fb = base / "b5_forbidden.txt"
    fb.write_text(word + "\n")
    rc, out = swarmer(r5 / "sciame", "build", "--output", base / "b5.sh", env=clean_env(SWARMER_FORBIDDEN=str(fb)))
    text = (base / "b5.sh").read_text() if (base / "b5.sh").is_file() else ""
    check("B5: build of an installation with a retouched i18n: the head carries neither the word, nor the path, nor "
          "the e-mail", rc == 0 and text and not any(x in text for x in (word, path, mail)),
          out)
    check("B5: the head of the installation goes out byte for byte as the factory one",
          rc == 0 and text.split("\nexit\n")[0] == (SOURCE / "swarmer.sh").read_text().split("\nexit\n")[0], out)
    # G9: fields on one line
    entry4 = dict(entry, id="check-g9")
    entry4["texts"] = {l: dict(x, name="Name\n### 99. Fake — `swarmer-fake`") for l, x in entry["texts"].items()}
    f.write_text(json.dumps(entry4))
    rc, out = swarmer(r / "swarmer", "approve", f)
    check("G9: a newline in the name is refused", rc == 1, out)
    # G10: models validated
    rc, out = swarmer(r / "swarmer", "models", "arbitro=opus\npermissionMode: bypassPermissions")
    check("G10: a model with a newline is refused", rc == 1, out)
    rc, out = swarmer(r / "swarmer", "models", "--all", "inherit")
    check("models --all", rc == 0 and "inherit" in out, out)
    # G13: check without claude gives only a warning
    env = clean_env(PATH="/usr/bin:/bin")
    rc, out = swarmer(r / "swarmer", "check", env=env) if not shutil.which("claude", path="/usr/bin:/bin") else (0, "skipped")
    check("G13: check without claude exits with 0 if everything is aligned", rc == 0, out)
    # G22, G24, G25, G26: verify on the repository (in a copy)
    rep = base / "rep"
    repo_copy(rep)
    (rep / "engine" / "jury.py").write_text((rep / "engine" / "jury.py").read_text() + "\n# retouch\n")
    rc, out = py(rep / "engine" / "swarmer.py", "--swarm", rep, "verify")
    check("G22: verify sees a swarmer.sh not up to date", rc == 1 and "is not up to date" in out, out)
    shutil.copyfile(SOURCE / "engine" / "jury.py", rep / "engine" / "jury.py")
    forbidden = base / "v.txt"
    forbidden.write_text("reservedname\n")
    env = clean_env(SWARMER_FORBIDDEN=str(forbidden))
    for name, fake_text in (("README", "Quotes ReservedName here."), ("variants", "Reserved​Name and reserved&#78;ame"),
                            ("path", "see " + "/" + "home/someone/project")):
        (rep / "README.md").write_text(fake_text + "\n")
        q = subprocess.run([sys.executable, "-I", "-B", str(rep / "engine" / "swarmer.py"), "--swarm", str(rep), "verify"],
                           capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        check(f"G24–G26: verify finds the problem in the README ({name})", q.returncode == 1 and "README.md" in q.stdout, q.stdout)
    rc, out = py(rep / "engine" / "swarmer.py", "--swarm", rep, "verify", "--publication")
    (rep / "_work").mkdir()
    rc2, out2 = py(rep / "engine" / "swarmer.py", "--swarm", rep, "verify", "--publication")
    check("G2: verify --publication refuses the work folders", rc2 == 1 and "_work" in out2, out2)
    (rep / "_work").rmdir()
    (rep / ".codex" / "agents").mkdir(parents=True)
    (rep / ".codex" / "agents" / "x.toml").write_text('name = "x"\n')
    (rep / "GEMINI.md").write_text("# mine\n")
    rc3, out3 = py(rep / "engine" / "swarmer.py", "--swarm", rep, "verify", "--publication")
    check("G2 (M-2): verify --publication refuses the files of the targets at the root (.codex/, GEMINI.md)",
          rc3 == 1 and ".codex: a file of a target" in out3 and "GEMINI.md: a file of a target" in out3, out3)
    gi = (SOURCE / ".gitignore").read_text(encoding="utf-8").splitlines()
    check("G2 (M-2): .gitignore excludes the trees of the targets, anchored at the root (.claude-plugin stays)",
          all(x in gi for x in ("/.claude/", "/.codex/", "/.agents/", "/.gemini/", "/AGENTS.md", "/GEMINI.md",
                                "/CLAUDE.md")) and ".claude-plugin" not in "\n".join(gi))

    # 11. the checks of the second pass
    rep = base / "rep2"
    repo_copy(rep)
    odd = rep / "docs" / "en" / "name with space.md"
    odd.write_text("x\n")
    rc, out = py(rep / "engine" / "swarmer.py", "--swarm", rep, "build", "--output", base / "n1.sh")
    check("N1: a file name with a space stops build", rc == 1 and "file name" in out, out)
    odd.unlink()
    (rep / "NOTE.md").write_text("a note on " + "reserved" + "name\n")
    forbidden = base / "v2.txt"
    forbidden.write_text("reservedname\n")
    q2 = subprocess.run([sys.executable, "-I", "-B", str(rep / "engine" / "swarmer.py"), "--swarm", str(rep), "verify"],
                        capture_output=True, text=True, env=clean_env(SWARMER_FORBIDDEN=str(forbidden)), stdin=subprocess.DEVNULL)
    check("N9: verify also examines a NOTE.md at the root", q2.returncode == 1 and "NOTE.md" in q2.stdout, q2.stdout)
    # N5: the folder variables of bash from the environment do not count
    r = base / "n5"
    (r / "swarmer").mkdir(parents=True)
    (r / "swarmer" / "README.md").write_text("of the project\n")
    rc, out = install(r, "--folder", "swarmer/skill")
    q3 = bash(SOURCE / "swarmer.sh", "-C", r, "update", env=clean_env(SWARM_DIR="swarmer", CARTELLA="swarmer"))
    check("N5: SWARM_DIR in the environment does not change the folder", q3.returncode == 0
          and (r / "swarmer" / "README.md").read_text() == "of the project\n" and not (r / "swarmer" / "engine").exists(),
          q3.stdout + q3.stderr)
    # N6: after approve, update still updates swarmer.sh (it does not protect it as if it were of the project)
    r = base / "n6"
    rc, _ = install(r)
    entry = {"id": "check-n6", "type": "professional", "core": "critico",
             "texts": {l: {"name": "Check", "short": "test.", "keywords": ["x"], "body": "**Mission.** x.\n"} for l in languages()}}
    f = base / "n6.json"
    f.write_text(json.dumps(entry))
    rc, out = swarmer(r / "swarmer", "approve", f)
    rc, out = install(r)
    protected = EN["cli_updated"].split("{n}")[1].split("{protected}")[0]
    check("N6: after approve, update protects neither swarmer.sh nor the database",
          rc == 0 and "swarmer.sh" not in out.split(protected)[-1] and (r / ".claude" / "agents" / "swarmer-check-n6.md").is_file(), out)
    # G1 residual: the text of a local card does not enter the public database under another id
    r = base / "g1b"
    rc, _ = install(r)
    private = "this very particular sentence of the private project describes an internal method that must never go out"
    (r / "swarmer" / "local" / "AGENTS.md").write_text("### 1. Mine — `swarmer-mine`\n\n- **In short:** local.\n\n" + private + "\n")
    entry2 = dict(entry, id="check-g1b")
    entry2["texts"] = {l: dict(x, body="**Mission.** " + private + ".\n") for l, x in entry["texts"].items()}
    f.write_text(json.dumps(entry2))
    rc, out = swarmer(r / "swarmer", "approve", f)
    check("G1: the text of a local card does not enter the public database", rc == 1 and "in common" in out, out)

    # 12. the checks of the third pass
    rep = base / "rep3"
    repo_copy(rep)
    outside_dir = base / "outside3"
    outside_dir.mkdir()
    (rep / "link").symlink_to(outside_dir)
    rc, out = py(rep / "engine" / "swarmer.py", "--swarm", rep, "verify", "--publication")
    check("X1: verify --publication refuses a symbolic link", rc == 1 and "symbolic link" in out, out)
    (rep / "link").unlink()
    forbidden = base / "v3.txt"
    forbidden.write_text("reservedname\n")
    (rep / "docs" / "en" / ("reserved" + "name.md")).write_text("x\n")
    q3 = subprocess.run([sys.executable, "-I", "-B", str(rep / "engine" / "swarmer.py"), "--swarm", str(rep), "verify"],
                        capture_output=True, text=True, env=clean_env(SWARMER_FORBIDDEN=str(forbidden)), stdin=subprocess.DEVNULL)
    check("X5: a file name with a forbidden word stops verify", q3.returncode == 1, q3.stdout)
    r = base / "x2"
    rc, _ = install(r)
    head = r / "swarmer" / "engine" / "head.sh"
    head.write_text(head.read_text() + "\n# note of the project x2\n")
    rc, out = swarmer(r / "swarmer", "build", "--output", base / "x2.sh")
    check("X2: a head.sh retouched in the project does not go out in swarmer.sh",
          rc == 0 and "note of the project x2" not in (base / "x2.sh").read_text().split("\nexit\n")[0], out)
    (r / "swarmer" / "local" / "AGENTS.md").write_text("### 1. Mine — `swarmer-mine`\n\n- **In short:** local.\n\n" + private + "\n")
    entry = {"id": "check-x3", "type": "professional", "core": "critico", "version": private,
             "texts": {l: {"name": "Check", "short": "test.", "keywords": ["x"], "body": "**Mission.** x.\n"} for l in languages()}}
    f = base / "x3.json"
    f.write_text(json.dumps(entry))
    rc, out = swarmer(r / "swarmer", "approve", f)
    check("X3: a local sentence in a field outside the texts (version) is refused", rc == 1 and "in common" in out, out)
    # X4: a local repository that does not build leaves everything as it was
    r = base / "x4"
    rc, _ = install(r)
    broken = base / "broken_rep"
    repo_copy(broken)
    (broken / "engine" / "head.sh").unlink()
    cfg = r / ".swarmer" / "config.json"
    cfg.parent.mkdir(exist_ok=True)
    cfg.write_text(json.dumps({"local_repository": str(broken)}))
    before = tree(r)
    entry4 = dict(entry, id="check-x4")
    del entry4["version"]
    f.write_text(json.dumps(entry4))
    rc, out = swarmer(r / "swarmer", "approve", f)
    after = tree(r)
    check("X4: approve with a broken local repository writes nothing", rc == 1 and after == before
          and "check-x4" not in (broken / "db" / "professionals.json").read_text(), out)
    # X6: after an update with a protected file approve works
    r = base / "x6"
    rc, _ = install(r)
    doc = r / "swarmer" / "docs" / "en" / "HYPOTHESIS_CARD.md"
    doc.write_text(doc.read_text() + "\nline of the project x6\n")
    newsrc = base / "source_x6"
    repo_copy(newsrc)
    d6 = newsrc / "docs" / "en" / "HYPOTHESIS_CARD.md"
    d6.write_text(d6.read_text() + "\nnew factory line\n")
    py(newsrc / "engine" / "swarmer.py", "--swarm", newsrc, "build", "--output", newsrc / "swarmer.sh")
    rc, out = py(newsrc / "engine" / "swarmer.py", "install", "--from", newsrc, "--root", r)
    entry6 = dict(entry4, id="check-x6")
    f.write_text(json.dumps(entry6))
    rc, out = swarmer(r / "swarmer", "approve", f)
    check("X6: after an update with a protected file, approve and build work", rc == 0, out)

    # 13. the checks of the fourth pass
    home = base / "home_y1"
    home.mkdir()
    (home / ".gitconfig").write_text("[user]\n\tname = Global\n\temail = global@example.org\n")
    r = base / "x6"
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.name", "Local"], check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.email", "local@example.org"], check=True)
    rc, out = swarmer(r / "swarmer", "propose", "check-x6", "--send", env=clean_env(HOME=str(home)))
    check("Y1: the identity shown before --yes is the global one that signs the commit",
          "Global" in out and "Local" not in out, out)
    forb = base / "v4.txt"
    forb.write_text("alphafake betafake\n")
    env4 = clean_env(SWARMER_FORBIDDEN=str(forb))
    r = base / "y2"
    install(r)
    entry = {"id": "check-y2", "type": "professional", "core": "critico",
             "texts": {l: {"name": "Check", "short": "test.", "keywords": ["x"],
                           "body": "**Mission.** x alphafake\nbetafake y.\n"} for l in languages()}}
    f = base / "y2.json"
    f.write_text(json.dumps(entry))
    rc, out = swarmer(r / "swarmer", "approve", f, env=env4)
    check("Y2: a forbidden entry split by a newline is refused", rc == 1, out)
    rep = base / "rep4"
    repo_copy(rep)
    (rep / ".venv" / "bin").mkdir(parents=True)
    (rep / ".venv" / "bin" / "python").symlink_to(sys.executable)
    with open(rep / ".gitignore", "a") as g:
        g.write(".venv/\n")
    rc, out = py(rep / "engine" / "swarmer.py", "--swarm", rep, "verify", "--publication")
    check("Y6: a link in an ignored folder does not stop verify --publication", rc == 0, out)
    (rep / "docs" / "en" / "alphafake-betafake.md").write_text("x\n")
    rc, out = py(rep / "engine" / "swarmer.py", "--swarm", rep, "verify", env=env4)
    check("Y7: an entry of several words in a file name stops verify", rc == 1, out)
    (rep / "docs" / "en" / "alphafake-betafake.md").unlink()
    # V1: an entry of several words joined by «-» or «_» in the content, or in percent encoding, stops verify
    v1 = rep / "docs" / "en" / "V1.md"
    v1.write_text("neutral text\n")
    rc, out = py(rep / "engine" / "swarmer.py", "--swarm", rep, "verify", env=env4)
    check("V1: a neutral document is not flagged", "docs/en/V1.md" not in out, out)
    pct = "".join(f"%{b:02X}" for b in "alphafake betafake".encode())
    for label, text in (("joined by «-»", "x alphafake-betafake y"), ("joined by «_»", "x alphafake_betafake y"),
                        ("in percent encoding", f"x {pct} y")):
        v1.write_text(text + "\n")
        rc, out = py(rep / "engine" / "swarmer.py", "--swarm", rep, "verify", env=env4)
        check(f"V1: an entry of several words {label} in the content stops verify",
              rc == 1 and "docs/en/V1.md" in out and "forbidden" in out, out)
    v1.unlink()
    # V1: the body of propose (from the model on disk) is checked before it is written or sent
    r = base / "v1_propose"
    install(r, "--language", "it")
    entry_v1 = {"id": "check-v1", "type": "professional", "core": "critico",
                "texts": {l: {"name": "Check", "short": "test.", "keywords": ["x"], "body": "**Mission.** x.\n"}
                          for l in languages()}}
    f.write_text(json.dumps(entry_v1))
    rc, out = swarmer(r / "sciame", "approve", f)
    tpl = r / "sciame" / "docs" / "en" / "_PR_PROPOSAL.md"
    rc, out = swarmer(r / "sciame", "propose", "check-v1", env=env4)
    check("C3: propose in an Italian installation suggests «bash sciame/sciame.sh proponi … --invia --si»",
          rc == 0 and "bash sciame/sciame.sh proponi check-v1 --invia --si" in out, out)
    tpl.write_text(tpl.read_text() + "\nalphafake_betafake\n")
    rc, out = swarmer(r / "sciame", "propose", "check-v1", env=env4)
    prs = list((r / "sciame").rglob("PR-check-v1.md"))
    check("V1: a forbidden entry in the body of propose stops it, the proposal not rewritten", rc == 1
          and "forbidden" in out and prs and all("alphafake" not in p.read_text() for p in prs), out)
    r = base / "y3"
    install(r)
    if (r / "swarmer" / "UPSTREAM").is_file():
        (r / "swarmer" / "UPSTREAM").write_text("project/retouched\n")
        rc, out = swarmer(r / "swarmer", "build", "--output", base / "y3.sh")
        check("Y3: an UPSTREAM retouched in the project does not go out in swarmer.sh",
              rc == 0 and (base / "y3.sh").read_text().split("#==== swarmer.sh: file UPSTREAM ====\n")[1].split("\n")[0]
              != "project/retouched", out)
    r = base / "d7"
    rc, out = install(r, "--folder", "swarmer//skill/")
    cfg = json.loads((r / ".swarmer" / "config.json").read_text()) if (r / ".swarmer" / "config.json").is_file() else {}
    check("d7: the saved folder is the normalized one", rc == 0 and cfg.get("folder") == "swarmer/skill", out + str(cfg))

    # 14. the checks of the fifth pass
    forb5 = base / "v5.txt"
    forb5.write_text("nfake\nalphafake-betafake\nsecretfake\n")
    env5 = clean_env(SWARMER_FORBIDDEN=str(forb5))
    rep = base / "rep5"
    repo_copy(rep)
    doc = rep / "docs" / "en" / "W1.md"
    doc.write_text("path C:\\nfake\n")
    rc, out = py(rep / "engine" / "swarmer.py", "--swarm", rep, "verify", env=env5)
    check("W1: a forbidden entry after a backslash is still found", rc == 1 and "forbidden" in out, out)
    doc.unlink()
    (rep / "docs" / "en" / "alphafake-betafake.md").write_text("x\n")
    rc, out = py(rep / "engine" / "swarmer.py", "--swarm", rep, "verify", env=env5)
    check("W2: an entry with the hyphen in a file name is still found", rc == 1 and "forbidden" in out, out)
    (rep / "docs" / "en" / "alphafake-betafake.md").unlink()
    ext = base / "upstream_outside"
    ext.write_text("secretfake/outside\n")
    (rep / "UPSTREAM").unlink()
    (rep / "UPSTREAM").symlink_to(ext)
    rc, out = py(rep / "engine" / "swarmer.py", "--swarm", rep, "build", "--output", base / "w6.sh")
    check("W6: an UPSTREAM link is refused", rc == 1 and not (base / "w6.sh").exists(), out)
    (rep / "UPSTREAM").unlink()
    (rep / "UPSTREAM").write_text("GritHat/swarmer\n")
    subprocess.run(["git", "init", "-q", str(rep)], check=True)
    (rep / "extra").mkdir()
    (rep / "extra" / "data.txt").write_text("secretfake\n")
    with open(rep / ".gitignore", "a") as g:
        g.write("data.txt\n")
    subprocess.run(["git", "-C", str(rep), "add", "-f", "extra/data.txt"], check=True)
    rc, out = py(rep / "engine" / "swarmer.py", "--swarm", rep, "verify", "--publication", env=env5)
    check("W7: a tracked file is examined even if ignored by name", rc == 1 and "extra/data.txt" in out, out)

    # 15. the checks of the sixth pass
    rep = base / "rep6"
    repo_copy(rep)
    with open(rep / ".gitignore", "a") as g:
        g.write("HYPOTHESIS_CARD.md\n")
    subprocess.run(["git", "init", "-q", str(rep)], check=True)
    r = base / "n1"
    install(r)
    (r / ".swarmer").mkdir(exist_ok=True)
    (r / ".swarmer" / "config.json").write_text(json.dumps({"local_repository": str(rep)}))
    entry = {"id": "check-n1", "type": "professional", "core": "critico",
             "texts": {l: {"name": "Check", "short": "test.", "keywords": ["x"], "body": "**Mission.** x.\n"} for l in languages()}}
    f = base / "n1.json"
    f.write_text(json.dumps(entry))
    rc, out = swarmer(r / "swarmer", "approve", f)
    check("N1: a distributed file ignored by .gitignore does not break approve with a git repository",
          rc == 0 and "check-n1" in (rep / "swarmer.sh").read_text(), out)
    forb6 = base / "v6.txt"
    forb6.write_text("secretfake\n")
    env6 = clean_env(SWARMER_FORBIDDEN=str(forb6))
    rep = base / "rep7"
    repo_copy(rep)
    (rep / "extra").mkdir()
    (rep / "extra" / "data.txt").write_text("secretfake\n")
    with open(rep / ".gitignore", "a") as g:
        g.write("/other/extra\n")
    rc, out = py(rep / "engine" / "swarmer.py", "--swarm", rep, "verify", "--publication", env=env6)
    check("N2: an anchor of .gitignore does not exclude a file git would publish", rc == 1 and "extra/data.txt" in out, out)
    with open(rep / ".gitignore", "a") as g:
        g.write("!kept.txt\n")
    rc, out = py(rep / "engine" / "swarmer.py", "--swarm", rep, "verify", "--publication", env=env6)
    check("N2: a negation in .gitignore without .git stops verify", rc == 1 and "negation" in out, out)

    # 9. verify before publishing, on the source
    rc, out = py(ENGINE, "--swarm", SOURCE, "verify")
    check("verify of the source: no problems", rc == 0 and EN["verify_clean"] in out, out)


def main():
    with tempfile.TemporaryDirectory() as base:
        battery(Path(base))
        repo_copy_check(Path(base))
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
