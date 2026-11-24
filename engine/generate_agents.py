#!/usr/bin/env python3
"""swarmer: the command of the 3.x, `python3 -I swarmer/generate_agents.py`, with its options.

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
_ENG = SWARM / "engine"
# 5.3.2 (K-100, S18): compat is compiled from its source, never from a .pyc, and its engine_path puts the engine folder
# right after the standard library, every module of it compiled from its source
if not hasattr(sys.modules.get("compat"), "engine_path"):
    _c = type(sys)("compat")
    _c.__file__ = str(_ENG / "compat.py")
    exec(compile((_ENG / "compat.py").read_bytes(), _c.__file__, "exec", dont_inherit=True), _c.__dict__)
    sys.modules["compat"] = _c
sys.modules["compat"].engine_path(_ENG)
import aliases as A  # noqa: E402


def run(*arg):
    sys.exit(subprocess.run([sys.executable, "-I", "-B", str(ENGINE), "--swarm", str(SWARM), *arg]).returncode)


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
