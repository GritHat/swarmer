#!/usr/bin/env python3
"""Sciame 4.0: prepara lo scheletro di una convocazione (singolo, ventaglio, classica o completa) e ne controlla i
cancelli. Giuria e plenaria si contano con giuria.py.

È la forma generale della convocazione a grafo. Restano:
- le corsie cieche, con i canarini e la mappa nota solo al coordinatore;
- la foto delle letture;
- i sigilli;
- i cancelli legati con lo sha256;
- la selezione solo dal triage;
- la chiusura anticipata dei rami.

Non lancia agenti e non approva niente da solo. Solo libreria standard, niente rete.

Comandi (i percorsi diventano assoluti):
  ruoli     [--domanda TESTO]     i ruoli e i profili; con la domanda, i ruoli le cui parole chiave vi compaiono
  prepara   --nome N --strategia singolo|ventaglio|classica|completa --profilo P --domanda TESTO [--ruoli a,b] [--dest D] [--seme S]
            [--n N --forma fette|gara|mista --regola primo|classifica|migliore]   (ventaglio)
  fotografa C                     appena le corsie hanno consegnato, prima di leggerle
  cancello  C FASE --note TESTO [--non-consegnati RUOLO,…] [--verifica]
            FASE = f0, f1, f2, f3/H-001, f4/H-001, f5
  sigilla   C FILE…               ora e sha256 in SIGILLI.jsonl
  seleziona C H-001 [H-002 H-003] [--radicale H-00x] [--responsabile SIGLA]
  chiudi-ramo C H-00x --motivo TESTO
  stato     C
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import random
import re
import secrets
import sys
from pathlib import Path

QUI = Path(__file__).resolve().parent
BASE = QUI.parent if QUI.name == "motore" else QUI  # la cartella dello sciame, dove sta catalogo.json
VERSIONE = "4.0"
STRATEGIE = ("singolo", "ventaglio", "classica", "completa")
FORME = ("fette", "gara", "mista")
REGOLE = ("primo", "classifica", "migliore")
CAMPI_CONTRATTO = ("Domanda", "Criterio", "Ingressi", "Vincoli", "Esclusioni", "Quota", "Profilo")
CAMPI_EN = {"Domanda": "Question", "Criterio": "Criterion", "Ingressi": "Inputs", "Vincoli": "Constraints",
            "Esclusioni": "Exclusions", "Quota": "Budget", "Profilo": "Profile"}
DA_COMPILARE = "<da compilare>"
DA_COMPILARE_EN = "<to fill in>"


def LINGUA() -> str:
    """La lingua dello sciame (sciame/LINGUA, o SCIAME_LINGUA): le consegne e il contratto si scrivono in quella."""
    import os
    l = os.environ.get("SCIAME_LINGUA") or ((BASE / "LINGUA").read_text(encoding="utf-8").strip()
                                             if (BASE / "LINGUA").is_file() else "it")
    return "en" if l == "en" else "it"


T = {
    "it": {"consegna": "Consegna", "fase": "fase", "agente": "Agente", "convocazione": "Convocazione",
           "strategia": "strategia", "profilo": "profilo", "domanda": "Domanda", "ingressi": "Ingressi (leggi solo questi):",
           "uscita": "Uscita", "uscita_coda": "al più due pagine; `stato.md` nella stessa cartella se lavori più di dieci minuti.",
           "tempo": "Tempo", "tempo_coda": "minuti. Prove al più di classe 1 (cinque minuti ciascuna) salvo diversa indicazione.",
           "al_piu": "al più", "scrivi": "Scrivi solo in", "scrivi_coda": "Niente modifiche al progetto, niente git, niente segreti.",
           "vietato": "Spazio vietato:", "vietato_coda": "le cartelle degli altri agenti della convocazione, e ciò che il contratto esclude.",
           "criterio": "Criterio di fatto:", "criterio_coda": "quello del contratto; se la missione qui sotto ne dà uno più stretto, vale quello.",
           "esito": "Esito in testa alla consegna:", "esito_coda": "FATTO, PROBLEMI o BLOCCATO, con le prove (regola 11 del preambolo).",
           "canarino": "(La prima riga della tua consegna deve essere questa riga del canarino.)",
           "che_cosa": "Che cosa fare", "contratto": "Contratto della convocazione", "creato": "Creato",
           "principi": "Principi del progetto", "principi_testo": "Quelli che non si negoziano, se ci sono; altrimenti «nessuno oltre il preambolo».",
           "fetta": "Fetta {k} di {n}: <da compilare>"},
    "en": {"consegna": "Brief", "fase": "phase", "agente": "Agent", "convocazione": "Convening",
           "strategia": "strategy", "profilo": "profile", "domanda": "Question", "ingressi": "Inputs (read only these):",
           "uscita": "Output", "uscita_coda": "two pages at most; `stato.md` in the same folder if you work more than ten minutes.",
           "tempo": "Time", "tempo_coda": "minutes. Tests of class 1 at most (five minutes each) unless stated otherwise.",
           "al_piu": "at most", "scrivi": "Write only in", "scrivi_coda": "No changes to the project, no git, no secrets.",
           "vietato": "Forbidden scope:", "vietato_coda": "the folders of the other agents of the convening, and what the contract excludes.",
           "criterio": "Done criterion:", "criterio_coda": "the contract's; if the mission below gives a stricter one, that one holds.",
           "esito": "Outcome at the top of the deliverable:", "esito_coda": "DONE, ISSUES or BLOCKED, with the evidence (rule 11 of the preamble).",
           "canarino": "(The first line of your deliverable must be this canary line.)",
           "che_cosa": "What to do", "contratto": "Contract of the convening", "creato": "Created",
           "principi": "Project principles", "principi_testo": "The non-negotiable ones, if any; otherwise «none beyond the preamble».",
           "fetta": "Slice {k} of {n}: <to fill in>"},
}
ID = re.compile(r"\bH-?0*(\d{1,3})\b")
LIMITE_F1 = 40  # minuti per una consegna di f1
LIMITE_RAMO = 60


class Errore(Exception):
    pass


def ora() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def norm_id(s: str) -> str:
    m = re.fullmatch(r"H-?0*(\d{1,3})", s.strip(), re.I)
    if not m:
        raise Errore(f"ID malformato: {s} (la forma è H-001)")
    return f"H-{int(m.group(1)):03d}"


def catalogo() -> dict:
    """I ruoli e i profili: il catalogo accanto a questo script, fatto da genera_agenti.py."""
    p = BASE / "catalogo.json"
    if not p.exists():
        raise Errore(f"non trovo {p}: lo scrive bash sciame/sciame.sh rigenera")
    return json.loads(p.read_text(encoding="utf-8"))


def carica(c: Path) -> dict:
    p = c / "MANIFESTO.json"
    if not p.exists():
        raise Errore(f"{c} non è una convocazione (manca MANIFESTO.json)")
    return json.loads(p.read_text(encoding="utf-8"))


def salva(c: Path, m: dict) -> None:
    (c / "MANIFESTO.json").write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def traduci_missione(testo: str) -> str:
    """La missione in inglese, dalla tabella motore/missioni_en.json: le chiavi sono i testi italiani, con i segnaposto
    {…} che si ritrovano nel testo; il resto dopo la missione (per esempio la fetta) si conserva."""
    tabella = QUI / "missioni_en.json"
    if not tabella.is_file():
        return testo
    for it, en in json.loads(tabella.read_text(encoding="utf-8")).items():
        pezzi = re.split(r"\{[^{}]*\}", it)
        rx = "(.+?)".join(re.escape(x) for x in pezzi)
        m = re.match(rx + r"(.*)\Z", testo, re.S)
        if m:
            gruppi = m.groups()
            return en.format(*gruppi[:-1]) + gruppi[-1]
    return testo


def consegna(m: dict, c: Path, cartella: Path, ruolo: str, fase: str, uscita: str, missione: str, ingressi: list[Path],
             *, canarino: str | None = None, minuti: int = LIMITE_F1, h: str | None = None) -> Path:
    cartella.mkdir(parents=True, exist_ok=True)
    x = T[LINGUA()]
    if LINGUA() == "en":
        missione = traduci_missione(missione)
    righe = []
    if canarino:
        righe += [f"Canarino: {canarino}", "", x["canarino"], ""]
    righe += [
        f"# {x['consegna']}: {ruolo}, {x['fase']} {fase}" + (f", {h}" if h else ""),
        "",
        f"- **{x['agente']}:** `sciame-{ruolo}`",
        f"- **{x['convocazione']}:** {m['nome']} ({x['strategia']} {m['strategia']}, {x['profilo']} {m['profilo']})",
        f"- **{x['domanda']}:** {m['domanda']}",
        f"- **{x['ingressi']}**",
        *[f"  - `{p}`" for p in ingressi],
        f"- **{x['uscita']}:** `{cartella / uscita}`, {x['uscita_coda']}",
        f"- **{x['tempo']}:** {x['al_piu']} {minuti} {x['tempo_coda']}",
        f"- **{x['scrivi']}** `{cartella}`. {x['scrivi_coda']}",
        f"- **{x['vietato']}** {x['vietato_coda']}",
        f"- **{x['criterio']}** {x['criterio_coda']}",
        f"- **{x['esito']}** {x['esito_coda']}",
        "",
        f"## {x['che_cosa']}",
        "",
        missione,
        "",
    ]
    (cartella / "TASK.md").write_text("\n".join(righe), encoding="utf-8")
    return cartella / "TASK.md"


def contratto(m: dict) -> str:
    l = LINGUA()
    x = T[l]
    righe = [f"# {x['contratto']} {m['nome']}", "", f"{x['strategia'].capitalize()}: {m['strategia']}. {x['creato']}: {m['creato']}.", ""]
    valori = {"Domanda": m["domanda"], "Profilo": m["profilo"]}
    for campo in CAMPI_CONTRATTO:
        righe += [f"## {CAMPI_EN[campo] if l == 'en' else campo}", "",
                  valori.get(campo, DA_COMPILARE_EN if l == "en" else DA_COMPILARE), ""]
    righe += [f"## {x['principi']}", "", x["principi_testo"], ""]
    return "\n".join(righe)


MISSIONI = {
    "A": "Sei nella corsia A, conservativa. Diagnosi del problema e dei vincoli; due proposte, ciascuna con l'enunciato, il "
         "guadagno atteso, i vincoli, chi la può provare e il falsificatore più economico (al più cinque minuti) con "
         "l'esito atteso scritto prima in PREVISIONI.md.",
    "B": "Sei nella corsia B, divergente. Il creativo: al più quattro idee da campi lontani, ciascuna con il meccanismo "
         "tradotto e il test. Il rovesciatore: al più due rovesciamenti dei presupposti, ciascuno con l'alternativa "
         "concreta e il test. Ogni idea con il falsificatore più economico in PREVISIONI.md.",
    "tutti": "Tornata globale, dal tuo punto di vista: al più tre osservazioni o proposte, ciascuna con la prova o il "
             "falsificatore. Se il tuo campo non c'entra, scrivi «non pertinente: …» in una riga. Al più mezza pagina.",
    "singolo": "Esegui la richiesta nel tuo ruolo, per intero, e rileggiti con le tue «domande che si pone sempre» prima di "
               "consegnare.",
    "fetta": "Sei un agente di un ventaglio, con una fetta del lavoro: la tua è scritta qui sotto dal coordinatore. Fai solo "
             "la tua fetta, per intero, e verifica il criterio di fatto prima di consegnare.",
    "gara": "Sei un braccio di una gara: altri agenti hanno la tua stessa consegna, e il coordinatore sceglierà con la regola "
            "dichiarata nel contratto. Lavora da solo, per intero, e verifica il criterio di fatto prima di consegnare.",
}


def ruoli(ns) -> None:
    """I ruoli, e i profili. Con una domanda, solo i ruoli di cui una parola chiave compare nel testo, per intero."""
    cat = catalogo()
    nuclei = {n["id"]: n["nome"].lower() for n in cat["nuclei"]}
    testo = (ns.domanda or "").lower()
    trovati = 0
    for r in cat["ruoli"]:
        parole = list(dict.fromkeys(p.lower() for p in r["parole"]
                                    if re.search(rf"(?<!\w){re.escape(p.lower())}(?!\w)", testo))) if testo else []
        if testo and not parole:
            continue
        trovati += 1
        print(f"sciame-{r['sigla']}: {r['nome']} (nucleo {nuclei[r['nucleo']]})" + (f"; parole: {', '.join(parole)}" if parole else ""))
    if testo and not trovati:
        print("Nessuna parola chiave dei ruoli compare nella domanda: scegli dal profilo.")
    print("Profili:")
    for nome, p in cat["profili"].items():
        print(f"  {nome}: {p['per']} (corsia A: {', '.join(p['A'])})")


def prepara(ns) -> None:
    cat = catalogo()
    sigle = {r["sigla"] for r in cat["ruoli"]}
    if ns.profilo not in cat["profili"]:
        raise Errore(f"profilo sconosciuto: {ns.profilo} (sono: {', '.join(cat['profili'])})")
    extra = [r.strip() for r in (ns.ruoli or "").split(",") if r.strip()]
    for r in extra:
        if r not in sigle:
            raise Errore(f"ruolo sconosciuto: {r}")
    prof = cat["profili"][ns.profilo]
    seme = ns.seme if ns.seme is not None else secrets.randbelow(10**9)
    rnd = random.Random(seme)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    nome = re.sub(r"[^A-Za-z0-9_-]+", "-", ns.nome).strip("-")[:40] or "convocazione"
    dest = Path(ns.dest).resolve()
    c = dest / f"{stamp}-{nome}"
    if c.exists():
        raise Errore(f"esiste già {c}")
    c.mkdir(parents=True)
    m = {"versione": VERSIONE, "nome": nome, "strategia": ns.strategia, "profilo": ns.profilo, "domanda": ns.domanda,
         "seme": seme, "creato": ora(), "f1": {}, "selezionate": [], "radicale": None}
    (c / "CONTRATTO.md").write_text(contratto(m), encoding="utf-8")
    (c / "f0").mkdir()
    ingressi = [c / "CONTRATTO.md"]
    mappa = {}
    if ns.strategia == "ventaglio":
        if not ns.n or ns.n < 2 or ns.n > 16:
            raise Errore("il ventaglio vuole --n fra 2 e 16")
        if ns.forma not in FORME or (ns.forma != "fette" and ns.regola not in REGOLE):
            raise Errore("il ventaglio vuole --forma fette|gara|mista e, per gara e mista, --regola primo|classifica|migliore")
        m["ventaglio"] = {"n": ns.n, "forma": ns.forma, "regola": ns.regola}
        ruoli_v = extra or prof["A"][:1]
        for k in range(1, ns.n + 1):
            ruolo = ruoli_v[(k - 1) % len(ruoli_v)]
            cartella = c / "f1" / f"agente-{k}"
            consegna(m, c, cartella, ruolo, "f1", "CONSEGNA.md", MISSIONI["gara" if ns.forma == "gara" else "fetta"]
                     + ("" if ns.forma == "gara" else "\n\n" + T[LINGUA()]["fetta"].format(k=k, n=ns.n)), ingressi)
            m["f1"][f"agente-{k}"] = {"cartella": str(cartella), "corsia": ns.forma, "ruolo": ruolo}
    elif ns.strategia == "singolo":
        ruolo = extra[0] if extra else prof["A"][0]
        consegna(m, c, c / "f1" / ruolo, ruolo, "f1", "CONSEGNA.md", MISSIONI["singolo"], ingressi)
        m["f1"][ruolo] = {"cartella": str(c / "f1" / ruolo), "corsia": "singolo"}
    else:
        if ns.strategia == "classica":
            corsie = {"A": list(dict.fromkeys(prof["A"] + [r for r in extra if r not in prof["B"]])), "B": prof["B"]}
        else:
            # La tornata globale è dei professionisti; i sottoprofessionisti entrano solo se nominati.
            corsie = {"tutti": [r["sigla"] for r in cat["ruoli"] if r["sigla"] != "arbitro"
                                and (r.get("tipo", "professionista") == "professionista" or r["sigla"] in extra)]}
        canarini = {}
        for corsia, ruoli in corsie.items():
            for ruolo in ruoli:
                cartella = c / "f1" / secrets.token_hex(6)
                # Nella classica un canarino per corsia, nella completa uno per ruolo: ognuno è cieco agli altri.
                chiave = corsia if ns.strategia == "classica" else ruolo
                canarini.setdefault(chiave, f"sciame-canarino-{secrets.token_hex(8)}")
                consegna(m, c, cartella, ruolo, "f1", "CONSEGNA.md", MISSIONI[corsia], ingressi, canarino=canarini[chiave])
                mappa[ruolo] = {"cartella": str(cartella), "corsia": corsia, "canarino": canarini[chiave]}
                m["f1"][ruolo] = {"cartella": str(cartella), "corsia": corsia}
        if ns.strategia == "completa":
            consegna(m, c, c / "f1c" / "arbitro", "arbitro", "f1c", "CONSOLIDAMENTO.md",
                     "Consolida i contributi della tornata globale, prima per nucleo e poi d'insieme: fatti F# con lo stato, "
                     "contraddizioni K#, idee candidate con l'origine (ruolo e file), domande aperte, ruoli da chiamare dopo. "
                     "Niente voto. Le idee candidate entreranno in f2 come schede d'ingresso.",
                     ingressi + [Path(v["cartella"]) / "CONSEGNA.md" for v in mappa.values()], minuti=60)
        f1_consegne = [Path(v["cartella"]) / "CONSEGNA.md" for v in m["f1"].values()]
        if ns.strategia == "completa":
            f1_consegne = [c / "f1c" / "arbitro" / "CONSOLIDAMENTO.md"]
        traduttore = next((r for r in prof["traduce"] + ["formalista", "logico"] if r not in m["f1"]), "logico")
        f2 = c / "f2"
        consegna(m, c, f2 / "01-traduzione", traduttore, "f2", "SCHEDE.md",
                 "Una scheda per idea: oggetto, enunciato preciso, tipo, rischi, ipotesi critica e controesempio candidato, "
                 "come la si verifica. Niente fusioni: due idee sono la stessa solo se enunciato e tipo coincidono. Ogni "
                 "scheda dice da quale consegna viene.", ingressi + f1_consegne, minuti=40)
        (f2 / "02-firme").mkdir(parents=True)
        (f2 / "02-firme" / "LEGGIMI.md").write_text(
            "Ogni autore di f1 scrive qui `<sigla>.md`: per ogni scheda nata dalle sue idee, «fedele» oppure «si perde: …».\n",
            encoding="utf-8")
        consegna(m, c, f2 / "03-triage", "arbitro", "f2", "TRIAGE.md",
                 "Assegna gli H# nella forma H-001, con la classe TESTARE, RIFORMULARE, APERTA o SMENTITA (solo con una prova), "
                 "e le prime tre in ordine. Il coordinatore sigilla il triage appena arriva.",
                 ingressi + [f2 / "01-traduzione" / "SCHEDE.md", f2 / "02-firme"], minuti=30)
        consegna(m, c, f2 / "04-torneo", "avversario", "f2", "TORNEO.md",
                 "Esegui il falsificatore di ogni H# TESTARE o APERTA del triage sigillato, al più cinque minuti ciascuno, "
                 "con l'esito atteso registrato prima. Una smentita vale per l'idea solo se la decide un controllo che non "
                 "condivide il prototipo; altrimenti l'H# torna RIFORMULARE.",
                 ingressi + [f2 / "03-triage" / "TRIAGE.md", f2 / "01-traduzione" / "SCHEDE.md"], minuti=40)
        consegna(m, c, f2 / "05-selezione", "arbitro", "f2", "SELEZIONE.md",
                 "Sugli esiti del torneo proponi al più tre H# più una radicale, con le priorità ordinali (informazione attesa, "
                 "costo, probabilità di un controesempio). Chiudi con la riga «Controfirma: arbitro».",
                 ingressi + [f2 / "03-triage" / "TRIAGE.md", f2 / "04-torneo" / "TORNEO.md"], minuti=20)
    (c / "f5").mkdir()
    if mappa:
        nascosta = dest / f".{c.name}.corsie"
        nascosta.mkdir(mode=0o700)
        (nascosta / "MAPPA.json").write_text(json.dumps(mappa, ensure_ascii=False, indent=1), encoding="utf-8")
        m["mappa"] = str(nascosta / "MAPPA.json")
    salva(c, m)
    print(f"Convocazione: {c}")
    print(f"Strategia {ns.strategia}, profilo {ns.profilo}, seme {seme}. Nessun agente lanciato.")
    print("Compila CONTRATTO.md, poi: cancello C f0 --note '…'")
    print("Consegne di f1:")
    for ruolo, v in m["f1"].items():
        print(f"  {ruolo} ({v['corsia']}): {v['cartella']}/TASK.md")
    if mappa:
        print(f"Mappa delle corsie (solo tua, non darla agli agenti): {m['mappa']}")


def fotografa(ns) -> None:
    c = Path(ns.C).resolve()
    m = carica(c)
    foto = {"ora": ora(), "file": {}}
    for v in m["f1"].values():
        for p in sorted(Path(v["cartella"]).rglob("*")):
            if p.is_file():
                s = p.stat()
                foto["file"][str(p)] = {"mtime": s.st_mtime, "letto_dopo": s.st_atime > s.st_mtime}
    (c / "FOTO.json").write_text(json.dumps(foto, indent=1), encoding="utf-8")
    letti = [p for p, v in foto["file"].items() if v["letto_dopo"] and not p.endswith("TASK.md")]
    print(f"Foto di {len(foto['file'])} file. Letti dopo l'ultima scrittura: {len(letti)}")
    for p in letti:
        print(f"  {p}")


def sigilla(ns) -> None:
    c = Path(ns.C).resolve()
    carica(c)
    with (c / "SIGILLI.jsonl").open("a", encoding="utf-8") as f:
        for nome in ns.file:
            p = Path(nome).resolve()
            if not p.is_file():
                raise Errore(f"non c'è {p}")
            f.write(json.dumps({"ora": ora(), "file": str(p), "sha256": sha(p), "byte": p.stat().st_size}) + "\n")
            print(f"Sigillato {p}")


def sigilli(c: Path) -> dict[str, dict]:
    p = c / "SIGILLI.jsonl"
    trovati = {}
    for riga in p.read_text(encoding="utf-8").splitlines() if p.exists() else []:
        s = json.loads(riga)
        trovati.setdefault(s["file"], s)
    return trovati


def ids_in(p: Path) -> list[str]:
    if not p.exists():
        return []
    return list(dict.fromkeys(f"H-{int(n):03d}" for n in ID.findall(p.read_text(encoding="utf-8"))))


def pieno(p: Path) -> bool:
    testo = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
    return p.is_file() and p.stat().st_size > 0 and DA_COMPILARE not in testo and DA_COMPILARE_EN not in testo


def cartelle_fase(c: Path, m: dict, fase: str) -> list[Path]:
    if fase == "f0":
        return [c / "f0"]
    if fase == "f1":
        return [Path(v["cartella"]) for v in m["f1"].values()] + ([c / "f1c"] if m["strategia"] == "completa" else [])
    if fase in ("f2", "f5"):
        return [c / fase]
    return [c / fase]


def impronte(c: Path, m: dict, fase: str) -> dict[str, str]:
    file = [c / "CONTRATTO.md"] if fase == "f0" else []
    for cartella in cartelle_fase(c, m, fase):
        file += sorted(p for p in cartella.rglob("*.md") if p.is_file())
    if fase.startswith("f3/") or fase.startswith("f4/"):
        file += sorted(p for p in cartella.rglob("*.json") if p.is_file() and not p.name.startswith("GATE_"))
    return {str(p): sha(p) for p in file}


def file_gate(c: Path, fase: str) -> Path:
    return c / f"GATE_{fase.replace('/', '_')}.json"


def valido(c: Path, m: dict, fase: str) -> bool:
    p = file_gate(c, fase)
    if not p.exists():
        return False
    g = json.loads(p.read_text(encoding="utf-8"))
    return g.get("impronte") == impronte(c, m, fase)


def condizioni(c: Path, m: dict, fase: str, non_consegnati: set[str]) -> list[str]:
    errori = []
    precedente = {"f1": "f0", "f2": "f1", "f5": "f2"}.get(fase)
    if fase.startswith("f3/"):
        precedente = "f2"
    elif fase.startswith("f4/"):
        precedente = "f3/" + fase[3:]
    if m["strategia"] in ("singolo", "ventaglio") and fase == "f5":
        precedente = "f1"
    if precedente and not valido(c, m, precedente):
        errori.append(f"il cancello {precedente} non è approvato o non è più valido")
    if fase == "f0":
        testo = (c / "CONTRATTO.md").read_text(encoding="utf-8")
        for campo in CAMPI_CONTRATTO:
            sezione = (re.search(rf"^## {campo}\n(.*?)(?=^## |\Z)", testo, re.S | re.M)
                       or re.search(rf"^## {CAMPI_EN[campo]}\n(.*?)(?=^## |\Z)", testo, re.S | re.M))
            if not sezione or not sezione.group(1).strip() or DA_COMPILARE in sezione.group(1) or DA_COMPILARE_EN in sezione.group(1):
                errori.append(f"CONTRATTO.md: «{campo}» da compilare")
    elif fase == "f1":
        mappa = json.loads(Path(m["mappa"]).read_text(encoding="utf-8")) if m.get("mappa") else {}
        ultima = 0.0
        for ruolo, v in m["f1"].items():
            uscita = Path(v["cartella"]) / "CONSEGNA.md"
            if ruolo in non_consegnati:
                continue
            if not pieno(uscita):
                errori.append(f"{ruolo}: manca la consegna {uscita}")
                continue
            ultima = max(ultima, uscita.stat().st_mtime)
            testo = uscita.read_text(encoding="utf-8", errors="replace")
            if ruolo in mappa:
                proprio = mappa[ruolo]["canarino"]
                if not testo.lstrip().startswith(f"Canarino: {proprio}"):
                    errori.append(f"{ruolo}: la consegna non comincia con il suo canarino")
                altri = {v2["canarino"] for r2, v2 in mappa.items() if v2["canarino"] != proprio}
                if any(a in testo for a in altri):
                    errori.append(f"{ruolo}: nella consegna c'è il canarino di un'altra corsia (contaminazione)")
        if mappa:
            foto = c / "FOTO.json"
            if not foto.exists():
                errori.append("manca la foto delle letture: fotografa C, prima di leggere")
            elif _iso(json.loads(foto.read_text(encoding="utf-8"))["ora"]) < ultima - 1:
                errori.append("la foto è anteriore all'ultima consegna: rifalla")
        if m["strategia"] == "completa" and not pieno(c / "f1c" / "arbitro" / "CONSOLIDAMENTO.md"):
            errori.append("manca il consolidamento dell'arbitro (f1c/arbitro/CONSOLIDAMENTO.md)")
    elif fase == "f2":
        f2 = c / "f2"
        for p in (f2 / "01-traduzione" / "SCHEDE.md", f2 / "03-triage" / "TRIAGE.md", f2 / "04-torneo" / "TORNEO.md",
                  f2 / "05-selezione" / "SELEZIONE.md"):
            if not pieno(p):
                errori.append(f"manca {p.relative_to(c)}")
        firme = [p for p in (f2 / "02-firme").glob("*.md") if p.name != "LEGGIMI.md"]
        if not firme:
            errori.append("nessuna firma degli autori in f2/02-firme")
        triage = f2 / "03-triage" / "TRIAGE.md"
        s = sigilli(c).get(str(triage))
        if triage.exists():
            if not s:
                errori.append("il triage non è sigillato: sigilla C f2/03-triage/TRIAGE.md")
            else:
                if s["sha256"] != sha(triage):
                    errori.append("il triage è cambiato dopo il sigillo")
                if any(p.stat().st_mtime > _iso(s["ora"]) + 1 for p in firme):
                    errori.append("una firma è arrivata dopo il sigillo del triage")
                torneo = f2 / "04-torneo" / "TORNEO.md"
                if torneo.exists() and torneo.stat().st_mtime < _iso(s["ora"]):
                    errori.append("il torneo è anteriore al sigillo del triage")
        selezione = f2 / "05-selezione" / "SELEZIONE.md"
        if selezione.exists():
            fuori = set(ids_in(selezione)) - set(ids_in(triage))
            if fuori:
                errori.append(f"la selezione nomina H# che il triage non ha: {', '.join(sorted(fuori))}")
            if "Controfirma: arbitro" not in selezione.read_text(encoding="utf-8"):
                errori.append("la selezione non ha la riga «Controfirma: arbitro»")
    elif fase.startswith("f3/") or fase.startswith("f4/"):
        h = fase[3:]
        if h not in m["selezionate"] + ([m["radicale"]] if m["radicale"] else []):
            errori.append(f"{h} non è selezionata")
        if (c / "f3" / h / "CHIUSURA_ANTICIPATA.json").exists():
            errori.append(f"il ramo {h} è chiuso in anticipo: niente G3 né G4")
        cartella = c / fase
        if fase.startswith("f3/"):
            for nome in ("SOLUZIONE.md", "VERIFICA.md", "PIANO_MISURE.md", "ATTACCO.md", "PREVISIONI.md"):
                if not any(pieno(p) for p in cartella.rglob(nome)):
                    errori.append(f"{fase}: manca {nome}")
            for p in cartella.rglob("PREVISIONI.md"):
                if not re.search(r"^decide: (sì|si|no)\s*$", p.read_text(encoding="utf-8"), re.M):
                    errori.append(f"{p.relative_to(c)}: manca la riga «decide: sì» o «decide: no»")
        else:
            for nome in ("CONTROPROVE.md", "VERDETTO.md"):
                if not any(pieno(p) for p in cartella.rglob(nome)):
                    errori.append(f"{fase}: manca {nome}")
            sig = sigilli(c)
            controprove = [p for p in cartella.rglob("CONTROPROVE.md")]
            for p in cartella.rglob("PREVISIONI.md"):
                s = sig.get(str(p))
                if not s:
                    errori.append(f"{p.relative_to(c)} nata in f4 non è sigillata")
                elif sha(p) != s["sha256"] and not _solo_coda(p, s):
                    errori.append(f"{p.relative_to(c)} è cambiata dopo il sigillo, non solo in coda")
                elif any(q.stat().st_mtime < _iso(s["ora"]) for q in controprove):
                    errori.append(f"{p.relative_to(c)} è sigillata dopo le controprove")
            dossier = c / "f3" / h / f"{h}.md"
            if dossier.exists():
                vuoti = [r for r in dossier.read_text(encoding="utf-8").splitlines() if re.match(r"^- [^|]*:\s*$", r)]
                if vuoti:
                    errori.append(f"il dossier {h} ha {len(vuoti)} campi vuoti (si scrive «manca»)")
            else:
                errori.append(f"manca il dossier {dossier.relative_to(c)}")
    elif fase == "f5":
        chiusura = c / "f5" / "CHIUSURA.md"
        if not pieno(chiusura):
            errori.append("manca f5/CHIUSURA.md dell'arbitro")
        elif not re.search(r"^Esito: (chiuso|non chiuso)\b", chiusura.read_text(encoding="utf-8"), re.M):
            errori.append("CHIUSURA.md senza la riga «Esito: chiuso» o «Esito: non chiuso»")
        if m["strategia"] not in ("singolo", "ventaglio"):
            rami = m["selezionate"] + ([m["radicale"]] if m["radicale"] else [])
            provati = [h for h in rami if valido(c, m, f"f4/{h}")]
            aperti = [h for h in rami if h not in provati and not (c / "f3" / h / "CHIUSURA_ANTICIPATA.json").exists()]
            if aperti:
                errori.append(f"rami senza G4 valido né chiusura anticipata: {', '.join(aperti)}")
            if rami and not provati:
                errori.append("nessuna H# provata: il ciclo non si chiude con un G5")
    return errori


def _iso(s: str) -> float:
    return datetime.datetime.fromisoformat(s).timestamp()


def _solo_coda(p: Path, s: dict) -> bool:
    """Il sigillo vale ancora se al file si è solo aggiunto in coda: i primi byte sono quelli sigillati."""
    dati = p.read_bytes()
    byte = s.get("byte")
    return byte is not None and len(dati) >= byte and hashlib.sha256(dati[:byte]).hexdigest() == s["sha256"]


def cancello(ns) -> None:
    c = Path(ns.C).resolve()
    m = carica(c)
    fase = ns.fase
    if not re.fullmatch(r"f[0125]|f[34]/H-\d{3}", fase):
        raise Errore(f"fase sconosciuta: {fase}")
    non = {r.strip() for r in (ns.non_consegnati or "").split(",") if r.strip()}
    errori = condizioni(c, m, fase, non)
    if errori:
        print(f"Cancello {fase} RIFIUTATO:")
        for e in errori:
            print(f"  - {e}")
        sys.exit(1)
    if ns.verifica:
        print(f"Cancello {fase}: le condizioni reggono (verifica, niente scritto)")
        return
    g = {"fase": fase, "ora": ora(), "note": ns.note, "non_consegnati": sorted(non), "impronte": impronte(c, m, fase)}
    file_gate(c, fase).write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Cancello {fase} approvato ({len(g['impronte'])} file legati)")


def seleziona(ns) -> None:
    c = Path(ns.C).resolve()
    m = carica(c)
    if m["strategia"] in ("singolo", "ventaglio"):
        raise Errore("nel singolo non ci sono ipotesi da selezionare")
    if not valido(c, m, "f2"):
        raise Errore("il cancello f2 non è approvato o non è più valido")
    scelte = [norm_id(h) for h in ns.ipotesi]
    radicale = norm_id(ns.radicale) if ns.radicale else None
    if len(scelte) > 3:
        raise Errore("al più tre H# più una radicale")
    ammesse = set(ids_in(c / "f2" / "03-triage" / "TRIAGE.md")) & set(ids_in(c / "f2" / "05-selezione" / "SELEZIONE.md"))
    for h in scelte + ([radicale] if radicale else []):
        if h not in ammesse:
            raise Errore(f"{h} non è nel triage e nella selezione controfirmata")
    cat = catalogo()
    prof = cat["profili"][m["profilo"]]
    if ns.responsabile and ns.responsabile not in {r["sigla"] for r in cat["ruoli"]}:
        raise Errore(f"ruolo sconosciuto: {ns.responsabile}")
    modello = (BASE / "SCHEDA_IPOTESI.md").read_text(encoding="utf-8")
    ingressi_base = [c / "CONTRATTO.md", c / "f2" / "01-traduzione" / "SCHEDE.md", c / "f2" / "03-triage" / "TRIAGE.md",
                     c / "f2" / "04-torneo" / "TORNEO.md"]
    for h in scelte + ([radicale] if radicale else []):
        f3, f4 = c / "f3" / h, c / "f4" / h
        f3.mkdir(parents=True, exist_ok=True)
        (f3 / f"{h}.md").write_text(modello.replace("H-000", h), encoding="utf-8")
        responsabile = ns.responsabile or prof["f3"][0]
        verifica = next((r for r in prof["f3"][1:] if r not in ("avversario", "metrologo", responsabile)), "logico")
        consegna(m, c, f3 / f"01-{responsabile}", responsabile, "f3", "SOLUZIONE.md",
                 f"Sei il responsabile di {h}. Scrivi la soluzione: passi, invarianti, costo, «dipende da», «invalidata se "
                 "cambia». Le previsioni con la soglia in PREVISIONI.md, con la riga «decide: sì» o «decide: no».",
                 ingressi_base, minuti=LIMITE_RAMO, h=h)
        consegna(m, c, f3 / f"02-{verifica}", verifica, "f3", "VERIFICA.md",
                 f"Scrivi la prova o la verifica di {h}, dopo SOLUZIONE.md del responsabile: che cosa la rende corretta, con "
                 "quali ipotesi, e come la si controlla.", ingressi_base + [f3 / f"01-{responsabile}" / "SOLUZIONE.md"],
                 minuti=LIMITE_RAMO, h=h)
        consegna(m, c, f3 / "03-metrologo", "metrologo", "f3", "PIANO_MISURE.md",
                 f"Il piano delle misure di {h}: che cosa si misura, con quale soglia, prima delle prove. Se non servono misure, "
                 "scrivilo con il perché.", ingressi_base + [f3 / f"01-{responsabile}" / "SOLUZIONE.md"], minuti=30, h=h)
        consegna(m, c, f3 / "04-avversario", "avversario", "f3", "ATTACCO.md",
                 f"L'attacco a {h}: i casi che dovrebbero romperla, con le previsioni prima.",
                 ingressi_base + [f3 / f"01-{responsabile}" / "SOLUZIONE.md"], minuti=30, h=h)
        consegna(m, c, f4 / "01-avversario", "avversario", "f4", "CONTROPROVE.md",
                 f"Esegui le controprove di {h}, dalla più economica: prima le falsificazioni, poi la correttezza, poi il controllo "
                 "dissimile. Le previsioni nate ora vanno sigillate dal coordinatore prima delle prove.",
                 ingressi_base + [f3], minuti=LIMITE_RAMO, h=h)
        consegna(m, c, f4 / "02-debugger", "debugger", "f4", "DIFETTI.md",
                 f"Le anomalie delle controprove di {h} e i difetti nascosti, ciascuno con la causa provata o «non spiegata». "
                 "Se non ci sono anomalie, elenca i controlli fatti.", ingressi_base + [f3, f4 / "01-avversario"], h=h)
        for i, ruolo in enumerate([r for r in prof["f4"] if r not in ("avversario", "debugger")], start=3):
            consegna(m, c, f4 / f"{i:02d}-{ruolo}", ruolo, "f4", "MISURE.md",
                     f"Il tuo contributo alle prove di {h}, sul piano delle misure, dopo le controprove.",
                     ingressi_base + [f3, f4 / "01-avversario"], h=h)
        consegna(m, c, f4 / "09-arbitro", "arbitro", "f4", "VERDETTO.md",
                 f"Il verdetto di {h} per proprietà (correttezza, completezza, efficacia, costo), e il dossier "
                 f"{f3 / (h + '.md')} completato campo per campo («manca» dove manca).", ingressi_base + [f3, f4], minuti=30, h=h)
    m["selezionate"], m["radicale"] = scelte, radicale
    salva(c, m)
    consegna(m, c, c / "f5" / "01-arbitro", "arbitro", "f5", "CHIUSURA.md",
             "La chiusura: almeno una H# provata, nessuna contraddizione aperta su una conclusione adottata, previsioni risolte o "
             "dichiarate non risolte con la prova che le deciderebbe, le quattro verifiche dei risultati fondanti. Scrivi anche "
             f"{c / 'f5' / 'CHIUSURA.md'} con la riga «Esito: chiuso» o «Esito: non chiuso», e al più tre decisioni per l'utente.",
             [c / "CONTRATTO.md", c / "f3", c / "f4"], minuti=30)
    print(f"Rami aperti: {', '.join(scelte + ([radicale] if radicale else []))}")


def chiudi_ramo(ns) -> None:
    c = Path(ns.C).resolve()
    m = carica(c)
    h = norm_id(ns.ipotesi)
    if h not in m["selezionate"] + ([m["radicale"]] if m["radicale"] else []):
        raise Errore(f"{h} non è selezionata")
    if valido(c, m, f"f3/{h}"):
        raise Errore(f"{h} ha già un G3: la chiusura anticipata vale solo prima")
    p = c / "f3" / h / "CHIUSURA_ANTICIPATA.json"
    if p.exists():
        raise Errore(f"{h} è già chiusa")
    p.write_text(json.dumps({"ora": ora(), "ipotesi": h, "motivo": ns.motivo, "stato": "non risolto dichiarato"},
                            ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{h} chiusa in anticipo: non risolto dichiarato")


def stato(ns) -> None:
    c = Path(ns.C).resolve()
    m = carica(c)
    print(f"{m['nome']}: strategia {m['strategia']}, profilo {m['profilo']}")
    fasi = ["f0", "f1"] + ([] if m["strategia"] in ("singolo", "ventaglio") else ["f2"])
    for h in m["selezionate"] + ([m["radicale"]] if m["radicale"] else []):
        fasi += [f"f3/{h}", f"f4/{h}"]
    if m["strategia"] not in ("singolo", "ventaglio"):
        fasi.append("f5")
    for fase in fasi:
        if fase.startswith("f3/") and (c / fase / "CHIUSURA_ANTICIPATA.json").exists():
            print(f"  {fase}: CHIUSO IN ANTICIPO")
            continue
        g = file_gate(c, fase)
        if not g.exists():
            print(f"  {fase}: da approvare")
        else:
            print(f"  {fase}: {'approvato' if valido(c, m, fase) else 'NON PIÙ VALIDO (file cambiati)'}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="comando", required=True)
    q = sp.add_parser("ruoli")
    q.add_argument("--domanda")
    q = sp.add_parser("prepara")
    q.add_argument("--nome", required=True)
    q.add_argument("--strategia", required=True, choices=STRATEGIE)
    q.add_argument("--profilo", required=True)
    q.add_argument("--domanda", required=True)
    q.add_argument("--ruoli")
    q.add_argument("--dest", default=".sciame")
    q.add_argument("--seme", type=int)
    q.add_argument("--n", type=int, help="ventaglio: il numero totale di agenti, da 2 a 16")
    q.add_argument("--forma", choices=FORME, help="ventaglio: fette, gara o mista")
    q.add_argument("--regola", choices=REGOLE, help="ventaglio, gara o mista: la regola di scelta dichiarata prima")
    q = sp.add_parser("fotografa")
    q.add_argument("C")
    q = sp.add_parser("cancello")
    q.add_argument("C")
    q.add_argument("fase")
    q.add_argument("--note", required=True)
    q.add_argument("--non-consegnati")
    q.add_argument("--verifica", action="store_true")
    q = sp.add_parser("sigilla")
    q.add_argument("C")
    q.add_argument("file", nargs="+")
    q = sp.add_parser("seleziona")
    q.add_argument("C")
    q.add_argument("ipotesi", nargs="+")
    q.add_argument("--radicale")
    q.add_argument("--responsabile", metavar="SIGLA")
    q = sp.add_parser("chiudi-ramo")
    q.add_argument("C")
    q.add_argument("ipotesi")
    q.add_argument("--motivo", required=True)
    q = sp.add_parser("stato")
    q.add_argument("C")
    ns = p.parse_args()
    comandi = {"ruoli": ruoli, "prepara": prepara, "fotografa": fotografa, "cancello": cancello, "sigilla": sigilla, "seleziona": seleziona,
               "chiudi-ramo": chiudi_ramo, "stato": stato}
    try:
        comandi[ns.comando](ns)
    except (Errore, OSError, ValueError) as e:
        print(f"convoca: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
