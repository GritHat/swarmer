#!/usr/bin/env python3
"""swarmer 5.0: the dialects of the data and the migration from the 4.0 «sciame».

The only module of the engine that holds Italian words. Everything the code has to recognise from an Italian 4.0
installation lives here, so that the other modules work only on canonical (English) forms:
- the dialect tables of the data written in a project (convenings, juries, outcomes, configuration, database), as
  schemas by path, with `to_canonical` and `to_dialect`;
- the names of the files and folders in the two dialects (`CONVENE_FILES`, `JURY_FILES`, `FILE_NAMES`, `STATE_NAMES`);
- the protocol words of a jury round (`LINE_WORDS`), the controlled values (`VALUES`, `STATES`) and the fixed
  reasons of the engine (`REASONS`);
- the 4.0 markers (`OLD_MARKS`), the reserved Italian ids (`RESERVED_IT`), the old environment variables
  (`ENV_ALIASES`) and the forms of the requesters of the expert register (`normalize_requester`).
Standard library only.
"""
from __future__ import annotations

import os
import re
from pathlib import Path


class Error(Exception):
    """The base error of the engine: every module raises it, or a subclass of it."""


LANGUAGES = ("en", "it")   # en is canonical

# --- environment variables (F): the new name, then the old one ---

ENV_ALIASES = {
    "SWARMER_LANGUAGE": "SCIAME_LINGUA",
    "SWARMER_FORBIDDEN": "SCIAME_VIETATE",
    "SWARMER_ROOT": "SCIAME_RADICE",
    "SWARMER_AGENTS_DIR": "SCIAME_AGENTI",
    "SWARMER_G11_TESTS": "SCIAME_G11_PROVE",
    "SWARMER_TMP": "SCIAME_TMP",
}


def env(name: str, default: str | None = None) -> str | None:
    """The value of a 5.0 variable, or of its 4.0 alias; an empty value counts as unset."""
    v = os.environ.get(name)
    if v:
        return v
    old = ENV_ALIASES.get(name)
    v = os.environ.get(old) if old else None
    return v if v else default


def env_list(name: str) -> list[str]:
    """A path list variable: the new and the old lists are joined (SWARMER_FORBIDDEN + SCIAME_VIETATE)."""
    out = []
    for n in (name, ENV_ALIASES.get(name)):
        if n:
            out += [x for x in os.environ.get(n, "").split(os.pathsep) if x]
    return list(dict.fromkeys(out))


# --- markers of the 4.0 ---

OLD_MARKS = {
    "generated": "sciame-4 GENERATO",
    "file_mark": "#==== sciame.sh:",
    "end_of_files_line": "fine dei file",
    "end_of_files": "SCIAME_FINE_DEI_FILE",
    "claude_begin": "<!-- sciame:inizio (scritto da sciame/sciame.sh istruzioni: non modificare a mano) -->",
    "claude_begin_prefix": "<!-- sciame:inizio",
    "claude_end": "<!-- sciame:fine -->",
    "tmp_prefix": ".sciame-",
    "script": "sciame.sh",
}
# The note of the generated files, by language; `is_generated` recognises every form.
GENERATED_NOTES = {"en": "swarmer-5 GENERATED", "it": "sciame-5 GENERATO"}
GENERATED_RE = re.compile(r"^<!-- (sciame|swarmer)-[45] (GENERATO|GENERATED):")
# The same note in the files that cannot hold an HTML comment (the TOML agents of Codex): a comment on the first
# line.
TOML_GENERATED_RE = re.compile(r"^# (sciame|swarmer)-5 (GENERATO|GENERATED):")
# The sign of an agent generated from another language's text, waiting for its translation (K.2): the same in
# every language, followed by the code of the language of the installation.
TRANSLATION_PENDING = "translation-pending"
# The paragraph of CLAUDE.md, by language: (begin, end, begin prefix).
CLAUDE_MARKS = {
    "en": ("<!-- swarmer:begin (written by swarmer.sh instructions: do not edit by hand) -->", "<!-- swarmer:end -->",
           "<!-- swarmer:begin"),
    "it": (OLD_MARKS["claude_begin"], OLD_MARKS["claude_end"], OLD_MARKS["claude_begin_prefix"]),
}
# The notes with which a 3.x installation marked its files (only to recognise them).
NOTES_31 = {
    "agent": "Generato da sciame/genera_agenti.py dalla scheda",
    "skill": "Generato da sciame/genera_agenti.py dai documenti di sciame/",
    "docs": ("AGENTI.md", "PREAMBOLO.md", "PIPELINE.md", "ISTRUZIONI_COORDINATORE.md", "SCHEDA_IPOTESI.md", "README.md"),
    "skills": ("sciame", "sciame-singolo", "sciame-classica", "sciame-completa"),
    "catalog": "catalogo.json",
    "version": "VERSIONE",
    "roles": "ruoli",
    "id": "sigla",
}

# --- the internal state of an installation (A.2): new name → 4.0 name ---

STATE_NAMES = {"ROOT": "RADICE", "LANGUAGE": "LINGUA", "FACTORY.json": "FABBRICA.json", "VERSION": "VERSIONE",
               "catalog.json": "catalogo.json"}


def language(swarm) -> str:
    """The language of an installation (B.0, as head.sh): LANGUAGE, then its 4.0 name, then SWARMER_LANGUAGE (or
    SCIAME_LINGUA), then en. The variable never wins over the file: it would rename agents and documents."""
    for n in ("LANGUAGE", STATE_NAMES["LANGUAGE"]):
        p = Path(swarm) / n
        if p.is_file() and not p.is_symlink():
            v = p.read_text(encoding="utf-8").strip()
            if v:
                return v
    return env("SWARMER_LANGUAGE") or "en"


# The 4.0 tree of a source or an installation: canonical folder → 4.0 folder, and the old engine.
OLD_TREE = {"engine": "motore", "tests": "prove", "docs": "documenti", "wrappers": "involucri"}
OLD_ENGINE = "motore/sciame.py"
OLD_DB = {"professionals.json": "professionisti.json", "cores.json": "nuclei.json"}
# The 4.0 names of the documents in docs/<l>/ (the 4.0 kept the Italian names in every language).
OLD_DOCS = {"PREAMBLE.md": "PREAMBOLO.md", "COORDINATOR_INSTRUCTIONS.md": "ISTRUZIONI_COORDINATORE.md",
            "JURY.md": "GIURIA.md", "ENVIRONMENT.md": "AMBIENTE.md", "HYPOTHESIS_CARD.md": "SCHEDA_IPOTESI.md",
            "_HELP.txt": "_AIUTO.txt", "_LOCAL.md": "_LOCALE.md", "_PR_PROPOSAL.md": "_PROPOSTA_PR.md",
            "_EXPERT_REQUESTS.md": "_RICHIESTE_ESPERTI.md"}

# --- localized names of files and folders (A.3, A.4); the i18n section "files" wins, this is the fallback ---

FILE_NAMES = {
    "it": {
        # documents and factory files generated in the installation
        "PREAMBLE.md": "PREAMBOLO.md", "PIPELINE.md": "PIPELINE.md",
        "COORDINATOR_INSTRUCTIONS.md": "ISTRUZIONI_COORDINATORE.md", "JURY.md": "GIURIA.md",
        "ENVIRONMENT.md": "AMBIENTE.md", "HYPOTHESIS_CARD.md": "SCHEDA_IPOTESI.md", "README.md": "README.md",
        "AGENTS.md": "AGENTI.md",
        # wrappers at the root of the installation
        "convene.py": "convoca.py", "jury.py": "giuria.py", "generate_agents.py": "genera_agenti.py",
        "swarmer.sh": "sciame.sh",
        # files of the project (A.4)
        "swarmer": "sciame", ".swarmer": ".sciame", "proposals": "proposte", "local": "locale",
        "LOCAL_README.md": "LEGGIMI.md", "FORBIDDEN.txt": "VIETATE.txt", "EXPERT_REQUESTS.md": "RICHIESTE_ESPERTI.md",
        # suffix of a factory file that the project changed
        ".new": ".nuovo",
        # work folders that are never published
        "_work": "_lavoro",
        # the local overlay of the translations (K.3)
        "translations": "traduzioni",
    },
}
# The head of a new FORBIDDEN.txt, by language.
FORBIDDEN_HEAD = {"en": "# One word or phrase per line that must never leave the project.\n",
                  "it": "# Una parola o un'espressione per riga che non deve mai uscire dal progetto.\n"
                        "# One word or phrase per line that must never leave the project.\n"}
# The marker of an interrupted migration: its content says whether the installation came from a 4.0.
MIGRATING = "MIGRATING"
# The Italian aliases of the factory (A.3): alias → the English file they run.
ALIAS_STUBS = {"sciame.sh": "swarmer.sh", "convoca.py": "convene.py", "giuria.py": "jury.py",
               "genera_agenti.py": "generate_agents.py"}

# --- the reserved ids (C.1) ---

RESERVED_IT = {"singolo", "ventaglio", "classica", "giuria", "giuria-leggera", "completa", "plenaria", "esperto",
               "locale", "leggera"}

# --- controlled values: canonical → Italian (en is the identity) ---

VALUES = {
    "strategy": {"single": "singolo", "fan-out": "ventaglio", "classic": "classica", "jury": "giuria",
                 "light-jury": "giuria-leggera", "full": "completa", "plenary": "plenaria", "expert": "esperto",
                 "auto": "auto"},
    "form": {"slices": "fette", "race": "gara", "mixed": "mista"},
    "rule": {"first": "primo", "ranking": "classifica", "best": "migliore"},
    "profile": {"code": "codice", "defect": "difetto", "architecture": "architettura", "test": "prova", "data": "dati",
                "ai": "ia", "research": "ricerca", "writing": "scrittura", "study": "studio", "decision": "decisione",
                "plan": "piano", "security": "sicurezza", "device": "dispositivo", "interface": "interfaccia",
                "perception": "percezione", "motion": "movimento", "estimation": "stima", "tracking": "tracciamento",
                "localization": "localizzazione", "sensors": "sensori", "latency": "latenza", "general": "generale"},
    "lane": {"A": "A", "B": "B", "all": "tutti", "slices": "fette", "race": "gara", "mixed": "mista",
             "single": "singolo"},
    "closure_status": {"declared unresolved": "non risolto dichiarato", "not funded": "non finanziato"},
    "authority": {"binding": "vincolante", "recommendation": "raccomandazione"},
    "jury_form": {"ordinary": "ordinaria", "light": "leggera", "plenary": "plenaria"},
    "test_outcome": {"pass": "passa", "fail": "fallisce"},
    "entry_type": {"professional": "professionista", "subprofessional": "sottoprofessionista"},
    "entry_status": {"active": "attivo", "retired": "ritirato"},
    "jury_delegation": {"DELEGATION.md": "DELEGA.md"},
    "jury_relevance": {"RELEVANCE.md": "PERTINENZA.md"},
}
STATES = {"APPROVED": "APPROVATA", "RECOMMENDED": "RACCOMANDATA", "REVISION": "REVISIONE", "REJECTED": "RESPINTA",
          "NOT_CONVERGED": "NON_CONVERGENTE", "SUSPENDED": "SOSPESA", "TO_PLENARY": "DA_PLENARIA",
          "TO_REPROPOSE": "DA_RIPROPORRE", "TO_USER": "DA_UTENTE", "TO_JURY": "DA_GIURIA"}
VALUES["state"] = STATES

# The fixed reasons of the jury engine (decisions.*.reason): code → template by dialect. The Italian is exactly the 4.0.
REASONS = {
    "quick_test_fails": {"en": "the quick test fails", "it": "la prova veloce fallisce"},
    "juror_ordinary": {"en": "a juror classifies it ordinary: it goes to the ordinary jury",
                       "it": "un giurato la classifica ordinaria: va alla giuria ordinaria"},
    "not_delegated": {"en": "the decision is not among those delegated in DELEGATION.md",
                      "it": "la decisione non è fra quelle delegate in DELEGA.md"},
    "second_repropose": {"en": "second TO_REPROPOSE after {rel}: the user decides",
                         "it": "secondo DA_RIPROPORRE dopo {rel}: decide l'utente"},
}


def reason(code: str, **kw) -> str:
    """The canonical (English) text of a reason of the engine."""
    return REASONS[code]["en"].format(**kw)


# --- the protocol words of a jury (C.6): canonical → Italian ---

LINE_WORDS = {
    "OPTION": "OPZIONE", "OPTIONS": "OPZIONI", "OPERATIVE": "DISPOSITIVO", "DEPENDS": "DIPENDE",
    "INCOMPATIBLE": "INCOMPATIBILE", "TEST": "PROVA", "TEST-OUTCOME": "ESITO-PROVA", "VOTE": "VOTO",
    "REVISION": "REVISIONE", "CONDITION": "CONDIZIONE", "CLASS": "CLASSE", "CHANGE": "CAMBIO", "PREFER": "PREFERISCO",
    "SEAL": "SIGILLO", "INCOMPATIBLE-VERIFIED": "INCOMPATIBILE-VERIFICATO", "DELEGATED": "DELEGATA",
    "RELEVANT": "PERTINENTE", "PROXY": "DELEGA",
}
# Values of the protocol lines: every accepted spelling → canonical.
LINE_VALUES = {
    "vote": {"yes": "yes", "no": "no", "si": "yes", "sì": "yes"},
    "test_outcome": {"pass": "pass", "fail": "fail", "passa": "pass", "fallisce": "fail"},
    "class": {"light": "light", "ordinary": "ordinary", "plenary": "plenary", "leggera": "light",
              "ordinaria": "ordinary", "plenaria": "plenary"},
    # the Correctness line of a VERDICT.md (a convening): every spelling, lower case → canonical
    "correctness": {"proven": "proven", "verified": "verified", "supported": "supported", "refuted": "refuted",
                    "unresolved": "unresolved",
                    "dimostrato": "proven", "dimostrata": "proven", "provato": "proven", "provata": "proven",
                    "verificato": "verified", "verificata": "verified",
                    "sostenuto": "supported", "sostenuta": "supported", "supportato": "supported",
                    "supportata": "supported",
                    "smentito": "refuted", "smentita": "refuted", "confutato": "refuted", "confutata": "refuted",
                    "non risolto": "unresolved", "non risolta": "unresolved"},
    # the outcome of a CLOSURE.md
    "outcome": {"closed": "closed", "not closed": "not closed", "chiuso": "closed", "non chiuso": "not closed"},
}
# The sealed last line of a file of a jury, by language (the regular expressions accept every language).
SEAL_LINE = {"en": "sha256 of the bytes before this line: {sha}", "it": "sha256 dei byte che precedono questa riga: {sha}"}
SEAL_LINE_RE = re.compile(r"^(?:sha256 dei byte che precedono questa riga|sha256 of the bytes before this line): "
                          r"([0-9a-f]{64})\s*$")
SEAL_LINE_RE_L4 = re.compile(r"^sha256 dei byte che precedono questa riga: ([0-9a-f]{64})\s*$")
# The round token: giro_<r> (4.0, it) and round_<r> (en); both are accepted in every dialect of L5.
ROUND_PREFIX = {"en": "round_", "it": "giro_"}
ROUND_TOKEN_RE = re.compile(r"^(?:giro|round)_(\d+)$")
# The lexicon L4: exactly the expressions of the 4.0 (Italian words only).
L4 = {
    "values": {"TEST-OUTCOME": "(passa|fallisce)", "VOTE": "(si|sì|no)", "CLASS": "(leggera|ordinaria|plenaria)"},
    "seal": re.compile(r"^SIGILLO ((?:giro_\d+/)?[A-Za-z0-9_.-]+\.(?:md|json)) ([0-9a-f]{64})\s*$"),
    "verified": re.compile(r"^INCOMPATIBILE-VERIFICATO (giro_\d+) (D[0-9A-Za-z_.-]+)\s*$"),
    "delegated": r"^DELEGATA (D[0-9A-Za-z_.-]+)\s*$",
    "relevant": r"^PERTINENTE ([a-z][a-z0-9-]*)\s*$",
    "proxy": r"^DELEGA ([a-z][a-z0-9-]*) ([a-z][a-z0-9-]*)\s*$",
}
# The placeholder of the 4.0 template of the pull request text.
OLD_PR_PLACEHOLDER = "{voci}"

# --- the lines of a convening (C.4): accepted in every language, taught in the language of the brief ---

CONVENE_LINES = {
    "canary": {"en": "Canary:", "it": "Canarino:"},
    "decides_re": r"^(?:decides|decide): (?:yes|no|sì|si)\s*$",
    "decides": {"en": "«decides: yes» or «decides: no»", "it": "«decide: sì» o «decide: no»"},
    "outcome_re": r"^(?:Outcome: (closed|not closed)|Esito: (chiuso|non chiuso))\b",
    "outcome": {"en": "«Outcome: closed» or «Outcome: not closed»", "it": "«Esito: chiuso» o «Esito: non chiuso»"},
    # the Correctness line of a verdict (gate rules 2): «proven» means proven or verified
    "correctness_re": r"^(?:Correctness|Correttezza): (proven|verified|supported|refuted|unresolved|dimostrat[ao]|"
                      r"provat[ao]|verificat[ao]|sostenut[ao]|supportat[ao]|smentit[ao]|confutat[ao]|non risolt[ao])\b",
    "correctness": {"en": "«Correctness: proven|verified|supported|refuted|unresolved»",
                    "it": "«Correttezza: dimostrata|verificata|sostenuta|smentita|non risolta»"},
    # a missing sentinel declared in CLOSURE.md, with its reason
    "declared_missing_re": r"^(?:Declared missing|Dichiarato mancante): (sentinel|sentinella)\s*[:—-]\s*(\S.*)$",
    "declared_missing": {"en": "«Declared missing: sentinel: <reason>»",
                         "it": "«Dichiarato mancante: sentinella: <motivo>»"},
    # the fields of the contract that an amendment changes
    "amends_re": r"^(?:Amends|Modifica): *(\S.*)$",
    "amends": {"en": "«Amends: <contract fields>»", "it": "«Modifica: <campi del contratto>»"},
    "countersign": {"en": "Countersign: arbitro", "it": "Controfirma: arbitro"},
    "not_relevant": {"en": "not relevant:", "it": "non pertinente:"},
    "results": {"DONE": "FATTO", "ISSUES": "PROBLEMI", "BLOCKED": "BLOCCATO"},
    "missing_expert": {"en": "MISSING-EXPERT", "it": "ESPERTO-MANCANTE"},
    "to_fill_in": {"en": "<to fill in>", "it": "<da compilare>"},
    "contract_fields": {"Question": "Domanda", "Criterion": "Criterio", "Inputs": "Ingressi",
                        "Constraints": "Vincoli", "Exclusions": "Esclusioni", "Budget": "Quota", "Profile": "Profilo"},
    "canary_token": {"en": "swarmer-canary-", "it": "sciame-canarino-"},
}

# --- the labels of the head of a card in AGENTS.md, by language ---

LABELS = {
    "it": {"short": "In breve", "core": "Nucleo", "keywords": "Parole chiave", "parent": "Specializzazione di",
           "version": "Nello sciame dalla versione", "sub": "Sottoprofessionisti", "origin": "Origine",
           "core_heading": "Nucleo"},
    "en": {"short": "In short", "core": "Core", "keywords": "Keywords", "parent": "Specialization of",
           "version": "In the swarm since version", "sub": "Sub-professionals", "origin": "Origin",
           "core_heading": "Core:"},
}
# The role ids that the protocols name (data: never translated).
ROLES = {'arbiter': 'arbitro',
         'adversary': 'avversario',
         'inverter': 'rovesciatore',
         'logician': 'logico',
         'debugger': 'debugger',
         'statistician': 'statistico',
         'guarantor': 'garante',
         'formalist': 'formalista',
         'metrologist': 'metrologo'}
AGENT_PREFIXES = ("swarmer", "sciame")
# The folders of the agents of each target (generate.TARGETS), with their extension: Claude Code, Codex,
# Antigravity, Gemini CLI.
AGENT_DIRS = ((".claude/agents", ".md"), (".codex/agents", ".toml"), (".agents/agents", ".md"), (".gemini/agents", ".md"))

# --- the expert register (C.9) ---

REGISTER_WORDS = {"created": ("created", "creato"), "merged": ("merged into", "unito a")}
REGISTER_CLOSED = {"en": "- `{id}`: created, n. {n} ({date})", "it": "- `{id}`: creato, n. {n} ({date})"}
PLENARY_WORDS = ("plenary", "plenaria")


def normalize_requester(x: str) -> str:
    """The canonical form of a requester of the expert register: `coordinator`, `provisional:<id>` or `<id>` without
    an agent prefix. The result is not checked against the known roles: the caller does it."""
    c = x.strip().lower()
    for p in AGENT_PREFIXES:
        if c.startswith(p + "-"):
            c = c[len(p) + 1:]
            break
    if c in ("coordinator", "coordinatore"):
        return "coordinator"
    for p in ("provisional:", "provvisorio:"):
        if c.startswith(p):
            rest = c[len(p):]
            for q in AGENT_PREFIXES:
                if rest.startswith(q + "-"):
                    rest = rest[len(q) + 1:]
            return "provisional:" + rest
    return c


# --- schemas by path (C.0) ---

class Templates:
    """A value table of templates with a {rel}-like placeholder: canonical (en) text ↔ dialect text."""

    def __init__(self, table: dict):
        self.table = table

    @staticmethod
    def _match(template: str, text: str):
        parts = re.split(r"(\{[a-z_]+\})", template)
        rx = "".join(f"(?P<{p[1:-1]}>.+?)" if p.startswith("{") else re.escape(p) for p in parts)
        m = re.fullmatch(rx, text, re.S)
        return m.groupdict() if m else None

    def convert(self, value, src: str | None, dst: str):
        if not isinstance(value, str):
            return value
        for forms in self.table.values():
            for lang in ([src] if src else forms):
                kw = self._match(forms[lang], value) if lang in forms else None
                if kw is not None:
                    return forms[dst].format(**kw)
        return value


class Schema:
    """A schema by path. `fields` maps a path (a tuple of canonical keys; "*" for the keys of a map indexed by data)
    to (en key, it key, value table or None); `keymaps` maps a "*" path to a list of (en prefix, it prefix) for the
    keys of that map that carry a translated prefix (agent-<k> ↔ agente-<k>)."""

    def __init__(self, name: str, tree: dict, keymaps: dict | None = None):
        self.name = name
        self.fields = {}
        self.keymaps = keymaps or {}
        self._build(tree, ())

    def _build(self, tree: dict, path: tuple) -> None:
        for k, spec in tree.items():
            it, table, children = (tuple(spec) + (None, None, None))[:3]
            p = path + (k,)
            self.fields[p] = (k, it if it is not None else k, table)
            if children:
                self._build(children, p)

    def children(self, path: tuple) -> dict:
        n = len(path) + 1
        return {p[-1]: f for p, f in self.fields.items() if len(p) == n and p[:-1] == path and p[-1] != "*"}

    def is_map(self, path: tuple) -> bool:
        return path + ("*",) in self.fields


def _table_convert(table, value, dst: str):
    if table is None:
        return value
    if isinstance(table, Templates):
        return table.convert(value, None, dst)
    if isinstance(value, list):
        return [_table_convert(table, x, dst) for x in value]
    if not isinstance(value, str):
        return value
    if dst == "en":
        rev = {v: k for k, v in table.items()}
        return rev.get(value, value)
    return table.get(value, value)


def _key_map(schema: Schema, path: tuple, key: str, dst: str) -> str:
    for en, it in schema.keymaps.get(path, ()):
        src_p, dst_p = (it, en) if dst == "en" else (en, it)
        if key.startswith(src_p) and re.fullmatch(r"\d+", key[len(src_p):] or "x"):
            return dst_p + key[len(src_p):]
    return key


def _walk(obj, schema: Schema, path: tuple, dst: str, where: str, unknown: list | None = None):
    if isinstance(obj, list):
        f = schema.fields.get(path)
        if f and f[2] is not None and all(not isinstance(x, (dict, list)) for x in obj):
            return _table_convert(f[2], obj, dst)
        return [_walk(x, schema, path, dst, where, unknown) for x in obj]
    if isinstance(obj, dict) and (path == () or path in schema.fields):
        if schema.is_map(path):
            star = path + ("*",)
            out = {}
            for k, v in obj.items():
                ck = _key_map(schema, star, k, dst)
                if ck in out:
                    raise Error(f"{where}: two keys for {ck!r} at {'/'.join(path) or 'top level'}")
                out[ck] = _walk(v, schema, star, dst, where, unknown)
            return out
        kids = schema.children(path)
        by_name = {}
        for canon, (en, it, _t) in kids.items():
            by_name.setdefault(en, canon)
            by_name.setdefault(it, canon)
        out, seen = {}, {}
        for k, v in obj.items():
            canon = by_name.get(k)
            if canon is None:
                if unknown is None:
                    raise Error(f"{where}: unknown key {k!r} at {'/'.join(path) or 'top level'}")
                unknown.append("/".join(path + (k,)))   # kept as it is, never translated (data the 4.0 accepted)
                out[k] = v
                continue
            if canon in seen:
                raise Error(f"{where}: the same key in two languages: {seen[canon]!r} and {k!r}")
            seen[canon] = k
            en, it, _t = kids[canon]
            out[en if dst == "en" else it] = _walk(v, schema, path + (canon,), dst, where, unknown)
        return out
    f = schema.fields.get(path)
    return _table_convert(f[2], obj, dst) if f else obj


def to_canonical(obj, schema: Schema, where: str = "", unknown: list | None = None):
    """The canonical form of a data object read in any dialect: keys and controlled values in English. An unknown key
    is an error, unless a list `unknown` is given: then it is kept as it is and its path is appended (the data the 4.0
    accepted: config.json, giuria.json); the same concept in two languages is an error; free texts are never
    translated."""
    return _walk(obj, schema, (), "en", where or schema.name, unknown)


def to_dialect(obj, schema: Schema, lang: str, where: str = "", unknown: list | None = None):
    """The object in the dialect `lang` (en = canonical)."""
    if lang == "en":
        return _walk(obj, schema, (), "en", where or schema.name, unknown)
    return _walk(obj, schema, (), lang, where or schema.name, unknown)


def dialect_of(obj, schema: Schema, default: str) -> str:
    """The dialect of an object: the language of most of its recognised keys (keys equal in both languages do not
    count); a tie gives `default`."""
    count = {"en": 0, "it": 0}

    def visit(o, path):
        if isinstance(o, list):
            for x in o:
                visit(x, path)
        elif isinstance(o, dict) and (path == () or path in schema.fields):
            if schema.is_map(path):
                for v in o.values():
                    visit(v, path + ("*",))
                return
            kids = schema.children(path)
            for k, v in o.items():
                for canon, (en, it, _t) in kids.items():
                    if k in (en, it):
                        if en != it:
                            count["en" if k == en else "it"] += 1
                        visit(v, path + (canon,))
                        break
    visit(obj, ())
    if count["en"] == count["it"]:
        return default
    return "en" if count["en"] > count["it"] else "it"


DB_SCHEMA = Schema("db", {
    "format": ("formato",),
    "entries": ("voci", None, {
        "id": ("sigla",), "type": ("tipo", VALUES["entry_type"]), "parent": ("genitore",), "core": ("nucleo",),
        "version": ("versione",), "status": ("stato", VALUES["entry_status"]),
        "texts": ("testi", None, {"*": (None, None, {
            "name": ("nome",), "short": ("breve",), "keywords": ("parole",), "body": ("corpo",)})}),
    }),
})
# A translation of the local overlay (<swarm>/local/translations/<lang>/<id>.json, K.3): the texts of one entry in
# one language, and the fingerprint of the texts as `translate` wrote them.
TRANSLATION_SCHEMA = Schema("translation", {
    "id": ("sigla",), "language": ("lingua",), "name": ("nome",), "short": ("breve",), "keywords": ("parole",),
    "body": ("corpo",), "written_sha256": ("sha256_scritto",),
})
CORES_SCHEMA = Schema("cores", {
    "format": ("formato",),
    "cores": ("nuclei", None, {"id": ("id",), "texts": ("testi", None, {"*": (None, None, {"name": ("nome",)})})}),
})
CONFIG_SCHEMA = Schema("config.json", {
    "folder": ("cartella",), "local": ("locale",), "project_managed": ("gestiti_dal_progetto",),
    "models": ("modelli", None, {"*": (None,)}), "prefix": ("prefisso",),
    "swarmer_sh_copies": ("copie_sciame_sh",), "local_repository": ("repository_locale",),
    "targets": ("destinazioni",), "cli": ("cli",), "extensions": ("estensioni",),
})
JURY_SCHEMA = Schema("jury.json", {
    "subject": ("oggetto",), "rapporteur": ("relatore",), "clerk": ("cancelliere",),
    "jurors": ("giurati", None, {"role": ("ruolo",), "provisional": ("provvisorio",),
                                 "fresh_on_subject": ("nuovo_sull_oggetto",)}),
    "touches_code": ("tocca_codice",), "touches_numbers": ("tocca_numeri",),
    "authority": ("autorita", VALUES["authority"]), "delegation": ("delega", VALUES["jury_delegation"]),
    "classification": ("classificazione", VALUES["jury_form"]), "form": ("forma", VALUES["jury_form"]),
    "protocol": ("protocollo",), "lexicon": ("lessico",), "round_limit": ("limite_giri",),
    "relevance": ("pertinenza", VALUES["jury_relevance"]),
    "previous": ("precedenti",),
})
_DECISION = {
    "option": ("opzione",), "operative_text": ("dispositivo",), "proposal_sha": ("sha_proposta",),
    "depends_on": ("dipende",), "yes": ("si",), "no": ("no",), "state": ("stato", STATES),
    "text_round": ("giro_del_testo",),
    "requested_revisions": ("revisioni_chieste", None, {"*": (None,)}),
    "yes_conditions": ("condizioni_dei_si", None, {"*": (None,)}),
    "preferences": ("preferenze", None, {"*": (None,)}),
    "plenary_class": ("classe_plenaria",),
    "regression": ("regressiva", None, {"round": ("giro",), "yes_lost": ("si_persi",),
                                        "round_votes": ("voti_del_giro", None, {"yes": ("si",), "no": ("no",)})}),
    "incompatible": ("incompatibile", None, {"round": ("giro",), "reason": ("motivo",), "verified": ("verificata",)}),
    "test": ("prova", None, {"text": ("testo",), "outcome": ("esito", VALUES["test_outcome"])}),
    "reason": ("motivo", Templates(REASONS)),
    "repropose_with": ("da_riproporre_con",), "waiting_for": ("in_attesa_di",),
    "suspended_by": ("sospesa_per", None, {"blocked_by": ("dipende_da",), "state": ("stato", STATES)}),
}
OUTCOME_SCHEMA = Schema("outcome", {
    "round": ("giro",), "jurors": ("giurati",), "n": ("n",), "round_limit": ("limite_giri",),
    "form": ("forma", VALUES["jury_form"]), "protocol": ("protocollo",), "lexicon": ("lessico",),
    "vote_shas": ("sha_voti", None, {"*": (None,)}), "jury_sha": ("sha_giuria",),
    "decisions": ("decisioni", None, {"*": (None, None, _DECISION)}),
})
MANIFEST_SCHEMA = Schema("manifest", {
    "version": ("versione",), "name": ("nome",), "strategy": ("strategia", VALUES["strategy"]),
    "profile": ("profilo", VALUES["profile"]), "question": ("domanda",), "seed": ("seme",), "created": ("creato",),
    "f1": ("f1", None, {"*": (None, None, {"folder": ("cartella",), "lane": ("corsia", VALUES["lane"]),
                                           "role": ("ruolo",)})}),
    "selected": ("selezionate",), "radical": ("radicale",), "map": ("mappa",),
    "gate_rules": ("regole_cancelli",), "radical_funded": ("radicale_finanziato",),
    "fan_out": ("ventaglio", None, {"n": ("n",), "form": ("forma", VALUES["form"]), "rule": ("regola", VALUES["rule"])}),
}, keymaps={("f1", "*"): [("agent-", "agente-")]})
CONVENE_KEYS = {
    "manifest": MANIFEST_SCHEMA,
    "snapshot": Schema("snapshot", {"time": ("ora",), "file": ("file", None, {"*": (None, None, {
        "mtime": ("mtime",), "read_after": ("letto_dopo",)})})}),
    "seal": Schema("seal", {"time": ("ora",), "file": ("file",), "sha256": ("sha256",), "bytes": ("byte",)}),
    "gate": Schema("gate", {"phase": ("fase",), "time": ("ora",), "notes": ("note",),
                            "not_delivered": ("non_consegnati",), "fingerprints": ("impronte", None, {"*": (None,)}),
                            "rules": ("regole",), "closed": ("chiuso",), "warnings": ("avvisi",)}),
    "early_closure": Schema("early closure", {"time": ("ora",), "hypothesis": ("ipotesi",), "reason": ("motivo",),
                                              "status": ("stato", VALUES["closure_status"]),
                                              "deciding_test": ("prova_decisiva",)}),
    # the map of the lanes (not in the 4.0 list of the spec, but written by prepare: role → folder, lane, canary)
    "map": Schema("map", {"*": (None, None, {"folder": ("cartella",), "lane": ("corsia", VALUES["lane"]),
                                             "canary": ("canarino",)})}),
}

# --- names of the files of a convening (C.4) and of a jury (C.5): canonical → Italian ---

CONVENE_FILES = {
    "MANIFEST.json": "MANIFESTO.json", "CONTRACT.md": "CONTRATTO.md", "TASK.md": "TASK.md",
    "DELIVERABLE.md": "CONSEGNA.md", "SNAPSHOT.json": "FOTO.json", "SEALS.jsonl": "SIGILLI.jsonl",
    "EARLY_CLOSURE.json": "CHIUSURA_ANTICIPATA.json", "MAP.json": "MAPPA.json", "CONSOLIDATION.md": "CONSOLIDAMENTO.md",
    "01-translation": "01-traduzione", "CARDS.md": "SCHEDE.md", "02-signatures": "02-firme", "README.md": "LEGGIMI.md",
    "03-triage": "03-triage", "TRIAGE.md": "TRIAGE.md", "04-tournament": "04-torneo", "TOURNAMENT.md": "TORNEO.md",
    "05-selection": "05-selezione", "SELECTION.md": "SELEZIONE.md", "SOLUTION.md": "SOLUZIONE.md",
    "VERIFICATION.md": "VERIFICA.md", "MEASUREMENT_PLAN.md": "PIANO_MISURE.md", "ATTACK.md": "ATTACCO.md",
    "PREDICTIONS.md": "PREVISIONI.md", "COUNTERCHECKS.md": "CONTROPROVE.md", "DEFECTS.md": "DIFETTI.md",
    "MEASUREMENTS.md": "MISURE.md", "VERDICT.md": "VERDETTO.md", "CLOSURE.md": "CHIUSURA.md",
    "HYPOTHESIS_CARD.md": "SCHEDA_IPOTESI.md",
    "00-sentinel": "00-sentinella", "SENTINEL.md": "SENTINELLA.md", "HIDDEN_ASSUMPTIONS.md": "ASSUNZIONI_NASCOSTE.md",
    "REVISION.md": "REVISIONE.md", "work": "lavoro", "status.md": "stato.md",
}
# Names with a variable part: (canonical regex, canonical template, Italian regex, Italian template).
CONVENE_PATTERNS = [
    (r"agent-(\d+)", "agent-{0}", r"agente-(\d+)", "agente-{0}"),
    (r"\.(.+)\.lanes", ".{0}.lanes", r"\.(.+)\.corsie", ".{0}.corsie"),
    (r"AMENDMENT_(A?\d+)\.md", "AMENDMENT_{0}.md", r"EMENDAMENTO_(A?\d+)\.md", "EMENDAMENTO_{0}.md"),
]
JURY_FILES = {"jury.json": "giuria.json", "PROPOSAL.md": "PROPOSTA.md", "SEALS.md": "SIGILLI.md",
              "DELEGATION.md": "DELEGA.md", "RELEVANCE.md": "PERTINENZA.md"}
JURY_PATTERNS = [
    (r"round_(\d+)", "round_{0}", r"giro_(\d+)", "giro_{0}"),
    (r"VOTE_(.+)\.md", "VOTE_{0}.md", r"VOTO_(.+)\.md", "VOTO_{0}.md"),
    (r"OUTCOME_round_(\d+)\.json", "OUTCOME_round_{0}.json", r"ESITO_giro_(\d+)\.json", "ESITO_giro_{0}.json"),
    (r"CARD_(.+)\.md", "CARD_{0}.md", r"SCHEDA_(.+)\.md", "SCHEDA_{0}.md"),
    (r"RECUSAL_(.+)\.md", "RECUSAL_{0}.md", r"RINUNCIA_(.+)\.md", "RINUNCIA_{0}.md"),
]


def _name_in(name: str, lang: str, table: dict, patterns: list) -> str:
    """One path component, from its canonical name to the dialect `lang`."""
    if lang == "en":
        return name
    if name in table:
        return table[name]
    for crx, _ct, _irx, itp in patterns:
        m = re.fullmatch(crx, name)
        if m:
            return itp.format(*m.groups())
    return name


def _name_canonical(name: str, table: dict, patterns: list) -> str:
    rev = {v: k for k, v in table.items()}
    if name in rev:
        return rev[name]
    for _crx, ctp, irx, _it in patterns:
        m = re.fullmatch(irx, name)
        if m:
            return ctp.format(*m.groups())
    return name


def localize_path(canonical: str, lang: str, kind: str) -> str:
    """A relative path of a convening ("convene") or a jury ("jury"), component by component, in the dialect."""
    table, pats = (CONVENE_FILES, CONVENE_PATTERNS) if kind == "convene" else (JURY_FILES, JURY_PATTERNS)
    return "/".join(_name_in(x, lang, table, pats) for x in canonical.split("/"))


def canonical_path(name: str, kind: str) -> str:
    table, pats = (CONVENE_FILES, CONVENE_PATTERNS) if kind == "convene" else (JURY_FILES, JURY_PATTERNS)
    return "/".join(_name_canonical(x, table, pats) for x in name.split("/"))


def _dialect_by_root(folder: Path, en_name: str, it_name: str, what: str, default: str | None) -> str:
    folder = Path(folder)
    en, it = (folder / en_name).exists(), (folder / it_name).exists()
    if en and it:
        raise Error(f"both {folder / en_name} and {folder / it_name} exist")
    if en:
        return "en"
    if it:
        return "it"
    if default is None:
        raise Error(f"{folder} is not a {what} (neither {en_name} nor {it_name})")
    return default


def jury_dialect(folder, default: str | None = None) -> str:
    """The dialect of a jury: jury.json → en, giuria.json → it (both → error)."""
    return _dialect_by_root(folder, "jury.json", "giuria.json", "jury", default)


def jury_file(folder, canonical: str, lang: str | None = None) -> Path:
    """The path of a file of a jury in its dialect. Fails if the name of the other dialect exists too, for the top
    component (inside a round a file of the other dialect is an extraneous entry, as in 4.0)."""
    folder = Path(folder)
    lang = lang or jury_dialect(folder)
    rel = localize_path(canonical, lang, "jury")
    top_c = canonical.split("/")[0]
    other = "it" if lang == "en" else "en"
    top_o = _name_in(top_c, other, JURY_FILES, JURY_PATTERNS)
    if top_o != rel.split("/")[0] and (folder / top_o).exists() and (folder / rel.split("/")[0]).exists():
        raise Error(f"both {folder / rel.split('/')[0]} and {folder / top_o} exist")
    if top_o != rel.split("/")[0] and (folder / top_o).exists() and not (folder / rel.split("/")[0]).exists():
        raise Error(f"{folder / top_o} belongs to the other dialect of this jury ({lang}): rename it")
    return folder / rel


def convene_dialect(folder, default: str | None = None) -> str:
    """The dialect of a convening: MANIFEST.json → en, MANIFESTO.json → it (both → error)."""
    return _dialect_by_root(folder, "MANIFEST.json", "MANIFESTO.json", "convening", default)


def convene_file(folder, canonical: str, lang: str | None = None) -> Path:
    folder = Path(folder)
    lang = lang or convene_dialect(folder)
    return folder / localize_path(canonical, lang, "convene")


# --- the database: format 1 (4.0, Italian keys) ↔ format 2 ---

def db_from_v1(d: dict) -> dict:
    """A database file in format 1 (professionisti.json or nuclei.json) in format 2, same order of keys and entries."""
    schema = CORES_SCHEMA if ("nuclei" in d or "cores" in d) else DB_SCHEMA
    out = to_canonical(d, schema, schema.name)
    if "format" in out:
        out["format"] = 2
    return out


def db_to_v1(d: dict) -> dict:
    """The inverse of db_from_v1: db_to_v1(db_from_v1(f1)) == f1."""
    if "cores" in d or "nuclei" in d:
        out = to_dialect(d, CORES_SCHEMA, "it", "cores")
    else:
        out = to_dialect(d, DB_SCHEMA, "it", "db")
    if "formato" in out:
        out["formato"] = 1
    return out


def is_v1(d: dict) -> bool:
    return d.get("formato") == 1 or "format" not in d


# --- words of the 4.0 that some modules have to recognise in texts ---

IMPORT_LABELS = ("In breve", "In short", "Nucleo", "Core", "Parole chiave", "Keywords", "Origine", "Origin")
