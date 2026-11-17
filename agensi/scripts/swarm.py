#!/usr/bin/env python3
"""swarmer (Agensi edition): prints one piece of the public swarmer catalog. It only GETs fixed paths of the
catalog published from github.com/GritHat/swarmer (GitHub Pages); it sends nothing, and the search runs here.

  swarm.py roles [--match TEXT]   the roster, or the roles whose keywords appear in TEXT
  swarm.py profile [NAME]         the profiles by task type, or the roles of one
  swarm.py guide STRATEGY         the protocol of a strategy
  swarm.py card ID                the whole prompt of a role
  swarm.py doc NAME [SECTION]     the headings of a document, or one section
"""
import json
import os
import re
import sys
import urllib.request

BASE = os.environ.get("SWARMER_API") or "https://grithat.github.io/swarmer/api/v1/latest"
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


def get(path):
    with urllib.request.urlopen(f"{BASE.rstrip('/')}/{path}", timeout=30) as r:
        d = json.load(r)
    if d.get("format") != 1:
        sys.exit("the catalog changed format: load the skill again")
    return d


def main(a):
    cmd, rest = (a[0], a[1:]) if a else ("", [])
    if any(not NAME.match(x) for x in rest[:1]) and rest[:1] != ["--match"]:
        sys.exit("invalid name")
    if cmd == "roles":
        d = get("index.json")
        text = " ".join(rest[1:]).lower() if rest[:1] == ["--match"] else None
        out, last = [], None
        for rid, name, core, parent, short, kws in d["roles"]:
            if text is None:
                if core != last:
                    last = core
                    out.append(f"[{core}] {d['cores'].get(core, core)}")
                out.append(f"{'    ' if parent else '  '}{rid}: {name}")
                continue
            hit = [k for k in kws if re.search(r"(?<!\w)" + re.escape(k.lower()) + r"(?!\w)", text)]
            if hit:
                out.append((len(hit), f"{rid}: {name}{f' (sub of {parent})' if parent else ''} "
                                      f"[matched: {', '.join(hit)}]. {short}"))
        if text is not None:
            out = [s for _, s in sorted(out, key=lambda h: -h[0])] or ["no role matches: choose from the profile"]
        print("\n".join(out))
    elif cmd == "profile" and len(rest) <= 1:
        p = get("index.json")["profiles"]
        if not rest:
            print("\n".join(f"{k}: {v['for']}" for k, v in p.items()))
        elif rest[0] in p:
            print("\n".join(f"{k}: {v if isinstance(v, str) else ', '.join(v)}" for k, v in p[rest[0]].items()))
        else:
            sys.exit("profiles: " + ", ".join(p))
    elif cmd in ("guide", "card") and len(rest) == 1:
        print(get(f"{'guides' if cmd == 'guide' else 'roles'}/{rest[0]}.json")["text"])
    elif cmd == "doc" and 1 <= len(rest) <= 2:
        secs = get(f"docs/{rest[0].upper()}.json")["sections"]
        if len(rest) == 1:
            print("\n".join(h for h, _ in secs))
        else:
            print("\n\n".join(t for h, t in secs if rest[1].lower() in h.lower())[:40000] or "no such section")
    else:
        print(__doc__.strip())
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
