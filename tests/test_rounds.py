#!/usr/bin/env python3
"""Test battery of the order of f4, the rounds of a branch and of the closure (gate rules 3, swarmer 5.3):
python3 -I -B tests/test_rounds.py

Uses the harness of tests/test_convene.py (an installation in English and one in Italian, the commands by subprocess,
the Italian aliases in the Italian one). The checks are the acceptance tests of the 5.3 core patch:
- E1 (ENG-19, COORD-1): under the rules 3 the predictions born in f4 are ordered by the seal times of SEALS.jsonl,
  never by an mtime: those of the counterchecks before COUNTERCHECKS.md, those of the roles that work after the
  counterchecks before their own output; every block of a PREDICTIONS.md has its seal; the briefs name the category;
- E7 (ENG-21, COORD-2): under the rules 3 G4 refuses a REVISION.md not sealed after COUNTERCHECKS.md and DEFECTS.md;
- E4 (ENG-18, ENG-22): `repin` opens round 2 of a branch in f4_2/<H#>/, never touching a round-1 file nor the f3
  dossier, and its G4 counts only the round's own files; a second `select` is refused;
- E12: after a G5 «not closed» `fund` and `close-branch` act, and a second G5 goes to GATE_f5_2.json with its own
  closure folder f5_2/, while GATE_f5.json and every file it binds stay byte-identical; the latest G5 is the one of
  the highest ordinal; the lock opens only on a latest G5 that holds and records a non-closure.
Exits with 1 if a check fails.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import test_convene as TC  # noqa: E402   the harness: Swarm, check, the engine modules

C, V, check = TC.C, TC.V, TC.check
ARB = C.ROLES["arbiter"]
NAMES = {"00": "REVISION.md", "01": "COUNTERCHECKS.md", "02": "DEFECTS.md", "08": "HIDDEN_ASSUMPTIONS.md",
         "09": "VERDICT.md"}
SLOT = {"01": 10, "02": 20, "08": 40, "00": 50, "09": 60}   # the minute each output is sealed at (the others 30)
VALUES = {"proven": "dimostrata", "verified": "verificata", "refuted": "smentita"}
FUTURE = datetime.datetime.now().astimezone().replace(microsecond=0) + datetime.timedelta(days=1)
PAST = FUTURE - datetime.timedelta(days=30)


def at(minute: int, base=FUTURE) -> str:
    return (base + datetime.timedelta(minutes=minute)).isoformat()


def row(s, p: Path, time: str, data: bytes | None = None) -> dict:
    data = p.read_bytes() if data is None else data
    return C.to_dialect({"time": time, "file": str(p), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)},
                        C.CONVENE_KEYS["seal"], s.lang)


def seal_rows(s, c: Path) -> list[dict]:
    p = c / s.N("SEALS.jsonl")
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def write_seals(s, c: Path, rows) -> None:
    (c / s.N("SEALS.jsonl")).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def deliver(s, folder: Path, correctness="refuted", audit=True) -> dict[str, Path]:
    """The deliverable of every briefed NN-<role> folder of a round of f4, by the two digits of the folder."""
    out = {}
    for d in sorted(folder.iterdir()):
        if not d.is_dir() or not re.match(r"\d\d-", d.name) or (d.name.startswith("08-") and not audit):
            continue
        name = NAMES.get(d.name[:2], "MEASUREMENTS.md")
        text = "done\n"
        if name == "VERDICT.md":
            text = s.line(f"Correctness: {correctness}", f"Correttezza: {VALUES[correctness]}") + "\n"
        p = d / s.N(name)
        p.write_text(text, encoding="utf-8")
        out[d.name] = p
    return out


def output_rows(s, outs: dict[str, Path], base=FUTURE) -> list[dict]:
    """The seals of the outputs, in the order of f4: counterchecks, defects, measurements, V2, revision, verdict."""
    return [row(s, p, at(SLOT.get(k[:2], 30), base)) for k, p in sorted(outs.items())]


def round_dossier(p: Path, h: str) -> None:
    p.write_text(f"# {h}\n\n- ID: {h}\n- Short title: t\n- Results:\n  - r1\n  - r2\n", encoding="utf-8")


def tree(c: Path) -> dict[str, bytes]:
    """Every file of the convening, with its bytes."""
    return {str(p): p.read_bytes() for p in sorted(c.rglob("*")) if p.is_file()}


def changed(before: dict[str, bytes], after: dict[str, bytes]) -> list[str]:
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


def holds(c: Path, label: str) -> bool:
    """Whether the gate `label` still holds, recomputed in memory under its own rules."""
    V._FP.clear()
    return V.valid(V.Convening.load(c), label)


def mission_head(s, key: str) -> str:
    """The text of a mission up to its first placeholder: what every brief that carries it contains."""
    return s.t["missions"].get(key, f"<no mission {key}>").split("{")[0].strip()


# --- E1: the order of the predictions by the seals (ENG-19), the category in the briefs (COORD-1) ---

def e1_seal_order(s):
    L = f"E1 [{s.lang}]"
    P = s.N("PREDICTIONS.md")
    c = s.classic(rules=3)
    s.gate_f2(c)
    rc, out = s.run("select", c, "H-001")
    assert rc == 0, out
    s.f3(c, "H-001")
    b = c / "f4" / "H-001"
    tasks = {d.name[:2]: (d / "TASK.md").read_text(encoding="utf-8") for d in b.iterdir() if d.is_dir()}
    after, before = mission_head(s, "predictions_after"), mission_head(s, "predictions_before")
    check(f"{L}: under the rules 3 every f4 brief after the counterchecks names the post-countercheck category",
          all(after in t for k, t in tasks.items() if k != "01") and after not in tasks["01"],
          {k: after in t for k, t in tasks.items()})
    check(f"{L}: the counterchecks' brief names the predictions before COUNTERCHECKS.md",
          before in tasks["01"] and all(before not in t for k, t in tasks.items() if k != "01"))
    check(f"{L}: the owner's brief says that the revision is sealed after the counterchecks and the defects",
          mission_head(s, "revision_order") in tasks["00"], tasks["00"])
    outs = deliver(s, b)
    s.dossier(c, "H-001")
    base = seal_rows(s, c)
    rows = base + output_rows(s, outs)

    def verify(*extra, drop=()):
        write_seals(s, c, [r for r in rows if r not in drop] + list(extra))
        return s.run("gate", c, "f4/H-001", "--notes", "x", "--verify")

    rc, out = verify()
    check(f"{L}: the outputs sealed in the order of f4, no prediction: G4 holds", rc == 0, out)
    dbg = b / "02-debugger" / P
    dbg.write_text("the cause is in the cache\n", encoding="utf-8")
    rc, out = verify(row(s, dbg, at(15)))
    check(f"{L}: a debugger prediction sealed after COUNTERCHECKS.md and before its DEFECTS.md: G4 holds", rc == 0, out)
    rc, out = verify(row(s, dbg, at(25)))
    check(f"{L}: one sealed after its DEFECTS.md: refused",
          rc == 1 and "which it must precede" in out and s.N("DEFECTS.md") in out, out)
    rc, out = verify(row(s, dbg, at(20)))
    check(f"{L}: one sealed in the same second as its DEFECTS.md: refused (no order shown)",
          rc == 1 and "which it must precede" in out, out)
    defects_row = next(r for r in rows if r["file"] == str(outs["02-debugger"]))
    rc, out = verify(row(s, dbg, at(15)), drop=[defects_row])
    check(f"{L}: DEFECTS.md never sealed: the order cannot be read, refused",
          rc == 1 and "is not sealed" in out and s.N("DEFECTS.md") in out, out)
    data = dbg.read_bytes()
    dbg.write_bytes(data + b"a second prediction\n")
    rc, out = verify(row(s, dbg, at(15), data))
    check(f"{L}: a prediction block appended after the seal without its own seal: refused",
          rc == 1 and "no seal of its own" in out, out)
    rc, out = verify(row(s, dbg, at(15), data), row(s, dbg, at(18)))
    check(f"{L}: the appended block with its own seal before DEFECTS.md: G4 holds", rc == 0, out)
    rc, out = verify(row(s, dbg, at(15), data), row(s, dbg, at(26)))
    check(f"{L}: the appended block sealed after DEFECTS.md: refused", rc == 1 and "which it must precede" in out, out)
    dbg.write_bytes(b"another text\n")
    rc, out = verify(row(s, dbg, at(15), data))
    check(f"{L}: a PREDICTIONS.md rewritten after its seal: refused", rc == 1 and "not only at the end" in out, out)
    dbg.unlink()
    owner = next(b.glob("00-*"))
    own = owner / P
    own.write_text("the revision keeps the invariant\n", encoding="utf-8")
    rc, out = verify(row(s, own, at(45)))
    check(f"{L}: the owner's prediction sealed after the counterchecks, before its REVISION.md: G4 holds", rc == 0, out)
    rc, out = verify(row(s, own, at(55)))
    check(f"{L}: the owner's prediction sealed after its own REVISION.md: refused",
          rc == 1 and "which it must precede" in out and s.N("REVISION.md") in out, out)
    own.unlink()
    adv = next(b.glob("01-*")) / P
    adv.write_text("the attack breaks the edge\n", encoding="utf-8")
    rc, out = verify(row(s, adv, at(5)))
    check(f"{L}: the counterchecks' prediction sealed before COUNTERCHECKS.md: G4 holds", rc == 0, out)
    checks = outs[next(k for k in outs if k.startswith("01-"))]
    checks_row = next(r for r in rows if r["file"] == str(checks))
    rc, out = verify(row(s, checks, at(10, PAST)), row(s, adv, at(12, PAST)), drop=[checks_row])
    check(f"{L}: a late seal after COUNTERCHECKS.md: refused", rc == 1 and "which it must precede" in out, out)
    os.utime(checks)   # its mtime is now, later than every seal of the case
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify")
    check(f"{L}: a late seal followed by a touch of COUNTERCHECKS.md stays refused (seals, not mtimes)",
          rc == 1 and "which it must precede" in out, out)
    adv.unlink()
    write_seals(s, c, rows)
    # Under the rules 2 the briefs ask no role that works after the counterchecks for a PREDICTIONS.md it could not
    # seal (G4 of the rules 2 orders every one before the counterchecks).
    c2 = s.classic(rules=2)
    s.gate_f2(c2)
    s.run("select", c2, "H-001")
    old = mission_head(s, "predictions_after_old")
    tasks = {d.name[:2]: (d / "TASK.md").read_text(encoding="utf-8") for d in (c2 / "f4" / "H-001").iterdir()}
    check(f"{L}: under the rules 2 the briefs after the counterchecks ask for the predictions in the output instead",
          all(old in t and after not in t for k, t in tasks.items() if k != "01") and old not in tasks["01"],
          {k: old in t for k, t in tasks.items()})


# --- E7: the revision after the counterchecks and the defects (ENG-21, COORD-2) ---

def e7_revision_order(s):
    L = f"E7 [{s.lang}]"
    c = s.classic(rules=3)
    s.gate_f2(c)
    s.run("select", c, "H-001")
    s.f3(c, "H-001")
    b = c / "f4" / "H-001"
    outs = deliver(s, b)
    s.dossier(c, "H-001")
    rows = seal_rows(s, c) + output_rows(s, outs)
    rev = outs[next(k for k in outs if k.startswith("00-"))]
    rev_row = next(r for r in rows if r["file"] == str(rev))
    others = [r for r in rows if r is not rev_row]
    for minute, what in ((5, "before COUNTERCHECKS.md"), (15, "between COUNTERCHECKS.md and DEFECTS.md"),
                         (20, "in the same second as DEFECTS.md")):
        write_seals(s, c, others + [row(s, rev, at(minute))])
        rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify")
        check(f"{L}: REVISION.md sealed {what}: refused", rc == 1 and "the revision answers" in out, out)
    write_seals(s, c, others)
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify")
    check(f"{L}: REVISION.md never sealed: refused", rc == 1 and "is not sealed" in out and s.N("REVISION.md") in out,
          out)
    write_seals(s, c, rows)
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x")
    check(f"{L}: REVISION.md sealed after both: G4 approved under the rules 3",
          rc == 0 and s.gate_json(c, "f4/H-001")[1].get("rules") == 3, out)
    c2 = s.classic(rules=2)
    s.gate_f2(c2)
    s.run("select", c2, "H-001")
    s.f3(c2, "H-001")
    outs = deliver(s, c2 / "f4" / "H-001")
    s.dossier(c2, "H-001")
    rev = outs[next(k for k in outs if k.startswith("00-"))]
    write_seals(s, c2, seal_rows(s, c2) + [row(s, rev, at(5))])
    rc, out = s.run("gate", c2, "f4/H-001", "--notes", "x", "--verify")
    check(f"{L}: under the rules 2 the same order is not checked (a gate keeps the rules it is run under)", rc == 0,
          out)


# --- E4: repin and a second select (ENG-18, ENG-22) ---

def e4_repin(s):
    L = f"E4 [{s.lang}]"
    P = s.N("PREDICTIONS.md")
    c = s.classic()   # the rules 2, as the convening of the repair round
    s.gate_f2(c)
    rc, out = s.run("select", c, "H-001")
    assert rc == 0, out
    s.f3(c, "H-001")
    b1 = c / "f4" / "H-001"
    s.f4(c, "H-001", correctness="refuted")
    for d in ("02-debugger", f"08-{C.ROLES['inverter']}", f"09-{ARB}"):
        (b1 / d / P).write_text("late\n", encoding="utf-8")
    own1 = next(b1.glob("00-*")) / P
    own1.write_text("the owner's, after its revision\n", encoding="utf-8")
    s.run("seal", c, own1)
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify")
    check(f"{L}: round 1 with its late predictions fails G4", rc == 1 and "not sealed" in out, out)
    dossier = c / "f3" / "H-001" / "H-001.md"
    snap = tree(c)
    for args in (("H-001",), ("H-002",), ("H-001", "H-002")):
        rc, out = s.run("select", c, *args)
        check(f"{L}: a second select ({' '.join(args)}) is refused and writes nothing",
              rc == 1 and "select runs once" in out and not changed(snap, tree(c)), (out, changed(snap, tree(c))))
    rc, out = s.run("repin", c, "H-002")
    check(f"{L}: repin of an H# that is not a branch: refused", rc == 1 and not changed(snap, tree(c)), out)
    rc, out = s.run("repin", c, "H-001")
    b2 = c / "f4_2" / "H-001"
    briefs = sorted(d.name for d in b2.iterdir() if d.is_dir()) if b2.is_dir() else []
    check(f"{L}: repin opens round 2 in f4_2/H-001 with every f4 brief",
          rc == 0 and [x[:2] for x in briefs] == [x[:2] for x in sorted(d.name for d in b1.iterdir() if d.is_dir())]
          and all((b2 / x / "TASK.md").is_file() for x in briefs), (out, briefs))
    card = (s.swarm / C.FILE_NAMES.get(s.lang, {}).get("HYPOTHESIS_CARD.md", "HYPOTHESIS_CARD.md")).read_text(
        encoding="utf-8").replace("H-000", "H-001")
    check(f"{L}: the round has its own dossier, from the card", (b2 / "H-001.md").is_file()
          and (b2 / "H-001.md").read_text(encoding="utf-8") == card)
    diff = changed(snap, tree(c))
    allowed = {str(c / "f5" / f"01-{ARB}" / "TASK.md"), str(c / "f5" / s.N("00-sentinel") / "TASK.md")}
    check(f"{L}: repin changes no round-1 file, no seal, no gate and not the f3 dossier (only new files, and the "
          f"brief of the closure)", all(k in allowed or k.startswith(str(c / "f4_2")) for k in diff)
          and all(k in tree(c) for k in snap) and snap[str(dossier)] == dossier.read_bytes(), diff)
    task = (b2 / "02-debugger" / "TASK.md").read_text(encoding="utf-8") if b2.is_dir() else ""
    check(f"{L}: the round-2 briefs name the round and the previous round as an input, and the rules-3 category",
          mission_head(s, "f4_round") in task and f"`{b1}`" in task and mission_head(s, "predictions_after") in task,
          task)
    check(f"{L}: the round-2 arbiter completes the round's dossier",
          b2.is_dir() and str(b2 / "H-001.md") in (b2 / f"09-{ARB}" / "TASK.md").read_text(encoding="utf-8"))
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify")
    check(f"{L}: the G4 of round 2 runs only under the rules 3", rc == 1 and "--rules 3" in out, out)
    if not b2.is_dir():
        return
    outs = deliver(s, b2, correctness="proven")
    round_dossier(b2 / "H-001.md", "H-001")
    preds = {"01": (5, "the re-attack breaks nothing"), "02": (15, "no new anomaly"), "00": (45, "pin unchanged")}
    extra = []
    for d in briefs:
        if d[:2] in preds:
            p = b2 / d / P
            p.write_text(preds[d[:2]][1] + "\n", encoding="utf-8")
            extra.append(row(s, p, at(preds[d[:2]][0])))
    rows = seal_rows(s, c) + extra + output_rows(s, outs)
    write_seals(s, c, rows)
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "round 2", "--rules", "3")
    g = json.loads((c / "GATE_f4_2_H-001.json").read_text(encoding="utf-8")) if rc == 0 else {}
    check(f"{L}: a clean round 2 passes G4 with the late round-1 files in place, into GATE_f4_2_H-001.json",
          rc == 0 and C.to_canonical(g, C.CONVENE_KEYS["gate"]).get("rules") == 3 and own1.is_file()
          and not (c / "GATE_f4_H-001.json").exists(), out)
    fp = C.to_canonical(g, C.CONVENE_KEYS["gate"]).get("fingerprints", {}) if g else {}
    check(f"{L}: the G4 of round 2 binds only the round's own files", fp and all(k.startswith(str(b2)) for k in fp),
          sorted(fp)[:5])
    now, seals_p = tree(c), str(c / s.N("SEALS.jsonl"))
    kept = [k for k in snap if k.startswith((str(b1), str(c / "f3"))) or Path(k).name.startswith("GATE_")]
    check(f"{L}: after round 2 and its G4, every round-1 file, every f3 file and every earlier gate are byte-identical, "
          f"and SEALS.jsonl was only appended to", all(now.get(k) == snap[k] for k in kept)
          and now[seals_p].startswith(snap[seals_p]), [k for k in kept if now.get(k) != snap[k]])
    out = s.status(c)
    check(f"{L}: status shows round 2 approved and round 1 still to approve",
          s.st("status_approved", phase="f4_2/H-001") in out and s.st("status_pending", phase="f4/H-001") in out, out)
    late = b2 / f"09-{ARB}" / P
    late.write_text("proven on the domain\n", encoding="utf-8")
    write_seals(s, c, rows + [row(s, late, at(65))])
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x", "--verify", "--rules", "3")
    check(f"{L}: a round-2 prediction sealed after its own output fails",
          rc == 1 and "which it must precede" in out and s.N("VERDICT.md") in out, out)
    late.unlink()
    write_seals(s, c, rows)
    s.closure(c)
    rc, out = s.run("gate", c, "f5", "--notes", "x")
    check(f"{L}: G5 reads the G4 of the branch's latest round: closed on the proven round 2",
          rc == 0 and s.gate_json(c, "f5")[1].get("closed") is True, out)
    rc, out = s.run("repin", c, "H-001")
    check(f"{L}: repin after a closed G5: refused", rc == 1 and "f5" in out and not (c / "f4_3").exists(), out)


# --- E12: the second closure after a G5 «not closed» ---

def g5_files(s, c: Path) -> dict[str, bytes]:
    """GATE_f5.json and every file under f5/: what the first G5 binds or is."""
    out = {str(p): p.read_bytes() for p in sorted((c / "f5").rglob("*")) if p.is_file()}
    out[str(c / "GATE_f5.json")] = (c / "GATE_f5.json").read_bytes()
    return out


def e12_second_closure(s):
    L = f"E12 [{s.lang}]"
    c = s.classic()   # the rules 2, as propolis-design
    s.gate_f2(c)
    rc, out = s.run("select", c, "H-001", "H-003", "--radical", "H-002")
    assert rc == 0, out
    for h, v in (("H-001", "proven"), ("H-003", "refuted")):
        s.f3(c, h)
        s.f4(c, h, correctness=v)
        rc, out = s.run("gate", c, f"f4/{h}", "--notes", "x")
        assert rc == 0, out
    s.sentinel(c)
    s.closure(c, closed=False, extra="H-002 never funded\n")
    rc, out = s.run("gate", c, "f5", "--notes", "x")
    assert rc == 0, out
    first = g5_files(s, c)
    f52 = c / "f5_2"
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify")
    check(f"{L}: before the next closure is briefed, gate f5 --verify checks the G5 «not closed» again, as 5.2 did",
          rc == 0 and s.st("gate_holds", phase="f5") in out, out)
    rc, out = s.run("gate", c, "f5", "--notes", "again")
    check(f"{L}: and a gate f5 that would write over its record is refused",
          rc == 1 and "never written over" in out and not changed(first, g5_files(s, c)), out)
    check(f"{L}: status shows no next closure before it is briefed", "f5_2" not in s.status(c))
    rc, out = s.run("fund", c, "H-002")
    check(f"{L}: after a G5 «not closed» fund acts on the radical", rc == 0 and (c / "f4" / "H-002").is_dir(), out)
    check(f"{L}: fund leaves GATE_f5.json and every file under f5/ byte-identical, and the first G5 holds",
          not changed(first, g5_files(s, c)) and holds(c, "f5"), changed(first, g5_files(s, c)))
    task = f52 / f"01-{ARB}" / "TASK.md"
    text = task.read_text(encoding="utf-8") if task.is_file() else ""
    out_line = next((x for x in text.splitlines() if x.startswith("- **" + s.t["convene"]["output"])), "")
    check(f"{L}: the briefs of the new closure and of its sentinel go in f5_2/, and name f5_2/{s.N('CLOSURE.md')}",
          f"`{f52 / s.N('CLOSURE.md')}`" in out_line and (f52 / s.N("00-sentinel") / "TASK.md").is_file(), text)
    rc, out = s.run("close-branch", c, "H-002", "--reason", "no time", "--deciding-test", "the oracle")
    check(f"{L}: close-branch acts after the G5 «not closed»; the first G5 holds",
          rc == 0 and not changed(first, g5_files(s, c)) and holds(c, "f5"), out)
    ec = c / "f3" / "H-002" / s.N("EARLY_CLOSURE.json")
    if not ec.is_file():
        return
    raw = json.loads(ec.read_text(encoding="utf-8"))
    raw.pop(s.line("deciding_test", "prova_decisiva"))
    ec.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    task.unlink()
    rc, out = s.run("close-branch", c, "H-002", "--reason", "x", "--deciding-test", "the oracle on 10 cases")
    check(f"{L}: --deciding-test on a branch declared unresolved rewrites the new closure's brief; the first G5 holds",
          rc == 0 and task.is_file() and not changed(first, g5_files(s, c)) and holds(c, "f5"), out)
    closure2 = f52 / s.N("CLOSURE.md")
    closure2.write_text(s.line("Outcome: closed", "Esito: chiuso") + "\n", encoding="utf-8")
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify")
    check(f"{L}: round 1's sentinel alone does not meet the second G5", rc == 1 and "sentinel" in out, out)
    sentinel2 = f52 / s.N("00-sentinel") / s.N("SENTINEL.md")
    sentinel2.write_text("checked again\n", encoding="utf-8")
    rc, out = s.run("gate", c, "f5", "--notes", "round 2")
    g2 = c / "GATE_f5_2.json"
    raw = json.loads(g2.read_text(encoding="utf-8")) if g2.is_file() else {}
    check(f"{L}: the second G5 is approved «closed» into GATE_f5_2.json",
          rc == 0 and raw.get(s.line("closed", "chiuso")) is True, (out, raw))
    fp = C.to_canonical(raw, C.CONVENE_KEYS["gate"]).get("fingerprints", {}) if raw else {}
    check(f"{L}: it binds its closure and every file beside it, under f5_2/",
          fp and all(k.startswith(str(f52)) for k in fp) and str(closure2) in fp and str(sentinel2) in fp, sorted(fp))
    check(f"{L}: GATE_f5.json and every file under f5/ stay byte-identical, and the first G5 holds",
          not changed(first, g5_files(s, c)) and holds(c, "f5"), changed(first, g5_files(s, c)))
    out = s.status(c)
    check(f"{L}: status reports the newer G5 approved, and the first one as the non-closure it records",
          s.st("status_approved", phase="f5_2") in out and s.st("status_not_closed", phase="f5") in out, out)
    for args in (("fund", c, "H-002"), ("close-branch", c, "H-001", "--reason", "x", "--deciding-test", "t")):
        rc, out = s.run(*args)
        check(f"{L}: {args[0]} after the closed second G5: refused", rc == 1 and "f5_2" in out, out)
    for q, how in ((sentinel2, "append"), (closure2, "edit"), (closure2, "remove")):
        old = q.read_bytes()
        if how == "remove":
            q.unlink()
        else:
            q.write_bytes(old + b" " if how == "append" else old.replace(b"\n", b" (edited)\n"))
        out = s.status(c)
        check(f"{L}: {how} of {q.relative_to(c)} after the second G5: status reports it invalid",
              s.st("status_invalid", phase="f5_2") in out, out)
        q.write_bytes(old)
    check(f"{L}: restored, the second G5 holds again", s.st("status_approved", phase="f5_2") in s.status(c))


def plant(s, c: Path, k: int, closed: bool, stale=False) -> None:
    """A later G5 of ordinal k, written by hand: its closure folder f5_<k>/ and its gate file, holding (its
    fingerprints recomputed) or stale."""
    d = c / f"f5_{k}"
    d.mkdir(exist_ok=True)
    (d / s.N("CLOSURE.md")).write_text(
        s.line("Outcome: closed", "Esito: chiuso") if closed else s.line("Outcome: not closed", "Esito: non chiuso"),
        encoding="utf-8")
    V._FP.clear()
    fp = V.fingerprints(V.Convening.load(c), f"f5_{k}", 2)
    if stale:
        fp = {x: "0" * 64 for x in fp}
    g = {"phase": f"f5_{k}", "time": V.now(), "notes": "planted", "not_delivered": [], "fingerprints": fp, "rules": 2,
         "closed": closed}
    (c / f"GATE_f5_{k}.json").write_text(json.dumps(C.to_dialect(g, C.CONVENE_KEYS["gate"], s.lang)),
                                         encoding="utf-8")


def e12_ordinals(s):
    L = f"E12 [{s.lang}]"
    c = s.classic()
    s.gate_f2(c)
    s.run("select", c, "H-001", "--radical", "H-002")
    s.f3(c, "H-001")
    s.f4(c, "H-001", correctness="proven")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x")
    assert rc == 0, out
    s.closure(c, closed=False, extra="H-002 never funded\n")
    rc, out = s.run("gate", c, "f5", "--notes", "x")
    assert rc == 0, out
    newest = FUTURE.timestamp()
    acts = (("fund", c, "H-002"), ("close-branch", c, "H-002", "--reason", "no budget"))

    def refused(what, name):
        before = tree(c)
        for args in acts:
            rc, out = s.run(*args)
            check(f"{L}: {what}: {args[0]} refused, exit 1, nothing written",
                  rc == 1 and name in out and not changed(before, tree(c)), (out, changed(before, tree(c))))

    plant(s, c, 2, closed=False)
    plant(s, c, 10, closed=True)
    os.utime(c / "GATE_f5.json", (newest, newest))
    refused("the ordinals 2 (not closed) and 10 (closed), GATE_f5.json the newest mtime", "f5_10")
    out = s.status(c)
    check(f"{L}: status reads the G5s by ordinal",
          s.st("status_approved", phase="f5_10") in out and s.st("status_not_closed", phase="f5_2") in out, out)
    plant(s, c, 20, closed=False, stale=True)
    refused("a later G5 «not closed» with stale fingerprints", "GATE_f5_20.json")
    (c / "GATE_f5_20.json").write_bytes(b"")
    refused("a 0-byte later gate file", "GATE_f5_20.json")
    rc, out = s.run("gate", c, "f5", "--notes", "x")
    check(f"{L}: gate f5 never writes over an existing gate file",
          rc == 1 and (c / "GATE_f5_20.json").read_bytes() == b"", out)
    for k in (2, 10, 20):
        (c / f"GATE_f5_{k}.json").unlink()
        shutil.rmtree(c / f"f5_{k}")
    gate1 = c / "GATE_f5.json"
    good = gate1.read_bytes()
    for what, data in (("a 0-byte GATE_f5.json", b""), ("a GATE_f5.json with a BOM", b"\xef\xbb\xbf" + good),
                       ("a GATE_f5.json with a byte that is not UTF-8", good.replace(b'"x"', b'"x\xff"', 1))):
        gate1.write_bytes(data)
        refused(what, "GATE_f5.json")
    gate1.write_bytes(good)
    for name in ("GATE_f5_02.json", "GATE_f5_1.json"):
        (c / name).write_text("{}", encoding="utf-8")
        refused(f"an ambiguous ordinal ({name})", name)
        (c / name).unlink()
    (c / "GATE_f5_٣.json").write_text("{}", encoding="utf-8")   # U+0663 is no ASCII digit: not a gate of f5
    plant(s, c, 2, closed=True)
    plant(s, c, 10, closed=False)
    os.utime(gate1, (newest, newest))
    first = g5_files(s, c)
    rc, out = s.run("close-branch", c, "H-002", "--reason", "no budget")
    check(f"{L}: the latest G5 by ordinal (10) holds and is «not closed»: close-branch acts, its brief in f5_11/",
          rc == 0 and (c / "f5_11" / f"01-{ARB}" / "TASK.md").is_file() and not changed(first, g5_files(s, c)), out)
    (c / "GATE_f5_٣.json").unlink()


def e12_rules1(s):
    L = f"E12 [{s.lang}]"
    c = s.classic(rules=1)
    s.gate_f2(c)
    s.run("select", c, "H-001", "--radical", "H-002")
    s.f3(c, "H-001")
    s.f4(c, "H-001", line=False)
    s.run("gate", c, "f3/H-001", "--notes", "re-gated after the dossier")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x")
    assert rc == 0, out
    s.closure(c, closed=False, extra="H-002\n")
    rc, out = s.run("gate", c, "f5", "--notes", "x")
    assert rc == 0, out
    first = g5_files(s, c)
    rc, out = s.run("close-branch", c, "H-002", "--reason", "measured inside H-001")
    check(f"{L}: rules 1: after a G5 whose closure says «not closed», close-branch acts on the open branch",
          rc == 0 and (c / "f5_2" / f"01-{ARB}" / "TASK.md").is_file(), out)
    check(f"{L}: rules 1: and the first G5 still holds", not changed(first, g5_files(s, c)) and holds(c, "f5"),
          changed(first, g5_files(s, c)))
    (c / "f5_2" / s.N("CLOSURE.md")).write_text(s.line("Outcome: closed", "Esito: chiuso") + "\n", encoding="utf-8")
    rc, out = s.run("gate", c, "f5", "--notes", "x")
    raw = json.loads((c / "GATE_f5_2.json").read_text(encoding="utf-8")) if rc == 0 else {}
    check(f"{L}: rules 1: the second G5 is approved into GATE_f5_2.json with the keys of 5.0 only",
          rc == 0 and raw and not ({"rules", "regole", "closed", "chiuso"} & set(raw)), (out, raw))
    for args in (("close-branch", c, "H-001", "--reason", "x"), ("fund", c, "H-002")):
        rc, out = s.run(*args)
        check(f"{L}: rules 1: {args[0]} after a closed G5 of the rules 1: refused", rc == 1 and "f5" in out, out)


def main():
    with tempfile.TemporaryDirectory() as b:
        base = Path(b)
        for lang in ("en", "it"):
            s = TC.Swarm(base, lang)
            for t in (e1_seal_order, e7_revision_order, e4_repin, e12_second_closure, e12_ordinals, e12_rules1):
                t(s)
    failed = [n for n, ok in TC.results if not ok]
    print(f"\n{len(TC.results) - len(failed)}/{len(TC.results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
