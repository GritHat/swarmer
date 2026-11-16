#!/usr/bin/env python3
"""The single database of the professionals and sub-professionals of the swarm.

`db/professionals.json` is the only source of the roles: every entry has the id, the type (`professional` or
`subprofessional`), the parent (for a sub-professional), the core, the version in which it entered, the status and
the texts in every language (name, short description, keywords, body of the card). `db/cores.json` gives the order
and the names of the cores. From here AGENTS.md in every language, the catalog, the agents and the skills are
generated. Format 2 (English keys); a format 1 database (the 4.0 files, compat.OLD_DB) is read and converted in
memory, and is always written in format 2.

The local overrides (`<swarm>/local/AGENTS.md`, or the folder the configuration says) are cards in the format of
AGENTS.md: for the same id they always win over the generic role, and they never enter the database nor the public
repository.

    python3 -I engine/professionals.py validate [DB]           # checks the database
    python3 -I engine/professionals.py cards LANGUAGE [DB]     # prints AGENTS.md in the language
    python3 -I engine/professionals.py list [DB]               # ids, types, parents
    python3 -I engine/professionals.py import AGENTS.md LANGUAGE [DB]   # from a 3.x AGENTS.md to the database
Standard library only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compat as C  # noqa: E402

DEFAULT_DB = HERE.parent / "db"
DB_FILE, CORES_FILE = "professionals.json", "cores.json"
ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
TYPES = ("professional", "subprofessional")
STATUSES = ("active", "retired")
LANGUAGE_RE = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")
STRATEGIES = ("single", "fan-out", "classic", "jury", "light-jury", "full", "plenary", "expert", "auto")
# Reserved ids: the names of the strategies and of the skills, in every language (C.1).
RESERVED = set(STRATEGIES) | C.RESERVED_IT | {"local", "light"}
PREFIX_ALT = "|".join(C.AGENT_PREFIXES)
TITLE = re.compile(r"^### (\d+(?:\.\d+)?)\. (.+?) — `(?:" + PREFIX_ALT + r")-([a-z0-9-]+)`\s*$")
TEXT_FIELDS = ("name", "short", "keywords", "body")
CONTROL = re.compile(r"[\x00-\x1f\x7f  ]")


class Error(C.Error):
    pass


def line_problems(x: str) -> list[str]:
    """A one-line field: no newline nor control characters, no «|» (it would break the tables), no HTML comments
    nor block markers."""
    out = []
    if CONTROL.search(x):
        out.append("newline or control characters")
    if "|" in x:
        out.append("contains «|»")
    if "<!--" in x or "-->" in x:
        out.append("contains an HTML comment")
    if x.lstrip().startswith("#"):
        out.append("starts with «#»")
    return out


def _read(db: Path, name: str):
    p = db / name
    if not p.is_file():
        old = db / C.OLD_DB[name]
        if old.is_file():
            p = old
    return json.loads(p.read_text(encoding="utf-8"))


def to_v2(entries_file: dict, cores_file: dict) -> tuple[dict, dict]:
    """The two files in format 2 (a format 1 file is converted, in memory)."""
    if C.is_v1(entries_file):
        entries_file = C.db_from_v1(entries_file)
    if C.is_v1(cores_file):
        cores_file = C.db_from_v1(cores_file)
    return entries_file, cores_file


def load(db: Path = DEFAULT_DB) -> dict:
    db = Path(db)
    try:
        e, c = to_v2(_read(db, DB_FILE), _read(db, CORES_FILE))
    except (OSError, json.JSONDecodeError, C.Error) as x:
        raise Error(f"database not readable in {db}: {x}")
    return {"entries": e.get("entries", []), "cores": c.get("cores", []), "languages": languages_of(e)}


def entries_v2(file_data: dict) -> list[dict]:
    """The entries of a database file or of an `approve` file, in either format."""
    if not isinstance(file_data, dict):
        return []
    keys = C.DB_SCHEMA.fields[("entries",)][:2] + C.DB_SCHEMA.fields[("format",)][:2]
    if C.is_v1(file_data) and any(k in file_data for k in keys):
        return C.db_from_v1(file_data).get("entries", [])
    return file_data.get("entries", [])


def entry_v2(e: dict) -> dict:
    """One entry, in format 1 or 2, in format 2."""
    if not isinstance(e, dict):
        return e
    return C.to_canonical({"entries": [e]}, C.DB_SCHEMA, "entry")["entries"][0]


def languages_of(entries_file: dict) -> list[str]:
    every = set()
    for v in entries_file.get("entries", []):
        every |= set(v.get("texts", {}))
    return sorted(every)


# English is mandatory and complete in the public database (K.1); the other languages are optional.
REQUIRED = ("en",)


def text_problems(t, where: str, lang: str) -> list[str]:
    """The errors of the texts of one entry in one language: every field present, keywords a list, a body that does
    not break AGENTS.md, one-line fields."""
    if not t or not isinstance(t, dict):
        return [f"{where}: texts missing in «{lang}»"]
    errors = []
    for c in TEXT_FIELDS:
        if not t.get(c):
            errors.append(f"{where}: text «{c}» empty in «{lang}»")
    if not isinstance(t.get("keywords", []), list):
        errors.append(f"{where}: «keywords» is not a list in «{lang}»")
    body = t.get("body", "")
    if not isinstance(body, str):
        return errors + [f"{where}: the body in «{lang}» is not a text"]
    if re.search(r"^\s*#", body, re.M):
        errors.append(f"{where}: the body in «{lang}» has lines starting with «#», which would break AGENTS.md")
    if CONTROL.search(body.replace("\n", "").replace("\t", "")):
        errors.append(f"{where}: the body in «{lang}» contains control characters (for instance \\r)")
    if "<!--" in body:
        errors.append(f"{where}: the body in «{lang}» contains «<!--»")
    for c in ("name", "short"):
        errors += [f"{where}: «{c}» in «{lang}»: {x}" for x in line_problems(str(t.get(c, "")))]
    for w in t.get("keywords", []) if isinstance(t.get("keywords", []), list) else []:
        errors += [f"{where}: a keyword in «{lang}»: {x}" for x in line_problems(str(w))]
    return errors


def english_problems(entry: dict) -> list[str]:
    """What keeps an entry out of the public database: the English texts missing or incomplete (K.1)."""
    return text_problems((entry.get("texts") or {}).get("en"), str(entry.get("id", "?")), "en")


def validate(d: dict, langs: list[str] | None = None, existing=(), required=REQUIRED) -> list[str]:
    """The errors of the database: structure, ids, parents, cores, texts. The languages of `required` (English, by
    default: the public database, K.1) are mandatory for every entry; every other language present in an entry, and
    every language of `langs` it has, must be complete. With `required=()` (the generation in an installation, K.2)
    an entry needs only one complete language. A reserved id is an error only for an entry that is not in
    `existing` (a new one)."""
    errors = []
    required = tuple(required)
    existing = set(existing)
    cores = {n.get("id") for n in d["cores"]}
    for n in d["cores"]:
        for l in required:
            if not n.get("texts", {}).get(l, {}).get("name"):
                errors.append(f"core {n.get('id')}: name missing in «{l}»")
    seen, by_id = set(), {}
    for i, v in enumerate(d["entries"]):
        s = v.get("id", "")
        where = f"entry {i + 1} ({s or '?'})"
        if not ID_RE.match(s):
            errors.append(f"{where}: id not matching {ID_RE.pattern}")
        if s in RESERVED and s not in existing:
            errors.append(f"{where}: the id is reserved to a strategy")
        if s in seen:
            errors.append(f"{where}: duplicate id")
        seen.add(s)
        by_id[s] = v
        if v.get("type") not in TYPES:
            errors.append(f"{where}: type «{v.get('type')}» not in {TYPES}")
        if v.get("status", "active") not in STATUSES:
            errors.append(f"{where}: status «{v.get('status')}» not in {STATUSES}")
        if v.get("core") not in cores:
            errors.append(f"{where}: unknown core «{v.get('core')}»")
        if not re.match(r"^\d+\.\d+$", str(v.get("version", ""))):
            errors.append(f"{where}: version missing or not in the form «4.0»")
        texts = v.get("texts") if isinstance(v.get("texts"), dict) else {}
        if not texts:
            errors.append(f"{where}: no texts in any language")
        for l in required:
            if l not in texts:
                errors.append(f"{where}: texts missing in «{l}»" + (" (English is mandatory in the public database)"
                                                                     if l == "en" else ""))
        for l in sorted(texts):   # every language present (those of `langs` included) is complete
            if not LANGUAGE_RE.match(str(l)):
                errors.append(f"{where}: «{l}» is not a language code")
            errors += text_problems(texts[l], where, l)
    for v in d["entries"]:
        s, g = v.get("id"), v.get("parent")
        if v.get("type") == "professional" and g:
            errors.append(f"{s}: a professional has no parent")
        if v.get("type") == "subprofessional":
            if not g:
                errors.append(f"{s}: a sub-professional has a parent")
            elif g not in by_id:
                errors.append(f"{s}: parent «{g}» does not exist")
            elif by_id[g].get("type") != "professional":
                errors.append(f"{s}: the parent «{g}» is not a professional (one level only)")
            elif by_id[g].get("core") != v.get("core"):
                errors.append(f"{s}: the core is not the one of the parent «{g}»")
    return errors


def reserved_ids(d: dict) -> list[str]:
    """The ids of the database that are reserved (accepted with a warning when they were already there)."""
    return [v.get("id") for v in d["entries"] if v.get("id") in RESERVED]


def ordered(d: dict) -> list[dict]:
    """The active entries in order: by core, the professionals in the order of the database, each followed by its
    sub-professionals. Assigns the number: «7» to a professional, «7.2» to its second sub-professional."""
    active = [v for v in d["entries"] if v.get("status", "active") == "active"]
    children = {}
    for v in active:
        if v["type"] == "subprofessional":
            children.setdefault(v["parent"], []).append(v)
    out, n = [], 0
    for core in d["cores"]:
        for v in active:
            if v["type"] != "professional" or v["core"] != core["id"]:
                continue
            n += 1
            out.append(dict(v, number=str(n)))
            for k, f in enumerate(children.get(v["id"], []), 1):
                out.append(dict(f, number=f"{n}.{k}"))
    return out


def text(entry: dict, lang: str, fallback: str = "en") -> dict:
    t = entry["texts"]
    return t.get(lang) or t.get(fallback) or next(iter(t.values()))


def core_name(d: dict, cid: str, lang: str) -> str:
    for n in d["cores"]:
        if n["id"] == cid:
            t = n["texts"].get(lang) or n["texts"].get("en") or next(iter(n["texts"].values()))
            return t["name"]
    return cid


def card(d: dict, entry: dict, lang: str, prefix: str = "swarmer") -> str:
    """The card of an entry, in the format of AGENTS.md."""
    e = C.LABELS.get(lang, C.LABELS["en"])
    t = text(entry, lang)
    lines = [f"### {entry['number']}. {t['name']} — `{prefix}-{entry['id']}`", "",
             f"- **{e['short']}:** {t['short']}",
             f"- **{e['core']}:** {core_name(d, entry['core'], lang)}."]
    if entry["type"] == "subprofessional":
        g = next(x for x in d["entries"] if x["id"] == entry["parent"])
        lines.append(f"- **{e['parent']}:** {text(g, lang)['name']} (`{prefix}-{g['id']}`).")
    lines += [f"- **{e['keywords']}:** {', '.join(t['keywords'])}.", f"- **{e['version']}:** {entry['version']}.", "",
              t["body"].strip(), ""]
    return "\n".join(lines)


def agents_md(d: dict, lang: str, head: str = "", prefix: str = "swarmer") -> str:
    """AGENTS.md complete in the language: the head (from the documents of the language), then the cores with the
    cards."""
    parts = [head.rstrip() + "\n"] if head else []
    entries = ordered(d)
    for core in d["cores"]:
        es = [v for v in entries if v["core"] == core["id"]]
        if not es:
            continue
        parts.append(f"## {core_heading(lang)} {core_name(d, core['id'], lang)}\n")
        parts += [card(d, v, lang, prefix) for v in es]
    return "\n".join(parts).rstrip() + "\n"


def core_heading(lang: str) -> str:
    return C.LABELS.get(lang, C.LABELS["en"])["core_heading"]


# --- the local overrides ---

def _short_re():
    return re.compile(r"^- \*\*(" + "|".join(re.escape(x["short"]) for x in C.LABELS.values()) + r"):\*\*\s*(.*)$")


def local_cards(path: Path) -> dict[str, dict]:
    """The cards of a local AGENTS.md (format `### N. Name — `<prefix>-id``, any prefix of compat.AGENT_PREFIXES): id → {id,
    number, name, short, card}. The numbering is free. They never enter the database."""
    p = Path(path)
    if not p.is_file():
        return {}
    lines = p.read_text(encoding="utf-8").splitlines()
    starts = [i for i, r in enumerate(lines) if TITLE.match(r)]
    out = {}
    short_re = _short_re()
    for i in starts:
        end = len(lines)
        for j in range(i + 1, len(lines)):
            if TITLE.match(lines[j]) or lines[j].startswith("## ") or lines[j] == "---":
                end = j
                break
        n, name, cid = TITLE.match(lines[i]).groups()
        block = lines[i:end]
        short = ""
        for k, r in enumerate(block):
            m = short_re.match(r)
            if m:
                parts = [m.group(2)]
                for s in block[k + 1:]:
                    if not s.startswith("  ") or s.lstrip().startswith("- "):
                        break
                    parts.append(s.strip())
                short = " ".join(parts)
                break
        if cid in out:
            raise Error(f"{p}: two local cards with the id «{cid}»")
        out[cid] = {"id": cid, "number": n, "name": name, "short": short, "card": "\n".join(block).strip()}
    return out


# --- import from a 3.x AGENTS.md (migration) ---

def import_cards(path: Path, lang: str, d: dict) -> list[str]:
    """Adds to the database the cards of a 3.x AGENTS.md that the database does not have. Reports the others."""
    done = []
    cores_by_name = {core_name(d, n["id"], lang).lower(): n["id"] for n in d["cores"]}
    ids = {v["id"] for v in d["entries"]}
    labels = [x for x in C.LABELS.values()]
    for cid, s in local_cards(path).items():
        if cid in ids:
            done.append(f"{cid}: already there, not touching it")
            continue
        if cid in RESERVED:
            raise Error(f"{cid}: the id is reserved to a strategy")
        block = s["card"].splitlines()

        def field(names):
            for k, r in enumerate(block):
                for name in names:
                    if r.startswith(f"- **{name}:**"):
                        t = [r[len(f"- **{name}:**"):].strip()]
                        for x in block[k + 1:]:
                            if not x.startswith("  ") or x.lstrip().startswith("- "):
                                break
                            t.append(x.strip())
                        return " ".join(t)
            return ""
        core = cores_by_name.get(field([x["core"] for x in labels]).rstrip(".").strip().lower())
        if not core:
            done.append(f"{cid}: unknown core, not imported")
            continue
        head = re.compile(r"^- \*\*(" + "|".join(re.escape(x) for x in C.IMPORT_LABELS) + r"):\*\*")
        body = "\n".join(r for r in block[1:] if not head.match(r)
                         and not (r.startswith("  ") and not r.lstrip().startswith("- "))).strip()
        d["entries"].append({"id": cid, "type": "professional", "parent": None, "core": core,
                             "version": "5.0", "status": "active",
                             "texts": {lang: {"name": s["name"], "short": field([x["short"] for x in labels]),
                                              "keywords": [x.strip() for x in field([x["keywords"] for x in labels])
                                                           .rstrip(".").split(",") if x.strip()],
                                              "body": body + "\n"}}})
        done.append(f"{cid}: imported")
    return done


def db_text(d: dict) -> str:
    """The text of db/professionals.json: format 2, indent=1, ensure_ascii=False, order of the entries kept."""
    return json.dumps({"format": 2, "entries": d["entries"]}, ensure_ascii=False, indent=1) + "\n"


def save(d: dict, db: Path = DEFAULT_DB, dialect: str | None = None) -> None:
    """Writes db/professionals.json, always in format 2: the database belongs to the installation, not to the
    project, so the dialect rule of the project data does not apply (`dialect` is accepted and ignored). A format 1
    file next to it is left alone: the migration removes it."""
    (Path(db) / DB_FILE).write_text(db_text(d), encoding="utf-8")


def main(argv=None) -> None:
    a = list(sys.argv[1:] if argv is None else argv)
    try:
        if a[:1] == ["validate"]:
            d = load(Path(a[1]) if len(a) > 1 else DEFAULT_DB)
            errors = validate(d, d["languages"], existing=[v["id"] for v in d["entries"]])
            print("\n".join(errors) if errors else
                  f"valid database: {len(d['entries'])} entries, languages {', '.join(d['languages'])}")
            sys.exit(1 if errors else 0)
        elif a[:1] == ["cards"] and len(a) >= 2:
            d = load(Path(a[2]) if len(a) > 2 else DEFAULT_DB)
            print(agents_md(d, a[1]), end="")
        elif a[:1] == ["list"]:
            d = load(Path(a[1]) if len(a) > 1 else DEFAULT_DB)
            for v in ordered(d):
                print(f"{v['number']:>6}  {v['id']:<28} {v['type']:<20} {v.get('parent') or ''}")
        elif a[:1] == ["import"] and len(a) >= 3:
            db = Path(a[3]) if len(a) > 3 else DEFAULT_DB
            d = load(db)
            print("\n".join(import_cards(Path(a[1]), a[2], d)))
            save(d, db)
        else:
            print(__doc__)
            sys.exit(2)
    except Error as e:
        print(f"professionals: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
