#!/usr/bin/env python3
"""Sciame 4.0: il comando di sempre, `python3 -I sciame/genera_agenti.py`, con le opzioni della 3.x.

    python3 -I sciame/genera_agenti.py                    # rigenera tutto nel progetto
    python3 -I sciame/genera_agenti.py --controlla        # esce con 1 se qualcosa non è allineato alle fonti
    python3 -I sciame/genera_agenti.py --installa RADICE  # installa lo sciame in un altro progetto
    python3 -I sciame/genera_agenti.py --istruzioni       # il paragrafo dello sciame in CLAUDE.md
    python3 -I sciame/genera_agenti.py --togli-istruzioni
    python3 -I sciame/genera_agenti.py --togli            # toglie agenti e skill generati
    python3 -I sciame/genera_agenti.py --elenco           # i ruoli
Il lavoro lo fa sciame/motore/sciame.py.
"""
import subprocess
import sys
from pathlib import Path

QUI = Path(__file__).resolve().parent
SCIAME = QUI.parent if QUI.name == "motore" else QUI
MOTORE = SCIAME / "motore" / "sciame.py"


def lancia(*arg):
    sys.exit(subprocess.run([sys.executable, "-I", str(MOTORE), "--sciame", str(SCIAME), *arg]).returncode)


a = sys.argv[1:]
if not a:
    lancia("rigenera")
elif a[0] == "--controlla":
    lancia("controlla")
elif a[0] == "--installa" and len(a) == 2:
    lancia("installa", "--da", str(SCIAME), "--radice", a[1])
elif a[0] == "--istruzioni":
    lancia("istruzioni")
elif a[0] == "--togli-istruzioni":
    lancia("istruzioni", "--togli")
elif a[0] == "--togli":
    lancia("rimuovi")
elif a[0] == "--elenco":
    lancia("professionisti")
else:
    print(__doc__)
    sys.exit(2)
