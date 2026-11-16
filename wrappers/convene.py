#!/usr/bin/env python3
"""swarmer 5.0: the usual command, swarmer/convene.py. The code is in swarmer/engine/convene.py."""
import runpy
import sys
from pathlib import Path

m = Path(__file__).resolve().parent / "engine" / "convene.py"
sys.argv[0] = str(m)
runpy.run_path(str(m), run_name="__main__")
