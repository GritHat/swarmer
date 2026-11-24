#!/usr/bin/env python3
"""Acceptance tests of swarmer 5.3, the core patch R1: python3 -I -B tests/test_engine53.py

Written by the tester from the specification, before reading the tests of the patch's authors:
- E1-E11, the «Engine tests» of propolis-design's f5/01-arbitro/ACCEPTANCE.md (ENG-12..23, COORD-1, COORD-2);
- E1 and E4 as the REVISION lines on D5 of 20261120-jury-propolis-plan/OUTCOME_round_0.json widen them: the order of
  f4 read from the seal times of SEALS.jsonl, never from an mtime (a late seal followed by a touch of
  COUNTERCHECKS.md stays refused, a block appended after the seal without its own seal is refused), and a repin that
  opens a round 2 of f4 with every round-1 file byte-identical, whose G4 under the rules 3 counts only its own files;
- E12, clause 10 of that jury's round 3: after an approved G5 «not closed», fund and close-branch act again, a second
  G5 goes to a new gate file that binds its own closure folder, GATE_f5.json and every file it binds stay
  byte-identical, the latest G5 is the one of the highest ASCII ordinal (never the mtime, never the sorted names), the
  lock opens only on a latest G5 that holds, and a gate file of f5 that is empty, starts with a BOM or is not UTF-8
  stops fund and close-branch with exit 1 and nothing written; in English and in Italian;
- ENG-24 (`jury.py count .`), ENG-25 (a deliverable that only quotes the placeholder) and ENG-26 (a later gate under
  the rules 3 does not see an f0 changed after G1).

Installs the swarm twice in a temporary folder, in English and in Italian, and drives `<swarm>/convene.py` and
`<swarm>/jury.py` by subprocess (the canonical commands in English, the aliases in Italian). Every non-UTF-8 file name
stays inside the temporary folder. Exits with 1 if a check fails.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent
ENGINE = SOURCE / "engine" / "swarmer.py"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SOURCE / "engine"))
import compat as C  # noqa: E402
import convene as V  # noqa: E402

results: list[tuple[str, bool]] = []
T0 = int(time.time()) - 200_000   # the seal times the tests choose: whole seconds, two days back
NAMES = {"00": "REVISION.md", "01": "COUNTERCHECKS.md", "02": "DEFECTS.md", "08": "HIDDEN_ASSUMPTIONS.md",
         "09": "VERDICT.md"}   # the outputs of the role folders of a round of f4 (PIPELINE f4)
CORRECTNESS_IT = {"proven": "dimostrata", "verified": "verificata", "refuted": "smentita"}
NOT_UTF8 = b"\xff\xfeodd-\xe9.txt"


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("ok   " if ok else "FAILED ") + name + ("" if ok or not detail else f"\n     {str(detail)[:1500]}"),
          flush=True)


def i18n(lang):
    out = json.loads((SOURCE / "i18n" / "en.json").read_text(encoding="utf-8"))
    for k, v in json.loads((SOURCE / "i18n" / f"{lang}.json").read_text(encoding="utf-8")).items():
        out[k] = {**out[k], **v} if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


TEXTS = {"en": i18n("en"), "it": i18n("it")}


def clean_env():
    e = {k: v for k, v in os.environ.items() if not k.startswith(("SWARMER_", "SCIAME_"))}
    e["PATH"] = os.pathsep.join(d for d in e.get("PATH", "").split(os.pathsep)
                                if d and not os.path.exists(os.path.join(d, "claude")))
    return e


def _file_limit(n):
    def apply():
        import resource
        import signal
        signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
        resource.setrlimit(resource.RLIMIT_FSIZE, (n, n))
    return apply


def py(*arg, cwd=None, fsize=None):
    """A Python script of the swarm, isolated; `fsize` caps the size of every file it writes (a write that fails)."""
    p = subprocess.run([sys.executable, "-I", "-B", *map(str, arg)], capture_output=True, stdin=subprocess.DEVNULL,
                       env=clean_env(), cwd=cwd, preexec_fn=_file_limit(fsize) if fsize else None)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


def iso(t: float) -> str:
    return datetime.datetime.fromtimestamp(t).astimezone().isoformat(timespec="seconds")


def files(root: Path) -> dict[str, bytes]:
    """Every regular file under `root` and its bytes: what «byte-identical» and «nothing written» compare."""
    out = {}
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            p = Path(dp) / f
            if not p.is_symlink():
                out[str(p.relative_to(root))] = p.read_bytes()
    return out


def changes(a: dict, b: dict) -> list[str]:
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def restore(c: Path, backup: Path) -> None:
    """The convening as it was, at the same absolute path (a gate binds absolute paths), with its mtimes."""
    shutil.rmtree(c)
    shutil.copytree(backup, c, symlinks=True)


def roles_named(folder: Path, skip: Path | None = None) -> set[str]:
    """The roles named by the agent line of every brief under `folder`."""
    out = set()
    for p in folder.rglob("TASK.md"):
        if skip is not None and p == skip:
            continue
        out |= set(re.findall(r"`(?:swarmer|sciame)-([a-z0-9-]+)`", p.read_text(encoding="utf-8", errors="replace")))
    return out


def agent_of(task: Path) -> str | None:
    m = re.search(r"`(?:swarmer|sciame)-([a-z0-9-]+)`", task.read_text(encoding="utf-8", errors="replace"))
    return m.group(1) if m else None


class Swarm:
    """An installation in one language, and the convenings it drives."""

    def __init__(self, base: Path, lang: str):
        self.lang = lang
        self.it = lang == "it"
        self.base = base
        self.root = base / f"root_{lang}"
        self.root.mkdir(parents=True)
        rc, out = py(ENGINE, "install", "--from", SOURCE, "--root", self.root, "--language", lang)
        assert rc == 0, out
        self.swarm = self.root / ("sciame" if self.it else "swarmer")
        self.t = TEXTS[lang]
        self.cat = json.loads((self.swarm / "catalog.json").read_text(encoding="utf-8"))
        self.n = 0
        self.seal_keys = None

    # names, lines and texts of this installation
    def N(self, canonical: str) -> str:
        return C.localize_path(canonical, self.lang, "convene")

    def line(self, en: str, it: str) -> str:
        return it if self.it else en

    def st(self, key, **kw) -> str:
        return self.t["convene"][key].format(**kw).strip()

    def mission(self, key, **kw) -> str:
        return self.t["missions"][key].format(**kw)

    def placeholder(self) -> str:
        return C.CONVENE_LINES["to_fill_in"][self.lang]

    def run(self, *args, **kw):
        """convene.py with the canonical names (en) or with the Italian aliases (it)."""
        args = [str(a) for a in args]
        if self.it:
            cmds, opts = self.t["commands"], self.t["options"]
            args = [(cmds.get(a) or [a])[0] if i == 0 else ((opts.get(a) or [a])[0] if a.startswith("--") else a)
                    for i, a in enumerate(args)]
        return py(self.swarm / "convene.py", *args, **kw)

    def status(self, c):
        return self.run("status", c)[1]

    def gate(self, c, phase, *extra, **kw):
        return self.run("gate", c, phase, "--notes", "x", *extra, **kw)

    def verify(self, c, phase, *extra):
        return self.run("gate", c, phase, "--notes", "x", "--verify", *extra)

    def gate_ok(self, c, phase, *extra):
        rc, out = self.gate(c, phase, *extra)
        assert rc == 0, f"gate {phase}: {out}"

    def gate_file(self, c: Path, label: str) -> Path:
        return c / f"GATE_{label.replace('/', '_')}.json"

    def gate_c(self, c: Path, label: str) -> dict:
        p = self.gate_file(c, label)
        if not p.is_file():
            return {}
        return C.to_canonical(json.loads(p.read_text(encoding="utf-8")), C.CONVENE_KEYS["gate"])

    def manifest(self, c: Path) -> dict:
        return C.to_canonical(json.loads((c / self.N("MANIFEST.json")).read_text(encoding="utf-8")),
                              C.MANIFEST_SCHEMA)

    def set_rules(self, c: Path, rules: int) -> None:
        p = c / self.N("MANIFEST.json")
        m = json.loads(p.read_text(encoding="utf-8"))
        key = "regole_cancelli" if self.it else "gate_rules"
        assert m.get(key) == 3, f"a new convening is born with the rules 3: {m.get(key)}"
        if rules == 3:
            return
        if rules == 1:
            m.pop(key)
        else:
            m[key] = rules
        p.write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        # a convening born before 5.3 has no brief of the sentinel of f2
        shutil.rmtree(c / "f2" / self.N("00-sentinel"), ignore_errors=True)

    # --- the seals, with the times the test chooses (the format is the engine's own, read from a real seal) ---
    def _keys(self, c: Path, p: Path) -> dict:
        if self.seal_keys is None:
            rc, out = self.run("seal", c, p)
            assert rc == 0, out
            sp = c / self.N("SEALS.jsonl")
            lines = sp.read_text(encoding="utf-8").splitlines()
            row = json.loads(lines[-1])
            sp.write_text("".join(x + "\n" for x in lines[:-1]), encoding="utf-8")
            k = {}
            for key, v in row.items():
                if isinstance(v, str) and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d", v):
                    k["time"] = key
                elif isinstance(v, str) and v == str(p.resolve()):
                    k["file"] = key
                elif isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v):
                    k["sha256"] = key
                elif isinstance(v, int):
                    k["bytes"] = key
            assert set(k) == {"time", "file", "sha256", "bytes"}, row
            self.seal_keys = (k, list(row))
        return self.seal_keys

    def seal(self, c: Path, p: Path, t: float) -> None:
        """A seal of `p` as it is now, at the time `t`, appended to SEALS.jsonl (SIGILLI.jsonl)."""
        k, order = self._keys(c, p)
        data = p.read_bytes()
        vals = {"time": iso(t), "file": str(p.resolve()), "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data)}
        row = {key: vals[canon] for key in order for canon, kk in k.items() if kk == key}
        with open(c / self.N("SEALS.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    def seals(self, c: Path, plan) -> None:
        """SEALS.jsonl made again from scratch: plan is [(path, time)], in order."""
        sp = c / self.N("SEALS.jsonl")
        f2 = str(c / "f2") + os.sep
        keep = [x for x in sp.read_text(encoding="utf-8").splitlines()
                if any(isinstance(v, str) and v.startswith(f2) for v in json.loads(x).values())] if sp.exists() else []
        sp.write_text("".join(x + "\n" for x in keep), encoding="utf-8")
        for p, t in plan:
            self.seal(c, p, t)

    # --- a classic convening, written by hand up to G2 ---
    def prepare(self, strategy="classic", profile="data", question="q", seed=3, extra=()):
        self.n += 1
        dest = self.root / f"conv{self.n}"
        rc, out = self.run("prepare", "--name", "k", "--strategy", strategy, "--profile", profile, "--question",
                           question, "--seed", seed, "--dest", dest, *extra)
        assert rc == 0, out
        c = next(p for p in dest.iterdir() if not p.name.startswith("."))
        return c, dest

    def fill_contract(self, c: Path) -> None:
        p = c / self.N("CONTRACT.md")
        p.write_text(p.read_text(encoding="utf-8").replace(self.placeholder(), "filled"), encoding="utf-8")

    def classic(self, rules=3, profile="data", question="q", seed=3, triage=("H-001", "H-002", "H-003"),
                upto="f2", f2_sentinel=True) -> Path:
        c, dest = self.prepare("classic", profile, question, seed)
        self.set_rules(c, rules)
        self.fill_contract(c)
        self.gate_ok(c, "f0")
        lanes = next(p for p in dest.iterdir() if p.name.startswith("."))
        mp = json.loads(next(lanes.glob("*.json")).read_text(encoding="utf-8"))
        for role, v in mp.items():
            folder, canary = v.get("folder") or v.get("cartella"), v.get("canary") or v.get("canarino")
            Path(folder, self.N("DELIVERABLE.md")).write_text(
                f"{C.CONVENE_LINES['canary'][self.lang]} {canary}\nDONE\nidea of {role}\n", encoding="utf-8")
        assert self.run("snapshot", c)[0] == 0
        self.gate_ok(c, "f1")
        if upto == "f1":
            return c
        f2 = c / "f2"
        (f2 / self.N("01-translation") / self.N("CARDS.md")).write_text("cards\n", encoding="utf-8")
        triage_p = f2 / self.N("03-triage") / self.N("TRIAGE.md")
        triage_p.write_text("".join(f"{h} TEST\n" for h in triage), encoding="utf-8")
        assert self.run("seal", c, triage_p)[0] == 0
        sig = f2 / self.N("02-signatures") / "logico.md"
        sig.write_text("faithful\n", encoding="utf-8")
        os.utime(sig, (1, 1))
        (f2 / self.N("04-tournament") / self.N("TOURNAMENT.md")).write_text("ok\n", encoding="utf-8")
        (f2 / self.N("05-selection") / self.N("SELECTION.md")).write_text(
            " ".join(triage) + f"\n{C.CONVENE_LINES['countersign'][self.lang]}\n", encoding="utf-8")
        if rules >= 3 and f2_sentinel and (f2 / self.N("00-sentinel") / "TASK.md").is_file():
            self.sentinel(c, phase="f2")
        return c

    def decides(self) -> str:
        return self.line("decides: yes", "decide: sì")

    def f3(self, c: Path, h: str, gate=True):
        """f3 of `h` as the briefs ask: every role writes its output and a PREDICTIONS.md with the line «decides»."""
        b = c / "f3" / h
        for d, name in (("01-", "SOLUTION.md"), ("02-", "VERIFICATION.md"), ("03-", "MEASUREMENT_PLAN.md"),
                        ("04-", "ATTACK.md")):
            x = next(b.glob(d + "*"))
            (x / self.N(name)).write_text(f"{name}\n", encoding="utf-8")
            (x / self.N("PREDICTIONS.md")).write_text(f"threshold 1\n{self.decides()}\n", encoding="utf-8")
        if gate:
            self.gate_ok(c, f"f3/{h}")

    def dossier(self, c: Path, h: str, p: Path | None = None, extra=""):
        p = p or c / "f3" / h / f"{h}.md"
        p.write_text(f"# {h}\n\n- ID: {h}\n- Short title: t\n- Results:\n  - r1\n  - r2\n{extra}", encoding="utf-8")

    def verdict(self, correctness: str) -> str:
        return self.line(f"Correctness: {correctness}", f"Correttezza: {CORRECTNESS_IT[correctness]}") + "\n"

    def f4(self, c: Path, h: str, correctness="refuted", audit=True, folder: Path | None = None,
           dossier: Path | None = None) -> dict[str, Path]:
        """The deliverable of every briefed role folder of a round of f4, the arbiter's verdict, the dossier."""
        b = folder or c / "f4" / h
        out = {}
        for d in sorted(b.iterdir()):
            if not d.is_dir() or not re.match(r"\d\d-", d.name) or (d.name.startswith("08-") and not audit):
                continue
            name = NAMES.get(d.name[:2], "MEASUREMENTS.md")
            (d / self.N(name)).write_text(self.verdict(correctness) if name == "VERDICT.md" else "done\n",
                                          encoding="utf-8")
            out[d.name[:2]] = d / self.N(name)
        self.dossier(c, h, dossier)
        return out

    def f4_r3(self, c: Path, h: str, correctness="refuted", audit=True, folder=None, dossier=None, t=None):
        """f4 under the rules 3: the outputs, with COUNTERCHECKS, DEFECTS and REVISION sealed in that order."""
        t = T0 if t is None else t
        out = self.f4(c, h, correctness, audit, folder, dossier)
        for i, k in enumerate(("01", "02", "00")):
            self.seal(c, out[k], t + 10 * (i + 1))
        return out

    def f5(self, c: Path, k: int = 1) -> Path:
        return c / ("f5" if k == 1 else f"f5_{k}")

    def sentinel(self, c: Path, k: int = 1, phase: str | None = None) -> Path:
        d = (c / phase if phase else self.f5(c, k)) / self.N("00-sentinel")
        d.mkdir(parents=True, exist_ok=True)
        p = d / self.N("SENTINEL.md")
        p.write_text("checked\n", encoding="utf-8")
        return p

    def closure(self, c: Path, closed=True, extra="", k: int = 1) -> Path:
        line = (self.line("Outcome: closed", "Esito: chiuso") if closed else
                self.line("Outcome: not closed", "Esito: non chiuso"))
        p = self.f5(c, k) / self.N("CLOSURE.md")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"{line}\n{extra}", encoding="utf-8")
        return p

    def declared_missing(self) -> str:
        return self.line("Declared missing: sentinel: no free role\n",
                         "Dichiarato mancante: sentinella: nessun ruolo libero\n")


def role_dir(b: Path, prefix: str) -> Path:
    return next(d for d in sorted(b.iterdir()) if d.is_dir() and d.name.startswith(prefix))


# ------------------------------------------------------------------------------------------------------------------
# E1 (ENG-19, COORD-1) and E7 (ENG-21, COORD-2): the order of f4 from the seal times
# ------------------------------------------------------------------------------------------------------------------

def f4_case(s: Swarm, c: Path, b: Path):
    """The pieces of a round of f4 under the rules 3, with the outputs written but no seal."""
    s.f3(c, "H-001")
    out = s.f4(c, "H-001", correctness="refuted")
    P = s.N("PREDICTIONS.md")
    p01 = role_dir(b, "01-") / P
    p01.write_text("before the counterchecks: threshold 1\n", encoding="utf-8")
    return out, p01, role_dir(b, "02-") / P, role_dir(b, "00-") / P


def e1(s: Swarm, base: Path):
    L = f"E1 [{s.lang}]"
    c = s.classic(rules=3)
    s.gate_ok(c, "f2")
    assert s.run("select", c, "H-001")[0] == 0
    b = c / "f4" / "H-001"
    # COORD-1: the f4 briefs name the category of each role's predictions
    cc, dd = s.N("COUNTERCHECKS.md"), s.N("DEFECTS.md")
    t01 = (role_dir(b, "01-") / "TASK.md").read_text(encoding="utf-8")
    t02 = (role_dir(b, "02-") / "TASK.md").read_text(encoding="utf-8")
    t00 = (role_dir(b, "00-") / "TASK.md").read_text(encoding="utf-8")
    check(f"{L}: the counterchecks' brief says its predictions come before {cc} (rules 3)",
          s.mission("predictions_before", output=cc) in t01, t01[-900:])
    check(f"{L}: the debugger's brief names the post-countercheck category, against {dd}",
          s.mission("predictions_after", output=dd) in t02, t02[-900:])
    check(f"{L}: the owner's brief names the post-countercheck category, against {s.N('REVISION.md')}",
          s.mission("predictions_after", output=s.N("REVISION.md")) in t00, t00[-900:])
    out, p01, pdbg, pown = f4_case(s, c, b)
    CC, DEF, REV = out["01"], out["02"], out["00"]
    base_plan = [(p01, T0 + 1), (CC, T0 + 10), (DEF, T0 + 20), (REV, T0 + 30)]

    def case(name, plan, want_ok, needle=None, files_=(), after=None):
        for p in (pdbg, pown):
            if p.exists() and p not in files_:
                p.unlink()
        for p in files_:
            p.write_text("a prediction: threshold 1\n", encoding="utf-8")
        s.seals(c, plan)
        if after:
            after()
        rc, o = s.verify(c, "f4/H-001")
        ok = rc == 0 if want_ok else (rc == 1 and (needle is None or needle in o))
        check(f"{L}: {name}", ok, o)

    case("the counterchecks' prediction sealed before COUNTERCHECKS, the outputs in order: G4 holds", base_plan, True)
    case("a debugger prediction sealed after COUNTERCHECKS and before its DEFECTS.md passes G4",
         base_plan + [(pdbg, T0 + 15)], True, files_=(pdbg,))
    case("a debugger prediction sealed after its DEFECTS.md fails G4",
         base_plan + [(pdbg, T0 + 25)], False, pdbg.parent.name, files_=(pdbg,))
    case("a debugger prediction sealed in the same second as its DEFECTS.md fails G4 (no order shown)",
         base_plan + [(pdbg, T0 + 20)], False, pdbg.parent.name, files_=(pdbg,))
    case("an owner prediction sealed after its own REVISION.md fails G4 (5.2 passed it)",
         base_plan + [(pown, T0 + 35)], False, pown.parent.name, files_=(pown,))
    case("an owner prediction sealed before its own REVISION.md passes G4",
         base_plan + [(pown, T0 + 25)], True, files_=(pown,))
    case("an unsealed post-countercheck prediction fails G4", base_plan, False, pdbg.parent.name, files_=(pdbg,))
    late = [(CC, T0 + 10), (p01, T0 + 12), (DEF, T0 + 20), (REV, T0 + 30)]
    future = time.time() + 86400
    case("a late seal of the counterchecks' prediction followed by a touch of COUNTERCHECKS.md stays refused",
         late, False, p01.parent.name, after=lambda: os.utime(CC, (future, future)))

    def append_cc():
        CC.write_text(CC.read_text(encoding="utf-8") + "more\n", encoding="utf-8")
        s.seal(c, CC, T0 + 40)
    case("a late seal followed by an append to COUNTERCHECKS.md and a new seal of it stays refused",
         late, False, p01.parent.name, after=append_cc)
    CC.write_text("done\n", encoding="utf-8")

    def append_block():
        pdbg.write_text(pdbg.read_text(encoding="utf-8") + "a second block: threshold 2\n", encoding="utf-8")
    case("a prediction block appended after the seal without its own seal is refused",
         base_plan + [(pdbg, T0 + 15)], False, pdbg.parent.name, files_=(pdbg,), after=append_block)

    def append_sealed(t):
        def f():
            append_block()
            s.seal(c, pdbg, t)
        return f
    case("the appended block with its own seal before DEFECTS.md passes",
         base_plan + [(pdbg, T0 + 15)], True, files_=(pdbg,), after=append_sealed(T0 + 17))
    case("the appended block sealed only after DEFECTS.md is refused",
         base_plan + [(pdbg, T0 + 15)], False, pdbg.parent.name, files_=(pdbg,), after=append_sealed(T0 + 22))
    pdbg.write_text("a prediction: threshold 1\n", encoding="utf-8")

    def mtimes():
        os.utime(pdbg, (future, future))
        for p in (CC, DEF, REV):
            os.utime(p, (T0 - 5000, T0 - 5000))
    case("the order is read from the seals, not the mtimes: a debugger prediction touched after DEFECTS.md, the "
         "outputs dated back, still passes", base_plan + [(pdbg, T0 + 15)], True, files_=(pdbg,), after=mtimes)
    # the rules 2 keep their order: every PREDICTIONS.md of f4 sealed before the mtime of COUNTERCHECKS.md
    c2 = s.classic(rules=2)
    s.gate_ok(c2, "f2")
    assert s.run("select", c2, "H-001")[0] == 0
    b2 = c2 / "f4" / "H-001"
    t02 = (role_dir(b2, "02-") / "TASK.md").read_text(encoding="utf-8")
    check(f"{L}: under the rules 2 the debugger's brief asks for no PREDICTIONS.md it could not seal (COORD-1)",
          s.mission("predictions_after_old", rules=2, output=dd) in t02
          and s.mission("predictions_after", output=dd) not in t02, t02[-900:])
    out2, p01b, pdbgb, _ = f4_case(s, c2, b2)
    pdbgb.write_text("a prediction\n", encoding="utf-8")
    assert s.run("seal", c2, p01b, pdbgb)[0] == 0
    os.utime(out2["01"], (T0, T0))
    rc, o = s.verify(c2, "f4/H-001")
    check(f"{L}: rules 2 unchanged: a prediction sealed after the mtime of COUNTERCHECKS.md is refused",
          rc == 1 and "sealed after the counterchecks" in o, o)
    os.utime(out2["01"], (future, future))
    rc, o = s.verify(c2, "f4/H-001")
    check(f"{L}: rules 2 unchanged: sealed before that mtime it passes, as in 5.2", rc == 0, o)


def e7(s: Swarm, base: Path):
    L = f"E7 [{s.lang}]"
    c = s.classic(rules=3)
    s.gate_ok(c, "f2")
    assert s.run("select", c, "H-001")[0] == 0
    b = c / "f4" / "H-001"
    t00 = (role_dir(b, "00-") / "TASK.md").read_text(encoding="utf-8")
    check(f"{L}: the owner's brief says the revision comes after COUNTERCHECKS and DEFECTS (COORD-2)",
          s.mission("revision_order") in t00, t00[-900:])
    out, p01, _pdbg, _pown = f4_case(s, c, b)
    CC, DEF, REV = out["01"], out["02"], out["00"]
    rev = REV.parent.name
    for name, plan, want_ok in (
            ("a REVISION.md sealed before COUNTERCHECKS.md is refused",
             [(p01, T0 + 1), (REV, T0 + 5), (CC, T0 + 10), (DEF, T0 + 20)], False),
            ("a REVISION.md sealed after COUNTERCHECKS.md but before DEFECTS.md is refused",
             [(p01, T0 + 1), (CC, T0 + 10), (REV, T0 + 15), (DEF, T0 + 20)], False),
            ("a REVISION.md sealed in the same second as DEFECTS.md is refused",
             [(p01, T0 + 1), (CC, T0 + 10), (DEF, T0 + 20), (REV, T0 + 20)], False),
            ("a REVISION.md never sealed is refused", [(p01, T0 + 1), (CC, T0 + 10), (DEF, T0 + 20)], False),
            ("a REVISION.md sealed after both passes", [(p01, T0 + 1), (CC, T0 + 10), (DEF, T0 + 20), (REV, T0 + 30)],
             True)):
        s.seals(c, plan)
        rc, o = s.verify(c, "f4/H-001")
        check(f"{L}: {name}", rc == 0 if want_ok else (rc == 1 and rev in o), o)
    os.utime(REV, (T0 - 9000, T0 - 9000))
    rc, o = s.verify(c, "f4/H-001")
    check(f"{L}: a REVISION.md older by mtime but sealed after both still passes (the seals decide)", rc == 0, o)
    c2 = s.classic(rules=2)
    s.gate_ok(c2, "f2")
    assert s.run("select", c2, "H-001")[0] == 0
    s.f3(c2, "H-001")
    out2 = s.f4(c2, "H-001")
    os.utime(out2["00"], (T0, T0))
    rc, o = s.verify(c2, "f4/H-001")
    check(f"{L}: rules 2 unchanged: a REVISION.md older than the counterchecks still passes G4, as in 5.2", rc == 0, o)


# ------------------------------------------------------------------------------------------------------------------
# E2 (ENG-13): a name that is not UTF-8, and a write that fails
# ------------------------------------------------------------------------------------------------------------------

def e2(s: Swarm, base: Path):
    L = f"E2 [{s.lang}]"
    d = base / f"e2_inproc_{s.lang}"
    d.mkdir()
    with open(os.path.join(os.fsencode(d), NOT_UTF8), "wb") as f:
        f.write(b"x\n")
    (d / "plain.txt").write_text("y\n", encoding="utf-8")
    odd = os.fsdecode(os.path.join(os.fsencode(d), NOT_UTF8))
    try:
        t = V._tree(d, set())
        check(f"{L}: _tree succeeds on a non-UTF-8 name", t.startswith("tree:"), t)
    except Exception as e:  # noqa: BLE001
        check(f"{L}: _tree succeeds on a non-UTF-8 name", False, repr(e))
    fp = {}
    try:
        V._bind(d, fp, set())
        check(f"{L}: _bind succeeds and binds the non-UTF-8 name", odd in fp, sorted(fp))
    except Exception as e:  # noqa: BLE001
        check(f"{L}: _bind succeeds and binds the non-UTF-8 name", False, repr(e))
    gp = d / "GATE_x.json"
    try:
        V.Convening(d, s.lang).write_json(gp, {"phase": "f0", "time": "t", "notes": "n", "not_delivered": [],
                                              "fingerprints": fp}, "gate")
        back = C.to_canonical(json.loads(gp.read_bytes().decode("utf-8")), C.CONVENE_KEYS["gate"])
        check(f"{L}: write_json writes UTF-8 JSON that gives the non-UTF-8 name back", back["fingerprints"] == fp,
              back)
    except Exception as e:  # noqa: BLE001
        check(f"{L}: write_json writes UTF-8 JSON that gives the non-UTF-8 name back", False, repr(e))
    for rules in (2, 3):
        c = s.classic(rules=rules)
        s.gate_ok(c, "f2")
        assert s.run("select", c, "H-001")[0] == 0
        s.f3(c, "H-001")
        (s.f4_r3 if rules == 3 else s.f4)(c, "H-001")
        x = role_dir(c / "f4" / "H-001", "03-")
        work = x / s.N("work")
        work.mkdir()
        bad = []
        for folder in (x, work):
            q = os.path.join(os.fsencode(folder), NOT_UTF8)
            with open(q, "wb") as f:
                f.write(b"raw\n")
            bad.append(q)
        rc, out = s.gate(c, "f4/H-001")
        check(f"{L} rules {rules}: G4 approved with a non-UTF-8 name in a role folder and in its workspace", rc == 0,
              out)
        gp = s.gate_file(c, "f4/H-001")
        try:
            g = C.to_canonical(json.loads(gp.read_bytes().decode("utf-8")), C.CONVENE_KEYS["gate"])
        except Exception as e:  # noqa: BLE001
            g = {"error": repr(e)}
        check(f"{L} rules {rules}: the gate file is UTF-8 JSON and binds the file by its own name",
              os.fsdecode(bad[0]) in g.get("fingerprints", {}) and str(work) + "/" in g.get("fingerprints", {}), g)
        check(f"{L} rules {rules}: status: G4 approved", s.st("status_approved", phase="f4/H-001") in s.status(c))
        for q, what in zip(bad, ("the file", "the workspace")):
            with open(q, "ab") as f:
                f.write(b"!")
            out = s.status(c)
            check(f"{L} rules {rules}: one byte more in {what} with the non-UTF-8 name invalidates G4",
                  s.st("status_invalid", phase="f4/H-001") in out, out)
            with open(q, "wb") as f:
                f.write(b"raw\n")
        check(f"{L} rules {rules}: restored, G4 holds again", s.st("status_approved", phase="f4/H-001") in s.status(c))
        # a failed approval: the write of the gate file is cut at 64 bytes (RLIMIT_FSIZE)
        old = gp.read_bytes()
        rc, out = s.gate(c, "f4/H-001", fsize=64)
        stray = [p.name for p in c.iterdir() if p.name.startswith(".") or p.name.endswith(".tmp")]
        check(f"{L} rules {rules}: a gate whose write fails exits 1 and leaves the old gate file byte for byte",
              rc == 1 and gp.read_bytes() == old and not stray and "Traceback" not in out, (rc, out, stray))
    c, _dest = s.prepare()
    s.fill_contract(c)
    rc, out = s.gate(c, "f0", fsize=64)
    left = [p.name for p in c.iterdir() if "GATE_f0" in p.name]
    check(f"{L}: a first gate whose write fails leaves no gate file (no 0-byte GATE_f0.json) and no temporary file",
          rc == 1 and left == [], (rc, out, left))
    check(f"{L}: after it status works and shows f0 to approve", s.st("status_pending", phase="f0") in s.status(c))


# ------------------------------------------------------------------------------------------------------------------
# E3 (ENG-17): the sentinels of f2, f3 and f4
# ------------------------------------------------------------------------------------------------------------------

def e3(s: Swarm, base: Path):
    L = f"E3 [{s.lang}]"
    SD, SN = s.N("00-sentinel"), s.N("SENTINEL.md")
    c = s.classic(rules=3, f2_sentinel=False)
    t2 = c / "f2" / SD / "TASK.md"
    check(f"{L}: prepare briefs the sentinel of f2 ({t2.relative_to(c)})", t2.is_file())
    if not t2.is_file():
        return
    rc, out = s.verify(c, "f2")
    check(f"{L}: under the rules 3 G2 wants the f2 sentinel's deliverable", rc == 1 and SN in out, out)
    r2 = agent_of(t2)
    rc, out = s.verify(c, "f2", "--not-delivered", r2)
    check(f"{L}: G2 with --not-delivered of the f2 sentinel", rc == 0, out)
    s.sentinel(c, phase="f2")
    s.gate_ok(c, "f2")
    rc, out = s.run("select", c, "H-001", "H-002")
    t3, t4, t5 = c / "f3" / SD / "TASK.md", c / "f4" / SD / "TASK.md", c / "f5" / SD / "TASK.md"
    check(f"{L}: select of two branches briefs the sentinels of f3, f4 and the closure",
          rc == 0 and t3.is_file() and t4.is_file() and t5.is_file(), out)
    m = s.manifest(c)
    prof = s.cat["profiles"][m["profile"]]
    convened = set(m["f1"]) | {v.get("role") for v in m["f1"].values()}
    convened |= {r for k in ("A", "B", "translates", "f3", "f4") for r in prof.get(k, [])}
    for h in ("H-001", "H-002"):
        for f in ("f3", "f4"):
            convened |= {re.sub(r"^\d+-", "", x.name) for x in (c / f / h).iterdir() if x.is_dir()}
    for t in (t2, t3, t4, t5):
        if not t.is_file():
            continue
        r = agent_of(t)
        others = roles_named(c, skip=t)
        check(f"{L}: the sentinel {r} of {t.parent.parent.name} is a role no other brief names and the profile does "
              f"not convene", r and r not in convened and r not in others, (r, sorted(others & {r})))
    s.f3(c, "H-001")
    s.f3(c, "H-002", gate=False)
    rc, out = s.gate(c, "f3/H-002")
    check(f"{L}: G3 is approved while the f3 sentinel has not delivered (a warning, G5 requires it)", rc == 0, out)
    for h, v in (("H-001", "proven"), ("H-002", "refuted")):
        s.f4_r3(c, h, correctness=v)
        s.gate_ok(c, f"f4/{h}")
    s.closure(c, closed=True)
    s.sentinel(c)
    rc, out = s.verify(c, "f5")
    check(f"{L}: G5 refused without the deliverables of the f3 and f4 sentinels",
          rc == 1 and f"f3/{SD}" in out and f"f4/{SD}" in out, out)
    p3 = s.sentinel(c, phase="f3")
    rc, out = s.verify(c, "f5")
    check(f"{L}: G5 still refused with the f3 sentinel alone", rc == 1 and f"f4/{SD}" in out and f"f3/{SD}" not in out,
          out)
    p4 = s.sentinel(c, phase="f4")
    out = s.status(c)
    check(f"{L}: the f4 sentinel delivering after the G4s invalidates no G4",
          s.st("status_approved", phase="f4/H-001") in out and s.st("status_approved", phase="f4/H-002") in out, out)
    try:
        conv = V.Convening.load(c)
        ok = V.sentinel_found(conv, phase="f3") and V.sentinel_found(conv, phase="f4")
        check(f"{L}: sentinel_found accepts the sentinels of f3 and f4", ok)
    except Exception as e:  # noqa: BLE001
        check(f"{L}: sentinel_found accepts the sentinels of f3 and f4", False, repr(e))
    rc, out = s.gate(c, "f5")
    check(f"{L}: with the sentinels of f3, f4 and the closure, G5 is approved", rc == 0, out)
    old = p3.read_bytes()
    p3.write_bytes(old + b"!")
    out = s.status(c)
    check(f"{L}: the first G5 binds the f3 sentinel's deliverable", s.st("status_invalid", phase="f5") in out, out)
    p3.write_bytes(old)
    shutil.rmtree(p3.parent)
    shutil.rmtree(p4.parent)
    shutil.rmtree(s.f5(c) / SD)
    s.closure(c, closed=True, extra=s.declared_missing())
    rc, out = s.verify(c, "f5")
    check(f"{L}: «Declared missing: sentinel» in the closure stands for the missing sentinels", rc == 0, out)


# ------------------------------------------------------------------------------------------------------------------
# E4 (ENG-18, ENG-22): repin opens round 2, and a second select is refused
# ------------------------------------------------------------------------------------------------------------------

def e4(s: Swarm, base: Path):
    L = f"E4 [{s.lang}]"
    P = s.N("PREDICTIONS.md")
    c = s.classic(rules=2)
    s.gate_ok(c, "f2")
    assert s.run("select", c, "H-001")[0] == 0
    s.f3(c, "H-001")
    dossier1 = c / "f3" / "H-001" / "H-001.md"
    before = files(c)
    for args in (("H-002",), ("H-001",), ("H-002", "--radical", "H-003")):
        rc, out = s.run("select", c, *args)
        check(f"{L}: a second select ({' '.join(args)}) is refused and writes nothing", rc == 1 and files(c) == before,
              (out, changes(before, files(c))))
    # round 1, approved under the rules 2 with predictions sealed after their own outputs (as propolis-design's)
    b = c / "f4" / "H-001"
    out1 = s.f4(c, "H-001", correctness="refuted")
    pown, pdbg = role_dir(b, "00-") / P, role_dir(b, "02-") / P
    pown.write_text("owner: threshold 1\n", encoding="utf-8")
    pdbg.write_text("debugger: threshold 1\n", encoding="utf-8")
    s.seals(c, [(out1["01"], T0 + 10), (out1["02"], T0 + 20), (out1["00"], T0 + 30), (pdbg, T0 + 25),
                (pown, T0 + 40)])
    rc, out = s.gate(c, "f4/H-001")
    check(f"{L}: round 1's G4 approved under the rules 2 with two late predictions", rc == 0, out)
    snap = files(c)
    rc, out = s.run("repin", c, "H-001")
    r2 = c / "f4_2" / "H-001"
    after = files(c)
    changed = [k for k in snap if after.get(k) != snap[k]]
    added = [k for k in after if k not in snap]
    check(f"{L}: repin opens round 2 in f4_2/H-001/", rc == 0 and r2.is_dir(), out)
    roles1 = sorted(d.name for d in b.iterdir() if d.is_dir())
    roles2 = sorted(d.name for d in r2.iterdir() if d.is_dir() and (d / "TASK.md").is_file()) if r2.is_dir() else []
    check(f"{L}: round 2 has a brief for every role folder of round 1 and a dossier of its own",
          roles1 == roles2 and (r2 / "H-001.md").is_file(), (roles1, roles2))
    f5brief = lambda k: k.startswith("f5" + os.sep) and k.endswith("TASK.md")  # noqa: E731
    check(f"{L}: repin leaves every file of round 1, of f3, the seals and the gates byte-identical",
          all(f5brief(k) for k in changed), changed)
    check(f"{L}: what repin adds is in f4_2/ (or a brief of the closure)",
          all(k.startswith("f4_2" + os.sep) or f5brief(k) for k in added) and added, added)
    check(f"{L}: f3/H-001/H-001.md is never touched", dossier1.read_bytes() == snap[str(dossier1.relative_to(c))])
    t9 = (role_dir(r2, "09-") / "TASK.md").read_text(encoding="utf-8") if r2.is_dir() else ""
    t2 = (role_dir(r2, "02-") / "TASK.md").read_text(encoding="utf-8") if r2.is_dir() else ""
    check(f"{L}: the round-2 briefs read round 1 (f4/H-001) and write in f4_2/H-001",
          f"`{b}`" in t9 and str(r2) in t9, t9[:1500])
    check(f"{L}: the round-2 debugger's brief names the post-countercheck category of the rules 3",
          s.mission("predictions_after", output=s.N("DEFECTS.md")) in t2, t2[-900:])
    out = s.status(c)
    check(f"{L}: status: G3 and round 1's G4 still approved, round 2 to approve",
          s.st("status_approved", phase="f3/H-001") in out and s.st("status_approved", phase="f4/H-001") in out
          and s.st("status_pending", phase="f4_2/H-001") in out, out)
    seals_before = (c / s.N("SEALS.jsonl")).read_bytes()
    out2 = s.f4(c, "H-001", correctness="proven", folder=r2, dossier=r2 / "H-001.md")
    p2dbg, p2own = role_dir(r2, "02-") / P, role_dir(r2, "00-") / P
    p2dbg.write_text("round 2 debugger: threshold 1\n", encoding="utf-8")
    for p, t in ((out2["01"], T0 + 110), (p2dbg, T0 + 115), (out2["02"], T0 + 120), (out2["00"], T0 + 130)):
        s.seal(c, p, t)
    rc, o = s.verify(c, "f4/H-001")
    g = s.gate_c(c, "f4_2/H-001")
    check(f"{L}: round 2's G4 does not run under the rules 2 of the convening", rc == 1 or g.get("rules") == 3, o)
    rc, o = s.verify(c, "f4/H-001", "--rules", "3")
    check(f"{L}: with round 1's late files in place a clean round 2 passes G4 under the rules 3", rc == 0, o)
    keep = (c / s.N("SEALS.jsonl")).read_bytes()
    p2own.write_text("round 2 owner: threshold 1\n", encoding="utf-8")
    s.seal(c, p2own, T0 + 140)
    rc, o = s.verify(c, "f4/H-001", "--rules", "3")
    check(f"{L}: a round-2 prediction sealed after its own output fails", rc == 1 and p2own.parent.name in o, o)
    p2own.unlink()
    (c / s.N("SEALS.jsonl")).write_bytes(keep)
    rc, o = s.gate(c, "f4/H-001", "--rules", "3")
    g = s.gate_c(c, "f4_2/H-001")
    check(f"{L}: GATE_f4_2_H-001.json records the rules 3 and binds only round 2's files",
          rc == 0 and g.get("rules") == 3 and g["fingerprints"]
          and all(k.startswith(str(r2) + os.sep) for k in g["fingerprints"]), (o, sorted(g.get("fingerprints", {}))))
    now = files(c)
    check(f"{L}: after round 2 every round-1 file is byte-identical and SEALS.jsonl was only appended to",
          all(now.get(k) == v for k, v in snap.items() if not f5brief(k) and k != s.N("SEALS.jsonl"))
          and now[s.N("SEALS.jsonl")].startswith(seals_before) and seals_before == snap[s.N("SEALS.jsonl")],
          [k for k, v in snap.items() if now.get(k) != v])
    s.closure(c, closed=True)
    rc, o = s.verify(c, "f5")
    check(f"{L}: G5 reads the branch's latest round: «closed» on round 2's proven verdict (round 1 refuted)",
          rc == 0, o)
    out = s.status(c)
    check(f"{L}: status shows both rounds approved",
          s.st("status_approved", phase="f4/H-001") in out and s.st("status_approved", phase="f4_2/H-001") in out, out)


# ------------------------------------------------------------------------------------------------------------------
# E5 (ENG-20): the companions' f3 briefs ask for «decides»
# ------------------------------------------------------------------------------------------------------------------

def e5(s: Swarm, base: Path):
    L = f"E5 [{s.lang}]"
    yes, no = s.line("decides: yes", "decide: sì"), s.line("decides: no", "decide: no")
    for rules in (3, 2):
        c = s.classic(rules=rules)
        s.gate_ok(c, "f2")
        assert s.run("select", c, "H-001")[0] == 0
        b = c / "f3" / "H-001"
        for pre in ("01-", "02-", "03-", "04-"):
            t = (role_dir(b, pre) / "TASK.md").read_text(encoding="utf-8")
            check(f"{L} rules {rules}: the f3 brief of {role_dir(b, pre).name} asks for the line «{yes}»",
                  yes in t and no in t, t[-700:])
        s.f3(c, "H-001", gate=False)
        snap = {p: p.read_bytes() for p in b.rglob("*.md")}
        rc, out = s.gate(c, "f3/H-001")
        check(f"{L} rules {rules}: a fresh classic whose f3 roles follow their briefs passes G3", rc == 0, out)
        check(f"{L} rules {rules}: with no line appended afterwards",
              all(p.read_bytes() == v for p, v in snap.items()))
    c = s.classic(rules=3)
    s.gate_ok(c, "f2")
    assert s.run("select", c, "H-001")[0] == 0
    s.f3(c, "H-001", gate=False)
    p = role_dir(c / "f3" / "H-001", "03-") / s.N("PREDICTIONS.md")
    p.write_text("threshold 1\n", encoding="utf-8")
    rc, out = s.verify(c, "f3/H-001")
    check(f"{L}: a companion's PREDICTIONS.md without the line is still refused", rc == 1 and p.parent.name in out, out)


# ------------------------------------------------------------------------------------------------------------------
# E6 (ENG-23): the closure brief says what G5 checks
# ------------------------------------------------------------------------------------------------------------------

def e6(s: Swarm, base: Path):
    L = f"E6 [{s.lang}]"
    c = s.classic(rules=2)
    s.gate_ok(c, "f2")
    assert s.run("select", c, "H-001", "H-002", "--radical", "H-003")[0] == 0
    task = s.f5(c) / f"01-{C.ROLES['arbiter']}" / "TASK.md"
    words = s.line(("valid G4", "early closure", "radical", "never funded"),
                   ("G4 valido", "chiusura anticipata", "radicale", "mai finanziata"))

    def text():
        t = task.read_text(encoding="utf-8")
        return t.split("\n## ", 1)[-1]

    t = text()
    check(f"{L}: the closure brief states G5's rule of a non-closure (valid G4, early closure, a radical never "
          f"funded nor closed)", all(w in t for w in words), t)
    check(f"{L}: it names the open branches H-001, H-002 and the radical H-003",
          all(h in t for h in ("H-001", "H-002", "H-003")), t)
    rc, out = s.run("close-branch", c, "H-002", "--reason", "no time", "--deciding-test", "the oracle on 10 cases")
    t = text()
    check(f"{L}: after the early closure of H-002 the brief no longer names it among the open ones",
          rc == 0 and "H-002" not in t and "H-001" in t and "H-003" in t, (out, t))
    s.f3(c, "H-001")
    s.f4(c, "H-001", correctness="proven")
    s.gate_ok(c, "f4/H-001")
    s.sentinel(c)
    # as conditions does: G5 «not closed» names exactly the radical (H-001 has a valid G4, H-002 is closed early)
    s.closure(c, closed=False, extra="nothing named\n")
    rc, out = s.verify(c, "f5")
    check(f"{L}: «not closed» without naming the radical: refused, and the brief named it",
          rc == 1 and "H-003" in out and "H-003" in text(), out)
    s.closure(c, closed=False, extra="H-003 is open\n")
    rc, out = s.verify(c, "f5")
    check(f"{L}: «not closed» naming what the brief names as open: approved", rc == 0, out)


# ------------------------------------------------------------------------------------------------------------------
# E8 (ENG-14): the version, 5.3 everywhere it is stated
# ------------------------------------------------------------------------------------------------------------------

def e8(swarms: dict, base: Path):
    L = "E8"
    for lang, s in swarms.items():
        v = (s.swarm / "VERSION").read_text(encoding="utf-8").split()
        check(f"{L} [{lang}]: the installed VERSION says 5.3", v[:1] == ["5.3"], v)
        check(f"{L} [{lang}]: the catalog says 5.3", s.cat.get("version") == "5.3", s.cat.get("version"))
        rc, out = s.run("--help")
        check(f"{L} [{lang}]: convene --help says swarmer 5.3", "swarmer 5.3" in out, out[:300])
        c, _ = s.prepare()
        check(f"{L} [{lang}]: a new convening's manifest records 5.3", s.manifest(c).get("version") == "5.3",
              s.manifest(c).get("version"))
        for w in ("convene.py", "jury.py"):
            t = (s.swarm / w).read_text(encoding="utf-8")
            check(f"{L} [{lang}]: the installed wrapper {w} states no older version",
                  not re.search(r"\b5\.[0-2]\b", t), t[:300])
    plugin = json.loads((SOURCE / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    check(f"{L}: plugin.json (the Claude Code plugin and the Agensi package) is 5.3.2",
          plugin.get("version") == "5.3.2", plugin.get("version"))
    for p in sorted((SOURCE / "wrappers").glob("*.py")):
        t = p.read_text(encoding="utf-8")
        check(f"{L}: wrappers/{p.name} states no 5.0, 5.1 or 5.2", not re.search(r"\b5\.[0-2]\b", t), t[:300])
    conv = (SOURCE / "engine" / "convene.py").read_text(encoding="utf-8")
    check(f"{L}: engine/convene.py has no VERSION = \"5.0\"", not re.search(r"VERSION\s*=\s*['\"]5\.0", conv))
    for p in sorted((SOURCE / "engine").glob("*.py")):
        head = p.read_text(encoding="utf-8").split("\n", 3)[:3]
        check(f"{L}: the docstring of engine/{p.name} states no older swarmer version",
              not any(re.search(r"(swarmer|sciame)\s+5\.[0-2]\b", x) for x in head), head)
    for sh in ("swarmer.sh", "sciame.sh"):
        t = (SOURCE / sh).read_text(encoding="utf-8").split("\n", 3)[1]
        check(f"{L}: {sh} says version 5.3 in its head", "5.3" in t, t)
    for lang in ("en", "it"):
        t = (SOURCE / "docs" / lang / "README.md").read_text(encoding="utf-8").split("\n", 1)[0]
        check(f"{L}: docs/{lang}/README.md says 5.3", "5.3" in t, t)
        t = (SOURCE / "docs" / lang / "PIPELINE.md").read_text(encoding="utf-8")[:600]
        check(f"{L}: docs/{lang}/PIPELINE.md's status says 5.3", re.search(r"(Version|Versione) 5\.3", t), t)
    for name in ("CHANGELOG.md", "CHANGELOG.it.md"):
        p = SOURCE / name
        t = p.read_text(encoding="utf-8") if p.is_file() else ""
        check(f"{L}: {name} has a 5.3.2, a 5.3.1 and a 5.3.0 entry",
              all(re.search(rf"^## 5\.3\.{n}\b", t, re.M) for n in (2, 1, 0)), t[:200])
    script = SOURCE / ".github" / "scripts" / "agensi.py"
    if script.is_file() and (SOURCE / ".git").exists() and shutil.which("git"):
        out_dir = base / "agensi-pkg"
        rc, out = py(script, "--package", out_dir / "swarmer", "--api", base / "agensi-site")
        skill = out_dir / "swarmer" / "SKILL.md"
        ver = re.search(r"^version: (\S+)", skill.read_text(encoding="utf-8"), re.M) if skill.is_file() else None
        check(f"{L}: the Agensi edition's package states 5.3", rc == 0 and ver and ver.group(1).startswith("5.3"),
              (rc, out[-600:], ver and ver.group(1)))
    else:
        print(f"skip {L}: the Agensi package needs the git checkout")


# ------------------------------------------------------------------------------------------------------------------
# E9 (ENG-15): a convening-wide K# allocator that the engine reads
# ------------------------------------------------------------------------------------------------------------------

def e9(s: Swarm, base: Path):
    L = f"E9 [{s.lang}]"
    c = s.classic(rules=3)
    s.gate_ok(c, "f2")
    assert s.run("select", c, "H-001", "H-002")[0] == 0
    s.f3(c, "H-001")
    s.f3(c, "H-002")
    a = role_dir(c / "f3" / "H-001", "01-") / s.N("SOLUTION.md")
    b = role_dir(c / "f3" / "H-002", "01-") / s.N("SOLUTION.md")
    reg = c / s.N("CONTRADICTIONS.jsonl")
    rc1, o1 = s.run("contradiction", c, a, b, "--question", "is the bound tight?")
    rc2, o2 = s.run("contradiction", c, b, "--question", "does the cache hold?")
    rows = [json.loads(x) for x in reg.read_text(encoding="utf-8").splitlines()] if reg.is_file() else []
    ids = [next((v for v in r.values() if isinstance(v, str) and re.fullmatch(r"K-\d{3}", v)), None) for r in rows]
    check(f"{L}: contradiction allocates K-001 then K-002, one numbering for every branch, in {reg.name}",
          rc1 == 0 and rc2 == 0 and ids == ["K-001", "K-002"] and "K-001" in o1 and "K-002" in o2, (o1, o2, rows))
    check(f"{L}: the record keeps the binary question and the files of its sides",
          rows and "is the bound tight?" in json.dumps(rows[0], ensure_ascii=False) and str(a) in json.dumps(rows[0]),
          rows[:1])
    out = s.status(c)
    check(f"{L}: status lists the K# of the convening", "K-001" in out and "K-002" in out, out)
    for h, v in (("H-001", "proven"), ("H-002", "refuted")):
        s.f4_r3(c, h, correctness=v)
        if h == "H-002":
            vp = role_dir(c / "f4" / h, "09-") / s.N("VERDICT.md")
            vp.write_text(vp.read_text(encoding="utf-8") + "K-007 is open\n", encoding="utf-8")
            rc, out = s.gate(c, f"f4/{h}")
            check(f"{L}: G4 warns on a K# cited and never allocated", rc == 0 and "K-007" in out, out)
        else:
            s.gate_ok(c, f"f4/{h}")
    for ph in ("f3", "f4"):
        s.sentinel(c, phase=ph)
    s.sentinel(c)
    s.closure(c, closed=True, extra="K-001 resolved\n")
    rc, out = s.verify(c, "f5")
    check(f"{L}: G5 refused while an allocated K# is not named in the closure", rc == 1 and "K-002" in out, out)
    s.closure(c, closed=True, extra="K-001 resolved; K-002 open\n")
    rc, out = s.verify(c, "f5")
    check(f"{L}: G5 with every allocated K# named", rc == 0, out)
    keep = reg.read_bytes()
    for bad, what in ((keep + keep.splitlines(True)[0], "a K# written twice"), (keep + b"not a record\n",
                                                                                 "a line that is not a K# record")):
        reg.write_bytes(bad)
        rc, out = s.run("status", c)
        check(f"{L}: {what} stops status with exit 1", rc == 1 and "Traceback" not in out, out)
        rc, out = s.run("contradiction", c, a, "--question", "x?")
        check(f"{L}: {what} stops the allocator too", rc == 1 and reg.read_bytes() == bad, out)
    reg.write_bytes(keep)


# ------------------------------------------------------------------------------------------------------------------
# E10 (ENG-16): a fitness filter for a drawn sentinel, recorded in its brief
# ------------------------------------------------------------------------------------------------------------------

def fit_roles(s: Swarm, question: str) -> dict[str, list[str]]:
    """The roles with a keyword of their own, whole and in any case, in the question (computed here, not by roles)."""
    q = question.lower()
    out = {}
    for r in s.cat["roles"]:
        hit = [k for k in r.get("keywords", []) if re.search(rf"(?<!\w){re.escape(k.lower())}(?!\w)", q)]
        if hit:
            out[r["id"]] = hit
    return out


def e10(s: Swarm, base: Path):
    L = f"E10 [{s.lang}]"
    by = {r["id"]: r for r in s.cat["roles"]}
    k1, k2 = by["prestazioni"]["keywords"][0], by["economista"]["keywords"][0]
    question = f"{k1} / {k2} ?"
    fit = fit_roles(s, question)
    c, _ = s.prepare(question=question, seed=11)
    task = c / "f2" / s.N("00-sentinel") / "TASK.md"
    if not task.is_file():
        check(f"{L}: the f2 sentinel is briefed under the rules 3", False)
        return
    role = agent_of(task)
    m = s.manifest(c)
    prof = s.cat["profiles"][m["profile"]]
    convened = {r for k in ("A", "B", "translates", "f3", "f4") for r in prof.get(k, [])} | set(m["f1"])
    free_fit = [r for r in fit if r not in convened and r not in roles_named(c, skip=task)]
    pro = [r for r in free_fit if by[r].get("type", "professional") == "professional"]
    what = task.read_text(encoding="utf-8").split("\n## ", 1)[-1]
    check(f"{L}: the sentinel is drawn among the free roles fit for the question, professionals first",
          role in (pro or free_fit), (role, fit, free_fit))
    check(f"{L}: the brief records the draw: the seed and the drawn role's keywords",
          role in fit and "11" in what and all(k.lower() in what.lower() for k in fit[role]), what)
    c2, _ = s.prepare(question=question, seed=11)
    check(f"{L}: the draw is reproducible from the seed",
          agent_of(c2 / "f2" / s.N("00-sentinel") / "TASK.md") == role)
    c3, _ = s.prepare(question="q", seed=12)
    t3 = c3 / "f2" / s.N("00-sentinel") / "TASK.md"
    w3 = t3.read_text(encoding="utf-8").split("\n## ", 1)[-1] if t3.is_file() else ""
    prefix = s.t["missions"]["sentinel_draw_unfit"].split("{n}")[0].format(seed=12)
    check(f"{L}: with no fit role the brief records a draw among all the free roles", prefix in w3, w3)
    r3 = agent_of(t3) if t3.is_file() else None
    check(f"{L}: and the drawn role is free", r3 and r3 not in convened and r3 not in roles_named(c3, skip=t3), r3)


# ------------------------------------------------------------------------------------------------------------------
# E11 (ENG-12): a canary per arm in a fan-out race, checked by G1
# ------------------------------------------------------------------------------------------------------------------

def e11(s: Swarm, base: Path):
    L = f"E11 [{s.lang}]"
    token = C.CONVENE_LINES["canary_token"][s.lang]
    word = C.CONVENE_LINES["canary"][s.lang]
    c, _ = s.prepare("fan-out", extra=("--n", 3, "--form", "race", "--rule", "first"))
    s.fill_contract(c)
    s.gate_ok(c, "f0")
    m = s.manifest(c)
    arms = [Path(v["folder"]) for v in m["f1"].values()]
    canaries = []
    for a in arms:
        found = re.findall(re.escape(token) + r"[0-9a-f]{16}", (a / "TASK.md").read_text(encoding="utf-8"))
        canaries.append(found[0] if found else None)
    check(f"{L}: every arm of the race has a canary of its own in its brief",
          all(canaries) and len(set(canaries)) == len(arms) == 3, canaries)
    mp = m.get("map")
    lane_map = C.to_canonical(json.loads(Path(mp).read_text(encoding="utf-8")), C.CONVENE_KEYS["map"]) if mp else {}
    check(f"{L}: the lane map records each arm's canary",
          sorted(v.get("canary") for v in lane_map.values()) == sorted(x for x in canaries if x), lane_map)
    D = s.N("DELIVERABLE.md")

    def write(texts):
        for a, t in zip(arms, texts):
            (a / D).write_text(t, encoding="utf-8")
    write(["DONE\nmy answer\n"] * 3)
    rc, out = s.verify(c, "f1")
    check(f"{L}: G1 refuses deliverables without their canary", rc == 1, out)
    write([f"{word} {k}\nDONE\nmy answer\n" for k in canaries])
    shot = c / s.N("SNAPSHOT.json")
    rc, out = s.verify(c, "f1")
    check(f"{L}: G1 wants the snapshot of the reads in a race", rc == 1 and not shot.exists(), out)
    assert s.run("snapshot", c)[0] == 0
    rc, out = s.verify(c, "f1")
    check(f"{L}: each arm with its own canary and the snapshot: G1 holds", rc == 0, out)
    write([f"{word} {canaries[0]}\nDONE\n", f"{word} {canaries[1]}\nDONE\nas {canaries[0]} said\n",
           f"{word} {canaries[2]}\nDONE\n"])
    assert s.run("snapshot", c)[0] == 0
    rc, out = s.verify(c, "f1")
    check(f"{L}: an arm carrying another arm's canary is refused (contamination)", rc == 1, out)
    write([f"{word} {canaries[1]}\nDONE\n", f"{word} {canaries[0]}\nDONE\n", f"{word} {canaries[2]}\nDONE\n"])
    assert s.run("snapshot", c)[0] == 0
    rc, out = s.verify(c, "f1")
    check(f"{L}: two arms with each other's canary are refused", rc == 1, out)
    c2, _ = s.prepare("fan-out", extra=("--n", 2, "--form", "slices"))
    s.fill_contract(c2)
    s.gate_ok(c2, "f0")
    arms2 = [Path(v["folder"]) for v in s.manifest(c2)["f1"].values()]
    check(f"{L}: a fan-out of slices has no canary, as before",
          not any(token in (a / "TASK.md").read_text(encoding="utf-8") for a in arms2))
    for a in arms2:
        (a / D).write_text("DONE\nmy slice\n", encoding="utf-8")
    rc, out = s.verify(c2, "f1")
    check(f"{L}: and G1 of the slices needs neither canary nor snapshot", rc == 0, out)


# ------------------------------------------------------------------------------------------------------------------
# E12 (clause 10): a later closure after a G5 «not closed»
# ------------------------------------------------------------------------------------------------------------------

def plant_gate(s: Swarm, c: Path, src: int, dst, closed, folder=True, name=None) -> Path:
    """A later gate file of f5 made from the one of the closure `src`: its folder copied to f5_<dst>/ (if `folder`),
    its fingerprints moved there, its «closed» set. The fingerprints still match the copied bytes."""
    sdir, ddir = s.f5(c, src), c / f"f5_{dst}"
    if folder:
        shutil.copytree(sdir, ddir, symlinks=True)
    g = s.gate_c(c, "f5" if src == 1 else f"f5_{src}")
    g["fingerprints"] = {k.replace(str(sdir) + os.sep, str(ddir) + os.sep, 1): v for k, v in g["fingerprints"].items()}
    g["phase"] = f"f5_{dst}"
    g["closed"] = closed
    p = c / (name or f"GATE_f5_{dst}.json")
    p.write_text(json.dumps(C.to_dialect(g, C.CONVENE_KEYS["gate"], s.lang), ensure_ascii=False, indent=1),
                 encoding="utf-8")
    return p


def set_closed(s: Swarm, c: Path, label: str, closed: bool) -> None:
    p = s.gate_file(c, label)
    g = s.gate_c(c, label)
    g["closed"] = closed
    p.write_text(json.dumps(C.to_dialect(g, C.CONVENE_KEYS["gate"], s.lang), ensure_ascii=False, indent=1),
                 encoding="utf-8")


def e12(s: Swarm, base: Path):
    L = f"E12 [{s.lang}]"
    arb = f"01-{C.ROLES['arbiter']}"
    SD, SN, CL = s.N("00-sentinel"), s.N("SENTINEL.md"), s.N("CLOSURE.md")
    c = s.classic(rules=2)
    s.gate_ok(c, "f2")
    assert s.run("select", c, "H-001", "H-002", "--radical", "H-003")[0] == 0
    s.f3(c, "H-001")
    s.f4(c, "H-001", correctness="proven")
    s.gate_ok(c, "f4/H-001")
    s.sentinel(c)
    s.closure(c, closed=False, extra="H-002 and H-003 are open\n")
    rc, out = s.gate(c, "f5")
    g1 = s.gate_c(c, "f5")
    check(f"{L}: the first G5 is approved «not closed» under the rules 2",
          rc == 0 and g1.get("closed") is False and g1.get("rules") == 2, out)
    gate1 = c / "GATE_f5.json"
    raw1 = gate1.read_bytes()
    bound = {k: Path(k).read_bytes() for k in g1["fingerprints"] if not k.endswith("/")}
    f5_files = files(s.f5(c))

    def first_holds(where):
        same = (gate1.read_bytes() == raw1 and all(Path(k).is_file() and Path(k).read_bytes() == v
                                                   for k, v in bound.items()) and files(s.f5(c)) == f5_files)
        out = s.status(c)
        check(f"{L}: {where}: GATE_f5.json, f5/{CL} and every file it binds byte-identical, the first G5 holds",
              same and s.st("status_not_closed", phase="f5") in out, (changes(f5_files, files(s.f5(c))), out))

    rc, out = s.gate(c, "f5")
    check(f"{L}: a gate f5 that would write over the recorded non-closure is refused",
          rc == 1 and gate1.read_bytes() == raw1, out)
    rc, out = s.verify(c, "f5")
    check(f"{L}: gate f5 --verify checks the first G5 again, as in 5.2", rc == 0, out)
    b1 = base / f"e12_b1_{s.lang}"
    shutil.copytree(c, b1, symlinks=True)
    # --- fund and close-branch act; a second G5 «closed» in a new gate file
    f52 = s.f5(c, 2)
    rc, out = s.run("fund", c, "H-003")
    check(f"{L}: fund acts on the radical after the «not closed» G5",
          rc == 0 and (c / "f3" / "H-003" / "H-003.md").is_file() and (c / "f4" / "H-003").is_dir(), out)
    task = f52 / arb / "TASK.md"
    check(f"{L}: fund briefs the next closure's arbiter and sentinel beside it, in f5_2/",
          task.is_file() and (f52 / SD / "TASK.md").is_file(), sorted(files(c)) if not task.is_file() else "")
    first_holds("after fund")
    before = task.read_bytes() if task.is_file() else b""
    rc, out = s.run("close-branch", c, "H-002", "--reason", "no time", "--deciding-test", "the oracle on 10 cases")
    check(f"{L}: close-branch --deciding-test declares H-002 unresolved after the «not closed» G5 and rewrites the "
          f"next closure's brief", rc == 0 and (c / "f3" / "H-002" / s.N("EARLY_CLOSURE.json")).is_file()
          and task.is_file() and task.read_bytes() != before, out)
    first_holds("after close-branch --deciding-test")
    s.f3(c, "H-003")
    s.f4(c, "H-003", correctness="refuted")
    s.gate_ok(c, "f4/H-003")
    first_holds("after the G3 and G4 of the radical")
    rc, out = s.verify(c, "f5")
    check(f"{L}: without f5_2/{CL} the second G5 is refused, though f5/{CL} is there", rc == 1 and "f5_2" in out, out)
    s.closure(c, closed=True, k=2)
    rc, out = s.gate(c, "f5")
    check(f"{L}: round 1's f5/{SD}/{SN} alone does not meet the second G5's sentinel condition",
          rc == 1 and not (c / "GATE_f5_2.json").exists(), out)
    sent2 = s.sentinel(c, k=2)
    rc, out = s.gate(c, "f5")
    g2 = s.gate_c(c, "f5_2")
    check(f"{L}: the second G5 is approved «closed» into GATE_f5_2.json, its outcome from f5_2/{CL}",
          rc == 0 and g2.get("closed") is True, out)
    first_holds("after the second G5")
    out = s.status(c)
    check(f"{L}: status reports the newer G5 (f5_2 approved) beside the first",
          s.st("status_approved", phase="f5_2") in out and s.st("status_not_closed", phase="f5") in out, out)
    fp2 = g2.get("fingerprints", {})
    check(f"{L}: the second G5 binds its closure, its briefs and its sentinel, all in f5_2/",
          fp2 and all(k.startswith(str(f52) + os.sep) for k in fp2)
          and {str(f52 / CL), str(sent2), str(task)} <= set(fp2), sorted(fp2))
    rc, out = s.verify(c, "f5")
    check(f"{L}: gate f5 --verify reads the latest G5", rc == 0 and "f5_2" in out, out)
    for p, how in ((f52 / CL, "an edit of"), (f52 / CL, "the removal of"), (sent2, "one byte appended to"),
                   (task, "one byte appended to")):
        old = p.read_bytes()
        if how == "the removal of":
            p.unlink()
        elif how == "an edit of":
            p.write_bytes(old.replace(b"\n", b" edited\n", 1))
        else:
            p.write_bytes(old + b" ")
        out = s.status(c)
        check(f"{L}: {how} {p.relative_to(c)} after the second G5: status reports f5_2 no longer valid",
              s.st("status_invalid", phase="f5_2") in out, out)
        p.write_bytes(old)
    check(f"{L}: restored, f5_2 approved again", s.st("status_approved", phase="f5_2") in s.status(c))
    snap = files(c)
    for cmd in (("close-branch", c, "H-001", "--reason", "x", "--deciding-test", "t"), ("fund", c, "H-003"),
                ("repin", c, "H-001")):
        rc, out = s.run(*cmd)
        check(f"{L}: after the closed second G5, {cmd[0]} is refused by the lock and writes nothing",
              rc == 1 and "f5_2" in out and files(c) == snap, out)
    # --- the readers on a first gate file that cannot be read
    for label in ("0 bytes", "a BOM", "a byte that is not UTF-8"):
        restore(c, b1)
        data = {"0 bytes": b"", "a BOM": b"\xef\xbb\xbf" + raw1,
                "a byte that is not UTF-8": raw1.replace(b': "x"', b': "\xff"', 1)}[label]
        assert data != raw1
        gate1.write_bytes(data)
        snap = files(c)
        for cmd in (("fund", c, "H-003"), ("close-branch", c, "H-002", "--reason", "x", "--deciding-test", "t"),
                    ("status", c)):
            rc, out = s.run(*cmd)
            check(f"{L}: GATE_f5.json with {label}: {cmd[0]} stops with exit 1 and writes nothing",
                  rc == 1 and files(c) == snap and "Traceback" not in out, out)
    # --- a second G5 «not closed», then the planted ordinals
    restore(c, b1)
    rc, out = s.run("close-branch", c, "H-003", "--reason", "no budget")
    check(f"{L}: close-branch of the unfunded radical acts after the «not closed» G5",
          rc == 0 and (c / "f3" / "H-003" / s.N("EARLY_CLOSURE.json")).is_file() and (f52 / arb / "TASK.md").is_file(),
          out)
    first_holds("after close-branch of the radical")
    s.closure(c, closed=False, extra="H-002 is open\n", k=2)
    s.sentinel(c, k=2)
    rc, out = s.gate(c, "f5")
    check(f"{L}: a second G5 «not closed» goes to GATE_f5_2.json",
          rc == 0 and s.gate_c(c, "f5_2").get("closed") is False, out)
    first_holds("after a second G5 «not closed»")
    b2 = base / f"e12_b2_{s.lang}"
    shutil.copytree(c, b2, symlinks=True)
    act = ("close-branch", c, "H-002", "--reason", "x", "--deciding-test", "t")
    # ordinals 2 and 10: the latest is 10, never the last sorted name (2) nor the newest mtime (GATE_f5.json)
    g10 = plant_gate(s, c, 2, 10, True)
    future, past = time.time() + 10 ** 6, T0
    os.utime(gate1, (future, future))
    os.utime(g10, (past, past))
    snap = files(c)
    rc, out = s.run(*act)
    check(f"{L}: ordinals 2 (open) and 10 (closed), GATE_f5.json the newest: close-branch refused by GATE_f5_10.json",
          rc == 1 and "f5_10" in out and files(c) == snap, out)
    rc, out = s.run("fund", c, "H-003")
    check(f"{L}: fund reads GATE_f5_10.json too", rc == 1 and "f5_10" in out and files(c) == snap, out)
    out = s.status(c)
    check(f"{L}: status reads the ordinals in order and reports f5_10",
          s.st("status_approved", phase="f5_10") in out and s.st("status_not_closed", phase="f5_2") in out, out)
    rc, out = s.verify(c, "f5")
    check(f"{L}: gate f5 reads GATE_f5_10.json", "f5_10" in out, out)
    set_closed(s, c, "f5_2", True)
    set_closed(s, c, "f5_10", False)
    rc, out = s.run(*act)
    check(f"{L}: ordinals 2 (closed) and 10 (open): close-branch acts and briefs the closure f5_11/",
          rc == 0 and (s.f5(c, 11) / arb / "TASK.md").is_file(), out)
    check(f"{L}: status lists f5_11 still to approve", s.st("status_pending", phase="f5_11") in s.status(c))
    for name in ("GATE_f5_\u0663.json", "GATE_f5_\uff13.json"):
        restore(c, b2)
        plant_gate(s, c, 2, 3, True, folder=False, name=name)
        rc, out = s.run(*act)
        check(f"{L}: {name} carries no ASCII ordinal: it does not shut the lock", rc == 0, out)
    for label, how in (("a planted later gate «not closed» with stale fingerprints", "stale"),
                       ("a later gate whose closure changed after it", "changed"),
                       ("a 0-byte later gate file", "empty"), ("a later gate file with a BOM", "bom")):
        restore(c, b2)
        if how == "stale":
            plant_gate(s, c, 2, 3, False, folder=False)
        elif how == "changed":
            plant_gate(s, c, 2, 3, False)
            p = s.f5(c, 3) / CL
            p.write_bytes(p.read_bytes() + b"x")
        elif how == "empty":
            (c / "GATE_f5_3.json").write_bytes(b"")
        else:
            g = c / "GATE_f5_2.json"
            g.write_bytes(b"\xef\xbb\xbf" + g.read_bytes())
        snap = files(c)
        rc, out = s.run(*act)
        check(f"{L}: {label}: close-branch refused with exit 1 and nothing written",
              rc == 1 and files(c) == snap and "Traceback" not in out, out)
    # --- the rules 1: a G5 records no «closed»; its closure says it
    c1 = s.classic(rules=1)
    s.gate_ok(c1, "f2")
    assert s.run("select", c1, "H-001", "H-002")[0] == 0
    s.f3(c1, "H-001", gate=False)
    s.dossier(c1, "H-001")   # under the rules 1 G3 binds the dossier: it is written before G3
    s.gate_ok(c1, "f3/H-001")
    s.f4(c1, "H-001", correctness="proven")
    s.gate_ok(c1, "f4/H-001")
    s.closure(c1, closed=False, extra="H-002 is open\n")
    rc, out = s.gate(c1, "f5")
    g = s.gate_c(c1, "f5")
    check(f"{L}: a G5 of the rules 1 «not closed» (no rules, no closed key)",
          rc == 0 and "rules" not in g and "closed" not in g, (out, g))
    keep1 = (c1 / "GATE_f5.json").read_bytes()
    rc, out = s.run("close-branch", c1, "H-002", "--reason", "no time")
    check(f"{L}: rules 1, closure «not closed»: close-branch acts on the branch left open",
          rc == 0 and (c1 / "f3" / "H-002" / s.N("EARLY_CLOSURE.json")).is_file()
          and (s.f5(c1, 2) / arb / "TASK.md").is_file(), out)
    out = s.status(c1)
    check(f"{L}: and the first G5 of the rules 1 still holds",
          s.st("status_not_closed", phase="f5") in out and (c1 / "GATE_f5.json").read_bytes() == keep1, out)
    c2 = s.classic(rules=1)
    s.gate_ok(c2, "f2")
    assert s.run("select", c2, "H-001", "H-002")[0] == 0
    s.f3(c2, "H-001", gate=False)
    s.dossier(c2, "H-001")   # under the rules 1 G3 binds the dossier: it is written before G3
    s.gate_ok(c2, "f3/H-001")
    s.f4(c2, "H-001", correctness="proven")
    s.gate_ok(c2, "f4/H-001")
    rc, out = s.run("close-branch", c2, "H-002", "--reason", "no time")
    assert rc == 0, out
    s.closure(c2, closed=True)
    s.gate_ok(c2, "f5")
    snap = files(c2)
    rc, out = s.run("close-branch", c2, "H-001", "--reason", "x")
    check(f"{L}: after a closed G5 of the rules 1 close-branch is refused by the lock", rc == 1 and "f5" in out
          and files(c2) == snap, out)
    if s.lang == "en":
        for name, words in (("CHANGELOG.md", ("5.2 engine", "GATE_f5.json")),
                            ("CHANGELOG.it.md", ("5.2", "GATE_f5.json"))):
            t = (SOURCE / name).read_text(encoding="utf-8") if (SOURCE / name).is_file() else ""
            sec = re.search(r"^## 5\.3\.0\b(.*?)(?=^## |\Z)", t, re.M | re.S)
            heads = re.findall(r"^### .*$", sec.group(1), re.M) if sec else []
            check(f"E12: {name} says what a 5.2 engine sees",
                  any("5.2" in h for h in heads) and all(w in (sec.group(1) if sec else "") for w in words), heads)


# ------------------------------------------------------------------------------------------------------------------
# ENG-24: jury.py count . reads the previous juries beside the folder
# ------------------------------------------------------------------------------------------------------------------

JURORS = ["garante", "avversario", "logico", "debugger", "statistico"]
SEAL_LINE = "sha256 of the bytes before this line: "


def sealed_text(text: str) -> str:
    body = text if text.endswith("\n") else text + "\n"
    return body + SEAL_LINE + hashlib.sha256(body.encode("utf-8")).hexdigest() + "\n"


def make_jury(base: Path, name: str, yes: int, previous=()) -> Path:
    """A jury of the protocol G2 in the English dialect: one decision D1, option (a), `yes` jurors of five for it."""
    c = base / name
    c.mkdir(parents=True)
    g = {"protocol": "G2", "lexicon": 5, "subject": name, "rapporteur": "formalista", "clerk": "arbitro",
         "touches_code": True, "touches_numbers": True, "authority": "recommendation", "delegation": "test",
         "classification": "ordinary", "jurors": [{"role": r, "fresh_on_subject": True} for r in JURORS]}
    if previous:
        g["previous"] = list(previous)
    (c / "jury.json").write_text(json.dumps(g), encoding="utf-8")
    seals = ["# reported seals", f"SEAL jury.json {hashlib.sha256((c / 'jury.json').read_bytes()).hexdigest()}"]
    (c / "round_0").mkdir()
    prop = sealed_text("# proposal\nOPTION D1 (a)\nOPTIONS D1 (a) | (b)\nOPERATIVE D1 one does (a)\n")
    (c / "round_0" / "PROPOSAL.md").write_text(prop, encoding="utf-8")
    seals.append(f"SEAL round_0/PROPOSAL.md {prop.rstrip().rsplit(' ', 1)[1]}")
    for i, r in enumerate(JURORS):
        v = "yes" if i < yes else "no"
        body = f"VOTE D1 {v}\n" + ("CONDITION D1 none\n" if v == "yes" else "REVISION D1 remove clause 2\n") + \
               "CLASS D1 ordinary\n"
        t = sealed_text(body)
        (c / "round_0" / f"VOTE_{r}.md").write_text(t, encoding="utf-8")
        seals.append(f"SEAL round_0/VOTE_{r}.md {t.rstrip().rsplit(' ', 1)[1]}")
    (c / "SEALS.md").write_text("\n".join(seals) + "\n", encoding="utf-8")
    return c


def eng24(s: Swarm, base: Path):
    L = f"ENG-24 [{s.lang}]"
    jury = s.swarm / "jury.py"
    w = base / f"juries_{s.lang}"
    first = make_jury(w, "first", yes=1)
    rc, out = py(jury, "count", first, 0)
    check(f"{L}: the previous jury is counted (D1 (a) rejected)",
          rc == 0 and (first / "OUTCOME_round_0.json").is_file(), out)
    second = make_jury(w, "second", yes=5, previous=["first"])
    rc_abs, out_abs = py(jury, "count", second, 0)
    check(f"{L}: with the absolute folder, the option already REJECTED in the previous jury is refused",
          rc_abs != 0 and "REJECTED" in out_abs, out_abs)
    for folder, cwd in ((".", second), ("..", second / "round_0"), ("second", w)):
        rc, out = py(jury, "count", folder, 0, cwd=cwd)
        check(f"{L}: count {folder} from {cwd.relative_to(w.parent)} reads the previous jury as the absolute folder "
              f"does", rc == rc_abs and out == out_abs and "has no outcome" not in out, out)
    ok = make_jury(w, "ok_prev", yes=5)
    assert py(jury, "count", ok, 0)[0] == 0
    third = make_jury(w, "third", yes=5, previous=["ok_prev"])
    rc_abs, out_abs = py(jury, "count", third, 0)
    text_abs = (third / "OUTCOME_round_0.json").read_bytes() if rc_abs == 0 else b""
    (third / "OUTCOME_round_0.json").unlink(missing_ok=True)
    rc, out = py(jury, "count", ".", 0, cwd=third)
    check(f"{L}: count . with a previous jury that rejected nothing: counted, the same outcome as the absolute folder",
          rc_abs == 0 and rc == 0 and out == out_abs and (third / "OUTCOME_round_0.json").read_bytes() == text_abs,
          (out_abs, out))


# ------------------------------------------------------------------------------------------------------------------
# ENG-25: a deliverable that only quotes the placeholder is filled; a real placeholder is not
# ------------------------------------------------------------------------------------------------------------------

def eng25(s: Swarm, base: Path):
    L = f"ENG-25 [{s.lang}]"
    P = s.placeholder()
    filled = {
        "the placeholder quoted in a code span": f"DONE\nEvery `{P}` of the template was replaced.\n",
        "the placeholder alone in a code span": f"DONE\n`{P}`\n",
        "the placeholder in a fenced code block": f"DONE\n```\n{P}\n```\nthe block quotes the template\n",
        "the placeholder in a ~~~ code block": f"DONE\n~~~text\n- Results: {P}\n~~~\n",
        "the placeholder in a sentence": f"DONE\nA brief that still says {P} in a field is refused by G1.\n",
        "a field whose value quotes the placeholder in a code span": f"DONE\n- Results: `{P}` stands for none\n",
    }
    unfilled = {
        "the placeholder alone on a line": f"DONE\n{P}\n",
        "the placeholder alone, indented": f"DONE\n   {P}   \n",
        "the placeholder as the value of a field": f"DONE\n- Results: {P}\n",
        "the placeholder as the value of a bold field": f"DONE\n**Results:** {P}\n",
        "the placeholder as the value of a slice line": f"DONE\nSlice 1 of 14: {P}\n",
        "the placeholder as a table cell": f"DONE\n| field | value |\n|---|---|\n| results | {P} |\n",
        "the placeholder alone after a closed code block": f"DONE\n```\nx\n```\n{P}\n",
    }
    for rules in (2, 3):
        c, _ = s.prepare("single")
        s.set_rules(c, rules)
        s.fill_contract(c)
        s.gate_ok(c, "f0")
        out_p = Path(next(iter(s.manifest(c)["f1"].values()))["folder"]) / s.N("DELIVERABLE.md")
        for name, text in filled.items():
            out_p.write_text(text, encoding="utf-8")
            rc, out = s.verify(c, "f1")
            check(f"{L} rules {rules}: {name}: filled, G1 holds", rc == 0, out)
        for name, text in unfilled.items():
            out_p.write_text(text, encoding="utf-8")
            rc, out = s.verify(c, "f1")
            check(f"{L} rules {rules}: {name}: still to fill in, G1 refused", rc == 1, out)
    c, _ = s.prepare("single")
    contract = c / s.N("CONTRACT.md")
    template = contract.read_text(encoding="utf-8")
    parts = template.split(P)
    contract.write_text(parts[0] + f"filled; the template said `{P}` here" + "filled".join(parts[1:]), encoding="utf-8")
    rc, out = s.verify(c, "f0")
    check(f"{L}: a contract that quotes the placeholder in a code span: G0 holds", rc == 0, out)
    contract.write_text(template.replace(P, "filled", 1), encoding="utf-8")
    rc, out = s.verify(c, "f0")
    check(f"{L}: a contract with its placeholders left: G0 refused", rc == 1, out)


# ------------------------------------------------------------------------------------------------------------------
# ENG-26: under the rules 3 a later gate sees an f0 changed after G1
# ------------------------------------------------------------------------------------------------------------------

def eng26(s: Swarm, base: Path):
    L = f"ENG-26 [{s.lang}]"
    c = s.classic(rules=3)
    contract = c / s.N("CONTRACT.md")
    keep = contract.read_bytes()
    extra = c / "f0" / "notes.md"

    def changed_f0(phase, *more):
        out = []
        contract.write_bytes(keep + b"changed after G1\n")
        rc1, o1 = s.verify(c, phase, *more)
        contract.write_bytes(keep)
        extra.write_text("a new input\n", encoding="utf-8")
        rc2, o2 = s.verify(c, phase, *more)
        extra.unlink()
        rc3, o3 = s.verify(c, phase, *more)
        return (rc1, rc2, rc3), (o1, o2, o3)

    rcs, outs = changed_f0("f2")
    check(f"{L}: rules 3: G2 refused when the contract, or a file of f0/, changed after G1; restored it holds",
          rcs == (1, 1, 0) and "f0" in outs[0] and "f0" in outs[1], outs)
    s.gate_ok(c, "f2")
    assert s.run("select", c, "H-001")[0] == 0
    s.f3(c, "H-001", gate=False)
    rcs, outs = changed_f0("f3/H-001")
    check(f"{L}: rules 3: G3 refused when f0 changed after G1", rcs == (1, 1, 0), outs)
    s.gate_ok(c, "f3/H-001")
    s.f4_r3(c, "H-001", correctness="proven")
    rcs, outs = changed_f0("f4/H-001")
    check(f"{L}: rules 3: G4 refused when f0 changed after G1", rcs == (1, 1, 0), outs)
    s.gate_ok(c, "f4/H-001")
    s.closure(c, closed=True)
    rcs, outs = changed_f0("f5")
    check(f"{L}: rules 3: G5 refused when f0 changed after G1", rcs == (1, 1, 0), outs)
    c2 = s.classic(rules=2)
    contract = c2 / s.N("CONTRACT.md")
    keep2 = contract.read_bytes()
    contract.write_bytes(keep2 + b"changed after G1\n")
    rc, out = s.verify(c2, "f2")
    check(f"{L}: rules 2 unchanged: G2 checks only G1, as in 5.2", rc == 0, out)
    rc, out = s.verify(c2, "f2", "--rules", "3")
    check(f"{L}: the same gate with --rules 3 is refused", rc == 1 and "f0" in out, out)
    contract.write_bytes(keep2)
    c3, _ = s.prepare("fan-out", extra=("--n", 2, "--form", "slices"))
    s.fill_contract(c3)
    s.gate_ok(c3, "f0")
    for v in s.manifest(c3)["f1"].values():
        (Path(v["folder"]) / s.N("DELIVERABLE.md")).write_text("DONE\nmy slice\n", encoding="utf-8")
    s.gate_ok(c3, "f1")
    s.closure(c3, closed=True)
    (c3 / "f0" / "notes.md").write_text("changed after G1\n", encoding="utf-8")
    rc, out = s.verify(c3, "f5")
    check(f"{L}: the fan-out of architetto's F2: with f0 changed after G1, gate f5 --verify is refused",
          rc == 1 and "f0" in out, out)


TESTS = (e1, e2, e3, e4, e5, e6, e7, e9, e10, e11, e12, eng24, eng25, eng26)


def main():
    only = set(sys.argv[1:])
    with tempfile.TemporaryDirectory() as b:
        base = Path(b)
        swarms = {}
        for lang in ("en", "it"):
            s = Swarm(base, lang)
            swarms[lang] = s
            for t in TESTS:
                if only and t.__name__ not in only:
                    continue
                try:
                    t(s, base)
                except Exception:  # noqa: BLE001
                    check(f"{t.__name__} [{lang}] ran to the end", False, traceback.format_exc())
        if not only or "e8" in only:
            try:
                e8(swarms, base)
            except Exception:  # noqa: BLE001
                check("e8 ran to the end", False, traceback.format_exc())
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
