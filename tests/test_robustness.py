#!/usr/bin/env python3
"""Test battery of the robustness of the gates and of the version (swarmer 5.3): python3 -I -B tests/test_robustness.py

Uses the harness of tests/test_convene.py (an installation in English and one in Italian, the commands by subprocess,
the Italian aliases in the Italian one) and the seal helpers of tests/test_rounds.py. The checks:
- E2 (ENG-13): a file name that is not UTF-8 is bound by a gate, as a file of the phase and inside a workspace; the
  gate file stays UTF-8 JSON and holds; `_tree`, `_bind` and `write_json` succeed on such a name; a write that fails
  leaves the gate file byte-identical, never empty, and no temporary file beside it;
- E8 (ENG-14): the version of swarmer is written once, in engine/generate.py: the swarm's VERSION, the manifest of a
  new convening and `convene --help` state it; the wrappers and the docstrings of the engine state none; plugin.json,
  engine/head.sh, swarmer.sh, the READMEs and the CHANGELOG agree with it;
- ENG-25: a deliverable or a contract that only quotes the placeholder of an unfilled field (in a code span, in a
  code block or in a sentence) is filled; the placeholder alone on a line or as the whole value of a field is not;
- ENG-26: under the rules 3 every gate checks G0 and the gated amendments again, not only the gate just before it:
  a contract, a file of f0/ or an amendment changed after their gates refuses every later gate; under the rules 2 a
  later gate checks only the gate just before, as in 5.2.
The file names that are not UTF-8 exist only inside the temporary folder of the battery, which removes them.
Exits with 1 if a check fails.
"""
from __future__ import annotations

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
import test_rounds as TR  # noqa: E402   the seals of a round of f4 in the order of the rules 3

C, V, check = TC.C, TC.V, TC.check
SOURCE = TC.SOURCE
BAD = b"bad\xff.txt"   # a file name that is not UTF-8
BAD_WORK = b"raw\xfe.md"


def plant(folder: Path, name: bytes, data: bytes = b"x\n") -> Path:
    """A file whose name is the bytes `name` (not UTF-8), and its path as the engine sees it (surrogateescape)."""
    folder.mkdir(parents=True, exist_ok=True)
    with open(os.path.join(os.fsencode(folder), name), "wb") as f:
        f.write(data)
    return folder / os.fsdecode(name)


def remove(p: Path) -> None:
    if os.path.lexists(os.fsencode(p)):
        os.unlink(os.fsencode(p))


def utf8_json(p: Path):
    """The JSON of a file that is UTF-8, or None."""
    try:
        return json.loads(p.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None


def not_utf8_names(base: Path) -> list[bytes]:
    out = []
    for root, dirs, files in os.walk(os.fsencode(base)):
        for x in dirs + files:
            try:
                x.decode("utf-8")
            except UnicodeDecodeError:
                out.append(os.path.join(root, x))
    return out


# --- E2: the file names that are not UTF-8 (ENG-13) ---

def e2_names(s):
    L = f"E2 [{s.lang}]"
    c = s.classic(rules=3)   # G0 and G1 approved
    gate0 = c / "GATE_f0.json"
    bad = plant(c / "f0", BAD)
    try:
        rc, out = s.run("gate", c, "f0", "--notes", "a file name that is not UTF-8")
        check(f"{L}: G0 approved again over a file of f0/ whose name is not UTF-8", rc == 0, out)
        g = utf8_json(gate0)
        check(f"{L}: the gate file is UTF-8 JSON, never left empty", gate0.stat().st_size > 0 and g is not None,
              gate0.stat().st_size)
        fp = C.to_canonical(g, C.CONVENE_KEYS["gate"]).get("fingerprints", {}) if isinstance(g, dict) else {}
        check(f"{L}: it binds the file by its own name", fp.get(str(bad)) == hashlib.sha256(b"x\n").hexdigest(),
              sorted(fp))
        work = c / "f0" / s.N("work")
        raw = plant(work, BAD_WORK)
        rc, out = s.run("gate", c, "f0", "--notes", "and one in a workspace")
        g = utf8_json(gate0)
        fp = C.to_canonical(g, C.CONVENE_KEYS["gate"]).get("fingerprints", {}) if isinstance(g, dict) else {}
        check(f"{L}: G0 approved again with a workspace holding a name that is not UTF-8, bound as one tree entry",
              rc == 0 and str(work) + "/" in fp and str(raw) not in fp, (out, sorted(fp)))
        rc, out = s.run("gate", c, "f0", "--notes", "x", "--verify")
        check(f"{L}: --verify: G0 holds", rc == 0, out)
        rc, out = s.run("gate", c, "f1", "--notes", "x", "--verify")
        check(f"{L}: the next gate reads G0 as valid", rc == 0, out)
        check(f"{L}: status: f0 approved", s.st("status_approved", phase="f0") in s.status(c), s.status(c))
        with open(os.fsencode(raw), "ab") as f:
            f.write(b"one more line\n")
        check(f"{L}: a byte appended to the file inside the workspace invalidates G0",
              s.st("status_invalid", phase="f0") in s.status(c), s.status(c))
    finally:
        for name in (BAD, BAD_WORK):
            remove(c / "f0" / os.fsdecode(name))
            remove(c / "f0" / s.N("work") / os.fsdecode(name))
    check(f"{L}: no name that is not UTF-8 left in the convening", not not_utf8_names(c), not_utf8_names(c))


def e2_unit(s, base: Path):
    """`_tree`, `_bind`, `write_json` and `create_json` in memory, on a folder of the battery."""
    L = f"E2 [{s.lang}]"
    d = base / f"e2_{s.lang}"
    d.mkdir()
    try:
        w = d / s.N("work")
        p = plant(w, BAD, b"y\n")
        try:
            t = V._tree(w, set())
        except Exception as e:   # noqa: BLE001   the defect is the exception itself
            t = f"{type(e).__name__}: {e}"
        line = BAD + b"\0" + hashlib.sha256(b"y\n").hexdigest().encode() + b"\n"
        check(f"{L}: _tree binds the name by its own bytes", t == "tree:" + hashlib.sha256(line).hexdigest(), t)
        out = {}
        try:
            V._bind(d, out, set())
        except Exception as e:   # noqa: BLE001
            out = {"error": f"{type(e).__name__}: {e}"}
        check(f"{L}: _bind succeeds, the workspace as one tree entry", out == {str(w) + "/": t}, out)
        conv = V.Convening(d, s.lang, {})
        target = d / "GATE_f0.json"
        target.write_bytes(b'{"phase": "f0"}')
        old = target.read_bytes()
        g = {"phase": "f0", "time": "2026-11-20T00:00:00+01:00", "notes": "n", "not_delivered": [],
             "fingerprints": {str(p): "0" * 64, str(d / "plain.md"): "1" * 64}}
        real = os.replace

        def broken(a, b):
            raise OSError("no space left on the device (simulated)")
        os.replace = broken
        try:
            conv.write_json(target, g, "gate")
            failed = "no error"
        except Exception as e:   # noqa: BLE001
            failed = e
        finally:
            os.replace = real
        check(f"{L}: a write that fails leaves the gate file byte-identical, never empty",
              isinstance(failed, OSError) and target.read_bytes() == old, (failed, target.read_bytes()[:40]))
        left = sorted(x.name for x in d.iterdir() if x.is_file())
        check(f"{L}: and no temporary file beside it", left == ["GATE_f0.json"], left)
        try:
            conv.write_json(target, g, "gate")
            back = conv.read_json(target, "gate")
        except Exception as e:   # noqa: BLE001
            back = f"{type(e).__name__}: {e}"
        check(f"{L}: write_json succeeds on a name that is not UTF-8, the file is UTF-8 and reads back the same",
              back == g and utf8_json(target) is not None, back)
        later = d / "GATE_f5_2.json"
        try:
            conv.create_json(later, g, "gate")
            made = conv.read_json(later, "gate") == g and utf8_json(later) is not None
        except Exception as e:   # noqa: BLE001
            made = f"{type(e).__name__}: {e}"
        check(f"{L}: create_json too (a later gate f5)", made is True, made)
        before = later.read_bytes() if later.is_file() else b""
        try:
            conv.create_json(later, {**g, "notes": "again"}, "gate")
            again = "no error"
        except Exception as e:   # noqa: BLE001
            again = e
        check(f"{L}: create_json never writes over an existing file", isinstance(again, FileExistsError)
              and later.read_bytes() == before, again)
    finally:
        shutil.rmtree(os.fsencode(d))
    check(f"{L}: no name that is not UTF-8 left in the battery's folder", not not_utf8_names(base),
          not_utf8_names(base))


# --- E8: the version from one place (ENG-14) ---

def e8_version(s):
    L = f"E8 [{s.lang}]"
    import generate as G
    v = G.VERSION
    words = (s.swarm / "VERSION").read_text(encoding="utf-8").split()
    check(f"{L}: the swarm's VERSION states the version of engine/generate.py", words[:1] == [v], words)
    c = s.classic()
    check(f"{L}: the manifest of a new convening stamps that version", s.manifest(c).get("version") == v,
          s.manifest(c).get("version"))
    rc, out = s.run("--help")
    check(f"{L}: convene --help states it", rc == 0 and f"swarmer {v}:" in out, out[:200])
    stated = {}
    for p in sorted(s.swarm.glob("*.py")):   # the wrappers, the alias stubs, the command of the 3.x
        first = p.read_text(encoding="utf-8").split('"""')[1].split("\n\n")[0]
        if re.search(r"swarmer \d+\.\d+", first):
            stated[p.name] = first[:60]
    check(f"{L}: no wrapper nor alias of the swarm folder states a version",
          not stated and (s.swarm / "convene.py").is_file(), stated)


def e8_sources():
    """The places of the source tree that state the version agree with engine/generate.py, the only one that writes
    it; the code reads it from there (or from the swarm's VERSION, which install writes from it)."""
    L = "E8 [source]"
    import generate as G
    v = G.VERSION
    check(f"{L}: the version is N.M, the form of the database and of the extensions' requirements",
          re.fullmatch(r"\d+\.\d+", v), v)
    lits = []
    for p in sorted((SOURCE / "engine").glob("*.py")) + sorted((SOURCE / "wrappers").glob("*.py")):
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"\s*VERSION\s*=\s*[\"']", line) and p.name != "generate.py":
                lits.append(f"{p.name}:{n}")
    check(f"{L}: no other module of the engine or wrapper writes a version", not lits, lits)
    heads = []
    for p in sorted((SOURCE / "engine").glob("*.py")) + sorted((SOURCE / "wrappers").glob("*.py")):
        doc = p.read_text(encoding="utf-8").split('"""')[1] if '"""' in p.read_text(encoding="utf-8") else ""
        first = doc.split("\n\n")[0]
        if re.search(r"swarmer \d+\.\d+", first):
            heads.append(f"{p.relative_to(SOURCE)}: {first[:60]}")
    check(f"{L}: no docstring of the engine or of a wrapper states a version of swarmer as its own", not heads, heads)
    plugin = json.loads((SOURCE / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    check(f"{L}: plugin.json (the Claude Code plugin and the Agensi package follow it) is {v}.<patch>",
          re.fullmatch(rf"{re.escape(v)}\.\d+", plugin), plugin)
    for rel in ("engine/head.sh", "swarmer.sh", "sciame.sh"):
        second = (SOURCE / rel).read_text(encoding="utf-8").splitlines()[1]
        check(f"{L}: {rel} states version {v}", second.endswith(f", version {v}"), second)
    for rel, words in (("docs/en/README.md", f"(version {v})"), ("docs/it/README.md", f"(versione {v})")):
        first = (SOURCE / rel).read_text(encoding="utf-8").splitlines()[0]
        check(f"{L}: {rel} states {words} in its title", first.endswith(words), first)
    for rel, words in (("README.md", f"Version {v} adds"), ("README.it.md", f"La versione {v} aggiunge")):
        text = " ".join((SOURCE / rel).read_text(encoding="utf-8").split())
        check(f"{L}: {rel} says what {v} adds", words in text)
    for rel in ("CHANGELOG.md", "CHANGELOG.it.md"):
        heads = re.findall(r"^## (\S+)", (SOURCE / rel).read_text(encoding="utf-8"), re.M)
        check(f"{L}: {rel} opens with the entry of plugin.json's version", heads[:1] == [plugin], heads[:3])


# --- ENG-25: a quoted placeholder is not an unfilled field ---

def e25_placeholder(s):
    L = f"ENG-25 [{s.lang}]"
    ph = C.CONVENE_LINES["to_fill_in"][s.lang]
    other = C.CONVENE_LINES["to_fill_in"]["it" if s.lang == "en" else "en"]
    d = s.root / "e25"
    d.mkdir(exist_ok=True)
    quoted = {
        "in a code span": f"The engine writes `{ph}` in every field it leaves to the coordinator.\n",
        "in a code span alone on its line": f"The placeholder:\n\n`{ph}`\n",
        "in a double code span": f"``{ph}`` is the placeholder.\n",
        "in a fenced code block": f"The template:\n\n```\n## Question\n\n{ph}\n```\n",
        "in a tilde code block": f"~~~text\n{ph}\n~~~\n",
        "in a sentence": f"A field left as {ph} is refused by the gate.\n",
        "of the other language, in a field": f"- Results: the Italian template says `{other}`\n",
        "as part of a field's value": f"- Results: {ph} was replaced by the measurement\n",
        "with a period, as part of a field's value": f"- Goal: {ph}. Then the measurement\n",
        "in an indented code block": f"The template writes:\n\n    {ph}\n",
        "in an indented code block at the start": f"    {ph}\n",
        "in a tab-indented code block": f"The template writes:\n\n\t{ph}\n",
        "in an indented code block after a heading": f"## Example\n    {ph}\n",
        "in an indented code block inside a list item": f"- Example:\n\n      {ph}\n",
    }
    unfilled = {
        "alone on a line": f"{ph}\n",
        "alone on a line, indented": f"Done.\n\n   {ph}   \n",
        "alone in a list item": f"- {ph}\n",
        "as the whole value of a field": f"- Results: {ph}\n",
        "as the whole value of a bold field": f"- **Results:** {ph}\n",
        "as the value of the slice line of a brief": f"Slice 1 of 14: {ph}\n",
        "as a table cell": f"| Results | {ph} |\n",
        "of the other language, alone on a line": f"{other}\n",
        "after a closed code block": f"```\nx\n```\n\n{ph}\n",
        "as a field's value, followed by a period": f"- Goal: {ph}.\n",
        "alone on a line, followed by a period": f"{ph}.\n",
        "as a table cell, followed by a period": f"| Goal | {ph}. |\n",
        "indented by 4 under a list item (its content, not code)": f"- Results:\n\n    {ph}\n",
        "indented by 4 continuing a field (not code)": f"Results:\n    {ph}\n",
        "after an indented code block": f"    code\n\n{ph}\n",
    }
    for k, text in quoted.items():
        p = d / "q.md"
        p.write_text(text, encoding="utf-8")
        check(f"{L}: a deliverable that quotes the placeholder {k} is filled", V.full(p), text)
    for k, text in unfilled.items():
        p = d / "u.md"
        p.write_text(text, encoding="utf-8")
        check(f"{L}: one with the placeholder {k} is not", not V.full(p), text)
    # through the gates: f2 (a deliverable) and f0 (a contract section)
    c = s.classic()
    cards = c / "f2" / s.N("01-translation") / s.N("CARDS.md")
    cards.write_text(f"cards\n\nAn empty field of the card reads `{ph}`.\n", encoding="utf-8")
    rc, out = s.run("gate", c, "f2", "--notes", "x", "--verify")
    check(f"{L}: gate f2 holds with cards that quote the placeholder in a code span", rc == 0, out)
    cards.write_text(f"cards\n- H-001: {ph}\n", encoding="utf-8")
    rc, out = s.run("gate", c, "f2", "--notes", "x", "--verify")
    check(f"{L}: refused with a card left with the placeholder as a field's value",
          rc == 1 and s.N("CARDS.md") in out, out)
    contract = c / s.N("CONTRACT.md")
    text = contract.read_text(encoding="utf-8")
    contract.write_text(text.replace("filled", f"filled; the engine writes `{ph}` in a field to fill in", 1),
                        encoding="utf-8")
    rc, out = s.run("gate", c, "f0", "--notes", "x", "--verify")
    check(f"{L}: the conditions of G0 hold with a contract that quotes the placeholder", rc == 0, out)
    contract.write_text(text.replace("filled", ph, 1), encoding="utf-8")
    rc, out = s.run("gate", c, "f0", "--notes", "x", "--verify")
    check(f"{L}: refused with a section left as the placeholder", rc == 1 and s.N("CONTRACT.md") in out, out)
    contract.write_text(text.replace("filled", ph + ".", 1), encoding="utf-8")
    rc, out = s.run("gate", c, "f0", "--notes", "x", "--verify")
    check(f"{L}: refused with a section left as the placeholder and a period", rc == 1 and s.N("CONTRACT.md") in out,
          out)
    contract.write_text(text, encoding="utf-8")


# --- ENG-26: every gate checks G0 and the gated amendments again under the rules 3 ---

def e26_chain(s):
    L = f"ENG-26 [{s.lang}]"
    refused = "the gate f0 is not approved or no longer valid"
    for rules in (3, 2):
        c = s.classic(rules=rules)   # G0, G1 approved; f2 ready
        contract = c / s.N("CONTRACT.md")
        orig = contract.read_bytes()
        contract.write_bytes(orig + b"\nchanged after G1\n")
        rc, out = s.run("gate", c, "f2", "--notes", "x", "--verify")
        if rules == 3:
            check(f"{L}: rules 3: the contract changed after G1: G2 refused", rc == 1 and refused in out, out)
        else:
            check(f"{L}: rules 2: the contract changed after G1: G2 checks only G1, as in 5.2", rc == 0, out)
        contract.write_bytes(orig)
        extra = c / "f0" / "notes.md"
        extra.write_text("added after G1\n", encoding="utf-8")
        rc, out = s.run("gate", c, "f2", "--notes", "x", "--verify")
        if rules == 3:
            check(f"{L}: rules 3: a file added to f0/ after G1: G2 refused", rc == 1 and refused in out, out)
            rc, out = s.run("gate", c, "f2", "--notes", "x", "--verify", "--rules", "2")
            check(f"{L}: --rules 2 does not lower the rules of the convening: still refused",
                  rc == 1 and refused in out, out)
        else:
            check(f"{L}: rules 2: a file added to f0/ after G1: G2 holds, as in 5.2", rc == 0, out)
            rc, out = s.run("gate", c, "f2", "--notes", "x", "--verify", "--rules", "3")
            check(f"{L}: rules 2, a gate run with --rules 3: refused", rc == 1 and refused in out, out)
        extra.unlink()
        rc, out = s.run("gate", c, "f2", "--notes", "x", "--verify")
        check(f"{L}: rules {rules}: f0 restored: G2 holds", rc == 0, out)
    # rules 3, down the chain: G3, G4 and G5 of a branch, then the amendments
    c = s.classic(rules=3)
    s.gate_f2(c)
    rc, out = s.run("select", c, "H-001")
    assert rc == 0, out
    s.f3(c, "H-001")
    b = c / "f4" / "H-001"
    outs = TR.deliver(s, b)
    s.dossier(c, "H-001")
    TR.write_seals(s, c, TR.seal_rows(s, c) + TR.output_rows(s, outs))
    rc, out = s.run("gate", c, "f4/H-001", "--notes", "x")
    assert rc == 0, out
    s.closure(c, closed=False, extra="H-001 refuted\n")
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify")
    check(f"{L}: rules 3: G5 holds on an intact chain", rc == 0, out)
    contract = c / s.N("CONTRACT.md")
    orig = contract.read_bytes()
    contract.write_bytes(orig + b"\nchanged after G4\n")
    for label in ("f3/H-001", "f4/H-001", "f5"):
        rc, out = s.run("gate", c, label, "--notes", "x", "--verify")
        check(f"{L}: rules 3: the contract changed after G4: gate {label} refused", rc == 1 and refused in out, out)
    contract.write_bytes(orig)
    rc, out = s.run("gate", c, "f5", "--notes", "x", "--verify")
    check(f"{L}: rules 3: the contract restored: G5 holds again", rc == 0, out)
    a1, a2 = c / s.N("AMENDMENT_1.md"), c / s.N("AMENDMENT_2.md")
    a1.write_text(s.line("Amends: Constraints\n", "Modifica: Vincoli\n") + "git allowed\n", encoding="utf-8")
    s.run("seal", c, a1)
    rc, out = s.run("gate", c, "A1", "--notes", "x")
    check(f"{L}: rules 3: gate A1 approved", rc == 0, out)
    a2.write_text(s.line("Amends: Inputs\n", "Modifica: Ingressi\n") + "one more source\n", encoding="utf-8")
    s.run("seal", c, a2)
    rc, out = s.run("gate", c, "A2", "--notes", "x", "--verify")
    check(f"{L}: rules 3: gate A2 holds while A1 holds", rc == 0, out)
    a1.write_text(a1.read_text(encoding="utf-8") + "and more\n", encoding="utf-8")
    rc, out = s.run("gate", c, "A2", "--notes", "x", "--verify")
    check(f"{L}: rules 3: {a1.name} changed after its gate: gate A2 refused", rc == 1 and a1.name in out, out)


def e26_rules2_amendment(s):
    """Under the rules 2 an amendment gate checks only G0, as in 5.2."""
    L = f"ENG-26 [{s.lang}]"
    c = s.classic(rules=2)
    a1, a2 = c / s.N("AMENDMENT_1.md"), c / s.N("AMENDMENT_2.md")
    a1.write_text(s.line("Amends: Constraints\n", "Modifica: Vincoli\n") + "git allowed\n", encoding="utf-8")
    s.run("seal", c, a1)
    s.run("gate", c, "A1", "--notes", "x")
    a2.write_text(s.line("Amends: Inputs\n", "Modifica: Ingressi\n") + "one more source\n", encoding="utf-8")
    s.run("seal", c, a2)
    a1.write_text(a1.read_text(encoding="utf-8") + "and more\n", encoding="utf-8")
    rc, out = s.run("gate", c, "A2", "--notes", "x", "--verify")
    check(f"{L}: rules 2: {a1.name} changed after its gate: gate A2 checks only G0, as in 5.2", rc == 0, out)


def main():
    with tempfile.TemporaryDirectory() as b:
        base = Path(b)
        e8_sources()
        for lang in ("en", "it"):
            s = TC.Swarm(base, lang)
            e2_names(s)
            e2_unit(s, base)
            e8_version(s)
            e25_placeholder(s)
            e26_chain(s)
            e26_rules2_amendment(s)
        left = not_utf8_names(base)
    check("no name that is not UTF-8 left after the battery", not left, left)
    failed = [n for n, ok in TC.results if not ok]
    print(f"\n{len(TC.results) - len(failed)}/{len(TC.results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
