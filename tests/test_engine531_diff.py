#!/usr/bin/env python3
"""The differential test of swarmer 5.3.1 against 5.3.0 (third repair round): python3 -I -B tests/test_engine531_diff.py

5.3.1 makes the id regexes of the engine read ASCII digits only (defect 2). A regex that 5.3.0 used as a check could
then stop seeing a text, and the check passed in silence where 5.3.0 refused (jury 20261121-jury-engine-5-3-1c). This
test reads 5.3.0's engine with `git show 40848fb:engine/<file>` (read only) into a temporary folder, and runs the same
probes on both engines, each in a process of its own:

- SITES lists every regex the 5.3.1 diff changed in engine/, and every regex built at runtime from them; a static check
  recomputes the changed regexes from the two sources (re calls, and literals with \\d or [0-9]) and fails on one that
  no site claims;
- each site has a probe that drives the code that reads the regex, on a generated corpus: the numbers the site reads,
  written in ASCII, Arabic-Indic, Extended Arabic-Indic, fullwidth, Devanagari and superscript digits, whole or mixed
  with ASCII, and Unicode spaces where the site reads a space;
- the rule, for every site and every string: on a string whose read digits are all ASCII, 5.3.1 gives 5.3.0's result;
  on a string with a non-ASCII digit where 5.3.0 matched (a value, or an error), 5.3.1 refuses with an error (a
  warning only at the one site whose 5.3.0 output is itself a warning), never the value, never silence; where 5.3.0
  did not match, 5.3.1 does not match either or refuses.

Without the git history of the source tree (an installation) the test says so and checks nothing. Exits with 1 if a
check fails.
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import os
import re
import subprocess
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent
REV = "40848fb"   # swarmer 5.3.0
sys.dont_write_bytecode = True

FAMILIES = {
    "ascii": "0123456789",
    "arabic-indic": "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669",
    "ext-arabic-indic": "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9",
    "fullwidth": "\uff10\uff11\uff12\uff13\uff14\uff15\uff16\uff17\uff18\uff19",
    "devanagari": "\u0966\u0967\u0968\u0969\u096a\u096b\u096c\u096d\u096e\u096f",
    "superscript": "\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079",   # not \d: the control
}
SPACES = {"space": " ", "nbsp": "\u00a0", "emsp": "\u2003", "ideographic": "\u3000", "none": ""}
SHA = "0" * 64
TWIN = "\u0436"   # CYRILLIC SMALL LETTER ZHE: \w and not \d, as a non-ASCII digit is for a strict regex

results: list[tuple[str, bool]] = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("ok   " if ok else "FAILED ") + name + ("" if ok or not detail else f"\n     {str(detail)[:2500]}"),
          flush=True)


def non_ascii_digit(s: str) -> bool:
    return any(c.isdecimal() and c not in "0123456789" for c in s)


def renders(v: str):
    """The number `v` (ASCII) in every family, whole, and mixed with ASCII (first digit or the others)."""
    for fam, digits in FAMILIES.items():
        t = v.translate(str.maketrans("0123456789", digits))
        yield fam, t
        if fam != "ascii" and sum(c.isdigit() for c in v) > 1:
            i = next(k for k, c in enumerate(v) if c.isdigit())
            yield fam + "+ascii", v[:i + 1] + t[i + 1:]
            yield "ascii+" + fam, t[:i + 1] + v[i + 1:]


def corpus(templates, values):
    """(text, wide, twin): each template with {n} the number and {s} a space; wide when a digit of the number is not
    ASCII, and then twin is the same text with each such digit written «ж», a letter that is \\w like a digit and in no
    ASCII class: where 5.3.0 gives the twin the result it gives the text, it did not read those digits."""
    out = []
    for tpl in templates:
        for v in values:
            for _fam, d in renders(v):
                for sp in (SPACES.values() if "{s}" in tpl else [""]):
                    if sp and non_ascii_digit(d):
                        continue   # the spaces with the ASCII number and the plain one: the space alone is read
                    wide = "{n}" in tpl and non_ascii_digit(d)
                    twin = tpl.format(n="".join(TWIN if non_ascii_digit(c) else c for c in d), s=sp) if wide else None
                    out.append((tpl.format(n=d, s=sp), wide, twin))
    return list(dict.fromkeys(out))


# --------------------------------------------------------------------------------------------------------------------
# The sites: (id, file, function or <module>, fragments of the changed regex items it claims, class, probe); a fragment
# «=x» claims the item x alone. The class says what 5.3.1 does where 5.3.0 read a non-ASCII digit: «explicit» it
# refused already before this round, «fixed» this round makes it refuse, «detector» its \d is Unicode as in 5.3.0 (a
# warning or a problem, as 5.3.0 gave), «new» a regex this round adds to refuse.
# --------------------------------------------------------------------------------------------------------------------

SITES = [
    # compat.py
    ("C1 ROUND_TOKEN_RE", "compat.py", "<module>", ("(?:giro|round)_(\\d+)$",), "explicit", "seals_l5"),
    ("C2 L4 seal", "compat.py", "<module>", ("SIGILLO ((?:giro_",), "fixed", "seals_l4"),
    ("C3 L4 verified", "compat.py", "<module>", ("INCOMPATIBILE-VERIFICATO (giro_",), "fixed", "seals_l4"),
    ("C4 _key_map", "compat.py", "_key_map", ("key[len(src_p):]", "=\\d+"), "fixed", "key_map"),
    ("C5 _name_in (CONVENE_PATTERNS, JURY_PATTERNS)", "compat.py", "_name_in", ("re.fullmatch(crx", "re.compile(crx"),
     "fixed", "localize"),
    ("C6 _name_canonical (CONVENE_PATTERNS, JURY_PATTERNS)", "compat.py", "_name_canonical",
     ("re.fullmatch(irx", "re.compile(irx"), "fixed", "canonical"),
    ("C7 NUMBER (new)", "compat.py", "<module>", ("NUMBER = ", 're.compile(r"\\d+", re.ASCII)', "=\\d+"), "new",
     "key_map"),
    ("C8 NON_ASCII_DIGIT (new)", "compat.py", "<module>", ("[^\\D0-9]",), "new", "key_map"),
    ("C9 wide, the 5.3.0 form of a strict regex (new)", "compat.py", "wide", ("=[0-9]", "=\\d", "rx.pattern.replace"),
     "new", "key_map"),
    # convene.py
    ("V1 ID", "convene.py", "<module>", ("\\bH-?0*(",), "fixed", "ids_in"),
    ("V2 KID", "convene.py", "<module>", ("\\bK-0*(",), "fixed", "k_ids_in"),
    ("V2b KID read through KTOKEN (_unallocated)", "convene.py", "_unallocated", (), "detector", "unallocated"),
    ("V3 norm_id", "convene.py", "norm_id", ("H-?0*(\\d{1,3})",), "explicit", "norm_id"),
    ("V4 AMENDMENT_RE (built from CONVENE_PATTERNS)", "convene.py", "<module>", ('p[1].startswith("AMENDMENT")',),
     "fixed", "amendments"),
    ("V5 swarmer_version", "convene.py", "swarmer_version", ("\\d+\\.\\d+",), "fixed", "version_file"),
    ("V6 amendment_phases (GATE_A)", "convene.py", "amendment_phases", ("GATE_A\\d+\\.json",), "fixed", "gate_files"),
    ("V7 _role_folder", "convene.py", "_role_folder", ("\\d+-",), "fixed", "role_folder"),
    ("V8 _bind", "convene.py", "_bind", ("\\d+-",), "fixed", "bind"),
    ("V9 fingerprints (A<n>)", "convene.py", "fingerprints", ("A\\d+",), "fixed", "fingerprints"),
    ("V10 arbiter_verdict", "convene.py", "arbiter_verdict", ("\\d+-",), "fixed", "arbiter"),
    ("V11 _role_of", "convene.py", "_role_of", ("^\\d+-",), "fixed", "role_of"),
    ("V12 team", "convene.py", "team", ("\\d+-",), "fixed", "team"),
    ("V13 conditions (A<n>)", "convene.py", "conditions", ("A\\d+",), "fixed", "conditions_amend"),
    ("V14 _g4_rules2 (the briefed role folders, A4)", "convene.py", "_g4_rules2", ("\\d\\d-",), "fixed",
     "g4_deliverable"),
    ("V15 _g4_rules2 (the V2 audits)", "convene.py", "_g4_rules2", ("=\\d+-", "p.relative_to(folder).parts[0]"),
     "fixed", "g4_audit"),
    ("V16 _order_rules3", "convene.py", "_order_rules3", ("\\d\\d-",), "fixed", "order_rules3"),
    ("V17 gate (A<n>)", "convene.py", "gate", ("[Aa]?(\\d+)",), "explicit", "gate_label"),
    ("V18 gate (the phase)", "convene.py", "gate", ("f[0125]|f[34]/H-\\d{3}|A\\d+",), "explicit", "gate_label"),
    ("V19 _convened", "convene.py", "_convened", ("\\d+-",), "fixed", "convened"),
    ("V20 _sentinel_brief", "convene.py", "_sentinel_brief", ("\\d+-",), "fixed", "sentinel_brief"),
    ("V21 ROLE_DIR, ROLE_DIR_2 (new)", "convene.py", "<module>",
     ("ROLE_DIR", "=^\\d+-", "=^\\d\\d-", 're.compile(r"^\\d+-"', 're.compile(r"^\\d\\d-"'), "new", "role_of"),
    ("V22 AMENDMENT_LABEL (new)", "convene.py", "<module>", ("AMENDMENT_LABEL", "=A\\d+", 're.compile(r"A\\d+"'),
     "new", "fingerprints"),
    ("V23 GATE_AMENDMENT (new)", "convene.py", "<module>",
     ("GATE_AMENDMENT", "=GATE_A\\d+\\.json", 're.compile(r"GATE_A\\d+'), "new", "gate_files"),
    ("V24 VERSION_NUMBER (new)", "convene.py", "<module>",
     ("VERSION_NUMBER", "=\\d+\\.\\d+", 're.compile(r"\\d+\\.\\d+"'), "new", "version_file"),
    # extensions.py
    ("E1 VERSION_RE", "extensions.py", "<module>", ("VERSION_RE", 're.compile(r"^\\d+\\.\\d+$"'), "explicit",
     "ext_validate"),
    ("E2 REQ", "extensions.py", "<module>", ("REQ = ", "^>=\\s*("), "explicit", "ext_validate"),
    # jury.py
    ("J1 ID_EN (and the lexicon lines built from it)", "jury.py", "<module>",
     ("=(D[0-9][0-9A-Za-z_.-]*)", "=(D\\d[0-9A-Za-z_.-]*)"), "explicit", "lexicon"),
    ("J2 VERIFIED_L5", "jury.py", "<module>", ("INCOMPATIBLE-VERIFIED (\\S+) (D",), "explicit", "seals_l5"),
    ("J3 DELEGATED_L5", "jury.py", "<module>", ("^DELEGATED (D",), "explicit", "delegated"),
    ("J4 outcome_files (en)", "jury.py", "outcome_files", ("OUTCOME_round_(\\d+)",), "fixed", "outcomes"),
    ("J5 outcome_files (it, JURY_PATTERNS)", "jury.py", "outcome_files", ("JURY_PATTERNS[2][2]",), "fixed",
     "outcomes"),
    ("J6 REQUEST_ROW", "jury.py", "<module>", ("REQUEST_ROW", "{4}-"), "explicit", "register"),
    ("J7 read_seals (the L4 lines through C.wide)", "jury.py", "read_seals", (), "fixed", "seals_l4"),
    # paths.py: back to 5.3.0's bytes
    ("S1 MACHINE_PATH", "paths.py", "<module>", (), "detector", "machine_path"),
    # professionals.py
    ("P1 TITLE", "professionals.py", "<module>", ("^### (",), "fixed", "local_cards"),
    ("P2 validate (the version)", "professionals.py", "validate", ("^\\d+\\.\\d+$",), "explicit", "db_version"),
]
# Sites whose 5.3.0 output for a non-ASCII digit is a warning, and whose 5.3.1 refusal may be a warning too.
WARN_OK = {"unallocated"}


# --------------------------------------------------------------------------------------------------------------------
# The static part: the regexes that changed between the two sources.
# --------------------------------------------------------------------------------------------------------------------

def regex_items(src: str) -> collections.Counter:
    """(function, text) of every re.<f>(…) call and every string literal with \\d or [0-9] (not a docstring)."""
    tree = ast.parse(src)
    out: collections.Counter = collections.Counter()
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docs.add(id(first.value))

    def visit(node, where):
        for child in ast.iter_child_nodes(node):
            w = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else where
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and \
                    isinstance(child.func.value, ast.Name) and child.func.value.id == "re":
                out[(w, " ".join(ast.get_source_segment(src, child).split()))] += 1
            elif isinstance(child, ast.Assign) and len(child.targets) == 1 and isinstance(child.targets[0], ast.Name) \
                    and isinstance(child.value, ast.Call) and isinstance(child.value.func, ast.Attribute) \
                    and child.value.func.attr == "compile":
                out[(w, child.targets[0].id + " = " + " ".join(ast.get_source_segment(src, child.value).split()))] += 1
            elif isinstance(child, ast.Constant) and isinstance(child.value, str) and id(child) not in docs \
                    and ("\\d" in child.value or "[0-9]" in child.value):
                out[(w, child.value)] += 1
            visit(child, w)

    visit(tree, "<module>")
    return out


def changed_regexes(old: Path, new: Path) -> list[tuple[str, str, str, str]]:
    """(side, file, function, text): the regex items 5.3.1 has and 5.3.0 has not («new»), and the other way («old»)."""
    out = []
    for f in sorted({p.name for p in new.glob("*.py")} | {p.name for p in old.glob("*.py")}):
        a = regex_items((old / f).read_text(encoding="utf-8")) if (old / f).is_file() else collections.Counter()
        b = regex_items((new / f).read_text(encoding="utf-8")) if (new / f).is_file() else collections.Counter()
        out += [("new", f, w, t) for (w, t) in sorted(b - a)] + [("old", f, w, t) for (w, t) in sorted(a - b)]
    return out


def claimed(item, sites=SITES) -> list[str]:
    _side, f, w, t = item
    return [s[0] for s in sites if s[1] == f and s[2] == w
            and any(t == x[1:] if x.startswith("=") else x in t for x in s[3])]


# --------------------------------------------------------------------------------------------------------------------
# The probes, run inside one engine (the child process): each returns ("ok", value), ("none",) or ("warn", …); an
# Error of the engine is ("err", message), another exception ("crash", …).
# --------------------------------------------------------------------------------------------------------------------

class Reached(Exception):
    pass


def _patch(mod, **kw):
    old = {k: getattr(mod, k) for k in kw}
    for k, v in kw.items():
        setattr(mod, k, v)
    return old


def _raise(tag):
    def f(*a, **k):
        raise Reached((tag,) + tuple(str(x) for x in a[1:2]))
    return f


class FakeJury:
    def __init__(self, folder: Path, lexicon):
        self.folder, self.lexicon = folder, lexicon
        self.lang = "it" if lexicon.number == 4 else "en"

    def name(self, canonical):
        return canonical

    def file(self, canonical):
        return self.folder / ("SIGILLI.md" if self.lexicon.number == 4 else "SEALS.md")


def make_probes(E, root: Path):
    C, V, J, P, S, X = E["compat"], E["convene"], E["jury"], E["professionals"], E["paths"], E["extensions"]
    counter = [0]

    def fresh() -> Path:
        counter[0] += 1
        d = root / f"p{counter[0]}"
        d.mkdir()
        return d

    def conv(d: Path):
        m = {"strategy": "classic", "selected": ["H-001"], "radical": None, "f1": {}, "profile": "p", "seed": 1}
        return V.Convening(d, "en", m)

    def some(v):
        return ("ok", v) if v else ("none",)

    def seals(lexicon, line):
        d = fresh()
        for r in range(0, 13):
            (d / f"round_{r}").mkdir()
        j = FakeJury(d, lexicon)
        j.file("SEALS.md").write_text(line + "\n", encoding="utf-8")
        s = J.read_seals(j)
        return some(sorted(map(str, s.files.items())) + sorted(map(str, s.verified)))

    def key_map(x):
        dst = "en" if x.startswith("agente-") else "it"
        v = C._key_map(C.MANIFEST_SCHEMA, ("f1", "*"), x, dst)
        return ("ok", v) if v != x else ("none",)

    def localize(x):
        kind, name = x.split(":", 1)
        v = C.localize_path(name, "it", kind)
        return ("ok", v) if v != name else ("none",)

    def canonical(x):
        kind, name = x.split(":", 1)
        v = C.canonical_path(name, kind)
        return ("ok", v) if v != name else ("none",)

    def ids_in(x):
        p = fresh() / "SELECTION.md"
        p.write_text(x + "\n", encoding="utf-8")
        return some(V.ids_in(p))

    def k_ids_in(x):
        return some(V.k_ids_in(x))

    def unallocated(x):
        d = fresh()
        c = conv(d)
        (d / "MANIFEST.json").write_text("{}\n", encoding="utf-8")
        reg = "".join(json.dumps({"id": k, "time": "2026-11-21T00:00:00+00:00", "question": "q", "files": []}) + "\n"
                      for k in ("K-001", "K-007"))
        c.file("CONTRADICTIONS.jsonl").write_text(reg, encoding="utf-8")
        p = d / "VERDICT.md"
        p.write_text(x + "\n", encoding="utf-8")
        w = V._unallocated(c, [p])
        return ("warn", len(w)) if w else ("ok", "silent")   # silence is the reading of an allocated K#

    def norm_id(x):
        return ("ok", V.norm_id(x))

    def amendments(x):
        d = fresh()
        (d / x).write_text("an amendment\n", encoding="utf-8")
        return some(sorted(V.amendments(conv(d), [])))

    def version_file(x):
        d = fresh()
        (d / "VERSION").write_text(x + "\n", encoding="utf-8")
        old = _patch(V, BASE=d)
        try:
            import generate as G
            v = V.swarmer_version()
            return ("ok", v) if v != G.VERSION else ("none",)
        finally:
            _patch(V, **old)

    def gate_files(x):
        d = fresh()
        (d / x).write_text("{}\n", encoding="utf-8")
        return some(V.amendment_phases(conv(d), []))

    def role_folder(x):
        parent, name = x.split("|")
        return ("ok", True) if V._role_folder(fresh() / "f3" / parent / name) else ("none",)

    def bind(x):
        d = fresh()
        top = d / "f4" / "H-001"
        deep = top / x / "deep"
        deep.mkdir(parents=True)
        for i in range(3):
            (deep / f"{i}.md").write_text(f"{i}\n", encoding="utf-8")
        out = {}
        old = _patch(V, FILES_PER_FOLDER=2)
        try:
            V._bind(top, out, set())
        finally:
            _patch(V, **old)
        return ("ok", "walked") if any(k.endswith("/deep/") for k in out) else ("none",)

    def fingerprints(x):
        d = fresh()
        (d / "AMENDMENT_A3.md").write_text("an amendment\n", encoding="utf-8")
        (d / x).mkdir()
        (d / x / "a.md").write_text("a\n", encoding="utf-8")
        seen = []
        real = V.amendments

        def spy(*a, **k):
            seen.append(1)
            return real(*a, **k)
        old = _patch(V, amendments=spy)
        V._FP.clear()
        try:
            fp = V.fingerprints(conv(d), x)
        finally:
            _patch(V, **old)
        return ("ok", sorted(Path(k).name for k in fp)) if seen else ("none",)

    def arbiter(x):
        d = fresh() / "f4" / "H-001"
        a = d / f"{x}-{C.ROLES['arbiter']}"
        a.mkdir(parents=True)
        (a / "VERDICT.md").write_text("Correctness: refuted\n", encoding="utf-8")
        p = V.arbiter_verdict(conv(d.parent.parent), "H-001", d)
        return ("ok", p.parent.name) if p.is_file() else ("none",)

    def role_of(x):
        v = V._role_of(x)
        return ("ok", v) if v != x else ("none",)

    def team(x):
        d = fresh()
        (d / "f3" / "H-001" / x).mkdir(parents=True)
        return some(sorted(V.team(conv(d), "H-001")))

    def conditions_amend(x):
        d = fresh()
        old = _patch(V, valid=_raise("valid"), g3_holds=_raise("g3_holds"))
        try:
            V.conditions(conv(d), x, set())
        except Reached as r:
            return ("ok", list(r.args[0]))
        finally:
            _patch(V, **old)
        return ("ok", "no gate before")

    def g4(x, proven: bool):
        d = fresh()
        c = conv(d)
        folder = d / "f4" / "H-001"
        a = folder / f"09-{C.ROLES['arbiter']}"
        a.mkdir(parents=True)
        (a / c.name("TASK.md")).write_text("the brief\n", encoding="utf-8")
        (a / c.name("VERDICT.md")).write_text(f"Correctness: {'proven' if proven else 'refuted'}\n", encoding="utf-8")
        r = folder / x
        r.mkdir()
        if proven:
            (r / c.name("HIDDEN_ASSUMPTIONS.md")).write_text("an audit of the hidden assumptions\n", encoding="utf-8")
        else:
            (r / c.name("TASK.md")).write_text("the brief\n", encoding="utf-8")
        old = _patch(V, _f5_now=lambda conv: 1, sentinel_required=lambda conv: False)
        try:
            errors = V._g4_rules2(c, "H-001", folder, set(), [])
        finally:
            _patch(V, **old)
        if proven:
            return ("err", "V2 missing") if any("V2 missing" in e for e in errors) else ("ok", "audited")
        bad = [e for e in errors if "no deliverable" in e]
        return ("err", "no deliverable") if bad else ("none",)

    def order_rules3(x):
        d = fresh()
        c = conv(d)
        folder = d / "f4" / "H-001"
        r = folder / x
        r.mkdir(parents=True)
        (r / c.name("PREDICTIONS.md")).write_text("a prediction\n", encoding="utf-8")
        (r / c.name(V.f4_output(x))).write_text("the output\n", encoding="utf-8")
        old = _patch(V, seal_rows=lambda conv: {}, _whole_seal=lambda rows, p: (1.0, None),
                     _first_seal=lambda rows, p: None)
        try:
            errors = V._order_rules3(c, folder)
        finally:
            _patch(V, **old)
        own = [e for e in errors if "against its own output" in e or f"{x}/{c.name(V.f4_output(x))} is not sealed" in e]
        return ("err", "ordered against its own output") if own else ("none",)

    def gate_label(x):
        d = fresh()
        (d / "MANIFEST.json").write_text(json.dumps({"strategy": "classic", "f1": {}}) + "\n", encoding="utf-8")
        ns = argparse.Namespace(C=str(d), phase=x, rules=None, notes="n", not_delivered=None, verify=True)
        old = _patch(V, conditions=_raise("conditions"), level=lambda conv: 1)
        try:
            V.gate(ns)
        except Reached as r:
            return ("ok", list(r.args[0]))
        finally:
            _patch(V, **old)
        return ("ok", "returned")

    def convened(x):
        d = fresh()
        (d / "f3" / "H-001" / x).mkdir(parents=True)
        used = V._convened(conv(d), {})
        return ("ok", "statistico") if "statistico" in used else ("none",)

    def sentinel_brief(x):
        d = fresh()
        c = conv(d)
        c.m["selected"] = ["H-001", "H-002"]
        (d / "f3" / "H-001" / x).mkdir(parents=True)
        old = _patch(V, gated_amendments=lambda conv: [], _round_dirs=lambda conv: [], level=lambda conv: 1,
                     brief=lambda conv, folder, role, *a, **k: role)
        try:
            role = V._sentinel_brief(c, {"roles": [{"id": "statistico"}]})
        finally:
            _patch(V, **old)
        return ("ok", "drawn elsewhere") if role != "statistico" else ("none",)

    def ext_validate(x):
        version, req = x.split("|")
        d = fresh() / "extensions" / "x"
        d.mkdir(parents=True)
        m = {"name": "x", "version": version, "requires": {"swarmer": req}, "commands": {"c": "engine/c.py"}}
        errs = [e for e in X.validate(d.parent.parent, d, m) if "is not N.M" in e or "requires is" in e]
        return ("err", errs[0][-40:]) if errs else ("ok", "valid")

    words = {}

    def lexicon(x):
        word, rest = x.split("|", 1)
        if not words:
            for canon in J.PROPOSAL_WORDS + J.VOTE_WORDS:
                for w in {canon, J.W[canon]}:
                    for val in ("D2", "yes", "sì", "pass", "passa", "light", "leggera", "(a)"):
                        try:
                            if J.valid_lines(f"{w} D1 {val}\n", "X.md", set(J.PROPOSAL_WORDS + J.VOTE_WORDS), J.L5):
                                words[w] = val
                                break
                        except J.Error:
                            continue
        line = rest.replace("<w>", word).replace("<v>", words.get(word, "x"))
        return some(J.valid_lines(line + "\n", "X.md", set(J.PROPOSAL_WORDS + J.VOTE_WORDS), J.L5))

    def delegated(x):
        text = x.replace("<w>", J.W["DELEGATED"])
        return some(J._protocol_lines(text + "\n", "DELEGATION.md", J.DELEGATED_L5, J.DELEGATED_NEAR))

    def outcomes(x):
        d = fresh()
        (d / x).write_text("{}\n", encoding="utf-8")
        return some([r for r, _p in J.outcome_files(d)])

    def register(x):
        d = fresh()
        (d / "conv").mkdir()
        reg = d / "REGISTER.md"
        reg.write_text(f"| {x} | conv | coordinator | `new-expert` | x | a reason long enough |\n", encoding="utf-8")
        old = _patch(J, known_roles=lambda: set())
        try:
            return some(sorted(J.requests(reg, d)))
        finally:
            _patch(J, **old)

    def machine_path(x):
        found = [p for p in S.public_problems(x, []) if p.startswith("machine path")]
        return ("err", found[0]) if found else ("none",)

    def local_cards(x):
        p = fresh() / "AGENTS.md"
        p.write_text(x.replace("|", "\n") + "\n", encoding="utf-8")
        return some(sorted(P.local_cards(p)))

    def db_version(x):
        entry = {"id": "x", "type": "professional", "core": "c", "version": x}
        errs = [e for e in P.validate({"cores": [], "entries": [entry]}, required=()) if "version missing" in e]
        return ("err", "version") if errs else ("ok", "valid")

    return {
        "seals_l4": lambda x: seals(J.L4, x), "seals_l5": lambda x: seals(J.L5, x), "key_map": key_map,
        "localize": localize, "canonical": canonical, "ids_in": ids_in, "k_ids_in": k_ids_in,
        "unallocated": unallocated, "norm_id": norm_id, "amendments": amendments, "version_file": version_file,
        "gate_files": gate_files, "role_folder": role_folder, "bind": bind, "fingerprints": fingerprints,
        "arbiter": arbiter, "role_of": role_of, "team": team, "conditions_amend": conditions_amend,
        "g4_deliverable": lambda x: g4(x, False), "g4_audit": lambda x: g4(x, True), "order_rules3": order_rules3,
        "gate_label": gate_label, "convened": convened, "sentinel_brief": sentinel_brief,
        "ext_validate": ext_validate, "lexicon": lexicon, "delegated": delegated, "outcomes": outcomes,
        "register": register, "machine_path": machine_path, "local_cards": local_cards, "db_version": db_version,
    }


VOTE_LINES = [f"<w> D{{n}} <v>", f"<w>{{s}}D1 <v>", "<w> D1{n} <v>"]
CORPORA = {
    "seals_l4": (["SIGILLO giro_{n}/PROPOSTA.md " + SHA + "{s}", "SIGILLO giro_{n}/VOTO_x.md " + SHA,
                  "INCOMPATIBILE-VERIFICATO giro_{n} D1{s}", "INCOMPATIBILE-VERIFICATO giro_0 D{n}"], ["1", "3", "12"]),
    "seals_l5": (["SEAL round_{n}/PROPOSAL.md " + SHA, "SIGILLO giro_{n}/PROPOSTA.md " + SHA,
                  "INCOMPATIBLE-VERIFIED round_{n} D1", "INCOMPATIBLE-VERIFIED round_0 D{n}{s}",
                  "INCOMPATIBILE-VERIFICATO giro_{n} D1", "SEAL{s}round_{n}/PROPOSAL.md " + SHA], ["1", "3", "12"]),
    "key_map": (["agente-{n}", "agent-{n}"], ["1", "3", "12"]),
    "localize": (["convene:agent-{n}", "convene:AMENDMENT_{n}.md", "convene:AMENDMENT_A{n}.md", "jury:round_{n}",
                  "jury:OUTCOME_round_{n}.json", "jury:round_{n}/PROPOSAL.md"], ["1", "3", "12"]),
    "canonical": (["convene:agente-{n}", "convene:EMENDAMENTO_{n}.md", "convene:EMENDAMENTO_A{n}.md", "jury:giro_{n}",
                   "jury:ESITO_giro_{n}.json", "jury:giro_{n}/PROPOSTA.md"], ["1", "3", "12"]),
    "ids_in": (["H-{n}", "{s}H-{n}{s}", "H{n}", "the selection: H-001, H-{n}", "h-{n} and H-002", "(H-{n})"],
               ["9", "009", "35", "1"]),
    "k_ids_in": (["K-{n}", "{s}K-{n}{s}", "K-001-{n}", "K-{n}-1", "see K-{n}."], ["1", "007", "8", "001"]),
    "unallocated": (["K-{n} is open", "{s}K-{n}{s}", "K-001-{n}", "K-{n}-1"], ["1", "007", "8", "001"]),
    "norm_id": (["H-{n}", "{s}H{n}{s}", "h-{n}", "H{n}"], ["9", "035", "1"]),
    "amendments": (["AMENDMENT_{n}.md", "AMENDMENT_A{n}.md", "EMENDAMENTO_{n}.md", "EMENDAMENTO_A{n}.md"],
                   ["1", "3", "12"]),
    "version_file": (["{n}.{n}", "{n}.9 a build", "4.{n}"], ["4", "12"]),
    "gate_files": (["GATE_A{n}.json"], ["1", "3", "12"]),
    "role_folder": (["H-001|{n}-statistico", "H-{n}|01-statistico", "H-{n}|{n}-statistico"], ["03", "3", "001"]),
    "bind": (["{n}-statistico", "{n}-x"], ["03", "3", "12"]),
    "fingerprints": (["A{n}"], ["3", "1", "12"]),
    "arbiter": (["{n}"], ["09", "9", "12"]),
    "role_of": (["{n}-statistico", "{n}-"], ["03", "3", "12"]),
    "team": (["{n}-statistico"], ["03", "3", "12"]),
    "conditions_amend": (["A{n}"], ["3", "1", "12"]),
    "g4_deliverable": (["{n}-statistico"], ["03", "3", "12"]),
    "g4_audit": (["{n}-auditor"], ["05", "5", "12"]),
    "order_rules3": (["{n}-statistico"], ["02", "05", "12"]),
    "gate_label": (["A{n}", "{n}", "a{n}", "f4/H-{n}", "f3/H-{n}"], ["1", "3", "001", "12"]),
    "convened": (["{n}-statistico"], ["03", "3", "12"]),
    "sentinel_brief": (["{n}-statistico"], ["03", "3", "12"]),
    "ext_validate": (["{n}.{n}|>=5.3", "1.0|>={n}.{n}", "1.0|>={s}5.{n}", "1.0|>={s}5.3"], ["5", "12"]),
    "lexicon": ([w + "|" + t for w in ("VOTE", "VOTO", "PREFER", "PREFERISCO", "OPTION", "OPZIONE", "DEPENDS", "DIPENDE",
                                       "TEST-OUTCOME", "ESITO-TEST", "CLASS", "CLASSE", "OPERATIVE", "REVISION",
                                       "CONDITION", "CHANGE", "INCOMPATIBLE", "TEST", "OPTIONS")
                 for t in VOTE_LINES], ["1", "12"]),
    "delegated": (["DELEGATED D{n}", "DELEGATED{s}D{n}", "<w> D{n}", "DELEGATED D1{n}"], ["1", "12"]),
    "outcomes": (["OUTCOME_round_{n}.json", "ESITO_giro_{n}.json"], ["1", "3", "12"]),
    "register": (["{n}-11-21", "2026-{n}-21", "{s}2026-11-21"], ["2026", "11"]),
    "machine_path": (["see /tmp/claude-{n}/x", "/tmp/claude-{n}", "a log in /tmp/claude-{n}{s}/y"], ["1000", "1"]),
    "local_cards": (["### 1. Alpha — `swarmer-loc-a`|- **In short:** a|### {n}. Beta — `swarmer-loc-b`|- **In short:** b",
                     "### {n}. Beta — `swarmer-loc-b`{s}", "### 2.{n}. Beta — `swarmer-loc-b`"], ["2", "22"]),
    "db_version": (["{n}.0", "4.{n}", "{n}.{n}"], ["4", "12"]),
}


def child(engine: str, out: str):
    """Runs every probe on its corpus inside the engine of `engine` and writes the results as JSON."""
    sys.path.insert(0, engine)
    import importlib
    E = {m: importlib.import_module(m) for m in ("compat", "convene", "jury", "professionals", "paths", "extensions")}
    res = {}
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        probes = make_probes(E, root)
        def one(name, text):
            try:
                r = list(probes[name](text))
            except Reached as x:
                r = ["ok", list(x.args)]
            except E["compat"].Error as x:
                r = ["err", str(x)]
            except Exception as x:  # noqa: BLE001
                r = ["crash", f"{type(x).__name__}: {x}"]
            return [re.sub(r"<T>/p[0-9]+", "<T>", str(v).replace(str(root), "<T>")) if i else v for i, v in enumerate(r)]

        for name, (templates, values) in CORPORA.items():
            res[name] = [[text, wide, one(name, text), one(name, twin) if wide else None]
                         for text, wide, twin in corpus(templates, values)]
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=0), encoding="utf-8")


def same(a: list, b: list) -> bool:
    return a[0] == b[0] and (a[0] not in ("ok", "warn") or a[1:] == b[1:])


def violation(name: str, wide: bool, a: list, b: list, twin: list | None) -> str | None:
    """Why 5.3.1's result `b` breaks the rule against 5.3.0's `a`, or None. `twin` is 5.3.0's result on the text
    with its non-ASCII digits written as letters: equal to `a`, 5.3.0 did not read them."""
    refused = b[0] == "err" or (b[0] == "warn" and name in WARN_OK)
    if not wide:
        return None if same(a, b) else "a string with ASCII digits only gives another result"
    if b[0] == "crash":
        return "a crash, not an explicit refusal"
    if a[0] == "none":   # 5.3.0 did not match: no match either, or a refusal
        return None if b[0] in ("none", "err") else "accepts what 5.3.0 did not match"
    if same(a, twin):   # 5.3.0 did not read the non-ASCII digits: the same result, or a refusal
        return None if same(a, b) or refused else "a string whose non-ASCII digits 5.3.0 did not read changes"
    if refused:
        return None
    if b[0] == "none":
        return "ignores in silence what 5.3.0 read"
    return "accepts a non-ASCII digit" if same(a, b) else "reads it as something else"


def old_engine(tmp: Path) -> Path | None:
    """5.3.0's engine, from the git history of the source tree, in tmp/engine; None without that history."""
    git = ["git", "-C", str(SOURCE), "show"]
    try:
        r = subprocess.run(git + [f"{REV}:engine/"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    d = tmp / "engine"
    d.mkdir()
    for f in [x for x in r.stdout.splitlines()[2:] if x.strip()]:
        b = subprocess.run(git + [f"{REV}:engine/{f}"], capture_output=True, timeout=60)
        if b.returncode != 0:
            return None
        (d / f).write_bytes(b.stdout)
    return d


def run_child(engine: Path, out: Path, tmp: Path) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("SWARMER_", "SCIAME_"))}
    env["TMPDIR"] = str(tmp)
    r = subprocess.run([sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--child", str(engine), str(out)],
                       capture_output=True, text=True, timeout=600, env=env)
    return r.returncode, r.stdout + r.stderr


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        child(sys.argv[2], sys.argv[3])
        return
    # --engine DIR: another 5.3.1 engine in place of SOURCE/engine (the evidence of a fix, failing before it)
    new = Path(sys.argv[2]).resolve() if len(sys.argv) == 3 and sys.argv[1] == "--engine" else SOURCE / "engine"
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        old = old_engine(tmp)
        if old is None:
            print(f"skipped: no git history with {REV} (swarmer 5.3.0) beside {SOURCE}: nothing checked")
            print("\n0/0 checks passed")
            sys.exit(0)
        # the static part: every changed regex is a site, and every site names one
        changed = changed_regexes(old, new)
        loose = [f"{side} {f} {w}: {x[:90]}" for side, f, w, x in changed if not claimed((side, f, w, x))]
        check(f"every regex the 5.3.1 diff changed in engine/ is a site of this test ({len(changed)} changed items, "
              f"{len(SITES)} sites)", changed and not loose, loose)
        named = {s[0] for item in changed for s in SITES if s[0] in claimed(item)}
        static = {s[0] for s in SITES if s[3]}
        check("every site of this test with a fragment names a changed regex (the others read one: V2b, J7; or are "
              "5.3.0's bytes again: S1)", named == static, sorted(static - named))
        check("every site has a probe and a corpus", all(s[5] in CORPORA for s in SITES),
              [s[0] for s in SITES if s[5] not in CORPORA])
        # the dynamic part: the same probes on both engines
        runs = {}
        for tag, eng in (("5.3.0", old), ("5.3.1", new)):
            out = tmp / f"{tag}.json"
            (tmp / tag).mkdir()
            rc, text = run_child(eng, out, tmp / tag)
            check(f"the probes ran in {tag}'s engine", rc == 0 and out.is_file(), text)
            if rc != 0 or not out.is_file():
                break
            runs[tag] = json.loads(out.read_text(encoding="utf-8"))
        if len(runs) == 2:
            a, b = runs["5.3.0"], runs["5.3.1"]
            for name in CORPORA:
                rows = list(zip(a[name], b[name]))
                sites = ", ".join(s[0].split()[0] for s in SITES if s[5] == name)
                bad = []
                for (ta, wa, ra, twa), (tb, _wb, rb, _twb) in rows:
                    assert ta == tb
                    why = violation(name, wa, ra, rb, twa)
                    if why:
                        bad.append(f"{ta!a}: 5.3.0 {ra[0]} {str(ra[1:])[:60]} → 5.3.1 {rb[0]} {str(rb[1:])[:80]}: {why}")
                wide_read = sum(1 for (_t, w, ra, tw), _ in rows if w and not same(ra, tw))
                ascii_read = sum(1 for (_t, w, ra, _tw), _ in rows if not w and ra[0] != "none")
                check(f"{name} ({sites}): {len(rows)} strings, {wide_read} with a non-ASCII digit that 5.3.0 read: "
                      "5.3.1 gives 5.3.0's result on ASCII digits and refuses the others", not bad,
                      "\n     ".join(bad[:8]) + (f"\n     … {len(bad)} in all" if len(bad) > 8 else ""))
                check(f"{name}: the corpus reaches 5.3.0's reading with ASCII digits and with non-ASCII ones",
                      wide_read > 0 and ascii_read > 0, (wide_read, ascii_read))
            fixed = sum(1 for s in SITES if s[4] == "fixed")
            print(f"sites: {len(SITES)} ({fixed} fixed, "
                  f"{sum(1 for s in SITES if s[4] == 'explicit')} explicit already, "
                  f"{sum(1 for s in SITES if s[4] == 'detector')} detectors, "
                  f"{sum(1 for s in SITES if s[4] == 'new')} new in this round); strings: "
                  f"{sum(len(v) for v in a.values())} per engine")
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
