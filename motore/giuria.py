#!/usr/bin/env python3
"""Lo sciame 4.0, protocollo G (sciame/GIURIA.md): conta i voti di una giuria e la soglia degli esperti nuovi.

    python3 -I sciame/giuria.py conta <cartella della giuria> <giro>
    python3 -I sciame/giuria.py richieste [sciame/RICHIESTE_ESPERTI.md]

`conta` ricalcola dai file sigillati tutti i giri da 0 a <giro> (non si fida degli ESITO già scritti), confronta i
sigilli con `SIGILLI.md` del cancelliere, controlla composizione, voti, non regressione, dipendenze e limite, e scrive
`ESITO_giro_<r>.json`. Esce con 0 se tutti i controlli passano, con 2 altrimenti (e allora non scrive niente).
Un ESITO già scritto deve coincidere con quello ricalcolato: un rivoto sullo stesso giro o un ESITO ritoccato sono un
errore. Non lancia agenti.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import os

QUI = Path(__file__).resolve().parent
BASE = QUI.parent if QUI.name == "motore" else QUI  # la cartella dello sciame
RADICE = Path(os.environ.get("SCIAME_RADICE", (BASE / (BASE / "RADICE").read_text(encoding="utf-8").strip()).resolve()
                             if (BASE / "RADICE").is_file() else BASE.parent))
AGENTI_DIR = Path(os.environ.get("SCIAME_AGENTI", RADICE / ".claude" / "agents"))
SIGILLO = re.compile(r"^sha256 dei byte che precedono questa riga: ([0-9a-f]{64})\s*$")
ID = r"(D[0-9A-Za-z_.-]+)"
RIGHE = {  # parola chiave → espressione della riga intera
    "OPZIONE": re.compile(rf"^OPZIONE {ID} (.+?)\s*$"),
    "OPZIONI": re.compile(rf"^OPZIONI {ID} (.+?)\s*$"),
    "DISPOSITIVO": re.compile(rf"^DISPOSITIVO {ID} (.+?)\s*$"),
    "DIPENDE": re.compile(rf"^DIPENDE {ID} {ID}\s*$"),
    "INCOMPATIBILE": re.compile(rf"^INCOMPATIBILE {ID} (.+?)\s*$"),
    "PROVA": re.compile(rf"^PROVA {ID} (.+?)\s*$"),
    "ESITO-PROVA": re.compile(rf"^ESITO-PROVA {ID} (passa|fallisce)\s*$"),
    "VOTO": re.compile(rf"^VOTO {ID} (si|sì|no)\s*$"),
    "REVISIONE": re.compile(rf"^REVISIONE {ID} (.+?)\s*$"),
    "CONDIZIONE": re.compile(rf"^CONDIZIONE {ID} (.+?)\s*$"),
    "CLASSE": re.compile(rf"^CLASSE {ID} (leggera|ordinaria|plenaria)\s*$"),
    "CAMBIO": re.compile(rf"^CAMBIO {ID} (.+?)\s*$"),
    "PREFERISCO": re.compile(rf"^PREFERISCO {ID} (.+?)\s*$"),
}
# quasi conforme: la parola chiave, in qualunque forma, in testa (dopo segni di elenco, citazione o grassetto) e
# seguita da un identificativo D…: «VOTO D1: no», «voto D1 si», «- VOTO D1 si», «**VOTO** D1». La prosa come
# «- **CONDIZIONE #1** …», «# Voto del…» o
# «classe (iii)» non lo è.
QUASI = re.compile(r"^[\s\-*>#]*(?i:(" + "|".join(sorted(RIGHE, key=len, reverse=True)) + r"))[\s:*]+D[0-9A-Za-z_.-]")
RUOLO = re.compile(r"^[a-z][a-z0-9-]*$")
AVVERSARI = {"avversario", "rovesciatore"}
PASSATA = {"logico", "debugger"}  # con un avversario: obbligatori in una giuria vincolante (GIURIA.md §2)
LIMITE_GIRI = 3
LIMITE_GIRI_LEGGERA = 1  # la giuria leggera ha un solo giro di revisione, poi passa alla giuria ordinaria
CRITICI = {"avversario", "rovesciatore", "debugger"}
FINALI = {"APPROVATA", "RACCOMANDATA", "RESPINTA", "NON_CONVERGENTE", "SOSPESA", "DA_PLENARIA", "DA_RIPROPORRE",
          "DA_GIURIA", "DA_UTENTE"}


def limite(g):
    return LIMITE_GIRI_LEGGERA if g.get("forma") == "leggera" else LIMITE_GIRI


class Errore(Exception):
    pass


def sha(dati):
    return hashlib.sha256(dati).hexdigest()


def sigillato(p):
    """(testo prima del sigillo, sigillo), se il sigillo coincide; altrimenti Errore."""
    if not p.is_file():
        raise Errore(f"manca {p}")
    dati = p.read_bytes()
    corpo, _, ultima = dati.rstrip(b"\n").rpartition(b"\n")
    m = SIGILLO.match(ultima.decode("utf-8", "replace"))
    if not m:
        raise Errore(f"{p.name}: ultima riga senza sigillo")
    corpo += b"\n"
    if sha(corpo) != m.group(1):
        raise Errore(f"{p.name}: il sigillo non coincide con i byte che lo precedono")
    return corpo.decode("utf-8"), m.group(1)


def righe_valide(testo, nome, ammesse):
    """Le righe del protocollo fuori dai blocchi ```; una riga quasi conforme è un errore."""
    trovate, dentro = [], False
    for n, riga in enumerate(testo.splitlines(), 1):
        if riga.lstrip().startswith("```"):
            dentro = not dentro
            continue
        if dentro:
            continue
        q = QUASI.match(riga)
        if not q:
            continue
        chiave = q.group(1).upper()
        m = RIGHE.get(chiave) and RIGHE[chiave].match(riga)
        if not m or chiave not in ammesse:
            raise Errore(f"{nome} r. {n}: riga non conforme o non ammessa qui: «{riga.strip()[:80]}»")
        trovate.append((chiave, m.groups()))
    if dentro:
        raise Errore(f"{nome}: blocco ``` non chiuso")
    return trovate


def ruoli_noti():
    if not AGENTI_DIR.is_dir():
        raise Errore(f"manca {AGENTI_DIR}")
    return {p.stem[len("sciame-"):] for p in AGENTI_DIR.glob("sciame-*.md")}


def leggi_giuria(cartella):
    p = cartella / "giuria.json"
    if not p.is_file():
        raise Errore("manca giuria.json")
    dati = p.read_bytes()
    try:
        g = json.loads(dati)
    except json.JSONDecodeError as x:
        raise Errore(f"giuria.json non è json: {x}")
    if not isinstance(g, dict):
        raise Errore("giuria.json: serve un oggetto")
    return g, sha(dati)


def controlla_composizione(cartella, g):
    errori = []
    for campo, tipo in (("oggetto", str), ("relatore", str), ("cancelliere", str), ("giurati", list),
                        ("tocca_codice", bool), ("tocca_numeri", bool), ("autorita", str), ("delega", str),
                        ("classificazione", str)):
        if not isinstance(g.get(campo), tipo):
            errori.append(f"campo «{campo}» mancante o di tipo sbagliato")
    if errori:
        raise Errore("giuria.json: " + "; ".join(errori))
    if g["autorita"] not in ("vincolante", "raccomandazione"):
        errori.append("autorita: «vincolante» o «raccomandazione»")
    if g["classificazione"] not in ("ordinaria", "plenaria"):
        errori.append("classificazione: «ordinaria» o «plenaria»")
    if g.get("protocollo", "G2") not in ("G2", "G1.1"):
        errori.append("protocollo: «G2» (di difetto) o «G1.1»")
    if g.get("forma", "ordinaria") not in ("ordinaria", "leggera"):
        errori.append("forma: «ordinaria» o «leggera»")
    leggera = g.get("forma") == "leggera"
    if g.get("limite_giri", limite(g)) != limite(g):
        errori.append(f"limite_giri: il protocollo lo fissa a {limite(g)}")
    noti = ruoli_noti()
    ruoli = []
    for x in g["giurati"]:
        if not isinstance(x, dict) or not isinstance(x.get("ruolo"), str):
            errori.append("un giurato senza «ruolo»")
            continue
        r = x["ruolo"]
        ruoli.append(r)
        if not RUOLO.match(r):
            errori.append(f"ruolo «{r}» non conforme a {RUOLO.pattern}")
        elif x.get("provvisorio"):
            try:
                sigillato(cartella / f"SCHEDA_{r}.md")
            except Errore as e:
                errori.append(f"esperto provvisorio «{r}» senza scheda sigillata: {e}")
        elif r not in noti:
            errori.append(f"ruolo «{r}» non è fra gli agenti dello sciame e non è segnato provvisorio")
    n = len(ruoli)
    if len(set(ruoli)) != n:
        errori.append("un ruolo compare due volte fra i giurati")
    plenaria = g["classificazione"] == "plenaria"
    for chi in ("relatore", "cancelliere"):
        if g[chi] in ruoli:
            errori.append(f"il {chi} ({g[chi]}) non può votare")
    if leggera and plenaria:
        errori.append("la giuria leggera non vale per una plenaria")
    if plenaria and g2(g) and (cartella / "PERTINENZA.md").is_file():
        attesi = pertinenti(cartella, g)
        if set(ruoli) != attesi:
            errori.append("plenaria: i votanti sono i pertinenti di PERTINENZA.md: mancano "
                          + (", ".join(sorted(attesi - set(ruoli))) or "nessuno") + "; in più "
                          + (", ".join(sorted(set(ruoli) - attesi)) or "nessuno"))
    elif plenaria:
        mancano = sorted(noti - set(ruoli) - {g["relatore"], g["cancelliere"]})
        if mancano:
            errori.append("plenaria: mancano i ruoli " + ", ".join(mancano))
        if not all(x.get("nuovo_sull_oggetto") for x in g["giurati"] if isinstance(x, dict)):
            errori.append("plenaria: al voto finale ogni ruolo vota con un'istanza nuova")
    elif leggera:
        if g["classificazione"] != "ordinaria":
            errori.append("la giuria leggera non vale per una plenaria")
        if n != 3:
            errori.append(f"giuria leggera: {n} giurati, ne servono 3 (competente, critico, garante)")
        if not CRITICI & set(ruoli):
            errori.append("giuria leggera: manca un critico (avversario, rovesciatore o debugger)")
        if not set(ruoli) - CRITICI - {"garante"}:
            errori.append("giuria leggera: manca il ruolo competente per la funzione")
    else:
        if not 5 <= n <= 9 or n % 2 == 0:
            errori.append(f"giurati {n}: servono da 5 a 9, in numero dispari")
        nuovi = sum(1 for x in g["giurati"] if isinstance(x, dict) and x.get("nuovo_sull_oggetto"))
        if 2 * nuovi < n:
            errori.append(f"istanze nuove sull'oggetto {nuovi} su {n}: servono almeno la metà")
        provv = sum(1 for x in g["giurati"] if isinstance(x, dict) and x.get("provvisorio"))
        if 3 * provv > n:
            errori.append(f"esperti provvisori {provv} su {n}: al più un terzo")
    if "garante" not in ruoli:
        errori.append("manca il garante dell'obiettivo")
    if not leggera:
        if not AVVERSARI & set(ruoli):
            errori.append("manca un avversario (avversario o rovesciatore)")
        if g["tocca_codice"] and "debugger" not in ruoli:
            errori.append("la decisione tocca codice e manca il debugger")
        if g["tocca_numeri"] and "statistico" not in ruoli:
            errori.append("la decisione tocca soglie o cifre e manca lo statistico")
        if g["autorita"] == "vincolante" and not PASSATA <= set(ruoli):
            errori.append("decisione vincolante: servono logico, debugger e un avversario")
    for p in cartella.glob("RINUNCIA_*.md"):
        if p.stem[len("RINUNCIA_"):] in ruoli:
            errori.append(f"{p.name}: chi rinuncia non può essere giurato")
    if errori:
        raise Errore("composizione: " + "; ".join(errori))
    return ruoli


def leggi_sigilli(cartella):
    p = cartella / "SIGILLI.md"
    if not p.is_file():
        raise Errore("manca SIGILLI.md: i sigilli riportati da relatore e giurati nelle loro risposte finali")
    out, verificate = {}, set()
    for riga in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^SIGILLO ((?:giro_\d+/)?[A-Za-z0-9_.-]+\.(?:md|json)) ([0-9a-f]{64})\s*$", riga)
        if m:
            out[m.group(1)] = m.group(2)
        m = re.match(r"^INCOMPATIBILE-VERIFICATO (giro_\d+) (D[0-9A-Za-z_.-]+)\s*$", riga)
        if m:  # il cancelliere conferma l'incompatibilità dichiarata dal relatore in quel giro
            verificate.add((m.group(1), m.group(2)))
    out["__incompatibili_verificate__"] = verificate
    return out


def g2(g):
    """Nella skill il protocollo G2 vale per difetto; "protocollo": "G1.1" solo per le giurie votate prima di lui."""
    return g.get("protocollo", "G2") == "G2"


def controlla_g2(cartella, g, sha_giuria, sigilli):
    """Protocollo G2: giuria.json sigillato prima del giro 0; nessun SIGILLO orfano; la delega e la pertinenza
    sigillate quando servono."""
    errori = []
    if sigilli.get("giuria.json") != sha_giuria:
        errori.append("SIGILLI.md: manca «SIGILLO giuria.json <sha>» uguale al file (G2: la giuria si fissa prima del giro 0)")
    for rel in sigilli:
        if rel.startswith("__"):
            continue
        if not (cartella / rel).is_file():
            errori.append(f"SIGILLI.md: SIGILLO orfano, {rel} non esiste")
    if g.get("autorita") == "vincolante":
        if g.get("delega") != "DELEGA.md":
            errori.append("G2: una giuria vincolante ha \"delega\": \"DELEGA.md\", con le righe «DELEGATA Dk»")
        else:
            con_sigillo_dichiarato(cartella, "DELEGA.md", sigilli)
    if g.get("classificazione") == "plenaria":
        if g.get("pertinenza") != "PERTINENZA.md":
            errori.append("G2: una plenaria ha \"pertinenza\": \"PERTINENZA.md\", con le righe «PERTINENTE <ruolo>»")
        else:
            con_sigillo_dichiarato(cartella, "PERTINENZA.md", sigilli)
    if errori:
        raise Errore("; ".join(errori))


def delegate(cartella, g):
    if not (g2(g) and g.get("autorita") == "vincolante"):
        return None
    testo = (cartella / "DELEGA.md").read_text(encoding="utf-8")
    return set(re.findall(r"^DELEGATA (D[0-9A-Za-z_.-]+)\s*$", testo, re.M))


def pertinenti(cartella, g):
    """I votanti di una plenaria G2: i ruoli PERTINENTE, con le deleghe dei sottoprofessionisti (DELEGA <sotto>
    <genitore>: il sottoprofessionista vota al posto del genitore, mai insieme)."""
    testo = (cartella / "PERTINENZA.md").read_text(encoding="utf-8")
    per = set(re.findall(r"^PERTINENTE ([a-z][a-z0-9-]*)\s*$", testo, re.M))
    for sotto, genitore in re.findall(r"^DELEGA ([a-z][a-z0-9-]*) ([a-z][a-z0-9-]*)\s*$", testo, re.M):
        if genitore in per:
            per.discard(genitore)
            per.add(sotto)
    return per - {g.get("relatore"), g.get("cancelliere")}


def con_sigillo_dichiarato(cartella, relativo, sigilli):
    testo, s = sigillato(cartella / relativo)
    if sigilli.get(relativo) != s:
        raise Errore(f"{relativo}: il sigillo non coincide con quello riportato in SIGILLI.md")
    return testo, s


def leggi_proposta(cartella, r, sigilli):
    testo, s = con_sigillo_dichiarato(cartella, f"giro_{r}/PROPOSTA.md", sigilli)
    righe = righe_valide(testo, f"giro_{r}/PROPOSTA.md", {"OPZIONE", "OPZIONI", "DISPOSITIVO", "DIPENDE", "INCOMPATIBILE",
                                                          "PROVA", "ESITO-PROVA"})
    p = {"sha": s, "opzione": {}, "opzioni": {}, "dispositivo": {}, "dipende": {}, "incompatibile": {}, "prova": {},
         "esito-prova": {}}
    for chiave, gr in righe:
        if chiave == "DIPENDE":
            p["dipende"].setdefault(gr[0], set()).add(gr[1])
            continue
        campo = chiave.lower()
        if gr[0] in p[campo]:
            raise Errore(f"giro_{r}/PROPOSTA.md: due righe {chiave} per {gr[0]}")
        if campo in ("prova", "esito-prova") and gr[0] not in p["opzione"] and False:
            pass
        p[campo][gr[0]] = gr[1]
    if not p["opzione"]:
        raise Errore(f"giro_{r}/PROPOSTA.md: nessuna riga OPZIONE")
    for d in p["opzione"]:
        if d not in p["dispositivo"]:
            raise Errore(f"giro_{r}/PROPOSTA.md: manca DISPOSITIVO {d}")
    for d in p["incompatibile"]:
        if d not in p["opzione"]:
            raise Errore(f"giro_{r}/PROPOSTA.md: INCOMPATIBILE su {d}, che non è in esame")
    if r == 0:
        for d, o in p["opzione"].items():
            lista = [x.strip() for x in p["opzioni"].get(d, "").split("|") if x.strip()]
            if o not in lista:
                raise Errore(f"giro_0/PROPOSTA.md: OPZIONE {d} «{o}» non è nella riga OPZIONI {d}")
    return p


def leggi_voto(cartella, r, ruolo, decisioni, sigilli, facoltative=frozenset()):
    rel = f"giro_{r}/VOTO_{ruolo}.md"
    testo, s = con_sigillo_dichiarato(cartella, rel, sigilli)
    v = {"sha": s, "voto": {}, "revisione": {}, "condizione": {}, "classe": {}, "cambio": {}, "preferisco": {}}
    for chiave, gr in righe_valide(testo, rel, {"VOTO", "REVISIONE", "CONDIZIONE", "CLASSE", "CAMBIO", "PREFERISCO"}):
        campo = chiave.lower()
        if gr[0] in facoltative:
            continue
        if gr[0] not in decisioni:
            raise Errore(f"{rel}: {chiave} su {gr[0]}, che non è in esame")
        if gr[0] in v[campo]:
            raise Errore(f"{rel}: due righe {chiave} per {gr[0]}")
        v[campo][gr[0]] = "si" if gr[1] == "sì" else gr[1]
    errori = []
    for d in decisioni:
        if d not in v["voto"]:
            errori.append(f"manca il voto su {d}")
            continue
        if v["voto"][d] == "no" and d not in v["revisione"]:
            errori.append(f"no su {d} senza REVISIONE")
        if v["voto"][d] == "si" and d not in v["condizione"]:
            errori.append(f"sì su {d} senza CONDIZIONE")
        if d not in v["classe"]:
            errori.append(f"manca CLASSE {d}")
    if errori:
        raise Errore(f"{rel}: " + "; ".join(errori))
    return v


def esito_conteggio(s, n):
    if s == n:
        return "APPROVATA"
    if 2 * s > n:
        return "REVISIONE"
    return "RESPINTA"


def calcola_giro(cartella, g, ruoli, r, prec, sigilli):
    giro = cartella / f"giro_{r}"
    if not giro.is_dir():
        raise Errore(f"manca la cartella giro_{r}")
    attesi = {"PROPOSTA.md"} | {f"VOTO_{x}.md" for x in ruoli}
    estranei = sorted(p.name for p in giro.iterdir() if p.name not in attesi)
    if estranei:
        raise Errore(f"giro_{r}: voci estranee " + ", ".join(estranei))
    p = leggi_proposta(cartella, r, sigilli)
    if g.get("forma") == "leggera":
        for d in p["opzione"]:
            if d not in p["prova"] or d not in p["esito-prova"]:
                raise Errore(f"giro_{r}/PROPOSTA.md: nella giuria leggera {d} vuole PROVA ed ESITO-PROVA (prova prima del voto)")
    if prec is None:
        if p["incompatibile"]:
            raise Errore("giro_0/PROPOSTA.md: INCOMPATIBILE vale solo nei giri di revisione")
    else:
        in_revisione = {d for d, e in prec["decisioni"].items() if e["stato"] == "REVISIONE"}
        if set(p["opzione"]) != in_revisione:
            raise Errore(f"giro_{r}/PROPOSTA.md: le decisioni devono essere quelle in REVISIONE "
                         f"({', '.join(sorted(in_revisione)) or 'nessuna'})")
        for d in p["opzione"]:
            e = prec["decisioni"][d]
            if p["opzione"][d] != e["opzione"]:
                raise Errore(f"giro_{r}: l'opzione di {d} è cambiata: è una proposta nuova, dal giro 0")
            if p["dispositivo"][d] != e["dispositivo"]:
                raise Errore(f"giro_{r}: il DISPOSITIVO di {d} è cambiato: non è una revisione piccola")
            if p["dipende"].get(d, set()) != set(e.get("dipende", [])):
                raise Errore(f"giro_{r}: le dipendenze di {d} sono cambiate")
    verificate = {d for (g, d) in sigilli.get("__incompatibili_verificate__", set()) if g == f"giro_{r}"}
    for d in verificate:
        if d not in p["incompatibile"]:
            raise Errore(f"SIGILLI.md: INCOMPATIBILE-VERIFICATO giro_{r} {d}, ma la proposta non lo dichiara")
    chiuse = {d for d in p["incompatibile"] if d in verificate}
    da_votare = [d for d in p["opzione"] if d not in chiuse]
    # Su una decisione dichiarata INCOMPATIBILE ma chiusa dal cancelliere, i voti sono ammessi e non contano.
    voti = {x: leggi_voto(cartella, r, x, da_votare, sigilli, facoltative=chiuse) for x in ruoli}
    n = len(ruoli)
    decisioni = {}
    for d in p["opzione"]:
        base = {"opzione": p["opzione"][d], "dispositivo": p["dispositivo"][d], "sha_proposta": p["sha"],
                "dipende": sorted(p["dipende"].get(d, set()))}
        if d in chiuse:
            decisioni[d] = dict(prec["decisioni"][d], stato="NON_CONVERGENTE",
                                incompatibile={"giro": r, "motivo": p["incompatibile"][d], "verificata": True})
            continue
        si = sorted(x for x in ruoli if voti[x]["voto"][d] == "si")
        no = sorted(x for x in ruoli if voti[x]["voto"][d] == "no")
        stato = esito_conteggio(len(si), n)
        voce = dict(base, si=si, no=no, stato=stato, giro_del_testo=r,
                    revisioni_chieste={x: voti[x]["revisione"][d] for x in no},
                    condizioni_dei_si={x: voti[x]["condizione"][d] for x in si},
                    classe_plenaria=sorted(x for x in ruoli if voti[x]["classe"][d] == "plenaria"),
                    preferenze={x: voti[x]["preferisco"][d] for x in ruoli if d in voti[x]["preferisco"]})
        if prec is not None:
            e = prec["decisioni"][d]
            persi = sorted(set(e["si"]) - set(si))
            # CAMBIO si chiede rispetto all'ultimo voto espresso dal giurato, anche in un giro scartato come regressivo.
            ultimi_no = e["regressiva"]["voti_del_giro"]["no"] if e.get("regressiva", {}).get("giro") == r - 1 else e["no"]
            senza_cambio = sorted(x for x in si if x in ultimi_no and d not in voti[x]["cambio"])
            if senza_cambio:
                raise Errore(f"giro_{r}: {d}, da no a sì senza riga CAMBIO: " + ", ".join(senza_cambio))
            if stato != "RESPINTA" and persi:
                # revisione regressiva: si scarta, restano il testo e i voti del giro precedente
                voce = dict(e, stato="REVISIONE",
                            regressiva={"giro": r, "si_persi": persi, "voti_del_giro": {"si": si, "no": no}})
        if g.get("forma") == "leggera":
            voce["prova"] = {"testo": p["prova"][d], "esito": p["esito-prova"][d]}
            classi = {voti[x]["classe"][d] for x in ruoli}
            if "plenaria" in classi:
                voce["stato"] = "DA_PLENARIA"
            elif "ordinaria" in classi:
                voce["stato"] = "DA_GIURIA"
                voce["motivo"] = "un giurato la classifica ordinaria: va alla giuria ordinaria"
            elif voce["stato"] in ("APPROVATA", "REVISIONE") and p["esito-prova"][d] == "fallisce":
                voce["stato"] = "RESPINTA"
                voce["motivo"] = "la prova veloce fallisce"
        if g2(g) and prec is None:
            fuori = sorted(x for x, o in voce.get("preferenze", {}).items()
                           if o not in [y.strip() for y in p["opzioni"].get(d, "").split("|")])
            if fuori:
                raise Errore(f"{d}: PREFERISCO fuori dall'elenco OPZIONI ({', '.join(fuori)})")
        if voce["stato"] == "APPROVATA":
            pref = {}
            for o in voce["preferenze"].values():
                if o != voce["opzione"]:
                    pref[o] = pref.get(o, 0) + 1
            migliore = max(pref.items(), key=lambda kv: kv[1], default=(None, 0))
            if voce["classe_plenaria"] and g.get("forma") != "leggera" and not (
                    g2(g) and g.get("classificazione") == "plenaria"):
                voce["stato"] = "DA_PLENARIA"
            elif 2 * migliore[1] > n:
                voce["stato"] = "DA_RIPROPORRE"
                voce["da_riproporre_con"] = migliore[0]
            elif g["autorita"] == "raccomandazione":
                voce["stato"] = "RACCOMANDATA"
            elif delegate(cartella, g) is not None and d not in delegate(cartella, g):
                voce["stato"] = "RACCOMANDATA"
                voce["motivo"] = "la decisione non è fra quelle delegate in DELEGA.md"
        if voce["stato"] == "REVISIONE" and r == limite(g):
            voce["stato"] = "DA_GIURIA" if g.get("forma") == "leggera" else "NON_CONVERGENTE"
        decisioni[d] = voce
    if prec is not None:
        for d, e in prec["decisioni"].items():
            decisioni.setdefault(d, e)
    # dipendenze: un'approvata che dipende da una non approvata non diventa atto
    for _ in range(len(decisioni)):
        for d, e in decisioni.items():
            for dj in e.get("dipende", []):
                if dj not in decisioni:
                    raise Errore(f"{d} dipende da {dj}, che non è fra le decisioni della giuria")
                sj = decisioni[dj]["stato"]
                if sj == "REVISIONE" and e["stato"] in ("APPROVATA", "RACCOMANDATA"):
                    e["stato"] = "REVISIONE"
                    e["in_attesa_di"] = dj
                elif sj in FINALI - {"APPROVATA", "RACCOMANDATA"} and e["stato"] not in ("RESPINTA",):
                    if e["stato"] != "SOSPESA":
                        e["stato"] = "SOSPESA"
                        e["sospesa_per"] = {"dipende_da": dj, "stato": sj}
    return {"giro": r, "giurati": ruoli, "n": n, "limite_giri": limite(g), **({"forma": "leggera"} if g.get("forma") == "leggera" else {}), "protocollo": g.get("protocollo", "G2"),
            "sha_voti": {x: voti[x]["sha"] for x in ruoli}, "decisioni": decisioni}


def precedenti(cartella, g, e, k):
    """G2: le giurie precedenti sulla stessa domanda (giuria.json "precedenti", cartelle relative alla cartella madre).
    Un'opzione già RESPINTA non si ripropone; un secondo DA_RIPROPORRE sulla stessa decisione diventa DA_UTENTE."""
    if k != 0:
        return
    for rel in g.get("precedenti", []):
        if Path(rel).is_absolute() or ".." in Path(rel).parts or "/" in rel:
            raise Errore(f"precedenti: «{rel}» non ammesso")
        c = (cartella.parent / rel).resolve()
        esiti = sorted(c.glob("ESITO_giro_*.json"))
        if not esiti:
            raise Errore(f"precedenti: {rel} non ha un ESITO")
        vecchio = json.loads(esiti[-1].read_text(encoding="utf-8"))["decisioni"]
        for d, v in e["decisioni"].items():
            w = vecchio.get(d)
            if not w:
                continue
            if w["stato"] == "RESPINTA" and w["opzione"] == v["opzione"]:
                raise Errore(f"{d}: l'opzione «{v['opzione']}» è già RESPINTA in {rel}: non si ripropone")
            if w["stato"] == "DA_RIPROPORRE" and v["stato"] == "DA_RIPROPORRE":
                v["stato"] = "DA_UTENTE"
                v["motivo"] = f"secondo DA_RIPROPORRE dopo {rel}: decide l'utente"


def conta(cartella, r):
    cartella = Path(cartella)
    if not isinstance(r, int) or r < 0:
        raise Errore("il giro è un intero ≥ 0")
    g, sha_giuria = leggi_giuria(cartella)
    if r > limite(g):
        raise Errore(f"giro {r} oltre il limite ({limite(g)})")
    if not g2(g) and os.environ.get("SCIAME_G11_PROVE") != "1":
        e0 = cartella / "ESITO_giro_0.json"
        if not e0.is_file() or '"protocollo"' in e0.read_text(encoding="utf-8"):
            raise Errore("protocollo G1.1: ammesso solo per ricontare le giurie votate prima di G2 (un ESITO_giro_0.json "
                         "senza la chiave «protocollo»); una giuria nuova segue G2")
    ruoli = controlla_composizione(cartella, g)
    sigilli = leggi_sigilli(cartella)
    if g2(g):
        controlla_g2(cartella, g, sha_giuria, sigilli)
    prec = None
    for k in range(r + 1):
        e = calcola_giro(cartella, g, ruoli, k, prec, sigilli)
        e["sha_giuria"] = sha_giuria
        p = cartella / f"ESITO_giro_{k}.json"
        if g2(g):
            precedenti(cartella, g, e, k)
        testo = json.dumps(e, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
        if p.exists():
            vecchio = p.read_text(encoding="utf-8")
            if '"protocollo"' not in vecchio:
                senza = {a: b for a, b in e.items() if a != "protocollo"}
                testo = json.dumps(senza, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
            if vecchio != testo:
                raise Errore(f"{p.name} esiste e non coincide con il ricalcolo: rivoto, voto cambiato, "
                             f"giuria.json cambiata o ESITO ritoccato")
        elif k < r:
            raise Errore(f"manca {p.name}: i giri si contano in ordine")
        if k < r and not any(v["stato"] == "REVISIONE" for v in e["decisioni"].values()):
            raise Errore(f"dopo il giro {k} nessuna decisione è in REVISIONE: il giro {r} non esiste")
        prec = e
    uscita = cartella / f"ESITO_giro_{r}.json"
    if uscita.is_symlink():
        raise Errore(f"{uscita.name} è un collegamento simbolico: non lo seguo")
    uscita.write_text(testo, encoding="utf-8")
    return prec


# ---- §4, gli esperti che non esistono ancora ----

RIGA_TABELLA = re.compile(r"^\|\s*\d{4}")
RIGA_RICHIESTA = re.compile(
    r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*`([a-z0-9-]+)`\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*$")
RIGA_CHIUSA = re.compile(r"^- `([a-z0-9-]+)`: (creato|created|(?:unito a|merged into) `([a-z0-9-]+)`)")


def normalizza_richiedente(chi, noti):
    c = chi.strip().lower()
    if c.startswith("sciame-"):
        c = c[len("sciame-"):]
    if c == "coordinatore" or c in noti:
        return c
    if c.startswith("provvisorio:") and RUOLO.match(c[len("provvisorio:"):]):
        return c
    raise Errore(f"richiedente «{chi}» non è un ruolo dello sciame, «coordinatore» o «provvisorio:<sigla>»")


def richieste(registro, radice=None):
    radice = Path(radice) if radice else RADICE
    noti = ruoli_noti()
    righe = Path(registro).read_text(encoding="utf-8").splitlines()
    creati, uniti = set(), {}
    for riga in righe:
        m = RIGA_CHIUSA.match(riga)
        if m:
            if m.group(2) in ("creato", "created"):
                creati.add(m.group(1))
            else:
                uniti[m.group(1)] = m.group(3)
    per_sigla = {}
    for n, riga in enumerate(righe, 1):
        if not RIGA_TABELLA.match(riga):
            continue
        m = RIGA_RICHIESTA.match(riga)
        if not m:
            raise Errore(f"registro r. {n}: riga non conforme «{riga[:80]}»")
        _, conv, chi, sigla, _, motivo = m.groups()
        if len(motivo) < 10:
            raise Errore(f"registro r. {n}: motivo assente o troppo breve")
        if not (radice / conv).is_dir():
            raise Errore(f"registro r. {n}: la convocazione «{conv}» non è una cartella d'archivio esistente")
        chi = normalizza_richiedente(chi, noti)
        while sigla in uniti:
            sigla = uniti[sigla]
        if sigla in creati:
            continue
        if chi == f"provvisorio:{sigla}":
            continue  # l'esperto provvisorio non chiede la propria creazione
        per_sigla.setdefault(sigla, set()).add((conv, chi))
    soglia = {}
    for sigla, coppie in per_sigla.items():
        coord = sorted(c for c in coppie if c[1] == "coordinatore")[:1]
        agenti = {c for c in coppie if c[1] != "coordinatore"}
        conteggiate = agenti | set(coord)
        conv = {}
        for c, chi in agenti:
            conv.setdefault(c, set()).add(chi)
        tutte_conv = {c for c, _ in conteggiate}
        a = sorted(c for c, chi in conv.items() if len(chi) >= (5 if "plenaria" in c else 3))
        richiedenti = {chi for _, chi in agenti}
        b = len(conteggiate) >= 3 and len(tutte_conv) >= 2 and len(richiedenti) >= 2
        soglia[sigla] = {"richieste": len(conteggiate), "convocazioni": len(tutte_conv),
                         "richiedenti": len(richiedenti), "contemporanea": a, "accumulata": b,
                         "da_creare": bool(a) or b}
    return soglia


def main():
    a = sys.argv[1:]
    try:
        if a[:1] == ["conta"] and len(a) == 3:
            try:
                giro = int(a[2])
            except ValueError:
                raise Errore("il giro è un intero ≥ 0")
            e = conta(a[1], giro)
            for d, v in sorted(e["decisioni"].items()):
                extra = ""
                if v.get("regressiva", {}).get("giro") == e["giro"]:
                    vg = v["regressiva"]["voti_del_giro"]
                    extra = f" (revisione regressiva scartata: sì del giro {len(vg['si'])}/{e['n']})"
                print(f"{d}: {v['stato']}{extra} — sì {len(v.get('si', []))}/{e['n']} — {v['opzione']}")
        elif a[:1] == ["richieste"] and len(a) <= 2:
            reg = a[1] if len(a) == 2 else str(BASE / "RICHIESTE_ESPERTI.md")
            s = richieste(reg)
            for sigla, v in sorted(s.items()):
                print(f"{sigla}: {v['richieste']} richieste, {v['convocazioni']} convocazioni, "
                      f"{v['richiedenti']} richiedenti — {'DA CREARE' if v['da_creare'] else 'sotto la soglia'}")
            if not s:
                print("nessuna richiesta aperta")
            sigle = sorted(s)
            vicine = [(x, y) for i, x in enumerate(sigle) for y in sigle[i + 1:] if x[:5] == y[:5]]
            for x, y in vicine:
                print(f"sigle vicine, da unire o da distinguere con un motivo: {x}, {y}")
        else:
            print(__doc__)
            sys.exit(2)
    except Errore as x:
        print(f"ERRORE: {x}")
        sys.exit(2)
    except (OSError, ValueError, KeyError, TypeError) as x:
        print(f"ERRORE: {type(x).__name__}: {x}")
        sys.exit(2)


if __name__ == "__main__":
    main()
