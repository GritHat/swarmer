#!/usr/bin/env python3
"""Test battery of swarmer-crossroads 1.0 and of the extension mechanism of swarmer 5.2:
python3 -I -B tests/test_crossroads.py [--long] [--make-fixture DIR]

Everything is built at test time in temporary folders (throwaway git repositories with GIT_CONFIG_NOSYSTEM=1,
GIT_CONFIG_GLOBAL=/dev/null, the author x <x@invalid> and fixed dates); no path of the design record is read. The groups:
the extension mechanism (enable, disable, skills, documents, coordinator block, requirements, aliases); the hunk sha
and amendment F; the acceptance rows A1-A11 and B1-B12 of the convenings crossroads and crossroads-r2, each with its
sealed expected result; the audit items; K-501..K-507 and K-102; the joint tests J1-J3; the regressions (weave = oracle
on an exhaustive small domain, the edge set, read commands write nothing, determinism). The pass rule of the A rows is
the sealed one: OK and equal to HAND with no mode or user-file change, or a blocking issue with 0 writes.
--long adds the scale cases at N=20000. --make-fixture DIR writes the J2 and the scale fixture (N=2000, ids of 96
bytes, D = the root) for the class 3 run, and nothing else. Exits with 1 if a check fails.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent
EXT = SOURCE / "extensions" / "crossroads"
ENGINE = SOURCE / "engine" / "swarmer.py"
sys.dont_write_bytecode = True
for _p in (str(EXT / "engine"), str(SOURCE / "engine")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
GENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_AUTHOR_NAME": "x",
        "GIT_AUTHOR_EMAIL": "x@invalid", "GIT_COMMITTER_NAME": "x", "GIT_COMMITTER_EMAIL": "x@invalid",
        "GIT_AUTHOR_DATE": "2026-11-17T09:30:00+01:00", "GIT_COMMITTER_DATE": "2026-11-17T09:30:00+01:00",
        "LC_ALL": "C"}
os.environ.update(GENV)
for _k in [k for k in os.environ if k.startswith(("SWARMER_", "SCIAME_"))]:
    del os.environ[_k]
import backtrack as A  # noqa: E402
import compat as C  # noqa: E402
import crossroads as X  # noqa: E402
import extensions as E  # noqa: E402
import hunksha as HS  # noqa: E402
import jury as J  # noqa: E402
import paths as S  # noqa: E402

LONG = "--long" in sys.argv
results = []
TD, TC, TR = "Crossroads-Decision", "Crossroads-Concern", "Crossroads-Reverts"
T0 = "2026-11-17T08:00:00+01:00"


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("ok   " if ok else "FAILED ") + name + ("" if ok or not detail else f"\n     {str(detail)[:900]}"))


# --- running things ---
def clean_env(**extra):
    e = {k: v for k, v in os.environ.items() if not k.startswith(("SWARMER_", "SCIAME_"))}
    e.update(extra)
    return e


def py(*arg, cwd=None):
    p = subprocess.run([sys.executable, "-I", "-B", *map(str, arg)], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, env=clean_env(), cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def bash(*arg, cwd=None):
    p = subprocess.run(["bash", *map(str, arg)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                       env=clean_env(), cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def cx(root, *argv, lang="en"):
    """crossroads in this process, as the extension mechanism calls it: (rc, stdout, stderr)."""
    ctx = {"swarm": SOURCE, "root": Path(root), "lang": lang, "state": None, "i18n": E.i18n(SOURCE, "crossroads", lang)}
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = X.main([str(a) for a in argv], ctx)
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
            if not isinstance(e.code, int) and e.code is not None:
                print(e.code, file=sys.stderr)
    return rc, out.getvalue(), err.getvalue()


def cxj(root, *argv):
    rc, out, err = cx(root, *argv)
    try:
        return rc, json.loads(out), err
    except json.JSONDecodeError:
        return rc, {"_raw": out}, err


def g(repo, *a, inp=None, check=True):
    r = subprocess.run(["git", "-c", "core.quotePath=false", "-C", str(repo), *map(str, a)], input=inp,
                       capture_output=True, env=clean_env())
    if check and r.returncode:
        raise RuntimeError("git %s: %s" % (a[:3], r.stderr.decode()[:300]))
    return r.stdout.decode("utf-8", "surrogateescape")


def W(repo, p, lines, eol="\n", final=True):
    fp = Path(repo) / p
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_bytes((eol.join(lines) + (eol if final and lines else "")).encode("utf-8"))


def Rl(repo, p):
    return (Path(repo) / p).read_bytes().decode("utf-8").split("\n")[:-1]


def ed(repo, p, i, new):
    L = Rl(repo, p)
    L[i - 1] = new
    W(repo, p, L)


def commit(repo, dec, con, msg="x", extra=""):
    g(repo, "add", "-A")
    tr = "" if dec is None else "\n\n%s: %s\n%s: %s\n%s" % (TD, dec, TC, con, extra)
    g(repo, "commit", "-q", "--allow-empty", "-F", "-", inp=(msg + tr).encode())
    return g(repo, "rev-parse", "HEAD").strip()


BASE = ["line %02d" % i for i in range(1, 61)]


def shared(changes):
    L = list(BASE)
    for i, t in changes.items():
        L[i - 1] = t
    return "\n".join(L) + "\n"


def new_repo(base, name):
    r = Path(base) / name
    r.mkdir(parents=True)
    g(r, "init", "-q", "-b", "main")
    (r / ".git" / "info").mkdir(parents=True, exist_ok=True)
    (r / ".git" / "info" / "exclude").write_text(".swarmer/\n")
    W(r, "src/shared.py", BASE)
    W(r, "docs/b.md", ["b %02d" % i for i in range(1, 11)])
    commit(r, None, None, "base")
    return r


def dec(root, name, depends=(), supersedes=(), impact="core", evidence=None, time_=T0, authority="owner",
        options="(a) yes | (b) no", chose="a", reject=("(b) not this",), question=None, rationale=None):
    """a U record through `decide`; returns its id"""
    argv = ["decide", "--question", question or f"question of {name}", "--options", options, "--chose", chose,
            "--rationale", rationale or f"because {name}", "--time", time_, "--authority", authority]
    for r_ in reject:
        argv += ["--reject", r_]
    if impact:
        argv += ["--impact", impact]
    if evidence:
        argv += ["--evidence", evidence]
    if depends:
        argv += ["--depends", " ".join(depends)]
    if supersedes:
        argv += ["--supersedes", " ".join(supersedes)]
    rc, out, err = cx(root, *argv)
    assert rc == 0, (rc, out, err)
    return out.strip()


def records(root, spec):
    """spec: [(name, [dependency names], extra kwargs)] in order; returns {name: id}"""
    ids = {}
    for item in spec:
        name, deps = item[0], item[1]
        kw = item[2] if len(item) > 2 else {}
        if "supersedes" in kw:
            kw = dict(kw, supersedes=[ids.get(x, x) for x in kw["supersedes"]])
        ids[name] = dec(root, name, depends=[ids[d] for d in deps], **kw)
    return ids


REC = [("D", []), ("F", ["D"]), ("X", []), ("Z", [])]


def snap(repo):
    """refs + HEAD + every worktree file outside .git and .swarmer, with sha256 and mode"""
    files = {}
    for top, dirs, fs in os.walk(repo):
        dirs[:] = [d for d in dirs if not (top == str(repo) and d in (".git", ".swarmer"))]
        for f in fs:
            p = os.path.join(top, f)
            st = os.lstat(p)
            data = os.readlink(p).encode() if os.path.islink(p) else open(p, "rb").read()
            files[os.path.relpath(p, repo)] = (hashlib.sha256(data).hexdigest(), oct(st.st_mode))
    return {"refs": g(repo, "for-each-ref", "--format=%(refname) %(objectname)"),
            "head": g(repo, "symbolic-ref", "-q", "HEAD", check=False).strip(), "files": files}


def tree(repo, rev):
    out = {}
    for e in g(repo, "ls-tree", "-r", "-z", rev).split("\0"):
        if e:
            meta, p = e.split("\t", 1)
            mode, _, sha = meta.split()
            out[p] = (mode, subprocess.run(["git", "-C", str(repo), "cat-file", "blob", sha], capture_output=True).stdout
                      if mode != "160000" else sha.encode())
    return out


def plan_of(root, D, *extra):
    rc, out, err = cxj(root, "plan", D, *extra)
    p = Path(root) / out["plan"] if "plan" in out else None
    return rc, (json.loads(p.read_text()) if p and p.is_file() else {}), out, err


def reverse(root, D, keep=(), tests=None, untracked=None):
    """plan D; on no blocking issue record D' and apply --execute. The sealed pass rule's raw material."""
    for p_, txt in (untracked or {}).items():
        fp = Path(root) / p_
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(txt)
    head0 = g(root, "rev-parse", "HEAD").strip()
    s0 = snap(root)
    rc, pl, out, err = plan_of(root, D, *(["--keep", *keep] if keep else []))
    res = {"plan_rc": rc, "issues": [i[0] for i in pl.get("issues", [])], "warnings": [w[0] for w in pl.get("warnings", [])],
           "radius": pl.get("radius", []), "commits": pl.get("commits_newest_first", []), "head0": head0, "pl": pl}
    if rc != 0:
        res["writes"] = snap(root) != s0
        return res
    dp = dec(root, "Dp-" + D[:8], supersedes=sorted(set(pl["radius"]) - set(keep)),
             impact=" ".join(pl["dprime_draft"]["impact"]) or "core", time_="2026-11-17T10:00:00+01:00")
    res["dprime"], res["plan_path"] = dp, Path(root) / out["plan"]
    argv = ["apply", Path(root) / out["plan"], "--dprime", dp, "--execute"] + (["--tests", tests] if tests else [])
    rc2, o2, e2 = cxj(root, *argv)
    res.update(apply_rc=rc2, apply=o2, status=o2.get("status"), apply_err=e2,
               apply_bytes=len(json.dumps(o2, sort_keys=True, ensure_ascii=False, indent=1).encode()) + 1)
    s1 = snap(root)
    res["user_files_changed"] = sorted(p for p in (untracked or {}) if s0["files"].get(p) != s1["files"].get(p))
    res["writes"] = s1["refs"] != s0["refs"]
    if res["status"] in ("OK", "OK-BROKEN"):
        res["after"] = tree(root, "HEAD")
        res["before"] = tree(root, head0)
        res["outside_changed"] = sorted(p for p in set(res["after"]) | set(res["before"])
                                        if p not in pl["files"] and res["after"].get(p) != res["before"].get(p))
    return res


def hand_ok(res, hand, modes=None):
    if res.get("status") != "OK":
        return False
    after = res["after"]
    if any(after.get(p, (None, b""))[1] != b.encode("utf-8") for p, b in hand.items()):
        return False
    if modes and any(after.get(p, ("absent",))[0] != m for p, m in modes.items()):
        return False
    return not res["outside_changed"] and not res["user_files_changed"]


def blocked(res, *kinds):
    return res["plan_rc"] == 1 and not res["writes"] and all(k in res["issues"] for k in kinds)


def text_at(res):
    return b"".join(v[1] for v in res.get("after", {}).values()).decode("utf-8", "replace")


# ======================================================================= the extension mechanism
def install(root, *extra):
    root.mkdir(parents=True, exist_ok=True)
    return py(ENGINE, "install", "--from", SOURCE, "--root", root, *extra)


def group_extensions(base):
    p = base / "ext_en"
    rc, out = install(p, "--targets", "claude,agents")
    check("extensions: install en (claude + shared targets)", rc == 0, out)
    sh = p / "swarmer" / "swarmer.sh"
    rc, out = bash(sh, "extensions")
    check("extensions: the listing names crossroads 1.0, none enabled", rc == 0 and "crossroads 1.0" in out, out)
    rc, out = bash(sh, "crossroads", "derive")
    check("extensions: a disabled extension's command is an error that says how to enable it",
          rc == 1 and "extensions --add crossroads" in out and "Traceback" not in out, out)
    claude, shared_ = p / ".claude/skills/swarmer-crossroads/SKILL.md", p / ".agents/skills/swarmer-crossroads/SKILL.md"
    classic = p / ".claude/skills/swarmer-classic/SKILL.md"
    check("extensions: no skill, document or coordinator block while disabled",
          not claude.exists() and not (p / "swarmer/CROSSROADS.md").exists()
          and "crossroads is enabled" not in classic.read_text())
    rc_h0, help0 = bash(sh, "help")
    rc, out = bash(sh, "extensions", "--add", "crossroads")
    check("extensions --add crossroads", rc == 0 and "crossroads" in out, out)
    rc_h1, help1 = bash(sh, "help")
    check("extensions: help shows the extension's own help line only once it is enabled",
          rc_h0 == 0 and rc_h1 == 0 and "EXTENSION crossroads" not in help0 and "EXTENSION crossroads" in help1
          and "check-commits" in help1, help1[-400:])
    cfg = json.loads((p / ".swarmer/config.json").read_text())
    ok = claude.is_file() and shared_.is_file()
    ct, st = (claude.read_text() if claude.is_file() else ""), (shared_.read_text() if shared_.is_file() else "")
    check("extensions: the skill is written for claude (argument-hint) and the shared target (name and description)",
          ok and "argument-hint:" in ct and "argument-hint:" not in st and "name: swarmer-crossroads" in st
          and S.is_generated(claude) and S.is_generated(shared_), ct[:300])
    check("extensions: config.json has the key extensions", cfg.get("extensions") == ["crossroads"], cfg)
    docs = [p / "swarmer/CROSSROADS.md", p / "swarmer/CROSSROADS_FORMATS.md"]
    check("extensions: the documents are in the swarm folder, generated", all(d.is_file() and S.is_generated(d) for d in docs))
    check("extensions: the coordinator block is in every strategy skill",
          all("crossroads is enabled" in (p / f".claude/skills/{n}/SKILL.md").read_text()
              for n in ("swarmer", "swarmer-classic", "swarmer-jury", "swarmer-single")))
    rc, out = bash(sh, "check")
    check("extensions: check is clean with the extension enabled", rc == 0, out)
    rc, out = bash(sh, "regenerate")
    rc2, out2 = bash(sh, "check")
    check("extensions: regenerate then check stay clean", rc == 0 and rc2 == 0, out + out2)
    rc, out = bash(sh, "crossroads", "decide", "--question", "q?", "--options", "(a) x | (b) y", "--chose", "a",
                   "--rationale", "r", "--time", T0)
    rc2, out2 = bash(sh, "crossroads", "derive")
    check("extensions: the command runs once enabled (decide, derive)",
          rc == 0 and re.fullmatch(r"U-[0-9a-f]{12}\n", out) and rc2 == 0, out + out2)
    rc, out = bash(sh, "extensions", "--remove", "crossroads")
    check("extensions --remove: the state folder is kept, said aloud",
          rc == 0 and (p / ".swarmer/crossroads/records").is_dir() and "kept" in out, out)
    check("extensions --remove: the skills, documents and coordinator block go",
          not claude.exists() and not shared_.exists() and not any(d.exists() for d in docs)
          and "crossroads is enabled" not in classic.read_text())
    rc, out = bash(sh, "check")
    check("extensions: check clean after the removal", rc == 0, out)
    # Italian: estensioni --aggiungi incroci
    q = base / "ext_it"
    rc, out = install(q, "--language", "it", "--targets", "claude")
    sq = q / "sciame" / "sciame.sh"
    rc, out = bash(sq, "estensioni", "--aggiungi", "incroci")
    sk = q / ".claude/skills/sciame-incroci/SKILL.md"
    check("extensions: estensioni --aggiungi incroci (Italian names: skill sciame-incroci, INCROCI.md)",
          rc == 0 and sk.is_file() and (q / "sciame/INCROCI.md").is_file() and (q / "sciame/FORMATI_INCROCI.md").is_file()
          and "incroci è attivo" in (q / ".claude/skills/sciame-classica/SKILL.md").read_text(), out)
    cfg = json.loads((q / ".sciame/config.json").read_text())
    check("extensions: the Italian config.json key is estensioni", cfg.get("estensioni") == ["crossroads"], cfg)
    rc, out = bash(sq, "incroci", "decidi", "--domanda", "dove?", "--opzioni", "(a) qui | (b) là", "--scelta", "a",
                   "--motivazione", "vicino", "--ora", T0)
    check("extensions: Italian command and options (incroci decidi --domanda …), store .sciame/incroci/",
          rc == 0 and len(list((q / ".sciame/incroci/records").glob("U-*.md"))) == 1, out)
    rc, out = bash(sq, "controlla")
    check("extensions: Italian check clean", rc == 0, out)
    # requirements
    import generate as G
    ms = {"a": {"name": "a", "version": "1.0", "requires": {"swarmer": ">=5.2", "extensions": {"crossroads": ">=1.0"}}},
          "crossroads": E.available(SOURCE)["crossroads"],
          "z": {"name": "z", "version": "1.0", "requires": {"swarmer": ">=9.0", "extensions": {}}}}
    errs = []
    for names in (["a"], ["z"], ["nope"]):
        try:
            E.check_requires(ms, names, G.VERSION)
            errs.append(None)
        except E.Error as e:
            errs.append(str(e))
    E.check_requires(ms, ["crossroads", "a"], G.VERSION)
    check("extensions: requires: a missing required extension, too old a swarmer, an unknown name are errors",
          all(errs) and "crossroads" in errs[0] and "9.0" in errs[1] and "nope" in errs[2], errs)
    check("extensions: --remove refuses when an enabled extension requires it",
          E.required_by(ms, ["crossroads", "a"], "crossroads") == ["a"])
    bad = base / "badext"
    shutil.copytree(SOURCE / "extensions", bad / "extensions")
    (bad / "docs" / "en").mkdir(parents=True)
    (bad / "i18n").mkdir()
    (bad / "i18n" / "en.json").write_text("{}")
    m = json.loads((bad / "extensions/crossroads/extension.json").read_text())
    m["colour"] = "red"
    (bad / "extensions/crossroads/extension.json").write_text(json.dumps(m))
    _ms, probs = E.manifests(bad)
    check("extensions: an unknown key of extension.json is an error", any("colour" in x for x in probs), probs)
    # aliases: one table for core and extensions, collision-free
    import swarmer as SW
    check("extensions: the alias table covers the extension (incroci, deriva, --da-cursore) without collisions",
          not SW.alias_collisions(SOURCE) and "incroci" in SW.A.load(SOURCE)["commands"]["crossroads"]
          and "deriva" in SW.A.load(SOURCE)["commands"]["derive"]
          and "--da-cursore" in SW.A.load(SOURCE)["options"]["--since"])
    ns = SW.cli_namespaces(SOURCE)
    check("extensions: cli_namespaces has «crossroads» and «crossroads <command>»",
          "crossroads" in ns["swarmer"]["commands"] and "extensions" in ns["swarmer"]["commands"]
          and "derive" in ns["crossroads"]["commands"] and "--since" in ns["crossroads changes"]["options"])
    group_toy(base)
    return p


def group_toy(base):
    """A toy extension in a copy of the swarm: its help line lives in its own i18n (no core edit), an alias it gives
    to a core name never reaches the table and verify reports it, a command named like a core command or like
    another extension's is refused cleanly (no traceback)."""
    import aliases as AL
    import swarmer as SW
    sw = base / "toyswarm"
    shutil.copytree(SOURCE, sw, ignore=shutil.ignore_patterns(".git", "__pycache__", "tests", "swarmer.sh", "sciame.sh"))
    t = sw / "extensions" / "context"
    (t / "engine").mkdir(parents=True)
    (t / "engine" / "context.py").write_text(
        "import argparse\n\ndef build_parser(al):\n    p = argparse.ArgumentParser(prog='context')\n"
        "    p.add_subparsers(dest='cmd').add_parser('summary')\n    return p\n\n"
        "def main(argv, ctx):\n    print('context', argv)\n    return 0\n")
    for l in ("en", "it"):
        (t / "docs" / l).mkdir(parents=True)
        (t / "docs" / l / "CONTEXT.md").write_text("# context\n")
        sec = {"commands": {"context": ["contesto"] if l == "it" else [], "check": ["controlla", "esamina"] if l == "it" else []}}
        (t / "i18n" / f"{l}.json").parent.mkdir(exist_ok=True)
        (t / "i18n" / f"{l}.json").write_text(json.dumps(sec))
    man = {"name": "context", "version": "1.0", "requires": {"swarmer": ">=5.2"}, "commands": {"context": "engine/context.py"},
           "documents": ["CONTEXT.md"]}
    (t / "extension.json").write_text(json.dumps(man))
    errs = SW.verify(sw)
    check("toy extension: verify asks for its help line in its own i18n («help»), not in docs/*/_HELP.txt",
          any("extensions/context/i18n/en.json: the key «help» has no line for the command «context»" in x for x in errs)
          and not any("_HELP.txt" in x and "context" in x for x in errs), errs)
    check("toy extension: an alias it adds to a core command (esamina for check) is reported by verify",
          any("an alias added to the core: «esamina» for the core «check»" in x for x in errs), errs)
    check("toy extension: that alias never reaches the table (esamina does not run check)",
          "esamina" not in AL.per_language(sw)["it"]["commands"]["check"]
          and "contesto" in AL.per_language(sw)["it"]["commands"]["context"])
    for l in ("en", "it"):
        d_ = json.loads((t / "i18n" / f"{l}.json").read_text())
        d_["help"] = "EXTENSION context\n  context summary    the summary\n"
        d_["commands"].pop("check")
        (t / "i18n" / f"{l}.json").write_text(json.dumps(d_))
    errs = SW.verify(sw)
    check("toy extension: with its «help» key and no core alias, verify has nothing to say about it",
          not any("context" in x for x in errs), errs)
    h = io.StringIO()
    with contextlib.redirect_stdout(h):
        print(SW.extensions_help(sw, "en"), end="")
    check("toy extension: help prints the extensions' help lines (both, in the repository)",
          "EXTENSION context" in h.getvalue() and "EXTENSION crossroads" in h.getvalue(), h.getvalue())
    for cmd, want in (("count", "is a command of swarmer"), ("crossroads", "is also a command of the extension crossroads")):
        (t / "extension.json").write_text(json.dumps(dict(man, commands={cmd: "engine/context.py"})))
        _ms, probs = E.manifests(sw)
        rc, out = py(sw / "engine" / "swarmer.py", "--swarm", sw, "verify")
        check(f"toy extension: a command named «{cmd}» is refused with a clear message, no traceback",
              "context" not in _ms and any(want in x for x in probs) and want in out and "Traceback" not in out,
              (probs, out[-600:]))



# ======================================================================= hunk sha and amendment F
def hsha(path, lines):
    return hashlib.sha256(path.encode() + b"\n" + b"".join(x + b"\n" for x in lines)).hexdigest()


def group_hunksha(base):
    r = base / "hs"
    r.mkdir()
    g(r, "init", "-q", "-b", "main")
    files = {"x y.txt": b"a\nb\nc\n", "t\tab.txt": b"a\nb\n", "crlf.txt": b"a\r\nb\r\n", "noeol.txt": b"a\nc",
             "bin.dat": b"\x00\x01\x02", "café.txt": b"one\ntwo\n"}
    for n, b in files.items():
        (r / n).write_bytes(b)
    commit(r, None, None, "base")
    (r / "x y.txt").write_bytes(b"a\nB\nc\n")
    (r / "t\tab.txt").write_bytes(b"a\nB\n")
    (r / "crlf.txt").write_bytes(b"a\r\nB\r\n")
    (r / "noeol.txt").write_bytes(b"a\nC")
    (r / "bin.dat").write_bytes(b"\x00\x09\x02")
    (r / "café.txt").write_bytes(b"one\nTWO\n")
    g(r, "add", "-A")
    st = HS.staged(str(r))
    c = commit(r, None, None, "edit")
    ht = HS.hunks(str(r), c)
    want = {("x y.txt", "2,1 2,1", hsha("x y.txt", [b"-b", b"+B"])),
            ("t\tab.txt", "2,1 2,1", hsha("t\tab.txt", [b"-b", b"+B"])),
            ("crlf.txt", "2,1 2,1", hsha("crlf.txt", [b"-b\r", b"+B\r"])),
            ("noeol.txt", "2,1 2,1", hsha("noeol.txt", [b"-c", HS.MARKER, b"+C", HS.MARKER])),
            ("bin.dat", "BINARY", "BINARY"),
            ("café.txt", "2,1 2,1", hashlib.sha256("café.txt\n-two\n+TWO\n".encode()).hexdigest())}
    got = {(p, hdr, hs) for p, hdr, hs, k in ht}
    check("HS1-HS4: space and TAB paths, CRLF, the no-EOL marker, binary, café: the §3.3 formula", got == want,
          sorted(got ^ want))
    check("K-501 (F-1): the staged hunk keys (diff --cached -O/dev/null, rc 0) = the diff-tree keys of the commit",
          {(p, hdr, hs) for p, hdr, hs, k in st} == got)
    sealed = subprocess.run(["git", *HS.PIN_C, "-C", str(r), "diff", "--cached", *HS.PIN_F, "HEAD~1"],
                            capture_output=True, env=clean_env())
    dt = subprocess.run(["git", *HS.PIN_C, "-C", str(r), "diff-tree", "-r", "--root", "--no-commit-id", *HS.PIN_F, c],
                        capture_output=True, env=clean_env())
    check("K-501 evidence: diff-tree accepts the sealed pin; porcelain diff with it exits 128 on this git, or works",
          dt.returncode == 0 and sealed.returncode in (0, 128), (sealed.returncode, sealed.stderr[:120]))
    # F-2: typechange, in the index and in a commit
    (r / "link").write_text("target\n")
    commit(r, None, None, "file")
    (r / "link").unlink()
    os.symlink("x y.txt", r / "link")
    g(r, "add", "-A")
    try:
        st2, err = HS.staged(str(r)), None
    except Exception as e:
        st2, err = [], repr(e)
    c2 = commit(r, None, None, "typechange")
    ht2 = HS.hunks(str(r), c2)
    check("K-502 (F-2): a typechange gives one UNSUPPORTED entry and no hunk sha, no exception (index and commit)",
          err is None and st2 == [("link", "UNSUPPORTED", "UNSUPPORTED", 0)] and ht2 == st2, (err, st2, ht2))
    s0 = sorted(p.name for p in (r / ".swarmer/crossroads/records").glob("*")) if (r / ".swarmer").exists() else []
    (r / "link").unlink()
    (r / "link").write_text("back\n")
    g(r, "add", "-A")
    rc, out, err = cx(r, "realize", "U-000000000000", "--concern", "core")
    s1 = sorted(p.name for p in (r / ".swarmer/crossroads/records").glob("*")) if (r / ".swarmer/crossroads/records").exists() else []
    check("K-502: realize refuses a staged typechange with UNSUPPORTED, exit 1, nothing written",
          rc == 1 and "UNSUPPORTED" in err and s0 == s1, (rc, out, err))
    commit(r, None, None, "back to a file")
    os.symlink("back", r / "newlink")                               # a new symbolic link (mode 120000), no typechange
    g(r, "add", "-A")
    rc, out, err = cx(r, "realize", "U-000000000000", "--concern", "core")
    s2 = sorted(p.name for p in (r / ".swarmer/crossroads/records").glob("*")) if (r / ".swarmer/crossroads/records").exists() else []
    check("F-2 symlink: realize refuses a staged symbolic link (120000) with UNSUPPORTED, exit 1, nothing written",
          rc == 1 and "UNSUPPORTED" in err and "newlink" in err and s2 == s1, (rc, out, err))
    g(r, "reset", "-q")
    (r / "newlink").unlink()


# ======================================================================= A1-A11 (Branch A rows)
def case(base, name, spec=REC):
    r = new_repo(base, name)
    return r, records(r, spec)


def group_a(base):
    # A1: revert chains; only git's own line counts; a partial revert is not a full one
    for name, tag in (("pr1", True), ("pr1u", False)):
        r, I = case(base, name)
        ed(r, "src/shared.py", 10, "D ten")
        ed(r, "src/shared.py", 40, "D forty")
        c = commit(r, I["D"], "core")
        g(r, "revert", "-n", c)
        ed(r, "src/shared.py", 40, "D forty")
        commit(r, I["X"] if tag else None, "core", 'Revert "x" (partly)\n\nThis reverts commit %s.' % c)
        res = reverse(r, I["D"])
        if tag:
            check("A1 pr1: a tagged partial revert → blocking ENTANGLED-CONTENT, 0 writes",
                  blocked(res, "ENTANGLED-CONTENT"), res["issues"])
        else:
            check("A1 pr1u: an untagged partial revert inherits D → OK = HAND, «D forty» absent",
                  hand_ok(res, {"src/shared.py": shared({})}) and "D forty" not in text_at(res), res.get("status"))
    r, I = case(base, "pr2")
    ed(r, "src/shared.py", 10, "D ten")
    c = commit(r, I["D"], "core")
    ed(r, "docs/b.md", 3, "X three")
    commit(r, I["X"], "docs", "X docs\n\nNote: an earlier draft said: This reverts commit %s. It did not." % c)
    res = reverse(r, I["D"])
    check("A1 pr2: a mention is not a revert → OK = HAND, «D ten» absent",
          hand_ok(res, {"src/shared.py": shared({})}) and "D ten" not in text_at(res), res.get("status"))
    # A2: a radius-owned revert of an outside commit is planned; a reversal of a reversal
    r, I = case(base, "rv1")
    ed(r, "src/shared.py", 20, "X twenty")
    x = commit(r, I["X"], "core")
    ed(r, "src/shared.py", 10, "D ten")
    commit(r, I["D"], "core")
    g(r, "revert", "--no-edit", x)
    body = g(r, "show", "-s", "--format=%B", "HEAD").rstrip("\n")
    g(r, "commit", "-q", "--amend", "-F", "-", inp=("%s\n\n%s: %s\n%s: core\n" % (body, TD, I["F"], TC)).encode())
    res = reverse(r, I["D"])
    check("A2 rv1: the radius revert of X is planned (REVERT-IN-RADIUS-PLANNED) → OK, «X twenty» kept",
          hand_ok(res, {"src/shared.py": shared({20: "X twenty"})}) and "REVERT-IN-RADIUS-PLANNED" in res["warnings"],
          (res.get("status"), res["warnings"]))
    r, I = case(base, "rv2")
    ed(r, "src/shared.py", 10, "D ten")
    c = commit(r, I["D"], "core")
    ed(r, "src/shared.py", 50, "X fifty")
    commit(r, I["X"], "core")
    dp = dec(r, "Dp", supersedes=[I["D"]], time_="2026-11-17T08:30:00+01:00")
    g(r, "revert", "-n", c)
    commit(r, dp, "core", "reverse D", extra="%s: %s\n" % (TR, c))
    res = reverse(r, dp)
    check("A2 rv2: plan Dp brings D back → OK = HAND",
          hand_ok(res, {"src/shared.py": shared({10: "D ten", 50: "X fifty"})}), (res.get("status"), res["issues"]))
    # A3: modes tracked; typechange → UNSUPPORTED
    for name, far in (("mode1", False), ("mode2", True)):
        r, I = case(base, name)
        W(r, "src/run.sh", ["#!/bin/sh"] + ["echo %d" % i for i in range(2, 11)])
        commit(r, I["Z"], "core")
        ed(r, "src/run.sh", 3, "echo D")
        commit(r, I["D"], "core")
        if far:
            ed(r, "src/run.sh", 9, "echo X")
        os.chmod(r / "src/run.sh", 0o755)
        g(r, "add", "-A")
        g(r, "update-index", "--chmod=+x", "src/run.sh")
        commit(r, I["X"], "core")
        L = ["#!/bin/sh"] + ["echo %d" % i for i in range(2, 11)]
        if far:
            L[8] = "echo X"
        res = reverse(r, I["D"])
        check(f"A3 {name}: the outside mode change is kept → OK, 100755 = HAND",
              hand_ok(res, {"src/run.sh": "\n".join(L) + "\n"}, {"src/run.sh": "100755"}), (res.get("status"), res["issues"]))
    r, I = case(base, "ty1")
    W(r, "src/link.txt", ["k %d" % i for i in range(6)])
    commit(r, I["Z"], "core")
    ed(r, "src/link.txt", 2, "D two")
    commit(r, I["D"], "core")
    (r / "src/link.txt").unlink()
    os.symlink("shared.py", r / "src/link.txt")
    commit(r, I["X"], "core")
    res = reverse(r, I["D"])
    check("A3 ty1: a typechange on a radius path → blocking UNSUPPORTED, no exception, 0 writes",
          blocked(res, "UNSUPPORTED"), res)
    # A4: untracked and ignored targets refused; eol through git switch
    r, I = case(base, "ut1")
    W(r, "src/gone.py", ["g %d" % i for i in range(5)])
    commit(r, I["Z"], "core")
    (r / "src/gone.py").unlink()
    commit(r, I["D"], "core")
    ed(r, "docs/b.md", 2, "X two")
    commit(r, I["X"], "docs")
    res = reverse(r, I["D"], untracked={"src/gone.py": "my scratch, not committed\n"})
    check("A4 ut1: an untracked file at a written path → REFUSED, the user file intact, 0 writes",
          str(res.get("status", "")).startswith("REFUSED untracked") and not res["user_files_changed"] and not res["writes"],
          res.get("status"))
    r, I = case(base, "ut2")
    W(r, "src/gone2.py", ["h %d" % i for i in range(5)])
    commit(r, I["Z"], "core")
    (r / "src/gone2.py").unlink()
    commit(r, I["D"], "core")
    W(r, ".gitignore", ["src/gone2.py"])
    commit(r, I["X"], "core")
    res = reverse(r, I["D"], untracked={"src/gone2.py": "ignored local notes\n"})
    check("A4 ut2: an ignored file at a written path → REFUSED, the user file intact, 0 writes",
          str(res.get("status", "")).startswith("REFUSED untracked") and not res["user_files_changed"] and not res["writes"],
          res.get("status"))
    r, I = case(base, "attr1")
    W(r, ".gitattributes", ["*.txt text eol=crlf"])
    W(r, "docs/a.txt", ["t %d" % i for i in range(1, 11)])
    commit(r, I["Z"], "docs")
    (r / "docs/a.txt").unlink()
    g(r, "checkout", "--", "docs/a.txt")
    L = [x.rstrip("\r") for x in Rl(r, "docs/a.txt")]
    L[2] = "D three"
    W(r, "docs/a.txt", L, eol="\r\n")
    commit(r, I["D"], "docs")
    L[8] = "X nine"
    W(r, "docs/a.txt", L, eol="\r\n")
    commit(r, I["X"], "docs")
    res = reverse(r, I["D"])
    hand = ["t %d" % i for i in range(1, 11)]
    hand[8] = "X nine"
    check("A4 attr1_crlf: the worktree gets CRLF through git switch",
          res.get("status") == "OK" and (r / "docs/a.txt").read_bytes() == ("\r\n".join(hand) + "\r\n").encode(),
          (res.get("status"), res["issues"]))
    # A5: the weave splits on LF only
    for code, ch in (("0c", "\x0c"), ("85", "\x85"), ("2028", " "), ("after", "\x0c"), ("crlf", None)):
        r, I = case(base, "ff_" + code)
        L = ["f %02d" % i for i in range(1, 31)]
        at = 25 if code == "after" else 5
        if ch:
            L[at - 1] = "a" + ch + "b"
        eol = "\r\n" if code == "crlf" else "\n"
        W(r, "src/ff.py", L, eol=eol)
        commit(r, I["Z"], "core")
        L2 = list(L)
        L2[19] = "D twenty"
        W(r, "src/ff.py", L2, eol=eol)
        commit(r, I["D"], "core")
        ed(r, "docs/b.md", 2, "X two")
        commit(r, I["X"], "docs")
        res = reverse(r, I["D"])
        check(f"A5 ff_{code}: OK = HAND, no WEAVE-INCONSISTENT", hand_ok(res, {"src/ff.py": eol.join(L) + eol}),
              (res.get("status"), res["issues"]))
    # A6: realized rows; an unmatched hunk blocks; rows checked when C_Rad = ∅ (A6b)
    r, I = case(base, "m2c")
    ed(r, "src/shared.py", 30, "D thirty")
    g(r, "add", "-A")
    cx(r, "realize", I["D"], "--concern", "core", "--time", T0)
    commit(r, I["D"], "core")
    g(r, "switch", "-q", "-c", "side")
    ed(r, "src/shared.py", 10, "F ten")
    g(r, "add", "-A")
    cx(r, "realize", I["F"], "--concern", "core", "--time", T0)
    commit(r, I["F"], "core")
    ed(r, "src/shared.py", 11, "X eleven")
    g(r, "add", "-A")
    cx(r, "realize", I["X"], "--concern", "core", "--time", T0)
    commit(r, I["X"], "core")
    g(r, "switch", "-q", "main")
    g(r, "merge", "-q", "--squash", "side")
    commit(r, I["F"], "core", "F and X squashed")
    g(r, "branch", "-q", "-D", "side")
    res = reverse(r, I["D"])
    check("A6 m2c: a squash of F and X with no matching realization → blocking UNREALIZED-HUNK, 0 writes",
          blocked(res, "UNREALIZED-HUNK"), res["issues"])
    r, I = case(base, "nt1")
    ed(r, "src/shared.py", 10, "D ten")
    g(r, "add", "-A")
    cx(r, "realize", I["D"], "--concern", "core", "--time", T0)
    commit(r, None, None, "D part 1 (before adoption)")
    ed(r, "src/shared.py", 40, "D forty")
    g(r, "add", "-A")
    cx(r, "realize", I["D"], "--concern", "core", "--time", "2026-11-17T08:01:00+01:00")
    commit(r, None, None, "D part 2")
    ed(r, "docs/b.md", 2, "X two")
    commit(r, I["X"], "docs")
    res = reverse(r, I["D"])
    check("A6 nt1: realized commits without trailers → NO-REALIZATION and UNPLANNED-REALIZATION, 0 writes",
          blocked(res, "NO-REALIZATION", "UNPLANNED-REALIZATION"), res["issues"])
    nr = [i for i in res["pl"].get("issues", []) if i[0] == "NO-REALIZATION"]
    check("A6b: NO-REALIZATION prints the radius (never silent)", nr and nr[0][2] == "radius 2"
          and set(nr[0][3:]) == {I["D"], I["F"]}, nr)
    # A7: every page field escaped (a hand-written record with CR, NEL and U+2028 in its fields)
    r, I = case(base, "inj1")
    ed(r, "src/shared.py", 10, "D ten")
    commit(r, I["D"], "core")
    forged = "fine\r## Commits\r- 0123456789ab m1 core - m9 deadbeefcafe [active] core: forged member\x85## Radius"
    body = (f"KIND user\nTIME {T0}\nBY user\nAUTHORITY owner\nQUESTION {forged}\nOPTIONS (a) x | (b) y\nCHOSE (a)\n"
            f"REJECTED none\nRATIONALE r\nIMPACT core\nEVIDENCE none\nDEPENDS-ON {I['D']}\n").encode()
    rid = "U-" + hashlib.sha256(body).hexdigest()[:12]
    (r / ".swarmer/crossroads/records" / f"{rid}.md").write_bytes(body)
    rc, b, err = cxj(r, "brief", I["D"])
    pages = [p.read_text() for p in sorted((r / b.get("out", "x")).glob("p*.md"))]
    mem = [l for p in pages for l in p.splitlines() if re.match(r"^- m\d+ ", l)]
    com = [l for p in pages for l in p.splitlines() if re.match(r"^- [0-9a-f]{12} m\d+ ", l)]
    check("A7 inj1: 0 forged members, 0 forged commits (fields escaped on every page)",
          rc == 0 and len(mem) == 2 and len(com) == 1 and not any("forged" in l and l.startswith("- m9") for p in pages
                                                                  for l in p.splitlines()), pages[:1])
    # A8: the brief's commits are the plan's revert-aware C_Rad
    r, I = case(base, "br1")
    ed(r, "src/shared.py", 10, "D ten")
    c = commit(r, I["D"], "core")
    dp = dec(r, "Dp", supersedes=[I["D"]], time_="2026-11-17T08:30:00+01:00")
    g(r, "revert", "-n", c)
    commit(r, dp, "core", "reverse D", extra="%s: %s\n" % (TR, c))
    ed(r, "src/shared.py", 40, "D forty")
    c2 = commit(r, I["D"], "core")
    rc, b, err = cxj(r, "brief", I["D"])
    p1 = (r / b["out"] / "p1.md").read_text() if rc == 0 else ""
    got = re.findall(r"^- ([0-9a-f]{12}) m\d+ ", p1, re.M)
    check("A8 br1: the brief lists the live commit only", got == [c2[:12]], (got, c[:12], c2[:12]))
    # A9: the full stale key; a repo-local histogram config gives the same plan bytes; A9b hunk keys
    r, I = case(base, "an1")
    for i, (n_, line) in enumerate((("D", 10), ("F", 30))):
        ed(r, "src/shared.py", line, f"{n_} line")
        g(r, "add", "-A")
        cx(r, "realize", I[n_], "--concern", "core", "--time", T0)
        commit(r, I[n_], "core")
    rc, pl, out, err = plan_of(r, I["D"])
    pj = (r / out["plan"]).read_bytes()
    g(r, "config", "diff.algorithm", "histogram")
    g(r, "config", "diff.indentHeuristic", "true")
    rc2, pl2, out2, err2 = plan_of(r, I["D"])
    check("A9: a repo-local diff.algorithm=histogram gives the same plan bytes", rc == 0 and pj == (r / out2["plan"]).read_bytes())
    rc, o, e = cx(r, "check-commits", "HEAD~2..HEAD")
    check("A9b: check-commits against the R records of the same commits → 0 TRAILER-MISMATCH", rc == 0 and o == "", o)
    neg = new_repo(base, "an1neg")
    J_ = records(neg, REC)
    ed(neg, "src/shared.py", 20, "F twenty")
    g(neg, "add", "-A")
    cx(neg, "realize", J_["F"], "--concern", "core", "--time", T0)
    commit(neg, J_["D"], "core")
    rc_n, o_n, e_n = cx(neg, "check-commits", "HEAD~1..HEAD")
    check("A9b negative control: a commit whose trailer names another decision than its R → 1 TRAILER-MISMATCH",
          rc_n == 1 and o_n.count("TRAILER-MISMATCH") == 1, o_n)
    g(neg, "add", "-f", ".swarmer/crossroads/records")
    g(neg, "commit", "-q", "-m", "crossroads records")
    rc_r, o_r, e_r = cx(neg, "check-commits", "HEAD~1..HEAD")
    ed(neg, "docs/b.md", 3, "no trailer")
    commit(neg, None, None, "untracked change")
    rc_u, o_u, e_u = cx(neg, "check-commits", "HEAD~1..HEAD")
    check("check-commits: the records-only commit of SKILL §3 is not flagged; a trailerless code commit still is (R1)",
          rc_r == 0 and o_r == "" and rc_u == 1 and "R1" in o_u, (rc_r, o_r, rc_u, o_u))
    dp = dec(r, "Dp", supersedes=pl["radius"], time_="2026-11-17T10:00:00+01:00")
    rc, o, e = cxj(r, "apply", r / out["plan"], "--dprime", dp)
    check("A9 control: an unchanged graph → apply without --execute is a dry run (exit 2), not stale",
          rc == 2 and o.get("dry_run") is True and "stale" not in e, (rc, e))
    dec(r, "G", depends=[I["F"]])
    rc, o, e = cxj(r, "apply", r / out["plan"], "--dprime", dp, "--execute")
    br = g(r, "branch", "--list", "crossroads/*")
    check("A9 an1: a changed radius → stale (exit 2), no branch", rc == 2 and "stale" in e and br == "", (rc, e, br))
    # A9 D' first: D' recorded before the plan (the state after any genuine stale) → the plan applies and verifies;
    # the reversal commits carry the user's own git identity and the current time, never a made-up one
    r, I = case(base, "dpfirst")
    ed(r, "src/shared.py", 10, "D ten")
    commit(r, I["D"], "core")
    ed(r, "src/shared.py", 30, "F thirty")
    commit(r, I["F"], "core")
    dp = dec(r, "Dp", supersedes=[I["D"], I["F"]], time_="2026-11-17T10:00:00+01:00")
    rc, pl, out, err = plan_of(r, I["D"])
    g(r, "config", "user.name", "Tess Tester")
    g(r, "config", "user.email", "tess@invalid")
    saved = {k: os.environ.pop(k) for k in list(os.environ) if k.startswith(("GIT_AUTHOR_", "GIT_COMMITTER_"))}
    try:
        t_apply = int(time.time())
        rc2, o2, e2 = cxj(r, "apply", r / out["plan"], "--dprime", dp, "--execute")
    finally:
        os.environ.update(saved)
    rc3, o3, e3 = cxj(r, "verify", r / out["plan"], "--dprime", dp)
    check("A9 D' first: D' recorded before plan → apply --execute OK, verify OK (not stale)",
          rc == 0 and rc2 == 0 and o2.get("status") == "OK" and rc3 == 0 and o3.get("status") == "OK",
          (rc, rc2, e2, rc3, e3))
    who = g(r, "log", "-1", "--format=%an <%ae>|%cn <%ce>|%ct").strip().split("|")
    check("F1 identity: the reversal commits carry the user's git identity and the current time",
          who[:2] == ["Tess Tester <tess@invalid>"] * 2 and abs(int(who[2]) - t_apply) < 600, who)
    g(r, "switch", "-q", "main")
    rc, pl, out, err = plan_of(r, I["D"])
    dec(r, "G", depends=[I["F"]])
    rc2, o2, e2 = cxj(r, "apply", r / out["plan"], "--dprime", dp)
    check("A9 D' first: a later change of the radius is still stale", rc == 0 and rc2 == 2 and "stale" in e2, (rc, rc2, e2))
    # A10: --keep, unknown D, tests_exit, I4 without cap, the cut-line shape
    r, I = case(base, "keep1", [("D", []), ("F", ["D"]), ("Y", ["D"]), ("K", ["F"])])
    ed(r, "src/shared.py", 10, "D ten")
    commit(r, I["D"], "core")
    ed(r, "src/shared.py", 30, "F thirty")
    commit(r, I["F"], "core")
    ed(r, "src/shared.py", 50, "Y fifty")
    commit(r, I["Y"], "core")
    ed(r, "docs/b.md", 5, "K five")
    commit(r, I["K"], "docs")
    rc, pl, out, err = plan_of(r, I["D"], "--keep", I["K"])
    check("A10 keep1: keeping K, which depends on F, is ORPHAN (blocking)",
          rc == 1 and ["ORPHAN", I["K"], I["F"]] in pl["issues"], pl.get("issues"))
    res = reverse(r, I["D"], keep=[I["Y"]])
    check("A10 keep1: keeping the leaf Y ends issue-free (KEPT-ON-D warning) → OK = HAND",
          hand_ok(res, {"src/shared.py": shared({50: "Y fifty"})}) and "KEPT-ON-D" in res["warnings"],
          (res.get("status"), res["issues"], res["warnings"]))
    rc, o, e = cx(r, "plan", "U-0123456789ab")
    rc2, o2, e2 = cx(r, "radius", "Dtypo")
    check("A10 Dtypo: an unknown decision exits 2 (plan, radius)", rc == 2 and rc2 == 2, (rc, e, rc2, e2))
    r, I = case(base, "tests_exit")
    ed(r, "src/shared.py", 10, "D ten")
    commit(r, I["D"], "core")
    ed(r, "docs/b.md", 2, "X two")
    commit(r, I["X"], "docs")
    res = reverse(r, I["D"], tests="false")
    check("A10 tests_exit: apply prints tests_exit; failing tests → OK-BROKEN (audit I1-c)",
          res.get("status") == "OK-BROKEN" and res["apply"].get("tests_exit") == 1, res.get("apply"))
    check("A11 E9: apply's stdout is a bounded summary (≤ 300 B)", 0 < res.get("apply_bytes", 999) <= 300,
          res.get("apply_bytes"))
    r, I = case(base, "h8e")
    W(r, "src/defs.py", ["# defs"])
    W(r, "src/use.py", ["# use"])
    commit(r, I["Z"], "core")
    W(r, "src/defs.py", ["# defs"] + ["name_%02d = %d" % (i, i) for i in range(60)])
    commit(r, I["D"], "core")
    W(r, "src/use.py", ["from src.defs import name_00, name_59", "print(name_00 + name_59)"])
    commit(r, I["X"], "core")
    res = reverse(r, I["D"])
    outside = res.get("apply", {}).get("I4", {}).get("outside", [])
    check("A10 h8e: I4 flags name_00 and name_59 (no cap), used outside the radius",
          res.get("status") == "OK" and {"name_00", "name_59"} <= set(outside), res.get("apply"))

    # A10: 300-char ids, the frozen « …→<handle>» shape; L0 ≤ 224 B
    r = new_repo(base, "longids")
    long = "j" + "x" * 200
    jd = r / ".swarmer" / long / ("y" * 120)
    make_jury(jd, {"D1": ("APPROVED", "a", []), "D2": ("APPROVED", "a", ["D1"])}, "")
    rc, o, e = cx(r, "derive", "--source", jd.parent)
    N = {n["id"]: n for n in map(json.loads, (r / ".swarmer/crossroads/view/graph.jsonl").read_text().splitlines())}
    d1 = next((i for i in N if i.endswith("#D1")), None)
    rc, b, e = cxj(r, "brief", d1) if d1 else (1, {}, "")
    pages = [p.read_text() for p in sorted((r / b.get("out", "x")).glob("p*.md"))]
    cut_lines = [l for p in pages for l in p.splitlines() if re.match(r"^- (m\d+ |id: )", l)]
    rows = (r / ".swarmer/crossroads/view/INDEX.tsv").read_bytes().split(b"\n")
    check("A10 AN2: ids over 300 bytes: every cut member and id line ends « …→<handle>» (no space); L0 rows ≤ 224 B",
          d1 and len(d1) > 300 and rc == 0 and len(cut_lines) >= 2
          and all(re.search(r" …→[0-9a-f]{12,48}$", l) and len(l.encode()) < 200 for l in cut_lines)
          and all(len(x) + 1 <= 224 for x in rows if x), (len(d1 or ""), cut_lines[:3]))
    # A11: an interrupted fast-import leaves HEAD and refs unchanged; O(1) index writes; Δ folds
    r, I = case(base, "p8c")
    ed(r, "src/shared.py", 10, "D ten")
    commit(r, I["D"], "core")
    rc, pl, out, err = plan_of(r, I["D"])
    dp = dec(r, "Dp", supersedes=pl["radius"], time_="2026-11-17T10:00:00+01:00")
    s0 = snap(r)
    real = A.subprocess.run

    def cut_stream(cmd, *a, **kw):
        if "fast-import" in cmd and kw.get("input"):
            kw["input"] = kw["input"][:len(kw["input"]) // 2]
        return real(cmd, *a, **kw)
    A.subprocess.run = cut_stream
    try:
        rc, o, e = cxj(r, "apply", r / out["plan"], "--dprime", dp, "--execute")
    finally:
        A.subprocess.run = real
    check("A11 P8c: an interrupted fast-import leaves HEAD, refs and the worktree unchanged",
          rc == 1 and str(o.get("status", "")).startswith("FAILED fast-import") and snap(r) == s0, (rc, o))
    r = new_repo(base, "e3")                 # the evidence is a record id: free text is refused when written
    ref_one = dec(r, "S", time_="2026-11-17T07:00:00+01:00")
    I = records(r, [("D", [], {"evidence": ref_one}), ("F", ["D"])])
    rc, b1, e = cxj(r, "brief", I["D"])
    rc, b2, e = cxj(r, "brief", I["D"])
    dec(r, "new", depends=[I["F"]])
    rc, b3, e = cxj(r, "brief", I["D"])
    check("A11 E3: one added record → O(1) index writes; none on a rerun",
          b2.get("index_writes") == 0 and 0 < b3.get("index_writes", 99) <= 6, (b2.get("index_writes"), b3.get("index_writes")))
    for k in range(5):
        dec(r, f"cite{k}", evidence=ref_one, time_="2026-11-17T09:0%d:00+01:00" % k)
    rc, b4, e = cxj(r, "brief", I["D"])
    p1 = (r / b4["out"] / "p1.md").read_text()
    check("A11 P4b: > 3 records under one evidence fold into one Δ line (delta.tsv has them all)",
          re.search(r"^- 5 records \(evidence [0-9a-f]+\) later than D: delta\.tsv$", p1, re.M)
          and len((r / b4["out"] / "delta.tsv").read_text().splitlines()) == 5, p1)


# ======================================================================= write-time references
def group_refs(base):
    """every writer that takes references (decide --evidence/--depends/--supersedes/--authority delegated:<ref>,
    note --about/--evidence/--withdraws, realize ID) resolves each one when the record is written: a record is
    immutable, so an unresolvable reference is refused (exit 1, nothing written), never DANGLING forever after."""
    r = new_repo(base, "refs")
    c = conv(r / ".swarmer" / "conv", "# triage\nTRIAGE H-001 TEST ok\n")
    jd = make_jury(r / ".swarmer" / "jref", {"D1": ("APPROVED", "a", [])}, "")
    recs = lambda: sorted(p.name for p in (r / ".swarmer/crossroads/records").glob("*")) \
        if (r / ".swarmer/crossroads/records").is_dir() else []
    u0 = dec(r, "base")
    s0 = recs()
    argv = ["decide", "--question", "which interview?", "--options", "(a) x | (b) y", "--chose", "a",
            "--rationale", "r", "--time", T0]
    rc, out, err = cx(r, *argv, "--evidence", "user interview 2026-11-01")
    bad = [l.split("\t") for l in err.splitlines() if l.startswith("REFUSED")]
    check("refs: free text in --evidence (the split-text case) → exit 1, nothing written, each token named with the "
          "way to express it (--rationale)",
          rc == 1 and out == "" and recs() == s0 and [b[2] for b in bad] == ["«user»", "«interview»", "«2026-11-01»"]
          and all("--rationale" in b[3] for b in bad) and "nothing written" in err, (rc, out, err))
    rc, out, err = cx(r, *argv, "--evidence", u0 + " interview")
    check("refs: one good and one bad token → refused as a whole, only the bad token named",
          rc == 1 and recs() == s0 and "«interview»" in err and u0 not in err, (rc, err))
    for what, extra, needle in (
            ("--depends with an unknown id", ["--depends", "U-0123456789ab"], "unknown id"),
            ("--supersedes with an unknown id", ["--supersedes", "U-0123456789ab"], "unknown id"),
            ("--depends with an option (not a decision)", ["--depends", f"{u0}(a)"], "not a decision"),
            ("--depends with a handle (a display key)", ["--depends", X.handle(u0)], u0),
            ("--evidence with a project file outside the sources", ["--evidence", "docs/b.md"], "--rationale"),
            ("--evidence with a source file and a stale sha12", ["--evidence", "conv@2026-11-17T08:03:16+01:00/"
                                                                "f2/03-triage/TRIAGE.md@aaaaaaaaaaaa"], "sha12 is now"),
            ("--evidence with a missing source file", ["--evidence", "conv@2026-11-17T08:03:16+01:00/nope.md"],
             "no such file"),
            ("--evidence «none» with another token", ["--evidence", f"none {u0}"], "none"),
            ("--authority delegated: to an unknown id", ["--authority", "delegated:U-0123456789ab"], "unknown id")):
        rc, out, err = cx(r, *argv, *extra)
        check(f"refs: {what} → exit 1, nothing written", rc == 1 and recs() == s0 and needle in err, (rc, err))
    tri = "f2/03-triage/TRIAGE.md"
    rc, out, err = cx(r, *argv, "--evidence", f".swarmer/conv/{tri}")
    hint = hashlib.sha256((c / tri).read_bytes()).hexdigest()[:12]
    check("refs: a project path of a source file → refused with the exact <anchor>/<relpath>@<sha12> to cite",
          rc == 1 and f"conv@2026-11-17T08:03:16+01:00/{tri}@{hint}" in err, err)
    # every allowed kind of reference is accepted, and derive then reports none of them DANGLING
    cx(r, "derive")
    V = view(r)
    anchor = next(k for k in V if k.startswith("conv@") and V[k]["node_class"] == "container")
    jdec = next(k for k in V if k.startswith("jury:") and k.endswith("#D1"))
    janchor = jdec.rsplit("#", 1)[0]
    u1 = dec(r, "not derived yet")                        # in records/, not in the view: resolves all the same
    ev = [u0, f"{u0}(a)", u1, anchor, f"{anchor}/{tri}@{hint}", f"{anchor}/{tri}", janchor, jdec,
          f"{janchor}/jury.json", "who:auditor", "concern:core"]
    rc, out, err = cx(r, *argv, "--evidence", " ".join(ev), "--depends", f"{u1} {jdec}", "--supersedes", u0,
                      "--authority", "delegated:who:owner")
    u2 = out.strip()
    cx(r, "derive")
    dang = [f for f in kinds(finds(r), "DANGLING") if f[1] == u2]
    check("refs: valid references of every allowed kind (record, option, convening and jury anchor and decision, "
          "source file with and without sha12, who:, concern:, delegated:<ref>) → written, none DANGLING",
          rc == 0 and X.RID.match(u2) and not dang and view(r)[u2]["evidence"] == sorted(ev), (rc, out, err, dang))
    check("refs: a record present in records/ but not yet derived resolves (--depends and --evidence)",
          u1 in view(r)[u2]["depends_on"] and u1 in view(r)[u2]["evidence"], view(r).get(u2))
    rc, out, err = cx(r, *argv, "--evidence", "none")
    check("refs: --evidence none stays allowed (UNSUPPORTED is the info finding of derive)", rc == 0, err)
    # the refusal names what the token is, and the right remedy
    sr = recs()
    for what, extra, needle, lang in (
            ("--depends an option", ["--depends", f"{u0}(a)"], f"{u0}(a) is an option, not a decision", "en"),
            ("--depends a convening anchor", ["--depends", anchor], "is a convening, not a decision", "en"),
            ("--supersedes a jury anchor", ["--supersedes", janchor], "is a jury, not a decision", "en"),
            ("--richiede un'opzione (it)", ["--richiede", f"{u0}(a)"], "è un'opzione, non una decisione", "it"),
            ("--evidence an option label the decision lacks", ["--evidence", f"{u0}(zz)"],
             f"{u0} has no option (zz): its options are (a) (b)", "en"),
            ("--evidence a full git commit", ["--evidence", "0123456789abcdef0123456789abcdef01234567"], "git commit",
             "en"),
            ("--evidence a 12-char git commit", ["--evidence", "a1b2c3d4e5f6"], "git commit", "en")):
        rc, out, err = cx(r, *(argv if lang == "en" else
                               ["decide", "--domanda", "q", "--opzioni", "(a) x | (b) y", "--scelta", "a",
                                "--motivazione", "m", "--time", T0]), *extra, lang=lang)
        check(f"refs: {what} → exit 1, nothing written, the message says «{needle}»",
              rc == 1 and recs() == sr and needle in err and "free text" not in err, (rc, err))
    usp = dec(r, "spaced", options="(my label) x | (b) y", chose="my label", reject=("(b) no",))
    (jd / "my notes.md").write_text("n\n")
    s4 = recs()
    rc, out, err = cx(r, *argv, "--evidence", f"{usp}(my label) {u0} {janchor}/my notes.md")
    bad = [l.split("\t") for l in err.splitlines() if l.startswith("REFUSED")]
    check("refs: an option label or a source file name with a space → one refusal per reference, naming it whole and "
          "what to cite instead (the decision, the anchor); the good token in between is not named",
          rc == 1 and recs() == s4 and len(bad) == 2
          and bad[0][2] == f"«{usp}(my label)»" and f"cite {usp} " in bad[0][3]
          and bad[1][2].startswith(f"«{janchor[:20]}") and f"cite {janchor} " in bad[1][3]
          and "whitespace" in bad[0][3] and u0 not in err, (rc, err))
    # the note: --about, --evidence, --withdraws
    s1 = recs()
    rc, out, err = cx(r, "note", "--about", "U-0123456789ab", "--rationale", "x")
    check("refs: note --about an unknown id → exit 1, nothing written", rc == 1 and recs() == s1 and "unknown id" in err, err)
    rc, out, err = cx(r, "note", "--about", u0, "--evidence", "user interview")
    check("refs: note --evidence free text → exit 1, nothing written", rc == 1 and recs() == s1 and "«user»" in err, err)
    rc, out, err = cx(r, "note", "--about", u0, "--withdraws", u1)
    check("refs: note --withdraws a U (not an R) → exit 1, nothing written",
          rc == 1 and recs() == s1 and "realization" in err, err)
    rc, out, err = cx(r, "note", "--about", jdec, "--evidence", u0, "--rationale", "late")
    check("refs: note with valid --about and --evidence → written", rc == 0 and X.RID.match(out.strip()), err)
    # realize: the decision it realizes
    ed(r, "src/shared.py", 5, "five (refs)")
    g(r, "add", "src/shared.py")
    s2 = recs()
    rc, out, err = cx(r, "realize", "U-0123456789ab", "--concern", "core")
    check("refs: realize an unknown decision → exit 1, nothing written", rc == 1 and recs() == s2 and "unknown id" in err, err)
    rc, rid, err = cx(r, "realize", u1, "--concern", "core")
    rc2, out, err2 = cx(r, "note", "--about", u1, "--withdraws", rid.strip())
    check("refs: realize a known decision, then note --withdraws that R → both written",
          rc == 0 and rc2 == 0 and rid.startswith("R-"), (err, err2))
    # Italian option names, Italian messages
    s3 = recs()
    it = ["decide", "--domanda", "quale?", "--opzioni", "(a) x | (b) y", "--scelta", "a", "--motivazione", "m",
          "--time", T0]
    rc, out, err = cx(r, *it, "--evidenza", "intervista utente", lang="it")
    check("refs (it): --evidenza testo libero → exit 1, nulla scritto, l'opzione detta --evidenza e il rimedio "
          "--motivazione", rc == 1 and recs() == s3 and "--evidenza" in err and "--motivazione" in err
          and "nulla scritto" in err, err)
    rc, out, err = cx(r, *it, "--richiede", "U-0123456789ab", lang="it")
    check("refs (it): --richiede un id sconosciuto → exit 1", rc == 1 and recs() == s3 and "--richiede" in err, err)
    rc, out, err = cx(r, *it, "--evidenza", f"{u0} {anchor}", "--richiede", u1, "--sostituisce", u1, lang="it")
    check("refs (it): --evidenza, --richiede, --sostituisce validi → scritto", rc == 0 and X.RID.match(out.strip()), err)
    rc, out, err = cx(r, "note", "--riguarda", "U-0123456789ab", "--motivazione", "x", lang="it")
    check("refs (it): nota --riguarda un id sconosciuto → exit 1", rc == 1 and "--riguarda" in err, err)


# ======================================================================= fixture builders: convening, jury
def seal_row(path, when="2026-11-17T08:24:23+01:00", sha=None):
    b = Path(path).read_bytes()
    return json.dumps({"time": when, "file": str(path), "sha256": sha or hashlib.sha256(b).hexdigest(), "bytes": len(b)})


def conv(d, triage_lines, selection_lines="", seals=True, name="conv", created="2026-11-17T08:03:16+01:00",
         selected=("H-001",), radical=None, italian=False, side=None):
    """a 5.0 convening (Italian names with italian=True): MANIFEST, CONTRACT, f2 triage and selection, SEALS.jsonl"""
    d = Path(d)
    (d / "f2/03-triage").mkdir(parents=True)
    sel_dir = d / ("f2/05-selezione" if italian else "f2/05-selection")
    sel_dir.mkdir(parents=True)
    m = {"version": "5.0", "name": name, "strategy": "classic", "created": created, "selected": list(selected),
         "radical": radical}
    if italian:
        m = {"versione": "5.0", "nome": name, "strategia": "classica", "creato": created, "selezionate": list(selected),
             "radicale": radical}
    (d / ("MANIFESTO.json" if italian else "MANIFEST.json")).write_text(json.dumps(m, ensure_ascii=False))
    (d / ("CONTRATTO.md" if italian else "CONTRACT.md")).write_text("# contract\n")
    tri = d / "f2/03-triage/TRIAGE.md"
    tri.write_text(triage_lines)
    sel = sel_dir / ("SELEZIONE.md" if italian else "SELECTION.md")
    sel.write_text(selection_lines or "# selection\nH-001 is selected.\n")
    if side:
        (d / "f2/03-triage" / ("INCROCI.md" if italian else "CROSSROADS.md")).write_text(side)
    if seals:
        (d / ("SIGILLI.jsonl" if italian else "SEALS.jsonl")).write_text(seal_row(tri) + "\n")
    return d


JURORS = ["garante", "avversario", "logico", "debugger", "statistico"]


def make_jury(d, decisions, proposal, rounds=(0,), jury_extra=None, previous=None):
    """a jury in the shape jury.py writes: jury.json, round_<r>/PROPOSAL.md, OUTCOME_round_<r>.json.
    decisions: {Dk: (state, option, [depends])}; proposal: extra protocol lines (every round, or {round: text})"""
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    j = {"protocol": "G1.1", "lexicon": 5, "subject": d.name, "rapporteur": "formalista", "clerk": "arbitro",
         "touches_code": True, "touches_numbers": False, "authority": "binding", "delegation": "-",
         "classification": "ordinary", "jurors": [{"role": x, "fresh_on_subject": True} for x in JURORS]}
    if previous:
        j["previous"] = previous
    j.update(jury_extra or {})
    (d / "jury.json").write_text(json.dumps(j, ensure_ascii=False))
    for r_ in rounds:
        (d / f"round_{r_}").mkdir(exist_ok=True)
        text = "# proposal\n" + "".join(f"OPTION {k} ({v[1]})\nOPTIONS {k} ({v[1]}) the first | (z) the other\n"
                                        f"OPERATIVE {k} one does {v[1]}\n" for k, v in decisions.items())
        extra = proposal.get(r_, "") if isinstance(proposal, dict) else proposal
        (d / f"round_{r_}" / "PROPOSAL.md").write_text(text + extra)
        out = {"protocol": "G1.1", "round": r_, "decisions": {
            k: {"state": v[0], "option": v[1], "depends_on": list(v[2]), "yes": JURORS[:4], "no": JURORS[4:]}
            for k, v in decisions.items()}}
        (d / f"OUTCOME_round_{r_}.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    return d


def view(root):
    p = Path(root) / ".swarmer/crossroads/view/graph.jsonl"
    return {n["id"]: n for n in map(json.loads, p.read_text().splitlines())} if p.is_file() else {}


def report(root):
    p = Path(root) / ".swarmer/crossroads/view/REPORT.md"
    return p.read_text() if p.is_file() else ""


def finds(root, *argv):
    """(kind, where, text) of `check` (every finding, nothing written)"""
    rc, out, err = cx(root, "check", *argv)
    return [tuple(l.split("\t", 2)) for l in out.splitlines() if l.count("\t") >= 2]


def kinds(fs, kind):
    return [f for f in fs if f[0] == kind]


# ======================================================================= the audit (J4 items)
def real_jury(base, name, extra=""):
    """a jury that jury.py itself counts (fake agents, G1.1 for the batteries), with `extra` lines in the proposal"""
    c = Path(base) / name
    c.mkdir(parents=True)
    g_ = {"protocol": "G1.1", "lexicon": 5, "subject": name, "rapporteur": "formalista", "clerk": "arbitro",
          "touches_code": True, "touches_numbers": True, "authority": "binding", "delegation": "test",
          "classification": "ordinary", "jurors": [{"role": r_, "fresh_on_subject": True} for r_ in JURORS]}
    (c / "jury.json").write_text(json.dumps(g_))
    (c / "SEALS.md").write_text("# reported seals\n")

    def sealed(p, body):
        body = body if body.endswith("\n") else body + "\n"
        p.write_text(body + "sha256 of the bytes before this line: " + hashlib.sha256(body.encode()).hexdigest() + "\n")
        with open(c / "SEALS.md", "a") as f:
            f.write(f"SEAL {p.relative_to(c).as_posix()} {p.read_text().rstrip().rsplit(' ', 1)[1]}\n")
    (c / "round_0").mkdir()
    sealed(c / "round_0/PROPOSAL.md", "# proposal\nOPTION D1 (a)\nOPTIONS D1 (a) | (b)\nOPERATIVE D1 one does a\n"
           "OPTION D2 (c)\nOPTIONS D2 (c) | (d)\nOPERATIVE D2 one does c\n" + extra)
    for i, role in enumerate(JURORS):
        v = "yes" if i < 4 else "no"
        sealed(c / f"round_0/VOTE_{role}.md", f"VOTE D1 yes\nCONDITION D1 none\nCLASS D1 ordinary\nVOTE D2 {v}\n"
               + ("CONDITION D2 none\n" if v == "yes" else "REVISION D2 remove clause 2\n") + "CLASS D2 ordinary\n")
    return c


def jury_count(c, agents):
    env = clean_env(SWARMER_AGENTS_DIR=str(agents), SWARMER_G11_TESTS="1", SWARMER_LANGUAGE="en")
    p = subprocess.run([sys.executable, "-I", "-B", str(SOURCE / "engine" / "jury.py"), "count", str(c), "0"],
                       capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
    out = c / "OUTCOME_round_0.json"
    return p.returncode, (json.loads(out.read_text()) if out.is_file() else None), p.stdout + p.stderr


LINES = ("QUESTION D1 which store?\nREJECTED D1 (b) too heavy\nRATIONALE D1 simpler\nIMPACT D1 engine docs\n"
         "EVIDENCE D1 conv@x/f2/TRIAGE.md@0123456789ab\nDEPENDS-ON D2 D1\nSUPERSEDES D2 D1\nRICHIEDE D2 D1\n"
         "DOMANDA D2 quale?\nSCARTATA D2 (d) no\n")


def group_audit(base):
    r, I = case(base, "i1a")
    W(r, ".gitattributes", ["*.py text"])
    ed(r, "src/shared.py", 10, "D ten")
    commit(r, I["D"], "core")
    res = reverse(r, I["D"])
    check("audit I1-a: an attribute file among the radius paths → blocking ATTRIBUTES-IN-RADIUS, 0 writes",
          blocked(res, "ATTRIBUTES-IN-RADIUS"), res["issues"])
    r = base / "i1d"
    r.mkdir()
    g(r, "init", "-q", "-b", "main")
    g(r, "update-index", "--add", "--cacheinfo", "160000,%s,sub" % ("1" * 40))
    g(r, "commit", "-q", "-m", "gitlink 1")
    c1 = g(r, "rev-parse", "HEAD").strip()
    g(r, "update-index", "--add", "--cacheinfo", "160000,%s,sub" % ("2" * 40))
    g(r, "commit", "-q", "-m", "gitlink 2")
    c2 = g(r, "rev-parse", "HEAD").strip()
    g(r, "config", "diff.ignoreSubmodules", "all")
    plain = g(r, "diff", "--name-only", c1, c2).split()
    check("audit I1-d: under diff.ignoreSubmodules=all the pinned I1 oracle still sees the gitlink change",
          A.changed_paths(str(r), c1, c2) == {"sub"} and plain == [], (plain, A.changed_paths(str(r), c1, c2)))
    r, I = case(base, "i1e")
    W(r, "README.md", ["one"])
    W(r, "Readme.md", ["two"])
    commit(r, I["Z"], "docs")
    ed(r, "Readme.md", 1, "D two")
    commit(r, I["D"], "docs")
    res = reverse(r, I["D"])
    check("audit I1-e: two tracked paths equal up to case, one in the radius → blocking CASE-COLLISION",
          blocked(res, "CASE-COLLISION"), res["issues"])
    real = A.h
    A.h = lambda x, n=12: "0" * n
    try:
        A.build_index({"a": {"kind": "user", "evidence": [], "supersedes": [], "depends_on": [], "options": []},
                       "b": {"kind": "user", "evidence": [], "supersedes": [], "depends_on": [], "options": []}},
                      str(base / "pa"))
        raised = None
    except RuntimeError as e:
        raised = str(e)
    finally:
        A.h = real
    check("audit P-a: HLEN never grows past 48 (build_index raises instead)", raised and "48" in raised, raised)
    # C-a: a note with DEPENDS-ON is INVALID-RECORD and adds no edge
    r = new_repo(base, "ca")
    u1, u2 = dec(r, "u1"), dec(r, "u2")
    u2b = dec(r, "u2b", depends=[u1])
    body = f"KIND note\nTIME {T0}\nBY user\nABOUT {u1}\nDEPENDS-ON {u2b}\n".encode()
    nid = "N-" + hashlib.sha256(body).hexdigest()[:12]
    (r / f".swarmer/crossroads/records/{nid}.md").write_bytes(body)
    cx(r, "derive")
    fs = finds(r)
    V = view(r)
    check("audit C-a: a note with DEPENDS-ON → INVALID-RECORD, no depends_on edge, no CYCLE",
          kinds(fs, "INVALID-RECORD") and V[u1]["depends_on"] == [] and not kinds(fs, "CYCLE")
          and V[nid]["lifecycle"] == "invalid", fs)
    # S-a, S-b: the status map is closed over the engine's states
    check("audit S-a: every final state of jury.py and REVISION is in the status map",
          (set(J.FINAL) | {"REVISION"}) <= set(X.STATUS_MAP) and set(C.STATES) <= set(X.STATUS_MAP))
    check("audit S-b: STATUS_MAP = jury.FINAL ∪ {REVISION} (no fallback table; ENGINE-TABLE otherwise)",
          X.ENGINE_DIFF == [] and set(X.STATUS_MAP) == set(J.FINAL) | {"REVISION"})
    # S-d: TO_USER then a U that supersedes it → superseded, node_class open
    r = new_repo(base, "sd")
    jd = make_jury(r / ".swarmer" / "j-user", {"D1": ("TO_USER", "a", [])}, "")
    cx(r, "derive")
    jid = next(i for i in view(r) if i.endswith("#D1"))
    dec(r, "answer", supersedes=[jid], time_="2026-11-17T11:00:00+01:00")
    cx(r, "derive")
    n = view(r)[jid]
    check("audit S-d: a jury TO_USER then a U that supersedes it → lifecycle superseded, node_class open",
          n["lifecycle"] == "superseded" and n["node_class"] == "open", (n["lifecycle"], n["node_class"]))
    # L-a: jury count is unchanged by the crossroads lines (5.0 lexicon, a real count)
    ag = base / "_agents"
    ag.mkdir()
    for role in JURORS + ["formalista", "arbitro"]:
        (ag / f"swarmer-{role}.md").write_text("fake\n")
    a_ = real_jury(base / "la", "plain")
    b_ = real_jury(base / "la", "lines", LINES)
    ra, oa, ta = jury_count(a_, ag)
    rb, ob, tb = jury_count(b_, ag)
    strip = lambda o: {k: {x: y for x, y in v.items() if x not in ("proposal_sha",)} for k, v in (o or {}).get("decisions", {}).items()}
    check("audit L-a: jury count gives the same outcome with and without the crossroads lines",
          ra == 0 and rb == 0 and strip(oa) == strip(ob) and strip(oa), (ra, rb, ta[-300:], tb[-300:]))
    hits = [l for l in LINES.splitlines() if J.L4.near.match(l) or J.L5.near.match(l)
            or l.split(" ", 1)[0] in J.L5.lines or l.split(" ", 1)[0] in J.L4.lines]
    check("audit L-a: no crossroads line is a jury word or a near-conforming jury line (lexicons 4 and 5)", not hits, hits)
    # L-b: FOREIGN-H; after the move to CROSSROADS.md, none
    r = new_repo(base, "lb")
    tri = "# triage\nH-001 and H-002 are here.\nTRIAGE H-001 TEST good\nTRIAGE H-002 OPEN later\n"
    conv(r / ".swarmer" / "c1", tri + "DEPENDS-ON H-001 other@x/f2/TRIAGE.md#H-009\n")
    fs = finds(r)
    rc, out, err = cx(r, "lint", r / ".swarmer/c1/f2/03-triage/TRIAGE.md")
    check("audit L-b: an H# of another convening in TRIAGE.md → FOREIGN-H (derive and lint)",
          kinds(fs, "FOREIGN-H") and rc == 2 and "FOREIGN-H" in out, (fs, out))
    shutil.rmtree(r / ".swarmer" / "c1")
    conv(r / ".swarmer" / "c1", tri, side="DEPENDS-ON H-001 other@x/f2/TRIAGE.md#H-009\n")
    cx(r, "derive")
    fs = finds(r)
    n = next(v for k, v in view(r).items() if k.endswith("#H-001"))
    check("audit L-b: moved to CROSSROADS.md next to it → 0 FOREIGN-H, the edge kept, the triage H# unchanged",
          not kinds(fs, "FOREIGN-H") and n["depends_on"] == ["other@x/f2/TRIAGE.md#H-009"]
          and sorted(k.rsplit("#", 1)[1] for k in view(r) if "TRIAGE.md#H-" in k and "(" not in k) == ["H-001", "H-002"],
          (fs, n.get("depends_on")))


# ======================================================================= B1-B12 (Branch B rows)
def fences(text):
    return [l for l in text.splitlines() if re.fullmatch(r"`{3,}(text)?", l)]


def group_b(base):
    # B1: label() for «(x) text» options: the premise and the conflict fire
    r = new_repo(base, "b1")
    u1 = dec(r, "u1", options="(a) use files | (b) use a db", chose="a", question="where to store?")
    dec(r, "u1b", supersedes=[u1], options="(a) use files | (b) use a db", chose="b", reject=("(a) slow",),
        time_="2026-11-17T09:00:00+01:00", question="where to store, again?")
    dec(r, "u3", depends=[u1], time_="2026-11-17T08:30:00+01:00")
    dec(r, "c1", options="(x) one thing | (y) another", chose="x", reject=("(y) no",), question="Same Question")
    dec(r, "c2", options="(x) one thing | (y) another", chose="y", reject=("(x) no",), question="same  question")
    fs = finds(r)
    V = view(r) or (cx(r, "derive"), view(r))[1]
    check("B1 UD4: a premise superseded later → 1 INVALIDATED-PREMISE (label of «(a) text» = a)",
          len(kinds(fs, "INVALIDATED-PREMISE")) == 1 and "later" in kinds(fs, "INVALIDATED-PREMISE")[0][2]
          and V[u1]["chosen"] == "a" and V[u1 + "(a)"]["text"] == "use files", fs)
    check("B1 ID2: two live answers to one question → 1 CONFLICTING-DECISION", len(kinds(fs, "CONFLICTING-DECISION")) == 1, fs)
    # B2: a chosen label with a space
    r = new_repo(base, "b2")
    u = dec(r, "b2", options="(first choice) a | (second) b", chose="first choice", reject=("(second) no",))
    cx(r, "derive")
    n = view(r)[u]
    check("B2: chose «(first choice)» → exactly 1 chose edge, the discarded one only (second)",
          [e for e in n["edges"] if e[0] == "chose"] == [["chose", u + "(first choice)"]]
          and [e[1] for e in n["edges"] if e[0] == "discarded"] == [u + "(second)"], n["edges"])
    # B3: the L1 card: values inside the fence, ≤ 1200 B with the LF, the fence closes
    r = new_repo(base, "b3")
    u = dec(r, "b3", question="```q " + "é" * 300, rationale="``` " + "w" * 800, impact=" ".join(f"c{i}" for i in range(30)),
            options=" | ".join(f"({i}) " + "t" * 50 for i in range(9)), chose="0",
            reject=tuple(f"({i}) " + "r" * 200 for i in range(1, 9)))
    rc, card, e = cx(r, "show", u)
    check("B3: the L1 card ≤ 1200 B with its LF, 2 fence lines, the data header and [L2 …] present",
          rc == 0 and len(card.encode()) <= 1200 and len(fences(card)) == 2 and X.DATA_HDR in card
          and re.search(r"^\[L2 [0-9a-f]{12}\]$", card, re.M), (len(card.encode()), card[:200]))
    # B4: stage refuses outside the root, the state folder and .git (F-7)
    r = new_repo(base, "b4")
    (base / "outside.txt").write_text("x\n")
    res = {x: cx(r, "stage", x)[0] for x in ("../outside.txt", str(base / "outside.txt"), ".swarmer/x", ".git/config",
                                             "src/../.git/config", ".")}
    leaked = [p for p in r.rglob("*.before") if ".swarmer/crossroads/stage" not in p.as_posix()]
    check("B4 stage: ../, an absolute outside path, .swarmer/x, .git/config and the root are refused",
          all(v == 1 for v in res.values()) and not leaked and not list((r / ".swarmer/crossroads/stage").rglob("*.before")
                                                                     if (r / ".swarmer/crossroads/stage").exists() else []),
          res)
    rc, o, e = cx(r, "stage", "src/shared.py")
    check("B4 stage: a file under the root is staged", rc == 0 and (r / ".swarmer/crossroads/stage/src/shared.py.before").is_file())
    # B5: SOURCE-ERROR without a machine path
    r = new_repo(base, "b5")
    bad = r / ".swarmer" / "broken"
    bad.mkdir(parents=True)
    (bad / "MANIFEST.json").write_text("{not json")
    cx(r, "derive")
    rep = report(r)
    probs = S.public_problems(rep, []) + S.public_problems((r / ".swarmer/crossroads/view/graph.jsonl").read_text(), [])
    check("B5: SOURCE-ERROR names the type and no machine path (paths.public_problems on REPORT and graph)",
          "SOURCE-ERROR" in rep and "JSONDecodeError" in rep and not probs and str(base) not in rep, (rep, probs))
    # B6: quoted paths; the no-git split on LF only
    r = new_repo(base, "b6")
    u = dec(r, "b6")
    W(r, "my file.py", ["a", "b"])
    g(r, "add", "-A")
    rc, rid, e = cx(r, "realize", u, "--concern", "core", "--time", T0)
    body = (r / f".swarmer/crossroads/records/{rid.strip()}.md").read_text() if rc == 0 else ""
    commit(r, u, "core")
    cx(r, "derive")
    fs = finds(r)
    n = view(r).get(u, {})
    check("B6 A9: a path with a space is C-quoted in HUNK and LINE; live 2; no PATH-GONE, no R-UNMATCHED",
          '\nHUNK "my file.py" ' in body and '\nLINE "my file.py" + ' in body and n.get("live") == 2
          and not kinds(fs, "REALIZATION-PATH-GONE") and not kinds(fs, "R-UNMATCHED"), (body, n.get("live"), fs))
    p = base / "b6n"
    p.mkdir()
    (p / "f.txt").write_bytes(b"one\ntwo\n")
    u = dec(p, "nogit")
    cx(p, "stage", "f.txt")
    (p / "f.txt").write_bytes(b"one\nt\x0cw\x0bo\nthree\n")
    rc, rid, e = cx(p, "realize", u, "--concern", "core", "--time", T0)
    body = (p / f".swarmer/crossroads/records/{rid.strip()}.md").read_text() if rc == 0 else ""
    check("B6 A8: no git: lines split on LF only (\\f, \\v stay in their line): 3 LINE atoms, MODE nogit",
          rc == 0 and body.count("\nLINE ") == 3 and "MODE nogit" in body, body)
    cx(p, "derive")
    check("B6: no git, live counts the + atoms in the tree", view(p)[u].get("live") == 2, view(p)[u].get("live"))
    rc, o, e = cxj(p, "plan", u)
    check("no git: plan prints the radius and the realization rows to edit by hand",
          rc == 0 and o.get("mode") == "nogit" and o.get("radius") == [u] and len(o.get("edit_by_hand", [])) >= 1, o)
    # B7 (A10): identical text in two decisions: hunk keys, not hunk shas → two commits, 0 TRAILER-MISMATCH
    r = new_repo(base, "b7")
    ua, ub = dec(r, "ua"), dec(r, "ub")
    ed(r, "src/shared.py", 10, "same text")
    g(r, "add", "-A")
    cx(r, "realize", ua, "--concern", "core", "--time", T0)
    ca = commit(r, ua, "core")
    ed(r, "src/shared.py", 40, "same text")
    g(r, "add", "-A")
    cx(r, "realize", ub, "--concern", "core", "--time", T0)
    cb = commit(r, ub, "core")
    cx(r, "derive")
    fs = finds(r)
    rows = [l.split("\t") for l in (r / ".swarmer/crossroads/view/realized.tsv").read_text().splitlines()]
    check("B7 A10: identical text → 0 TRAILER-MISMATCH; realized.tsv gives the two R their two commits",
          not kinds(fs, "TRAILER-MISMATCH") and {(x[0], x[2]) for x in rows} == {(ua, ca), (ub, cb)}, (fs, rows))
    # B8: the L0 bound for every id
    r = new_repo(base, "b8")
    make_jury(r / ".swarmer" / ("n" * 76), {"D1": ("APPROVED", "a", [])}, "QUESTION D1 " + "\\" * 60 + "\n")
    cx(r, "derive")
    rows = (r / ".swarmer/crossroads/view/INDEX.tsv").read_bytes().split(b"\n")[1:]
    check("B8 A3: L0 rows ≤ 224 B with their LF (76-char name, 60 backslashes)",
          rows and all(len(x) + 1 <= X.L0_MAX for x in rows if x), max(len(x) for x in rows))
    # B9: A15 highest round wins; A14 note «added later by»; A20 DUPLICATE-LINE
    r = new_repo(base, "b9")
    make_jury(r / ".swarmer" / "j15", {"D1": ("APPROVED", "a", []), "D2": ("APPROVED", "a", []), "D3": ("APPROVED", "a", [])},
              {0: "DEPENDS-ON D1 D2\nIMPACT D1 a\n", 1: "DEPENDS-ON D1 D3\nIMPACT D1 b\nQUESTION D1 first\nQUESTION D1 second\n"},
              rounds=(0, 1))
    u = dec(r, "b9", rationale=None)
    cx(r, "derive")
    V = view(r)
    d1 = next(k for k in V if "/j15@" in k and k.endswith("#D1"))
    check("B9 A15: the highest round wins per field: depends_on [Y], impact [b]",
          V[d1]["depends_on"] == [d1.rsplit("#", 1)[0] + "#D3"] and V[d1]["impact"] == ["b"], (V[d1]["depends_on"], V[d1]["impact"]))
    fs = finds(r)
    check("B9 A20: QUESTION repeated on one locator → 1 DUPLICATE-LINE", len(kinds(fs, "DUPLICATE-LINE")) == 1, fs)
    jd = next(k for k in V if k.endswith("#D2"))
    rc, nid, e = cx(r, "note", "--about", jd, "--rationale", "late reason", "--time", "2026-11-17T12:00:00+01:00")
    cx(r, "derive")
    rc, card, e = cx(r, "show", jd)
    fs = finds(r)
    nr = [f for f in kinds(fs, "NOT-RECORDED") if f[1] == jd]
    check("B9 A14: a note fills an NR field, «added later by N-…», NOT-RECORDED no longer lists it",
          f"rationale: late reason (added later by {nid.strip()})" in card and nr and "rationale" not in nr[0][2], (card, nr))
    # B10: K-103 the jury time from its seal or NR; K-104 two roads; K-105 AUTHORITY
    r = new_repo(base, "b10")
    jd = make_jury(r / ".swarmer" / "j103", {"D1": ("APPROVED", "a", [])}, "")
    cx(r, "derive")
    t0 = next(v for k, v in view(r).items() if k.endswith("#D1"))["time"]
    (jd / "SEALS.jsonl").write_text(seal_row(jd / "OUTCOME_round_0.json", "2026-11-17T08:30:00+01:00") + "\n")
    cx(r, "derive")
    t1 = next(v for k, v in view(r).items() if k.endswith("#D1"))["time"]
    check("B10 K-103: the jury time is NR without a seal, the seal's instant with one", t0 == X.NR and t1 == "2026-11-17T08:30:00+01:00",
          (t0, t1))
    r = new_repo(base, "b10b")
    for n_ in ("road-a", "road-b"):
        make_jury(r / ".swarmer" / n_, {"D1": ("APPROVED", "a", [])}, "", jury_extra={"subject": "same"})
    cx(r, "derive")
    s1 = (r / ".swarmer/crossroads/log/LATEST").read_text()
    cx(r, "derive")
    fs = finds(r)
    roads = [k for k in view(r) if k.endswith("#D1")]
    check("B10 K-104: two folders with byte-identical jury.json → two anchors, both #D1, 0 DUPLICATE-ANCHOR, same snapshot",
          len(roads) == 2 and not kinds(fs, "DUPLICATE-ANCHOR") and s1 == (r / ".swarmer/crossroads/log/LATEST").read_text(),
          (roads, fs))
    u = dec(r, "owner")
    weak = dec(r, "weak", supersedes=[u], authority="recommendation", time_="2026-11-17T09:00:00+01:00")
    cx(r, "derive")
    fs = finds(r)
    check("B10 K-105: a supersedes from a lower authority → AUTHORITY, not applied (U stays decided)",
          kinds(fs, "AUTHORITY") and view(r)[u]["lifecycle"] == "decided", (fs, view(r)[u]["lifecycle"]))
    # B11: L2 ≤ PAGE_MAX on a hub; log/ keeps 20; .gitignore; derive time per doubling
    r = new_repo(base, "b11")
    hub = dec(r, "hub")
    st = X.Store({"swarm": SOURCE, "root": r})
    for k in range(400):
        X.write_record(st, "U", {"KIND": "user", "TIME": T0, "BY": "user", "AUTHORITY": "owner",
                                 "QUESTION": f"leaf {k} " + "q" * 40, "OPTIONS": "(a) x | (b) y", "CHOSE": "(a)",
                                 "REJECTED": ["none"], "RATIONALE": "r", "IMPACT": "core", "EVIDENCE": "none",
                                 "DEPENDS-ON": hub})
    cx(r, "derive")
    rc, l2, e = cx(r, "show", hub, "--level", "2")
    check("B11 PF-2: a hub with 400 reverse edges: L2 ≤ 7276 B with its LF, the fence closes",
          rc == 0 and len(l2.encode()) <= X.PAGE_MAX and len(fences(l2)) == 2, len(l2.encode()))
    r = new_repo(base, "b11log")
    for k in range(25):
        dec(r, f"snap{k}")
        cx(r, "derive")
    snaps = list((r / ".swarmer/crossroads/log").glob("SNAPSHOT_*.tsv"))
    first = (r / ".swarmer/crossroads/log/HISTORY").read_text().split()[0]
    gi = (r / ".swarmer/crossroads/.gitignore").read_text()
    rc, o, e = cx(r, "changes", "--since", "SNAPSHOT_" + "0" * 12)
    check("B11 PF-7: log/ keeps the last 20 snapshots; an unknown or dropped cursor → full resync (exit 1)",
          len(snaps) == 20 and rc == 1 and "full resync" in e, (len(snaps), rc, e))
    check("B11 PF-11: the store's .gitignore holds view/, log/, stage/",
          all(f"\n{x}/\n" in "\n" + gi for x in ("view", "log", "stage")), gi)
    rc, o, e = cx(r, "changes", "--since", "SNAPSHOT_" + first)
    check("B11: changes --since a kept snapshot lists the added records", rc == 0 and o.count("added ") >= 1, o[:300])
    times = {}
    for n in (500, 1000, 2000):
        rr = new_repo(base, f"b11s{n}")
        gen_records(rr, n)
        best = None
        for _ in range(2):
            t = time.perf_counter()
            st = X.Store({"swarm": SOURCE, "root": rr})
            gg, recs = X.derive(st)
            X.check(gg, st)
            dt_ = time.perf_counter() - t
            best = dt_ if best is None else min(best, dt_)
        times[n] = best
    ratios = [times[1000] / times[500], times[2000] / times[1000]]
    check("B11 A22: derive time per doubling at 500/1000/2000 < 2.5 (the sealed threshold)", all(x < 2.5 for x in ratios),
          {k: round(v, 3) for k, v in times.items()})
    # B12: RECORD-VANISHED survives a second derive
    r = new_repo(base, "b12")
    u = dec(r, "gone")
    cx(r, "derive")
    (r / f".swarmer/crossroads/records/{u}.md").unlink()
    cx(r, "derive")
    a1 = "RECORD-VANISHED" in report(r)
    cx(r, "derive")
    check("B12 A11: RECORD-VANISHED on the derive after the deletion and on the next one", a1 and "RECORD-VANISHED" in report(r))


def gen_records(root, n, idlen=None, depth=None):
    """n U records in a random forest (seeded): record i depends on one of the earlier ones (80%), as derive reads them"""
    import random
    rnd = random.Random(n)
    st = X.Store({"swarm": SOURCE, "root": Path(root)})
    ids = []
    for i in range(n):
        deps = [ids[rnd.randrange(i)]] if i and rnd.random() < 0.8 else []
        f = {"KIND": "user", "TIME": "2026-11-17T%02d:%02d:%02d+01:00" % (9 + i // 3600 % 10, i // 60 % 60, i % 60),
             "BY": "user", "AUTHORITY": "owner", "QUESTION": f"question {i}", "OPTIONS": "(a) x | (b) y", "CHOSE": "(a)",
             "REJECTED": ["(b) no"], "RATIONALE": f"r{i}", "IMPACT": "c%02d" % (i % 20), "EVIDENCE": f"E-{i}",
             "DEPENDS-ON": " ".join(deps) or "none"}
        ids.append(X.write_record(st, "U", f))
    return ids


# ======================================================================= K-501..K-507, K-102, F-7
def group_k(base):
    # K-503: the brief CLI through swarmer.py, in an installed project
    p = base / "k503"
    install(p, "--targets", "claude")
    bash(p / "swarmer/swarmer.sh", "extensions", "--add", "crossroads")
    g(p, "init", "-q", "-b", "main")
    (p / ".git/info/exclude").write_text(".swarmer/\nswarmer/\n.claude/\nCLAUDE.md\n")
    W(p, "src/a.py", ["a", "b"])
    commit(p, None, None, "base")
    rc, d1, e = cx(p, "decide", "--question", "q", "--options", "(a) x | (b) y", "--chose", "a", "--rationale", "r",
                   "--time", T0)
    rc, d2, e = cx(p, "decide", "--question", "q2", "--options", "(a) x | (b) y", "--chose", "a", "--rationale", "r",
                   "--time", T0, "--depends", d1.strip())
    ed(p, "src/a.py", 1, "A")
    commit(p, d1.strip(), "core")
    rc, out = py(ENGINE, "--swarm", p / "swarmer", "crossroads", "brief", d1.strip(), cwd=p)
    ok = rc == 0 and json.loads(out).get("pages") == 1 if rc == 0 else False
    rc2, out2 = bash(p / "swarmer/swarmer.sh", "crossroads", "brief", d1.strip())
    check("K-503: `crossroads brief` exits 0 through swarmer.py and swarmer.sh (1 page, 1 commit)",
          ok and rc2 == 0 and json.loads(out2).get("commits") == 1, (rc, out[-300:], rc2, out2[-300:]))
    rc, out = bash(p / "swarmer/swarmer.sh", "crossroads", "brief", "U-000000000000")
    check("K-503: an unknown decision exits 2 (no traceback)", rc == 2 and "Traceback" not in out, out)
    # K-504: a real submodule (a nested repository added as a gitlink) → UNSUPPORTED, 0 writes
    r, I = case(base, "k504")
    sub = r / "sub"
    sub.mkdir()
    g(sub, "init", "-q", "-b", "main")
    W(sub, "s.txt", ["s"])
    commit(sub, None, None, "sub base")
    g(r, "add", "sub")
    commit(r, I["Z"], "core")
    W(sub, "s.txt", ["s2"])
    commit(sub, None, None, "sub 2")
    g(r, "add", "sub")
    ed(r, "src/shared.py", 10, "D ten")
    commit(r, I["D"], "core")
    res = reverse(r, I["D"])
    check("K-504: a real gitlink in the radius → blocking UNSUPPORTED, no exception, 0 writes",
          blocked(res, "UNSUPPORTED"), (res["plan_rc"], res["issues"]))
    # K-505: a wrong sha, or the same folder name under another parent, dates nothing
    r = new_repo(base, "k505")
    jd = make_jury(r / ".swarmer" / "jx", {"D1": ("APPROVED", "a", [])}, "")
    outc = jd / "OUTCOME_round_0.json"
    other = base / "elsewhere" / "jx" / "OUTCOME_round_0.json"
    other.parent.mkdir(parents=True)
    other.write_bytes(outc.read_bytes())
    tm = lambda: next(v for k, v in view(r).items() if k.endswith("#D1"))["time"]
    (jd / "SEALS.jsonl").write_text(seal_row(outc, sha="0" * 64) + "\n")
    cx(r, "derive")
    wrong = tm()
    (jd / "SEALS.jsonl").write_text(seal_row(other) + "\n")
    cx(r, "derive")
    elsewhere = tm()
    (jd / "SEALS.jsonl").write_text(json.dumps({"time": "2026-11-17T08:40:00+01:00", "file": "OUTCOME_round_0.json",
                                                "sha256": hashlib.sha256(outc.read_bytes()).hexdigest()}) + "\n")
    cx(r, "derive")
    rel = tm()
    check("K-505 (F-4): a wrong sha → NR; a same-named folder under another parent → NR; the right relative row → its time",
          wrong == X.NR and elsewhere == X.NR and rel == "2026-11-17T08:40:00+01:00", (wrong, elsewhere, rel))
    # K-506: the L2 case one byte over: ≤ 7276 with its LF, 2 fence lines
    n0 = {"id": "U-0123456789ab", "kind": "user", "lifecycle": "decided", "rationale": ""}
    render = lambda n: (f"# L2 {X.id_field(n['id'])}\n# {X.DATA_HDR}\n"
                        + X.fence(json.dumps({k: v for k, v in n.items()}, sort_keys=True, ensure_ascii=False, indent=1)))
    k = X.PAGE_MAX - len(render(n0).encode())
    n1 = dict(n0, rationale="r" * k)
    over = len(render(n1).encode()) + 1
    out = X.l2(n1)
    check("K-506 (F-3): the 7277-B L2 (7276 + its LF) is cut to ≤ 7276 with its LF, 2 fence lines",
          over == X.PAGE_MAX + 1 and len(out.encode()) + 1 <= X.PAGE_MAX and len(fences(out)) == 2, (over, len(out.encode())))
    n2 = dict(n0, rationale="x" * 9000, question="y" * 9000, extra=["z" * 3000] * 3)
    out = X.l2(n2)
    check("K-506: scalars alone over 7276 B: halved inside the JSON, the fence still closes",
          len(out.encode()) + 1 <= X.PAGE_MAX and len(fences(out)) == 2 and json.loads(out.split("\n", 3)[3].rsplit("\n", 1)[0]))
    # K-507 (F-6): CYCLE over depends_on ∪ supersedes; the radius over depends_on only
    r = new_repo(base, "k507")
    u1 = dec(r, "u1")
    u2 = dec(r, "u2", depends=[u1], supersedes=[])
    body = (f"KIND user\nTIME {T0}\nBY user\nAUTHORITY owner\nQUESTION cyc\nOPTIONS (a) x | (b) y\nCHOSE (a)\n"
            f"REJECTED none\nRATIONALE r\nIMPACT core\nEVIDENCE none\nDEPENDS-ON none\nSUPERSEDES {u2}\n").encode()
    u3 = "U-" + hashlib.sha256(body).hexdigest()[:12]
    (r / f".swarmer/crossroads/records/{u3}.md").write_bytes(body)
    body = (f"KIND user\nTIME {T0}\nBY user\nAUTHORITY owner\nQUESTION cyc2\nOPTIONS (a) x | (b) y\nCHOSE (a)\n"
            f"REJECTED none\nRATIONALE r\nIMPACT core\nEVIDENCE none\nDEPENDS-ON {u3}\n").encode()
    u0 = "U-" + hashlib.sha256(body).hexdigest()[:12]
    (r / f".swarmer/crossroads/records/{u0}.md").write_bytes(body)
    cx(r, "derive")
    fs = finds(r)
    nocyc = not kinds(fs, "CYCLE")          # records alone: ids are content hashes, so no cycle (F-004)
    body = (f"KIND user\nTIME {T0}\nBY user\nAUTHORITY owner\nQUESTION cyc3\nOPTIONS (a) x | (b) y\nCHOSE (a)\n"
            f"REJECTED none\nRATIONALE r\nIMPACT core\nEVIDENCE none\nDEPENDS-ON {u2}\nSUPERSEDES {u3}\n").encode()
    u4 = "U-" + hashlib.sha256(body).hexdigest()[:12]
    (r / f".swarmer/crossroads/records/{u4}.md").write_bytes(body)
    # a cycle needs a source whose edges are not content-addressed: a jury where D1 depends on D2 and D2 supersedes D1
    jd = make_jury(r / ".swarmer" / "jc", {"D1": ("APPROVED", "a", ["D2"]), "D2": ("APPROVED", "a", [])},
                   "SUPERSEDES D2 D1\n")
    cx(r, "derive")
    fs = finds(r)
    cyc = kinds(fs, "CYCLE")
    rc, rad, e = cxj(r, "radius", u2)
    rad_ok = rc == 0 and set(rad) == {u2, u4}
    ev = dec(r, "cites", evidence=u1)
    sup = dec(r, "sups", supersedes=[u1], time_="2026-11-17T09:00:00+01:00")
    rc, rad1, e = cxj(r, "radius", u1)
    check("K-507 (F-6): CYCLE over depends_on ∪ supersedes (a jury D1 depends on D2, D2 supersedes D1)",
          nocyc and len(cyc) == 1 and "#D1" in cyc[0][2] and "#D2" in cyc[0][2], fs)
    check("K-507: the radius spreads over depends_on only, never over rests_on (evidence) or supersedes",
          rad_ok and set(rad1) == {u1, u2, u4}, (rad, rad1))
    # K-102 (F-5): G7 decides «still realized», G8 is evidence, LIVE-DISAGREES when they differ
    r = new_repo(base, "k102")
    d = dec(r, "d")
    e_ = dec(r, "e")
    ed(r, "src/shared.py", 10, "common line")
    g(r, "add", "-A")
    cx(r, "realize", d, "--concern", "core", "--time", T0)
    c = commit(r, d, "core")
    ed(r, "src/shared.py", 40, "common line")
    commit(r, e_, "core")
    g(r, "revert", "--no-edit", c)
    dec(r, "dp", supersedes=[d], time_="2026-11-17T09:00:00+01:00")
    cx(r, "derive")
    fs = finds(r)
    n = view(r)[d]
    check("K-102 (F-5): a full revert chain → not realized (no SUPERSEDED-STILL-REALIZED) while live > 0 → LIVE-DISAGREES",
          n["live"] == 1 and not [f for f in kinds(fs, "SUPERSEDED-STILL-REALIZED") if f[1] == d]
          and [f for f in kinds(fs, "LIVE-DISAGREES") if f[1] == d], (n["live"], fs))
    r = new_repo(base, "k102b")
    d, x = dec(r, "d"), dec(r, "x")
    ed(r, "src/shared.py", 10, "only D")
    g(r, "add", "-A")
    cx(r, "realize", d, "--concern", "core", "--time", T0)
    commit(r, d, "core")
    ed(r, "src/shared.py", 10, "X rewrote it")
    commit(r, x, "core")
    dec(r, "dp", supersedes=[d], time_="2026-11-17T09:00:00+01:00")
    cx(r, "derive")
    fs = finds(r)
    check("K-102 reverse: still realized by its commit (G7) while live = 0 → SUPERSEDED-STILL-REALIZED and LIVE-DISAGREES",
          view(r)[d]["live"] == 0 and [f for f in kinds(fs, "SUPERSEDED-STILL-REALIZED") if f[1] == d]
          and [f for f in kinds(fs, "LIVE-DISAGREES") if f[1] == d], fs)
    p = base / "k102n"
    p.mkdir()
    (p / "f.txt").write_text("a\n")
    d = dec(p, "d")
    cx(p, "stage", "f.txt")
    (p / "f.txt").write_text("a\nD line\n")
    cx(p, "realize", d, "--concern", "core", "--time", T0)
    dec(p, "dp", supersedes=[d], time_="2026-11-17T09:00:00+01:00")
    cx(p, "derive")
    fs = finds(p)
    check("K-102 without git: the rule falls back to G8 (live > 0 → SUPERSEDED-STILL-REALIZED)",
          [f for f in kinds(fs, "SUPERSEDED-STILL-REALIZED") if f[1] == d and "G8" in f[2]], fs)
    # F-2 in derive: a commit scan meeting a typechange gives the info finding UNSUPPORTED
    r = new_repo(base, "f2scan")
    d = dec(r, "d")
    W(r, "src/t.txt", ["one"])
    g(r, "add", "-A")
    cx(r, "realize", d, "--concern", "core", "--time", T0)
    commit(r, d, "core")
    (r / "src/t.txt").unlink()
    os.symlink("shared.py", r / "src/t.txt")
    commit(r, None, None, "typechange")
    rc, o, e = cx(r, "derive", "-v")
    check("K-502 in derive: the commit scan gives the info finding UNSUPPORTED for a typechange, derive exits 0",
          rc == 0 and re.search(r"^UNSUPPORTED\t[0-9a-f]{12}\tsrc/t\.txt: typechange", o, re.M), o)
    # F-7: a source below the read depth → SOURCE-SKIPPED (report), never silence
    r = new_repo(base, "f7")
    make_jury(r / ".swarmer" / "conv" / "f5" / "01-jury", {"D1": ("APPROVED", "a", [])}, "")
    conv(r / ".swarmer" / "conv", "# triage\nTRIAGE H-001 TEST ok\n")
    cx(r, "derive")
    fs = finds(r)
    check("F-7: a jury nested below the read depth → SOURCE-SKIPPED (report) with its relative path",
          [f for f in kinds(fs, "SOURCE-SKIPPED") if f[1] == ".swarmer/conv/f5/01-jury"], fs)


# ======================================================================= joint tests J1-J3, regressions
TRIAGE = ("# Triage f2\nThe hypotheses H-001, H-002 and H-003.\n"
          "TRIAGE H-001 TEST capture by derivation\nTRIAGE H-002 REFORMULATE too wide\nTRIAGE H-003 OPEN later\n"
          "QUESTION H-001 how to capture decisions?\nRATIONALE H-002 the statement is too wide\n"
          "DEPENDS-ON H-002 H-001\nEVIDENCE H-001 CARDS.md@0123456789ab\nIMPACT H-001 engine\n")
SELECTION = ("# Selection\nH-001 is selected, H-002 is not.\nREJECTED select (H-002) reformulate first\n"
             "RATIONALE select the cheapest test first\n"
             "DEPENDS-ON select conv@2026-11-17T08:03:16+01:00/f2/03-triage/TRIAGE.md#H-001\n")


def w_fixture(r):
    """a W-like source set with edges across every kind: a convening, a jury that depends on its triage, U records"""
    c = conv(r / ".swarmer" / "conv1", TRIAGE, SELECTION, selected=("H-001",))
    jd = make_jury(r / ".swarmer" / "jury1", {"D1": ("APPROVED", "a", []), "D2": ("RECOMMENDED", "a", ["D1"])},
                   "QUESTION D1 which store?\nREJECTED D1 (z) too heavy\n")
    cx(r, "derive")
    V = view(r)
    h1 = next(k for k in V if k.endswith("TRIAGE.md#H-001"))
    j1 = next(k for k in V if k.endswith("#D1") and k.startswith("jury:"))
    u1 = dec(r, "u1", depends=[h1, j1])
    u2 = dec(r, "u2", depends=[u1])
    cx(r, "derive")
    return {"h1": h1, "h2": h1.replace("H-001", "H-002"), "sel": next(k for k in view(r) if k.endswith("#select")),
            "j1": j1, "j2": j1.replace("#D1", "#D2"), "u1": u1, "u2": u2, "conv": c, "jury": jd}


def group_joint(base):
    # J1: Branch A on Branch B's graph: no alias, no dangling depends_on, the radius across kinds
    r = new_repo(base, "j1")
    I = w_fixture(r)
    V = view(r)
    deps = [(k, t) for k, n in V.items() for t in n.get("depends_on", [])]
    low = {}
    for k in V:
        low.setdefault(k.casefold(), set()).add(k)
    rc, rad, e = cxj(r, "radius", I["h1"])
    check("J1: every depends_on target is a node id (0 dangling), no two ids equal up to case (0 aliases)",
          deps and all(t in V for _k, t in deps) and all(len(v) == 1 for v in low.values()), [d for d in deps if d[1] not in V])
    check("J1: radius on B's graph spans the kinds: triage H-001 → H-002, select, u1, u2",
          rc == 0 and set(rad) == {I["h1"], I["h2"], I["sel"], I["u1"], I["u2"]}, rad)
    rc, b, e = cxj(r, "brief", I["j1"])
    check("J1: brief of a jury decision on B's graph (rc 0, page ≤ 7276 B)",
          rc == 0 and max(b["page_bytes"]) <= X.PAGE_MAX and b["radius"] == 4, b)
    # X2: the edge set against hand-written expected edges
    want = {(I["h2"], "depends_on", I["h1"]), (I["sel"], "depends_on", I["h1"]), (I["j2"], "depends_on", I["j1"]),
            (I["u1"], "depends_on", I["h1"]), (I["u1"], "depends_on", I["j1"]), (I["u2"], "depends_on", I["u1"]),
            (I["h1"], "chose", I["h1"] + "(TEST)"), (I["sel"], "chose", I["sel"] + "(H-001)"),
            (I["sel"], "discarded", I["sel"] + "(H-002)"), (I["j1"], "chose", I["j1"] + "(a)"),
            (I["j1"], "discarded", I["j1"] + "(z)"), (I["u1"], "chose", I["u1"] + "(a)"),
            (I["u1"], "discarded", I["u1"] + "(b)")}
    got = {(k, e_, t) for k, n in V.items() for e_, t in n["edges"] if e_ in ("depends_on", "supersedes", "chose", "discarded")
           and k in {I[x] for x in ("h1", "h2", "sel", "j1", "j2", "u1", "u2")} and e_ != "discarded" or
           (e_ == "discarded" and k in {I["sel"], I["j1"], I["u1"]})}
    got = {x for x in got if x[1] != "discarded" or x[0] in {I["sel"], I["j1"], I["u1"]}}
    want_dis = {x for x in want if x[1] == "discarded"}
    ok = (want - got) == set() and {x for x in got if x[1] in ("depends_on", "supersedes")} == \
        {x for x in want if x[1] == "depends_on"}
    check("X2: the derived edges = the hand-written expected edges (depends_on exactly; chose and discarded present)",
          ok and want_dis <= got, sorted((want - got) | ({x for x in got if x[1] == "depends_on"} -
                                                         {x for x in want if x[1] == "depends_on"})))
    sel = V[I["sel"]]
    check("J1: the selection's discarded H-002 carries its reason, the rationale is the line's",
          sel["rejected"].get("H-002") == "reformulate first" and sel["rationale"] == "the cheapest test first", sel["rejected"])
    # C2: read commands write nothing; C3: derive is deterministic, also from a copy of the project
    st = r / ".swarmer/crossroads"
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in st.rglob("*") if p.is_file()}
    for argv in (("show", I["u1"]), ("show", I["u1"], "--level", "0"), ("show", I["j1"], "--level", "2"), ("check",),
                 ("radius", I["u1"]), ("lint", I["conv"] / "f2/03-triage/TRIAGE.md"),
                 ("changes", "--since", "SNAPSHOT_" + (st / "log/LATEST").read_text().strip())):
        cx(r, *argv)
    after = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in st.rglob("*") if p.is_file()}
    check("C2: show, check, radius, lint, changes write nothing when the view is fresh", before == after,
          sorted(str(p) for p in set(before) ^ set(after)))
    g1 = (st / "view/graph.jsonl").read_bytes()
    cx(r, "derive")
    g2 = (st / "view/graph.jsonl").read_bytes()
    cp = base / "j1copy"
    shutil.copytree(r, cp, symlinks=True)
    shutil.rmtree(cp / ".swarmer/crossroads/view")
    cx(cp, "derive")
    check("C3: derive is deterministic (twice, and from a copy of the project in another folder)",
          g1 == g2 == (cp / ".swarmer/crossroads/view/graph.jsonl").read_bytes())
    j2(base)
    # J3: one glossary in the crossroads documents
    bad = []
    for l in ("en", "it"):
        for n in ("CROSSROADS.md", "CROSSROADS_FORMATS.md", "SKILL.md"):
            t = (EXT / "docs" / l / n).read_text()
            prose = re.sub(r"`[^`\n]*`", "", re.sub(r"```.*?```", "", t, flags=re.S))
            for rx in (r"\bC_R\b", r"\bT4\b", r"file token", r"(?<![#\w-])D\d+\b", r"\b\d+ holds?\b", r"defects? holds?"):
                bad += [f"{l}/{n}: {rx}: {m.group(0)}" for m in re.finditer(rx, prose)]
    check("J3: the crossroads documents (en, it) use C_Rad, R, D, token and holds in their glossary sense only", not bad, bad)


def j2(base):
    """J2: the contract's scenario end to end: ≥ 8 decisions over 3 levels, ≥ 2 commits per concern, a late failure
    traced to D; derive, brief, plan, apply --execute, verify."""
    r = base / "j2"
    r.mkdir()
    g(r, "init", "-q", "-b", "main")
    (r / ".git/info/exclude").write_text(".swarmer/\n")
    W(r, "src/core/format.py", ["FORMAT = 'v0'", "def load(x):", "    return x", "# end"])
    W(r, "src/api/routes.py", ["ROUTES = []"] + ["# r%d" % i for i in range(1, 10)] + ["# end"])
    W(r, "docs/guide.md", ["# guide", "one", "two", "three", "four", "end"])
    W(r, "check.py", ["import sys", "t = open('src/core/format.py').read()",
                      "sys.exit(1 if 'v1' in t or 'cache_v1' in open('src/api/routes.py').read() else 0)"])
    commit(r, None, None, "base")
    (r / ".swarmer/crossroads").mkdir(parents=True)
    (r / ".swarmer/crossroads/CONCERNS.md").write_text("CONCERN core src/core/*\nCONCERN api src/api/*\n"
                                                      "CONCERN docs docs/* check.py\n")
    t = lambda m: "2026-11-17T08:%02d:00+01:00" % m
    I = {}
    I["A"] = dec(r, "A", impact="docs", time_=t(1))
    I["B"] = dec(r, "B", impact="api", time_=t(2))
    I["D"] = dec(r, "D", impact="core api", time_=t(3), evidence=I["A"],
                 options="(v1) the cache format v1 | (v0) keep v0 | (ext) an external store", chose="v1",
                 reject=("(v0) slower reads", "(ext) one more service"), question="which cache format?")
    I["C"] = dec(r, "C", depends=[I["A"]], impact="docs", time_=t(4))
    I["F"] = dec(r, "F", depends=[I["D"]], impact="api", time_=t(5))
    I["G"] = dec(r, "G", depends=[I["F"]], impact="api", time_=t(6))
    I["H"] = dec(r, "H", depends=[I["D"]], impact="core", time_=t(7))
    I["K"] = dec(r, "K", depends=[I["B"]], impact="api", time_=t(8))

    def work(name, con, path, line, text):
        ed(r, path, line, text)
        g(r, "add", path)
        rc_, rid, e_ = cx(r, "realize", I[name], "--concern", con, "--time", t(30))
        rc_, tr, e_ = cx(r, "trailers", I[name], con)
        g(r, "commit", "-q", "-F", "-", inp=(f"{name} in {con}\n\n" + tr).encode())
    work("A", "docs", "docs/guide.md", 2, "one (A)")
    work("D", "core", "src/core/format.py", 1, "FORMAT = 'v1'")
    work("B", "api", "src/api/routes.py", 2, "# r1 (B)")
    work("D", "api", "src/api/routes.py", 4, "ROUTES.append('cache_v1')")
    work("C", "docs", "docs/guide.md", 4, "three (C)")
    work("F", "api", "src/api/routes.py", 6, "# r5 (F)")
    work("H", "core", "src/core/format.py", 3, "    return x  # H")
    work("G", "api", "src/api/routes.py", 10, "# r9 (G)")
    work("K", "api", "src/api/routes.py", 8, "# r7 (K)")
    late = dec(r, "late", evidence=I["A"], time_=t(40), impact="docs")
    head0 = g(r, "rev-parse", "HEAD").strip()
    failing = subprocess.run([sys.executable, "-I", "-B", "check.py"], cwd=r).returncode
    rc, o, e = cx(r, "derive")
    rc_cc, cc, e_cc = cx(r, "check-commits", "HEAD~9..HEAD")
    check("J2: the late failure is there (tests exit 1); derive ok; check-commits 0 violations by concern",
          failing == 1 and rc == 0 and rc_cc == 0 and cc == "", (o, cc))
    rc, b, e = cxj(r, "brief", I["D"])
    p1 = (r / b["out"] / "p1.md").read_text()
    check("J2: page 1 has D's discarded options with their reasons and Δ (the later record citing D's evidence)",
          "(v0) keep v0; reason: slower reads" in p1 and "(ext) an external store; reason: one more service" in p1
          and re.search(r"^## Changed since\n- [0-9a-f]{12} evidence ", p1, re.M) and b["radius"] == 4
          and b["reads"]["n"] == 4, p1)
    res = reverse(r, I["D"], tests=f"{sys.executable} -I -B check.py")
    hand_core = "FORMAT = 'v0'\ndef load(x):\n    return x\n# end\n"
    hand_api = "ROUTES = []\n# r1 (B)\n# r2\n# r3\n# r4\n# r5\n# r6\n# r7 (K)\n# r8\n# r9\n# end\n"
    pages = [p for p in (r / ".swarmer/crossroads/view").rglob("*.md")]
    check("J2: apply --execute → OK; outside the radius nothing changed; inside = HAND; tests_exit printed (0)",
          hand_ok(res, {"src/core/format.py": hand_core, "src/api/routes.py": hand_api,
                        "docs/guide.md": "# guide\none (A)\ntwo\nthree (C)\nfour\nend\n"})
          and res["apply"].get("tests_exit") == 0 and len(res["commits"]) == 5, (res.get("status"), res["issues"], res.get("apply")))
    check("J2: every page written (brief, PLAN) ≤ 7276 B", pages and all(len(p.read_bytes()) <= X.PAGE_MAX for p in pages))
    rc, v, e = cxj(r, "verify", res.get("plan_path", "x"), "--dprime", res.get("dprime", "x"), "--tests",
                   f"{sys.executable} -I -B check.py")
    check("J2: verify on the new branch: I1, I2, I3 hold, status OK", rc == 0 and v.get("status") == "OK" and v.get("I1")
          and v.get("I2") and v.get("I3"), v)
    rc, o, e = cx(r, "check-commits", f"{head0}..HEAD")
    check("J2: the reversal commits carry D', the concern and Crossroads-Reverts (check-commits clean)", rc == 0 and o == "", o)
    g(r, "switch", "-q", "main")
    check("J2: the current branch and HEAD are untouched by apply", g(r, "rev-parse", "HEAD").strip() == head0)
    return r


def group_regressions(base):
    """X1a: the weave = the replay oracle (git's own merge machinery, merge-tree) on the exhaustive 2-commit domain
    d1 2 (unique lines); every compared case equal; the cases git cannot merge or the weave entangles are skipped,
    as the plan blocks them."""
    def ops(L, fresh):
        out = [("c", i, fresh) for i in range(len(L))]
        out += [("i", i, fresh) for i in range(len(L) + 1)]
        out += [("d", i, None) for i in range(len(L)) if len(L) > 1]
        return out

    def do(L, op):
        k, i, v = op
        L = list(L)
        if k == "c":
            L[i] = v
        elif k == "i":
            L.insert(i, v)
        else:
            del L[i]
        return L
    base_l = ["a", "b", "c", "d"]
    hist = [(o1, o2) for o1 in ops(base_l, "n0") for o2 in ops(do(base_l, o1), "n1")]
    if not LONG:
        hist = hist[::3]
    r = base / "x1a"
    r.mkdir()
    g(r, "init", "-q", "-b", "main")
    stream, marks = [], []
    blob = lambda L: "".join(x + "\n" for x in L).encode()

    def cmt(ref, mark, frm, data):
        m = b"m\n"
        s_ = b"commit %s\nmark :%d\ncommitter x <x@invalid> 1794902400 +0100\ndata %d\n%s" % (ref, mark, len(m), m)
        if frm:
            s_ += b"from :%d\n" % frm
        return s_ + b"M 100644 inline f.txt\ndata %d\n%s\n" % (len(data), data)
    mk = 1
    for hi, (o1, o2) in enumerate(hist):
        L1 = do(base_l, o1)
        L2 = do(L1, o2)
        ref = b"refs/heads/h%d" % hi
        stream += [cmt(ref, mk, None, blob(base_l)), cmt(ref, mk + 1, mk, blob(L1)), cmt(ref, mk + 2, mk + 1, blob(L2))]
        marks.append((mk, mk + 1, mk + 2))
        mk += 3
    exp = b"".join(stream) + b"".join(b"" for _ in ())
    marks_file = r / "marks"
    subprocess.run(["git", "-C", str(r), "fast-import", "--quiet", "--export-marks=" + str(marks_file)], input=exp,
                   check=True, env=clean_env())
    M = dict(l.split() for l in marks_file.read_text().splitlines())
    shas = [tuple(M[":%d" % x] for x in t_) for t_ in marks]
    ch_, _ = A.changes(str(r), [s for t_ in shas for s in t_[1:]])
    compared = mismatch = skipped = 0
    detail = []
    for (b_, c0, c1), (o1, o2) in zip(shas, hist):
        L1 = do(base_l, o1)
        for S in ({c0}, {c1}, {c0, c1}):
            W_ = A.Weave("f.txt", ("100644", blob(base_l)))
            bad = []
            for k in (c0, c1):
                for sec in ch_[k]:
                    W_.step(k, sec, S, bad)
            if bad:
                skipped += 1
                continue
            if S == {c0, c1}:
                orc = blob(base_l)
            elif S == {c1}:
                orc = blob(L1)
            else:
                mt = subprocess.run(["git", "-C", str(r), "merge-tree", "--write-tree", "--merge-base", c0, b_, c1],
                                    capture_output=True, env=clean_env())
                if mt.returncode:
                    skipped += 1
                    continue
                orc = subprocess.run(["git", "-C", str(r), "cat-file", "blob", mt.stdout.split()[0].decode() + ":f.txt"],
                                     capture_output=True).stdout
            got = W_.expected(S)[1]
            compared += 1
            if got != orc:
                mismatch += 1
                detail.append((o1, o2, len(S), got, orc))
    check(f"X1a: weave = replay oracle on the 2-commit domain d1 2 ({compared} compared, {skipped} git or the weave refuse)",
          compared > 100 and mismatch == 0, detail[:5])
    # P13 (K-302): the grid of one radius commit D and one outside commit X at a gap; the oracle is «line 09»
    rows = []
    for op_, gap_, side in itertools.product(("change", "delete", "insert"), (0, 1, 2), ("above", "below")):
        rr = base / f"grid_{op_}{gap_}{side}"
        rr.mkdir()
        g(rr, "init", "-q", "-b", "main")
        (rr / ".git/info/exclude").write_text(".swarmer/\n")
        L = ["line %02d" % j for j in range(20)]
        W(rr, "f.txt", L)
        commit(rr, None, None, "base")
        I = records(rr, [("D", []), ("X", [])])
        a_ = list(L)
        a_[9] = "D changed line 10"
        W(rr, "f.txt", a_)
        commit(rr, I["D"], "core")
        b2 = list(a_)
        if op_ in ("change", "delete"):
            j = 9 - 1 - gap_ if side == "above" else 10 + gap_
            if op_ == "change":
                b2[j] = "X changed line %d" % (j + 1)
            else:
                del b2[j]
        else:
            b2.insert((9 - gap_) if side == "above" else (10 + gap_), "X inserted line")
        W(rr, "f.txt", b2)
        commit(rr, I["X"], "core")
        oracle = "".join(("line 09" if l == "D changed line 10" else l) + "\n" for l in b2)
        res = reverse(rr, I["D"])
        flagged = "ENTANGLED" in res["issues"]
        rows.append((op_, gap_, side, flagged, res.get("status"),
                     res.get("status") != "OK" or res["after"]["f.txt"][1].decode() == oracle))
    wrong = [x for x in rows if not x[5] or (x[1] == 0 and not x[3] and x[0] != "insert")]
    check("P13 (K-302): the grid: every unflagged reversal = the oracle («line 09» back), adjacent changes flagged",
          not wrong and any(x[4] == "OK" for x in rows), wrong or rows)


# ======================================================================= scale (P4b, E9, A22) and the class 3 fixture
def gen_scale(root, N, L=96):
    """N decisions as U records and one commit each (git fast-import): a fixed component Q (|Rad| = 50), the root
    component M (a random tree), and Z (15 records later than everything, citing the evidence of Q0 and M0: Δ).
    Text fields are filled to L bytes. Deterministic (seeded); returns {"Q0", "M0", "leaf", "ids"}."""
    import random
    rnd = random.Random(N * 1000 + L)
    root = Path(root)
    root.mkdir(parents=True)
    g(root, "init", "-q", "-b", "main")
    (root / ".git/info/exclude").write_text(".swarmer/\n")
    st = X.Store({"swarm": SOURCE, "root": root})
    q = min(50, N // 2)
    z = 15 if N >= 100 else min(5, N - q - 2)
    m = N - q - z
    fill = lambda salt: (salt + " " + "the nearer city, the stronger coffee, the smaller unit; " * 4)[:L]
    iso = lambda k: "2026-11-17T%02d:%02d:%02d+01:00" % (9 + k // 3600 % 10, k // 60 % 60, k % 60)

    def rec(k, deps, ev):
        return X.write_record(st, "U", {"KIND": "user", "TIME": iso(k), "BY": "user", "AUTHORITY": "owner",
                                        "QUESTION": fill(f"q{k}"), "OPTIONS": f"(a) {fill('a')} | (b) {fill('b')}",
                                        "CHOSE": "(a)", "REJECTED": [f"(b) {fill('r')}"], "RATIONALE": fill(f"r{k}"),
                                        "IMPACT": "concern-%02d" % (k % 20), "EVIDENCE": " ".join(ev),
                                        "DEPENDS-ON": " ".join(deps) or "none"})
    Q, M, Z = [], [], []
    for i in range(q):
        Q.append(rec(i, [] if i == 0 else [Q[rnd.randrange(i)]], [f"E-q{i}"]))
    for i in range(m):
        M.append(rec(q + i, [] if i == 0 else [M[rnd.randrange(i)]], [f"E-m{i}"]))
    for i in range(z):
        Z.append(rec(q + m + i, [], ["E-q0", "E-m0"]))
    files = {}
    buf, n = [], 0
    order = [("q", i) for i in range(q)] + [("m", i) for i in range(m)]
    rnd.shuffle(order)
    order.sort(key=lambda t_: (t_ != ("q", 0), t_ != ("m", 0)))
    for kind, i in order:
        x = (Q if kind == "q" else M)[i]
        path = "src/q%02d.py" % (i % 10) if kind == "q" else "src/f%02d.py" % (i % 100)
        f = files.setdefault(path, ["%s line %03d" % (path, j) for j in range(200)])
        f[(2 * (i // (10 if kind == "q" else 100))) % 200] = "%s edits line" % x
        body = "".join(l + "\n" for l in f).encode()
        msg = ("work for %s\n\n%s: %s\n%s: concern-%02d\n" % (x, TD, x, TC, i % 20)).encode()
        n += 1
        buf.append(b"commit refs/heads/main\ncommitter x <x@invalid> %d +0100\ndata %d\n%s\n" % (1794902400 + n, len(msg), msg))
        buf.append(b"M 100644 inline %s\ndata %d\n%s\n" % (path.encode(), len(body), body))
    subprocess.run(["git", "-C", str(root), "fast-import", "--quiet"], input=b"".join(buf), check=True, env=clean_env())
    g(root, "checkout", "-q", "main")
    return {"Q0": Q[0], "M0": M[0], "leaf": M[-1], "N": N}


def scale_case(base, N):
    r = base / f"scale{N}"
    t = time.perf_counter()
    I = gen_scale(r, N)
    tg = time.perf_counter() - t
    t = time.perf_counter()
    rc, o, e = cx(r, "derive")
    td = time.perf_counter() - t
    rc1, b, e1 = cxj(r, "brief", I["Q0"])
    rcr, broot, er = cxj(r, "brief", I["M0"])
    t = time.perf_counter()
    rc2, pl, out, e2 = plan_of(r, I["Q0"])
    tp = time.perf_counter() - t
    pages = list((r / ".swarmer/crossroads/view").rglob("*.md"))
    return {"N": N, "derive_rc": rc, "brief_pages_fixed": b.get("pages"), "brief_reads": b.get("reads", {}).get("n"),
            "brief_root_pages": broot.get("pages"), "plan_rc": rc2, "plan_commits": len(pl.get("commits_newest_first", [])),
            "max_page": max(len(p.read_bytes()) for p in pages) if pages else None, "seconds": [round(tg, 1), round(td, 1), round(tp, 1)],
            "delta": b.get("delta", {}).get("n"), "radius": b.get("radius")}


def group_scale(base):
    small, big = scale_case(base, 200), scale_case(base, 2000)
    check("P4b: the brief of a fixed radius (50) costs the same pages at N=200 and N=2000; Δ folds; reads = |Rad|",
          small["brief_pages_fixed"] == big["brief_pages_fixed"] and big["radius"] == 50 and big["brief_reads"] == 50
          and big["delta"] == 15, (small, big))
    check("scale N=2000: derive, plan (50 commits, 0 issues) and briefs, every page ≤ 7276 B",
          big["derive_rc"] == 0 and big["plan_rc"] == 0 and big["plan_commits"] == 50 and big["max_page"] <= X.PAGE_MAX, big)
    if LONG:
        huge = scale_case(base, 20000)
        check("scale N=20000 (--long): the same pages as N=2000 for the fixed radius, every page ≤ 7276 B",
              huge["brief_pages_fixed"] == big["brief_pages_fixed"] and huge["max_page"] <= X.PAGE_MAX
              and huge["plan_rc"] == 0, huge)


def make_fixture(d):
    """--make-fixture DIR: the J2 fixture and the scale fixture (N=2000, fields of 96 bytes, D = the root) for the
    class 3 run (P17/M20). Writes only under DIR, which must not exist."""
    d = Path(d)
    if d.exists():
        sys.exit(f"{d} exists: give a new folder")
    d.mkdir(parents=True)
    j = j2(d)
    I = gen_scale(d / "scale", 2000, 96)
    cx(d / "scale", "derive")
    (d / "FIXTURE.json").write_text(json.dumps({"j2": str(j.relative_to(d)), "scale": "scale", "D_scale_root": I["M0"],
                                                "N": 2000, "field_bytes": 96}, indent=1) + "\n")
    print(f"fixture written: {d}/FIXTURE.json (J2 in {j.name}/, scale in scale/, D = {I['M0']})")
    return 0


def main():
    if "--make-fixture" in sys.argv:
        return make_fixture(Path(sys.argv[sys.argv.index("--make-fixture") + 1]))
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for name, fn in GROUPS:
            d = base / name
            d.mkdir()
            t = time.time()
            try:
                fn(d)
            except Exception as e:   # a crash of a group is a failure, never a traceback that hides the others
                import traceback
                check(f"{name}: no exception", False, "".join(traceback.format_exception(e))[-1500:])
            print(f"     ({name}: {time.time() - t:.1f} s)")
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed in {time.time() - t0:.0f} s")
    sys.exit(1 if failed else 0)


GROUPS = [("extensions", group_extensions), ("hunksha", group_hunksha), ("a", group_a), ("audit", group_audit),
          ("b", group_b), ("k", group_k), ("joint", group_joint), ("refs", group_refs),
          ("regressions", group_regressions),
          ("scale", group_scale)]


if __name__ == "__main__":
    main()
