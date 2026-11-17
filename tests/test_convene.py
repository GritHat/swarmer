#!/usr/bin/env python3
"""Test battery of the gates of a convening (PIPELINE.md, engine/convene.py): python3 -I -B tests/test_convene.py

Installs the swarm twice in a temporary folder, once in English and once in Italian, and drives
`<swarm>/convene.py` by subprocess (the canonical commands in English, the aliases in Italian) through classic
convenings written by hand. The checks T1–T10 are the defects found in a real convening (ENG-1 to ENG-10: the dossier
bound at G4, the fields continued on the next lines, the copies of a convening inside a workspace, the code and the
raw outputs bound, the sentinel, the outcome and the proven results of G5, V2 and the statistician, the radical
funded on demand, the brief of the closure, the amendments); T12–T14 are the holes found by the review of that patch
(the folders taken as nested convenings, the generated trees, the symbolic links, the verdict that decides «proven»,
the radical never funded, the upgrade path of an older convening); T11 is the compatibility of the convenings born
before the rules 2 (no gate_rules key: the gates of 5.0, the fixture of 4.0). Exits with 1 if a check fails.
"""
from __future__ import annotations

import hashlib
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
FIXTURES = HERE / "fixtures"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SOURCE / "engine"))
import compat as C  # noqa: E402
import convene as V  # noqa: E402

results = []


def i18n(lang):
    out = json.loads((SOURCE / "i18n" / "en.json").read_text(encoding="utf-8"))
    p = SOURCE / "i18n" / f"{lang}.json"
    if p.is_file():
        for k, v in json.loads(p.read_text(encoding="utf-8")).items():
            out[k] = {**out[k], **v} if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


TEXTS = {"en": i18n("en"), "it": i18n("it")}


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("ok   " if ok else "FAILED ") + name + ("" if ok or not detail else f"\n     {str(detail)[:900]}"))


def clean_env():
    e = {k: v for k, v in os.environ.items() if not k.startswith(("SWARMER_", "SCIAME_"))}
    e["PATH"] = os.pathsep.join(d for d in e.get("PATH", "").split(os.pathsep)
                                if d and not os.path.exists(os.path.join(d, "claude")))
    return e


def py(*arg):
    p = subprocess.run([sys.executable, "-I", "-B", *map(str, arg)], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, env=clean_env())
    return p.returncode, p.stdout + p.stderr


def legacy_fingerprints(c: Path, m: dict, phase: str, contract: Path) -> dict:
    """A copy of the fingerprints of 5.0 (the rules 1), to check that they did not change."""
    def sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()
    if phase == "f0":
        folders = [c / "f0"]
    elif phase == "f1":
        folders = [Path(v.get("folder") or v.get("cartella")) for v in m["f1"].values()]
    else:
        folders = [c / phase]
    files = [contract] if phase == "f0" else []
    folder = c
    for folder in folders:
        files += sorted(p for p in folder.rglob("*.md") if p.is_file())
    if phase.startswith("f3/") or phase.startswith("f4/"):
        files += sorted(p for p in folder.rglob("*.json") if p.is_file() and not p.name.startswith("GATE_"))
    return {str(p): sha(p) for p in files}


class Swarm:
    """An installation in one language, and the convenings it drives."""

    def __init__(self, base: Path, lang: str):
        self.lang = lang
        self.it = lang == "it"
        self.root = base / f"root_{lang}"
        self.root.mkdir(parents=True)
        rc, out = py(ENGINE, "install", "--from", SOURCE, "--root", self.root, "--language", lang)
        assert rc == 0, out
        self.swarm = self.root / ("sciame" if self.it else "swarmer")
        self.t = TEXTS[lang]
        self.n = 0

    # names and lines in the dialect of the convenings of this installation
    def N(self, canonical: str) -> str:
        return C.localize_path(canonical, self.lang, "convene")

    def line(self, en: str, it: str) -> str:
        return it if self.it else en

    def run(self, *args):
        """convene.py with the canonical names (en) or with the Italian aliases (it)."""
        args = [str(a) for a in args]
        if self.it:
            cmds, opts = self.t["commands"], self.t["options"]
            args = [(cmds.get(a) or [a])[0] if i == 0 else ((opts.get(a) or [a])[0] if a.startswith("--") else a)
                    for i, a in enumerate(args)]
        return py(self.swarm / "convene.py", *args)

    def status(self, c):
        return self.run("status", c)[1]

    def st(self, key, **kw):
        return self.t["convene"][key].format(**kw).strip()

    def gate_json(self, c: Path, phase: str) -> tuple[dict, dict]:
        raw = json.loads((c / f"GATE_{phase.replace('/', '_')}.json").read_text(encoding="utf-8"))
        return raw, C.to_canonical(raw, C.CONVENE_KEYS["gate"])

    def manifest(self, c: Path) -> dict:
        p = c / self.N("MANIFEST.json")
        return C.to_canonical(json.loads(p.read_text(encoding="utf-8")), C.MANIFEST_SCHEMA)

    # --- a classic convening, written by hand up to G2 ---
    def classic(self, profile="data", rules=2, triage=("H-001", "H-002", "H-003")) -> Path:
        self.n += 1
        dest = self.root / f"conv{self.n}"
        rc, out = self.run("prepare", "--name", "k", "--strategy", "classic", "--profile", profile, "--question", "q",
                           "--seed", "3", "--dest", dest)
        assert rc == 0, out
        c = next(p for p in dest.iterdir() if not p.name.startswith("."))
        if rules == 1:   # a convening born before the rules 2: no gate_rules key
            p = c / self.N("MANIFEST.json")
            m = json.loads(p.read_text(encoding="utf-8"))
            m.pop("regole_cancelli" if self.it else "gate_rules")
            p.write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        contract = c / self.N("CONTRACT.md")
        contract.write_text(contract.read_text(encoding="utf-8").replace(self.line("<to fill in>", "<da compilare>"),
                                                                         "filled"), encoding="utf-8")
        rc, out = self.run("gate", c, "f0", "--notes", "ok")
        assert rc == 0, out
        lanes = next(p for p in dest.iterdir() if p.name.startswith("."))
        mp = json.loads(next(lanes.glob("*.json")).read_text(encoding="utf-8"))
        for role, v in mp.items():
            folder, canary = v.get("folder") or v.get("cartella"), v.get("canary") or v.get("canarino")
            Path(folder, self.N("DELIVERABLE.md")).write_text(
                f"{C.CONVENE_LINES['canary'][self.lang]} {canary}\nDONE\nidea of {role}\n", encoding="utf-8")
        assert self.run("snapshot", c)[0] == 0
        rc, out = self.run("gate", c, "f1", "--notes", "x")
        assert rc == 0, out
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
        return c

    def gate_f2(self, c):
        rc, out = self.run("gate", c, "f2", "--notes", "x")
        assert rc == 0, out

    def f3(self, c: Path, h: str, gate=True):
        b = c / "f3" / h
        owner = next(b.glob("01-*"))
        (owner / self.N("SOLUTION.md")).write_text("solution\n", encoding="utf-8")
        (owner / self.N("PREDICTIONS.md")).write_text(
            "threshold 1\n" + self.line("decides: yes", "decide: sì") + "\n", encoding="utf-8")
        (next(b.glob("02-*")) / self.N("VERIFICATION.md")).write_text("proof\n", encoding="utf-8")
        (next(b.glob("03-*")) / self.N("MEASUREMENT_PLAN.md")).write_text("plan\n", encoding="utf-8")
        (next(b.glob("04-*")) / self.N("ATTACK.md")).write_text("attack\n", encoding="utf-8")
        if gate:
            rc, out = self.run("gate", c, f"f3/{h}", "--notes", "x")
            assert rc == 0, out

    def dossier(self, c: Path, h: str, extra=""):
        (c / "f3" / h / f"{h}.md").write_text(f"# {h}\n\n- ID: {h}\n- Short title: t\n- Results:\n  - r1\n"
                                              f"  - r2\n{extra}", encoding="utf-8")

    def f4(self, c: Path, h: str, correctness="refuted", audit=True, skip=(), line=True):
        """The deliverables of every briefed folder of f4/<h>; the verdict with its Correctness line."""
        names = {"00": "REVISION.md", "01": "COUNTERCHECKS.md", "02": "DEFECTS.md", "08": "HIDDEN_ASSUMPTIONS.md",
                 "09": "VERDICT.md"}
        values = {"proven": "dimostrata", "verified": "verificata", "refuted": "smentita"}
        for d in sorted((c / "f4" / h).iterdir()):
            if not d.is_dir() or d.name in skip or (d.name.startswith("08-") and not audit):
                continue
            name = names.get(d.name[:2], "MEASUREMENTS.md")
            text = "done\n"
            if name == "VERDICT.md" and line:
                text = self.line(f"Correctness: {correctness}", f"Correttezza: {values[correctness]}") + "\n"
            (d / self.N(name)).write_text(text, encoding="utf-8")
        self.dossier(c, h)

    def sentinel(self, c: Path):
        d = c / "f5" / self.N("00-sentinel")
        d.mkdir(parents=True, exist_ok=True)
        (d / self.N("SENTINEL.md")).write_text("checked\n", encoding="utf-8")

    def closure(self, c: Path, closed=True, extra=""):
        line = (self.line("Outcome: closed", "Esito: chiuso") if closed else
                self.line("Outcome: not closed", "Esito: non chiuso"))
        (c / "f5" / self.N("CLOSURE.md")).write_text(f"{line}\n{extra}", encoding="utf-8")


# --- the checks ---

def t1_dossier(s: Swarm):
    """ENG-1: completing the dossier in f4 does not invalidate G3; the dossier is bound at G4."""
    L = f"T1 [{s.lang}]"
    c = s.classic()
    s.gate_f2(c)
    rc, out = s.run("select", c, "H-001")
    check(f"{L}: select one branch", rc == 0, out)
    s.f3(c, "H-001")
    g = s.gate_json(c, "f3/H-001")[1]
    dossier = c / "f3" / "H-001" / "H-001.md"
    check(f"{L}: a G3 of the rules 2 records rules 2 and does not bind the dossier",
          g.get("rules") == 2 and str(dossier) not in g["fingerprints"], g.get("rules"))
    s.f4(c, "H-001")
    out = s.status(c)
    check(f"{L}: completing the dossier leaves G3 approved", s.st("status_approved", phase="f3/H-001") in out, out)
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x")
    check(f"{L}: G4 passes after the dossier is completed", rc == 0, out)
    g = s.gate_json(c, "f4/H-001")[1]
    check(f"{L}: GATE_f4 binds the dossier", str(dossier) in g["fingerprints"])
    dossier.write_text(dossier.read_text(encoding="utf-8") + "- Limits: none\n", encoding="utf-8")
    out = s.status(c)
    check(f"{L}: editing the dossier invalidates G4 and not G3",
          s.st("status_invalid", phase="f4/H-001") in out and s.st("status_approved", phase="f3/H-001") in out, out)


def t2_fields(s: Swarm):
    """ENG-2: a field continued on the next lines is not empty; an untouched template field is."""
    L = f"T2 [{s.lang}]"
    card = (s.swarm / C.FILE_NAMES.get(s.lang, {}).get("HYPOTHESIS_CARD.md", "HYPOTHESIS_CARD.md")).read_text(
        encoding="utf-8").replace("H-000", "H-003")
    filled = "- ID: H-003\n- Results:\n  - command a, 3 counts\n  - file b\n- Short title: one line\n"
    check(f"{L}: «- Results:» followed by indented lines is not empty", V._empty_fields(filled, card) == [],
          V._empty_fields(filled, card))
    table = [b for b in V._blocks(card) if any("|---" in x for x in b)][0]
    check(f"{L}: the untouched table field of the template is empty",
          V._empty_fields("\n".join(table) + "\n", card) == [table[0]], table[0])
    two = [b for b in V._blocks(card) if len([x for x in b if x.strip()]) == 2 and not b[0].rstrip().endswith(":")
           and b[-1].rstrip().endswith(":")][0]
    check(f"{L}: an untouched field of two lines is empty", V._empty_fields("\n".join(two) + "\n", card) == [two[0]],
          two)
    check(f"{L}: «- ID: H-003» is never empty", V._empty_fields("- ID: H-003\n", card) == [])
    check(f"{L}: under the rules 1 only the field with nothing after it is empty",
          V._empty_fields("\n".join(table) + "\n- Short title:\n", card, 1) == ["- Short title:"])
    c = s.classic()
    s.gate_f2(c)
    s.run("select", c, "H-001")
    s.f3(c, "H-001")
    s.f4(c, "H-001")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify")
    check(f"{L}: G4 with a field continued on indented lines", rc == 0, out)
    s.dossier(c, "H-001", extra="\n".join(table) + "\n")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify")
    check(f"{L}: G4 refused with the untouched table of the template", rc == 1 and "empty fields" in out, out)


def t3_foreign(s: Swarm):
    """ENG-3: the copies of a convening inside a workspace or a corpus are not the branch's own files."""
    L = f"T3 [{s.lang}]"
    c = s.classic()
    s.gate_f2(c)
    s.run("select", c, "H-001")
    s.f3(c, "H-001")
    s.f4(c, "H-001")
    x = next((c / "f4" / "H-001").glob("03-*"))
    for sub in (x / s.N("work") / "root" / s.N(".swarmer") / "c", x / "corpus" / "c"):
        sub.mkdir(parents=True)
        shutil.copy(c / s.N("MANIFEST.json"), sub / s.N("MANIFEST.json"))
        shutil.copytree(c / "f3", sub / "f3")
        (sub / "f4" / "H-001" / "01-x").mkdir(parents=True)
        (sub / "f4" / "H-001" / "01-x" / s.N("PREDICTIONS.md")).write_text("copy\n", encoding="utf-8")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify")
    check(f"{L}: G4 does not read the PREDICTIONS.md of the copies (workspace, corpus)",
          rc == 0 and s.N("PREDICTIONS.md") not in out, out)
    (x / s.N("PREDICTIONS.md")).write_text("born in f4\n", encoding="utf-8")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify")
    check(f"{L}: an unsealed PREDICTIONS.md of the branch is still reported",
          rc == 1 and "not sealed" in out and out.count("not sealed") == 1, out)


def t4_binding(s: Swarm):
    """ENG-4: code, raw outputs and archives are bound; a workspace is one tree entry."""
    L = f"T4 [{s.lang}]"
    c = s.classic()
    s.gate_f2(c)
    s.run("select", c, "H-001")
    s.f3(c, "H-001")
    s.f4(c, "H-001")
    x = next((c / "f4" / "H-001").glob("03-*"))
    (x / "proto").mkdir()
    py_ = x / "proto" / "x.py"
    py_.write_text("print(1)\n", encoding="utf-8")
    raw = x / "out_a.jsonl"
    raw.write_text('{"a": 1}\n', encoding="utf-8")
    tgz = x / "c.tar.gz"
    tgz.write_bytes(b"\x1f\x8b archive")
    gen = x / s.N("work") / "gen"
    gen.mkdir(parents=True)
    for i in range(500):
        (gen / f"r{i:03d}.json").write_text(json.dumps({"i": i}), encoding="utf-8")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x")
    check(f"{L}: G4 with code, raw outputs, an archive and 500 generated files", rc == 0, out)
    p = c / "GATE_f4_H-001.json"
    fp = s.gate_json(c, "f4/H-001")[1]["fingerprints"]
    trees = [k for k, v in fp.items() if v.startswith("tree:")]
    check(f"{L}: x.py, out_a.jsonl and c.tar.gz are bound one by one",
          all(str(q) in fp for q in (py_, raw, tgz)), sorted(fp)[:10])
    check(f"{L}: the workspace is exactly one tree entry", trees == [str(x / s.N("work")) + "/"], trees)
    check(f"{L}: the gate stays under 20 KB", p.stat().st_size < 20_000, p.stat().st_size)
    for q, label in ((gen / "r123.json", "a generated file"), (py_, "x.py"), (tgz, "c.tar.gz")):
        old = q.read_bytes()
        q.write_bytes(old + b" ")
        out = s.status(c)
        check(f"{L}: changing {label} invalidates G4", s.st("status_invalid", phase="f4/H-001") in out, out)
        q.write_bytes(old)
    (x / "proto" / "__pycache__").mkdir()
    (x / "proto" / "__pycache__" / "x.cpython.pyc").write_bytes(b"cache")
    out = s.status(c)
    check(f"{L}: a __pycache__ created afterwards does not invalidate G4",
          s.st("status_approved", phase="f4/H-001") in out, out)


def t5_sentinel(s: Swarm):
    """ENG-5: with two funded branches G5 needs the sentinel, or its declared absence."""
    L = f"T5 [{s.lang}]"
    c = s.classic()
    s.gate_f2(c)
    rc, out = s.run("select", c, "H-001", "H-002")
    task = c / "f5" / s.N("00-sentinel") / "TASK.md"
    check(f"{L}: select of two branches writes the brief of the sentinel", rc == 0 and task.is_file(), out)
    m = s.manifest(c)
    used = set(m["f1"]) | {"arbitro"} | {d.name[3:] for f in ("f3", "f4") for h in ("H-001", "H-002")
                                       for d in (c / f / h).iterdir() if d.is_dir()}
    role = task.read_text(encoding="utf-8").split("`", 2)[1].split("-", 1)[1]
    check(f"{L}: the sentinel is a role of no lane and no team", role not in used, role)
    for h in ("H-001", "H-002"):
        s.f3(c, h)
        s.f4(c, h, correctness="proven")
        rc, out = s.run("gate", c, f"f4/{h}", "--notes", "x")
        assert rc == 0, out
    check(f"{L}: G4 warns that the sentinel is missing", "sentinel" in out
          and s.gate_json(c, "f4/H-002")[1].get("warnings"), out)
    s.closure(c)
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify")
    check(f"{L}: G5 refused without the sentinel", rc == 1 and "sentinel" in out, out)
    s.sentinel(c)
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify")
    check(f"{L}: G5 with the sentinel", rc == 0, out)
    shutil.rmtree(c / "f5" / s.N("00-sentinel"))
    s.closure(c, extra=s.line("Declared missing: sentinel: no free role\n",
                              "Dichiarato mancante: sentinella: nessun ruolo libero\n"))
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify")
    check(f"{L}: G5 with the line «Declared missing» of the dialect", rc == 0, out)
    c = s.classic()
    s.gate_f2(c)
    s.run("select", c, "H-001")
    check(f"{L}: no brief of the sentinel with one branch", not (c / "f5" / s.N("00-sentinel")).exists())
    s.f3(c, "H-001")
    s.f4(c, "H-001", correctness="proven")
    s.run("gate", c, "f4/H-001", "--notes", "x")
    s.closure(c)
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify")
    check(f"{L}: one branch: G5 without the sentinel", rc == 0, out)


def t6_v2(s: Swarm):
    """ENG-7: G4 needs the deliverable of every briefed role, and V2 outside the f3 team on a proven result."""
    L = f"T6 [{s.lang}]"
    c = s.classic(profile="data")
    s.gate_f2(c)
    s.run("select", c, "H-001")
    s.f3(c, "H-001")
    b = c / "f4" / "H-001"
    check(f"{L}: the V2 brief goes to the inverter, in 08-rovesciatore", (b / "08-rovesciatore" / "TASK.md").is_file(),
          sorted(x.name for x in b.iterdir()))
    s.f4(c, "H-001", correctness="proven", audit=False)
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify")
    check(f"{L}: «proven» without the audit: refused", rc == 1 and "V2 missing" in out, out)
    inside = b / "03-statistico" / s.N("HIDDEN_ASSUMPTIONS.md")
    inside.write_text("audit\n", encoding="utf-8")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify")
    check(f"{L}: the audit by a role of the f3 team (statistico): refused", rc == 1 and "V2 missing" in out, out)
    inside.unlink()
    (b / "08-rovesciatore" / s.N("HIDDEN_ASSUMPTIONS.md")).write_text("audit\n", encoding="utf-8")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify")
    check(f"{L}: the audit in 08-rovesciatore: approved", rc == 0, out)
    for q in (b / "03-statistico").iterdir():
        if q.name != "TASK.md":
            q.unlink()
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify")
    check(f"{L}: the statistician's folder with only TASK.md: refused", rc == 1 and "03-statistico" in out, out)
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify", "--not-delivered", "statistico")
    check(f"{L}: with --not-delivered statistico: approved", rc == 0, out)


def t7_outcome(s: Swarm):
    """ENG-6: «Outcome: closed» needs a verdict proven or verified; «not closed» is a recorded non-closure."""
    L = f"T7 [{s.lang}]"
    c = s.classic()
    s.gate_f2(c)
    s.run("select", c, "H-001", "H-002")
    for h in ("H-001", "H-002"):
        s.f3(c, h)
        s.f4(c, h, correctness="refuted")
        rc, out = s.run("gate", c, f"f4/{h}", "--notes", "x")
        assert rc == 0, out
    s.sentinel(c)
    s.closure(c)
    rc, out = s.run("gate", c, "f5", "--notes", "x")
    check(f"{L}: two refuted verdicts and «closed»: G5 refused", rc == 1 and "no H# proven" in out, out)
    s.closure(c, closed=False)
    rc, out = s.run("gate", c, "f5", "--notes", "x")
    raw, g = s.gate_json(c, "f5")
    check(f"{L}: «not closed»: G5 approved as a non-closure", rc == 0 and s.st(
        "gate_approved_not_closed", phase="f5", n=len(g["fingerprints"])) in out, out)
    check(f"{L}: the gate records closed: false" + (" (key «chiuso»)" if s.it else ""),
          raw.get("chiuso" if s.it else "closed") is False, raw)
    out = s.status(c)
    check(f"{L}: status shows the convening not closed", s.st("status_not_closed", phase="f5") in out, out)
    c = s.classic()
    s.gate_f2(c)
    s.run("select", c, "H-001", "H-002")
    for h, v in (("H-001", "verified"), ("H-002", "refuted")):
        s.f3(c, h)
        s.f4(c, h, correctness=v)
        rc, out = s.run("gate", c, f"f4/{h}", "--notes", "x")
        assert rc == 0, out
    s.sentinel(c)
    s.closure(c)
    rc, out = s.run("gate", c, "f5", "--notes", "x")
    raw = s.gate_json(c, "f5")[0]
    check(f"{L}: one verified verdict, V2, the sentinel and «closed»: approved, closed: true",
          rc == 0 and raw.get("chiuso" if s.it else "closed") is True, (out, raw))
    check(f"{L}: status shows f5 approved", s.st("status_approved", phase="f5") in s.status(c))


def t8_radical(s: Swarm):
    """ENG-8: the radical is recorded by select and briefed by fund; the early closures."""
    L = f"T8 [{s.lang}]"
    c = s.classic()
    s.gate_f2(c)
    rc, out = s.run("select", c, "H-001", "--radical", "H-002")
    check(f"{L}: select --radical writes nothing for the radical",
          rc == 0 and not (c / "f3" / "H-002").exists() and not (c / "f4" / "H-002").exists(), out)
    check(f"{L}: the manifest records the radical not funded", s.manifest(c).get("radical_funded") is False)
    rc, out = s.run("gate", c, "f3/H-002", "--notes", "x", "--verify")
    check(f"{L}: a gate on the unfunded radical is refused", rc == 1 and "radical not funded" in out, out)
    out = s.status(c)
    check(f"{L}: status says the radical is not funded", s.st("status_not_funded", phase="f3/H-002", h="H-002") in out,
          out)
    rc, out = s.run("close-branch", c, "H-002", "--reason", "no budget")
    e = json.loads((c / "f3" / "H-002" / s.N("EARLY_CLOSURE.json")).read_text(encoding="utf-8"))
    check(f"{L}: close-branch of the unfunded radical: status «{s.line('not funded', 'non finanziato')}»",
          rc == 0 and e.get(s.line("status", "stato")) == s.line("not funded", "non finanziato"), (out, e))
    c = s.classic()
    s.gate_f2(c)
    s.run("select", c, "H-001", "--radical", "H-002")
    rc, out = s.run("fund", c, "H-002")
    check(f"{L}: fund writes the dossier and the briefs of the radical",
          rc == 0 and (c / "f3" / "H-002" / "H-002.md").is_file() and (c / "f4" / "H-002" / "09-arbitro" / "TASK.md")
          .is_file() and s.manifest(c).get("radical_funded") is True, out)
    rc, out = s.run("fund", c, "H-002")
    check(f"{L}: fund twice is refused", rc == 1, out)
    rc, out = s.run("close-branch", c, "H-002", "--reason", "no time")
    check(f"{L}: close-branch of a funded branch without --deciding-test: refused", rc == 1 and "--deciding-test" in out,
          out)
    kept = c / "f4" / "H-002" / "09-arbitro" / "notes.md"
    kept.write_text("started\n", encoding="utf-8")
    rc, out = s.run("close-branch", c, "H-002", "--reason", "no time", "--deciding-test", "run the oracle on 10 cases")
    e = C.to_canonical(json.loads((c / "f3" / "H-002" / s.N("EARLY_CLOSURE.json")).read_text(encoding="utf-8")),
                       C.CONVENE_KEYS["early_closure"])
    check(f"{L}: with --deciding-test: declared unresolved with the test",
          rc == 0 and e["status"] == "declared unresolved" and e["deciding_test"].startswith("run the oracle"), (out, e))
    check(f"{L}: the untouched briefs of the closed branch are removed, a started one stays",
          not (c / "f3" / "H-002" / "01-dati").exists() and not (c / "f4" / "H-002" / "01-avversario").exists()
          and kept.is_file() and (c / "f3" / "H-002" / "H-002.md").is_file(),
          sorted(str(p.relative_to(c)) for p in (c / "f4").rglob("*") if "H-002" in str(p)))


def t9_closure_brief(s: Swarm):
    """ENG-9: the brief of the closure names f5/CLOSURE.md and every input of the arbiter."""
    L = f"T9 [{s.lang}]"
    c = s.classic()
    s.gate_f2(c)
    s.run("select", c, "H-001", "H-003", "--radical", "H-002")
    task = c / "f5" / "01-arbitro" / "TASK.md"
    text = task.read_text(encoding="utf-8")
    closure = c / "f5" / s.N("CLOSURE.md")
    out_line = next(x for x in text.splitlines() if x.startswith("- **" + s.t["convene"]["output"]))
    check(f"{L}: the Output line names {closure.relative_to(c)}", f"`{closure}`" in out_line, out_line)
    want = [c / "f4" / h / "09-arbitro" / s.N("VERDICT.md") for h in ("H-001", "H-003")] + [
        c / "f4" / "H-001" / "00-dati" / s.N("REVISION.md"), c / "f5" / s.N("00-sentinel") / s.N("SENTINEL.md"),
        c / "f3" / "H-001" / "H-001.md"]
    check(f"{L}: the inputs include the verdicts, the revision of the owner, the dossiers and the sentinel",
          all(f"`{p}`" in text for p in want), [str(p) for p in want if f"`{p}`" not in text])
    check(f"{L}: the unfunded radical is not among the inputs", "H-002" not in text)
    s.run("fund", c, "H-002")
    text = task.read_text(encoding="utf-8")
    check(f"{L}: after fund the radical's verdict and dossier are listed",
          f"`{c / 'f4' / 'H-002' / '09-arbitro' / s.N('VERDICT.md')}`" in text
          and f"`{c / 'f3' / 'H-002' / 'H-002.md'}`" in text)


def t10_amendments(s: Swarm):
    """ENG-10: an amendment is sealed and bound by its own gate; under the rules 2 it blocks the other gates."""
    L = f"T10 [{s.lang}]"
    c = s.classic()
    a1 = c / s.N("AMENDMENT_1.md")
    a1.write_text(s.line("Amends: Constraints, Budget\n", "Modifica: Vincoli, Quota\n") + "git allowed\n",
                  encoding="utf-8")
    rc, out = s.run("gate", c, "A1", "--notes", "x")
    check(f"{L}: {a1.name} unsealed: gate A1 refused", rc == 1 and "not sealed" in out, out)
    s.run("seal", c, a1)
    rc, out = s.run("gate", c, "A1", "--notes", "x")
    check(f"{L}: sealed: gate A1 approved", rc == 0 and (c / "GATE_A1.json").is_file(), out)
    a2 = c / s.N("AMENDMENT_2.md")
    a2.write_text(s.line("Amends: Inputs\n", "Modifica: Ingressi\n"), encoding="utf-8")
    rc, out = s.run("gate", c, "f2", "--notes", "x", "--verify")
    check(f"{L}: gate f2 refused while {a2.name} is not bound", rc == 1 and a2.name in out, out)
    s.run("seal", c, a2)
    rc, out = s.run("gate", c, "2", "--notes", "x")
    check(f"{L}: gate 2 is the gate A2", rc == 0 and (c / "GATE_A2.json").is_file(), out)
    rc, out = s.run("gate", c, "f2", "--notes", "x")
    check(f"{L}: gate f2 once the amendments are bound", rc == 0, out)
    rc, out = s.run("select", c, "H-001")
    brief = (c / "f3" / "H-001" / "01-dati" / "TASK.md").read_text(encoding="utf-8")
    check(f"{L}: the briefs of the branch read the gated amendments", f"`{a1}`" in brief and f"`{a2}`" in brief, brief)
    out = s.status(c)
    check(f"{L}: status lists the amendment gates", s.st("status_approved", phase="A1") in out, out)
    a1.write_text(a1.read_text(encoding="utf-8") + "and more\n", encoding="utf-8")
    out = s.status(c)
    check(f"{L}: editing {a1.name} invalidates A1 and leaves f0 approved",
          s.st("status_invalid", phase="A1") in out and s.st("status_approved", phase="f0") in out, out)
    rc, out = s.run("gate", c, "f3/H-001", "--notes", "x", "--verify")
    check(f"{L}: and blocks the next gates", rc == 1 and a1.name in out, out)


def t12_review_g4(s: Swarm):
    """Review of ENG-3, ENG-4, ENG-6, ENG-7: a manifest that is not a convening's, a generated tree spread over
    subfolders, symbolic links, a VERDICT.md other than the arbiter's, V2 at the root of the branch."""
    L = f"T12 [{s.lang}]"
    c = s.classic()
    s.gate_f2(c)
    s.run("select", c, "H-001")
    s.f3(c, "H-001")
    s.f4(c, "H-001", correctness="proven")
    b = c / "f4" / "H-001"
    x = next(b.glob("03-*"))
    pred = x / s.N("PREDICTIONS.md")
    pred.write_text("born in f4\n", encoding="utf-8")
    for body in ('{"files": ["a"]}', "{}"):
        (x / s.N("MANIFEST.json")).write_text(body, encoding="utf-8")
        rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify")
        check(f"{L}: a {s.N('MANIFEST.json')} {body} in a role folder does not hide its unsealed predictions",
              rc == 1 and "not sealed" in out, out)
    (x / s.N("MANIFEST.json")).unlink()
    pred.unlink()
    stray = b / next(d.name for d in b.iterdir() if d.name.startswith("00-")) / s.N("VERDICT.md")
    stray.write_text(s.line("Correctness: proven", "Correttezza: dimostrata") + "\n", encoding="utf-8")
    (b / "09-arbitro" / s.N("VERDICT.md")).write_text(s.line("Correctness: refuted", "Correttezza: smentita") + "\n",
                                                       encoding="utf-8")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify")
    check(f"{L}: a Correctness line outside the arbiter's verdict: G4 refused",
          rc == 1 and "only the arbiter's verdict" in out, out)
    conv = V.Convening.load(c)
    check(f"{L}: «proven» is read from the arbiter's verdict only", V._correctness(conv, "H-001") == "refuted")
    stray.unlink()
    s.f4(c, "H-001", correctness="proven", audit=False)
    for q in b.glob("08-*/" + s.N("HIDDEN_ASSUMPTIONS.md")):
        q.unlink()
    (b / s.N("HIDDEN_ASSUMPTIONS.md")).write_text("audit\n", encoding="utf-8")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify", "--not-delivered", "rovesciatore")
    check(f"{L}: V2 at the root of the branch (in no role folder): refused", rc == 1 and "V2 missing" in out, out)
    (b / s.N("HIDDEN_ASSUMPTIONS.md")).unlink()
    s.f4(c, "H-001", correctness="proven")
    cases = x / "fixtures" / "cases"
    for i in range(300):
        (cases / f"c{i:04d}").mkdir(parents=True)
        for k in range(3):
            (cases / f"c{i:04d}" / f"{k}.json").write_text(str(i * k), encoding="utf-8")
    outside = s.root / f"outside{s.n}"
    (outside / "d").mkdir(parents=True)
    (outside / "f.md").write_text("one\n", encoding="utf-8")
    (outside / "d" / "g.md").write_text("one\n", encoding="utf-8")
    os.symlink(outside / "f.md", x / "linked.md")
    os.symlink(outside / "d", x / "linked_dir")
    os.symlink(x, x / "loop")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x")
    check(f"{L}: G4 with 900 generated files in 300 subfolders and three symbolic links", rc == 0, out)
    fp = s.gate_json(c, "f4/H-001")[1]["fingerprints"]
    gate_p = c / "GATE_f4_H-001.json"
    check(f"{L}: the generated tree is one entry, the gate stays under 20 KB",
          fp.get(str(x / "fixtures") + "/", "").startswith("tree:") and gate_p.stat().st_size < 20_000,
          (gate_p.stat().st_size, len(fp)))
    for q, label in ((outside / "f.md", "a linked file"), (outside / "d" / "g.md", "a file in a linked folder"),
                     (cases / "c0123" / "1.json", "a file deep in the generated tree")):
        old = q.read_bytes()
        q.write_bytes(old + b"two\n")
        out = s.status(c)
        check(f"{L}: changing {label} invalidates G4", s.st("status_invalid", phase="f4/H-001") in out, out)
        q.write_bytes(old)
    check(f"{L}: restored, G4 holds again", s.st("status_approved", phase="f4/H-001") in s.status(c))


def t13_review_g5(s: Swarm):
    """Review of ENG-5, ENG-8, ENG-10: the sentinel only in f5, a radical never funded, nothing after G5, a gated
    amendment deleted."""
    L = f"T13 [{s.lang}]"
    c = s.classic()
    a1 = c / s.N("AMENDMENT_1.md")
    a1.write_text(s.line("Amends: Constraints\n", "Modifica: Vincoli\n"), encoding="utf-8")
    s.run("seal", c, a1)
    rc, out = s.run("gate", c, "A1", "--notes", "x")
    assert rc == 0, out
    a1.unlink()
    rc, out = s.run("gate", c, "f2", "--notes", "x", "--verify")
    check(f"{L}: a gated amendment deleted: gate f2 refused", rc == 1 and "no longer there" in out, out)
    check(f"{L}: status shows A1 no longer valid", s.st("status_invalid", phase="A1") in s.status(c))
    a1.write_text(s.line("Amends: Constraints\n", "Modifica: Vincoli\n"), encoding="utf-8")
    s.gate_f2(c)
    s.run("select", c, "H-001", "--radical", "H-002")
    for where in (c / "f2", c / "f3" / "H-001", c / "f4" / "H-001"):
        d = where / s.N("00-sentinel")
        d.mkdir(parents=True)
        (d / s.N("SENTINEL.md")).write_text("checked\n", encoding="utf-8")
        check(f"{L}: a sentinel in {where.relative_to(c)} does not count (only f5)",
              not V.sentinel_found(V.Convening.load(c)))
        shutil.rmtree(d)
    s.f3(c, "H-001")
    s.f4(c, "H-001", correctness="proven")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x")
    assert rc == 0, out
    s.closure(c)
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify")
    check(f"{L}: «closed» with the radical neither funded nor closed: refused", rc == 1 and "H-002" in out, out)
    s.closure(c, closed=False, extra="H-002 never funded\n")
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify")
    check(f"{L}: «not closed» naming the radical: approved", rc == 0, out)
    rc, out = s.run("close-branch", c, "H-002", "--reason", "no budget")
    assert rc == 0, out
    s.closure(c)
    rc, out = s.run("gate", c, "f5", "--notes", "x")
    check(f"{L}: the radical closed as not funded: G5 closes", rc == 0, out)
    rc, out = s.run("fund", c, "H-002")
    check(f"{L}: fund after G5: refused", rc == 1 and "f5" in out, out)
    rc, out = s.run("close-branch", c, "H-001", "--reason", "x", "--deciding-test", "t")
    check(f"{L}: close-branch after G5: refused", rc == 1 and "f5" in out, out)
    check(f"{L}: G5 still approved", s.st("status_approved", phase="f5") in s.status(c))


def t14_review_old(s: Swarm):
    """Review of the upgrade path: a convening of the rules 1 with an amendment without «Amends», a radical declared
    unresolved without a test, G4 and G5 under --rules 2, the keys of 5.0 in its gates, status."""
    L = f"T14 [{s.lang}]"
    c = s.classic(rules=1)
    a1 = c / s.N("AMENDMENT_A1.md")
    a1.write_text("git allowed in a throwaway repository\n", encoding="utf-8")
    s.run("seal", c, a1)
    rc, out = s.run("gate", c, "A1", "--notes", "x")
    raw = s.gate_json(c, "A1")[0] if rc == 0 else {}
    check(f"{L}: rules 1: an amendment without «{s.line('Amends', 'Modifica')}» passes A1 with a warning",
          rc == 0 and s.line("Amends", "Modifica") in out and not ({"warnings", "avvisi", "rules", "regole"} & set(raw)),
          (out, raw))
    rc, out = s.run("gate", c, "A1", "--notes", "x", "--verify", "--rules", "2")
    check(f"{L}: under --rules 2 the same amendment is refused", rc == 1 and s.line("Amends", "Modifica") in out, out)
    s.gate_f2(c)
    s.run("select", c, "H-001", "--radical", "H-002")
    owner = next((c / "f4" / "H-001").glob("00-*"))
    shutil.rmtree(owner)   # as select of 5.0 wrote it: no revision, no sentinel
    shutil.rmtree(c / "f5" / s.N("00-sentinel"))
    rc, out = s.run("close-branch", c, "H-002", "--reason", "measured inside H-001")
    task = (c / "f5" / "01-arbitro" / "TASK.md").read_text(encoding="utf-8")
    check(f"{L}: rules 1: the closure brief names no revision and no sentinel that were never briefed",
          rc == 0 and s.N("REVISION.md") not in task and s.N("SENTINEL.md") not in task, task)
    check(f"{L}: rules 1: close-branch leaves the briefs of the branch, as in 5.0",
          (c / "f4" / "H-002" / "09-arbitro" / "TASK.md").is_file())
    s.f3(c, "H-001")
    s.f4(c, "H-001", line=False)
    s.run("gate", c, "f3/H-001", "--notes", "re-gated after the dossier")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x")
    assert rc == 0, out
    s.closure(c)
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify", "--rules", "2")
    check(f"{L}: G5 --rules 2 on a G4 of the rules 1 without the Correctness line: refused, with the way out",
          rc == 1 and "no H# proven" in out and "f4/H-001 --rules 2" in out, out)
    check(f"{L}: G5 --rules 2 asks the test of the branch declared unresolved, and says how to add it",
          "H-002: declared unresolved" in out and "--deciding-test" in out.split("H-002: declared unresolved")[1], out)
    rc, out = s.run("close-branch", c, "H-002", "--reason", "x", "--deciding-test", "run the oracle")
    e = C.to_canonical(json.loads((c / "f3" / "H-002" / s.N("EARLY_CLOSURE.json")).read_text(encoding="utf-8")),
                       C.CONVENE_KEYS["early_closure"])
    check(f"{L}: close-branch --deciding-test adds the test to the old closure, and keeps its reason",
          rc == 0 and e["deciding_test"] == "run the oracle" and e["reason"] == "measured inside H-001", (out, e))
    rc, out = s.run("close-branch", c, "H-002", "--reason", "x", "--deciding-test", "another")
    check(f"{L}: and only once", rc == 1, out)
    s.f4(c, "H-001", correctness="proven")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--rules", "2")
    check(f"{L}: G4 --rules 2 over the amendment gated under the rules 1", rc == 0, out)
    check(f"{L}: the sentinel warning says it is the rules 2 that would require it",
          "sentinel" not in out or "--rules 2" in out, out)
    check(f"{L}: status: the G3 of the rules 1 holds once its G4 is of the rules 2",
          s.st("status_approved", phase="f3/H-001") in s.status(c), s.status(c))
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify", "--rules", "2")
    check(f"{L}: G5 --rules 2 once the verdict has its line and the test is recorded", rc == 0, out)
    rc, out = s.run("gate", c, "f5", "--notes", "x")
    raw = s.gate_json(c, "f5")[0] if rc == 0 else {}
    check(f"{L}: a G5 of the rules 1 writes only the keys of 5.0",
          rc == 0 and set(raw) <= {"phase", "time", "notes", "not_delivered", "fingerprints",
                                   "fase", "ora", "note", "non_consegnati", "impronte"}, raw)
    s.closure(c, closed=False, extra="H-001\n")
    s.run("gate", c, "f5", "--notes", "x")
    out = s.status(c)
    check(f"{L}: status of a G5 of the rules 1 with «not closed»", s.st("status_not_closed", phase="f5") in out, out)
    (c / s.N("AMENDMENT_1.md")).write_text("x\n", encoding="utf-8")
    rc, out = s.run("status", c)
    check(f"{L}: rules 1: two spellings of A1, status reports it and does not abort",
          rc == 0 and "two amendments" in out, out)


def t11_compatibility(s: Swarm, base: Path):
    """T11: a convening without gate_rules gates as 5.0 did; the 4.0 fixture still shows f0 approved."""
    L = f"T11 [{s.lang}]"
    c = s.classic(rules=1)
    s.gate_f2(c)
    rc, out = s.run("select", c, "H-001", "--radical", "H-002")
    check(f"{L}: under the rules 1 select briefs the radical at once", rc == 0 and (c / "f4" / "H-002").is_dir(), out)
    s.f3(c, "H-001")
    s.f3(c, "H-002")
    s.f4(c, "H-001", audit=False, line=False)
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify")
    check(f"{L}: under the rules 1 the completed dossier invalidates G3, as in 5.0: G4 refused", rc == 1, out)
    s.run("gate", c, "f3/H-001", "--notes", "re-gated after the dossier")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x")
    check(f"{L}: G4 of the rules 1: no Correctness line, no V2, no sentinel required", rc == 0, out)
    m = s.manifest(c)
    contract = c / s.N("CONTRACT.md")
    for phase in ("f0", "f1", "f2", "f3/H-001", "f3/H-002", "f4/H-001"):
        g = s.gate_json(c, phase)[1]
        ok = "rules" not in g and g["fingerprints"] == legacy_fingerprints(c, m, phase, contract)
        check(f"{L}: GATE {phase} without «rules», fingerprints of 5.0", ok, sorted(g))
    s.f4(c, "H-002", correctness="refuted")
    out = s.status(c)
    check(f"{L}: status: the G3 of the rules 1 is no longer valid once the dossier is completed",
          s.st("status_invalid", phase="f3/H-002") in out, out)
    rc, out = s.run("gate", c, "f4/H-002", "--notes", "x", "--rules", "2")
    g = s.gate_json(c, "f4/H-002")[1]
    check(f"{L}: gate --rules 2 on one G4: approved over a G3 of the rules 1 without its dossier",
          rc == 0 and g.get("rules") == 2, out)
    out = s.status(c)
    check(f"{L}: status: that G3 of the rules 1 is approved again, beside its G4 of the rules 2",
          s.st("status_approved", phase="f3/H-002") in out and s.st("status_approved", phase="f4/H-002") in out, out)
    s.closure(c)
    rc, out = s.run("gate", c, "f5", "--notes", "x")
    check(f"{L}: G5 of the rules 1: «proven» taken from the G4 of the rules 1, with a warning",
          rc == 0 and "rules 1" in out, out)
    src = FIXTURES / "convening-4.0"
    if s.it and src.is_dir():
        work = base / "fixture40"
        for p in sorted(src.rglob("*")):
            q = work / p.relative_to(src)
            if p.is_dir():
                q.mkdir(parents=True, exist_ok=True)
            else:
                q.parent.mkdir(parents=True, exist_ok=True)
                q.write_text(p.read_text(encoding="utf-8").replace("@FIXTURE_ROOT@", str(work)), encoding="utf-8")
        f = next(p for p in work.iterdir() if p.is_dir() and not p.name.startswith("."))
        out = s.status(f)
        check(f"{L}: the 4.0 fixture still shows f0 approved", s.st("status_approved", phase="f0") in out, out)


def main():
    with tempfile.TemporaryDirectory() as b:
        base = Path(b)
        for lang in ("en", "it"):
            s = Swarm(base, lang)
            for t in (t1_dossier, t2_fields, t3_foreign, t4_binding, t5_sentinel, t6_v2, t7_outcome, t8_radical,
                      t9_closure_brief, t10_amendments, t12_review_g4, t13_review_g5, t14_review_old):
                t(s)
            t11_compatibility(s, base)
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
