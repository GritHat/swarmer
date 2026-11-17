#!/usr/bin/env python3
"""The Agensi edition of swarmer: a static catalog for GitHub Pages and a three-file skill package that reads it.

    python3 -I -B .github/scripts/agensi.py --api DIR [--package DIR] [--zip FILE] [--test]

--api DIR writes the catalog, generated as an installation generates it (db/, docs/en/, i18n/en.json), under
DIR/api/v1/<version>/ and DIR/api/v1/latest/: index.json (the roster with short texts and keywords, the cores, the
profiles), roles/<id>.json (the whole prompt of each role: who it is, the rules, its full card),
guides/<strategy>.json (the protocol of each strategy) and docs/<NAME>.json (the full documents by section). One file
per role: the catalog grows with the database, the skill does not change.

--package DIR writes the skill for Agensi: SKILL.md (from agensi/SKILL.md), scripts/swarm.py, LICENSE.txt. Nothing else:
Agensi runs a script in isolation, so the script reads the catalog from GitHub Pages and nothing of the package.
--test runs every command of the package's script against the catalog just built (file://), in a temporary folder.

Versions: the catalog's is the plugin version, then the number of commits that changed swarmer.sh (a new specialist
always changes it); the package's is the plugin version, then the number of commits that changed agensi/. Both need
the full git history. Not part of swarmer.sh. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine"))
import generate as G  # noqa: E402

API = "https://grithat.github.io/swarmer/api/v1/latest"   # GitHub Pages of GritHat/swarmer
FORMAT = 1
STRATEGIES = ("auto", "single", "fan-out", "classic", "jury", "light-jury", "full", "plenary", "expert")
DOCS = ("PIPELINE", "JURY", "PREAMBLE", "ENVIRONMENT", "COORDINATOR_INSTRUCTIONS", "HYPOTHESIS_CARD")
SKILL_LIMIT, SCRIPT_LIMIT = 9_000, 5_000   # bytes: SKILL.md is loaded, the script written out, at every use


def git_count(*paths: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), "rev-list", "--count", "HEAD", "--", *paths], check=True,
                          capture_output=True, text=True).stdout.strip()


def plugin_version() -> str:
    return json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]


def shared(text: str) -> str:
    """The texts are shared with the full installation: the roles are called by id, the search is the script's."""
    text = re.sub(r"bash swarmer/swarmer\.sh roles ", "swarm.py roles --match ", text)
    return text.replace("`swarmer-<id>`", "`<id>`")


def sections(text: str) -> list[list[str]]:
    lines = text.splitlines()
    heads = [(i, len(m.group(1))) for i, l in enumerate(lines) if (m := re.match(r"^(#{1,4}) ", l))]
    out = []
    for k, (i, level) in enumerate(heads):
        end = next((j for j, lv in heads[k + 1:] if lv <= level), len(lines))
        out.append([lines[i], shared("\n".join(lines[i:end]).strip())])
    return out


def catalog() -> dict[str, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        data = G.catalog(ROOT, Path(tmp), "en")
    if any(r["origin"] != "generic" for r in data["roles"]):
        raise SystemExit("local roles found: the catalog is generated from the public database only")
    t, x = data["i18n"], data["texts"]
    st = x["strategies"]
    version = f"{plugin_version()}.{git_count('swarmer.sh')}"
    out = {"index.json": {
        "format": FORMAT, "version": version,
        "cores": {c["id"]: c["name"] for c in data["cores"]},
        "profiles": data["profiles"],
        "strategies": list(STRATEGIES),
        "roles": [[r["id"], r["name"], r["core"], r["parent"], r["short"], r["keywords"]] for r in data["roles"]]}}
    for r in data["roles"]:
        out[f"roles/{r['id']}.json"] = {"format": FORMAT, "version": version, "text": shared(r["prompt"].strip())}
    for s in STRATEGIES:
        parts = [x["coordinator"], x["brief"], x["environment"]]
        if s == "auto":
            parts += [t["auto_preamble"]] + [st[k] for k in STRATEGIES]
        elif s == "full":
            parts += [t["full_preamble"], st["full"], st["classic"]]
        elif s == "plenary":
            parts += [t["plenary_preamble"], st["plenary"], st["full"], st["jury"]]
        else:
            parts += [G.fmt(t["strategy_is"], strategy=s), st[s]]
        if s not in ("single", "expert"):
            parts.append(x["profiles"])
        text = shared("\n\n".join(p.strip() for p in parts if p.strip()))
        out[f"guides/{s}.json"] = {"format": FORMAT, "version": version, "text": text}
    for n in DOCS:
        text = (ROOT / "docs" / "en" / f"{n}.md").read_text(encoding="utf-8")
        out[f"docs/{n}.json"] = {"format": FORMAT, "version": version, "sections": sections(text)}
    return out


def package() -> dict[str, bytes]:
    script = (ROOT / "agensi" / "scripts" / "swarm.py").read_text(encoding="utf-8")
    if f'"{API}"' not in script:
        raise SystemExit(f"agensi/scripts/swarm.py does not read {API}")
    skill = (ROOT / "agensi" / "SKILL.md").read_text(encoding="utf-8")
    for k, v in (("@@VERSION@@", f"{plugin_version()}.{git_count('agensi')}"), ("@@API@@", API)):
        skill = skill.replace(k, v)
    if "@@" in skill or len(skill.encode()) > SKILL_LIMIT or len(script.encode()) > SCRIPT_LIMIT:
        raise SystemExit(f"agensi/: a placeholder left, SKILL.md over {SKILL_LIMIT} or swarm.py over {SCRIPT_LIMIT} bytes")
    return {"SKILL.md": skill.encode(), "scripts/swarm.py": script.encode(), "LICENSE.txt": (ROOT / "LICENSE").read_bytes()}   # Agensi takes only text files with an extension


def write(base: Path, files: dict[str, bytes]) -> None:
    for rel, data in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


def test(api: Path, pkg: Path) -> list[str]:
    errors = []
    index = json.loads((api / "index.json").read_text(encoding="utf-8"))
    skill = (pkg / "SKILL.md").read_text(encoding="utf-8")
    for c in ("guide", "roles", "profile", "card", "doc"):
        if f"swarm.py {c}" not in skill:
            errors.append(f"SKILL.md does not mention «swarm.py {c}»")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp, "swarm.py")   # as Agensi runs it: alone, in a temporary folder
        shutil.copy(pkg / "scripts" / "swarm.py", script)
        env = dict(os.environ, SWARMER_API=api.resolve().as_uri())
        calls = [["guide", s] for s in STRATEGIES] + [["card", r[0]] for r in index["roles"]] + [
            ["roles"], ["roles", "--match", "a Kalman filter drift in the LiDAR odometry"], ["profile"],
            ["profile", "code"], ["doc", "JURY"], ["doc", "JURY", "light jury"], ["doc", "pipeline"]]
        for args in calls:
            p = subprocess.run([sys.executable, "-I", "-B", str(script), *args], cwd=tmp, env=env, capture_output=True,
                               text=True, stdin=subprocess.DEVNULL)
            if p.returncode or not p.stdout.strip():
                errors.append(f"swarm.py {' '.join(args)}: rc={p.returncode}: {(p.stdout + p.stderr)[-200:]}")
        p = subprocess.run([sys.executable, "-I", "-B", str(script), "card", "../index"], cwd=tmp, env=env,
                           capture_output=True, text=True)
        if p.returncode == 0:
            errors.append("swarm.py accepts a path that leaves the catalog")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", required=True, help="the site folder: the catalog goes under api/v1/")
    ap.add_argument("--package")
    ap.add_argument("--zip")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    cat = catalog()
    version = cat["index.json"]["version"]
    files = {rel: (json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n").encode() for rel, d in cat.items()}
    site = Path(a.api)
    for v in ("latest", version):
        d = site / "api" / "v1" / v
        if d.exists():
            shutil.rmtree(d)
        write(d, files)
    (site / ".nojekyll").write_bytes(b"")
    print(f"catalog {version}: {len(files)} files, {sum(map(len, files.values()))} bytes, in {site}/api/v1/")
    pkg = package()
    pdir = Path(a.package) if a.package else Path(tempfile.mkdtemp()) / "swarmer"
    if pdir.exists():
        shutil.rmtree(pdir)
    write(pdir, pkg)
    if a.zip:
        with zipfile.ZipFile(a.zip, "w", zipfile.ZIP_DEFLATED) as z:
            for rel, data in sorted(pkg.items()):
                z.writestr(f"swarmer/{rel}", data)
    pv = pkg["SKILL.md"].decode().split("\nversion: ", 1)[1].split("\n", 1)[0]
    print(f"package {pv}: SKILL.md {len(pkg['SKILL.md'])} bytes, swarm.py {len(pkg['scripts/swarm.py'])} bytes, "
          f"in {pdir}" + (f", zip {a.zip}" if a.zip else ""))
    if a.test:
        errors = test(site / "api" / "v1" / "latest", pdir)
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        if errors:
            return 1
        print("every check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
