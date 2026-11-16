#!/usr/bin/env python3
"""swarmer 5.0, protocol G (JURY.md): counts the votes of a jury and the threshold of the new experts.

    python3 -I swarmer/jury.py count <jury folder> <round>
    python3 -I swarmer/jury.py requests [swarmer/EXPERT_REQUESTS.md]

`count` recomputes from the sealed files every round from 0 to <round> (it does not trust the outcomes already
written), compares the seals with the clerk's SEALS.md, checks composition, votes, non-regression, dependencies and
limit, and writes OUTCOME_round_<r>.json. It exits with 0 if every check passes, with 2 otherwise (and then writes
nothing). An outcome already written must coincide with the recomputed one: a re-vote on the same round or a
retouched outcome are an error. It launches no agent.

Dialects (C.5): a jury with `jury.json` is English (round_<r>/, PROPOSAL.md, VOTE_<role>.md, SEALS.md,
OUTCOME_round_<r>.json …); a jury with the 4.0 root file keeps the 4.0 names (compat.JURY_FILES). The outcome is computed in canonical form
and written in the dialect of the jury, with the 4.0 serialization. Lexicons: fixed by the sealed root file, never by
an outcome: a `giuria.json` without the key "lessico" (every 4.0 jury) is counted exactly as the 4.0 did (L4) in every
round; a `giuria.json` with "lessico": 5 and every `jury.json` with the words of both languages (L5).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compat as C  # noqa: E402

BASE = HERE.parent if HERE.name in ("engine", C.OLD_TREE["engine"]) else HERE  # the swarm folder

ROLE_RE = re.compile(r"^[a-z][a-z0-9-]*$")
ADVERSARIES = {C.ROLES["adversary"], C.ROLES["inverter"]}
PASS = {C.ROLES["logician"], C.ROLES["debugger"]}   # with an adversary: mandatory in a binding jury (JURY.md §2)
ROUND_LIMIT = 3
ROUND_LIMIT_LIGHT = 1   # the light jury has a single revision round, then it goes to the ordinary jury
CRITICS = {C.ROLES["adversary"], C.ROLES["inverter"], C.ROLES["debugger"]}
FINAL = {"APPROVED", "RECOMMENDED", "REJECTED", "NOT_CONVERGED", "SUSPENDED", "TO_PLENARY", "TO_REPROPOSE",
         "TO_JURY", "TO_USER"}
LEXICON = 5
W = C.LINE_WORDS
PROPOSAL_WORDS = ("OPTION", "OPTIONS", "OPERATIVE", "DEPENDS", "INCOMPATIBLE", "TEST", "TEST-OUTCOME")
VOTE_WORDS = ("VOTE", "REVISION", "CONDITION", "CLASS", "CHANGE", "PREFER")


class Error(C.Error):
    pass


# --- where things are ---

def root() -> Path:
    v = C.env("SWARMER_ROOT")
    if v:
        return Path(v)
    for n in ("ROOT", C.STATE_NAMES["ROOT"]):
        p = BASE / n
        if p.is_file():
            return (BASE / p.read_text(encoding="utf-8").strip()).resolve()
    return BASE.parent


def agents_dir() -> Path:
    v = C.env("SWARMER_AGENTS_DIR")
    return Path(v) if v else root() / ".claude" / "agents"


def language() -> str:
    return C.language(BASE)


def texts() -> dict:
    out = {}
    for l in ("en", language()):
        p = BASE / "i18n" / f"{l}.json"
        if p.is_file():
            try:
                out.update(json.loads(p.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                pass
    return out


class _Keep(dict):
    def __missing__(self, k):
        return "{" + k + "}"


def msg(key: str, default: str | None = None, **kw) -> str:
    t = texts().get(key, default if default is not None else key)
    try:
        return str(t).format_map(_Keep(kw))
    except (ValueError, IndexError):
        return str(t)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- lexicons: L4 (exactly the 4.0, Italian words only) and L5 (both languages) ---

ID_IT = r"(D[0-9A-Za-z_.-]+)"
ID_EN = r"(D\d[0-9A-Za-z_.-]*)"
_VALUE = {
    "DEPENDS": None,   # two ids
    "TEST-OUTCOME": "test_outcome", "VOTE": "vote", "CLASS": "class",
}
_L4_VALUES = C.L4["values"]


def _alt(values: dict) -> str:
    return "(" + "|".join(sorted(map(re.escape, values), key=len, reverse=True)) + ")"


def _line_re(word: str, canon: str, ident: str, l4: bool):
    if canon == "DEPENDS":
        return re.compile(rf"^{re.escape(word)} {ident} {ident}\s*$")
    if canon in _VALUE:
        vals = _L4_VALUES[canon] if l4 else _alt(C.LINE_VALUES[_VALUE[canon]])
        return re.compile(rf"^{re.escape(word)} {ident} {vals}\s*$")
    return re.compile(rf"^{re.escape(word)} {ident} (.+?)\s*$")


class Lexicon:
    """The protocol lines of PROPOSAL and VOTE: word → (canonical word, strict expression), and the near-conformity
    expression (a near-conforming line is an error)."""

    def __init__(self, number: int):
        self.number = number
        words = PROPOSAL_WORDS + VOTE_WORDS
        self.lines = {}
        for canon in words:
            it = W[canon]
            self.lines[it] = (canon, _line_re(it, canon, ID_IT, number == 4))
            if number == 5:
                self.lines[canon] = (canon, _line_re(canon, canon, ID_EN, False))
        it_words = [W[c] for c in words]
        if number == 4:
            self.near = re.compile(r"^[\s\-*>#]*(?i:(" + "|".join(sorted(it_words, key=len, reverse=True))
                                   + r"))[\s:*]+D[0-9A-Za-z_.-]")
        else:
            self.near = re.compile(r"^[\s\-*>#]*(?:(?i:(" + "|".join(sorted(map(re.escape, it_words), key=len, reverse=True))
                                   + r"))[\s:*]+D[0-9A-Za-z_.-]|(?i:(" + "|".join(sorted(map(re.escape, words), key=len,
                                                                                     reverse=True))
                                   + r"))[\s:*]+D\d)")
        self.seal_line = C.SEAL_LINE_RE_L4 if number == 4 else C.SEAL_LINE_RE

    def canonical_value(self, canon: str, v: str) -> str:
        cat = _VALUE.get(canon)
        return C.LINE_VALUES[cat].get(v, v) if cat else v


L4, L5 = Lexicon(4), Lexicon(5)


def sealed(p: Path, lex: Lexicon):
    """(text before the seal, seal), if the seal matches; otherwise Error."""
    if not p.is_file():
        raise Error(f"{p} is missing")
    data = p.read_bytes()
    body, _, last = data.rstrip(b"\n").rpartition(b"\n")
    m = lex.seal_line.match(last.decode("utf-8", "replace"))
    if not m:
        raise Error(f"{p.name}: last line without a seal")
    body += b"\n"
    if sha(body) != m.group(1):
        raise Error(f"{p.name}: the seal does not match the bytes before it")
    return body.decode("utf-8"), m.group(1)


def valid_lines(text: str, name: str, allowed: set, lex: Lexicon):
    """The protocol lines outside the ``` blocks, as (canonical word, groups with canonical values); a
    near-conforming line is an error."""
    found, inside = [], False
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            inside = not inside
            continue
        if inside:
            continue
        q = lex.near.match(line)
        if not q:
            continue
        word = next(g for g in q.groups() if g).upper()
        entry = lex.lines.get(word)
        m = entry[1].match(line) if entry else None
        if not m or entry[0] not in allowed:
            raise Error(f"{name} l. {n}: line not conforming or not allowed here: «{line.strip()[:80]}»")
        hit = (entry[0], m.groups())
        canon, groups = hit
        if canon in _VALUE and _VALUE[canon]:
            groups = (groups[0], lex.canonical_value(canon, groups[1]))
        found.append((canon, groups))
    if inside:
        raise Error(f"{name}: ``` block not closed")
    return found


# --- the jury, its files and its dialect ---

class Jury:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.lang = C.jury_dialect(self.folder)
        p = self.file("jury.json")
        if not p.is_file():
            raise Error(f"{p.name} is missing")
        data = p.read_bytes()
        try:
            raw = json.loads(data)
        except json.JSONDecodeError as x:
            raise Error(f"{p.name} is not json: {x}")
        if not isinstance(raw, dict):
            raise Error(f"{p.name}: an object is needed")
        # a giuria.json keeps the keys the 4.0 accepted; jury.json exists only from 5.0 and is strict
        self.unknown = [] if self.lang == "it" else None
        self.g = C.to_canonical(raw, C.JURY_SCHEMA, p.name, self.unknown)
        self.sha = sha(data)
        # the lexicon of the whole jury and of every round, from the root file sealed before round 0 (C.5)
        lx = self.g.get("lexicon")
        if lx not in (None, LEXICON):
            raise Error(f"{p.name}: «{_jname(self, 'lexicon')}»: {LEXICON} or absent")
        self.lexicon = L4 if self.lang == "it" and lx is None else L5

    def file(self, canonical: str) -> Path:
        return C.jury_file(self.folder, canonical, self.lang)

    def name(self, canonical: str) -> str:
        return C.localize_path(canonical, self.lang, "jury")

    def outcome_path(self, r: int) -> Path:
        return self.file(f"OUTCOME_round_{r}.json")

    def round_lexicon(self, r: int) -> Lexicon:
        """The same for every round: the lexicon of the root file (an outcome, which can be lost, never chooses it)."""
        return self.lexicon


def limit(g):
    return ROUND_LIMIT_LIGHT if g.get("form") == "light" else ROUND_LIMIT


def known_roles() -> set[str]:
    """The roles of the swarm: the agents <prefix>-<id> of both prefixes. The same id with two different bodies is an
    error: a juror must have a single definition."""
    d = agents_dir()
    if not d.is_dir():
        raise Error(f"{d} is missing")
    out = {}
    for pre in C.AGENT_PREFIXES:
        for p in d.glob(f"{pre}-*.md"):
            rid = p.stem[len(pre) + 1:]
            body = _body(p)
            if rid in out and out[rid] != body:
                raise Error(msg("jury_ambiguous_role", "role «{role}» has two different agents: {a} and {b}",
                                role=rid, a=f"{C.AGENT_PREFIXES[0]}-{rid}", b=f"{C.AGENT_PREFIXES[1]}-{rid}"))
            out[rid] = body
    return set(out)


def _body(p: Path) -> str:
    t = p.read_text(encoding="utf-8", errors="replace")
    if t.startswith("---\n"):
        i = t.find("\n---", 4)
        if i >= 0:
            return t[i + 4:]
    return t


def recusals(j: Jury) -> list[tuple[str, str]]:
    out = []
    for pre in ("RECUSAL_", C.localize_path("RECUSAL_x.md", "it", "jury")[:-len("x.md")]):
        out += [(p.name, p.stem[len(pre):]) for p in j.folder.glob(f"{pre}*.md")]
    return out


def check_composition(j: Jury):
    g = j.g
    errors = []
    for field, typ in (("subject", str), ("rapporteur", str), ("clerk", str), ("jurors", list),
                       ("touches_code", bool), ("touches_numbers", bool), ("authority", str), ("delegation", str),
                       ("classification", str)):
        if not isinstance(g.get(field), typ):
            errors.append(f"field «{_jname(j, field)}» missing or of the wrong type")
    if errors:
        raise Error(f"{j.name('jury.json')}: " + "; ".join(errors))
    if g["authority"] not in ("binding", "recommendation"):
        errors.append("authority: «binding» or «recommendation»")
    if g["classification"] not in ("ordinary", "plenary"):
        errors.append("classification: «ordinary» or «plenary»")
    if g.get("protocol", "G2") not in ("G2", "G1.1"):
        errors.append("protocol: «G2» (default) or «G1.1»")
    if g.get("form", "ordinary") not in ("ordinary", "light"):
        errors.append("form: «ordinary» or «light»")
    light = g.get("form") == "light"
    if g.get("round_limit", limit(g)) != limit(g):
        errors.append(f"round_limit: the protocol fixes it at {limit(g)}")
    known = known_roles()
    roles = []
    for x in g["jurors"]:
        if not isinstance(x, dict) or not isinstance(x.get("role"), str):
            errors.append("a juror without «role»")
            continue
        r = x["role"]
        roles.append(r)
        if not ROLE_RE.match(r):
            errors.append(f"role «{r}» not matching {ROLE_RE.pattern}")
        elif x.get("provisional"):
            try:
                sealed(j.file(f"CARD_{r}.md"), j.lexicon)
            except Error as e:
                errors.append(f"provisional expert «{r}» without a sealed card: {e}")
        elif r not in known:
            errors.append(f"role «{r}» is not among the agents of the swarm and is not marked provisional")
    n = len(roles)
    if len(set(roles)) != n:
        errors.append("a role appears twice among the jurors")
    plenary = g["classification"] == "plenary"
    for who in ("rapporteur", "clerk"):
        if g[who] in roles:
            errors.append(f"the {who} ({g[who]}) cannot vote")
    if light and plenary:
        errors.append("the light jury does not apply to a plenary")
    if plenary and g2(g) and j.file("RELEVANCE.md").is_file():
        expected = relevant(j)
        if set(roles) != expected:
            errors.append("plenary: the voters are the relevant roles of the relevance file: missing "
                          + (", ".join(sorted(expected - set(roles))) or "none") + "; extra "
                          + (", ".join(sorted(set(roles) - expected)) or "none"))
    elif plenary:
        missing = sorted(known - set(roles) - {g["rapporteur"], g["clerk"]})
        if missing:
            errors.append("plenary: missing the roles " + ", ".join(missing))
        if not all(x.get("fresh_on_subject") for x in g["jurors"] if isinstance(x, dict)):
            errors.append("plenary: at the final vote every role votes with a fresh instance")
    elif light:
        if g["classification"] != "ordinary":
            errors.append("the light jury does not apply to a plenary")
        if n != 3:
            errors.append(f"light jury: {n} jurors, 3 are needed (competent, critic, guarantor)")
        if not CRITICS & set(roles):
            errors.append("light jury: a critic is missing (an adversary, an inverter or the debugger)")
        if not set(roles) - CRITICS - {C.ROLES["guarantor"]}:
            errors.append("light jury: the role competent for the function is missing")
    else:
        if not 5 <= n <= 9 or n % 2 == 0:
            errors.append(f"jurors {n}: from 5 to 9 are needed, in odd number")
        fresh = sum(1 for x in g["jurors"] if isinstance(x, dict) and x.get("fresh_on_subject"))
        if 2 * fresh < n:
            errors.append(f"fresh instances on the subject {fresh} of {n}: at least half are needed")
        prov = sum(1 for x in g["jurors"] if isinstance(x, dict) and x.get("provisional"))
        if 3 * prov > n:
            errors.append(f"provisional experts {prov} of {n}: at most a third")
    if C.ROLES["guarantor"] not in roles:
        errors.append("the guarantor of the goal is missing")
    if not light:
        if not ADVERSARIES & set(roles):
            errors.append("an adversary is missing (adversary or inverter)")
        if g["touches_code"] and C.ROLES["debugger"] not in roles:
            errors.append("the decision touches code and the debugger is missing")
        if g["touches_numbers"] and C.ROLES["statistician"] not in roles:
            errors.append("the decision touches thresholds or figures and the statistician is missing")
        if g["authority"] == "binding" and not PASS <= set(roles):
            errors.append("binding decision: the logician, the debugger and an adversary are needed")
    for fname, who in recusals(j):
        if who in roles:
            errors.append(f"{fname}: whoever recuses cannot be a juror")
    if errors:
        raise Error("composition: " + "; ".join(errors))
    return roles


def _jname(j: Jury, field: str) -> str:
    en, it, _t = C.JURY_SCHEMA.fields[(field,)]
    return it if j.lang == "it" else en


# --- the seals of the clerk ---

class Seals:
    """The SEAL lines of the seals file. In L4 the keys are the raw paths of the 4.0 (round directory and file name
    as written); in L5 they are (round or None, canonical name), and a round token that matches no round is an
    error."""

    def __init__(self, lexicon: Lexicon):
        self.l4 = lexicon.number == 4
        self.files = {}
        self.verified = set()

    def key(self, j: Jury, r, canonical: str):
        if self.l4:
            return (f"{C.ROUND_PREFIX['it']}{r}/" if r is not None else "") + C.localize_path(canonical, "it", "jury")
        return (r, canonical)

    def get(self, j: Jury, r, canonical: str):
        return self.files.get(self.key(j, r, canonical))

    def verified_in(self, r: int) -> set:
        if self.l4:
            return {d for (tok, d) in self.verified if tok == f"{C.ROUND_PREFIX['it']}{r}"}
        return {d for (rr, d) in self.verified if rr == r}

    def paths(self, j: Jury):
        """(description, path) of every sealed file, for the orphan check."""
        for k in self.files:
            if self.l4:
                yield k, j.folder / k
            else:
                r, name = k
                rel = (f"round_{r}/" if r is not None else "") + name
                yield j.name(rel), j.folder / j.name(rel)


SEAL_L4 = C.L4["seal"]
VERIFIED_L4 = C.L4["verified"]
_SW, _VW = (re.escape(W["SEAL"]), re.escape(W["INCOMPATIBLE-VERIFIED"]))
SEAL_L5 = re.compile(rf"^(?:{_SW}|SEAL) (?:([A-Za-z]+_[^/\s]*)/)?([A-Za-z0-9_.-]+\.(?:md|json)) ([0-9a-f]{{64}})\s*$")
VERIFIED_L5 = re.compile(rf"^(?:{_VW} (\S+) (D[0-9A-Za-z_.-]+)|INCOMPATIBLE-VERIFIED (\S+) (D\d[0-9A-Za-z_.-]*))\s*$")
_ROUND_ALT = "|".join(re.escape(x) for x in C.ROUND_PREFIX.values())
SEAL_NEAR = re.compile(rf"^[\s\-*>#]*(?i:({_VW}|INCOMPATIBLE-VERIFIED|{_SW}|SEAL))[\s:*]+"
                       rf"(?:(?:{_ROUND_ALT})|D\d|[A-Za-z0-9_.-]+\.(?:md|json)\b|[A-Za-z0-9_.-]+/)")


def _round_of(j: Jury, token: str, where: str) -> int:
    m = C.ROUND_TOKEN_RE.match(token)
    if not m:
        raise Error(f"{where}: malformed round token «{token}»")
    r = int(m.group(1))
    if not (j.folder / j.name(f"round_{r}")).is_dir():
        raise Error(f"{where}: round token «{token}» matches no round of this jury")
    return r


def read_seals(j: Jury) -> Seals:
    p = j.file("SEALS.md")
    if not p.is_file():
        raise Error(f"{p.name} is missing: the seals reported by rapporteur and jurors in their final answers")
    s = Seals(j.lexicon)
    text = p.read_text(encoding="utf-8")
    if s.l4:
        for line in text.splitlines():
            m = SEAL_L4.match(line)
            if m:
                s.files[m.group(1)] = m.group(2)
            m = VERIFIED_L4.match(line)
            if m:   # the clerk confirms the incompatibility declared by the rapporteur in that round
                s.verified.add((m.group(1), m.group(2)))
        return s
    inside = False
    for n, line in enumerate(text.splitlines(), 1):
        where = f"{p.name} l. {n}"
        if line.lstrip().startswith("```"):
            inside = not inside
            continue
        if inside:
            continue
        m = SEAL_L5.match(line)
        if m:
            tok, fname, h = m.groups()
            r = _round_of(j, tok, where) if tok else None
            canon = C.canonical_path(fname, "jury")
            s.files[(r, canon)] = h   # as in 4.0, a later seal of the same file replaces the earlier one
            continue
        m = VERIFIED_L5.match(line)
        if m:
            tok, d = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            s.verified.add((_round_of(j, tok, where), d))
            continue
        if SEAL_NEAR.match(line):
            raise Error(f"{where}: line not conforming: «{line.strip()[:80]}»")
    if inside:
        raise Error(f"{p.name}: ``` block not closed")
    return s


def g2(g):
    """In the skill the protocol G2 holds by default; "protocol": "G1.1" only for the juries voted before it."""
    return g.get("protocol", "G2") == "G2"


def check_g2(j: Jury, seals: Seals):
    """Protocol G2: the jury file sealed before round 0; no orphan SEAL; the delegation and the relevance sealed when
    needed."""
    g = j.g
    errors = []
    if seals.get(j, None, "jury.json") != j.sha:
        errors.append(f"{j.name('SEALS.md')}: «{_word(j, 'SEAL')} {j.name('jury.json')} <sha>» "
                      "equal to the file is missing (G2: the jury is fixed before round 0)")
    for desc, path in seals.paths(j):
        if not path.is_file():
            errors.append(f"{j.name('SEALS.md')}: orphan seal, {desc} does not exist")
    if g.get("authority") == "binding":
        if g.get("delegation") != "DELEGATION.md":
            errors.append(f"G2: a binding jury has \"{_jname(j, 'delegation')}\": \"{j.name('DELEGATION.md')}\", with "
                          f"the lines «{_word(j, 'DELEGATED')} Dk»")
        else:
            declared_seal(j, "DELEGATION.md", seals)
    if g.get("classification") == "plenary":
        if g.get("relevance") != "RELEVANCE.md":
            errors.append(f"G2: a plenary has \"{_jname(j, 'relevance')}\": \"{j.name('RELEVANCE.md')}\", with the "
                          f"lines «{_word(j, 'RELEVANT')} <role>»")
        else:
            declared_seal(j, "RELEVANCE.md", seals)
    if errors:
        raise Error("; ".join(errors))


def _word(j: Jury, canon: str) -> str:
    return W[canon] if j.lang == "it" else canon


def _protocol_lines(text: str, name: str, words: dict, near) -> list[tuple[str, tuple]]:
    """L5 lines of DELEGATION and RELEVANCE: words → (canonical, strict regex); a near-conforming line is an error."""
    out, inside = [], False
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            inside = not inside
            continue
        if inside:
            continue
        hit = None
        for canon, rx in words:
            m = rx.match(line)
            if m:
                hit = (canon, m.groups())
                break
        if hit:
            out.append(hit)
        elif near.match(line):
            raise Error(f"{name} l. {n}: line not conforming: «{line.strip()[:80]}»")
    return out


_DW, _RW, _PW = (re.escape(W[x]) for x in ("DELEGATED", "RELEVANT", "PROXY"))
DELEGATED_L5 = [("DELEGATED", re.compile(rf"^{_DW} (D[0-9A-Za-z_.-]+)\s*$")),
                ("DELEGATED", re.compile(r"^DELEGATED (D\d[0-9A-Za-z_.-]*)\s*$"))]
DELEGATED_NEAR = re.compile(rf"^[\s\-*>#]*(?:(?i:{_DW})[\s:*]+D[0-9A-Za-z_.-]|(?i:DELEGATED|DELEGATE)[\s:*]+D\d)")
RELEVANT_L5 = [("RELEVANT", re.compile(rf"^(?:{_RW}|RELEVANT) ([a-z][a-z0-9-]*)\s*$")),
               ("PROXY", re.compile(rf"^(?:{_PW}|PROXY) ([a-z][a-z0-9-]*) ([a-z][a-z0-9-]*)\s*$"))]
RELEVANT_NEAR = re.compile(rf"^[\s\-*>#]*(?i:{_RW}|RELEVANT|{_PW}|PROXY)[\s:*]+[a-z][a-z0-9-]*"
                           r"(?:[\s:*]+[a-z][a-z0-9-]*)?[\s.*]*$")


def delegated(j: Jury):
    g = j.g
    if not (g2(g) and g.get("authority") == "binding"):
        return None
    p = j.file("DELEGATION.md")
    text = p.read_text(encoding="utf-8")
    if j.lexicon.number == 4:
        return set(re.findall(C.L4["delegated"], text, re.M))
    return {gr[0] for _c, gr in _protocol_lines(text, p.name, DELEGATED_L5, DELEGATED_NEAR)}


def relevant(j: Jury):
    """The voters of a G2 plenary: the RELEVANT roles, with the proxies of the sub-professionals (PROXY <sub>
    <parent>: the sub-professional votes in place of the parent, never together)."""
    p = j.file("RELEVANCE.md")
    text = p.read_text(encoding="utf-8")
    if j.lexicon.number == 4:
        rel = set(re.findall(C.L4["relevant"], text, re.M))
        proxies = re.findall(C.L4["proxy"], text, re.M)
    else:
        lines = _protocol_lines(text, p.name, RELEVANT_L5, RELEVANT_NEAR)
        rel = {gr[0] for c, gr in lines if c == "RELEVANT"}
        proxies = [gr for c, gr in lines if c == "PROXY"]
    for sub, parent in proxies:
        if parent in rel:
            rel.discard(parent)
            rel.add(sub)
    return rel - {j.g.get("rapporteur"), j.g.get("clerk")}


def declared_seal(j: Jury, canonical: str, seals: Seals, r=None, lex: Lexicon | None = None):
    rel = (f"round_{r}/" if r is not None else "") + canonical
    p = j.folder / j.name(rel)
    text, s = sealed(p, lex or j.lexicon)
    if seals.get(j, r, canonical) != s:
        raise Error(f"{j.name(rel)}: the seal does not match the one reported in {j.name('SEALS.md')}")
    return text, s


def read_proposal(j: Jury, r: int, seals: Seals, lex: Lexicon):
    name = j.name(f"round_{r}/PROPOSAL.md")
    text, s = declared_seal(j, "PROPOSAL.md", seals, r, lex)
    lines = valid_lines(text, name, set(PROPOSAL_WORDS), lex)
    p = {"sha": s, "OPTION": {}, "OPTIONS": {}, "OPERATIVE": {}, "DEPENDS": {}, "INCOMPATIBLE": {}, "TEST": {},
         "TEST-OUTCOME": {}}
    for word, gr in lines:
        if word == "DEPENDS":
            p["DEPENDS"].setdefault(gr[0], set()).add(gr[1])
            continue
        if gr[0] in p[word]:
            raise Error(f"{name}: two {_word(j, word)} lines for {gr[0]}")
        p[word][gr[0]] = gr[1]
    if not p["OPTION"]:
        raise Error(f"{name}: no {_word(j, 'OPTION')} line")
    for d in p["OPTION"]:
        if d not in p["OPERATIVE"]:
            raise Error(f"{name}: {_word(j, 'OPERATIVE')} {d} is missing")
    for d in p["INCOMPATIBLE"]:
        if d not in p["OPTION"]:
            raise Error(f"{name}: {_word(j, 'INCOMPATIBLE')} on {d}, which is not under examination")
    if r == 0:
        for d, o in p["OPTION"].items():
            choices = [x.strip() for x in p["OPTIONS"].get(d, "").split("|") if x.strip()]
            if o not in choices:
                raise Error(f"{name}: {_word(j, 'OPTION')} {d} «{o}» is not in the {_word(j, 'OPTIONS')} {d} line")
    return p


def read_vote(j: Jury, r: int, role: str, decisions, seals: Seals, lex: Lexicon, optional=frozenset()):
    rel = f"round_{r}/VOTE_{role}.md"
    name = j.name(rel)
    text, s = declared_seal(j, f"VOTE_{role}.md", seals, r, lex)
    v = {"sha": s, "VOTE": {}, "REVISION": {}, "CONDITION": {}, "CLASS": {}, "CHANGE": {}, "PREFER": {}}
    for word, gr in valid_lines(text, name, set(VOTE_WORDS), lex):
        if gr[0] in optional:
            continue
        if gr[0] not in decisions:
            raise Error(f"{name}: {_word(j, word)} on {gr[0]}, which is not under examination")
        if gr[0] in v[word]:
            raise Error(f"{name}: two {_word(j, word)} lines for {gr[0]}")
        v[word][gr[0]] = gr[1]
    errors = []
    for d in decisions:
        if d not in v["VOTE"]:
            errors.append(f"the vote on {d} is missing")
            continue
        if v["VOTE"][d] == "no" and d not in v["REVISION"]:
            errors.append(f"no on {d} without {_word(j, 'REVISION')}")
        if v["VOTE"][d] == "yes" and d not in v["CONDITION"]:
            errors.append(f"yes on {d} without {_word(j, 'CONDITION')}")
        if d not in v["CLASS"]:
            errors.append(f"{_word(j, 'CLASS')} {d} is missing")
    if errors:
        raise Error(f"{name}: " + "; ".join(errors))
    return v


def count_outcome(s, n):
    if s == n:
        return "APPROVED"
    if 2 * s > n:
        return "REVISION"
    return "REJECTED"


def compute_round(j: Jury, roles, r, prev, seals: Seals):
    g = j.g
    lex = j.round_lexicon(r)
    rdir = j.folder / j.name(f"round_{r}")
    if not rdir.is_dir():
        raise Error(f"the folder {j.name(f'round_{r}')} is missing")
    expected = {j.name("PROPOSAL.md")} | {j.name(f"VOTE_{x}.md") for x in roles}
    extraneous = sorted(p.name for p in rdir.iterdir() if p.name not in expected)
    if extraneous:
        raise Error(f"{j.name(f'round_{r}')}: extraneous entries " + ", ".join(extraneous))
    p = read_proposal(j, r, seals, lex)
    pname = j.name(f"round_{r}/PROPOSAL.md")
    if g.get("form") == "light":
        for d in p["OPTION"]:
            if d not in p["TEST"] or d not in p["TEST-OUTCOME"]:
                raise Error(f"{pname}: in the light jury {d} wants {_word(j, 'TEST')} and {_word(j, 'TEST-OUTCOME')} "
                            "(test before the vote)")
    if prev is None:
        if p["INCOMPATIBLE"]:
            raise Error(f"{pname}: {_word(j, 'INCOMPATIBLE')} holds only in the revision rounds")
    else:
        in_revision = {d for d, e in prev["decisions"].items() if e["state"] == "REVISION"}
        if set(p["OPTION"]) != in_revision:
            raise Error(f"{pname}: the decisions must be those in REVISION "
                        f"({', '.join(sorted(in_revision)) or 'none'})")
        for d in p["OPTION"]:
            e = prev["decisions"][d]
            if p["OPTION"][d] != e["option"]:
                raise Error(f"{j.name(f'round_{r}')}: the option of {d} changed: it is a new proposal, from round 0")
            if p["OPERATIVE"][d] != e["operative_text"]:
                raise Error(f"{j.name(f'round_{r}')}: the {_word(j, 'OPERATIVE')} of {d} changed: it is not a small "
                            "revision")
            if p["DEPENDS"].get(d, set()) != set(e.get("depends_on", [])):
                raise Error(f"{j.name(f'round_{r}')}: the dependencies of {d} changed")
    verified = seals.verified_in(r)
    for d in verified:
        if d not in p["INCOMPATIBLE"]:
            raise Error(f"{j.name('SEALS.md')}: {_word(j, 'INCOMPATIBLE-VERIFIED')} {j.name(f'round_{r}')} {d}, but the "
                        "proposal does not declare it")
    closed = {d for d in p["INCOMPATIBLE"] if d in verified}
    to_vote = [d for d in p["OPTION"] if d not in closed]
    # On a decision declared INCOMPATIBLE but closed by the clerk, the votes are allowed and do not count.
    votes = {x: read_vote(j, r, x, to_vote, seals, lex, optional=closed) for x in roles}
    n = len(roles)
    decisions = {}
    for d in p["OPTION"]:
        base = {"option": p["OPTION"][d], "operative_text": p["OPERATIVE"][d], "proposal_sha": p["sha"],
                "depends_on": sorted(p["DEPENDS"].get(d, set()))}
        if d in closed:
            decisions[d] = dict(prev["decisions"][d], state="NOT_CONVERGED",
                                incompatible={"round": r, "reason": p["INCOMPATIBLE"][d], "verified": True})
            continue
        yes = sorted(x for x in roles if votes[x]["VOTE"][d] == "yes")
        no = sorted(x for x in roles if votes[x]["VOTE"][d] == "no")
        state = count_outcome(len(yes), n)
        entry = dict(base, yes=yes, no=no, state=state, text_round=r,
                     requested_revisions={x: votes[x]["REVISION"][d] for x in no},
                     yes_conditions={x: votes[x]["CONDITION"][d] for x in yes},
                     plenary_class=sorted(x for x in roles if votes[x]["CLASS"][d] == "plenary"),
                     preferences={x: votes[x]["PREFER"][d] for x in roles if d in votes[x]["PREFER"]})
        if prev is not None:
            e = prev["decisions"][d]
            lost = sorted(set(e["yes"]) - set(yes))
            # CHANGE is asked with respect to the last vote of the juror, also in a round discarded as regressive.
            last_no = e["regression"]["round_votes"]["no"] if e.get("regression", {}).get("round") == r - 1 else e["no"]
            without_change = sorted(x for x in yes if x in last_no and d not in votes[x]["CHANGE"])
            if without_change:
                raise Error(f"{j.name(f'round_{r}')}: {d}, from no to yes without a {_word(j, 'CHANGE')} line: "
                            + ", ".join(without_change))
            if state != "REJECTED" and lost:
                # regressive revision: discarded, the text and the votes of the previous round stay
                entry = dict(e, state="REVISION",
                             regression={"round": r, "yes_lost": lost, "round_votes": {"yes": yes, "no": no}})
        if g.get("form") == "light":
            entry["test"] = {"text": p["TEST"][d], "outcome": p["TEST-OUTCOME"][d]}
            classes = {votes[x]["CLASS"][d] for x in roles}
            if "plenary" in classes:
                entry["state"] = "TO_PLENARY"
            elif "ordinary" in classes:
                entry["state"] = "TO_JURY"
                entry["reason"] = C.reason("juror_ordinary")
            elif entry["state"] in ("APPROVED", "REVISION") and p["TEST-OUTCOME"][d] == "fail":
                entry["state"] = "REJECTED"
                entry["reason"] = C.reason("quick_test_fails")
        if g2(g) and prev is None:
            out = sorted(x for x, o in entry.get("preferences", {}).items()
                         if o not in [y.strip() for y in p["OPTIONS"].get(d, "").split("|")])
            if out:
                raise Error(f"{d}: {_word(j, 'PREFER')} outside the {_word(j, 'OPTIONS')} list ({', '.join(out)})")
        if entry["state"] == "APPROVED":
            pref = {}
            for o in entry["preferences"].values():
                if o != entry["option"]:
                    pref[o] = pref.get(o, 0) + 1
            best = max(pref.items(), key=lambda kv: kv[1], default=(None, 0))
            if entry["plenary_class"] and g.get("form") != "light" and not (
                    g2(g) and g.get("classification") == "plenary"):
                entry["state"] = "TO_PLENARY"
            elif 2 * best[1] > n:
                entry["state"] = "TO_REPROPOSE"
                entry["repropose_with"] = best[0]
            elif g["authority"] == "recommendation":
                entry["state"] = "RECOMMENDED"
            elif delegated(j) is not None and d not in delegated(j):
                entry["state"] = "RECOMMENDED"
                entry["reason"] = C.reason("not_delegated")
        if entry["state"] == "REVISION" and r == limit(g):
            entry["state"] = "TO_JURY" if g.get("form") == "light" else "NOT_CONVERGED"
        decisions[d] = entry
    if prev is not None:
        for d, e in prev["decisions"].items():
            decisions.setdefault(d, e)
    # dependencies: an approved decision that depends on a non-approved one does not become an act
    for _ in range(len(decisions)):
        for d, e in decisions.items():
            for dj in e.get("depends_on", []):
                if dj not in decisions:
                    raise Error(f"{d} depends on {dj}, which is not among the decisions of the jury")
                sj = decisions[dj]["state"]
                if sj == "REVISION" and e["state"] in ("APPROVED", "RECOMMENDED"):
                    e["state"] = "REVISION"
                    e["waiting_for"] = dj
                elif sj in FINAL - {"APPROVED", "RECOMMENDED"} and e["state"] not in ("REJECTED",):
                    if e["state"] != "SUSPENDED":
                        e["state"] = "SUSPENDED"
                        e["suspended_by"] = {"blocked_by": dj, "state": sj}
    return {"round": r, "jurors": roles, "n": n, "round_limit": limit(g),
            **({"form": "light"} if g.get("form") == "light" else {}), "protocol": g.get("protocol", "G2"),
            "vote_shas": {x: votes[x]["sha"] for x in roles}, "decisions": decisions}


def outcome_files(folder: Path) -> list[tuple[int, Path]]:
    """The outcomes of a jury folder in its dialect, ordered by round number; outcomes of two dialects → error."""
    en = [(int(m.group(1)), p) for p in folder.glob("OUTCOME_round_*.json")
          if (m := re.fullmatch(r"OUTCOME_round_(\d+)\.json", p.name))]
    it = [(int(m.group(1)), p) for p in folder.glob(C.JURY_PATTERNS[2][3].format("*"))
          if (m := re.fullmatch(C.JURY_PATTERNS[2][2], p.name))]
    if en and it:
        raise Error(f"{folder}: outcomes of two dialects")
    return sorted(en or it)


def previous(j: Jury, e, k):
    """G2: the previous juries on the same question (jury file "previous", folders relative to the parent folder).
    An option already REJECTED is not proposed again; a second TO_REPROPOSE on the same decision becomes TO_USER."""
    if k != 0:
        return
    for rel in j.g.get("previous", []):
        if Path(rel).is_absolute() or ".." in Path(rel).parts or "/" in rel:
            raise Error(f"previous: «{rel}» not allowed")
        c = (j.folder.parent / rel).resolve()
        outs = outcome_files(c)
        if not outs:
            raise Error(f"previous: {rel} has no outcome")
        old = C.to_canonical(json.loads(outs[-1][1].read_text(encoding="utf-8")), C.OUTCOME_SCHEMA,
                             str(outs[-1][1]))["decisions"]
        for d, v in e["decisions"].items():
            w = old.get(d)
            if not w:
                continue
            if w["state"] == "REJECTED" and w["option"] == v["option"]:
                raise Error(f"{d}: the option «{v['option']}» is already REJECTED in {rel}: it is not proposed again")
            if w["state"] == "TO_REPROPOSE" and v["state"] == "TO_REPROPOSE":
                v["state"] = "TO_USER"
                v["reason"] = C.reason("second_repropose", rel=rel)


def _has_protocol_key(text: str, lex: Lexicon, keys=("protocol", "protocollo")) -> bool:
    """L4: the substring check of the 4.0; L5: a top-level key protocol/protocollo (or `keys`) of the json."""
    if lex.number == 4:
        return '"protocollo"' in text
    try:
        e = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(e, dict) and any(k in e for k in keys)


def serialize(e: dict, lang: str) -> str:
    return json.dumps(C.to_dialect(e, C.OUTCOME_SCHEMA, lang), ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def count(folder, r):
    j = Jury(folder)
    if not isinstance(r, int) or r < 0:
        raise Error("the round is an integer ≥ 0")
    g = j.g
    if r > limit(g):
        raise Error(f"round {r} beyond the limit ({limit(g)})")
    if not g2(g) and C.env("SWARMER_G11_TESTS") != "1":
        # G1.1 only for a 4.0 jury (giuria.json in L4) whose round 0 was counted without the keys of 5.0
        e0 = j.folder / j.name("OUTCOME_round_0.json")
        t0 = e0.read_text(encoding="utf-8") if e0.is_file() else ""
        if (j.lexicon.number != 4 or not t0 or _has_protocol_key(t0, j.lexicon)
                or _has_protocol_key(t0, L5, ("lexicon", "lessico"))):
            raise Error("protocol G1.1: allowed only to recount the juries voted before G2 (an outcome of round 0 "
                        "without the key «protocol»); a new jury follows G2")
    roles = check_composition(j)
    seals = read_seals(j)
    if g2(g):
        check_g2(j, seals)
    prev = None
    text = ""
    for k in range(r + 1):
        lex = j.round_lexicon(k)
        e = compute_round(j, roles, k, prev, seals)
        e["jury_sha"] = j.sha
        p = j.folder / j.name(f"OUTCOME_round_{k}.json")
        if g2(g):
            previous(j, e, k)
        out = dict(e)
        if lex.number == 5:
            out["lexicon"] = LEXICON
        text = serialize(out, j.lang)
        if p.exists():
            old = p.read_text(encoding="utf-8")
            if not _has_protocol_key(old, lex):
                text = serialize({a: b for a, b in out.items() if a != "protocol"}, j.lang)
            if old != text:
                raise Error(f"{p.name} exists and does not coincide with the recount: re-vote, changed vote, "
                            "changed jury file or retouched outcome")
        elif k < r:
            raise Error(f"{p.name} is missing: the rounds are counted in order")
        if k < r and not any(v["state"] == "REVISION" for v in e["decisions"].values()):
            raise Error(f"after round {k} no decision is in REVISION: round {r} does not exist")
        prev = e
    target = j.folder / j.name(f"OUTCOME_round_{r}.json")
    if target.is_symlink():
        raise Error(f"{target.name} is a symbolic link: not following it")
    target.write_text(text, encoding="utf-8")
    return prev


# ---- §4, the experts that do not exist yet ----

TABLE_ROW = re.compile(r"^\|\s*\d{4}")
REQUEST_ROW = re.compile(
    r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*`([a-z0-9-]+)`\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*$")
CLOSED_ROW = re.compile(r"^- `([a-z0-9-]+)`: (" + "|".join(C.REGISTER_WORDS["created"]) + r"|(?:"
                        + "|".join(C.REGISTER_WORDS["merged"]) + r") `([a-z0-9-]+)`)")


def normalize_requester(who: str, known: set) -> str:
    c = C.normalize_requester(who)
    if c == "coordinator" or c in known:
        return c
    if c.startswith("provisional:") and ROLE_RE.match(c[len("provisional:"):]):
        return c
    raise Error(f"requester «{who}» is not a role of the swarm, «coordinator» or «provisional:<id>»")


def _plenary_name(conv: str) -> bool:
    return any(w in C.PLENARY_WORDS for w in re.split(r"[-_/]", conv.lower()))


def requests(register, root_dir=None):
    root_dir = Path(root_dir) if root_dir else root()
    known = known_roles()
    lines = Path(register).read_text(encoding="utf-8").splitlines()
    created, merged = set(), {}
    for line in lines:
        m = CLOSED_ROW.match(line)
        if m:
            if m.group(2) in C.REGISTER_WORDS["created"]:
                created.add(m.group(1))
            else:
                merged[m.group(1)] = m.group(3)
    by_id = {}
    for n, line in enumerate(lines, 1):
        if not TABLE_ROW.match(line):
            continue
        m = REQUEST_ROW.match(line)
        if not m:
            raise Error(f"register l. {n}: line not conforming «{line[:80]}»")
        _, conv, who, rid, _, why = m.groups()
        if len(why) < 10:
            raise Error(f"register l. {n}: reason missing or too short")
        if not (root_dir / conv).is_dir():
            raise Error(f"register l. {n}: the convening «{conv}» is not an existing archive folder")
        who = normalize_requester(who, known)
        while rid in merged:
            rid = merged[rid]
        if rid in created:
            continue
        if who == f"provisional:{rid}":
            continue   # the provisional expert does not request its own creation
        by_id.setdefault(rid, set()).add((conv, who))
    threshold = {}
    for rid, pairs in by_id.items():
        coord = sorted(c for c in pairs if c[1] == "coordinator")[:1]
        agents = {c for c in pairs if c[1] != "coordinator"}
        counted = agents | set(coord)
        conv = {}
        for c, who in agents:
            conv.setdefault(c, set()).add(who)
        all_conv = {c for c, _ in counted}
        a = sorted(c for c, who in conv.items() if len(who) >= (5 if _plenary_name(c) else 3))
        requesters = {who for _, who in agents}
        b = len(counted) >= 3 and len(all_conv) >= 2 and len(requesters) >= 2
        threshold[rid] = {"requests": len(counted), "convenings": len(all_conv), "requesters": len(requesters),
                          "simultaneous": a, "accumulated": b, "to_create": bool(a) or b}
    return threshold


def default_register() -> Path:
    import paths as S
    return S.find_project_file(BASE, "EXPERT_REQUESTS.md", language(), BASE)


def main(argv=None):
    import aliases as A
    a = list(sys.argv[1:] if argv is None else argv)
    al = A.load(BASE)
    p = A.parser(prog="jury", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add = A.subparsers(p, al)
    q = add("count")
    q.add_argument("folder")
    q.add_argument("round")
    q = add("requests")
    q.add_argument("register", nargs="?")
    if not a:
        print(__doc__)
        sys.exit(2)
    try:
        ns = p.parse_args(a)
    except SystemExit as x:
        sys.exit(2 if x.code else 0)
    prefix = msg("jury_error_prefix", "ERROR: ")
    lang = language()
    try:
        if ns.command == "count":
            try:
                rnd = int(ns.round)
            except ValueError:
                raise Error("the round is an integer ≥ 0")
            e = count(ns.folder, rnd)
            for d, v in sorted(e["decisions"].items()):
                extra = ""
                if v.get("regression", {}).get("round") == e["round"]:
                    vg = v["regression"]["round_votes"]
                    extra = msg("jury_regressive", " (regressive revision discarded: yes of the round {yes}/{n})",
                                yes=len(vg["yes"]), n=e["n"])
                state = C.STATES.get(v["state"], v["state"]) if lang == "it" else v["state"]
                print(msg("jury_line", "{decision}: {state}{extra} — yes {yes}/{n} — {option}", decision=d,
                          state=state, extra=extra, yes=len(v.get("yes", [])), n=e["n"], option=v["option"]))
        elif ns.command == "requests":
            reg = ns.register or str(default_register())
            s = requests(reg)
            for rid, v in sorted(s.items()):
                verdict = msg("requests_to_create", "TO CREATE") if v["to_create"] else msg("requests_below",
                                                                                            "below the threshold")
                print(msg("requests_line", "{id}: {requests} requests, {convenings} convenings, {requesters} "
                          "requesters — {verdict}", id=rid, role=rid, requests=v["requests"],
                          convenings=v["convenings"], requesters=v["requesters"], verdict=verdict))
            if not s:
                print(msg("requests_none", "no open request"))
            ids = sorted(s)
            near = [(x, y) for i, x in enumerate(ids) for y in ids[i + 1:] if x[:5] == y[:5]]
            for x, y in near:
                print(msg("requests_close", "close ids, to merge or to tell apart with a reason: {a}, {b}", a=x, b=y,
                          ids=f"{x}, {y}"))
    except C.Error as x:
        print(f"{prefix}{x}")
        sys.exit(2)
    except (OSError, ValueError, KeyError, TypeError) as x:
        print(f"{prefix}{type(x).__name__}: {x}")
        sys.exit(2)


if __name__ == "__main__":
    main()
