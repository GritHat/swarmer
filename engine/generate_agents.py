#!/usr/bin/env python3
"""swarmer 5.0: the command of the 3.x, `python3 -I swarmer/generate_agents.py`, with its options.

    python3 -I swarmer/generate_agents.py                    # regenerates everything in the project
    python3 -I swarmer/generate_agents.py --check            # exits with 1 if something is not aligned to the sources
    python3 -I swarmer/generate_agents.py --install ROOT     # installs the swarm in another project
    python3 -I swarmer/generate_agents.py --instructions     # the paragraph in CLAUDE.md, AGENTS.md, GEMINI.md
    python3 -I swarmer/generate_agents.py --remove-instructions
    python3 -I swarmer/generate_agents.py --remove           # removes the generated agents and skills
    python3 -I swarmer/generate_agents.py --list             # the roles
The options have aliases in every language of i18n/. The work is done by swarmer/engine/swarmer.py.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SWARM = HERE.parent if HERE.name == "engine" else HERE
ENGINE = SWARM / "engine" / "swarmer.py"
sys.path.insert(0, str(SWARM / "engine"))
import aliases as A  # noqa: E402


def run(*arg):
    sys.exit(subprocess.run([sys.executable, "-I", str(ENGINE), "--swarm", str(SWARM), *arg]).returncode)


def canonical(option: str, al: dict) -> str:
    for canon, names in al["options"].items():
        if option == canon or option in names:
            return canon
    return option


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    al = A.load(SWARM)
    first = canonical(a[0], al) if a else None
    if not a:
        run("regenerate")
    elif first == "--check" and len(a) == 1:
        run("check")
    elif first == "--install" and len(a) == 2:
        run("install", "--from", str(SWARM), "--root", a[1])
    elif first == "--instructions" and len(a) == 1:
        run("instructions")
    elif first == "--remove-instructions" and len(a) == 1:
        run("instructions", "--remove")
    elif first == "--remove" and len(a) == 1:
        run("remove")
    elif first == "--list" and len(a) == 1:
        run("professionals")
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
