#!/usr/bin/env python3
"""Test battery of the briefs, the sentinels, the K# and the race canaries (swarmer 5.3):
python3 -I -B tests/test_briefs.py

Uses the harness of tests/test_convene.py (an installation in English and one in Italian, the commands by subprocess,
the Italian aliases in the Italian one) and the seal helpers of tests/test_rounds.py. The checks are the acceptance
tests of group 3 of the 5.3 core patch:
- E3 (ENG-17): the engine briefs the sentinels of f2 (prepare), f3 and f4 (select, fund: two funded branches, under
  the rules 3, before any G5), and `sentinel_found` accepts them: G2 wants the f2 one or its «not delivered», G3 and
  G4 warn while theirs is missing, G5 wants every briefed one (or «Declared missing: sentinel: …») and binds the
  folders of f3 and f4; the rules 2 keep the sentinel of the closure alone;
- E5 (ENG-20): every f3 brief asks for the line «decides: yes|no», which G3 wants in every PREDICTIONS.md of f3;
- E6 (ENG-23): the closure brief states what G5 checks for a non-closure (every branch without a valid G4 nor an
  early closure, and a radical never funded nor closed) and names those branches;
- E9 (ENG-15): `contradiction C FILE… --question TEXT` allocates the K# convening-wide in CONTRADICTIONS.jsonl;
  status lists them; under the rules 3 G5 wants every allocated K# named in the closure, G4 warns on a K# cited and
  never allocated, and the briefs of the verdict and of the closure name the registry;
- E10 (ENG-16): under the rules 3 a sentinel is drawn among the free roles fit for the question (a keyword of theirs
  in it), all the free roles when none is fit, and its brief records the draw;
- E11 (ENG-12): in a fan-out race (and a mixed one) every arm has a canary of its own, in its brief and in the map,
  and G1 checks it; a fan-out of slices has none, as before.
Exits with 1 if a check fails.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import test_convene as TC  # noqa: E402   the harness: Swarm, check, the engine modules
import test_rounds as TR  # noqa: E402   the seals of a round of f4 in the order of the rules 3

C, V, check = TC.C, TC.V, TC.check
ARB = C.ROLES["arbiter"]
AGENT = re.compile(r"`(?:swarmer|sciame)-([^`/\s]+)`")


def head(s, key: str) -> str:
    return TR.mission_head(s, key)


def brief_role(task: Path) -> str:
    """The role of a brief, from its agent line."""
    mt = AGENT.search(task.read_text(encoding="utf-8")) if task.is_file() else None
    return mt.group(1) if mt else ""


def line_with(text: str, part: str) -> str:
    """The line of `text` that contains `part` (a mission is one line in its brief), or ''."""
    return next((x for x in text.splitlines() if part and part in x), "")


def fit_roles(s, question: str) -> set[str]:
    """The roles with a keyword of theirs in the question, whole and in any case (computed here, not by the engine)."""
    cat = json.loads((s.swarm / "catalog.json").read_text(encoding="utf-8"))
    q = question.lower()
    return {r["id"] for r in cat["roles"]
            if any(re.search(rf"(?<!\w){re.escape(k.lower())}(?!\w)", q) for k in r["keywords"])}


def convened(s, c: Path) -> set[str]:
    """The roles named by a brief of the convening other than a sentinel's, and every role of its profile."""
    cat = json.loads((s.swarm / "catalog.json").read_text(encoding="utf-8"))
    prof = cat["profiles"][s.manifest(c)["profile"]]
    out = {x for k in ("A", "B", "translates", "f3", "f4") for x in prof.get(k, [])}
    for task in c.rglob("TASK.md"):
        if task.parent.name != s.N("00-sentinel"):
            out.add(brief_role(task))
    return out


def round1(s, c: Path, h: str, correctness="refuted", extra=b"") -> None:
    """f4/<h> delivered and sealed in the order of the rules 3, with its dossier."""
    outs = TR.deliver(s, c / "f4" / h, correctness)
    if extra:
        v = outs[f"09-{ARB}"]
        v.write_bytes(v.read_bytes() + extra)
    s.dossier(c, h)
    TR.write_seals(s, c, TR.seal_rows(s, c) + TR.output_rows(s, outs))


def registry(s, c: Path) -> list[dict]:
    p = c / s.N("CONTRADICTIONS.jsonl")
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []


# --- E11: a canary per arm of a fan-out race (ENG-12) ---

def e11_race(s):
    L = f"E11 [{s.lang}]"
    word = C.CONVENE_LINES["canary"][s.lang]
    for form in ("race", "mixed", "slices"):
        s.n += 1
        dest = s.root / f"fan{s.n}"
        args = ["prepare", "--name", "f", "--strategy", "fan-out", "--profile", "code", "--question", "q", "--n", "3",
                "--form", form, "--dest", dest] + (["--rule", "first"] if form != "slices" else [])
        rc, out = s.run(*args)
        assert rc == 0, out
        c = next(p for p in dest.iterdir() if not p.name.startswith("."))
        folders = [c / "f1" / s.N(f"agent-{k}") for k in (1, 2, 3)]
        heads = [(f / "TASK.md").read_text(encoding="utf-8").splitlines()[0] for f in folders]
        canaries = [x.split(" ", 1)[1] if x.startswith(word + " ") else None for x in heads]
        m = s.manifest(c)
        if form == "slices":
            check(f"{L}: slices: no canary and no map, as before", not any(canaries) and not m.get("map"), heads)
            continue
        check(f"{L}: {form}: every arm's brief starts with a canary of its own",
              all(canaries) and len(set(canaries)) == 3, heads)
        mp = {}
        if m.get("map") and Path(m["map"]).is_file():
            mp = C.to_canonical(json.loads(Path(m["map"]).read_text(encoding="utf-8")), C.CONVENE_KEYS["map"])
        check(f"{L}: {form}: the map, outside the convening, holds the canary of each arm",
              sorted(v.get("canary") for v in mp.values()) == sorted(x for x in canaries if x) and len(mp) == 3
              and c not in Path(m.get("map") or "/").parents, mp)
        contract = c / s.N("CONTRACT.md")
        contract.write_text(contract.read_text(encoding="utf-8").replace(s.line("<to fill in>", "<da compilare>"),
                                                                         "filled"), encoding="utf-8")
        rc, out = s.run("gate", c, "f0", "--notes", "x")
        assert rc == 0, out
        outs = [f / s.N("DELIVERABLE.md") for f in folders]
        for p, k in zip(outs, canaries):
            p.write_text(f"{word} {k}\nDONE\n", encoding="utf-8")
        rc, out = s.run("gate", c, "f1", "--notes", "x", "--verify")
        check(f"{L}: {form}: G1 without the snapshot of the reads: refused", rc == 1 and "snapshot" in out, out)
        s.run("snapshot", c)
        rc, out = s.run("gate", c, "f1", "--notes", "x", "--verify")
        check(f"{L}: {form}: every arm with its own canary, snapshot taken: G1 holds", rc == 0, out)
        old = outs[1].read_text(encoding="utf-8")
        outs[1].write_text(old + f"copied from the other arm: {canaries[0]}\n", encoding="utf-8")
        s.run("snapshot", c)
        rc, out = s.run("gate", c, "f1", "--notes", "x", "--verify")
        check(f"{L}: {form}: an arm with the canary of another: G1 refused (contamination)",
              rc == 1 and "contamination" in out, out)
        outs[1].write_text("DONE\n", encoding="utf-8")
        s.run("snapshot", c)
        rc, out = s.run("gate", c, "f1", "--notes", "x", "--verify")
        check(f"{L}: {form}: an arm without its canary: G1 refused", rc == 1 and "canary" in out, out)
        outs[1].write_text(old, encoding="utf-8")
        s.run("snapshot", c)
        rc, out = s.run("gate", c, "f1", "--notes", "x")
        check(f"{L}: {form}: restored: G1 approved", rc == 0, out)


# --- E5: the «decides» line asked in every f3 brief (ENG-20) ---

def e5_decides(s):
    L = f"E5 [{s.lang}]"
    line = C.CONVENE_LINES["decides"][s.lang]
    for rules in (2, 3):
        c = s.classic(rules=rules)
        s.gate_f2(c)
        rc, out = s.run("select", c, "H-001")
        assert rc == 0, out
        b = c / "f3" / "H-001"
        roles = sorted(d for d in b.iterdir() if d.is_dir() and re.match(r"0[1-4]-", d.name))
        missing = [d.name for d in roles if line not in (d / "TASK.md").read_text(encoding="utf-8")]
        check(f"{L}: rules {rules}: every f3 brief (owner and companions) asks for the line {line}",
              len(roles) == 4 and not missing, missing)
        # every role follows its brief: its deliverable, and its predictions with the line asked
        for d, name in zip(roles, ("SOLUTION.md", "VERIFICATION.md", "MEASUREMENT_PLAN.md", "ATTACK.md")):
            (d / s.N(name)).write_text("done\n", encoding="utf-8")
            (d / s.N("PREDICTIONS.md")).write_text("threshold 1, before the test\n"
                                                   + s.line("decides: yes", "decide: sì") + "\n", encoding="utf-8")
        rc, out = s.run("gate", c, "f3/H-001", "--notes", "x")
        check(f"{L}: rules {rules}: a fresh classic whose f3 roles follow their briefs: G3 passes, no line appended",
              rc == 0, out)


# --- E6: the closure brief says what G5 checks (ENG-23) ---

def e6_closure(s):
    L = f"E6 [{s.lang}]"
    c = s.classic(rules=2)
    s.gate_f2(c)
    rc, out = s.run("select", c, "H-001", "H-003", "--radical", "H-002")
    assert rc == 0, out
    task = c / "f5" / f"01-{ARB}" / "TASK.md"
    rule = head(s, "closure_open")
    x = line_with(task.read_text(encoding="utf-8"), rule)
    check(f"{L}: the closure brief states G5's rule for a non-closure", bool(x), rule)
    tail = x[x.find(rule) + len(rule):] if x else ""
    check(f"{L}: and names every branch it checks: the funded ones and the radical never funded",
          all(h in tail for h in ("H-001", "H-002", "H-003")), tail)
    s.sentinel(c)
    s.closure(c, closed=False, extra="H-001, H-003 and H-002 stay open\n")
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify")
    check(f"{L}: a non-closure naming the branches of the brief: G5 holds", rc == 0, out)
    s.closure(c, closed=False, extra="H-001 and H-003 stay open\n")
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify")
    check(f"{L}: one naming the funded branches only: G5 refused for the radical, as the brief said",
          rc == 1 and "H-002" in out, out)
    rc, out = s.run("close-branch", c, "H-002", "--reason", "no time")
    assert rc == 0, out
    x = line_with(task.read_text(encoding="utf-8"), rule)
    tail = x[x.find(rule) + len(rule):] if x else ""
    check(f"{L}: once the radical is closed, the rewritten brief no longer names it",
          "H-001" in tail and "H-003" in tail and "H-002" not in tail, tail)


# --- E9: the K# allocated convening-wide (ENG-15) ---

def e9_contradictions(s):
    L = f"E9 [{s.lang}]"
    c = s.classic(rules=3)
    s.gate_f2(c)
    rc, out = s.run("select", c, "H-001")
    assert rc == 0, out
    s.f3(c, "H-001")
    b3 = c / "f3" / "H-001"
    sol, att = next(b3.glob("01-*")) / s.N("SOLUTION.md"), next(b3.glob("04-*")) / s.N("ATTACK.md")
    rc, out = s.run("contradiction", c, sol, att, "--question", "does the bound hold at n = 0?")
    rows = registry(s, c)
    check(f"{L}: contradiction allocates K-001 in {s.N('CONTRADICTIONS.jsonl')}, with its files",
          rc == 0 and "K-001" in out and [r.get("id") for r in rows] == ["K-001"]
          and str(sol) in json.dumps(rows, ensure_ascii=False), (out, rows))
    rc, out = s.run("contradiction", c, att, "--question", "is the attack in scope?")
    check(f"{L}: the next one is K-002, convening-wide",
          rc == 0 and "K-002" in out and [r.get("id") for r in registry(s, c)] == ["K-001", "K-002"], out)
    rc, out = s.run("contradiction", c, c / "nope.md", "--question", "x")
    check(f"{L}: a file that does not exist: refused, nothing allocated", rc == 1 and len(registry(s, c)) == 2, out)
    out = s.status(c)
    check(f"{L}: status lists the K# allocated", "K-001" in out and "K-002" in out, out)
    verdict = c / "f4" / "H-001" / f"09-{ARB}" / "TASK.md"
    closure_task = c / "f5" / f"01-{ARB}" / "TASK.md"
    note = head(s, "k_registry")
    check(f"{L}: rules 3: the briefs of the verdict and of the closure name the registry",
          note in verdict.read_text(encoding="utf-8") and note in closure_task.read_text(encoding="utf-8"), note)
    round1(s, c, "H-001", extra=b"K-007 is open, and K-001-3 is numbered by its branch\n")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x")
    check(f"{L}: rules 3: G4 approved, with a warning on K-007, cited and never allocated",
          rc == 0 and "K-007" in out, out)
    check(f"{L}: and on K-001-3, a K# numbered by its branch, which is not K-001 of the registry",
          rc == 0 and "K-001-3" in out, out)
    s.closure(c, closed=False, extra="H-001 refuted; K-001 resolved\n")
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify")
    check(f"{L}: rules 3: a closure that does not name K-002: G5 refused", rc == 1 and "K-002" in out, out)
    s.closure(c, closed=False, extra="H-001 refuted; K-001 resolved, K-002 open\n")
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify")
    check(f"{L}: rules 3: every allocated K# named: G5 holds", rc == 0, out)
    s.closure(c, closed=False, extra="H-001 refuted; K-001 resolved, K-002-1 open\n")
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify")
    check(f"{L}: rules 3: K-002-1 (numbered by a branch) does not name K-002: G5 refused", rc == 1 and "K-002" in out,
          out)
    s.closure(c, closed=False, extra="H-001 refuted; K-001 resolved, K-002 open\n")
    reg = c / s.N("CONTRADICTIONS.jsonl")
    old = reg.read_bytes()
    reg.write_bytes(old + old.splitlines(keepends=True)[0])
    rc, out = s.run("status", c)
    check(f"{L}: a K# written twice in the registry stops the readers with exit 1", rc == 1 and "K-001" in out, out)
    reg.write_bytes(old)
    # the rules 2: the registry works, G5 does not check it
    c = s.classic(rules=2)
    s.gate_f2(c)
    s.run("select", c, "H-001")
    s.f3(c, "H-001")
    s.f4(c, "H-001")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x")
    assert rc == 0, out
    rc, out = s.run("contradiction", c, c / s.N("CONTRACT.md"), "--question", "q?")
    check(f"{L}: rules 2: contradiction allocates K-001 too", rc == 0 and "K-001" in out, out)
    s.closure(c, closed=False, extra="H-001 refuted\n")
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify")
    check(f"{L}: rules 2: G5 does not check the K#, as in 5.2", rc == 0, out)


# --- E3 and E10: the sentinels of f2, f3 and f4 (ENG-17), the draw by fitness, recorded (ENG-16) ---

def e3_sentinels(s):
    L3, L10 = f"E3 [{s.lang}]", f"E10 [{s.lang}]"
    q = "kalman lidar slam"
    fit = fit_roles(s, q)
    c = s.classic(rules=3, question=q, sentinel=False)
    sent = {ph: c / ph / s.N("00-sentinel") for ph in ("f2", "f3", "f4", "f5")}
    t2 = sent["f2"] / "TASK.md"
    check(f"{L3}: prepare briefs the sentinel of f2, with its output in f2/{s.N('00-sentinel')}",
          t2.is_file() and f"`{sent['f2'] / s.N('SENTINEL.md')}`" in t2.read_text(encoding="utf-8"))
    r2 = brief_role(t2)
    check(f"{L10}: the sentinel of f2 is fit for the question (a keyword of its own in it)", r2 in fit, (r2, fit))
    rec = line_with(t2.read_text(encoding="utf-8") if t2.is_file() else "", head(s, "sentinel_draw"))
    check(f"{L10}: its brief records the draw: the seed and the fit roles drawn among",
          bool(rec) and "3" in rec and all(r in rec for r in fit), rec)
    rc, out = s.run("gate", c, "f2", "--notes", "x", "--verify")
    check(f"{L3}: rules 3: G2 refused while the sentinel of f2 has not delivered", rc == 1 and "sentinel" in out, out)
    rc, out = s.run("gate", c, "f2", "--notes", "x", "--verify", "--not-delivered", r2)
    check(f"{L3}: or declared not delivered: G2 holds", rc == 0, out)
    (sent["f2"] / s.N("SENTINEL.md")).write_text("checked\n", encoding="utf-8")
    rc, out = s.run("gate", c, "f2", "--notes", "x")
    g2 = s.gate_json(c, "f2")[1]["fingerprints"] if rc == 0 else {}
    check(f"{L3}: delivered: G2 approved, and binds it", str(sent["f2"] / s.N("SENTINEL.md")) in g2, out)
    rc, out = s.run("select", c, "H-001", "H-002")
    assert rc == 0, out
    t3, t4, t5 = (sent[p] / "TASK.md" for p in ("f3", "f4", "f5"))
    check(f"{L3}: with two branches select briefs the sentinels of f3 and f4", t3.is_file() and t4.is_file())
    rs = [brief_role(t) for t in (t2, t3, t4, t5)]
    check(f"{L3}: the four sentinels are four roles, none convened by a brief or by the profile",
          len(set(rs)) == 4 and all(rs) and not set(rs) & convened(s, c), (rs, set(rs) & convened(s, c)))
    check(f"{L10}: f3 and f4 drawn among the fit roles left", rs[1] in fit and rs[2] in fit, (rs, fit))
    check(f"{L10}: with no fit role left, the closure's sentinel is drawn among all the free ones, and says so",
          rs[3] not in fit and head(s, "sentinel_draw_unfit") in (t5.read_text(encoding="utf-8") if t5.is_file()
                                                                   else ""), rs)
    for h in ("H-001", "H-002"):
        s.f3(c, h, gate=False)
    rc, out = s.run("gate", c, "f3/H-001", "--notes", "x")
    where3 = f"f3/{s.N('00-sentinel')}"
    check(f"{L3}: G3 approved, with a warning while the sentinel of f3 has not delivered", rc == 0 and where3 in out,
          out)
    (sent["f3"] / s.N("SENTINEL.md")).write_text("checked\n", encoding="utf-8")
    rc, out = s.run("gate", c, "f3/H-002", "--notes", "x")
    check(f"{L3}: once it delivered, no such warning", rc == 0 and where3 not in out, out)
    for h in ("H-001", "H-002"):
        round1(s, c, h)
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x")
    where4 = f"f4/{s.N('00-sentinel')}"
    check(f"{L3}: G4 approved, with a warning while the sentinel of f4 has not delivered", rc == 0 and where4 in out,
          out)
    V._FP.clear()
    before = V.sentinel_found(V.Convening.load(c), phase="f4")
    (sent["f4"] / s.N("SENTINEL.md")).write_text("checked\n", encoding="utf-8")
    check(f"{L3}: sentinel_found accepts the sentinel of f4 once it delivered",
          not before and V.sentinel_found(V.Convening.load(c), phase="f4"))
    rc, out = s.run("gate", c, "f4/H-002", "--notes", "x")
    check(f"{L3}: and G4 no longer warns", rc == 0 and where4 not in out, out)
    sentinel5 = sent["f5"] / s.N("SENTINEL.md")
    sentinel5.write_text("checked\n", encoding="utf-8")
    s.closure(c, closed=False, extra="H-001 and H-002 refuted\n")
    s4 = sent["f4"] / s.N("SENTINEL.md")
    s4.unlink()
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify")
    check(f"{L3}: rules 3: G5 refused without the sentinel of f4", rc == 1 and where4 in out, out)
    s.closure(c, closed=False, extra="H-001 and H-002 refuted\n"
              + s.line("Declared missing: sentinel: f4 stopped\n", "Dichiarato mancante: sentinella: f4 fermata\n"))
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify")
    check(f"{L3}: or with the line «Declared missing» in the closure: G5 holds", rc == 0, out)
    s4.write_text("checked\n", encoding="utf-8")
    s.closure(c, closed=False, extra="H-001 and H-002 refuted\n")
    rc, out = s.run("gate", c, "f5", "--notes", "x")
    fp = s.gate_json(c, "f5")[1]["fingerprints"] if rc == 0 else {}
    check(f"{L3}: every sentinel delivered: G5 approved, binding the sentinels of f3 and f4",
          str(s4) in fp and str(sent["f3"] / s.N("SENTINEL.md")) in fp, (out, sorted(fp)))
    s4.write_text("checked, and edited after G5\n", encoding="utf-8")
    check(f"{L3}: the sentinel of f4 edited after G5: status reports G5 invalid",
          s.st("status_invalid", phase="f5") in s.status(c))
    s4.write_text("checked\n", encoding="utf-8")
    # rules 3, a radical funded before any G5: the sentinels stay as drawn, and none of them owns a branch
    c = s.classic(rules=3)
    s.gate_f2(c)
    rc, out = s.run("select", c, "H-001", "H-002", "--radical", "H-003")
    assert rc == 0, out
    paths = [c / ph / s.N("00-sentinel") / "TASK.md" for ph in ("f3", "f4", "f5")]
    before = [p.read_bytes() if p.is_file() else b"" for p in paths]
    owner = brief_role(paths[0])
    rc, out = s.run("fund", c, "H-003", "--owner", owner)
    check(f"{L10}: fund with a sentinel as --owner: refused, nothing written",
          rc == 1 and "sentinel" in out and not (c / "f3" / "H-003").exists(), out)
    rc, out = s.run("fund", c, "H-003")
    after = [p.read_bytes() if p.is_file() else b"" for p in paths]
    check(f"{L3}: fund leaves the briefs of the sentinels of f3 and f4 as written, and draws the closure's again alike",
          rc == 0 and all(before) and after == before, (out, [a == b for a, b in zip(after, before)]))
    # the rules 2: the sentinel of the closure alone, as in 5.2
    c = s.classic(rules=2)
    s.gate_f2(c)
    s.run("select", c, "H-001", "H-002")
    check(f"{L3}: rules 2: no sentinel of f3 nor of f4 is briefed",
          not (c / "f3" / s.N("00-sentinel")).exists() and not (c / "f4" / s.N("00-sentinel")).exists())
    # rules 3, a radical funded after a G5 «not closed»: no sentinel of f3 or f4 then, the first G5 holds
    c = s.classic(rules=3)
    s.gate_f2(c)
    rc, out = s.run("select", c, "H-001", "--radical", "H-002")
    assert rc == 0, out
    s.f3(c, "H-001")
    round1(s, c, "H-001")
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x")
    assert rc == 0, out
    s.closure(c, closed=False, extra="H-001 refuted, H-002 never funded\n")
    rc, out = s.run("gate", c, "f5", "--notes", "x")
    assert rc == 0, out
    rc, out = s.run("fund", c, "H-002")
    check(f"{L3}: rules 3: fund after a G5 «not closed» briefs no sentinel of f3 nor f4, and the first G5 holds",
          rc == 0 and not (c / "f3" / s.N("00-sentinel")).exists() and TR.holds(c, "f5"), out)


def main():
    with tempfile.TemporaryDirectory() as b:
        base = Path(b)
        for lang in ("en", "it"):
            s = TC.Swarm(base, lang)
            for t in (e11_race, e5_decides, e6_closure, e9_contradictions, e3_sentinels):
                try:
                    t(s)
                except Exception as e:   # one item failing on an unchanged engine does not hide the others
                    check(f"{t.__name__} [{s.lang}] ran to the end", False, repr(e))
    failed = [n for n, ok in TC.results if not ok]
    print(f"\n{len(TC.results) - len(failed)}/{len(TC.results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
