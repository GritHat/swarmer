#!/usr/bin/env python3
"""Sciame 4.0: il comando di sempre, sciame/giuria.py. Il codice è in sciame/motore/giuria.py."""
import runpy
import sys
from pathlib import Path

m = Path(__file__).resolve().parent / "motore" / "giuria.py"
sys.argv[0] = str(m)
runpy.run_path(str(m), run_name="__main__")
