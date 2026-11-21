#!/usr/bin/env python3
"""swarmer: the localized names of the command line (B).

The canonical names of commands, options and values are English. Every language declares its aliases in
`i18n/<l>.json`: `"commands": {"install": ["<alias>"], …}`, `"options": {"--folder": ["--<alias>"], …}`,
`"values": {"strategy": {"single": "<alias>", …}, "form": …, "rule": …, "profile": …, "lane": …}`. The parsers join
the aliases of **every** available language (an Italian command works in an English installation too), with
`allow_abbrev=False` everywhere: abbreviations do not exist. The controlled values of compat.py are aliases too.
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compat as C  # noqa: E402

VALUE_CATEGORIES = ("strategy", "form", "rule", "profile", "lane")


def _as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return [str(x) for x in v]


def _sections(t: dict) -> dict:
    return {"commands": {k: _as_list(v) for k, v in t.get("commands", {}).items()},
            "options": {k: _as_list(v) for k, v in t.get("options", {}).items()},
            "values": {c: {k: _as_list(v) for k, v in m.items()}
                       for c, m in t.get("values", {}).items() if isinstance(m, dict)}}


def _merge(into: dict, sec: dict, core: dict) -> None:
    """An extension's sections join the table; a canonical of the core keeps the core's aliases (an extension never
    adds an alias to a core command, option or value: `verify` reports one that tries, see core_additions)."""
    for k in ("commands", "options"):
        for c, names in sec[k].items():
            if c in core[k]:
                continue
            lst = into[k].setdefault(c, [])
            lst += [x for x in names if x not in lst]
    for cat, m in sec["values"].items():
        for c, names in m.items():
            if c in core["values"].get(cat, {}):
                continue
            lst = into["values"].setdefault(cat, {}).setdefault(c, [])
            lst += [x for x in names if x not in lst]


def core_additions(core: dict, sec: dict) -> list[str]:
    """The aliases an extension section gives to a canonical of the core that the core does not have."""
    out = []
    for k in ("commands", "options"):
        for c, names in sec[k].items():
            if c in core[k]:
                out += [f"«{x}» for the core «{c}»" for x in names if x not in core[k][c]]
    for cat, m in sec["values"].items():
        for c, names in m.items():
            if c in core["values"].get(cat, {}):
                out += [f"«{x}» for the core value «{c}»" for x in names if x not in core["values"][cat][c]]
    return out


def per_language(swarm) -> dict[str, dict]:
    """The alias sections of each i18n file: lang → {"commands", "options", "values"}. The sections of the
    extensions (extensions/*/i18n/<lang>.json, 5.2) join those of the core: one table covers both, and the collision
    checks see both."""
    out = {}
    d = Path(swarm) / "i18n" if swarm else None
    for p in sorted(d.glob("*.json")) if d and d.is_dir() else []:
        try:
            t = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out[p.stem] = _sections(t)
    core = {l: json.loads(json.dumps(v)) for l, v in out.items()}
    ext = Path(swarm) / "extensions" if swarm else None
    for p in sorted(ext.glob("*/i18n/*.json")) if ext and ext.is_dir() else []:
        if p.stem not in out:
            continue
        try:
            t = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        _merge(out[p.stem], _sections(t), core[p.stem])
    return out


def load(swarm) -> dict:
    """The union of the aliases of every language, plus the controlled values of compat.py."""
    al = {"commands": {}, "options": {}, "values": {c: {} for c in VALUE_CATEGORIES}}
    for sec in per_language(swarm).values():
        for k in ("commands", "options"):
            for canon, names in sec[k].items():
                al[k].setdefault(canon, [])
                al[k][canon] += [n for n in names if n != canon and n not in al[k][canon]]
        for cat, m in sec["values"].items():
            for canon, names in m.items():
                lst = al["values"].setdefault(cat, {}).setdefault(canon, [])
                lst += [n for n in names if n != canon and n not in lst]
    for cat in VALUE_CATEGORIES:
        for canon, it in C.VALUES.get(cat, {}).items():
            lst = al["values"].setdefault(cat, {}).setdefault(canon, [])
            if it != canon and it not in lst:
                lst.append(it)
    return al


def command_aliases(al: dict, canon: str) -> list[str]:
    return [a for a in al["commands"].get(canon, []) if not a.startswith("-")]


def option_strings(al: dict, *canons: str) -> list[str]:
    out = []
    for c in canons:
        out += [c] + [a for a in al["options"].get(c, []) if a not in out and a != c]
    return list(dict.fromkeys(out))


def value(al: dict, cat: str, v):
    """The canonical form of a value given as canonical or as an alias of any language."""
    if v is None:
        return None
    m = al["values"].get(cat, {})
    if v in m:
        return v
    for canon, names in m.items():
        if v in names:
            return canon
    return v


def parser(**kw) -> argparse.ArgumentParser:
    kw.setdefault("allow_abbrev", False)
    return argparse.ArgumentParser(**kw)


def subparsers(p: argparse.ArgumentParser, al: dict, dest: str = "command"):
    """A subparser group whose `add(name)` registers the aliases and sets `<dest>` to the canonical name."""
    sp = p.add_subparsers(dest="_" + dest, required=True)

    def add(name: str, **kw):
        q = sp.add_parser(name, aliases=command_aliases(al, name), allow_abbrev=False, **kw)
        q.set_defaults(**{dest: name})
        return q
    return add


def arg(q: argparse.ArgumentParser, al: dict, *names: str, **kw):
    """An option with its aliases (the dest is the one of the first canonical name)."""
    if names and names[0].startswith("-"):
        kw.setdefault("dest", names[0].lstrip("-").replace("-", "_"))
        return q.add_argument(*option_strings(al, *names), **kw)
    return q.add_argument(*names, **kw)


def collisions(per_lang: dict, namespaces: dict[str, dict[str, list[str]]]) -> list[str]:
    """The alias collisions, by namespace (B): an alias equal to a different canonical of the namespace, the same
    alias for two canonicals. `namespaces` maps a name to {"commands": [...]} or {"options": [...]} or
    {"values:<cat>": [...]}."""
    errors = []
    for lang, sec in per_lang.items():
        for ns_name, spec in namespaces.items():
            for kind, canons in spec.items():
                if kind.startswith("values:"):
                    table = sec["values"].get(kind.split(":", 1)[1], {})
                else:
                    table = sec[kind]
                seen = {}
                for canon in canons:
                    for a in table.get(canon, []):
                        if a == canon:
                            continue
                        if a in canons:
                            errors.append(f"i18n/{lang}.json: {ns_name}: the alias «{a}» of «{canon}» is the canonical "
                                          f"name of another")
                        if a in seen and seen[a] != canon:
                            errors.append(f"i18n/{lang}.json: {ns_name}: the alias «{a}» is used for «{seen[a]}» and "
                                          f"«{canon}»")
                        seen.setdefault(a, canon)
    return errors
