#!/usr/bin/env python3
"""Tests of swarmer 5.3.1, the engine defects 1, 2 and 5 of the ECC act D5: python3 -I -B tests/test_engine531.py

- D1: a G5 without f5/CLOSURE.md, or with one that has no outcome line, never reports «Outcome: closed …»;
- D2: every id regex of the engine reads ASCII digits only: H-٠٣٥ and H-０３５ are not H-035, D١ is not D1, agent-٣ is
  not agent-3 (norm_id, ids_in, the K# registry, the protocol lines of juries and crossroads, the names of the state
  files); and only the digits: \\s, \\b and \\w stay Unicode, so the near detectors of the juries and the placeholder
  check of the gates still catch a non-ASCII space or digit, as in 5.3.0 (5.3.1 repair round, D2 spaces);
- D2 closed: where 5.3.0 refused a text with a non-ASCII digit, 5.3.1 refuses it with an error (the four sites of the
  third repair round: a G4 role folder, a G2 selection, a local card, a machine path); tests/test_engine531_diff.py
  checks every other site of the diff against 5.3.0's engine;
- D5: INPUTS.md and ASSEMBLY.json, the derived views beside a brief's TASK.md, are not a deliverable for ENG-7a, and
  an early closure removes a brief folder that holds only them beside the unchanged TASK.md;
- A1-A7: the tester's acceptance checks of the same defects, of defect 7 and of the version (see their section).

Reuses the installation and the convenings of tests/test_engine53.py (in English and in Italian). Exits with 1 if a
check fails.
"""
from __future__ import annotations

import ast
import json
import re
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
import test_engine53 as T  # noqa: E402

C, V, SOURCE, check, results = T.C, T.V, T.SOURCE, T.check, T.results
ARABIC, FULLWIDTH = "H-٠٣٥", "H-０３５"   # H-٠٣٥ and H-０３５
RE_CALLS = {"compile", "match", "search", "fullmatch", "findall", "finditer", "sub", "subn", "split"}
FLAG_POS = {"compile": 1, "match": 2, "search": 2, "fullmatch": 2, "findall": 2, "finditer": 2, "split": 3,
            "sub": 4, "subn": 4}


def d1(s: T.Swarm, base: Path):
    L = f"D1 [{s.lang}]"
    c = s.classic(rules=2)
    s.gate_ok(c, "f2")
    assert s.run("select", c, "H-001")[0] == 0
    s.f3(c, "H-001")
    s.f4(c, "H-001", correctness="refuted")
    s.gate_ok(c, "f4/H-001")
    s.sentinel(c)
    CL = s.N("CLOSURE.md")
    rc, out = s.verify(c, "f5")
    check(f"{L}: a G5 without f5/{CL} is refused for the missing closure and reports no «Outcome: closed …»",
          rc == 1 and f"{CL} of the arbiter is missing" in out and "closed but no H#" not in out, out)
    p = s.f5(c) / CL
    p.write_text("the arbiter wrote no outcome line\n", encoding="utf-8")
    rc, out = s.verify(c, "f5")
    check(f"{L}: a G5 whose f5/{CL} has no outcome line reports that line missing, not «Outcome: closed …»",
          rc == 1 and f"{CL} without the line" in out and "closed but no H#" not in out, out)
    s.closure(c, closed=True)
    rc, out = s.verify(c, "f5")
    check(f"{L}: a G5 whose f5/{CL} says closed, with no H# proven, still reports «Outcome: closed but no H# proven»",
          rc == 1 and "closed but no H# proven" in out, out)


def _pattern_text(node, consts):
    """The text of a pattern argument when the source fixes it: a literal, an f-string, a + of them, or a module-level
    name bound to one; None otherwise. Bytes patterns are ASCII already."""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.JoinedStr):
        return "".join(_pattern_text(v, consts) or "" for v in node.values)
    if isinstance(node, ast.FormattedValue):
        return _pattern_text(node.value, consts) or ""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _pattern_text(node.left, consts), _pattern_text(node.right, consts)
        return None if a is None and b is None else (a or "") + (b or "")
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    return None


def _has_ascii(node) -> bool:
    return any(isinstance(x, ast.Attribute) and x.attr in ("ASCII", "A") for x in ast.walk(node)) or \
        any(isinstance(x, ast.Constant) and isinstance(x.value, str) and x.value.startswith("(?a") for x in ast.walk(node))


# The rule of the digits (5.3.1 repair round). re.ASCII changes \d, and also \s, \b and \w: so it goes only on a regex
# without \s, \S, \b, \B, \w, \W, where it changes the digits alone; elsewhere a strict regex writes [0-9]. A Unicode
# \d stays only in a negative lookaround (it refuses more) and in the detectors below, whose match turns a line into an
# error or a field into unfilled: there a wider match fails closed, as in 5.3.0.
DETECTORS = {"near", "SEAL_NEAR", "DELEGATED_NEAR", "PLACEHOLDER", "LIST_ITEM", "TABLE_ROW", "KTOKEN", "MACHINE_PATH"}
_ESC = r"(?<!\\)(?:\\\\)*\\"
UNICODE_CLASS = re.compile(_ESC + r"[sSbBwW]")
DIGIT = re.compile(_ESC + "d")
NEG_LOOK = re.compile(r"\(\?<?!(?:[^()\\]|\\.)*\)")


def assigned_names(tree) -> dict:
    """id(call) → the name or attribute a module or method assigns it to (PLACEHOLDER = re.compile(…), self.near = …)."""
    out = {}
    for st in ast.walk(tree):
        if isinstance(st, ast.Assign) and isinstance(st.value, ast.Call):
            for x in st.targets:
                name = x.id if isinstance(x, ast.Name) else x.attr if isinstance(x, ast.Attribute) else None
                if name:
                    out[id(st.value)] = name
    return out


def digit_rule(text: str, ascii_flag: bool, target) -> str | None:
    """Why a regex breaks the rule of the digits, or None."""
    if ascii_flag and UNICODE_CLASS.search(text):
        return "re.ASCII on a regex with \\s, \\b or \\w"
    if not ascii_flag and DIGIT.search(NEG_LOOK.sub("", text)) and target not in DETECTORS:
        return "Unicode \\d in a strict regex"
    return None


def unicode_digit_regexes(path: Path) -> list[str]:
    """The re calls of a source file that break the rule of the digits."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    consts = {}
    for st in tree.body:
        if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
            t = _pattern_text(st.value, consts)
            if t is not None:
                consts[st.targets[0].id] = t
    names = assigned_names(tree)
    bad = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in RE_CALLS
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "re" and node.args):
            continue
        text = _pattern_text(node.args[0], consts)
        if text is None:
            continue
        pos = FLAG_POS[node.func.attr]
        flags = [k.value for k in node.keywords if k.arg == "flags"] + list(node.args[pos:pos + 1])
        why = digit_rule(text, any(_has_ascii(f) for f in flags) or text.startswith("(?a"), names.get(id(node)))
        if why:
            bad.append(f"{path.relative_to(SOURCE)}:{node.lineno} {why}")
    return bad


def d2(s: T.Swarm, base: Path):
    L = f"D2 [{s.lang}]"
    if s.lang == "en":
        files = sorted([*(SOURCE / "engine").glob("*.py"), *(SOURCE / "wrappers").glob("*.py")])
        bad = [x for p in files for x in unicode_digit_regexes(p)]
        check("D2: no re call of the engine and the wrappers passes re.ASCII with \\s, \\b or \\w, and a Unicode \\d is "
              "left only in the near detectors and the placeholder check", files and not bad, bad)
        for x in (ARABIC, FULLWIDTH, "H-٣٥", "H-0٣٥"):
            try:
                got = V.norm_id(x)
            except V.Error:
                got = None
            check(f"D2: norm_id refuses {x!r}, it is not H-035", got is None, got)
        check("D2: norm_id keeps the ASCII forms (h35, H-035, H035 → H-035)",
              {V.norm_id(x) for x in ("h35", "H-035", "H035", " H-35 ")} == {"H-035"})
        text = f"{ARABIC} and {FULLWIDTH} and K-٠٠١\n"
        check("D2: ID and KID find no H# or K# in Arabic-Indic or fullwidth digits",
              not V.ID.findall(text) and not V.KID.findall(text),
              (V.ID.findall(text), V.KID.findall(text)))
        check("D2: H-035 stays found beside them, alone", V.ID.findall(text + "H-035\n") == ["35"],
              V.ID.findall(text + "H-035\n"))
        check("D2: a state name with Arabic-Indic digits is not localized as an ASCII one: agent-٣ is refused (5.3.1 "
              "third repair round: no longer left as is)", raises(C.localize_path, "agent-٣", "it", "convene") == "Error"
              and C.localize_path("agent-3", "it", "convene") == "agente-3",
              raises(C.localize_path, "agent-٣", "it", "convene"))
        check("D2: round_٢ is not a round token", not C.ROUND_TOKEN_RE.match("round_٢"))
        import jury as J
        vote = J.Lexicon(5).lines["VOTE"][1]
        check("D2: «VOTE D١ yes» is not a VOTE line on D1, «VOTE D1 yes» is",
              not vote.match("VOTE D١ yes") and vote.match("VOTE D1 yes"))
        check("D2: AMENDMENT_١.md and OUTCOME_round_١.json are not the names of amendment 1 and round 1 (the second "
              "is refused)", not V.AMENDMENT_RE.fullmatch("AMENDMENT_١.md") and V.AMENDMENT_RE.fullmatch("AMENDMENT_1.md")
              and raises(C.localize_path, "OUTCOME_round_١.json", "it", "jury") == "Error")
    # through the command line: select refuses H-٠٠١ and briefs nothing
    c = s.classic(rules=3)
    s.gate_ok(c, "f2")
    rc, out = s.run("select", c, "H-٠٠١")
    check(f"{L}: select H-٠٠١ is refused and selects nothing (it is not H-001)",
          rc == 1 and not (c / "f3" / "H-001").exists(), out)


NBSP, EMSP = " ", " "   # NO-BREAK SPACE and EM SPACE: \s in Unicode, not in ASCII


def d2_spaces(s: T.Swarm, base: Path):
    """The 5.3.1 repair round (jury 20261121-jury-engine-5-3-1, round 0): D2 makes the digits ASCII and nothing else.
    Each case below fails at the rejected pin (re.ASCII on the near detectors and on PLACEHOLDER) and holds in 5.3.0."""
    if s.lang != "en":
        return
    import jury as J
    import professionals as P
    import extensions as E
    L = "D2 spaces"

    def count_error(line: str) -> bool:
        try:
            J.valid_lines(f"VOTE D1 yes\n{line}\n", "VOTE_x.md", set(J.VOTE_WORDS), J.L5)
        except J.Error:
            return True
        return False

    for line in (f"VOTE{NBSP}D1 no", f"CLASS{NBSP}D1 plenary", f"PREFER{NBSP}D1 (c)", "PREFER D١ (c)", "VOTE D١ no",
                 f"{NBSP}VOTE D1 no", f"PREFER{EMSP}D1 (c)", f"VOTE{EMSP}D1 no", f"VOTO{NBSP}D1 no",
                 f"CLASSE{NBSP}D1 plenaria"):
        check(f"{L}: {line!a} is near-conforming, an error of the count (JURY.md §3), not prose",
              J.L5.near.match(line) is not None and count_error(line), line)
    check(f"{L}: control: «PREFER: D1 (c)» is an error, «I vote for D1» is prose",
          count_error("PREFER: D1 (c)") and not count_error("I vote for D1"))
    got = raises(J.valid_lines, f"VOTE D1 no{NBSP}\n", "VOTE_x.md", set(J.VOTE_WORDS), J.L5) or \
        J.valid_lines(f"VOTE D1 no{NBSP}\n", "VOTE_x.md", set(J.VOTE_WORDS), J.L5)
    check(f"{L}: a trailing NBSP after «VOTE D1 no» conforms, as in 5.3.0 (\\s*$ is Unicode)",
          got == [("VOTE", ("D1", "no"))], got)
    h = "0" * 64
    for line in (f"SEAL{NBSP}round_0/PROPOSAL.md {h}", f"SEAL{EMSP}PROPOSAL.md {h}", f"{NBSP}SEAL round_0/x.md {h}",
                 f"INCOMPATIBLE-VERIFIED{NBSP}round_0 D1", "INCOMPATIBLE-VERIFIED round_0 D١"):
        ok = J.SEAL_NEAR.match(line) is not None and not J.SEAL_L5.match(line) and not J.VERIFIED_L5.match(line)
        check(f"{L}: SEAL_NEAR: {line[:40]!a} is a non-conforming seal line, an error", ok, line)
    check(f"{L}: control: «SEAL round_0/PROPOSAL.md <sha>» and «INCOMPATIBLE-VERIFIED round_0 D1<NBSP>» conform",
          J.SEAL_L5.match(f"SEAL round_0/PROPOSAL.md {h}") and J.VERIFIED_L5.match(f"INCOMPATIBLE-VERIFIED round_0 D1{NBSP}"))
    for text in (f"DELEGATED{NBSP}D1\n", f"DELEGATED{EMSP}D1\n", "DELEGATED D١\n", f"{J.W['DELEGATED']}{NBSP}D1\n"):
        got = raises(J._protocol_lines, text, "DELEGATION.md", J.DELEGATED_L5, J.DELEGATED_NEAR)
        check(f"{L}: DELEGATED_NEAR: {text.strip()!a} is an error, not prose", got == "Error", got)
    got = raises(J._protocol_lines, f"DELEGATED D1{NBSP}\n", "DELEGATION.md", J.DELEGATED_L5, J.DELEGATED_NEAR) or \
        J._protocol_lines(f"DELEGATED D1{NBSP}\n", "DELEGATION.md", J.DELEGATED_L5, J.DELEGATED_NEAR)
    check(f"{L}: control: «DELEGATED D1<NBSP>» conforms", got == [("DELEGATED", ("D1",))], got)
    # the placeholder check of the gates (ENG-25): unfilled() and full()
    for ph in V.TO_FILL:
        for text in (f"Goal:{NBSP}{ph}", f"Results:{NBSP}{ph}", f"Results: {ph}{NBSP}", f"{NBSP}{ph}", f"{ph}{NBSP}",
                     f"Results: {ph}{EMSP}", f"Goal:{EMSP}{ph}", f"{EMSP}Results: {ph}", f"١. {ph}",
                     f"-{NBSP}{ph}"):
            check(f"{L}: unfilled({text!a}) is True: the field is left to fill in", V.unfilled(text + "\n"), text)
        check(f"{L}: control: «Results: {ph}» unfilled, «Results: done» and a quoted `{ph}` filled",
              V.unfilled(f"Results: {ph}\n") and not V.unfilled("Results: done\n")
              and not V.unfilled(f"the mark `{ph}` is quoted\n"))
    f = base / "nbsp-deliverable.md"
    f.write_text(f"Results:{NBSP}{V.TO_FILL[0]}\n", encoding="utf-8")
    check(f"{L}: full() refuses a deliverable whose only field is «Results:<NBSP>{V.TO_FILL[0]}»", not V.full(f))
    f.unlink()
    # the ids stay ASCII, beside Unicode spaces too
    for x in (ARABIC, FULLWIDTH):
        check(f"{L}: {x!a} is no id, between NBSPs too", V.ID.findall(f"{NBSP}{x}{NBSP}") == []
              and raises(V.norm_id, x) == "Error", V.ID.findall(f"{NBSP}{x}{NBSP}"))
    check(f"{L}: control: H-035 between NBSPs is H-035", V.ID.findall(f"{NBSP}H-035{NBSP}") == ["35"])
    check(f"{L}: KID: «K-004-٣» is not K-004 (the lookahead refuses any digit, as in 5.3.0); K-004 is",
          V.KID.findall("K-004-٣") == [] and V.KID.findall("K-004") == ["4"], V.KID.findall("K-004-٣"))
    row = "| {} | conv | coordinator | `new-expert` | x | a reason long enough |"
    check(f"{L}: a register row dated in Arabic-Indic digits is a row (TABLE_ROW) that does not conform (an error)",
          J.TABLE_ROW.match(row.format("٢٠٢٦-١١-٢١")) and not J.REQUEST_ROW.match(row.format("٢٠٢٦-١١-٢١")))
    check(f"{L}: control: a register row padded with NBSPs is a conforming row, as in 5.3.0",
          J.TABLE_ROW.match(f"|{NBSP}2026-11-21 | x |")
          and J.REQUEST_ROW.match(row.format("2026-11-21").replace("| ", f"|{NBSP}", 1)))
    title = "### 22. Developer — `swarmer-developer`"
    check(f"{L}: a card title with a trailing NBSP is a title, as in 5.3.0; one numbered ٢٢ is not",
          P.TITLE.match(title + NBSP) and not P.TITLE.match(title.replace("22", "٢٢")))
    check(f"{L}: «>=<NBSP>5.3» is a requirement, «>= ٥.٣» is not", E.REQ.match(f">={NBSP}5.3")
          and not E.REQ.match(">= ٥.٣"))
    check(f"{L}: a 4.0 seal line with a trailing NBSP conforms, one on giro_١ does not",
          C.L4["seal"].match(f"SIGILLO giro_1/PROPOSTA.md {h}{NBSP}")
          and not C.L4["seal"].match(f"SIGILLO giro_١/PROPOSTA.md {h}"))


def d2_ktoken(s: T.Swarm, base: Path):
    """The 5.3.1 second repair round (jury 20261121-jury-engine-5-3-1b, round 0): KTOKEN is a detector, so it keeps \\d
    as in 5.3.0. A G4 under the rules 3 warns on a K# token with a non-ASCII digit that the registry does not hold
    (_unallocated), and stays silent on the allocated K-001 in its three forms."""
    if s.lang != "en":
        return
    L = "D2 KTOKEN"
    c = s.classic(rules=3)
    s.gate_ok(c, "f2")
    assert s.run("select", c, "H-001")[0] == 0
    s.f3(c, "H-001")
    a = T.role_dir(c / "f3" / "H-001", "01-") / s.N("SOLUTION.md")
    assert s.run("contradiction", c, a, "--question", "is the bound tight?")[0] == 0
    check(f"{L}: the registry holds K-001 alone", list(V.contradictions(V.Convening(c))) == ["K-001"],
          list(V.contradictions(V.Convening(c))))
    s.f4_r3(c, "H-001", correctness="proven")
    vp = T.role_dir(c / "f4" / "H-001", "09-") / s.N("VERDICT.md")
    base_text = vp.read_text(encoding="utf-8")
    for tok, warned in (("K-٠٠٧", True), ("K-００７", True), ("K-007٣", True), ("K-001-٣", True), ("K-007", True),
                        ("K-001", False), ("K-1", False), ("K-01", False)):
        vp.write_text(base_text + f"{tok} is open\n", encoding="utf-8")
        rc, out = s.verify(c, "f4/H-001")
        hit = f"{tok} cited in" in out and "not allocated" in out
        check(f"{L}: G4 {'warns' if warned else 'does not warn'} on «{tok}» cited with the registry {{K-001}}",
              rc == 0 and hit == warned and ("not allocated" in out) == warned, (rc, out))
    vp.write_text(base_text, encoding="utf-8")


def d2_closed(s: T.Swarm, base: Path):
    """The 5.3.1 third repair round (jury 20261121-jury-engine-5-3-1c, round 0, avversario A1-A4): where 5.3.0 refused
    a text with a non-ASCII digit, 5.3.1 refuses it too, with an error that says so; each check fails at the pin
    4f208551…6670 and passes after. tests/test_engine531_diff.py checks every other site against 5.3.0."""
    L = f"D2 closed [{s.lang}]"
    import paths as S
    import professionals as P
    # A4: a briefed role folder renamed in non-ASCII digits after its deliverable is removed: G4 refused, not «holds»
    c = s.classic(rules=2)
    s.gate_ok(c, "f2")
    assert s.run("select", c, "H-001")[0] == 0
    s.f3(c, "H-001")
    out4 = s.f4(c, "H-001", correctness="refuted")
    d03 = out4["03"].parent
    out4["03"].unlink()
    for digits in ("٠٣", "０３"):
        moved = d03.parent / f"{digits}{d03.name[2:]}"
        d03.rename(moved)
        try:
            rc, out = s.verify(c, "f4/H-001")
        finally:
            moved.rename(d03)
        check(f"{L}: A4: G4 refuses f4/H-001/{moved.name} without its deliverable, naming the non-ASCII digits "
              "(5.3.0 refused it as a missing deliverable, the pin let it pass)",
              rc == 1 and "non-ASCII digits" in out and "Traceback" not in out, out)
    rc, out = s.verify(c, "f4/H-001")
    check(f"{L}: A4 control: the ASCII folder without its deliverable is refused as before", rc == 1
          and f"no deliverable of {d03.name[3:]}" in out, out)
    out4["03"].write_text("done\n", encoding="utf-8")
    rc, out = s.verify(c, "f4/H-001")
    check(f"{L}: A4 control: with its deliverable back G4 holds", rc == 0, out)
    # A1: G2 and a selection naming an H# in non-ASCII digits that the triage does not have
    c = s.classic(rules=2)
    sel = c / "f2" / s.N("05-selection") / s.N("SELECTION.md")
    text = sel.read_text(encoding="utf-8")
    for h in ("H-٠٠٩", "H-００９"):
        sel.write_text(text + f"also {h}\n", encoding="utf-8")
        rc, out = s.verify(c, "f2")
        check(f"{L}: A1: G2 refuses a selection that names {h}, naming the non-ASCII digits (5.3.0 refused it as an H# "
              "outside the triage, the pin let it pass)", rc == 1 and "non-ASCII digits" in out, out)
    sel.write_text(text + "also H-009\n", encoding="utf-8")
    rc, out = s.verify(c, "f2")
    check(f"{L}: A1 control: the ASCII H-009 outside the triage is refused as before",
          rc == 1 and "the triage does not have: H-009" in out, out)
    sel.write_text(text, encoding="utf-8")
    rc, out = s.verify(c, "f2")
    check(f"{L}: A1 control: the selection as it was holds", rc == 0, out)
    if s.lang != "en":
        return
    # A2: a local card numbered in non-ASCII digits does not vanish into the previous card
    f = base / "AGENTS-local.md"
    card = "### {}. {} — `swarmer-{}`\n\n- **In short:** {}\n\n"
    for n in ("٢", "２"):
        f.write_text(card.format(1, "Alpha", "loc-a", "a") + card.format(n, "Beta", "loc-b", "b"), encoding="utf-8")
        got = raises(P.local_cards, f)
        check(f"{L}: A2: local_cards refuses the card «### {n}. Beta» (5.3.0 read it, the pin added it to Alpha's)",
              got == "Error", got)
    f.write_text(card.format(1, "Alpha", "loc-a", "a") + card.format(2, "Beta", "loc-b", "b"), encoding="utf-8")
    check(f"{L}: A2 control: «### 2. Beta» is a card of its own", sorted(P.local_cards(f)) == ["loc-a", "loc-b"],
          sorted(P.local_cards(f)))
    f.unlink()
    # A3: the privacy detector sees a machine path in non-ASCII digits, as 5.3.0 did
    for d in ("١٠٠٠", "１０００", "1000"):   # built here: the source itself carries no machine path (build's check)
        x = f"/tmp/claude-{d}/x"
        got = [m for m in S.public_problems(f"see {x}", []) if m.startswith("machine path")]
        check(f"{L}: A3: public_problems reports the machine path {x!a}", got, got)


def d5(s: T.Swarm, base: Path):
    L = f"D5 [{s.lang}]"
    views = {"INPUTS.md": "# The inputs\n\n| decision | U-0 | x |\n", "ASSEMBLY.json": "{\"a\": 1}\n"}
    # ENG-7a: a role folder with TASK.md and the derived views only has not delivered
    c = s.classic(rules=2)
    s.gate_ok(c, "f2")
    assert s.run("select", c, "H-001", "H-002")[0] == 0
    s.f3(c, "H-001")
    out4 = s.f4(c, "H-001", correctness="refuted")
    d02 = out4["02"].parent
    for b in [x for x in (c / "f4" / "H-001").iterdir() if x.is_dir() and re.match(r"\d\d-", x.name)]:
        for n, t in views.items():
            (b / n).write_text(t, encoding="utf-8")
    out4["02"].unlink()
    role = re.sub(r"^\d+-", "", d02.name)
    rc, out = s.verify(c, "f4/H-001")
    check(f"{L}: G4 refuses a role folder holding only TASK.md, INPUTS.md and ASSEMBLY.json (ENG-7a)",
          rc == 1 and f"no deliverable of {role}" in out, out)
    out4["02"].write_text("done\n", encoding="utf-8")
    rc, out = s.verify(c, "f4/H-001")
    check(f"{L}: with its real deliverable beside INPUTS.md and ASSEMBLY.json the same folder has delivered", rc == 0, out)
    # early closure: the brief folders of H-002 that hold only TASK.md and the derived views go
    f3 = c / "f3" / "H-002"
    briefs = sorted(x for x in f3.iterdir() if x.is_dir() and re.match(r"\d\d-", x.name))
    for b in briefs:
        for n, t in views.items():
            (b / n).write_text(t, encoding="utf-8")
    kept = briefs[0]
    (kept / s.N("SOLUTION.md")).write_text("a real deliverable\n", encoding="utf-8")
    rc, out = s.run("close-branch", c, "H-002", "--reason", "no time", "--deciding-test", "the oracle on 10 cases")
    gone = [b for b in briefs[1:] if b.exists()]
    check(f"{L}: an early closure removes the f3 brief folders holding only TASK.md, INPUTS.md and ASSEMBLY.json",
          rc == 0 and briefs[1:] and not gone, (out, gone))
    check(f"{L}: and keeps the one with a real deliverable beside them, every file in place",
          (kept / s.N("SOLUTION.md")).is_file() and all((kept / n).is_file() for n in views), out)


# ------------------------------------------------------------------------------------------------------------------
# A1-A7: the acceptance checks of the tester (swarmer-tester), written from impl/NOTES.md items 1-6 and from «Engine
# defects found» 1, 2, 5, 7 of ecc-prompts-portfolio-design's f5/01-arbitro/ACCEPTANCE.md before reading D1-D5 above.
# A1 (defect 1) under the rules 3 with two refuted branches, «not closed» and an open branch; A2 (defect 2) by an own
# AST rule, four non-ASCII digit families, close-branch and gate labels; A5 (defect 5) under the rules 3 and 2, the f3
# and f4 folders, and the folders an early closure must keep; A7 (defect 7) on a real installation; A6 the version.
# They share with the patch the specification and test_engine53's Swarm.
# ------------------------------------------------------------------------------------------------------------------

CLOSED_NO_H = "closed but no H# proven"
AR = "٠٣٥"        # Arabic-Indic 035
FW = "０３５"        # fullwidth 035
EX = "۰۳۵"        # extended Arabic-Indic 035
MATH = "\U0001d7ce\U0001d7d1\U0001d7d3"   # mathematical bold 035


def branch_case(s: T.Swarm, rules=3, ids=("H-001", "H-002")):
    c = s.classic(rules=rules)
    s.gate_ok(c, "f2")
    rc, out = s.run("select", c, *ids)
    assert rc == 0, out
    return c


# ---- A1: defect 1 ----

def a1(s: T.Swarm):
    L = f"A1 [{s.lang}]"
    c = branch_case(s)
    for h in ("H-001", "H-002"):
        s.f3(c, h)
        s.f4_r3(c, h, correctness="refuted")
        s.gate_ok(c, f"f4/{h}")
    s.sentinel(c, phase="f3")
    s.sentinel(c, phase="f4")
    s.sentinel(c)
    CL = s.N("CLOSURE.md")
    rc, out = s.verify(c, "f5")
    check_missing = rc == 1 and CL in out and CLOSED_NO_H not in out
    check(f"{L}: no {CL}: G5 refused for the missing closure only, no «{CLOSED_NO_H}»", check_missing, out)
    p = s.f5(c) / CL
    p.write_text("a closure without its outcome line\n", encoding="utf-8")
    rc, out = s.verify(c, "f5")
    check(f"{L}: {CL} without the outcome line: refused for the line, no «{CLOSED_NO_H}»",
           rc == 1 and C.CONVENE_LINES["outcome"][s.lang] in out and CLOSED_NO_H not in out, out)
    s.closure(c, closed=True)
    rc, out = s.verify(c, "f5")
    check(f"{L}: control: «closed» with no H# proven is still refused with «{CLOSED_NO_H}»",
           rc == 1 and CLOSED_NO_H in out, out)
    s.closure(c, closed=False)
    rc, out = s.verify(c, "f5")
    check(f"{L}: control: «not closed» with every G4 valid holds and never says «{CLOSED_NO_H}»",
           rc == 0 and CLOSED_NO_H not in out, out)
    # the check of the branches without G4 stays as before for a missing outcome
    g = s.gate_file(c, "f4/H-002")
    keep = g.read_bytes()
    g.unlink()
    p.unlink()
    try:
        rc, out = s.verify(c, "f5")
        check(f"{L}: no {CL} and a branch without G4: the open branch is still reported, no «{CLOSED_NO_H}»",
               rc == 1 and "without a valid G4" in out and "H-002" in out and CLOSED_NO_H not in out, out)
    finally:
        g.write_bytes(keep)


# ---- A2: defect 2 ----

ACC_FLAG_POS = {"compile": 1, "match": 2, "fullmatch": 2, "search": 2, "findall": 2, "finditer": 2, "split": 3,
            "sub": 4, "subn": 4}


def _acc_has_ascii(node) -> bool:
    return any(isinstance(x, ast.Attribute) and x.attr in ("ASCII", "A") and isinstance(x.value, ast.Name)
               and x.value.id == "re" for x in ast.walk(node))


def _digit_literal(node) -> bool:
    return any(isinstance(x, ast.Constant) and isinstance(x.value, str) and "\\d" in x.value for x in ast.walk(node))


def _space_literal(node) -> bool:
    return any(isinstance(x, ast.Constant) and isinstance(x.value, str) and UNICODE_CLASS.search(x.value)
               for x in ast.walk(node))


def ascii_sites(root: Path) -> tuple[int, list[str]]:
    """Every call re.<f>(pattern, …) of engine/*.py whose pattern holds a literal \\d: those that read a Unicode digit
    outside the DETECTORS (no re.ASCII, \\d outside a negative lookaround), and those whose re.ASCII would also make a
    literal \\s, \\b or \\w of the pattern ASCII (the 5.3.1 repair round)."""
    n, bad = 0, []
    for f in sorted((root / "engine").glob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        names = assigned_names(tree)
        for x in ast.walk(tree):
            if not (isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr in ACC_FLAG_POS
                    and isinstance(x.func.value, ast.Name) and x.func.value.id == "re"):
                continue
            pat = x.args[0] if x.args else next((k.value for k in x.keywords if k.arg == "pattern"), None)
            if pat is None or not _digit_literal(pat):
                continue
            n += 1
            i = ACC_FLAG_POS[x.func.attr]
            flags = x.args[i] if len(x.args) > i else next((k.value for k in x.keywords if k.arg == "flags"), None)
            asc = flags is not None and _acc_has_ascii(flags)
            lits = [y.value for y in ast.walk(pat) if isinstance(y, ast.Constant) and isinstance(y.value, str)]
            if asc and _space_literal(pat):
                bad.append(f"{f.name}:{x.lineno} re.ASCII with \\s/\\b/\\w")
            elif not asc and names.get(id(x)) not in DETECTORS and any(DIGIT.search(NEG_LOOK.sub("", v)) for v in lits):
                bad.append(f"{f.name}:{x.lineno} Unicode \\d")
    return n, bad


def raises(f, *a):
    try:
        f(*a)
    except Exception as e:  # noqa: BLE001
        return type(e).__name__
    return None


def a2_inproc():
    L = "A2"
    n, bad = ascii_sites(SOURCE)
    check(f"{L}: every re call of engine/*.py with a literal \\d reads ASCII digits outside the detectors, and no "
          f"re.ASCII makes its \\s, \\b or \\w ASCII ({n} sites)", n >= 20 and not bad, bad)
    for name, d in (("Arabic-Indic", AR), ("fullwidth", FW), ("extended Arabic-Indic", EX), ("math bold", MATH)):
        check(f"{L}: norm_id refuses H-<{name} 035>", raises(V.norm_id, f"H-{d}") == "Error", raises(V.norm_id, f"H-{d}"))
        check(f"{L}: ID finds no H# in H-<{name} 035>", V.ID.findall(f"H-{d}") == [], V.ID.findall(f"H-{d}"))
    for form in ("H-035", "h-35", "H35", "H-0035", " H-035 "):
        check(f"{L}: control: norm_id({form!r}) is H-035", raises(V.norm_id, form) is None
               and V.norm_id(form) == "H-035", raises(V.norm_id, form))
    check(f"{L}: ID finds only the ASCII H-035 beside an Arabic-Indic one", V.ID.findall(f"H-{AR} H-035") == ["35"],
           V.ID.findall(f"H-{AR} H-035"))
    check(f"{L}: KID finds no K# in K-<Arabic-Indic 004>, finds K-004", V.KID.findall("K-٠٠٤ K-004")
           == ["4"], V.KID.findall("K-٠٠٤ K-004"))
    check(f"{L}: KTOKEN, a detector, takes the Arabic-Indic K token whole, and KID reads no K# in it",
           V.KTOKEN.findall("K-١-٢") == ["K-١-٢"] and V.KID.findall("K-١-٢") == [], V.KTOKEN.findall("K-١-٢"))
    check(f"{L}: round_<Arabic-Indic 2> is not a round token, round_2 is",
           C.ROUND_TOKEN_RE.match("round_٢") is None and C.ROUND_TOKEN_RE.match("round_2") is not None)
    for lang in ("it",):
        got, ctl = raises(C.localize_path, "agent-٣", lang, "convene"), C.localize_path("agent-3", lang, "convene")
        check(f"{L}: agent-<Arabic-Indic 3> is not localized as an agent folder (it is refused), agent-3 is",
               got == "Error" and ctl == "agente-3", (got, ctl))
        got = raises(C.canonical_path, "agente-٣", "convene")
        check(f"{L}: agente-<Arabic-Indic 3> has no canonical agent name (it is refused)", got == "Error", got)
    am = [p for p in C.CONVENE_PATTERNS if p[1].startswith("AMENDMENT")][0]
    check(f"{L}: AMENDMENT_A<Arabic-Indic 1>.md is not an amendment, AMENDMENT_A1.md is",
           V.AMENDMENT_RE.fullmatch(am[1].format("A١")) is None
           and V.AMENDMENT_RE.fullmatch(am[1].format("A1")) is not None)
    import jury as J
    lex = J.Lexicon(5)
    for word in ("VOTE", C.JURY_WORDS["VOTE"] if hasattr(C, "JURY_WORDS") else J.W["VOTE"]):
        if word not in lex.lines:
            continue
        rx = lex.lines[word][1]
        val = next((v for v in ("yes", "si", "sì", "no") if rx.match(f"{word} D1 {v}")), None)
        check(f"{L}: «{word} D<Arabic-Indic 1> {val}» is not a protocol line, «{word} D1 {val}» is",
               val is not None and rx.match(f"{word} D١ {val}") is None, (word, val))
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        (d / "OUTCOME_round_1.json").write_text("{}\n", encoding="utf-8")
        got = [r for r, _p in J.outcome_files(d)]
        (d / "OUTCOME_round_٢.json").write_text("{}\n", encoding="utf-8")
        bad = raises(J.outcome_files, d)
        check(f"{L}: outcome_files reads OUTCOME_round_1.json, and refuses OUTCOME_round_<Arabic-Indic 2>.json beside it "
              "(it does not skip it)", got == [1] and bad == "Error", (got, bad))
    check(f"{L}: \\b stays Unicode, as in 5.3.0: «éH-035» holds no H#", V.ID.findall("éH-035") == [],
           V.ID.findall("éH-035"))


def a2_cli(s: T.Swarm):
    L = f"A2 [{s.lang}]"
    c = s.classic(rules=3)
    s.gate_ok(c, "f2")
    rc, out = s.run("select", c, f"H-٠٠١")
    check(f"{L}: select H-<Arabic-Indic 001> is refused and briefs nothing",
           rc == 1 and not (c / "f3" / "H-001").exists() and "Traceback" not in out, out)
    rc, out = s.run("select", c, f"H-{FW[:1]}{FW[:1]}１")
    check(f"{L}: select H-<fullwidth 001> is refused", rc == 1 and not (c / "f3" / "H-001").exists(), out)
    rc, out = s.run("select", c, "H-001", "H-002")
    check(f"{L}: after the refusals, select H-001 H-002 briefs both", rc == 0 and (c / "f3" / "H-002").is_dir(), out)
    rc, out = s.run("close-branch", c, "H-٠٠٢", "--reason", "x", "--deciding-test", "t")
    check(f"{L}: close-branch H-<Arabic-Indic 002> is refused and closes nothing",
           rc == 1 and not (c / "f3" / "H-002" / s.N("EARLY_CLOSURE.json")).exists(), out)
    for ph in ("f4/H-٠٠١", "A١"):
        rc, out = s.verify(c, ph)
        check(f"{L}: gate {ph!a} is an unknown phase", rc == 1 and "unknown phase" in out, out)


# ---- A5: defect 5 ----

def plant_views(d: Path):
    (d / "INPUTS.md").write_text("# inputs\n- the contract, sha12 0123456789ab\n", encoding="utf-8")
    (d / "ASSEMBLY.json").write_text('{"inputs": []}\n', encoding="utf-8")


def a5(s: T.Swarm, rules: int):
    L = f"A5 [{s.lang}] rules {rules}"
    c = branch_case(s, rules=rules)
    s.f3(c, "H-001")
    out = (s.f4_r3 if rules == 3 else s.f4)(c, "H-001", correctness="refuted")
    meas = out["03"]
    folder = meas.parent
    meas.unlink()
    plant_views(folder)
    rc, o = s.verify(c, "f4/H-001")
    check(f"{L}: a role folder with only TASK.md, INPUTS.md and ASSEMBLY.json has no deliverable: G4 refused",
           rc == 1 and "no deliverable of" in o and folder.name in o, o)
    (folder / "INPUTS.md").unlink()
    (folder / "ASSEMBLY.json").unlink()
    (folder / "ASSEMBLY.md").write_text("an output named like a view but not one\n", encoding="utf-8")
    rc, o = s.verify(c, "f4/H-001")
    check(f"{L}: control: another .md (ASSEMBLY.md) still counts as a deliverable", rc == 0, o)
    (folder / "ASSEMBLY.md").unlink()
    plant_views(folder)
    meas.write_text("done\n", encoding="utf-8")
    rc, o = s.verify(c, "f4/H-001")
    check(f"{L}: control: the deliverable beside the views: G4 holds", rc == 0, o)
    # the early closure of the funded H-002, before its G3
    dirs = sorted(t.parent for f in ("f3", "f4") for t in (c / f / "H-002").glob("*/TASK.md"))
    assert len(dirs) >= 4, dirs
    nested, extra, changed, plain = dirs[0], dirs[1], dirs[2], dirs[3]
    for d in dirs:
        if d != plain:
            plant_views(d)
    (nested / s.N("work")).mkdir()
    (nested / s.N("work") / "INPUTS.md").write_text("a copy, nested\n", encoding="utf-8")
    (extra / "notes.txt").write_text("a role's own file\n", encoding="utf-8")
    (changed / "TASK.md").write_text((changed / "TASK.md").read_text(encoding="utf-8") + "edited\n", encoding="utf-8")
    rc, o = s.run("close-branch", c, "H-002", "--reason", "measured inside H-001", "--deciding-test", "the oracle")
    gone = [d for d in dirs if not d.exists()]
    kept = [d for d in dirs if d.exists()]
    if rules >= 2:
        want_gone = [d for d in dirs if d not in (nested, extra, changed)]
        check(f"{L}: the early closure removes the brief folders holding only TASK.md and the derived views "
               f"({len(want_gone)} folders)", rc == 0 and sorted(gone) == sorted(want_gone),
               (o, [str(d.relative_to(c)) for d in kept]))
        check(f"{L}: control: it keeps a folder with a nested work/INPUTS.md, one with a file of its own, and one "
               f"whose TASK.md changed", nested.is_dir() and extra.is_dir() and changed.is_dir(),
               [str(d.relative_to(c)) for d in gone])
    check(f"{L}: the closure is recorded", (c / "f3" / "H-002" / s.N("EARLY_CLOSURE.json")).is_file(), o)


# ---- A7: defect 7 ----

def a7(s: T.Swarm):
    L = f"A7 [{s.lang}]"
    import swarmer as SW
    import test_crossroads as X
    dst = s.base / f"toy-of-installed-{s.lang}"
    if hasattr(X, "toy_copy"):
        X.toy_copy(s.swarm, dst)
    else:   # 5.3.0's ignore list
        shutil.copytree(s.swarm, dst, ignore=shutil.ignore_patterns(".git", "__pycache__", "tests", "swarmer.sh",
                                                                    "sciame.sh"))
    check(f"{L}: the toy copy of a real installed swarm ({s.swarm.name}) is not installed",
           SW.installed(s.swarm) and not SW.installed(dst), (SW.installed(s.swarm), sorted(x.name for x in dst.iterdir())))
    shutil.rmtree(dst)


# ---- A6: the version ----

def a6():
    L = "A6"
    plugin = json.loads((SOURCE / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    check(f"{L}: plugin.json is 5.3.1", plugin.get("version") == "5.3.1", plugin.get("version"))
    for name in ("CHANGELOG.md", "CHANGELOG.it.md"):
        t = (SOURCE / name).read_text(encoding="utf-8")
        heads = re.findall(r"^## (\S+)", t, re.M)
        check(f"{L}: {name} opens with 5.3.1, then 5.3.0", heads[:2] == ["5.3.1", "5.3.0"], heads[:3])
    import generate as G
    check(f"{L}: the engine version stays 5.3 (no format or gate changed)", G.VERSION == "5.3", G.VERSION)
    rc, out = T.py(SOURCE / "engine" / "swarmer.py", "--swarm", SOURCE, "build", "--check")
    check(f"{L}: build --check: swarmer.sh is up to date", rc == 0, out)


def acc_once(s: T.Swarm, base: Path):
    if s.lang == "en":
        a2_inproc()
        a6()


def acc_a5(s: T.Swarm, base: Path):
    a5(s, 3)
    a5(s, 2)


def acc_a1(s: T.Swarm, base: Path):
    a1(s)


def acc_a2(s: T.Swarm, base: Path):
    a2_cli(s)


def acc_a7(s: T.Swarm, base: Path):
    a7(s)


ACC_TESTS = (acc_once, acc_a1, acc_a2, acc_a5, acc_a7)


TESTS = (d1, d2, d2_spaces, d2_ktoken, d2_closed, d5, *ACC_TESTS)


def main():
    only = set(sys.argv[1:])
    with tempfile.TemporaryDirectory() as b:
        base = Path(b)
        for lang in ("en", "it"):
            s = T.Swarm(base, lang)
            for t in TESTS:
                if only and t.__name__ not in only:
                    continue
                try:
                    t(s, base)
                except Exception:  # noqa: BLE001
                    check(f"{t.__name__} [{lang}] ran to the end", False, traceback.format_exc())
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
