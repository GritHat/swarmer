#!/usr/bin/env python3
"""Sciame 4.0: il comando di sempre, sciame/convoca.py. Il codice è in sciame/motore/convoca.py."""
import runpy
import sys
from pathlib import Path

m = Path(__file__).resolve().parent / "motore" / "convoca.py"
sys.argv[0] = str(m)
runpy.run_path(str(m), run_name="__main__")
