#!/usr/bin/env python3
"""Test battery of the swarmer 5.0 jury (JURY.md, engine/jury.py): python3 -I -B tests/test_jury.py

Builds fake juries in a temporary folder and checks that jury.py gives the outcomes of §3 (with non-regression, the
limit, the dependencies, the classes and the recommendations) and refuses the attacks found by the validation of the
protocol: each has its check here. Then the threshold of the experts of §4. The whole battery runs twice, once per
dialect of the jury files (en: jury.json, round_<r>/, VOTE lines; it: the 4.0 names), with the same assertions.
Then the checks of the migration: M4 (the same jury in it, en and mixed lines gives the same canonical outcome), M5
(every 4.0 jury of tests/fixtures/juries-4.0/ is recounted byte for byte), M11 (the L5 lexicon), M12 (the requesters
of the expert request register in both languages), M13 (one definition per juror, one dialect per file). Exits with 1
if a check fails. The agents are fake, in a temporary folder (SWARMER_AGENTS_DIR).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SWARM = HERE.parent
JURY = SWARM / "engine" / "jury.py"
FIXTURES = HERE / "fixtures" / "juries-4.0"
FAKE_ROLES = ["garante", "avversario", "logico", "debugger", "statistico", "rovesciatore", "creativo", "formalista",
              "fonti", "metrologo", "arbitro", "scelta-sociale", "prestazioni", "sviluppatore", "architetto"]
ROLES5 = ["garante", "avversario", "logico", "debugger", "statistico"]
results = []

# --- the two dialects of a jury: names of the files, keys, protocol words and values (test data) ---
DIALECTS = {
    "en": {"files": {"jury.json": "jury.json", "SEALS.md": "SEALS.md", "PROPOSAL.md": "PROPOSAL.md",
                     "DELEGATION.md": "DELEGATION.md", "RELEVANCE.md": "RELEVANCE.md"},
           "round": "round_{r}", "vote": "VOTE_{x}.md", "outcome": "OUTCOME_round_{r}.json", "card": "CARD_{x}.md",
           "recusal": "RECUSAL_{x}.md", "seal": "sha256 of the bytes before this line: ",
           "keys": {}, "values": {},
           "words": {}, "yes": "yes", "classes": {"ordinary": "ordinary", "plenary": "plenary", "light": "light"},
           "test": {"pass": "pass", "fail": "fail"}, "register": {"coordinator": "coordinator",
                                                                  "provisional": "provisional:", "created": "created",
                                                                  "merged": "merged into", "prefix": "swarmer-",
                                                                  "plenary": "plenary"}},
    "it": {"files": {"jury.json": "giuria.json", "SEALS.md": "SIGILLI.md", "PROPOSAL.md": "PROPOSTA.md",
                     "DELEGATION.md": "DELEGA.md", "RELEVANCE.md": "PERTINENZA.md"},
           "round": "giro_{r}", "vote": "VOTO_{x}.md", "outcome": "ESITO_giro_{r}.json", "card": "SCHEDA_{x}.md",
           "recusal": "RINUNCIA_{x}.md", "seal": "sha256 dei byte che precedono questa riga: ",
           "keys": {"protocol": "protocollo", "subject": "oggetto", "rapporteur": "relatore", "clerk": "cancelliere",
                    "touches_code": "tocca_codice", "touches_numbers": "tocca_numeri", "authority": "autorita",
                    "delegation": "delega", "classification": "classificazione", "jurors": "giurati",
                    "role": "ruolo", "fresh_on_subject": "nuovo_sull_oggetto", "provisional": "provvisorio",
                    "form": "forma", "round_limit": "limite_giri", "relevance": "pertinenza",
                    "previous": "precedenti", "lexicon": "lessico"},
           "values": {"binding": "vincolante", "recommendation": "raccomandazione", "ordinary": "ordinaria",
                      "plenary": "plenaria", "light": "leggera"},
           "words": {"OPTION": "OPZIONE", "OPTIONS": "OPZIONI", "OPERATIVE": "DISPOSITIVO", "DEPENDS": "DIPENDE",
                     "INCOMPATIBLE": "INCOMPATIBILE", "INCOMPATIBLE-VERIFIED": "INCOMPATIBILE-VERIFICATO",
                     "TEST": "PROVA", "TEST-OUTCOME": "ESITO-PROVA", "VOTE": "VOTO", "REVISION": "REVISIONE",
                     "CONDITION": "CONDIZIONE", "CLASS": "CLASSE", "CHANGE": "CAMBIO", "PREFER": "PREFERISCO",
                     "SEAL": "SIGILLO", "DELEGATED": "DELEGATA", "RELEVANT": "PERTINENTE"},
           "yes": "si", "classes": {"ordinary": "ordinaria", "plenary": "plenaria", "light": "leggera"},
           "test": {"pass": "passa", "fail": "fallisce"}, "register": {"coordinator": "coordinatore",
                                                                       "provisional": "provvisorio:",
                                                                       "created": "creato", "merged": "unito a",
                                                                       "prefix": "sciame-", "plenary": "plenaria"}},
}


class Dialect:
    def __init__(self, lang):
        self.lang = lang
        self.t = DIALECTS[lang]

    def f(self, canonical):
        return self.t["files"].get(canonical, canonical)

    def rnd(self, r):
        return self.t["round"].format(r=r)

    def vote(self, x):
        return self.t["vote"].format(x=x)

    def outcome(self, r):
        return self.t["outcome"].format(r=r)

    def w(self, word):
        return self.t["words"].get(word, word)

    def key(self, k):
        return self.t["keys"].get(k, k)

    def value(self, v):
        return self.t["values"].get(v, v) if isinstance(v, str) else v

    def cls(self, c):
        return self.t["classes"][c]

    def yes_no(self, v):
        return self.t["yes"] if v == "yes" else "no"


def ui_language():
    """The language jury.py prints in: the one of the swarm the battery belongs to."""
    for n in ("LANGUAGE", "LINGUA"):
        p = SWARM / n
        if p.is_file():
            return p.read_text(encoding="utf-8").strip() or "en"
    return "en"


def i18n(lang):
    out = json.loads((SWARM / "i18n" / "en.json").read_text(encoding="utf-8"))
    p = SWARM / "i18n" / f"{lang}.json"
    if p.is_file():
        out.update(json.loads(p.read_text(encoding="utf-8")))
    return out


UI = ui_language()
TEXT = i18n(UI)
sys.dont_write_bytecode = True
sys.path.insert(0, str(SWARM / "engine"))
import compat as C  # noqa: E402

D = Dialect("en")   # the dialect of the run in progress
FAKE_AGENTS = ""


def check(name, ok, detail=""):
    results.append((f"[{D.lang}] {name}", bool(ok)))
    print(("ok   " if ok else "FAILED ") + f"[{D.lang}] {name}" + ("" if ok or not detail else f"\n     {str(detail)[:500]}"))


def seal(text, lang=None):
    body = text if text.endswith("\n") else text + "\n"
    return body + DIALECTS[lang or D.lang]["seal"] + hashlib.sha256(body.encode()).hexdigest() + "\n"


def seal_of(p):
    return Path(p).read_text().rstrip("\n").rsplit(" ", 1)[1]


def jury(base, name, jurors=None, **extra):
    """A jury in the dialect of the run; jurors and extra with canonical keys and values (None removes a field)."""
    c = Path(base) / name
    c.mkdir()
    g = {"protocol": "G1.1", "lexicon": 5, "subject": name, "rapporteur": "formalista", "clerk": "arbitro",
         "touches_code": True,
         "touches_numbers": True, "authority": "binding", "delegation": "test", "classification": "ordinary",
         "jurors": jurors or [{"role": r, "fresh_on_subject": True} for r in ROLES5]}
    g.update(extra)
    out = {}
    for k, v in g.items():
        if v is None:
            continue
        if k == "jurors":
            v = [{D.key(a): b for a, b in x.items()} for x in v]
        elif k in ("authority", "classification", "form"):
            v = D.value(v)
        out[D.key(k)] = v
    (c / D.f("jury.json")).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    (c / D.f("SEALS.md")).write_text("# reported seals\n", encoding="utf-8")
    return c


def add_seal_line(c, line):
    with open(c / D.f("SEALS.md"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def register(c, rel):
    add_seal_line(c, f"{D.w('SEAL')} {rel} {seal_of(c / rel)}")


def proposal(c, r, options, operative=None, extra="", option_list=None, seal_it=True):
    d = c / D.rnd(r)
    d.mkdir(exist_ok=True)
    body = "# proposal\n"
    for k, v in options.items():
        body += f"{D.w('OPTION')} {k} {v}\n"
        if r == 0:
            body += f"{D.w('OPTIONS')} {k} {(option_list or {}).get(k, v + ' | (z)')}\n"
        body += f"{D.w('OPERATIVE')} {k} {(operative or {}).get(k, 'one does ' + v)}\n"
    (d / D.f("PROPOSAL.md")).write_text(seal(body + extra), encoding="utf-8")
    if seal_it:
        register(c, f"{D.rnd(r)}/{D.f('PROPOSAL.md')}")


def vote(c, r, role, votes, without=None, extra="", cls="ordinary", change=(), seal_it=True):
    lines = []
    for k, v in votes.items():
        lines.append(f"{D.w('VOTE')} {k} {D.yes_no(v)}")
        if without != k:
            lines.append(f"{D.w('REVISION')} {k} remove clause 2" if v == "no" else f"{D.w('CONDITION')} {k} none")
        lines.append(f"{D.w('CLASS')} {k} {D.cls(cls)}")
        if k in change:
            lines.append(f"{D.w('CHANGE')} {k} clause 2 is removed")
    (c / D.rnd(r) / D.vote(role)).write_text(seal("\n".join(lines) + "\n" + extra), encoding="utf-8")
    if seal_it:
        register(c, f"{D.rnd(r)}/{D.vote(role)}")


def roles_of(c):
    g = json.loads((c / D.f("jury.json")).read_text())
    return [x[D.key("role")] for x in g[D.key("jurors")]]


def vote_all(c, r, scheme, before=None):
    """scheme: {decision: number of yes}; the first k roles vote yes. before: the outcome of the previous round."""
    for i, role in enumerate(roles_of(c)):
        v = {d: ("yes" if i < k else "no") for d, k in scheme.items()}
        change = [d for d in v if before and v[d] == "yes" and role in before.get(d, {}).get("no", [])]
        vote(c, r, role, v, change=change)


def env(tests=True):
    e = {k: v for k, v in os.environ.items() if k not in C.ENV_ALIASES.values() and not k.startswith("SWARMER_")}
    e.update(SWARMER_AGENTS_DIR=FAKE_AGENTS, SWARMER_LANGUAGE=UI)
    if tests:
        e["SWARMER_G11_TESTS"] = "1"
    return e


def run(*arg, tests=True):
    p = subprocess.run([sys.executable, "-I", "-B", str(JURY), *map(str, arg)], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, env=env(tests))
    return p.returncode, p.stdout + p.stderr


def run_without_tests(*arg):
    return run(*arg, tests=False)


def raw_outcome(c, r):
    return json.loads((c / D.outcome(r)).read_text())


def outcome(c, r):
    """The canonical decisions of an outcome, after checking that the file is in the dialect of the jury."""
    e = raw_outcome(c, r)
    assert ("decisioni" in e) == (D.lang == "it"), f"outcome not in the dialect {D.lang}"
    return C.to_canonical(e, C.OUTCOME_SCHEMA)["decisions"]


def refuse(name, c, r=0, text=None):
    rc, out = run("count", c, r)
    check(name + " → refused", rc == 2 and TEXT["jury_error_prefix"].strip() in out and "Traceback" not in out
          and (text is None or text in out), out)


def simple(base, name, scheme, **kw):
    c = jury(base, name, **kw)
    proposal(c, 0, {d: f"({d.lower()})" for d in scheme})
    vote_all(c, 0, scheme)
    return c


def battery(base):
    base = Path(base)
    # --- 1. the three outcomes and the final classes
    c = simple(base, "three_outcomes", {"D1": 5, "D2": 3, "D3": 2, "D4": 0})
    rc, _ = run("count", c, 0)
    e = outcome(c, 0) if rc == 0 else {}
    check("total consensus → APPROVED", rc == 0 and e["D1"]["state"] == "APPROVED")
    check("majority 3/5 → REVISION", rc == 0 and e["D2"]["state"] == "REVISION")
    check("minority 2/5 → REJECTED", rc == 0 and e["D3"]["state"] == "REJECTED")
    check("consensus on no → REJECTED", rc == 0 and e["D4"]["state"] == "REJECTED")
    proposal(c, 1, {"D2": "(d2)"})
    vote_all(c, 1, {"D2": 5}, before=e)
    rc, _ = run("count", c, 1)
    e1 = outcome(c, 1) if rc == 0 else {}
    check("round 1, consensus with the CHANGE lines → APPROVED", rc == 0 and e1["D2"]["state"] == "APPROVED")
    check("the decisions closed at round 0 stay", rc == 0 and e1["D1"]["state"] == "APPROVED"
          and e1["D3"]["state"] == "REJECTED")
    rc, _ = run("count", c, 1)
    check("count repeated without changes is idempotent", rc == 0)

    c = simple(base, "recommendation", {"D1": 5}, authority="recommendation")
    rc, _ = run("count", c, 0)
    check("reserved matter: consensus → RECOMMENDED, not APPROVED", rc == 0 and outcome(c, 0)["D1"]["state"] == "RECOMMENDED")
    c = jury(base, "plenary_class")
    proposal(c, 0, {"D1": "(a)"})
    for i, role in enumerate(ROLES5):
        vote(c, 0, role, {"D1": "yes"}, cls="plenary" if i == 2 else "ordinary")
    rc, _ = run("count", c, 0)
    check("one plenary CLASS → TO_PLENARY", rc == 0 and outcome(c, 0)["D1"]["state"] == "TO_PLENARY")
    c = jury(base, "prefer")
    proposal(c, 0, {"D1": "(a)"}, option_list={"D1": "(a) | (b)"})
    for i, role in enumerate(ROLES5):
        vote(c, 0, role, {"D1": "yes"}, extra=f"{D.w('PREFER')} D1 (b)\n" if i < 3 else "")
    rc, _ = run("count", c, 0)
    check("all yes but the majority prefers (b) → TO_REPROPOSE (F11)",
          rc == 0 and outcome(c, 0)["D1"]["state"] == "TO_REPROPOSE")

    # Y5: a new jury does not declare itself G1.1
    c = simple(base, "g11_new", {"D1": 5})
    rc, out = run_without_tests("count", c, 0)
    check(f"Y5: a new G1.1 jury is refused without {D.outcome(0)}", rc == 2 and "G1.1" in out, out)
    # C2: G1.1 is not recounted, without the variable, in a jury of 5.0 (jury.json, or giuria.json with the lexicon
    # 5), even after the key «protocol» has been taken out of its outcome by hand
    c = simple(base, "g11_lexicon5", {"D1": 5})
    run("count", c, 0)
    p = c / D.outcome(0)
    e = json.loads(p.read_text())
    e.pop(D.key("protocol"), None)
    p.write_text(json.dumps(e, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    rc, out = run_without_tests("count", c, 0)
    check("C2: G1.1 of a 5.0 jury (lexicon 5) is refused without the variable, the outcome without «protocol»",
          rc == 2 and "G1.1" in out, out)
    # Y4: an outcome written before the key «protocol» is recounted (a 4.0 jury: giuria.json without the lexicon key);
    # a retouched one is not
    c = simple(base, "old_outcome", {"D1": 5}, lexicon=None)
    run("count", c, 0)
    p = c / D.outcome(0)
    e = json.loads(p.read_text())
    e.pop(D.key("protocol"), None)
    p.write_text(json.dumps(e, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    rc, out = run_without_tests("count", c, 0)
    if D.lang == "it":
        check("Y4: an outcome without «protocol» is recounted identical", rc == 0, out)
    else:
        check("C2: G1.1 in a jury.json without the lexicon key is still refused without the variable",
              rc == 2 and "G1.1" in out, out)
    decisions = e["decisioni" if D.lang == "it" else "decisions"]
    decisions["D1"]["stato" if D.lang == "it" else "state"] = "RESPINTA" if D.lang == "it" else "REJECTED"
    p.write_text(json.dumps(e, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    rc, out = run_without_tests("count", c, 0)
    check("Y4: an old retouched outcome stays refused", rc == 2, out)

    # W4: an outcome written with the key «protocol» does not open G1.1 outside the batteries
    c = simple(base, "g11_marked", {"D1": 5})
    run("count", c, 0)
    rc, out = run_without_tests("count", c, 0)
    check("W4: a G1.1 jury counted only with the variable of the batteries is not recounted without", rc == 2, out)

    # --- 2. revisions: regression, minority, limit, incompatible, unmotivated change
    c = simple(base, "regression", {"D1": 3})
    run("count", c, 0)
    e0 = outcome(c, 0)
    proposal(c, 1, {"D1": "(d1)"})
    for role, v in zip(ROLES5, ["no", "yes", "yes", "yes", "yes"]):
        vote(c, 1, role, {"D1": v}, change=["D1"] if role in e0["D1"]["no"] and v == "yes" else [])
    rc, out = run("count", c, 1)
    e = outcome(c, 1) if rc == 0 else {}
    check("revision that loses a yes → discarded, stays REVISION", rc == 0 and e["D1"]["state"] == "REVISION"
          and e["D1"].get("regression", {}).get("yes_lost") == ["garante"])
    check("after a regressive one the text and the yes of the previous round hold",
          rc == 0 and e["D1"]["yes"] == sorted(["garante", "avversario", "logico"]) and e["D1"]["text_round"] == 0)
    check("the print also says the yes of the discarded round (A12)",
          TEXT["jury_regressive"].format(yes=4, n=5).strip() in out, out)

    # after a discarded round, CHANGE with respect to the last vote cast: whoever was yes in the discarded round does
    # not write it again
    c = simple(base, "change_after_regressive", {"D1": 3})  # yes: garante, avversario, logico; no: debugger, statistico
    run("count", c, 0)
    proposal(c, 1, {"D1": "(d1)"})
    for role, v in zip(ROLES5, ["no", "yes", "yes", "yes", "no"]):  # the guarantor loses the yes, the debugger turns
        vote(c, 1, role, {"D1": v}, change=["D1"] if role == "debugger" else [])
    run("count", c, 1)
    proposal(c, 2, {"D1": "(d1)"})
    for role, v in zip(ROLES5, ["yes", "yes", "yes", "yes", "yes"]):  # the guarantor is yes again: CHANGE; the debugger not
        vote(c, 2, role, {"D1": v}, change=["D1"] if role in ("garante", "statistico") else [])
    rc, out = run("count", c, 2)
    check("after a discarded round, CHANGE with respect to the last vote cast",
          rc == 0 and outcome(c, 2)["D1"]["state"] == "APPROVED", out)
    c = simple(base, "minority_in_revision", {"D1": 3})
    run("count", c, 0)
    proposal(c, 1, {"D1": "(d1)"})
    vote_all(c, 1, {"D1": 2})
    rc, _ = run("count", c, 1)
    check("revision that falls into minority → REJECTED (directive; L1, F5, A12)",
          rc == 0 and outcome(c, 1)["D1"]["state"] == "REJECTED")

    c = simple(base, "limit", {"D1": 3})
    run("count", c, 0)
    for r in (1, 2, 3):
        proposal(c, r, {"D1": "(d1)"})
        vote_all(c, r, {"D1": 3})
        rc, _ = run("count", c, r)
    check("still a majority at round 3 → NOT_CONVERGED", rc == 0 and outcome(c, 3)["D1"]["state"] == "NOT_CONVERGED")
    refuse("round 4", c, 4)
    c = simple(base, "low_limit", {"D1": 3}, round_limit=0)
    refuse("round_limit other than 3 (F1)", c, text="round_limit")

    c = simple(base, "incompatible", {"D1": 3})
    run("count", c, 0)
    proposal(c, 1, {"D1": "(d1)"}, extra=f"{D.w('INCOMPATIBLE')} D1 the REVISION of the debugger contradicts the "
                                         "CONDITION of the logician\n")
    vote_all(c, 1, {"D1": 3})
    add_seal_line(c, f"{D.w('INCOMPATIBLE-VERIFIED')} {D.rnd(1)} D1")
    rc, _ = run("count", c, 1)
    check("INCOMPATIBLE verified by the clerk → NOT_CONVERGED, the votes do not count (F8, L6)",
          rc == 0 and outcome(c, 1)["D1"]["state"] == "NOT_CONVERGED")
    c = simple(base, "incompatible_not_verified", {"D1": 3})
    run("count", c, 0)
    proposal(c, 1, {"D1": "(d1)"}, extra=f"{D.w('INCOMPATIBLE')} D1 the REVISION contradicts a CONDITION\n")
    vote_all(c, 1, {"D1": 3})
    rc, _ = run("count", c, 1)
    check("INCOMPATIBLE not verified: it counts as a revision round", rc == 0 and outcome(c, 1)["D1"]["state"] == "REVISION")
    c = simple(base, "incompatible_invented", {"D1": 3})
    run("count", c, 0)
    proposal(c, 1, {"D1": "(d1)"})
    vote_all(c, 1, {"D1": 3})
    add_seal_line(c, f"{D.w('INCOMPATIBLE-VERIFIED')} {D.rnd(1)} D1")
    refuse("INCOMPATIBLE-VERIFIED without the declaration of the rapporteur", c, 1, "does not declare it")

    c = simple(base, "unmotivated_change", {"D1": 3})
    run("count", c, 0)
    proposal(c, 1, {"D1": "(d1)"})
    for role in ROLES5:
        vote(c, 1, role, {"D1": "yes"})
    refuse("from no to yes without CHANGE (F7)", c, 1, f"without a {D.w('CHANGE')} line")

    c = simple(base, "option", {"D1": 4, "D2": 5})
    run("count", c, 0)
    proposal(c, 1, {"D1": "(b)"})
    vote_all(c, 1, {"D1": 5})
    refuse("option changed in revision", c, 1, "the option of D1 changed")
    shutil.rmtree(c / D.rnd(1))
    proposal(c, 1, {"D1": "(d1)"}, operative={"D1": "one does something else entirely"})
    vote_all(c, 1, {"D1": 5})
    refuse("OPERATIVE changed in revision (F6, L5)", c, 1, f"the {D.w('OPERATIVE')} of D1 changed")
    shutil.rmtree(c / D.rnd(1))
    proposal(c, 1, {"D1": "(d1)", "D2": "(d2)"})
    vote_all(c, 1, {"D1": 5, "D2": 5})
    refuse("decision already approved presented again", c, 1, "those in REVISION")
    c = jury(base, "option_outside_list")
    proposal(c, 0, {"D1": "(a)"}, option_list={"D1": "(b) | (c)"})
    vote_all(c, 0, {"D1": 5})
    refuse("OPTION outside the OPTIONS list (L5)", c, text=f"is not in the {D.w('OPTIONS')} D1 line")

    # --- 3. dependencies (L4, F8)
    c = jury(base, "depends")
    proposal(c, 0, {"D1": "(a)", "D2": "(b)"}, extra=f"{D.w('DEPENDS')} D2 D1\n")
    vote_all(c, 0, {"D1": 2, "D2": 5})
    rc, _ = run("count", c, 0)
    check("D2 approved but D1 rejected → D2 SUSPENDED", rc == 0 and outcome(c, 0)["D2"]["state"] == "SUSPENDED")
    c = jury(base, "depends_rev")
    proposal(c, 0, {"D1": "(a)", "D2": "(b)"}, extra=f"{D.w('DEPENDS')} D2 D1\n")
    vote_all(c, 0, {"D1": 4, "D2": 5})
    rc, _ = run("count", c, 0)
    e = outcome(c, 0) if rc == 0 else {}
    check("D2 approved but D1 in revision → D2 is voted again with D1", rc == 0 and e["D2"]["state"] == "REVISION")
    proposal(c, 1, {"D1": "(a)", "D2": "(b)"}, extra=f"{D.w('DEPENDS')} D2 D1\n")
    vote_all(c, 1, {"D1": 5, "D2": 5}, before=e)
    rc, _ = run("count", c, 1)
    check("then both approved at round 1", rc == 0 and outcome(c, 1)["D2"]["state"] == "APPROVED"
          and outcome(c, 1)["D1"]["state"] == "APPROVED")

    # --- 4. integrity: jury changed, outcome retouched, re-vote, seals not reported (A1–A4, L2, L3, F3, F12)
    c = simple(base, "jury_changed", {"D1": 4})
    run("count", c, 0)
    g = json.loads((c / D.f("jury.json")).read_text())
    g[D.key("jurors")][1] = {D.key("role"): "rovesciatore", D.key("fresh_on_subject"): True}
    (c / D.f("jury.json")).write_text(json.dumps(g))
    (c / D.rnd(0) / D.vote("avversario")).rename(c / D.rnd(0) / D.vote("rovesciatore"))
    register(c, f"{D.rnd(0)}/{D.vote('rovesciatore')}")
    proposal(c, 1, {"D1": "(d1)"})
    vote_all(c, 1, {"D1": 5})
    refuse(f"{D.f('jury.json')} changed at round 1 (A1)", c, 1, "does not coincide with the recount")
    c = simple(base, "outcome_retouched", {"D1": 2})
    run("count", c, 0)
    e = json.loads((c / D.outcome(0)).read_text())
    decisions = e["decisioni" if D.lang == "it" else "decisions"]
    decisions["D1"]["stato" if D.lang == "it" else "state"] = "REVISIONE" if D.lang == "it" else "REVISION"
    (c / D.outcome(0)).write_text(json.dumps(e, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    proposal(c, 1, {"D1": "(d1)"})
    vote_all(c, 1, {"D1": 5})
    refuse("outcome of the previous round retouched (A2)", c, 1, "does not coincide with the recount")
    c = simple(base, "revote", {"D1": 3})
    run("count", c, 0)
    vote(c, 0, "statistico", {"D1": "yes"})
    refuse("re-vote on the same round (A4)", c, 0, "does not coincide with the recount")
    c = simple(base, "resealed", {"D1": 4})
    vote(c, 0, "statistico", {"D1": "yes"}, seal_it=False)
    refuse(f"vote rewritten and resealed, not reported in {D.f('SEALS.md')} (A3)", c, 0, D.f("SEALS.md"))
    c = simple(base, "without_seals", {"D1": 5})
    (c / D.f("SEALS.md")).unlink()
    refuse(f"{D.f('SEALS.md')} missing", c, text=f"{D.f('SEALS.md')} is missing")
    c = simple(base, "false_proposal", {"D1": 5})
    p = c / D.rnd(0) / D.f("PROPOSAL.md")
    p.write_text(p.read_text().replace("# proposal", "# proposal retouched"))
    refuse("proposal with a false seal", c, text="the seal does not match the bytes")

    # --- 5. malformed votes (A9, A10, minor F)
    c = simple(base, "no_without_revision", {"D1": 4})
    vote(c, 0, "statistico", {"D1": "no"}, without="D1")
    refuse("no without REVISION", c, text=f"without {D.w('REVISION')}")
    c = simple(base, "yes_without_condition", {"D1": 5})
    vote(c, 0, "garante", {"D1": "yes"}, without="D1")
    refuse("yes without CONDITION", c, text=f"without {D.w('CONDITION')}")
    c = simple(base, "double_vote", {"D1": 4})
    vote(c, 0, "statistico", {"D1": "no"}, extra=f"{D.w('VOTE')} D1 {D.yes_no('yes')}\n")
    refuse("double vote", c, text=f"two {D.w('VOTE')} lines")
    c = simple(base, "vote_in_block", {"D1": 4})
    vote(c, 0, "statistico", {}, extra=f"```\n{D.w('VOTE')} D1 {D.yes_no('yes')}\n{D.w('CONDITION')} D1 none\n"
                                       f"{D.w('CLASS')} D1 {D.cls('ordinary')}\n```\n{D.w('VOTE')} D1: no\n")
    refuse("true vote near-conforming, fake vote in a ``` block (A9)", c, text="not conforming")
    c = simple(base, "only_block", {"D1": 4})
    vote(c, 0, "statistico", {}, extra=f"```\n{D.w('VOTE')} D1 {D.yes_no('yes')}\n{D.w('CONDITION')} D1 none\n"
                                       f"{D.w('CLASS')} D1 {D.cls('ordinary')}\n```\n")
    refuse("the lines in a ``` block do not count: vote missing (A9)", c, text="the vote on D1 is missing")
    c = simple(base, "prose", {"D1": 5})
    vote(c, 0, "logico", {"D1": "yes"},
         extra=f"# {D.w('VOTE').title()} of the logician\n{D.w('CLASS').lower()} (iii) of the convergence\n"
               f"{D.w('OPTION').title()} chosen: the (a)\n- **{D.w('CONDITION')} #1** (the link) stays\n"
               f"{D.w('VOTE')} final: see above\n")
    rc, out = run("count", c, 0)
    check("prose that starts with a keyword is not a protocol line", rc == 0, out)
    c = simple(base, "lowercase", {"D1": 4})
    vote(c, 0, "statistico", {}, extra=f"{D.w('VOTE').lower()} D1 {D.yes_no('yes')}\n{D.w('CONDITION')} D1 none\n"
                                       f"{D.w('CLASS')} D1 {D.cls('ordinary')}\n")
    refuse(f"«{D.w('VOTE').lower()} D1 {D.yes_no('yes')}» in lowercase is near-conforming", c, text="not conforming")
    c = simple(base, "list", {"D1": 4})
    vote(c, 0, "statistico", {}, extra=f"- {D.w('VOTE')} D1 {D.yes_no('yes')}\n{D.w('CONDITION')} D1 none\n"
                                       f"{D.w('CLASS')} D1 {D.cls('ordinary')}\n")
    refuse(f"«- {D.w('VOTE')} D1 {D.yes_no('yes')}» in a list is near-conforming", c, text="not conforming")
    c = simple(base, "accent", {"D1": 4})
    (c / D.rnd(0) / D.vote("statistico")).write_text(seal(f"{D.w('VOTE')} D1 sì\n{D.w('CONDITION')} D1 none\n"
                                                         f"{D.w('CLASS')} D1 {D.cls('ordinary')}\n"))
    register(c, f"{D.rnd(0)}/{D.vote('statistico')}")
    rc, _ = run("count", c, 0)
    check(f"«{D.w('VOTE')} D1 sì» with the accent is yes (A10)", rc == 0 and outcome(c, 0)["D1"]["state"] == "APPROVED")
    c = simple(base, "class_missing", {"D1": 5})
    (c / D.rnd(0) / D.vote("statistico")).write_text(seal(f"{D.w('VOTE')} D1 {D.yes_no('yes')}\n{D.w('CONDITION')} D1 none\n"))
    register(c, f"{D.rnd(0)}/{D.vote('statistico')}")
    refuse("vote without CLASS (F13)", c, text=D.w("CLASS"))
    c = simple(base, "vote_missing", {"D1": 5, "D2": 5})
    vote(c, 0, "logico", {"D1": "yes"})
    refuse("vote missing on a decision", c, text="the vote on D2 is missing")
    c = simple(base, "extraneous_line", {"D1": 5})
    vote(c, 0, "logico", {"D1": "yes"}, extra=f"{D.w('CONDITION')} D9 none\n")
    refuse("line on a decision not under examination", c, text="not under examination")
    c = simple(base, "extraneous", {"D1": 5})
    vote(c, 0, "creativo", {"D1": "yes"})
    refuse("vote of someone who is not a juror", c, text="extraneous")
    c = simple(base, "traversal", {"D1": 5})
    (c / D.rnd(0) / "a").mkdir()
    refuse("extraneous entry in the folder of the round (A8)", c, text="extraneous entries")

    # --- 6. composition (A5–A8, F2, L9, binding jury)
    def jj(roles, fresh=None, prov=()):
        fresh = roles if fresh is None else fresh
        return [{"role": r, "fresh_on_subject": r in fresh, "provisional": r in prov} for r in roles]
    cases = [
        ("even jurors", jj(ROLES5[:4]), {}, "odd number"),
        ("3 jurors", jj(ROLES5[:3]), {}, "from 5 to 9"),
        ("11 jurors", jj(ROLES5 + ["formalista", "creativo", "fonti", "prestazioni", "sviluppatore", "metrologo"]),
         {"rapporteur": "rovesciatore"}, "from 5 to 9"),
        ("without guarantor", jj(["creativo", "avversario", "logico", "debugger", "statistico"]), {}, "guarantor"),
        ("without adversary", jj(["garante", "creativo", "logico", "debugger", "statistico"]), {}, "an adversary is missing"),
        ("code without debugger", jj(["garante", "avversario", "logico", "creativo", "statistico"]),
         {"authority": "recommendation"}, "the debugger is missing"),
        ("figures without statistician", jj(["garante", "avversario", "logico", "debugger", "creativo"]), {},
         "the statistician is missing"),
        ("binding without logician", jj(["garante", "avversario", "creativo", "debugger", "statistico"]), {},
         "the logician, the debugger and an adversary are needed"),
        ("rapporteur among the jurors", jj(ROLES5), {"rapporteur": "logico"}, "cannot vote"),
        ("fewer than half fresh", jj(ROLES5, fresh=["garante", "logico"]), {}, "at least half"),
        ("invented role (A6)", jj(["garante", "avversario", "logico", "debugger", "amico"]), {"touches_numbers": False},
         "is not among the agents"),
        ("role with a path (A8)", jj(["garante", "avversario", "logico", "debugger", "a/../garante"]),
         {"touches_numbers": False}, "not matching"),
        ("provisional without card", jj(ROLES5[:4] + ["crittografia"], prov=["crittografia"]), {}, "without a sealed card"),
        ("touches_code missing (A7)", None, {"touches_code": None}, D.key("touches_code")),
        ("authority missing", None, {"authority": None}, D.key("authority")),
        ("plenary of 5 (A5, F2)", None, {"classification": "plenary"}, "plenary: missing"),
    ]
    for name, jurors, extra, reason in cases:
        c = jury(base, "comp_" + "".join(ch if ch.isalnum() else "_" for ch in name), jurors=jurors, **extra)
        proposal(c, 0, {"D1": "(a)"})
        for x in roles_of(c):
            if "/" in x:
                continue
            vote(c, 0, x, {"D1": "yes"})
        refuse(f"composition: {name}", c, text=reason)
    c = jury(base, "recusal_and_vote")
    (c / DIALECTS[D.lang]["recusal"].format(x="logico")).write_text("not competent\n")
    proposal(c, 0, {"D1": "(a)"})
    vote_all(c, 0, {"D1": 5})
    refuse("RECUSAL and VOTE of the same role (adversary L3)", c, text="whoever recuses")
    c = jury(base, "comp_good_7", jurors=jj(ROLES5 + ["rovesciatore", "crittografia"], fresh=ROLES5[:4],
                                             prov=["crittografia"]))
    (c / DIALECTS[D.lang]["card"].format(x="crittografia")).write_text(seal("# provisional card\n"))
    proposal(c, 0, {"D1": "(a)"})
    vote_all(c, 0, {"D1": 7})
    rc, _ = run("count", c, 0)
    check("correct composition of 7 with a provisional expert with a card → accepted", rc == 0)
    known = sorted(FAKE_ROLES)
    voters = [r for r in known if r not in ("formalista", "arbitro")]
    c = jury(base, "whole_plenary", jurors=jj(voters), classification="plenary")
    proposal(c, 0, {"D1": "(a)"})
    vote_all(c, 0, {"D1": len(voters)})
    rc, _ = run("count", c, 0)
    check(f"plenary with all the {len(voters)} voting roles, fresh instances → accepted",
          rc == 0 and outcome(c, 0)["D1"]["state"] == "APPROVED")
    c = jury(base, "plenary_tie", jurors=jj(voters[:-1]), classification="plenary")
    refuse("plenary without one role", c, text="plenary: missing")

    # --- 6b. light jury: three jurors, test before the vote, one round, then the ordinary jury
    def light(name, jurors=None, **kw):
        j3 = jurors or [{"role": r, "fresh_on_subject": True} for r in ("garante", "avversario", "prestazioni")]
        return jury(base, name, jurors=j3, form="light", touches_numbers=False, touches_code=False, **kw)
    PASS = f"{D.w('TEST')} D1 python3 -I quick_test.py (expected: rc 0)\n{D.w('TEST-OUTCOME')} D1 {DIALECTS[D.lang]['test']['pass']}\n"
    FAIL = PASS.replace(DIALECTS[D.lang]["test"]["pass"] + "\n", DIALECTS[D.lang]["test"]["fail"] + "\n")

    def vote3(c, r, votes, cls="light", change=()):
        for role, v in zip(roles_of(c), votes):
            vote(c, r, role, {"D1": v}, cls=cls if not isinstance(cls, list) else cls[roles_of(c).index(role)],
                 change=change)
    c = light("light_ok")
    proposal(c, 0, {"D1": "(a)"}, extra=PASS)
    vote3(c, 0, ["yes", "yes", "yes"])
    rc, out = run("count", c, 0)
    check("light jury: consensus and a passing test → APPROVED", rc == 0 and outcome(c, 0)["D1"]["state"] == "APPROVED", out)
    c = light("light_test_fails")
    proposal(c, 0, {"D1": "(a)"}, extra=FAIL)
    vote3(c, 0, ["yes", "yes", "yes"])
    rc, out = run("count", c, 0)
    check("light jury: the test fails → REJECTED even with consensus",
          rc == 0 and outcome(c, 0)["D1"]["state"] == "REJECTED", out)
    c = light("light_escalation")
    proposal(c, 0, {"D1": "(a)"}, extra=PASS)
    vote3(c, 0, ["yes", "yes", "no"])
    rc, _ = run("count", c, 0)
    check("light jury: majority → REVISION", rc == 0 and outcome(c, 0)["D1"]["state"] == "REVISION")
    proposal(c, 1, {"D1": "(a)"}, extra=PASS)
    vote3(c, 1, ["yes", "yes", "no"])
    rc, out = run("count", c, 1)
    check("light jury: after a single round without consensus → TO_JURY (the ordinary jury)",
          rc == 0 and outcome(c, 1)["D1"]["state"] == "TO_JURY", out)
    refuse("light jury: a second revision round", c, 2)
    c = light("light_class")
    proposal(c, 0, {"D1": "(a)"}, extra=PASS)
    vote3(c, 0, ["yes", "yes", "yes"], cls=["light", "ordinary", "light"])
    rc, out = run("count", c, 0)
    check("light jury: a juror wants it ordinary → TO_JURY", rc == 0 and outcome(c, 0)["D1"]["state"] == "TO_JURY", out)
    c = light("light_without_test")
    proposal(c, 0, {"D1": "(a)"})
    vote3(c, 0, ["yes", "yes", "yes"])
    refuse("light jury without TEST and TEST-OUTCOME", c, text=f"{D.w('TEST')} and {D.w('TEST-OUTCOME')}")
    for name, roles3, reason in [
            ("five jurors", ["garante", "avversario", "prestazioni", "logico", "statistico"], "3 are needed"),
            ("without critic", ["garante", "logico", "prestazioni"], "a critic is missing"),
            ("without competent", ["garante", "avversario", "debugger"], "the role competent"),
            ("without guarantor", ["logico", "avversario", "prestazioni"], "the guarantor of the goal is missing")]:
        c = light("light_" + name.replace(" ", "_"), jurors=[{"role": r, "fresh_on_subject": True} for r in roles3])
        proposal(c, 0, {"D1": "(a)"}, extra=PASS)
        vote3(c, 0, ["yes"] * len(roles3))
        refuse(f"light jury {name}", c, text=reason)

    c = jury(base, "g2_by_default", protocol=None, authority="recommendation")
    proposal(c, 0, {"D1": "(a)"})
    vote_all(c, 0, {"D1": 5})
    refuse("G2 by default: without the protocol field the G2 rules hold", c, text=f"{D.w('SEAL')} {D.f('jury.json')}")
    c = jury(base, "light_plenary", jurors=[{"role": r, "fresh_on_subject": True} for r in ("garante", "avversario", "prestazioni")],
             form="light", classification="plenary", touches_numbers=False, touches_code=False)
    proposal(c, 0, {"D1": "(a)"}, extra=f"{D.w('TEST')} D1 x\n{D.w('TEST-OUTCOME')} D1 {DIALECTS[D.lang]['test']['pass']}\n")
    for role in ("garante", "avversario", "prestazioni"):
        vote(c, 0, role, {"D1": "yes"}, cls="light")
    refuse("a light jury does not hold for a plenary", c, text="does not apply to a plenary")
    # --- 6c. protocol G2: sealed jury, delegation by decision, PREFER among the OPTIONS, previous, plenary
    def fix(c):
        h = hashlib.sha256((c / D.f("jury.json")).read_bytes()).hexdigest()
        add_seal_line(c, f"{D.w('SEAL')} {D.f('jury.json')} {h}")
    c = jury(base, "g2_without_seal", protocol="G2", authority="recommendation")
    proposal(c, 0, {"D1": "(a)"})
    vote_all(c, 0, {"D1": 5})
    refuse(f"G2: {D.f('jury.json')} without a seal", c, text=f"{D.w('SEAL')} {D.f('jury.json')}")
    c = jury(base, "g2_ok", protocol="G2", authority="recommendation")
    fix(c)
    proposal(c, 0, {"D1": "(a)"})
    vote_all(c, 0, {"D1": 5})
    rc, out = run("count", c, 0)
    check(f"G2: {D.f('jury.json')} sealed → counted", rc == 0 and outcome(c, 0)["D1"]["state"] == "RECOMMENDED", out)
    add_seal_line(c, f"{D.w('SEAL')} {D.rnd(0)}/{D.vote('ghost')} " + "0" * 64)
    (c / D.outcome(0)).unlink()
    refuse("G2: an orphan SEAL", c, text="orphan")
    c = jury(base, "g2_without_delegation", protocol="G2")
    fix(c)
    proposal(c, 0, {"D1": "(a)"})
    vote_all(c, 0, {"D1": 5})
    refuse(f"G2: binding without {D.f('DELEGATION.md')}", c, text=D.f("DELEGATION.md"))
    c = jury(base, "g2_delegation", protocol="G2", delegation=D.f("DELEGATION.md"))
    (c / D.f("DELEGATION.md")).write_text(seal(f"{D.w('DELEGATED')} D1\n"))
    register(c, D.f("DELEGATION.md"))
    fix(c)
    proposal(c, 0, {"D1": "(a)", "D2": "(b)"})
    vote_all(c, 0, {"D1": 5, "D2": 5})
    rc, out = run("count", c, 0)
    e = outcome(c, 0) if rc == 0 else {}
    check("G2: the delegated decision is APPROVED, the one not delegated RECOMMENDED",
          rc == 0 and e["D1"]["state"] == "APPROVED" and e["D2"]["state"] == "RECOMMENDED", out)
    c = jury(base, "g2_prefer", protocol="G2", authority="recommendation")
    fix(c)
    proposal(c, 0, {"D1": "(a)"}, option_list={"D1": "(a) | (b)"})
    for role in ROLES5:
        vote(c, 0, role, {"D1": "yes"}, extra=f"{D.w('PREFER')} D1 (zeta)\n" if role == "logico" else "")
    refuse("G2: PREFER outside the OPTIONS list", c, text=D.w("PREFER"))
    c1 = jury(base, "g2_first", protocol="G2", authority="recommendation")
    fix(c1)
    proposal(c1, 0, {"D1": "(a)"}, option_list={"D1": "(a) | (b)"})
    vote_all(c1, 0, {"D1": 1})
    run("count", c1, 0)
    c2 = jury(base, "g2_after", protocol="G2", authority="recommendation", previous=["g2_first"])
    fix(c2)
    proposal(c2, 0, {"D1": "(a)"}, option_list={"D1": "(a) | (b)"})
    vote_all(c2, 0, {"D1": 5})
    refuse("G2: an option already REJECTED in a previous jury is not proposed again", c2, text="already REJECTED")
    c3 = jury(base, "g2_repropose1", protocol="G2", authority="recommendation")
    fix(c3)
    proposal(c3, 0, {"D1": "(a)"}, option_list={"D1": "(a) | (b)"})
    for i, role in enumerate(ROLES5):
        vote(c3, 0, role, {"D1": "yes"}, extra=f"{D.w('PREFER')} D1 (b)\n" if i < 3 else "")
    run("count", c3, 0)
    c4 = jury(base, "g2_repropose2", protocol="G2", authority="recommendation", previous=["g2_repropose1"])
    fix(c4)
    proposal(c4, 0, {"D1": "(a)"}, option_list={"D1": "(a) | (b)"})
    for i, role in enumerate(ROLES5):
        vote(c4, 0, role, {"D1": "yes"}, extra=f"{D.w('PREFER')} D1 (b)\n" if i < 3 else "")
    rc, out = run("count", c4, 0)
    check("G2: a second TO_REPROPOSE becomes TO_USER, also in the written outcome",
          rc == 0 and outcome(c4, 0)["D1"]["state"] == "TO_USER", out)
    rel = ["garante", "avversario", "logico", "debugger", "statistico", "rovesciatore", "creativo"]
    cp = jury(base, "g2_plenary", jurors=[{"role": r, "fresh_on_subject": True} for r in rel],
              protocol="G2", classification="plenary", authority="recommendation", relevance=D.f("RELEVANCE.md"))
    (cp / D.f("RELEVANCE.md")).write_text(seal("".join(f"{D.w('RELEVANT')} {r}\n" for r in rel)))
    register(cp, D.f("RELEVANCE.md"))
    fix(cp)
    proposal(cp, 0, {"D1": "(a)"})
    for i, role in enumerate(rel):
        vote(cp, 0, role, {"D1": "yes"}, cls="plenary" if i == 0 else "ordinary")
    rc, out = run("count", cp, 0)
    check("G2: plenary with the relevant roles only; a plenary CLASS does not send it back to itself",
          rc == 0 and outcome(cp, 0)["D1"]["state"] == "RECOMMENDED", out)

    # --- 7. input errors with a message (A11)
    c = base / "empty"
    c.mkdir()
    refuse("folder without a jury file", c, text="jury.json")
    c = simple(base, "negative_round", {"D1": 5})
    refuse("negative round", c, -1, "integer")
    refuse("round not an integer", c, "one", "integer")
    c = jury(base, "jury_not_json")
    (c / D.f("jury.json")).write_text("{not json")
    refuse(f"{D.f('jury.json')} not json", c, text="is not json")
    c = simple(base, "skip", {"D1": 3})
    proposal(c, 1, {"D1": "(d1)"})
    vote_all(c, 1, {"D1": 5})
    refuse("round 1 without the count of round 0", c, 1, f"{D.outcome(0)} is missing")

    # --- 8. threshold of the experts (§4; A13–A16, F9, F10)
    import jury as J
    reg_words = DIALECTS[D.lang]["register"]
    root = base / "tree"
    plen = f"{reg_words['plenary']}_P1"
    for cv in ("G1", "G2", "G3", "G1bis", plen):
        (root / cv).mkdir(parents=True)
    head = ["# register", "", "| date | convening | requester | skill | subject | reason |", "|---|---|---|---|---|---|"]
    m = "none of the roles covers the skill"

    def reg(rows, closed=()):
        p = base / f"reg_{len(results)}.md"
        p.write_text("\n".join(head + [f"| 2026-11-16 | {cv} | {who} | `{s}` | x | {why} |" for cv, who, s, why in rows]
                               + ["", "## Closed"] + list(closed)) + "\n")
        return p

    def threshold(rows, closed=()):
        return J.requests(reg(rows, closed), root)
    coord = reg_words["coordinator"]
    s = threshold([("G1", "logico", "alfa", m), ("G1", "debugger", "alfa", m), ("G1", "avversario", "alfa", m)])
    check("simultaneous: 3 requesters in one convening → to create", s["alfa"]["to_create"])
    s = threshold([("G1", "logico", "alfa", m), ("G1", "Logico", "alfa", m), ("G1", f"{reg_words['prefix']}logico", "alfa", m)])
    check("the same requester in three spellings counts once (A13, F9)", s["alfa"]["requesters"] == 1
          and not s["alfa"]["to_create"])
    s = threshold([("G1", "logico", "gamma", m), ("G2", "logico", "gamma", m), ("G2", "statistico", "gamma", m)])
    check("accumulated: 3 requests, 2 convenings, 2 requesters → to create", s["gamma"]["accumulated"])
    s = threshold([("G1", coord, "delta", m), ("G2", coord.title(), "delta", m), ("G3", coord, "delta", m),
                   ("G3", "logico", "delta", m)])
    check("the coordinator counts once and not as a distinct requester (A14)", not s["delta"]["to_create"])
    s = threshold([("G1", "logico", "eps", m), ("G1bis", coord, "eps", m), ("G1bis", "debugger", "eps", m)])
    check("existing convening: accumulated with the coordinator once → to create", s["eps"]["to_create"])
    for name, rows in (("convening that does not exist → refused (A15)", [("G9", "logico", "eta", m)]),
                       ("unknown requester → refused", [("G1", "amico", "eta", m)]),
                       ("reason «-» → refused (A16)", [("G1", "logico", "eta", "-")])):
        try:
            threshold(rows)
            check(name, False)
        except J.Error:
            check(name, True)
    p = reg([("G1", "logico", "eta", m)])
    p.write_text(p.read_text() + "| 2026-11-16 | G1 | logico | `Eta_X` | x | m |\n")
    try:
        J.requests(p, root)
        check("non-conforming row (uppercase id) → refused, not ignored (A16)", False)
    except J.Error:
        check("non-conforming row (uppercase id) → refused, not ignored (A16)", True)
    s = threshold([("G1", "logico", "teta", m), ("G1", "debugger", "teta2", m), ("G1", "avversario", "teta2", m)],
                  closed=[f"- `teta2`: {reg_words['merged']} `teta`, same skill"])
    check("«merged into» adds to the target id (A16)", s.get("teta", {}).get("to_create") and "teta2" not in s)
    s = threshold([("G1", "logico", "zeta", m), ("G1", "debugger", "zeta", m), ("G1", "avversario", "zeta", m)],
                  closed=[f"- `zeta`: {reg_words['created']}, n. 30"])
    check("an id already created no longer counts", "zeta" not in s)
    s = threshold([(plen, r, "iota", m) for r in ("logico", "debugger", "avversario", "statistico")])
    check("plenary: 4 requesters are not enough, 5 are needed (F10)", not s["iota"]["to_create"])
    s = threshold([("G1", f"{reg_words['provisional']}kappa", "kappa", m), ("G1", "logico", "kappa", m),
                   ("G1", "debugger", "kappa", m)])
    check("the provisional expert does not count for its own creation (F10)", not s["kappa"]["to_create"])


# --- the checks of the migration ---

def make_mixed(base, name, dialect, words, extra_vote=""):
    """A G2 jury of five with two decisions; dialect: names of files and keys; words: 'it', 'en' or 'mixed' (English
    VOTE lines with Italian values)."""
    global D
    saved, D = D, Dialect(dialect)
    try:
        c = jury(base, name, protocol=None, authority="recommendation", delegation="-")
        h = hashlib.sha256((c / D.f("jury.json")).read_bytes()).hexdigest()
        add_seal_line(c, f"{D.w('SEAL')} {D.f('jury.json')} {h}")
        pw = Dialect("en" if words == "en" else "it")
        vw = Dialect("en" if words in ("en", "mixed") else "it")
        d = c / D.rnd(0)
        d.mkdir()
        body = "# proposal\n"
        for k, o in (("D1", "(a)"), ("D2", "(c)")):
            body += f"{pw.w('OPTION')} {k} {o}\n{pw.w('OPTIONS')} {k} {o} | (z)\n{pw.w('OPERATIVE')} {k} do {o}\n"
        (d / D.f("PROPOSAL.md")).write_text(seal(body))
        register(c, f"{D.rnd(0)}/{D.f('PROPOSAL.md')}")
        for i, r in enumerate(ROLES5):
            lines = []
            for k, v in (("D1", "yes"), ("D2", "yes" if i < 3 else "no")):
                yes = "sì" if words == "mixed" else vw.yes_no("yes")
                lines.append(f"{vw.w('VOTE')} {k} {yes if v == 'yes' else 'no'}")
                lines.append(f"{vw.w('CONDITION')} {k} none" if v == "yes" else f"{vw.w('REVISION')} {k} fix it")
                lines.append(f"{vw.w('CLASS')} {k} {'ordinaria' if words == 'mixed' else vw.cls('ordinary')}")
            (d / D.vote(r)).write_text(seal("\n".join(lines) + "\n" + extra_vote))
            register(c, f"{D.rnd(0)}/{D.vote(r)}")
        return c
    finally:
        D = saved


def canonical_without_shas(c, r=0):
    p = next(Path(c).glob(f"*_{r}.json"))
    e = C.to_canonical(json.loads(p.read_text()), C.OUTCOME_SCHEMA)
    e.pop("vote_shas", None)
    e.pop("jury_sha", None)
    for d in e["decisions"].values():
        d.pop("proposal_sha", None)
    return e, p.name


def migration(base):
    global D
    base = Path(base)
    D = Dialect("en")
    # M4: the same jury with it, en and mixed lines
    outs = {}
    for name, dia, words in (("m4_it", "it", "it"), ("m4_en", "en", "en"), ("m4_mixed", "it", "mixed"),
                             ("m4_en_it_words", "en", "it")):
        c = make_mixed(base, name, dia, words)
        rc, out = run("count", c, 0, tests=False)
        check(f"M4: jury {name} counts", rc == 0, out)
        if rc == 0:
            outs[name] = canonical_without_shas(c)
    if len(outs) == 4:
        ref = outs["m4_it"][0]
        check("M4: same canonical outcome in it, en and mixed lines (except vote_shas, proposal_sha, jury_sha)",
              all(v[0] == ref for v in outs.values()), {k: v[0] for k, v in outs.items()})
        check("M4: giuria.json → ESITO, jury.json → OUTCOME", outs["m4_it"][1] == "ESITO_giro_0.json"
              and outs["m4_en"][1] == "OUTCOME_round_0.json")
        check("M4: an outcome written by 5.0 carries the lexicon key", ref.get("lexicon") == 5)
        rc, out = run("count", base / "m4_it", 0, tests=False)
        check("M4: the recount of a 5.0 outcome is identical", rc == 0, out)
    # M11: the L5 lexicon
    c = make_mixed(base, "m11_dup", "it", "it", extra_vote="VOTE D1 no\n")
    rc, out = run("count", c, 0, tests=False)
    check("M11: VOTO D1 si + VOTE D1 no → error (duplicates after normalization)", rc == 2 and "two" in out, out)
    c = make_mixed(base, "m11_dup_accent", "en", "mixed", extra_vote="VOTO D1 no\n")
    rc, out = run("count", c, 0, tests=False)
    check("M11: VOTE D1 sì + VOTO D1 no → error", rc == 2 and "two" in out, out)
    c = make_mixed(base, "m11_test_design", "en", "en", extra_vote="## Test Design\nChange Detection is prose\n")
    rc, out = run("count", c, 0, tests=False)
    check("M11: «## Test Design» in a VOTE is not an error", rc == 0, out)
    c = make_mixed(base, "m11_near", "en", "en", extra_vote="Vote D1 yes\n")
    rc, out = run("count", c, 0, tests=False)
    check("M11: a near-conforming English line → error", rc == 2 and "not conforming" in out, out)
    c = make_mixed(base, "m11_round_token", "it", "it")
    (c / "SIGILLI.md").write_text((c / "SIGILLI.md").read_text().replace("SIGILLO giro_0/", "SIGILLO round_0/"))
    rc, out = run("count", c, 0, tests=False)
    check("M11: round_0 in an Italian jury counts as giro_0", rc == 0, out)
    c = make_mixed(base, "m11_round9", "it", "it")
    (c / "SIGILLI.md").write_text((c / "SIGILLI.md").read_text() + "SIGILLO round_9/PROPOSTA.md " + "0" * 64 + "\n")
    rc, out = run("count", c, 0, tests=False)
    check("M11: round_9 that does not exist → error", rc == 2 and "round" in out, out)
    c = make_mixed(base, "m11_delegated", "en", "en")
    g = json.loads((c / "jury.json").read_text())
    g.update(authority="binding", delegation="DELEGATION.md")
    (c / "jury.json").write_text(json.dumps(g))
    (c / "DELEGATION.md").write_text(seal("Delegated D1\n", "en"))
    s = [x for x in (c / "SEALS.md").read_text().splitlines() if not x.startswith("SEAL jury.json")]
    s += [f"SEAL jury.json {hashlib.sha256((c / 'jury.json').read_bytes()).hexdigest()}",
          f"SEAL DELEGATION.md {seal_of(c / 'DELEGATION.md')}"]
    (c / "SEALS.md").write_text("\n".join(s) + "\n")
    rc, out = run("count", c, 0, tests=False)
    check("M11: «Delegated D1» in DELEGATION.md → NEAR error", rc == 2 and "DELEGATION.md" in out
          and "not conforming" in out, out)
    # M13: one dialect per file, one definition per juror
    c = make_mixed(base, "m13_both_seals", "it", "it")
    (c / "SEALS.md").write_text("x\n")
    rc, out = run("count", c, 0, tests=False)
    check("M13: SIGILLI.md + SEALS.md → error of jury_file", rc == 2 and "SIGILLI.md" in out and "SEALS.md" in out, out)
    other = Path(FAKE_AGENTS) / "sciame-logico.md"
    other.write_text("---\nname: sciame-logico\n---\nanother body\n")
    rc, out = run("count", base / "m4_en", 0, tests=False)
    amb = TEXT["jury_ambiguous_role"].split("{")[0]
    check("M13: sciame-x and swarmer-x with different bodies → jury_ambiguous_role",
          rc == 2 and "logico" in out and amb in out, out)
    other.unlink()
    # M12: the register with the requesters in both languages
    import jury as J
    root = base / "m12"
    for cv in ("G1", "G2", "nonplenaria", "plenaria_P1", "plenary_P2"):
        (root / cv).mkdir(parents=True)
    head = ["| date | convening | requester | skill | subject | reason |", "|---|---|---|---|---|---|"]
    m = "none of the roles covers the skill"

    def reg(rows):
        p = base / f"m12_{len(results)}.md"
        p.write_text("\n".join(head + [f"| 2026-11-16 | {cv} | {who} | `{s}` | x | {m} |" for cv, who, s in rows]) + "\n")
        return J.requests(p, root)
    a = reg([("G1", "coordinatore", "x"), ("G2", "coordinator", "x"), ("G2", "logico", "x"), ("G1", "debugger", "x")])
    b = reg([("G1", "coordinator", "x"), ("G2", "coordinator", "x"), ("G2", "logico", "x"), ("G1", "debugger", "x")])
    check("M12: coordinatore + coordinator count as the single form", a == b, (a, b))
    a = reg([("G1", "provvisorio:x", "x"), ("G1", "provisional:x", "x"), ("G1", "logico", "x"), ("G1", "debugger", "x")])
    b = reg([("G1", "provisional:x", "x"), ("G1", "logico", "x"), ("G1", "debugger", "x")])
    check("M12: provvisorio:x and provisional:x are both self requests", a == b and a["x"]["requesters"] == 2, (a, b))
    a = reg([("G1", "sciame-logico", "x"), ("G1", "swarmer-logico", "x"), ("G1", "logico", "x")])
    check("M12: sciame-x + swarmer-x + x count as one requester", a["x"]["requesters"] == 1 and not a["x"]["to_create"], a)
    a = reg([("nonplenaria", r, "y") for r in ("logico", "debugger", "avversario")])
    check("M12: «nonplenaria» does not raise the threshold", a["y"]["to_create"], a)
    a = reg([("plenaria_P1", r, "y") for r in ("logico", "debugger", "avversario", "statistico")])
    b = reg([("plenary_P2", r, "y") for r in ("logico", "debugger", "avversario", "statistico")])
    check("M12: «plenaria» and «plenary» need 5", not a["y"]["to_create"] and not b["y"]["to_create"], (a, b))
    # M5: every 4.0 jury of the fixtures is recounted byte for byte
    if not (FIXTURES / "EXPECTED.json").is_file():
        print("skipped M5: tests/fixtures/juries-4.0/ is not here (an installed copy does not carry the fixtures)")
        return
    exp = json.loads((FIXTURES / "EXPECTED.json").read_text(encoding="utf-8"))
    ag = base / "m5_agents"
    ag.mkdir()
    for r in exp["roles"]:
        (ag / f"sciame-{r}.md").write_text("finto\n")
    env5 = {k: v for k, v in env(tests=False).items()}
    env5["SWARMER_AGENTS_DIR"] = str(ag)
    work = base / "m5"
    shutil.copytree(FIXTURES, work)
    for name, x in sorted(exp["juries"].items()):
        c = work / name
        if "refused" in x:
            p = subprocess.run([sys.executable, "-I", "-B", str(JURY), "count", str(c), str(x["refused"])],
                               capture_output=True, text=True, stdin=subprocess.DEVNULL, env=env5)
            check(f"M5: {name}: refused by 5.0 as by 4.0", p.returncode == 2
                  and not (c / f"ESITO_giro_{x['refused']}.json").exists(), p.stdout + p.stderr)
            continue
        before = {r: (c / f"ESITO_giro_{r}.json").read_bytes() for r in x["rounds"]}
        same = True
        detail = ""
        for r in x["rounds"]:
            p = subprocess.run([sys.executable, "-I", "-B", str(JURY), "count", str(c), str(r)], capture_output=True,
                               text=True, stdin=subprocess.DEVNULL, env=env5)
            if p.returncode != 0 or (c / f"ESITO_giro_{r}.json").read_bytes() != before[r]:
                same = False
                detail = f"round {r}: rc {p.returncode} {p.stdout + p.stderr}"
        check(f"M5: {name}: recounted identical byte for byte", same, detail)
        last = c / f"ESITO_giro_{x['rounds'][-1]}.json"
        t = last.read_text(encoding="utf-8")
        last.write_text(t.replace('"n": ', '"n":  ', 1), encoding="utf-8")
        p = subprocess.run([sys.executable, "-I", "-B", str(JURY), "count", str(c), str(x["rounds"][-1])],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, env=env5)
        check(f"M5: {name}: an outcome retouched by one byte stays refused", p.returncode == 2, p.stdout + p.stderr)
    # B4: the lexicon comes from the sealed root file: without its outcomes, every 4.0 jury is recounted to the same bytes
    work = base / "m5_lost"
    shutil.copytree(FIXTURES, work)
    for name, x in sorted(exp["juries"].items()):
        if "refused" in x:
            continue
        c = work / name
        before = {r: (c / f"ESITO_giro_{r}.json").read_bytes() for r in x["rounds"]}
        for r in x["rounds"]:
            (c / f"ESITO_giro_{r}.json").unlink()
        if json.loads((c / "giuria.json").read_text(encoding="utf-8")).get("protocollo") == "G1.1":
            # G1.1 is recounted only from the outcome of round 0 the 4.0 wrote: lost, it is refused (never recomputed)
            p = subprocess.run([sys.executable, "-I", "-B", str(JURY), "count", str(c), "0"], capture_output=True,
                               text=True, stdin=subprocess.DEVNULL, env=env5)
            check(f"M5 (B4): {name}: G1.1 without its outcomes is refused", p.returncode == 2
                  and not (c / "ESITO_giro_0.json").exists(), p.stdout + p.stderr)
            continue
        detail = ""
        for r in x["rounds"]:
            p = subprocess.run([sys.executable, "-I", "-B", str(JURY), "count", str(c), str(r)], capture_output=True,
                               text=True, stdin=subprocess.DEVNULL, env=env5)
            if p.returncode != 0 or (c / f"ESITO_giro_{r}.json").read_bytes() != before[r]:
                detail = detail or f"round {r}: rc {p.returncode} {p.stdout + p.stderr}"
        check(f"M5 (B4): {name}: its outcomes deleted, recounted to the same bytes", not detail, detail)
    # B3: a 4.0 jury with a key the 4.0 accepted (not in the schema), sealed again, is recounted
    c = base / "m5_key" / "leggera_approvata"
    shutil.copytree(FIXTURES / "leggera_approvata", c)
    g = json.loads((c / "giuria.json").read_text(encoding="utf-8"))
    g["nota"] = "x"
    (c / "giuria.json").write_text(json.dumps(g, ensure_ascii=False), encoding="utf-8")
    s = (c / "SIGILLI.md").read_text(encoding="utf-8")
    old_sha = hashlib.sha256((FIXTURES / "leggera_approvata" / "giuria.json").read_bytes()).hexdigest()
    new_sha = hashlib.sha256((c / "giuria.json").read_bytes()).hexdigest()
    (c / "SIGILLI.md").write_text(s.replace(old_sha, new_sha), encoding="utf-8")
    e0 = c / "ESITO_giro_0.json"
    e0.write_text(e0.read_text(encoding="utf-8").replace(old_sha, new_sha), encoding="utf-8")
    p = subprocess.run([sys.executable, "-I", "-B", str(JURY), "count", str(c), "0"], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, env=env5)
    check("M5 (B3): a 4.0 giuria.json with a key more («nota»), sealed, is recounted", p.returncode == 0
          and old_sha in s, p.stdout + p.stderr)
    c = make_mixed(base, "m5_key_en", "en", "en")
    g = json.loads((c / "jury.json").read_text())
    g["note"] = "x"
    (c / "jury.json").write_text(json.dumps(g))
    rc, out = run("count", c, 0, tests=False)
    check("M5 (B3): an unknown key in a jury.json (5.0 only) stays an error", rc == 2 and "note" in out, out)


def main():
    global FAKE_AGENTS, D
    with tempfile.TemporaryDirectory() as base:
        ag = Path(base) / "_agents"
        ag.mkdir()
        for r in FAKE_ROLES:
            (ag / f"swarmer-{r}.md").write_text("fake\n")
        FAKE_AGENTS = str(ag)
        os.environ["SWARMER_AGENTS_DIR"] = FAKE_AGENTS   # for the functions called in this process
        for lang in ("en", "it"):
            D = Dialect(lang)
            d = Path(base) / lang
            d.mkdir()
            battery(d)
        d = Path(base) / "migration"
        d.mkdir()
        migration(d)
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
