#!/usr/bin/env python3
"""Sciame 4.0: la riga di comando. Di norma la lancia `bash sciame/sciame.sh <comando>`; `aiuto` dice tutto.

Solo libreria standard. Non lancia agenti: avvia Claude Code con la skill della strategia, oppure prepara, conta e
controlla. Le azioni verso l'esterno (una pull request) le fa solo su comando esplicito e confermato, e mai con i file
locali. Nessuna scrittura segue un collegamento simbolico, e nessun file del progetto che non sia dello sciame si
sovrascrive (percorsi.py).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

QUI = Path(__file__).resolve().parent          # <sciame>/motore
SCIAME = QUI.parent                            # la cartella dello sciame nel progetto (o il repository)
sys.path.insert(0, str(QUI))
import genera as G  # noqa: E402
import percorsi as S  # noqa: E402
import professionisti as P  # noqa: E402

DISTRIBUITI = ("motore", "db", "documenti", "i18n", "involucri", "prove")  # ciò che sciame.sh porta con sé
# Ciò che non si pubblica mai, e la cui presenza impedisce di pubblicare (verifica --pubblicazione).
NON_PUBBLICARE = ("_lavoro", "_v31", "locale", "proposte", "RICHIESTE_ESPERTI.md", ".sciame")
SIGLA_ARG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


class Errore(Exception):
    pass


# --- Il progetto e la configurazione ---

def radice_di(sciame: Path) -> Path:
    """La radice del progetto: dal file RADICE (la via relativa, scritta all'installazione), altrimenti la cartella
    che contiene quella dello sciame."""
    p = sciame / "RADICE"
    if p.is_file():
        return (sciame / p.read_text(encoding="utf-8").strip()).resolve()
    return sciame.parent


def installato(sciame: Path) -> bool:
    return (sciame / "RADICE").is_file() and (sciame / "FABBRICA.json").is_file()


def serve_installato(sciame: Path) -> None:
    if not installato(sciame):
        raise Errore(f"{sciame} non è uno sciame installato (mancano RADICE e FABBRICA.json): bash sciame.sh installa")


def lingua(sciame: Path) -> str:
    if os.environ.get("SCIAME_LINGUA"):
        return os.environ["SCIAME_LINGUA"]
    p = sciame / "LINGUA"
    return p.read_text(encoding="utf-8").strip() if p.is_file() and not p.is_symlink() else "it"


def msg(sciame: Path, chiave: str, **kw) -> str:
    return G.i18n(sciame, lingua(sciame)).get(chiave, chiave).format(**kw)


def leggi_config(radice: Path) -> dict:
    return S.config(radice)


def scrivi_config(radice: Path, cfg: dict) -> None:
    S.scrivi(radice, radice / ".sciame" / "config.json", json.dumps(cfg, ensure_ascii=False, indent=1) + "\n")


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def file_di_fabbrica(da: Path) -> list[str]:
    """I file distribuiti di una sorgente: le cartelle DISTRIBUITI, senza __pycache__, .nuovo e nascosti. Un
    collegamento simbolico o un nome di file fuori dalla forma ammessa (spazi, a capo, «..») ferma tutto."""
    out = []
    for nome in DISTRIBUITI:
        base = da / nome
        if base.is_symlink():
            raise Errore(f"{base} è un collegamento simbolico: non lo distribuisco")
        if base.is_dir():
            S.nessun_collegamento(base)
            for q in sorted(base.rglob("*")):
                if not q.is_file() or "__pycache__" in q.parts or q.name.endswith(".nuovo") or q.name.startswith("."):
                    continue
                rel = q.relative_to(da).as_posix()
                if not S.NOME_FILE.match(rel):
                    raise Errore(f"nome di file non ammesso in una sorgente da distribuire: {rel!r}")
                out.append(rel)
    return out


def file_da_distribuire(sciame: Path) -> list[str]:
    """Nel repository, tutti i file distribuiti. In uno sciame installato, solo quelli della fabbrica (FABBRICA.json):
    un file aggiunto dal progetto sotto documenti/, prove/ o motore/ non esce."""
    tutti = file_di_fabbrica(sciame)
    if not installato(sciame):
        return tutti
    fab = json.loads((sciame / "FABBRICA.json").read_text(encoding="utf-8"))
    # solo i file di fabbrica; uno ritoccato nel progetto esce nella versione di fabbrica (contenuto_distribuito)
    return [r for r in tutti if r in fab]


def originali(sciame: Path) -> dict[str, str]:
    """I file di fabbrica come stanno nel sciame.sh installato: la fonte della versione da distribuire di un file che il
    progetto ha ritoccato."""
    sh = sciame / "sciame.sh"
    out, nome, buf = {}, None, []
    if not sh.is_file():
        return out
    for riga in sh.read_text(encoding="utf-8").splitlines(keepends=True):
        if riga.startswith(S.SEGNO_FILE + " file ") and riga.rstrip("\n").endswith(" ===="):
            if nome:
                out[nome] = "".join(buf)
            nome, buf = riga[len(S.SEGNO_FILE + " file "):].rstrip("\n")[:-len(" ====")], []
        elif riga.startswith(S.SEGNO_FILE + " fine dei file"):
            if nome:
                out[nome] = "".join(buf)
            nome = None
        elif nome:
            buf.append(riga)
    return out


def contenuto_distribuito(sciame: Path, rel: str, cache: dict) -> str:
    """Il testo con cui un file esce: quello su disco se è identico alla fabbrica (o se non è un'installazione), altrimenti
    la versione di fabbrica dal sciame.sh installato. Un file ritoccato nel progetto non esce mai."""
    testo = (sciame / rel).read_text(encoding="utf-8")
    if not installato(sciame):
        return testo
    fab = cache.setdefault("fab", json.loads((sciame / "FABBRICA.json").read_text(encoding="utf-8")))
    if hashlib.sha256(testo.encode("utf-8")).hexdigest() == fab.get(rel):
        return testo
    orig = cache.setdefault("orig", originali(sciame)).get(rel)
    if orig is None or hashlib.sha256(orig.encode("utf-8")).hexdigest() != fab.get(rel):
        raise Errore(f"{rel} è stato ritoccato nel progetto e la sua versione di fabbrica non si ritrova: ripristinalo "
                     "o costruisci dal repository")
    return orig


# --- Generazione ---

def rigenera(sciame: Path, sostituibili=frozenset()) -> tuple[dict, list[str]]:
    serve_installato(sciame)
    radice = radice_di(sciame)
    dati = G.catalogo(sciame, radice, lingua(sciame))
    return dati, G.scrivi(sciame, radice, dati, sostituibili)


def controlla(sciame: Path) -> int:
    serve_installato(sciame)
    radice = radice_di(sciame)
    print(f"python3: {sys.version.split()[0]}")
    if shutil.which("claude"):
        r = subprocess.run(["claude", "--version"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        print("claude: " + ((r.stdout.strip().splitlines() or ["?"])[0]))
    else:
        print("claude: manca / missing (avviso: serve per avviare le convocazioni / warning: needed to convene)")
    try:
        dati = G.catalogo(sciame, radice, lingua(sciame))
        diversi = G.controlla(sciame, radice, dati)
    except (G.Errore, P.Errore, S.Errore) as e:
        print(f"sciame: {e}")
        return 1
    if diversi:
        print("\n".join(diversi))
        print(msg(sciame, "cli_non_allineato"))
        return 1
    print(msg(sciame, "cli_allineato", ruoli=len(dati["ruoli"]), profili=len(dati["profili"])))
    return 0


# --- Installazione e aggiornamento, con i file protetti ---

def installa(da: Path, radice: Path, cartella: str, lingua_scelta: str | None, forza: bool, locale: str | None,
             gestiti: bool) -> Path:
    """Copia i file di fabbrica da `da` in <radice>/<cartella>.
    - Una cartella che esiste e non è uno sciame (né FABBRICA.json né VERSIONE 3.x o 4.x) si rifiuta, salvo --forza, che
      prima ne fa una copia di sicurezza.
    - Un file che esiste e differisce da quello di fabbrica registrato, o che non è registrato, non si sovrascrive: la
      versione nuova va accanto con il suffisso .nuovo (salvo il database, che si unisce).
    - Nessuna scrittura segue un collegamento simbolico."""
    radice = radice.resolve()
    sciame = S.cartella_valida(radice, cartella)
    cartella = sciame.relative_to(radice).as_posix()   # la forma normalizzata, quella che legge testa.sh
    if locale:
        lp = Path(locale)
        if lp.is_absolute() or ".." in lp.parts:
            raise Errore(f"--locale «{locale}»: serve un percorso relativo dentro il progetto")
    versione = (sciame / "VERSIONE").read_text(encoding="utf-8") if (sciame / "VERSIONE").is_file() else ""
    sciame_noto = (sciame / "FABBRICA.json").is_file() or versione.startswith("3.")
    if sciame.exists() and any(sciame.iterdir()) and not sciame_noto and not forza:
        raise Errore(f"{sciame} esiste e non è uno sciame: non lo tocco. Scegli un'altra --cartella (per esempio "
                     f"{cartella}/skill, con --locale {cartella} se contiene schede proprie) o usa --forza, che ne fa "
                     "prima una copia di sicurezza")
    if sciame.exists() and any(sciame.iterdir()) and ((forza and not sciame_noto) or versione.startswith("3.")):
        copia = radice / f"{cartella.replace('/', '_')}.prima-{datetime.datetime.now():%Y%m%d-%H%M%S}"
        shutil.copytree(sciame, copia, symlinks=True)
        print(f"copia di sicurezza / backup: {copia}")
    sost = G.sostituibili_31(sciame, radice) if versione.startswith("3.") else frozenset()
    sciame.mkdir(parents=True, exist_ok=True)
    S.senza_collegamenti(radice, sciame)
    fab_p = sciame / "FABBRICA.json"
    fabbrica = json.loads(fab_p.read_text(encoding="utf-8")) if fab_p.is_file() else {}
    sorgenti = [(rel, da / rel) for rel in file_di_fabbrica(da)]
    sorgenti += [(n, da / "involucri" / n) for n in ("convoca.py", "giuria.py") if (da / "involucri" / n).is_file()]
    sorgenti.append(("genera_agenti.py", da / "motore" / "genera_agenti.py"))
    if (da / "sciame.sh").is_file():
        sorgenti.append(("sciame.sh", da / "sciame.sh"))
    if (da / "UPSTREAM").is_file():
        sorgenti.append(("UPSTREAM", da / "UPSTREAM"))
    protetti, scritti = [], 0
    for rel, src in sorgenti:
        dst = sciame / rel
        S.senza_collegamenti(sciame, dst)
        nuovo = src.read_bytes()
        h = hashlib.sha256(nuovo).hexdigest()
        if dst.is_file():
            attuale = sha_file(dst)
            if attuale == h:
                fabbrica[rel] = h
                continue
            if rel == "db/professionisti.json" and rel in fabbrica:
                # il database si unisce sempre: le voci approvate nel progetto restano, quelle nuove di fabbrica entrano
                unisci_db(sciame, dst, src)
                fabbrica[rel] = sha_file(dst)
                continue
            v31 = versione.startswith("3.") and f"sciame/{rel}" in sost
            cambiato_nel_progetto = rel not in fabbrica or attuale != fabbrica[rel]
            if cambiato_nel_progetto and not v31 and not (forza and not sciame_noto):
                S.scrivi(sciame, dst.parent / (dst.name + ".nuovo"), nuovo)
                fabbrica[rel] = h        # la fabbrica nuova è quella del sciame.sh nuovo: il file resta del progetto
                protetti.append(rel)
                continue
        S.scrivi(sciame, dst, nuovo, 0o755 if rel.endswith(".sh") else None)
        fabbrica[rel] = h
        scritti += 1
    l = lingua_scelta or "it"
    if not (sciame / "RICHIESTE_ESPERTI.md").exists() and (da / "documenti" / l / "_RICHIESTE_ESPERTI.md").is_file():
        S.scrivi(sciame, sciame / "RICHIESTE_ESPERTI.md", (da / "documenti" / l / "_RICHIESTE_ESPERTI.md").read_bytes())
    if not (sciame / "locale" / "LEGGIMI.md").exists() and (da / "documenti" / l / "_LOCALE.md").is_file():
        S.scrivi(sciame, sciame / "locale" / "LEGGIMI.md", (da / "documenti" / l / "_LOCALE.md").read_bytes())
    if not (sciame / "locale" / "VIETATE.txt").exists():
        S.scrivi(sciame, sciame / "locale" / "VIETATE.txt",
                 "# Una parola o un'espressione per riga che non deve mai uscire dal progetto.\n"
                 "# One word or phrase per line that must never leave the project.\n")
    if lingua_scelta:
        if lingua_scelta not in G.lingue_disponibili(sciame):
            raise Errore(msg(sciame, "cli_lingua_sconosciuta", lingua=lingua_scelta,
                             lingue=", ".join(G.lingue_disponibili(sciame))))
        S.scrivi(sciame, sciame / "LINGUA", lingua_scelta + "\n")
    elif not (sciame / "LINGUA").exists():
        S.scrivi(sciame, sciame / "LINGUA", "it\n")
    cfg = leggi_config(radice)
    if locale:
        cfg["locale"] = locale
    if gestiti:
        cfg["gestiti_dal_progetto"] = True
    if cartella != "sciame" or "cartella" in cfg:
        cfg["cartella"] = cartella
    if cfg:
        scrivi_config(radice, cfg)
    S.scrivi(sciame, fab_p, json.dumps(fabbrica, indent=1, sort_keys=True) + "\n")
    S.scrivi(sciame, sciame / "RADICE", os.path.relpath(radice, sciame) + "\n")
    dati, fatti = rigenera(sciame, sost)
    saltati = [f for f in fatti if f.startswith("saltato")]
    print(msg(sciame, "cli_installato", versione=G.VERSIONE, radice=radice, lingua=dati["lingua"],
              agenti=sum(1 for f in fatti if f.startswith(".claude/agents/")),
              skill=sum(1 for f in fatti if f.startswith(".claude/skills/"))))
    if saltati:
        print(msg(sciame, "cli_saltati", n=len(saltati)))
    if protetti:
        print(msg(sciame, "cli_aggiornato", n=scritti, protetti=", ".join(protetti)))
    return sciame


def unisci_db(sciame: Path, locale: Path, nuovo: Path) -> None:
    """Unisce il database del progetto con quello nuovo di fabbrica: le voci nuove di fabbrica si aggiungono, quelle
    aggiunte nel progetto restano; per una sigla presente in tutti e due resta la versione del progetto, e una lingua
    nuova di fabbrica si aggiunge."""
    a = json.loads(locale.read_text(encoding="utf-8"))
    b = json.loads(nuovo.read_text(encoding="utf-8"))
    sigle = {v["sigla"] for v in a["voci"]}
    for v in b["voci"]:
        if v["sigla"] not in sigle:
            a["voci"].append(v)
        else:
            vecchia = next(x for x in a["voci"] if x["sigla"] == v["sigla"])
            for l, t in v.get("testi", {}).items():
                vecchia.setdefault("testi", {}).setdefault(l, t)
    S.scrivi(sciame, locale, json.dumps(a, ensure_ascii=False, indent=1) + "\n")


# --- Avvio di una convocazione ---

def avvia(sciame: Path, strategia: str, ns) -> None:
    serve_installato(sciame)
    richiesta = ns.richiesta or ""
    if ns.da_file:
        richiesta = Path(ns.da_file).read_text(encoding="utf-8")
    if not richiesta.strip():
        raise Errore(msg(sciame, "cli_manca_richiesta", strategia=strategia))
    cat = json.loads((sciame / "catalogo.json").read_text(encoding="utf-8"))
    if ns.profilo and ns.profilo not in cat["profili"]:
        raise Errore(msg(sciame, "cli_profilo_sconosciuto", profilo=ns.profilo, profili=", ".join(cat["profili"])))
    sigle = {r["sigla"] for r in cat["ruoli"]}
    ruoli = [r.strip()[len("sciame-"):] if r.strip().startswith("sciame-") else r.strip()
             for r in (ns.ruoli or "").split(",") if r.strip()]
    for r in ruoli:
        if r not in sigle:
            raise Errore(msg(sciame, "cli_ruolo_sconosciuto", ruolo=r))
    if ns.lingua and ns.lingua not in G.lingue_disponibili(sciame):
        raise Errore(msg(sciame, "cli_lingua_sconosciuta", lingua=ns.lingua, lingue=", ".join(G.lingue_disponibili(sciame))))
    skill = G.SKILL[strategia]
    radice = radice_di(sciame)
    if not (radice / ".claude" / "skills" / skill / "SKILL.md").is_file():
        raise Errore(f"manca la skill {skill}: bash sciame/sciame.sh rigenera")
    testo = f"/{skill}" + (f" profilo={ns.profilo}" if ns.profilo else "") + (f" ruoli={','.join(ruoli)}" if ruoli else "") \
        + (f" lingua={ns.lingua}" if ns.lingua else "") + f" {richiesta}"
    comando = ["claude"] + (["--model", ns.modello] if ns.modello else []) + (["-p"] if ns.stampa else []) + [testo] + ns.resto
    if ns.mostra:
        import shlex
        print(f"cd {shlex.quote(str(radice))} && " + " ".join(shlex.quote(x) for x in comando))
        return
    if not shutil.which("claude"):
        raise Errore(msg(sciame, "cli_manca_claude"))
    os.chdir(radice)
    os.execvp("claude", comando)


# --- Professionisti nuovi: approvazione e proposta al repository ---

def vietate(sciame: Path) -> list[str]:
    return S.vietate(radice_di(sciame), sciame)[0]


def problemi_pubblici(testo: str, parole: list[str]) -> list[str]:
    return S.problemi_pubblici(testo, parole)


def sigle_locali(sciame: Path) -> set[str]:
    radice = radice_di(sciame)
    return set(P.schede_locali(S.file_agenti_locale(radice, sciame))) if installato(sciame) else set()


def serve_vietate(sciame: Path) -> list[str]:
    """In un progetto con override locali, prima di produrre materiale pubblico serve un VIETATE.txt (anche vuoto,
    purché esista): è la dichiarazione che il progetto ha pensato a che cosa non deve uscire."""
    radice = radice_di(sciame)
    parole, _ = S.vietate(radice, sciame)
    trovato = (S.cartella_locale(radice, sciame) / "VIETATE.txt").is_file()
    if installato(sciame) and S.ha_override(radice, sciame) and not trovato:
        raise Errore(f"il progetto ha override locali ma nessun VIETATE.txt in {S.cartella_locale(radice, sciame)}: "
                     "scrivilo prima di approvare, proporre o costruire")
    return parole


def identita_git() -> tuple[str, str]:
    """L'identità con cui proponi firma il commit: quella globale, letta fuori da ogni repository; il commit la usa con
    -c, quindi la configurazione locale del progetto non conta."""
    with tempfile.TemporaryDirectory() as vuota:
        leggi = lambda k: subprocess.run(["git", "config", "--global", "--get", k], capture_output=True, text=True,
                                         cwd=vuota, stdin=subprocess.DEVNULL).stdout.strip()
        return leggi("user.name"), leggi("user.email")


def albero_pubblico(base: Path) -> list[str]:
    """I file che il repository pubblicherebbe. Con .git: `git ls-files -co --exclude-standard` (le regole complete di
    .gitignore e i file già tracciati). Senza: le cartelle DISTRIBUITI per intero (salvo __pycache__, .pyc, .nuovo) e il
    resto meno ciò che .gitignore esclude per nome. Un collegamento simbolico fra i file pubblicati ferma tutto."""
    base = Path(base)
    if (base / ".git").exists():
        p = subprocess.run(["git", "-C", str(base), "ls-files", "-co", "--exclude-standard", "-z"], capture_output=True,
                           stdin=subprocess.DEVNULL, check=True)
        rels = {r for r in p.stdout.decode("utf-8").split("\0") if r}
        # ciò che costruisci distribuisce si esamina e si copia comunque, anche se .gitignore lo esclude
        rels |= set(file_di_fabbrica(base)) | {x for x in ("UPSTREAM", "sciame.sh") if (base / x).is_file()}
        rels = sorted(rels)
    else:
        ign = {".git", "__pycache__"} | set(NON_PUBBLICARE) | ignorati(base)
        ign_file = {".git", "__pycache__"} | set(NON_PUBBLICARE) | ignorati(base, solo_file=True)
        rels = []
        for radice_w, cartelle, file in os.walk(base, followlinks=False):
            d = Path(radice_w)
            dentro = d != base and d.relative_to(base).parts[0] in DISTRIBUITI
            for c in list(cartelle):
                if (d / c).is_symlink():
                    raise Errore(f"{(d / c).relative_to(base)} è un collegamento simbolico: non lo pubblico")
            cartelle[:] = [c for c in cartelle if c not in ("__pycache__", ".git")
                           and (dentro or (d == base and c in DISTRIBUITI) or c not in ign)]
            for n in file:
                if n.endswith((".pyc", ".nuovo")) or (not dentro and n in ign_file):
                    continue
                rels.append((d / n).relative_to(base).as_posix())
        rels.sort()
    for r in rels:
        S.senza_collegamenti(base, base / r)
    return rels


def ignorati(base: Path, solo_file: bool = False) -> set[str]:
    """Le cartelle e i file che .gitignore esclude per nome (senza «*»): non si pubblicano, quindi non si esaminano."""
    gi = Path(base) / ".gitignore"
    if not gi.is_file():
        return set()
    righe = [r.rstrip() for r in gi.read_text(encoding="utf-8").splitlines()
             if r.strip() and not r.startswith(("#", " ", "\t"))]   # uno spazio iniziale fa parte del nome: non la applico
    if any(r.startswith("!") for r in righe):
        raise Errore(".gitignore ha una negazione «!»: senza .git non so che cosa si pubblica; fai git init e ripeti")
    # solo i nomi semplici (con al più la «/» finale): un'ancora, un percorso o un modello non si applicano, così si
    # esamina di più, mai di meno
    nomi = [r for r in righe if not any(c in r.rstrip("/") for c in "/*?[\\")]
    # «nome/» vale solo per le cartelle: con solo_file restano i nomi senza la «/» finale
    return {r.rstrip("/") for r in nomi if not (solo_file and r.endswith("/"))}


def problemi_nome(rel: str, parole: list[str]) -> list[str]:
    """Il percorso di un file, così com'è e con «-», «_», «.», «/» come spazi (per le voci di più parole)."""
    return sorted(set(problemi_pubblici(rel, parole) + problemi_pubblici(re.sub(r"[-_./]", " ", rel), parole)))


def stringhe(x) -> list[str]:
    """Tutte le stringhe di una voce, a ogni profondità, chiavi comprese."""
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [s for k, v in x.items() for s in stringhe(k) + stringhe(v)]
    if isinstance(x, list):
        return [s for v in x for s in stringhe(v)]
    return []


def frasi(testo: str, n: int = 10) -> set[str]:
    parole = re.findall(r"\w+", S.normalizza(testo))
    return {" ".join(parole[i:i + n]) for i in range(max(0, len(parole) - n + 1))}


def frasi_locali(sciame: Path) -> set[str]:
    """Le sequenze di dieci parole dei file della cartella locale: un testo pubblico non ne deve contenere nessuna."""
    radice = radice_di(sciame)
    out = set()
    loc = S.cartella_locale(radice, sciame)
    file = [S.file_agenti_locale(radice, sciame)] + (sorted(loc.glob("*.md")) if loc.is_dir() else [])
    for f in dict.fromkeys(file):
        if f.is_file():
            out |= frasi(f.read_text(encoding="utf-8"))
    return out


def approva(sciame: Path, file: Path, ricostruisci: bool = True, generica_di_locale: bool = False) -> str:
    """Aggiunge voci nuove al database (dopo l'approvazione). Tutto si prova prima in una copia: se un controllo fallisce,
    il database, gli agenti e sciame.sh restano come erano."""
    serve_installato(sciame)
    voce = json.loads(Path(file).read_text(encoding="utf-8"))
    voci = voce if isinstance(voce, list) else [voce]
    d = P.carica(sciame / "db")
    lingue = G.lingue_disponibili(sciame)
    sigle = {v["sigla"] for v in d["voci"]}
    parole = serve_vietate(sciame)
    locali = sigle_locali(sciame)
    for v in voci:
        if not isinstance(v, dict) or not SIGLA_ARG.match(str(v.get("sigla", ""))):
            raise Errore("una voce senza una sigla valida")
        v.setdefault("versione", G.VERSIONE)
        v.setdefault("stato", "attivo")
        v.setdefault("genitore", None)
        if v["sigla"] in sigle:
            raise Errore(f"sciame-{v['sigla']} c'è già nel database")
        if v["sigla"] in locali and not generica_di_locale:
            raise Errore(f"sciame-{v['sigla']} è una scheda locale: nel database pubblico entra solo una sua versione "
                         "generica, senza dettagli del progetto, con --generica-di-locale")
        prob = problemi_pubblici(json.dumps(v, ensure_ascii=False), parole)
        comuni = frasi(" ".join(stringhe(v))) & frasi_locali(sciame)
        if comuni:
            prob.append(f"{len(comuni)} sequenze di dieci parole in comune con le schede locali (per esempio «{sorted(comuni)[0]}»)")
        if prob:
            raise Errore(f"sciame-{v['sigla']}: non può andare nel database pubblico: " + "; ".join(prob))
        d["voci"].append(v)
        sigle.add(v["sigla"])
    errori = P.valida(d, lingue)
    if errori:
        raise Errore("la voce non è valida:\n  " + "\n  ".join(errori[:20]))
    radice = radice_di(sciame)
    cfg = leggi_config(radice)
    copie = []
    for c in cfg.get("copie_sciame_sh", []) if ricostruisci else []:
        if Path(c).is_absolute() or ".." in Path(c).parts:
            raise Errore(f"copie_sciame_sh: «{c}» non è un percorso relativo dentro il progetto")
        copie.append(S.senza_collegamenti(radice, radice / c))
    rep = cfg.get("repository_locale") if ricostruisci else None
    if rep:
        rep = Path(rep) if Path(rep).is_absolute() else radice / rep
        dr = P.carica(rep / "db")
        nuove_rep = [v for v in voci if v["sigla"] not in {x["sigla"] for x in dr["voci"]}]
        dr["voci"] += nuove_rep
        err = P.valida(dr, G.lingue_disponibili(rep))
        if err:
            raise Errore(f"{rep}: la voce non è valida nel repository: " + "; ".join(err[:5]))
    S.nessun_collegamento(sciame)
    testo_db = json.dumps({"formato": 1, "voci": d["voci"]}, ensure_ascii=False, indent=1) + "\n"
    with tempfile.TemporaryDirectory() as tmp:  # la prova in copia di tutto ciò che si scriverà, con la radice vera
        prova = Path(tmp) / "s"
        shutil.copytree(sciame, prova, symlinks=False, ignore=shutil.ignore_patterns("__pycache__", "*.nuovo"))
        (prova / "RADICE").write_text(str(radice) + "\n", encoding="utf-8")
        (prova / "db" / "professionisti.json").write_text(testo_db, encoding="utf-8")
        fab_prova = json.loads((prova / "FABBRICA.json").read_text(encoding="utf-8"))
        fab_prova["db/professionisti.json"] = hashlib.sha256(testo_db.encode("utf-8")).hexdigest()
        (prova / "FABBRICA.json").write_text(json.dumps(fab_prova), encoding="utf-8")
        G.catalogo(prova, radice, lingua(sciame))
        if ricostruisci:
            costruisci(prova, Path(tmp) / "sciame.sh")
        if rep:
            prova_rep = Path(tmp) / "r"
            for r_ in albero_pubblico(rep):   # la copia di ciò che si pubblica, file per file, senza collegamenti
                (prova_rep / r_).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(rep / r_, prova_rep / r_, follow_symlinks=False)
            P.salva(dr, prova_rep / "db")
            costruisci(prova_rep, Path(tmp) / "rep.sh", parole_extra=parole)
    S.scrivi(sciame, sciame / "db" / "professionisti.json",
             json.dumps({"formato": 1, "voci": d["voci"]}, ensure_ascii=False, indent=1) + "\n")
    rigenera(sciame)
    for v in voci:
        S.scrivi(sciame, sciame / "proposte" / f"{v['sigla']}.json", json.dumps(v, ensure_ascii=False, indent=1) + "\n")
        chiudi_richieste(sciame, v["sigla"], d)
    uscita = "—"
    fab_p = sciame / "FABBRICA.json"
    fab = json.loads(fab_p.read_text(encoding="utf-8"))
    fab["db/professionisti.json"] = sha_file(sciame / "db" / "professionisti.json")  # cambiato per approvazione
    S.scrivi(sciame, fab_p, json.dumps(fab, indent=1, sort_keys=True) + "\n")   # prima di costruire: il db esce
    if ricostruisci:
        uscita = str(costruisci(sciame, sciame / "sciame.sh"))
        fab["sciame.sh"] = sha_file(sciame / "sciame.sh")
        for dest in copie:
            S.scrivi(radice, dest, (sciame / "sciame.sh").read_bytes(), 0o755)
            uscita += f", {dest}"
        if rep:
            S.scrivi(rep, rep / "db" / "professionisti.json",
                     json.dumps({"formato": 1, "voci": dr["voci"]}, ensure_ascii=False, indent=1) + "\n")
            costruisci(rep, rep / "sciame.sh", parole_extra=parole)
            uscita += f", {rep / 'sciame.sh'} (+{len(nuove_rep)} voci nel repository locale)"
    S.scrivi(sciame, fab_p, json.dumps(fab, indent=1, sort_keys=True) + "\n")
    return msg(sciame, "cli_approvato", sigla=",".join(v["sigla"] for v in voci), tipo=voci[0]["tipo"],
               sciame_sh=uscita, proposta=sciame / "proposte")


def chiudi_richieste(sciame: Path, sigla: str, d: dict) -> None:
    p = sciame / "RICHIESTE_ESPERTI.md"
    if not p.is_file():
        return
    t = p.read_text(encoding="utf-8")
    numero = next((v["numero"] for v in P.ordinate(d) if v["sigla"] == sigla), "?")
    riga = f"- `{sigla}`: creato, n. {numero} ({datetime.date.today().isoformat()})"
    if f"- `{sigla}`: creato" not in t:
        S.scrivi(sciame, p, t.rstrip("\n") + "\n" + riga + "\n")


def proponi(sciame: Path, sigle: list[str], esegui: bool, si: bool) -> str:
    """Prepara la pull request delle voci approvate al repository pubblico (UPSTREAM). Con --invia e --si la apre:
    clona UPSTREAM, aggiunge le voci al suo database, ricostruisce sciame.sh con il motore LOCALE (non con il codice
    scaricato), verifica il clone con le parole vietate del progetto, fa il fork, il push e la pull request."""
    serve_installato(sciame)
    upstream = (sciame / "UPSTREAM").read_text(encoding="utf-8").strip() if (sciame / "UPSTREAM").is_file() else ""
    l = lingua(sciame)
    voci = []
    for s in sigle:
        if not SIGLA_ARG.match(s):
            raise Errore(f"sigla non valida: {s}")
        p = sciame / "proposte" / f"{s}.json"
        if not p.is_file():
            raise Errore(f"manca {p}: prima bash sciame/sciame.sh approva <scheda>")
        voci.append(json.loads(p.read_text(encoding="utf-8")))
    parole = serve_vietate(sciame)
    for v in voci:
        prob = problemi_pubblici(json.dumps(v, ensure_ascii=False), parole)
        if prob:
            raise Errore(f"sciame-{v['sigla']}: " + "; ".join(prob))
    modello = sciame / "documenti" / l / "_PROPOSTA_PR.md"
    corpo = (modello.read_text(encoding="utf-8") if modello.is_file() else "{voci}").replace("{voci}", "\n".join(
        f"- `sciame-{v['sigla']}` ({v['tipo']}{', ' + v['genitore'] if v.get('genitore') else ''}): {P.testo(v, l)['nome']}"
        for v in voci))
    uscita = sciame / "proposte" / f"PR-{'-'.join(sigle)[:60]}.md"
    S.scrivi(sciame, uscita, corpo)
    riepilogo = (f"Pull request a {upstream or '<proprietario>/<repository>'} con {len(voci)} voci: "
                 + ", ".join(f"sciame-{v['sigla']}" for v in voci) + f". Testo: {uscita}")
    if not esegui:
        return riepilogo + "\n" + msg(sciame, "cli_proposta_scritta", percorso=uscita,
                                      comando="bash sciame/sciame.sh proponi " + " ".join(sigle) + " --invia --si")
    nome, mail = identita_git()
    if not si:
        return (riepilogo + f"\nIl commit sarà firmato come «{nome or '?'} <{mail or '?'}>», che diventa pubblico. "
                "Non inviata: ripeti con --si per confermare / Not sent: repeat with --si to confirm.")
    if not shutil.which("gh") or not re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", upstream):
        raise Errore("per inviare serve gh autenticato e sciame/UPSTREAM nella forma <proprietario>/<repository>")
    with tempfile.TemporaryDirectory() as tmp:
        r = Path(tmp) / "r"
        subprocess.run(["gh", "auth", "status"], check=True, stdin=subprocess.DEVNULL)
        subprocess.run(["gh", "repo", "clone", upstream, str(r)], check=True, stdin=subprocess.DEVNULL)
        S.nessun_collegamento(r)
        ramo = f"proposta-{'-'.join(sigle)[:40]}"
        subprocess.run(["git", "-C", str(r), "checkout", "-b", ramo], check=True)
        d = P.carica(r / "db")
        d["voci"] += [v for v in voci if v["sigla"] not in {x["sigla"] for x in d["voci"]}]
        err = P.valida(d, G.lingue_disponibili(r))
        if err:
            raise Errore("le voci non sono valide nel repository: " + "; ".join(err[:5]))
        P.salva(d, r / "db")
        costruisci(r, r / "sciame.sh", parole_extra=parole)
        errori = verifica(r, parole_extra=parole)
        if errori:
            raise Errore("il clone non passa la verifica: " + "; ".join(errori[:5]))
        if not nome or not mail:
            raise Errore("serve un'identità git globale (user.name e user.email): è quella che il commit pubblica")
        subprocess.run(["git", "-C", str(r), "add", "db/professionisti.json", "sciame.sh"], check=True)
        diff = subprocess.run(["git", "-C", str(r), "diff", "--cached", "--stat"], capture_output=True, text=True).stdout
        print(f"Invio a {upstream} come «{nome} <{mail}>»:\n{diff}")
        chi = {"GIT_AUTHOR_NAME": nome, "GIT_AUTHOR_EMAIL": mail, "GIT_COMMITTER_NAME": nome, "GIT_COMMITTER_EMAIL": mail}
        subprocess.run(["git", "-C", str(r), "commit", "-m", f"sciame: {', '.join(sigle)}"], check=True,
                       env=dict(os.environ, **chi))
        firmato = subprocess.run(["git", "-C", str(r), "log", "-1", "--format=%an <%ae>|%cn <%ce>"], capture_output=True,
                                 text=True, check=True).stdout.strip()
        if firmato != f"{nome} <{mail}>|{nome} <{mail}>":
            raise Errore(f"il commit è firmato «{firmato}», non «{nome} <{mail}>»: non lo invio")
        subprocess.run(["gh", "repo", "fork", "--remote", "--remote-name", "fork"], check=True, cwd=r, stdin=subprocess.DEVNULL)
        subprocess.run(["git", "-C", str(r), "push", "-u", "fork", ramo], check=True)
        subprocess.run(["gh", "pr", "create", "--repo", upstream, "--title", f"sciame: {', '.join(sigle)}",
                        "--body-file", str(uscita)], check=True, cwd=r, stdin=subprocess.DEVNULL)
    return f"pull request aperta su {upstream}"


# --- sciame.sh, un file solo ---

def costruisci(sciame: Path, uscita: Path, parole_extra: list[str] | None = None) -> Path:
    """Ricostruisce sciame.sh: la testa (motore/testa.sh) e i file distribuiti, in chiaro dopo la riga «exit». Prima
    controlla ogni file: niente segreti, email, percorsi della macchina, parole vietate, segni di sciame.sh."""
    cache = {}
    testa = contenuto_distribuito(sciame, "motore/testa.sh", cache)
    parti = [testa.rstrip("\n") + "\n", "exit\n",
             "# Da qui in giù ci sono i file dello sciame, che «installa» scrive in sciame/. Bash non arriva oltre «exit».\n",
             f": <<'{S.FINE_FILE}'\n"]
    if installato(sciame):
        parole = serve_vietate(sciame)
    else:
        parole = S.vietate(sciame, sciame)[0]
    parole = parole + list(parole_extra or [])
    distribuiti = file_da_distribuire(sciame) + (["UPSTREAM"] if (sciame / "UPSTREAM").is_file() else [])
    for rel in distribuiti:
        S.senza_collegamenti(sciame, sciame / rel)
        testo = contenuto_distribuito(sciame, rel, cache)
        prob = problemi_nome(rel, parole) + problemi_pubblici(testo, parole)
        if prob:
            raise Errore(f"{rel}: " + "; ".join(prob))
        if any(r.startswith(S.SEGNO_FILE) or r.strip() == S.FINE_FILE for r in testo.splitlines()):
            raise Errore(f"{rel}: contiene una riga-segno di sciame.sh")
        parti.append(f"{S.SEGNO_FILE} file {rel} ====\n" + testo + ("" if testo.endswith("\n") else "\n"))
    parti.append(f"{S.SEGNO_FILE} fine dei file ====\n{S.FINE_FILE}\n")
    uscita = Path(uscita)
    S.scrivi(uscita.parent, uscita, "".join(parti), 0o755)
    return uscita


def verifica(sciame: Path, pubblicazione: bool = False, parole_extra: list[str] | None = None) -> list[str]:
    """I controlli prima di pubblicare: database valido in tutte le lingue, documenti con gli stessi blocchi in ogni
    lingua, chiavi i18n uguali, nessun segreto, email, percorso della macchina, parola vietata o segno di sciame.sh in
    tutto il materiale pubblico (anche README, CONTRIBUTING, .github, skills, .claude-plugin), sciame.sh aggiornato; con
    --pubblicazione, nessuna cartella di lavoro nell'albero."""
    errori = []
    d = P.carica(sciame / "db")
    lingue = G.lingue_disponibili(sciame)
    errori += P.valida(d, lingue)
    blocchi = {}
    for l in lingue:
        for n in G.DOCUMENTI:
            p = sciame / "documenti" / l / n
            if not p.is_file():
                errori.append(f"documenti/{l}/{n} manca")
                continue
            blocchi.setdefault(n, {})[l] = set(G.blocchi(p.read_text(encoding="utf-8")))
    for n, per in blocchi.items():
        if len({frozenset(b) for b in per.values()}) > 1:
            errori.append(f"{n}: i blocchi differiscono fra le lingue: " + "; ".join(f"{l}={sorted(b)}" for l, b in per.items()))
    chiavi = {l: set(G.i18n(sciame, l)) for l in lingue}
    for l in lingue:
        if chiavi[l] != chiavi.get("it", chiavi[l]):
            errori.append(f"i18n/{l}.json: chiavi diverse da it.json")
    parole = (vietate(sciame) if installato(sciame) else S.vietate(sciame, sciame)[0]) + list(parole_extra or [])
    da_esaminare = list(file_da_distribuire(sciame))
    if not installato(sciame):
        # tutto l'albero che git pubblicherebbe: ogni file, anche nascosto, salvo .git, le cartelle di lavoro e ciò che
        # .gitignore esclude per nome di cartella o di file
        try:
            pubblici = albero_pubblico(sciame)
        except (Errore, S.Errore, subprocess.CalledProcessError) as e:
            errori.append(str(e))
            pubblici = []
        for rel in pubblici:
            if rel in da_esaminare or rel == "sciame.sh":
                continue
            if Path(rel).parts[0] in NON_PUBBLICARE:
                errori.append(f"{rel}: una cartella di lavoro che non va pubblicata")
            if not S.NOME_FILE.match(rel):
                errori.append(f"nome di file non ammesso: {rel!r}")
                continue
            da_esaminare.append(rel)
    for rel in da_esaminare:
        try:
            testo = (sciame / rel).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errori.append(f"{rel}: non è testo")
            continue
        prob = problemi_nome(rel, parole) + problemi_pubblici(testo, parole)
        errori += [f"{rel}: {x}" for x in prob]
    with tempfile.TemporaryDirectory() as tmp:
        for l in lingue:
            try:
                G.catalogo(sciame, Path(tmp), l)
            except (G.Errore, P.Errore, S.Errore) as e:
                errori.append(f"lingua {l}: {e}")
        if not installato(sciame) and (sciame / "sciame.sh").is_file():
            try:
                nuovo = costruisci(sciame, Path(tmp) / "sciame.sh", parole_extra=parole_extra).read_bytes()
                if nuovo != (sciame / "sciame.sh").read_bytes():
                    errori.append("sciame.sh non è aggiornato: costruisci --uscita sciame.sh")
            except (Errore, S.Errore, OSError) as e:
                errori.append(f"sciame.sh: {e}")
    if pubblicazione:
        for nome in NON_PUBBLICARE + ("motore/__pycache__", "prove/__pycache__"):
            if (sciame / nome).exists():
                errori.append(f"{nome}: non deve esserci nell'albero da pubblicare")
    return errori


# --- Il paragrafo per CLAUDE.md ---

INIZIO = "<!-- sciame:inizio (scritto da sciame/sciame.sh istruzioni: non modificare a mano) -->"
FINE = "<!-- sciame:fine -->"


def istruzioni(sciame: Path, file: Path, togli: bool = False) -> str:
    radice = radice_di(sciame)
    t = file.read_text(encoding="utf-8") if file.is_file() else ""
    i, j = t.find("<!-- sciame:inizio"), t.find(FINE)
    if (i < 0) != (j < 0) or (i >= 0 and j < i):
        raise Errore(f"{file}: i segni del paragrafo dello sciame sono rovinati, sistemali a mano")
    if i < 0 and togli:
        return "non c'era"
    if i >= 0:
        t = t[:i].rstrip("\n") + ("\n" if t[:i].strip() else "") + t[j + len(FINE):].lstrip("\n")
    if togli:
        S.scrivi(radice, file, t)
        return "tolto"
    par = (sciame / "documenti" / lingua(sciame) / "_CLAUDE.md").read_text(encoding="utf-8")
    S.scrivi(radice, file, (t.rstrip("\n") + "\n\n" if t.strip() else "") + INIZIO + "\n" + par.strip() + "\n" + FINE + "\n")
    return "scritto"


# --- La riga di comando ---

def main() -> None:
    p = argparse.ArgumentParser(prog="sciame", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sciame", type=Path, default=SCIAME, help=argparse.SUPPRESS)
    sp = p.add_subparsers(dest="comando", required=True)
    q = sp.add_parser("installa")
    q.add_argument("--da", type=Path, required=True)
    q.add_argument("--radice", type=Path, required=True)
    q.add_argument("--cartella", default="sciame")
    q.add_argument("--lingua")
    q.add_argument("--forza", action="store_true")
    q.add_argument("--istruzioni", action="store_true")
    q.add_argument("--locale", help="la cartella (o il file AGENTI.md) degli override locali, relativa alla radice")
    q.add_argument("--gestiti-dal-progetto", action="store_true",
                   help="gli agenti degli override li genera il progetto: lo sciame non li scrive")
    for s in G.STRATEGIE:
        q = sp.add_parser(s)
        q.add_argument("richiesta", nargs="?")
        q.add_argument("--profilo")
        q.add_argument("--ruoli")
        q.add_argument("--da-file")
        q.add_argument("--modello")
        q.add_argument("--lingua")
        q.add_argument("--stampa", action="store_true")
        q.add_argument("--mostra", action="store_true")
        q.add_argument("resto", nargs=argparse.REMAINDER)
    q = sp.add_parser("lingua")
    q.add_argument("codice", nargs="?")
    q = sp.add_parser("ruoli")
    q.add_argument("domanda", nargs="?")
    sp.add_parser("professionisti")
    sp.add_parser("controlla")
    sp.add_parser("rigenera")
    sp.add_parser("rimuovi")
    q = sp.add_parser("istruzioni")
    q.add_argument("--togli", action="store_true")
    q = sp.add_parser("modelli")
    q.add_argument("assegnazioni", nargs="*")
    q.add_argument("--tutti")
    sp.add_parser("richieste")
    q = sp.add_parser("conta")
    q.add_argument("cartella")
    q.add_argument("giro")
    q = sp.add_parser("approva")
    q.add_argument("file", type=Path)
    q.add_argument("--senza-sciame-sh", action="store_true")
    q.add_argument("--generica-di-locale", action="store_true",
                   help="la voce è la versione generica, senza dettagli del progetto, di una scheda locale")
    q = sp.add_parser("proponi")
    q.add_argument("sigle", nargs="+")
    q.add_argument("--invia", action="store_true")
    q.add_argument("--si", action="store_true", help="conferma l'invio della pull request")
    q = sp.add_parser("costruisci")
    q.add_argument("--uscita", type=Path)
    q.add_argument("--controlla", action="store_true", help="esce con 1 se sciame.sh non è aggiornato")
    q = sp.add_parser("verifica")
    q.add_argument("--pubblicazione", action="store_true", help="anche: nessuna cartella di lavoro nell'albero")
    q = sp.add_parser("importa-schede")
    q.add_argument("file", type=Path)
    ns = p.parse_args()
    sciame = ns.sciame.resolve()
    try:
        c = ns.comando
        if c == "installa":
            s = installa(ns.da.resolve(), ns.radice.resolve(), ns.cartella, ns.lingua, ns.forza, ns.locale,
                         ns.gestiti_dal_progetto)
            if ns.istruzioni:
                print(f"CLAUDE.md: {istruzioni(s, ns.radice.resolve() / 'CLAUDE.md')}")
        elif c in G.STRATEGIE:
            if ns.resto and ns.resto[0] == "--":
                ns.resto = ns.resto[1:]
            avvia(sciame, c, ns)
        elif c == "lingua":
            if not ns.codice:
                print(msg(sciame, "cli_lingua_attuale", lingua=lingua(sciame), lingue=", ".join(G.lingue_disponibili(sciame))))
            else:
                if ns.codice not in G.lingue_disponibili(sciame):
                    raise Errore(msg(sciame, "cli_lingua_sconosciuta", lingua=ns.codice,
                                     lingue=", ".join(G.lingue_disponibili(sciame))))
                serve_installato(sciame)
                S.scrivi(sciame, sciame / "LINGUA", ns.codice + "\n")
                rigenera(sciame)
                print(msg(sciame, "cli_lingua_cambiata", lingua=ns.codice))
        elif c == "ruoli":
            sys.argv = ["convoca.py", "ruoli"] + (["--domanda", ns.domanda] if ns.domanda else [])
            import runpy
            runpy.run_path(str(QUI / "convoca.py"), run_name="__main__")
        elif c == "professionisti":
            d = P.carica(sciame / "db")
            l = lingua(sciame)
            for v in P.ordinate(d):
                rientro = "    " if v["tipo"] == "sottoprofessionista" else ""
                print(f"{rientro}{v['numero']}. sciame-{v['sigla']}: {P.testo(v, l)['nome']}")
        elif c == "controlla":
            sys.exit(controlla(sciame))
        elif c == "rigenera":
            dati, fatti = rigenera(sciame)
            print(msg(sciame, "cli_allineato", ruoli=len(dati["ruoli"]), profili=len(dati["profili"])))
            saltati = [f for f in fatti if f.startswith("saltato")]
            if saltati:
                print(msg(sciame, "cli_saltati", n=len(saltati)))
        elif c == "rimuovi":
            serve_installato(sciame)
            tolti = G.togli(radice_di(sciame))
            cl = radice_di(sciame) / "CLAUDE.md"
            if cl.is_file():
                istruzioni(sciame, cl, togli=True)
            print(f"tolti {len(tolti)} file generati; restano {sciame} e .sciame/")
        elif c == "istruzioni":
            serve_installato(sciame)
            print(f"CLAUDE.md: {istruzioni(sciame, radice_di(sciame) / 'CLAUDE.md', ns.togli)}")
        elif c == "modelli":
            serve_installato(sciame)
            radice = radice_di(sciame)
            cfg = leggi_config(radice)
            m = cfg.setdefault("modelli", {})
            assegnazioni = list(ns.assegnazioni) + ([f"*={ns.tutti}"] if ns.tutti else [])
            for a in assegnazioni:
                chi, _, val = a.partition("=")
                if not val or not G.MODELLO.match(val) or not re.match(r"^[a-z0-9*][a-z0-9-]*$", chi):
                    raise Errore(f"forma: ruolo=modello, nucleo=modello o --tutti modello, con nomi semplici ({a})")
                m[chi] = val
            if assegnazioni:
                scrivi_config(radice, cfg)
                rigenera(sciame)
            print(json.dumps(m, ensure_ascii=False, indent=1) if m else "tutti: inherit")
        elif c in ("richieste", "conta"):
            sys.argv = (["giuria.py", "richieste", str(sciame / "RICHIESTE_ESPERTI.md")] if c == "richieste"
                        else ["giuria.py", "conta", ns.cartella, ns.giro])
            import runpy
            runpy.run_path(str(QUI / "giuria.py"), run_name="__main__")
        elif c == "approva":
            print(approva(sciame, ns.file, not ns.senza_sciame_sh, ns.generica_di_locale))
        elif c == "proponi":
            print(proponi(sciame, ns.sigle, ns.invia, ns.si))
        elif c == "costruisci":
            uscita = ns.uscita or sciame / "sciame.sh"
            if ns.controlla:
                with tempfile.TemporaryDirectory() as tmp:
                    nuovo = costruisci(sciame, Path(tmp) / "sciame.sh").read_bytes()
                aggiornato = uscita.is_file() and uscita.read_bytes() == nuovo
                print(f"{uscita}: " + ("aggiornato" if aggiornato else "NON aggiornato: costruisci"))
                sys.exit(0 if aggiornato else 1)
            print(costruisci(sciame, uscita))
        elif c == "verifica":
            errori = verifica(sciame, ns.pubblicazione)
            print("\n".join(errori) if errori else "verifica: nessun problema")
            sys.exit(1 if errori else 0)
        elif c == "importa-schede":
            # Le schede di un AGENTI.md 3.x che il database non ha sono del progetto: vanno negli override locali,
            # mai nel database pubblico.
            serve_installato(sciame)
            radice = radice_di(sciame)
            d = P.carica(sciame / "db")
            noti = {v["sigla"] for v in d["voci"]}
            destinazione = S.file_agenti_locale(radice, sciame)
            gia = P.schede_locali(destinazione)
            nuove = [s for s in P.schede_locali(ns.file).values() if s["sigla"] not in noti and s["sigla"] not in gia]
            if nuove:
                testo = destinazione.read_text(encoding="utf-8") if destinazione.is_file() else "# Schede locali\n"
                testo = testo.rstrip("\n") + "\n\n" + "\n\n".join(s["scheda"] for s in nuove) + "\n"
                S.scrivi(radice, destinazione, testo)
                rigenera(sciame)
            print(f"{len(nuove)} schede portate negli override locali ({destinazione}); il database pubblico non cambia")
    except (Errore, G.Errore, P.Errore, S.Errore, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as e:
        print(f"sciame: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
