#!/usr/bin/env python3
"""Tests of swarmer 5.3.2, K-100 and S18: python3 -I -B tests/test_engine532.py

- K-100: no module of the engine puts its folder, nor extensions.entry the named swarm's <swarm>/engine or the
  extension's own folder, on sys.path ahead of the standard library: a file named like a stdlib module, planted in
  those folders, never runs in its place;
- S18: a timestamp .pyc of the same size and mtime as its source, planted in their __pycache__, never runs in place of
  the source: the engine compiles its modules, and the extension modules, from their source;
- a clean run of every launch form writes no .pyc;
- the version: plugin.json says 5.3.2 and both CHANGELOGs open with it.

Every launch form, with `python3 -I -B` (swarmer.sh finds `python3` in the PATH, here the interpreter under test):
swarmer.sh (a command, help, an extension command through the loader extensions.entry), the engine's module scripts
and the installed wrappers, crossroads.py run directly, the repository layout, and across swarms (the clean engine of
one swarm with `--swarm` naming another one, which is planted). On sys.executable and on python3.8, python3.10 and
python3.14 when the PATH has them. Installs the swarm with this tree's swarmer.sh, in a temporary folder. Exits with 1
if a check fails.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent
sys.dont_write_bytecode = True

results: list[tuple[str, bool]] = []
# names of stdlib modules that the engine, or crossroads, imports at its top or later (none of them is imported by the
# interpreter before a script runs, under -I)
STDLIB_NAMES = ("argparse", "ast", "base64", "bisect", "calendar", "datetime", "difflib", "fnmatch", "hashlib", "heapq",
                "hmac", "html", "json", "random", "secrets", "shutil", "string", "struct", "subprocess", "tempfile",
                "textwrap", "tokenize", "unicodedata")
TOY_IGNORE = (".git", "__pycache__", "tests", "swarmer.sh", "sciame.sh", "ROOT", "FACTORY.json", "RADICE",
              "FABBRICA.json")
# run by the interpreter under test: a timestamp .pyc (PEP 552 flags 0) for every source of a folder, with the mtime and
# the size of the source in its header, whose code appends to MARK and then runs the real source (so the outputs of a
# run do not change: only MARK tells)
PLANT_PYC = r'''
import importlib.util, marshal, os, sys
folder, mark = sys.argv[1], sys.argv[2]
for n in sorted(os.listdir(folder)):
    if not n.endswith(".py"):
        continue
    src = os.path.join(folder, n)
    st = os.stat(src)
    text = ("open(%r, 'a').write(%r)\n" % (mark, "pyc " + n + "\n")
            + "exec(compile(open(__file__, 'rb').read(), __file__, 'exec', dont_inherit=True))\n")
    code = compile(text, src, "exec", dont_inherit=True)
    pyc = importlib.util.cache_from_source(src)
    os.makedirs(os.path.dirname(pyc), exist_ok=True)
    with open(pyc, "wb") as f:
        f.write(importlib.util.MAGIC_NUMBER + (0).to_bytes(4, "little")
                + (int(st.st_mtime) & 0xFFFFFFFF).to_bytes(4, "little")
                + (st.st_size & 0xFFFFFFFF).to_bytes(4, "little")
                + marshal.dumps(code))
'''


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("ok   " if ok else "FAILED ") + name + ("" if ok or not detail else f"\n     {str(detail)[:1500]}"),
          flush=True)


def interpreters() -> list[tuple[str, str]]:
    """(label, path) of sys.executable and of python3.8, python3.10 and python3.14 when found, each real one once."""
    out, seen = [], set()
    for n in (sys.executable, "python3.8", "python3.10", "python3.14"):
        p = n if os.sep in n else shutil.which(n)
        if not p:
            print(f"skip {n}: not in the PATH")
            continue
        r = os.path.realpath(p)
        if r in seen:
            continue
        v = subprocess.run([p, "-I", "-B", "-c", "import sys; print('%d.%d' % sys.version_info[:2]); "
                            "sys.exit(sys.version_info < (3, 8))"], capture_output=True)
        if v.returncode != 0:
            print(f"skip {n}: not a python >= 3.8")
            continue
        seen.add(r)
        out.append((v.stdout.decode().strip(), p))
    return out


class Lab:
    """Two installations (the planted one, and the clean one whose engine names it with --swarm), a repository copy,
    and the environment of one interpreter."""

    def __init__(self, base: Path):
        self.base = base
        self.home = base / "home"
        self.home.mkdir()
        self.mark = base / "MARK"
        self.root = base / "root"
        self.other = base / "other"
        for r in (self.root, self.other):
            r.mkdir()
            rc, out = self.sh_raw(["bash", str(SOURCE / "swarmer.sh"), "-C", str(r), "install", "--language", "en"])
            assert rc == 0, out
            rc, out = self.sh_raw(["bash", str(r / "swarmer" / "swarmer.sh"), "extensions", "--add", "crossroads"],
                                  cwd=r)
            assert rc == 0, out
        self.sw = self.root / "swarmer"
        self.osw = self.other / "swarmer"
        self.repo = base / "repo"
        shutil.copytree(SOURCE, self.repo, ignore=shutil.ignore_patterns(*TOY_IGNORE))
        self.proj = base / "proj"          # the project root of the repository forms (the current folder)
        self.proj.mkdir()
        self.bin = base / "bin"
        self.bin.mkdir()

    def env(self) -> dict:
        e = {k: v for k, v in os.environ.items() if not k.startswith(("SWARMER_", "SCIAME_"))}
        e["PATH"] = str(self.bin) + os.pathsep + e.get("PATH", "")
        e.update(HOME=str(self.home), GIT_CEILING_DIRECTORIES=str(self.base), GIT_CONFIG_NOSYSTEM="1")
        return e

    def use(self, py: str) -> None:
        """`python3` in the PATH is the interpreter under test (swarmer.sh runs python3)."""
        link = self.bin / "python3"
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(py)

    def sh_raw(self, argv, cwd=None):
        p = subprocess.run(argv, capture_output=True, stdin=subprocess.DEVNULL, cwd=cwd or self.base,
                           env={k: v for k, v in os.environ.items() if not k.startswith(("SWARMER_", "SCIAME_"))},
                           timeout=600)
        return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")

    def run(self, argv, cwd) -> tuple[int, str, str, str]:
        """rc, stdout, stderr and what the planted files wrote to MARK."""
        if self.mark.exists():
            self.mark.unlink()
        p = subprocess.run([str(a) for a in argv], capture_output=True, stdin=subprocess.DEVNULL, cwd=str(cwd),
                           env=self.env(), timeout=300)
        mark = self.mark.read_text(encoding="utf-8") if self.mark.exists() else ""
        if self.mark.exists():
            self.mark.unlink()
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace"), mark

    def forms(self, py: str) -> list[tuple[str, list, Path]]:
        sw, osw, repo, root = self.sw, self.osw, self.repo, self.root
        q = ["roles", "--question", "a python bug"]
        return [
            ("swarmer.sh verify", ["bash", sw / "swarmer.sh", "verify"], root),
            ("swarmer.sh professionals", ["bash", sw / "swarmer.sh", "professionals"], root),
            ("swarmer.sh help", ["bash", sw / "swarmer.sh", "help"], root),
            ("swarmer.sh crossroads derive (extensions.entry)",
             ["bash", sw / "swarmer.sh", "crossroads", "derive"], root),
            ("engine/swarmer.py language", [py, "-I", "-B", sw / "engine" / "swarmer.py", "--swarm", sw, "language"],
             root),
            ("engine/swarmer.py crossroads derive (extensions.entry)",
             [py, "-I", "-B", sw / "engine" / "swarmer.py", "--swarm", sw, "crossroads", "derive"], root),
            ("convene.py roles (installed wrapper)", [py, "-I", "-B", sw / "convene.py", *q], root),
            ("engine/convene.py roles", [py, "-I", "-B", sw / "engine" / "convene.py", *q], root),
            ("jury.py requests (installed wrapper)", [py, "-I", "-B", sw / "jury.py", "requests"], root),
            ("engine/jury.py requests", [py, "-I", "-B", sw / "engine" / "jury.py", "requests"], root),
            ("generate_agents.py --list", [py, "-I", "-B", sw / "generate_agents.py", "--list"], root),
            ("engine/professionals.py", [py, "-I", "-B", sw / "engine" / "professionals.py"], root),
            ("crossroads.py derive, run directly",
             [py, "-I", "-B", sw / "extensions" / "crossroads" / "engine" / "crossroads.py", "derive"], root),
            ("across swarms: the other swarm's clean engine, --swarm this one, crossroads derive",
             [py, "-I", "-B", osw / "engine" / "swarmer.py", "--swarm", sw, "crossroads", "derive"], root),
            ("across swarms: the other swarm's clean engine, --swarm this one, verify",
             [py, "-I", "-B", osw / "engine" / "swarmer.py", "--swarm", sw, "verify"], root),
            ("repository layout: engine/swarmer.py crossroads derive",
             [py, "-I", "-B", repo / "engine" / "swarmer.py", "--swarm", repo, "crossroads", "derive"], self.proj),
            ("repository layout: engine/convene.py roles", [py, "-I", "-B", repo / "engine" / "convene.py", *q],
             self.proj),
        ]

    def folders(self) -> list[Path]:
        """The planted folders: the engine and the extension folder of this swarm and of the repository copy."""
        return [d for s in (self.sw, self.repo) for d in (s / "engine", s / "extensions" / "crossroads" / "engine")]

    def plant_stdlib(self) -> None:
        for d in self.folders():
            for n in STDLIB_NAMES:
                (d / f"{n}.py").write_text(f"open({str(self.mark)!r}, 'a').write({'stdlib ' + n + chr(10)!r})\n",
                                           encoding="utf-8")

    def plant_pyc(self, py: str) -> None:
        for d in self.folders():
            rc = subprocess.run([py, "-I", "-B", "-c", PLANT_PYC, str(d), str(self.mark)], capture_output=True,
                                stdin=subprocess.DEVNULL, env=self.env(), timeout=120)
            assert rc.returncode == 0, rc.stderr.decode("utf-8", "replace")

    def unplant(self) -> None:
        for d in self.folders():
            shutil.rmtree(d / "__pycache__", ignore_errors=True)
            for n in STDLIB_NAMES:
                p = d / f"{n}.py"
                if p.exists():
                    p.unlink()

    def pycs(self) -> list[str]:
        out = []
        for top in (self.sw, self.osw, self.repo, self.proj):
            for dp, dn, fn in os.walk(top):
                out += [os.path.join(dp, x) for x in dn if x == "__pycache__"]
                out += [os.path.join(dp, x) for x in fn if x.endswith((".pyc", ".pyo"))]
        return sorted(out)


def one_interpreter(lab: Lab, label: str, py: str) -> None:
    L = f"[python {label}]"
    lab.use(py)
    lab.unplant()
    clean = {}
    for name, argv, cwd in lab.forms(py):
        clean[name] = r = lab.run(argv, cwd)
        check(f"{L} {name}: the clean run ends without a traceback", "Traceback" not in r[2], (r[0], r[2][-800:]))
    left = lab.pycs()
    check(f"{L}: a clean run of every launch form writes no __pycache__ and no .pyc", not left, left)
    for kind in ("stdlib", "pyc"):
        what = ("a file named like a stdlib module, planted in the engine and extension folders, never runs"
                if kind == "stdlib" else
                "a timestamp .pyc of the same size and mtime as its source, planted, never runs instead of the source")
        lab.unplant()
        lab.plant_stdlib() if kind == "stdlib" else lab.plant_pyc(py)
        for name, argv, cwd in lab.forms(py):
            r = lab.run(argv, cwd)
            check(f"{L} {name}: {what}", r[3] == "", (r[3], r[0], r[2][-600:]))
            check(f"{L} {name}: with the {kind} plants, the same exit code and output as the clean run",
                  r[:2] == clean[name][:2], (r[0], clean[name][0], r[1][-400:], clean[name][1][-400:], r[2][-400:]))
        lab.unplant()


def version():
    plugin = json.loads((SOURCE / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    check("version: plugin.json is 5.3.2", plugin.get("version") == "5.3.2", plugin.get("version"))
    for name in ("CHANGELOG.md", "CHANGELOG.it.md"):
        heads = re.findall(r"^## (\S+)", (SOURCE / name).read_text(encoding="utf-8"), re.M)
        check(f"version: {name} opens with 5.3.2, then 5.3.1", heads[:2] == ["5.3.2", "5.3.1"], heads[:3])


def main():
    if (SOURCE / ".claude-plugin" / "plugin.json").is_file():   # the repository (an installed swarm has none)
        version()
    pys = interpreters()
    with tempfile.TemporaryDirectory() as b:
        try:
            lab = Lab(Path(b))
        except Exception:  # noqa: BLE001
            check("the two installations and the repository copy are made", False, traceback.format_exc())
            lab = None
        if lab is not None:
            for label, py in pys:
                try:
                    one_interpreter(lab, label, py)
                except Exception:  # noqa: BLE001
                    check(f"[python {label}] ran to the end", False, traceback.format_exc())
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
