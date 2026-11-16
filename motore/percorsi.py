#!/usr/bin/env python3
"""Sciame 4.0: percorsi, scritture sicure, cartella locale, note dei file generati e controlli del materiale pubblico.

Un modulo solo, usato dal generatore e dalla riga di comando, perché le regole siano le stesse ovunque:
- nessuna scrittura segue un collegamento simbolico, e ogni file si scrive con un temporaneo e una sostituzione;
- la cartella dello sciame è dentro la radice del progetto e diversa da lei;
- la cartella locale (gli override) è una sola, quella della configurazione;
- un file è «generato dallo sciame» solo se porta la nota nel posto esatto;
- il materiale pubblico non contiene segreti, indirizzi email, percorsi della macchina, parole vietate dal progetto
  (anche scritte in modo diverso) né i segni con cui sciame.sh separa i file.
Solo libreria standard.
"""
from __future__ import annotations

import html
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path

GENERATO = "sciame-4 GENERATO"
SEGNO_FILE = "#==== sciame.sh:"
FINE_FILE = "SCIAME_FINE_DEI_FILE"


class Errore(Exception):
    pass


# --- scritture ---

def senza_collegamenti(base: Path, percorso: Path) -> Path:
    """Il percorso, se sta dentro `base` e nessun suo componente da `base` in giù è un collegamento simbolico."""
    base = Path(base)
    percorso = Path(percorso)
    try:
        rel = percorso.relative_to(base)
    except ValueError:
        raise Errore(f"{percorso} non sta dentro {base}")
    if ".." in rel.parts:
        raise Errore(f"{percorso}: «..» non è ammesso")
    corrente = base
    for parte in rel.parts:
        corrente = corrente / parte
        if corrente.is_symlink():
            raise Errore(f"{corrente} è un collegamento simbolico: non lo seguo")
    return percorso


def scrivi(base: Path, percorso: Path, dati, modo: int | None = None) -> None:
    """Scrive testo o byte in `percorso` (dentro `base`), senza seguire collegamenti, con un temporaneo e os.replace."""
    percorso = senza_collegamenti(base, percorso)
    senza_collegamenti(base, percorso.parent)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    senza_collegamenti(base, percorso.parent)
    b = dati.encode("utf-8") if isinstance(dati, str) else dati
    if modo is None and percorso.is_file():
        modo = percorso.stat().st_mode & 0o7777   # un file che esiste tiene i suoi permessi
    elif modo is None:
        modo = 0o666 & ~_umask()
    fd, tmp = tempfile.mkstemp(dir=str(percorso.parent), prefix=".sciame-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(b)
        if modo is not None:
            os.chmod(tmp, modo)
        os.replace(tmp, percorso)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _umask() -> int:
    m = os.umask(0)
    os.umask(m)
    return m


def nessun_collegamento(base: Path, ignora=frozenset()) -> None:
    """Nessun collegamento simbolico sotto `base` (una sorgente da distribuire o una copia da provare), fuori dalle
    cartelle e dai file di `ignora`, che non si distribuiscono né si copiano."""
    base = Path(base)
    if base.is_symlink():
        raise Errore(f"{base} è un collegamento simbolico")
    for radice, cartelle, file in os.walk(base, followlinks=False):
        cartelle[:] = [c for c in cartelle if c not in ignora]
        for n in cartelle + [f for f in file if f not in ignora]:
            p = Path(radice) / n
            if p.is_symlink():
                raise Errore(f"{p} è un collegamento simbolico: non lo distribuisco né lo seguo")


def togli(base: Path, percorso: Path) -> None:
    percorso = senza_collegamenti(base, percorso)
    percorso.unlink()


# --- cartelle ---

def cartella_valida(radice: Path, cartella: str) -> Path:
    """La cartella dello sciame: relativa, senza «..», dentro la radice e diversa da lei; le barre doppie o finali si
    tolgono."""
    if os.path.isabs(str(cartella)):
        raise Errore(f"--cartella «{cartella}»: serve un percorso relativo dentro il progetto")
    cartella = "/".join(x for x in str(cartella).split("/") if x not in ("",))
    if not cartella or os.path.isabs(cartella) or ".." in Path(cartella).parts or Path(cartella) in (Path("."), Path("")):
        raise Errore(f"--cartella «{cartella}»: serve un percorso relativo dentro il progetto, senza «..», diverso da «.»")
    radice = Path(radice).resolve()
    s = (radice / cartella)
    senza_collegamenti(radice, s) if s.exists() else None
    if s.resolve() == radice or radice not in s.resolve().parents:
        raise Errore(f"--cartella «{cartella}» non sta dentro {radice}")
    return s


def config(radice: Path) -> dict:
    p = Path(radice) / ".sciame" / "config.json"
    if p.is_symlink():
        raise Errore(f"{p} è un collegamento simbolico")
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def cartella_locale(radice: Path, sciame: Path) -> Path:
    """La cartella degli override locali: quella di config.json («locale», relativa alla radice), altrimenti
    <sciame>/locale. Se la configurazione indica un file AGENTI.md, la cartella è quella che lo contiene."""
    cfg = config(radice)
    loc = cfg.get("locale")
    if loc:
        p = Path(loc)
        if p.is_absolute() or ".." in p.parts:
            raise Errore(f"locale «{loc}»: serve un percorso relativo dentro il progetto")
        p = Path(radice) / p
        return p.parent if p.suffix == ".md" else p
    return Path(sciame) / "locale"


def file_agenti_locale(radice: Path, sciame: Path) -> Path:
    cfg = config(radice)
    loc = cfg.get("locale")
    if loc and Path(loc).suffix == ".md":
        return Path(radice) / loc
    return cartella_locale(radice, sciame) / "AGENTI.md"


def vietate(radice: Path, sciame: Path) -> tuple[list[str], bool]:
    """Le parole vietate dal progetto e se c'è un elenco: VIETATE.txt nella cartella locale configurata, in
    <sciame>/locale, e i file di SCIAME_VIETATE. Mai distribuito."""
    candidati = [cartella_locale(radice, sciame) / "VIETATE.txt", Path(sciame) / "locale" / "VIETATE.txt"]
    candidati += [Path(x) for x in os.environ.get("SCIAME_VIETATE", "").split(os.pathsep) if x]
    out, trovato = [], False
    for p in dict.fromkeys(candidati):
        if p.is_file():
            trovato = True
            out += [r.strip() for r in p.read_text(encoding="utf-8").splitlines() if r.strip() and not r.startswith("#")]
    return out, trovato


def ha_override(radice: Path, sciame: Path) -> bool:
    f = file_agenti_locale(radice, sciame)
    return f.is_file() and "— `sciame-" in f.read_text(encoding="utf-8")


# --- la nota dei file generati ---

def nota(testo_nota: str) -> str:
    return f"<!-- {GENERATO}: {testo_nota} -->"


def generato(p: Path) -> bool:
    """Vero solo se la nota GENERATO sta nel posto esatto: la prima riga dopo la testa YAML (agenti e skill), o la
    prima riga (documenti). Una nota altrove, per esempio dentro un «in breve», non conta."""
    try:
        if not p.is_file() or p.is_symlink():
            return False
        righe = p.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return False
    i = 0
    if righe and righe[0] == "---":
        try:
            i = righe.index("---", 1) + 1
        except ValueError:
            return False
        while i < len(righe) and not righe[i].strip():
            i += 1
    return i < len(righe) and righe[i].startswith(f"<!-- {GENERATO}:")


# --- il materiale pubblico ---

SEGRETI = [re.compile(x) for x in (
    r"gh[opusr]_[A-Za-z0-9]{30,}", r"github_pat_[A-Za-z0-9_]{40,}", r"sk-[A-Za-z0-9_-]{20,}", r"hf_[A-Za-z0-9]{30,}",
    r"rpa_[A-Za-z0-9]{20,}", r"AKIA[0-9A-Z]{16}", r"xox[abpr]-[A-Za-z0-9-]{10,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"\s]{12,}['\"]")]
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@(?!example\.(?:com|org)\b)[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PERCORSO = re.compile(r"(/home/(?!<)[A-Za-z_][A-Za-z0-9._-]*/|/Users/(?!<)[A-Za-z0-9._-]+/|/r[o]ot/|[A-Za-z]:\\+Users\\+|/tmp/claude-\d+)")
NOME_FILE = re.compile(r"^(?!(?:.*/)?\.\.?(?:/|$))[A-Za-z0-9_.][A-Za-z0-9_.-]*(?:/(?!\.\.?(?:/|$))[A-Za-z0-9_.][A-Za-z0-9_.-]*)*$")
ZERO = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)


def normalizza(t: str) -> str:
    """Per il confronto con le parole vietate: entità e \\uXXXX decodificate, NFKC, senza segni diacritici staccati né
    caratteri invisibili, spazi e a capo compressi, minuscolo."""
    t = html.unescape(t)
    t = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), t)
    t = unicodedata.normalize("NFKC", t).translate(ZERO)
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).lower()


def problemi_pubblici(testo: str, parole: list[str]) -> list[str]:
    out = [f"possibile segreto: {rx.pattern}" for rx in SEGRETI if rx.search(testo)]
    out += [f"indirizzo email: {m.group(0).split('@')[0][:2]}…@…" for m in EMAIL.finditer(testo)][:1]
    out += [f"percorso della macchina: {m.group(0)[:14]}…" for m in PERCORSO.finditer(testo)][:1]
    forme = (normalizza(testo), normalizza(re.sub(r"\\[nrtbf]", " ", testo)))  # anche con gli escape del JSON come spazi
    out += [f"parola vietata dal progetto (VIETATE.txt), voce n. {i + 1}" for i, w in enumerate(parole)
            if normalizza(w) and any(normalizza(w) in n for n in forme)]
    for k, riga in enumerate(testo.splitlines(), 1):
        if riga.startswith(SEGNO_FILE) or riga.strip() == FINE_FILE:
            out.append(f"riga {k}: un segno di sciame.sh dentro un file")
            break
    return out
