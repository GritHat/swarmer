#!/usr/bin/env python3
"""swarmer: the extensions of the swarm (since 5.2).

An extension lives in `<swarm>/extensions/<name>/` (the repository has the same layout):
- `extension.json`: name, version, requires (swarmer and other extensions), commands (command → entry module),
  documents, skills (skill id → body file), coordinator (the block appended to every strategy skill), state (its
  folders under the state folder of the project), provides (documentation of the files it offers to other extensions);
- `engine/*.py`: the entry module and its helpers, standard library only;
- `docs/<language>/*.md`: documents and skill bodies, with the same <!-- blocks --> in every language;
- `i18n/<language>.json`: the same keys in every language; the sections commands, options, values and files join the
  aliases of the core (aliases.py, paths.py), the other keys are the extension's texts.
Every extension is always shipped inside swarmer.sh; only enabling one is a choice (`extensions --add X`), recorded
in config.json (key `extensions`, Italian `estensioni`). An entry module offers `build_parser(al)` and
`main(argv, ctx) -> int`, with ctx = {swarm, root, lang, state, i18n}. Standard library only.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compat as C  # noqa: E402

FOLDER = "extensions"
KEYS = {"name", "version", "requires", "commands", "documents", "skills", "coordinator", "state", "provides"}
NAME = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
VERSION_RE = re.compile(r"^\d+\.\d+$")
REQ = re.compile(r"^>=\s*(\d+\.\d+)$")
FILE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_][A-Za-z0-9_.-]*)*$")
_MODULES: dict = {}
# the commands of the core (`verify` checks this list against the parser of swarmer.py): an extension command may not
# take one of these names
RESERVED = frozenset({"install", "update", "single", "fan-out", "classic", "jury", "light-jury", "full", "plenary",
                      "expert", "auto", "help", "language", "roles", "professionals", "check", "regenerate", "remove",
                      "targets", "instructions", "models", "requests", "count", "approve", "propose", "build", "verify",
                      "tests", "import-cards", "translate", "extensions"})


class Error(C.Error):
    pass


def version_tuple(v: str) -> tuple:
    return tuple(int(x) for x in str(v).split("."))


def folder(swarm) -> Path:
    return Path(swarm) / FOLDER


def _languages(swarm) -> list[str]:
    swarm = Path(swarm)
    docs = swarm / "docs"
    found = {p.name for p in docs.iterdir() if p.is_dir()} if docs.is_dir() else set()
    return sorted(l for l in found if (swarm / "i18n" / f"{l}.json").is_file())


def validate(swarm, d: Path, m) -> list[str]:
    """The problems of one manifest: schema, files that exist, documents and skills in every language."""
    where = f"{FOLDER}/{d.name}/extension.json"
    if not isinstance(m, dict):
        return [f"{where}: an object is needed"]
    out = [f"{where}: unknown key «{k}»" for k in sorted(set(m) - KEYS)]
    out += [f"{where}: the key «{k}» is missing" for k in ("name", "version", "requires", "commands") if k not in m]
    if out:
        return out
    if m["name"] != d.name or not NAME.match(str(m["name"])):
        out.append(f"{where}: name «{m['name']}» must be the folder name, lower case")
    if not VERSION_RE.match(str(m["version"])):
        out.append(f"{where}: version «{m['version']}» is not N.M")
    req = m["requires"]
    if not isinstance(req, dict) or set(req) - {"swarmer", "extensions"} or not REQ.match(str(req.get("swarmer", ""))) \
            or not isinstance(req.get("extensions", {}), dict) \
            or any(not REQ.match(str(v)) for v in req.get("extensions", {}).values()):
        out.append(f"{where}: requires is {{\"swarmer\": \">=N.M\", \"extensions\": {{name: \">=N.M\"}}}}")
    if not isinstance(m["commands"], dict) or not m["commands"]:
        out.append(f"{where}: commands is a map command → engine/<module>.py")
    else:
        for c, f in m["commands"].items():
            if not NAME.match(str(c)) or not FILE.match(str(f)) or not str(f).endswith(".py") \
                    or not (d / str(f)).is_file():
                out.append(f"{where}: command «{c}» → «{f}»: a lower-case name and an existing module")
            elif c in RESERVED:
                out.append(f"{where}: command «{c}» is a command of swarmer: choose another name")
    langs = _languages(swarm)
    docs = m.get("documents", [])
    skills = m.get("skills", {})
    if not isinstance(docs, list) or not isinstance(skills, dict):
        out.append(f"{where}: documents is a list of file names, skills a map id → file name")
        return out
    for f in list(docs) + list(skills.values()):
        if not FILE.match(str(f)) or "/" in str(f):
            out.append(f"{where}: «{f}» is not a file name")
            continue
        for l in langs:
            if not (d / "docs" / l / str(f)).is_file():
                out.append(f"{FOLDER}/{d.name}/docs/{l}/{f} is missing")
    for s in skills:
        if not NAME.match(str(s)):
            out.append(f"{where}: skill id «{s}» is not a lower-case name")
    co = m.get("coordinator")
    if co is not None and (not isinstance(co, str) or "#" not in co or co.split("#", 1)[0] not in docs):
        out.append(f"{where}: coordinator is «<one of the documents>#<block>»")
    if not isinstance(m.get("state", []), list) or any(not NAME.match(str(x)) for x in m.get("state", [])):
        out.append(f"{where}: state is a list of folder names")
    if not isinstance(m.get("provides", {}), dict):
        out.append(f"{where}: provides is a map path → format")
    for l in langs:
        if not (d / "i18n" / f"{l}.json").is_file():
            out.append(f"{FOLDER}/{d.name}/i18n/{l}.json is missing")
    return out


def manifests(swarm) -> tuple[dict, list[str]]:
    """Every extension of the swarm (valid ones only) and the problems of the others."""
    out, problems = {}, []
    base = folder(swarm)
    for d in sorted(base.iterdir()) if base.is_dir() else []:
        if not d.is_dir() or d.name.startswith((".", "_")):
            continue
        p = d / "extension.json"
        if not p.is_file():
            problems.append(f"{FOLDER}/{d.name}: extension.json is missing")
            continue
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            problems.append(f"{FOLDER}/{d.name}/extension.json: not json: {e}")
            continue
        bad = validate(swarm, d, m)
        if bad:
            problems += bad
        else:
            out[m["name"]] = m
    owners: dict = {}
    for n, m in out.items():
        for c in m["commands"]:
            owners.setdefault(c, []).append(n)
    for c, ns in sorted(owners.items()):                 # one command, two extensions: neither is valid
        if len(ns) > 1:
            problems += [f"{FOLDER}/{n}/extension.json: command «{c}» is also a command of the extension "
                         + ", ".join(x for x in ns if x != n) for n in ns]
            for n in ns:
                out.pop(n, None)
    return out, problems


def available(swarm) -> dict:
    """name → manifest of every extension of the swarm; an invalid manifest is an error."""
    out, problems = manifests(swarm)
    if problems:
        raise Error("; ".join(problems))
    return out


def enabled(root) -> list[str]:
    """The extensions enabled in the project: the key `extensions` of config.json (default none)."""
    import paths as S
    v = S.config(root).get("extensions") or []
    if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
        raise Error("config.json: extensions is a list of names")
    return list(dict.fromkeys(v))


def check_requires(manifests_: dict, names, swarmer_version: str) -> None:
    """An unknown name, too old a swarmer, or a missing, disabled or too old required extension is an error."""
    names = list(names)
    for n in names:
        if n not in manifests_:
            raise Error(f"unknown extension «{n}»: the extensions are {', '.join(sorted(manifests_)) or 'none'}")
        m = manifests_[n]
        need = REQ.match(m["requires"]["swarmer"]).group(1)
        if version_tuple(swarmer_version) < version_tuple(need):
            raise Error(f"{n} {m['version']} needs swarmer >= {need}, this is {swarmer_version}")
        for other, spec in sorted(m["requires"].get("extensions", {}).items()):
            want = REQ.match(spec).group(1)
            if other not in names:
                raise Error(f"{n} needs the extension {other} >= {want}: enable it first")
            if other not in manifests_ or version_tuple(manifests_[other]["version"]) < version_tuple(want):
                raise Error(f"{n} needs {other} >= {want}")


def required_by(manifests_: dict, names, x: str) -> list[str]:
    """The enabled extensions that require x."""
    return sorted(n for n in names if n != x and x in manifests_.get(n, {}).get("requires", {}).get("extensions", {}))


def i18n(swarm, name: str, lang: str) -> dict:
    """The extension's texts: en.json, overlaid by <lang>.json (dictionaries merged), as G.i18n."""
    d = folder(swarm) / name / "i18n"
    base = {}
    en = d / "en.json"
    if en.is_file():
        base = json.loads(en.read_text(encoding="utf-8"))
    p = d / f"{lang}.json"
    if lang != "en" and p.is_file():
        for k, v in json.loads(p.read_text(encoding="utf-8")).items():
            base[k] = {**base[k], **v} if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return base


def i18n_files(swarm) -> list[Path]:
    """Every i18n file of every extension folder (for aliases.py and paths.py, which must not fail on a bad one)."""
    base = folder(swarm) if swarm is not None else None
    if base is None or not base.is_dir():
        return []
    return sorted(base.glob("*/i18n/*.json"))


def entry(swarm, name: str, command: str | None = None):
    """The entry module of a command of the extension, loaded once, with its folder and <swarm>/engine on sys.path."""
    m = manifests(swarm)[0][name]                        # a broken other extension does not stop this one
    cmd = command or next(iter(m["commands"]))
    path = (folder(swarm) / name / m["commands"][cmd]).resolve()
    key = str(path)
    if key not in _MODULES:
        for p in (str(path.parent), str(Path(swarm).resolve() / "engine")):
            if p not in sys.path:
                sys.path.insert(0, p)
        sys.dont_write_bytecode = True
        spec = importlib.util.spec_from_file_location(f"swarmer_ext_{name}_{path.stem}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MODULES[key] = mod
    return _MODULES[key]


def commands(swarm) -> dict:
    """command → extension name, for every available extension."""
    out = {}
    for n, m in manifests(swarm)[0].items():
        for c in m["commands"]:
            out[c] = n
    return out


def command_owner(swarm, al: dict, word: str):
    """(extension, canonical command) when `word` is an extension command or one of its aliases, else None."""
    for c, n in commands(swarm).items():
        if word == c or word in [a for a in al.get("commands", {}).get(c, []) if not a.startswith("-")]:
            return n, c
    return None


def resolve_name(swarm, al: dict, word: str):
    """An extension named by its name, by one of its commands or by an alias of one (estensioni --aggiungi incroci)."""
    ms = manifests(swarm)[0]
    if word in ms:
        return word
    own = command_owner(swarm, al, word)
    return own[0] if own else word


def block(swarm, name: str, lang: str, ref: str) -> str:
    """The text of «<document>#<block>» in the language (en if the language lacks the document)."""
    import generate as G
    doc, _, b = ref.partition("#")
    for l in (lang, "en"):
        p = folder(swarm) / name / "docs" / l / doc
        if p.is_file():
            blocks = G.blocks(p.read_text(encoding="utf-8"))
            if b in blocks:
                return blocks[b]
    raise Error(f"{FOLDER}/{name}/docs/{lang}/{doc}: the block «{b}» is missing")
