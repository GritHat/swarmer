#!/usr/bin/env python3
"""Batteria della giuria dello sciame 4.0 (GIURIA.md, motore/giuria.py): python3 -I prove/prova_giuria.py

Costruisce giurie finte in una cartella temporanea e controlla che giuria.py dia gli esiti del §3 (con la non
regressione, il limite, le dipendenze, le classi e le raccomandazioni) e che rifiuti gli attacchi trovati dalla
validazione del protocollo: ognuno ha qui il suo dente. Poi la soglia degli esperti del §4. Esce con 1 se un
controllo fallisce. Gli agenti sono finti, in una cartella temporanea (SCIAME_AGENTI).
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import os

QUI = Path(__file__).resolve().parent
GIURIA = QUI.parent / "motore" / "giuria.py"
RUOLI_FINTI = ["garante", "avversario", "logico", "debugger", "statistico", "rovesciatore", "creativo", "formalista",
               "fonti", "metrologo", "arbitro", "scelta-sociale", "prestazioni", "sviluppatore", "architetto"]
RUOLI5 = ["garante", "avversario", "logico", "debugger", "statistico"]
esiti = []


def sigilla(testo):
    corpo = testo if testo.endswith("\n") else testo + "\n"
    return corpo + "sha256 dei byte che precedono questa riga: " + hashlib.sha256(corpo.encode()).hexdigest() + "\n"


def sigillo_di(p):
    return Path(p).read_text().rstrip("\n").rsplit(" ", 1)[1]


def giuria(base, nome, giurati=None, **extra):
    c = Path(base) / nome
    c.mkdir()
    g = {"protocollo": "G1.1", "oggetto": nome, "relatore": "formalista", "cancelliere": "arbitro", "tocca_codice": True,
         "tocca_numeri": True, "autorita": "vincolante", "delega": "prova", "classificazione": "ordinaria",
         "giurati": giurati or [{"ruolo": r, "nuovo_sull_oggetto": True} for r in RUOLI5]}
    g.update(extra)
    for k in [k for k, v in g.items() if v is None]:
        del g[k]
    (c / "giuria.json").write_text(json.dumps(g), encoding="utf-8")
    (c / "SIGILLI.md").write_text("# sigilli riportati\n", encoding="utf-8")
    return c


def registra(c, rel):
    with open(c / "SIGILLI.md", "a", encoding="utf-8") as f:
        f.write(f"SIGILLO {rel} {sigillo_di(c / rel)}\n")


def registra_file(c, rel):
    with open(c / "SIGILLI.md", "a", encoding="utf-8") as f:
        f.write(f"SIGILLO {rel} {sigillo_di(c / rel)}\n")


def proposta(c, r, opzioni, dispositivo=None, extra="", opzioni_lista=None, registra_sigillo=True):
    d = c / f"giro_{r}"
    d.mkdir(exist_ok=True)
    corpo = "# proposta\n"
    for k, v in opzioni.items():
        corpo += f"OPZIONE {k} {v}\n"
        if r == 0:
            corpo += f"OPZIONI {k} {(opzioni_lista or {}).get(k, v + ' | (z)')}\n"
        corpo += f"DISPOSITIVO {k} {(dispositivo or {}).get(k, 'si fa ' + v)}\n"
    (d / "PROPOSTA.md").write_text(sigilla(corpo + extra), encoding="utf-8")
    if registra_sigillo:
        registra(c, f"giro_{r}/PROPOSTA.md")


def voto(c, r, ruolo, voti, senza=None, extra="", classe="ordinaria", cambio=(), registra_sigillo=True):
    righe = []
    for k, v in voti.items():
        righe.append(f"VOTO {k} {v}")
        if senza != k:
            righe.append(f"REVISIONE {k} togliere la clausola 2" if v == "no" else f"CONDIZIONE {k} nessuna")
        righe.append(f"CLASSE {k} {classe}")
        if k in cambio:
            righe.append(f"CAMBIO {k} la clausola 2 è tolta")
    (c / f"giro_{r}" / f"VOTO_{ruolo}.md").write_text(sigilla("\n".join(righe) + "\n" + extra), encoding="utf-8")
    if registra_sigillo:
        registra(c, f"giro_{r}/VOTO_{ruolo}.md")


def ruoli_di(c):
    return [x["ruolo"] for x in json.loads((c / "giuria.json").read_text())["giurati"]]


def vota_tutti(c, r, schema, prima=None):
    """schema: {decisione: numero di sì}; i primi k ruoli votano sì. prima: l'esito del giro precedente."""
    for i, ruolo in enumerate(ruoli_di(c)):
        v = {d: ("si" if i < k else "no") for d, k in schema.items()}
        cambio = [d for d in v if prima and v[d] == "si" and ruolo in prima.get(d, {}).get("no", [])]
        voto(c, r, ruolo, v, cambio=cambio)


def lancia(*arg):
    p = subprocess.run([sys.executable, "-I", "-B", str(GIURIA), *map(str, arg)], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, env=dict(os.environ, SCIAME_AGENTI=AGENTI_FINTI, SCIAME_G11_PROVE="1"))
    return p.returncode, p.stdout + p.stderr


def lancia_senza_prove(*arg):
    p = subprocess.run([sys.executable, "-I", "-B", str(GIURIA), *map(str, arg)], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, env=dict(os.environ, SCIAME_AGENTI=AGENTI_FINTI))
    return p.returncode, p.stdout + p.stderr


def esito(c, r):
    return json.loads((c / f"ESITO_giro_{r}.json").read_text())["decisioni"]


def prova(nome, ok, dettaglio=""):
    esiti.append((nome, bool(ok)))
    print(("ok   " if ok else "FALLITO ") + nome + ("" if ok or not dettaglio else f"\n     {dettaglio[:400]}"))


def rifiuta(nome, c, r=0, testo=None):
    rc, out = lancia("conta", c, r)
    prova(nome + " → rifiutato", rc == 2 and "ERRORE" in out and "Traceback" not in out
          and (testo is None or testo in out))


def semplice(base, nome, schema, **kw):
    c = giuria(base, nome, **kw)
    proposta(c, 0, {d: f"({d.lower()})" for d in schema})
    vota_tutti(c, 0, schema)
    return c


def batteria(base):
    # --- 1. i tre esiti e le classi finali
    c = semplice(base, "tre_esiti", {"D1": 5, "D2": 3, "D3": 2, "D4": 0})
    rc, _ = lancia("conta", c, 0)
    e = esito(c, 0) if rc == 0 else {}
    prova("consenso totale → APPROVATA", rc == 0 and e["D1"]["stato"] == "APPROVATA")
    prova("maggioranza 3/5 → REVISIONE", rc == 0 and e["D2"]["stato"] == "REVISIONE")
    prova("minoranza 2/5 → RESPINTA", rc == 0 and e["D3"]["stato"] == "RESPINTA")
    prova("consenso sul no → RESPINTA", rc == 0 and e["D4"]["stato"] == "RESPINTA")
    proposta(c, 1, {"D2": "(d2)"})
    vota_tutti(c, 1, {"D2": 5}, prima=e)
    rc, _ = lancia("conta", c, 1)
    e1 = esito(c, 1) if rc == 0 else {}
    prova("giro 1, consenso con le righe CAMBIO → APPROVATA", rc == 0 and e1["D2"]["stato"] == "APPROVATA")
    prova("le decisioni chiuse al giro 0 restano", rc == 0 and e1["D1"]["stato"] == "APPROVATA"
          and e1["D3"]["stato"] == "RESPINTA")
    rc, _ = lancia("conta", c, 1)
    prova("conta ripetuto senza cambiamenti è idempotente", rc == 0)

    c = semplice(base, "raccomandazione", {"D1": 5}, autorita="raccomandazione")
    rc, _ = lancia("conta", c, 0)
    prova("voce riservata: consenso → RACCOMANDATA, non APPROVATA", rc == 0 and esito(c, 0)["D1"]["stato"] == "RACCOMANDATA")
    c = giuria(base, "classe_plenaria")
    proposta(c, 0, {"D1": "(a)"})
    for i, ruolo in enumerate(RUOLI5):
        voto(c, 0, ruolo, {"D1": "si"}, classe="plenaria" if i == 2 else "ordinaria")
    rc, _ = lancia("conta", c, 0)
    prova("una CLASSE plenaria → DA_PLENARIA", rc == 0 and esito(c, 0)["D1"]["stato"] == "DA_PLENARIA")
    c = giuria(base, "preferisco")
    proposta(c, 0, {"D1": "(a)"}, opzioni_lista={"D1": "(a) | (b)"})
    for i, ruolo in enumerate(RUOLI5):
        voto(c, 0, ruolo, {"D1": "si"}, extra="PREFERISCO D1 (b)\n" if i < 3 else "")
    rc, _ = lancia("conta", c, 0)
    prova("tutti sì ma la maggioranza preferisce (b) → DA_RIPROPORRE (F11)",
          rc == 0 and esito(c, 0)["D1"]["stato"] == "DA_RIPROPORRE")

    # Y5: una giuria nuova non si dichiara G1.1
    c = semplice(base, "g11_nuova", {"D1": 5})
    rc, out = lancia_senza_prove("conta", c, 0)
    prova("Y5: una giuria nuova G1.1 si rifiuta senza ESITO_giro_0.json", rc == 2 and "G1.1" in out, out)
    # Y4: un ESITO scritto prima della chiave «protocollo» si riconta; uno ritoccato no
    c = semplice(base, "esito_vecchio", {"D1": 5})
    lancia("conta", c, 0)
    p = c / "ESITO_giro_0.json"
    e = json.loads(p.read_text())
    e.pop("protocollo", None)
    p.write_text(json.dumps(e, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    rc, out = lancia_senza_prove("conta", c, 0)
    prova("Y4: un ESITO senza «protocollo» si riconta identico", rc == 0, out)
    e["decisioni"]["D1"]["stato"] = "RESPINTA"
    p.write_text(json.dumps(e, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    rc, out = lancia_senza_prove("conta", c, 0)
    prova("Y4: un ESITO vecchio ritoccato resta rifiutato", rc == 2, out)

    # W4: un ESITO scritto con la chiave «protocollo» non apre G1.1 fuori dalle batterie
    c = semplice(base, "g11_marcata", {"D1": 5})
    lancia("conta", c, 0)
    rc, out = lancia_senza_prove("conta", c, 0)
    prova("W4: una giuria G1.1 contata solo con la variabile delle batterie non si riconta senza", rc == 2, out)

    # --- 2. revisioni: regressione, minoranza, limite, incompatibile, cambio non motivato
    c = semplice(base, "regressione", {"D1": 3})
    lancia("conta", c, 0)
    e0 = esito(c, 0)
    proposta(c, 1, {"D1": "(d1)"})
    for ruolo, v in zip(RUOLI5, ["no", "si", "si", "si", "si"]):
        voto(c, 1, ruolo, {"D1": v}, cambio=["D1"] if ruolo in e0["D1"]["no"] and v == "si" else [])
    rc, out = lancia("conta", c, 1)
    e = esito(c, 1) if rc == 0 else {}
    prova("revisione che perde un sì → scartata, resta REVISIONE", rc == 0 and e["D1"]["stato"] == "REVISIONE"
          and e["D1"].get("regressiva", {}).get("si_persi") == ["garante"])
    prova("dopo una regressiva valgono testo e sì del giro precedente",
          rc == 0 and e["D1"]["si"] == sorted(["garante", "avversario", "logico"]) and e["D1"]["giro_del_testo"] == 0)
    prova("la stampa dice anche i sì del giro scartato (A12)", "sì del giro 4/5" in out)

    # dopo un giro scartato, CAMBIO rispetto all'ultimo voto espresso: chi era sì nel giro scartato non lo riscrive
    c = semplice(base, "cambio_dopo_regressiva", {"D1": 3})  # sì: garante, avversario, logico; no: debugger, statistico
    lancia("conta", c, 0)
    proposta(c, 1, {"D1": "(d1)"})
    for ruolo, v in zip(RUOLI5, ["no", "si", "si", "si", "no"]):  # il garante perde il sì, il debugger passa a sì
        voto(c, 1, ruolo, {"D1": v}, cambio=["D1"] if ruolo == "debugger" else [])
    lancia("conta", c, 1)
    proposta(c, 2, {"D1": "(d1)"})
    for ruolo, v in zip(RUOLI5, ["si", "si", "si", "si", "si"]):  # il garante torna sì: CAMBIO; il debugger no
        voto(c, 2, ruolo, {"D1": v}, cambio=["D1"] if ruolo in ("garante", "statistico") else [])
    rc, out = lancia("conta", c, 2)
    prova("dopo un giro scartato, CAMBIO rispetto all'ultimo voto espresso", rc == 0 and esito(c, 2)["D1"]["stato"] == "APPROVATA", out)
    c = semplice(base, "minoranza_in_revisione", {"D1": 3})
    lancia("conta", c, 0)
    proposta(c, 1, {"D1": "(d1)"})
    vota_tutti(c, 1, {"D1": 2})
    rc, _ = lancia("conta", c, 1)
    prova("revisione che scende in minoranza → RESPINTA (direttiva; L1, F5, A12)",
          rc == 0 and esito(c, 1)["D1"]["stato"] == "RESPINTA")

    c = semplice(base, "limite", {"D1": 3})
    lancia("conta", c, 0)
    for r in (1, 2, 3):
        proposta(c, r, {"D1": "(d1)"})
        vota_tutti(c, r, {"D1": 3})
        rc, _ = lancia("conta", c, r)
    prova("ancora in maggioranza al giro 3 → NON_CONVERGENTE", rc == 0 and esito(c, 3)["D1"]["stato"] == "NON_CONVERGENTE")
    rifiuta("giro 4", c, 4)
    c = semplice(base, "limite_basso", {"D1": 3}, limite_giri=0)
    rifiuta("limite_giri diverso da 3 (F1)", c, testo="limite_giri")

    c = semplice(base, "incompatibile", {"D1": 3})
    lancia("conta", c, 0)
    proposta(c, 1, {"D1": "(d1)"}, extra="INCOMPATIBILE D1 la REVISIONE del debugger contraddice la CONDIZIONE del logico\n")
    vota_tutti(c, 1, {"D1": 3})
    with open(c / "SIGILLI.md", "a") as f:
        f.write("INCOMPATIBILE-VERIFICATO giro_1 D1\n")
    rc, _ = lancia("conta", c, 1)
    prova("INCOMPATIBILE verificato dal cancelliere → NON_CONVERGENTE, i voti non contano (F8, L6)",
          rc == 0 and esito(c, 1)["D1"]["stato"] == "NON_CONVERGENTE")
    c = semplice(base, "incompatibile_non_verificato", {"D1": 3})
    lancia("conta", c, 0)
    proposta(c, 1, {"D1": "(d1)"}, extra="INCOMPATIBILE D1 la REVISIONE contraddice una CONDIZIONE\n")
    vota_tutti(c, 1, {"D1": 3})
    rc, _ = lancia("conta", c, 1)
    prova("INCOMPATIBILE non verificato: si conta come un giro di revisione", rc == 0 and esito(c, 1)["D1"]["stato"] == "REVISIONE")
    c = semplice(base, "incompatibile_inventato", {"D1": 3})
    lancia("conta", c, 0)
    proposta(c, 1, {"D1": "(d1)"})
    vota_tutti(c, 1, {"D1": 3})
    with open(c / "SIGILLI.md", "a") as f:
        f.write("INCOMPATIBILE-VERIFICATO giro_1 D1\n")
    rifiuta("INCOMPATIBILE-VERIFICATO senza dichiarazione del relatore", c, 1, "non lo dichiara")

    c = semplice(base, "cambio_non_motivato", {"D1": 3})
    lancia("conta", c, 0)
    proposta(c, 1, {"D1": "(d1)"})
    for ruolo in RUOLI5:
        voto(c, 1, ruolo, {"D1": "si"})
    rifiuta("da no a sì senza CAMBIO (F7)", c, 1, "CAMBIO")

    c = semplice(base, "opzione", {"D1": 4, "D2": 5})
    lancia("conta", c, 0)
    proposta(c, 1, {"D1": "(b)"})
    vota_tutti(c, 1, {"D1": 5})
    rifiuta("opzione cambiata in revisione", c, 1, "opzione")
    shutil.rmtree(c / "giro_1")
    proposta(c, 1, {"D1": "(d1)"}, dispositivo={"D1": "si fa tutt'altro"})
    vota_tutti(c, 1, {"D1": 5})
    rifiuta("DISPOSITIVO cambiato in revisione (F6, L5)", c, 1, "DISPOSITIVO")
    shutil.rmtree(c / "giro_1")
    proposta(c, 1, {"D1": "(d1)", "D2": "(d2)"})
    vota_tutti(c, 1, {"D1": 5, "D2": 5})
    rifiuta("decisione già approvata ripresentata", c, 1, "quelle in REVISIONE")
    c = giuria(base, "opzione_fuori_lista")
    proposta(c, 0, {"D1": "(a)"}, opzioni_lista={"D1": "(b) | (c)"})
    vota_tutti(c, 0, {"D1": 5})
    rifiuta("OPZIONE fuori dalla lista OPZIONI (L5)", c, testo="non è nella riga OPZIONI")

    # --- 3. dipendenze (L4, F8)
    c = giuria(base, "dipende")
    proposta(c, 0, {"D1": "(a)", "D2": "(b)"}, extra="DIPENDE D2 D1\n")
    vota_tutti(c, 0, {"D1": 2, "D2": 5})
    rc, _ = lancia("conta", c, 0)
    prova("D2 approvata ma D1 respinta → D2 SOSPESA", rc == 0 and esito(c, 0)["D2"]["stato"] == "SOSPESA")
    c = giuria(base, "dipende_rev")
    proposta(c, 0, {"D1": "(a)", "D2": "(b)"}, extra="DIPENDE D2 D1\n")
    vota_tutti(c, 0, {"D1": 4, "D2": 5})
    rc, _ = lancia("conta", c, 0)
    e = esito(c, 0) if rc == 0 else {}
    prova("D2 approvata ma D1 in revisione → D2 si rivota con D1", rc == 0 and e["D2"]["stato"] == "REVISIONE")
    proposta(c, 1, {"D1": "(a)", "D2": "(b)"}, extra="DIPENDE D2 D1\n")
    vota_tutti(c, 1, {"D1": 5, "D2": 5}, prima=e)
    rc, _ = lancia("conta", c, 1)
    prova("poi tutte e due approvate al giro 1", rc == 0 and esito(c, 1)["D2"]["stato"] == "APPROVATA"
          and esito(c, 1)["D1"]["stato"] == "APPROVATA")

    # --- 4. integrità: giuria cambiata, ESITO ritoccato, rivoto, sigilli non riportati (A1–A4, L2, L3, F3, F12)
    c = semplice(base, "giuria_cambiata", {"D1": 4})
    lancia("conta", c, 0)
    g = json.loads((c / "giuria.json").read_text())
    g["giurati"][1] = {"ruolo": "rovesciatore", "nuovo_sull_oggetto": True}
    (c / "giuria.json").write_text(json.dumps(g))
    (c / "giro_0" / "VOTO_avversario.md").rename(c / "giro_0" / "VOTO_rovesciatore.md")
    registra(c, "giro_0/VOTO_rovesciatore.md")
    proposta(c, 1, {"D1": "(d1)"})
    vota_tutti(c, 1, {"D1": 5})
    rifiuta("giuria.json cambiata al giro 1 (A1)", c, 1, "non coincide con il ricalcolo")
    c = semplice(base, "esito_ritoccato", {"D1": 2})
    lancia("conta", c, 0)
    e = json.loads((c / "ESITO_giro_0.json").read_text())
    e["decisioni"]["D1"]["stato"] = "REVISIONE"
    (c / "ESITO_giro_0.json").write_text(json.dumps(e, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    proposta(c, 1, {"D1": "(d1)"})
    vota_tutti(c, 1, {"D1": 5})
    rifiuta("ESITO del giro precedente ritoccato (A2)", c, 1, "non coincide con il ricalcolo")
    c = semplice(base, "rivoto", {"D1": 3})
    lancia("conta", c, 0)
    voto(c, 0, "statistico", {"D1": "si"})
    rifiuta("rivoto sullo stesso giro (A4)", c, 0, "non coincide con il ricalcolo")
    c = semplice(base, "risigillato", {"D1": 4})
    voto(c, 0, "statistico", {"D1": "si"}, registra_sigillo=False)
    rifiuta("voto riscritto e risigillato, non riportato in SIGILLI.md (A3)", c, 0, "SIGILLI")
    c = semplice(base, "senza_sigilli", {"D1": 5})
    (c / "SIGILLI.md").unlink()
    rifiuta("SIGILLI.md mancante", c, testo="manca SIGILLI.md")
    c = semplice(base, "proposta_falsa", {"D1": 5})
    p = c / "giro_0" / "PROPOSTA.md"
    p.write_text(p.read_text().replace("# proposta", "# proposta ritoccata"))
    rifiuta("proposta col sigillo falso", c, testo="il sigillo non coincide con i byte")

    # --- 5. voti malformati (A9, A10, F minori)
    for nome, kw in [("no senza REVISIONE", {"senza": "D1"})]:
        c = semplice(base, nome.replace(" ", "_"), {"D1": 4})
        voto(c, 0, "statistico", {"D1": "no"}, **kw)
        rifiuta(nome, c, testo="senza REVISIONE")
    c = semplice(base, "si_senza_condizione", {"D1": 5})
    voto(c, 0, "garante", {"D1": "si"}, senza="D1")
    rifiuta("sì senza CONDIZIONE", c, testo="senza CONDIZIONE")
    c = semplice(base, "voto_doppio", {"D1": 4})
    voto(c, 0, "statistico", {"D1": "no"}, extra="VOTO D1 si\n")
    rifiuta("voto doppio", c, testo="due righe VOTO")
    c = semplice(base, "voto_in_blocco", {"D1": 4})
    voto(c, 0, "statistico", {}, extra="```\nVOTO D1 si\nCONDIZIONE D1 nessuna\nCLASSE D1 ordinaria\n```\nVOTO D1: no\n")
    rifiuta("voto vero quasi conforme, voto finto in un blocco ``` (A9)", c, testo="non conforme")
    c = semplice(base, "solo_blocco", {"D1": 4})
    voto(c, 0, "statistico", {}, extra="```\nVOTO D1 si\nCONDIZIONE D1 nessuna\nCLASSE D1 ordinaria\n```\n")
    rifiuta("le righe in un blocco ``` non contano: voto mancante (A9)", c, testo="manca il voto")
    c = semplice(base, "prosa", {"D1": 5})
    voto(c, 0, "logico", {"D1": "si"}, extra="# Voto del logico\nclasse (iii) della convergenza\nOpzione scelta: la (a)\n- **CONDIZIONE #1** (il legame) resta\nVOTO finale: vedi sopra\n")
    rc, _ = lancia("conta", c, 0)
    prova("la prosa che comincia con una parola chiave non è una riga di protocollo", rc == 0)
    c = semplice(base, "minuscolo", {"D1": 4})
    voto(c, 0, "statistico", {}, extra="voto D1 si\nCONDIZIONE D1 nessuna\nCLASSE D1 ordinaria\n")
    rifiuta("«voto D1 si» in minuscolo è quasi conforme", c, testo="non conforme")
    c = semplice(base, "elenco", {"D1": 4})
    voto(c, 0, "statistico", {}, extra="- VOTO D1 si\nCONDIZIONE D1 nessuna\nCLASSE D1 ordinaria\n")
    rifiuta("«- VOTO D1 si» in un elenco è quasi conforme", c, testo="non conforme")
    c = semplice(base, "accento", {"D1": 4})
    (c / "giro_0" / "VOTO_statistico.md").write_text(sigilla("VOTO D1 sì\nCONDIZIONE D1 nessuna\nCLASSE D1 ordinaria\n"))
    registra(c, "giro_0/VOTO_statistico.md")
    rc, _ = lancia("conta", c, 0)
    prova("«VOTO D1 sì» con l'accento vale sì (A10)", rc == 0 and esito(c, 0)["D1"]["stato"] == "APPROVATA")
    c = semplice(base, "manca_classe", {"D1": 5})
    (c / "giro_0" / "VOTO_statistico.md").write_text(sigilla("VOTO D1 si\nCONDIZIONE D1 nessuna\n"))
    registra(c, "giro_0/VOTO_statistico.md")
    rifiuta("voto senza CLASSE (F13)", c, testo="CLASSE")
    c = semplice(base, "voto_mancante", {"D1": 5, "D2": 5})
    voto(c, 0, "logico", {"D1": "si"})
    rifiuta("voto mancante su una decisione", c, testo="manca il voto su D2")
    c = semplice(base, "riga_estranea", {"D1": 5})
    voto(c, 0, "logico", {"D1": "si"}, extra="CONDIZIONE D9 nessuna\n")
    rifiuta("riga su una decisione non in esame", c, testo="non è in esame")
    c = semplice(base, "estraneo", {"D1": 5})
    voto(c, 0, "creativo", {"D1": "si"})
    rifiuta("voto di chi non è giurato", c, testo="estranee")
    c = semplice(base, "traversale", {"D1": 5})
    (c / "giro_0" / "a").mkdir()
    rifiuta("voce estranea nella cartella del giro (A8)", c, testo="voci estranee")

    # --- 6. composizione (A5–A8, F2, L9, giuria vincolante)
    def gg(ruoli, nuovi=None, provv=()):
        nuovi = ruoli if nuovi is None else nuovi
        return [{"ruolo": r, "nuovo_sull_oggetto": r in nuovi, "provvisorio": r in provv} for r in ruoli]
    casi = [
        ("giurati pari", gg(RUOLI5[:4]), {}, "dispari"),
        ("giurati 3", gg(RUOLI5[:3]), {}, "da 5 a 9"),
        ("giurati 11", gg(RUOLI5 + ["formalista", "creativo", "fonti", "prestazioni", "sviluppatore", "metrologo"]), {"relatore": "rovesciatore"}, "da 5 a 9"),
        ("senza garante", gg(["creativo", "avversario", "logico", "debugger", "statistico"]), {}, "garante"),
        ("senza avversario", gg(["garante", "creativo", "logico", "debugger", "statistico"]), {}, "manca un avversario"),
        ("codice senza debugger", gg(["garante", "avversario", "logico", "creativo", "statistico"]),
         {"autorita": "raccomandazione"}, "manca il debugger"),
        ("numeri senza statistico", gg(["garante", "avversario", "logico", "debugger", "creativo"]), {}, "manca lo statistico"),
        ("vincolante senza logico", gg(["garante", "avversario", "creativo", "debugger", "statistico"]), {}, "servono logico, debugger e un avversario"),
        ("relatore fra i giurati", gg(RUOLI5), {"relatore": "logico"}, "non può votare"),
        ("meno di metà nuovi", gg(RUOLI5, nuovi=["garante", "logico"]), {}, "almeno la metà"),
        ("ruolo inventato (A6)", gg(["garante", "avversario", "logico", "debugger", "amico"]), {"tocca_numeri": False}, "non è fra gli agenti"),
        ("ruolo con percorso (A8)", gg(["garante", "avversario", "logico", "debugger", "a/../garante"]), {"tocca_numeri": False}, "non conforme"),
        ("provvisorio senza scheda", gg(RUOLI5[:4] + ["crittografia"], provv=["crittografia"]), {}, "senza scheda"),
        ("tocca_codice assente (A7)", None, {"tocca_codice": None}, "tocca_codice"),
        ("autorita assente", None, {"autorita": None}, "autorita"),
        ("plenaria a 5 (A5, F2)", None, {"classificazione": "plenaria"}, "plenaria: mancano"),
    ]
    for nome, giurati, extra, motivo in casi:
        c = giuria(base, "comp_" + "".join(ch if ch.isalnum() else "_" for ch in nome), giurati=giurati, **extra)
        proposta(c, 0, {"D1": "(a)"})
        for x in ruoli_di(c):
            if "/" in x:
                continue
            voto(c, 0, x, {"D1": "si"})
        rifiuta(f"composizione: {nome}", c, testo=motivo)
    c = giuria(base, "rinuncia_e_voto")
    (c / "RINUNCIA_logico.md").write_text("non competente\n")
    proposta(c, 0, {"D1": "(a)"})
    vota_tutti(c, 0, {"D1": 5})
    rifiuta("RINUNCIA e VOTO dello stesso ruolo (avversario L3)", c, testo="chi rinuncia")
    c = giuria(base, "comp_buona_7", giurati=gg(RUOLI5 + ["rovesciatore", "crittografia"], nuovi=RUOLI5[:4],
                                                    provv=["crittografia"]))
    (c / "SCHEDA_crittografia.md").write_text(sigilla("# scheda provvisoria\n"))
    proposta(c, 0, {"D1": "(a)"})
    vota_tutti(c, 0, {"D1": 7})
    rc, _ = lancia("conta", c, 0)
    prova("composizione corretta a 7 con un provvisorio con scheda → accettata", rc == 0)
    noti = sorted(RUOLI_FINTI)
    votanti = [r for r in noti if r not in ("formalista", "arbitro")]
    c = giuria(base, "plenaria_intera", giurati=gg(votanti), classificazione="plenaria")
    proposta(c, 0, {"D1": "(a)"})
    vota_tutti(c, 0, {"D1": len(votanti)})
    rc, _ = lancia("conta", c, 0)
    prova(f"plenaria con tutti i {len(votanti)} ruoli votanti, istanze nuove → accettata",
          rc == 0 and esito(c, 0)["D1"]["stato"] == "APPROVATA")
    c = giuria(base, "plenaria_parita", giurati=gg(votanti[:-1]), classificazione="plenaria")
    rifiuta("plenaria senza un ruolo", c, testo="plenaria: mancano")

    # --- 6b. giuria leggera: tre giurati, prova prima del voto, un giro, poi la giuria ordinaria
    def leggera(nome, giurati=None, **kw):
        gg3 = giurati or [{"ruolo": r, "nuovo_sull_oggetto": True} for r in ("garante", "avversario", "prestazioni")]
        return giuria(base, nome, giurati=gg3, forma="leggera", tocca_numeri=False, tocca_codice=False, **kw)
    PASSA = "PROVA D1 python3 -I prova_veloce.py (atteso: rc 0)\nESITO-PROVA D1 passa\n"
    def vota3(c, r, voti, classe="leggera", cambio=()):
        for ruolo, v in zip(ruoli_di(c), voti):
            voto(c, r, ruolo, {"D1": v}, classe=classe if not isinstance(classe, list) else classe[ruoli_di(c).index(ruolo)],
                 cambio=cambio)
    c = leggera("leggera_ok")
    proposta(c, 0, {"D1": "(a)"}, extra=PASSA)
    vota3(c, 0, ["si", "si", "si"])
    rc, out = lancia("conta", c, 0)
    prova("giuria leggera: consenso e prova che passa → APPROVATA", rc == 0 and esito(c, 0)["D1"]["stato"] == "APPROVATA", out)
    c = leggera("leggera_prova_fallisce")
    proposta(c, 0, {"D1": "(a)"}, extra=PASSA.replace("passa\n", "fallisce\n"))
    vota3(c, 0, ["si", "si", "si"])
    rc, out = lancia("conta", c, 0)
    prova("giuria leggera: la prova fallisce → RESPINTA anche con il consenso", rc == 0 and esito(c, 0)["D1"]["stato"] == "RESPINTA", out)
    c = leggera("leggera_escalation")
    proposta(c, 0, {"D1": "(a)"}, extra=PASSA)
    vota3(c, 0, ["si", "si", "no"])
    rc, _ = lancia("conta", c, 0)
    prova("giuria leggera: maggioranza → REVISIONE", rc == 0 and esito(c, 0)["D1"]["stato"] == "REVISIONE")
    proposta(c, 1, {"D1": "(a)"}, extra=PASSA)
    vota3(c, 1, ["si", "si", "no"])
    rc, out = lancia("conta", c, 1)
    prova("giuria leggera: dopo un solo giro senza consenso → DA_GIURIA (la giuria ordinaria)",
          rc == 0 and esito(c, 1)["D1"]["stato"] == "DA_GIURIA", out)
    rifiuta("giuria leggera: un secondo giro di revisione", c, 2)
    c = leggera("leggera_classe")
    proposta(c, 0, {"D1": "(a)"}, extra=PASSA)
    vota3(c, 0, ["si", "si", "si"], classe=["leggera", "ordinaria", "leggera"])
    rc, out = lancia("conta", c, 0)
    prova("giuria leggera: un giurato la vuole ordinaria → DA_GIURIA", rc == 0 and esito(c, 0)["D1"]["stato"] == "DA_GIURIA", out)
    c = leggera("leggera_senza_prova")
    proposta(c, 0, {"D1": "(a)"})
    vota3(c, 0, ["si", "si", "si"])
    rifiuta("giuria leggera senza PROVA ed ESITO-PROVA", c, testo="PROVA ed ESITO-PROVA")
    for nome, ruoli3, motivo in [
            ("cinque giurati", ["garante", "avversario", "prestazioni", "logico", "statistico"], "ne servono 3"),
            ("senza critico", ["garante", "logico", "prestazioni"], "manca un critico"),
            ("senza competente", ["garante", "avversario", "debugger"], "manca il ruolo competente"),
            ("senza garante", ["logico", "avversario", "prestazioni"], "manca il garante")]:
        c = leggera("leggera_" + nome.replace(" ", "_"), giurati=[{"ruolo": r, "nuovo_sull_oggetto": True} for r in ruoli3])
        proposta(c, 0, {"D1": "(a)"}, extra=PASSA)
        vota3(c, 0, ["si"] * len(ruoli3))
        rifiuta(f"giuria leggera {nome}", c, testo=motivo)

    c = giuria(base, "g2_di_difetto", protocollo=None, autorita="raccomandazione")
    proposta(c, 0, {"D1": "(a)"})
    vota_tutti(c, 0, {"D1": 5})
    rifiuta("G2 di difetto: senza il campo protocollo valgono le regole G2", c, testo="SIGILLO giuria.json")
    c = giuria(base, "leggera_plenaria", giurati=[{"ruolo": r, "nuovo_sull_oggetto": True} for r in ("garante", "avversario", "prestazioni")],
               forma="leggera", classificazione="plenaria", tocca_numeri=False, tocca_codice=False)
    proposta(c, 0, {"D1": "(a)"}, extra="PROVA D1 x\nESITO-PROVA D1 passa\n")
    for ruolo in ("garante", "avversario", "prestazioni"):
        voto(c, 0, ruolo, {"D1": "si"}, classe="leggera")
    rifiuta("una giuria leggera non vale per una plenaria", c, testo="leggera non vale")
    # --- 6c. protocollo G2: giuria sigillata, delega per decisione, PREFERISCO fra le OPZIONI, precedenti, plenaria
    def fissa(c):
        h = hashlib.sha256((c / "giuria.json").read_bytes()).hexdigest()
        with open(c / "SIGILLI.md", "a", encoding="utf-8") as f:
            f.write(f"SIGILLO giuria.json {h}\n")
    c = giuria(base, "g2_senza_sigillo", protocollo="G2", autorita="raccomandazione")
    proposta(c, 0, {"D1": "(a)"})
    vota_tutti(c, 0, {"D1": 5})
    rifiuta("G2: giuria.json senza sigillo", c, testo="SIGILLO giuria.json")
    c = giuria(base, "g2_ok", protocollo="G2", autorita="raccomandazione")
    fissa(c)
    proposta(c, 0, {"D1": "(a)"})
    vota_tutti(c, 0, {"D1": 5})
    rc, out = lancia("conta", c, 0)
    prova("G2: giuria.json sigillato → si conta", rc == 0 and esito(c, 0)["D1"]["stato"] == "RACCOMANDATA", out)
    with open(c / "SIGILLI.md", "a", encoding="utf-8") as f:
        f.write("SIGILLO giro_0/VOTO_fantasma.md " + "0" * 64 + "\n")
    (c / "ESITO_giro_0.json").unlink()
    rifiuta("G2: un SIGILLO orfano", c, testo="orfano")
    c = giuria(base, "g2_senza_delega", protocollo="G2")
    fissa(c)
    proposta(c, 0, {"D1": "(a)"})
    vota_tutti(c, 0, {"D1": 5})
    rifiuta("G2: vincolante senza DELEGA.md", c, testo="DELEGA.md")
    c = giuria(base, "g2_delega", protocollo="G2", delega="DELEGA.md")
    (c / "DELEGA.md").write_text(sigilla("DELEGATA D1\n"))
    registra_file(c, "DELEGA.md")
    fissa(c)
    proposta(c, 0, {"D1": "(a)", "D2": "(b)"})
    vota_tutti(c, 0, {"D1": 5, "D2": 5})
    rc, out = lancia("conta", c, 0)
    e = esito(c, 0) if rc == 0 else {}
    prova("G2: la decisione delegata è APPROVATA, quella non delegata RACCOMANDATA",
          rc == 0 and e["D1"]["stato"] == "APPROVATA" and e["D2"]["stato"] == "RACCOMANDATA", out)
    c = giuria(base, "g2_preferisco", protocollo="G2", autorita="raccomandazione")
    fissa(c)
    proposta(c, 0, {"D1": "(a)"}, opzioni_lista={"D1": "(a) | (b)"})
    for ruolo in RUOLI5:
        voto(c, 0, ruolo, {"D1": "si"}, extra="PREFERISCO D1 (zeta)\n" if ruolo == "logico" else "")
    rifiuta("G2: PREFERISCO fuori dall'elenco OPZIONI", c, testo="PREFERISCO")
    c1 = giuria(base, "g2_prima", protocollo="G2", autorita="raccomandazione")
    fissa(c1)
    proposta(c1, 0, {"D1": "(a)"}, opzioni_lista={"D1": "(a) | (b)"})
    vota_tutti(c1, 0, {"D1": 1})
    lancia("conta", c1, 0)
    c2 = giuria(base, "g2_dopo", protocollo="G2", autorita="raccomandazione", precedenti=["g2_prima"])
    fissa(c2)
    proposta(c2, 0, {"D1": "(a)"}, opzioni_lista={"D1": "(a) | (b)"})
    vota_tutti(c2, 0, {"D1": 5})
    rifiuta("G2: un'opzione già RESPINTA in una giuria precedente non si ripropone", c2, testo="già RESPINTA")
    c3 = giuria(base, "g2_riproponi1", protocollo="G2", autorita="raccomandazione")
    fissa(c3)
    proposta(c3, 0, {"D1": "(a)"}, opzioni_lista={"D1": "(a) | (b)"})
    for i, ruolo in enumerate(RUOLI5):
        voto(c3, 0, ruolo, {"D1": "si"}, extra="PREFERISCO D1 (b)\n" if i < 3 else "")
    lancia("conta", c3, 0)
    c4 = giuria(base, "g2_riproponi2", protocollo="G2", autorita="raccomandazione", precedenti=["g2_riproponi1"])
    fissa(c4)
    proposta(c4, 0, {"D1": "(a)"}, opzioni_lista={"D1": "(a) | (b)"})
    for i, ruolo in enumerate(RUOLI5):
        voto(c4, 0, ruolo, {"D1": "si"}, extra="PREFERISCO D1 (b)\n" if i < 3 else "")
    rc, out = lancia("conta", c4, 0)
    prova("G2: un secondo DA_RIPROPORRE diventa DA_UTENTE, anche nell'ESITO scritto",
          rc == 0 and esito(c4, 0)["D1"]["stato"] == "DA_UTENTE", out)
    pert = ["garante", "avversario", "logico", "debugger", "statistico", "rovesciatore", "creativo"]
    cp = giuria(base, "g2_plenaria", giurati=[{"ruolo": r, "nuovo_sull_oggetto": True} for r in pert],
                protocollo="G2", classificazione="plenaria", autorita="raccomandazione", pertinenza="PERTINENZA.md")
    (cp / "PERTINENZA.md").write_text(sigilla("".join(f"PERTINENTE {r}\n" for r in pert)))
    registra_file(cp, "PERTINENZA.md")
    fissa(cp)
    proposta(cp, 0, {"D1": "(a)"})
    for i, ruolo in enumerate(pert):
        voto(cp, 0, ruolo, {"D1": "si"}, classe="plenaria" if i == 0 else "ordinaria")
    rc, out = lancia("conta", cp, 0)
    prova("G2: plenaria con i soli pertinenti; CLASSE plenaria non la rimanda a sé stessa",
          rc == 0 and esito(cp, 0)["D1"]["stato"] == "RACCOMANDATA", out)

    # --- 7. errori di ingresso con un messaggio (A11)
    c = Path(base) / "vuota"
    c.mkdir()
    rifiuta("cartella senza giuria.json", c, testo="manca giuria.json")
    c = semplice(base, "giro_negativo", {"D1": 5})
    rifiuta("giro negativo", c, -1, "intero")
    rifiuta("giro non intero", c, "uno", "intero")
    c = giuria(base, "giuria_non_json")
    (c / "giuria.json").write_text("{non json")
    rifiuta("giuria.json non json", c, testo="non è json")
    c = semplice(base, "salto", {"D1": 3})
    proposta(c, 1, {"D1": "(d1)"})
    vota_tutti(c, 1, {"D1": 5})
    rifiuta("giro 1 senza il conto del giro 0", c, 1, "manca ESITO_giro_0")

    # --- 8. soglia degli esperti (§4; A13–A16, F9, F10)
    sys.dont_write_bytecode = True
    os.environ["SCIAME_AGENTI"] = AGENTI_FINTI
    sys.path.insert(0, str(QUI.parent / "motore"))
    import giuria as G
    radice = Path(base) / "albero"
    for cv in ("G1", "G2", "G3", "G1bis", "plenaria_P1"):
        (radice / cv).mkdir(parents=True)
    testa = ["# registro", "", "| data | convocazione | richiedente | competenza | oggetto | motivo |", "|---|---|---|---|---|---|"]
    m = "nessuno dei ruoli copre la competenza"

    def reg(righe, chiuse=()):
        p = Path(base) / f"reg_{len(esiti)}.md"
        p.write_text("\n".join(testa + [f"| 2026-11-16 | {cv} | {chi} | `{s}` | x | {mot} |" for cv, chi, s, mot in righe]
                               + ["", "## Chiuse"] + list(chiuse)) + "\n")
        return p

    def soglia(righe, chiuse=()):
        return G.richieste(reg(righe, chiuse), radice)

    s = soglia([("G1", "logico", "alfa", m), ("G1", "debugger", "alfa", m), ("G1", "avversario", "alfa", m)])
    prova("contemporanea: 3 richiedenti in una convocazione → da creare", s["alfa"]["da_creare"])
    s = soglia([("G1", "logico", "alfa", m), ("G1", "Logico", "alfa", m), ("G1", "sciame-logico", "alfa", m)])
    prova("lo stesso richiedente in tre grafie conta una volta (A13, F9)", s["alfa"]["richiedenti"] == 1
          and not s["alfa"]["da_creare"])
    s = soglia([("G1", "logico", "gamma", m), ("G2", "logico", "gamma", m), ("G2", "statistico", "gamma", m)])
    prova("accumulata: 3 richieste, 2 convocazioni, 2 richiedenti → da creare", s["gamma"]["accumulata"])
    s = soglia([("G1", "coordinatore", "delta", m), ("G2", "Coordinatore", "delta", m), ("G3", "coordinatore", "delta", m),
                ("G3", "logico", "delta", m)])
    prova("il coordinatore conta una volta e non come richiedente distinto (A14)", not s["delta"]["da_creare"])
    s = soglia([("G1", "logico", "eps", m), ("G1bis", "coordinatore", "eps", m), ("G1bis", "debugger", "eps", m)])
    prova("convocazione esistente: accumulata con il coordinatore una volta → da creare", s["eps"]["da_creare"])
    try:
        soglia([("G9", "logico", "eta", m)])
        prova("convocazione inesistente → rifiutata (A15)", False)
    except G.Errore:
        prova("convocazione inesistente → rifiutata (A15)", True)
    try:
        soglia([("G1", "amico", "eta", m)])
        prova("richiedente sconosciuto → rifiutato", False)
    except G.Errore:
        prova("richiedente sconosciuto → rifiutato", True)
    try:
        soglia([("G1", "logico", "eta", "-")])
        prova("motivo «-» → rifiutato (A16)", False)
    except G.Errore:
        prova("motivo «-» → rifiutato (A16)", True)
    p = reg([("G1", "logico", "eta", m)])
    p.write_text(p.read_text() + "| 2026-11-16 | G1 | logico | `Eta_X` | x | m |\n")
    try:
        G.richieste(p, radice)
        prova("riga non conforme (sigla maiuscola) → rifiutata, non ignorata (A16)", False)
    except G.Errore:
        prova("riga non conforme (sigla maiuscola) → rifiutata, non ignorata (A16)", True)
    s = soglia([("G1", "logico", "teta", m), ("G1", "debugger", "teta2", m), ("G1", "avversario", "teta2", m)],
               chiuse=["- `teta2`: unito a `teta`, stessa competenza"])
    prova("«unito a» somma alla sigla di destinazione (A16)", s.get("teta", {}).get("da_creare") and "teta2" not in s)
    s = soglia([("G1", "logico", "zeta", m), ("G1", "debugger", "zeta", m), ("G1", "avversario", "zeta", m)],
               chiuse=["- `zeta`: creato, n. 30"])
    prova("una sigla già creata non conta più", "zeta" not in s)
    s = soglia([("plenaria_P1", r, "iota", m) for r in ("logico", "debugger", "avversario", "statistico")])
    prova("plenaria: 4 richiedenti non bastano, ne servono 5 (F10)", not s["iota"]["da_creare"])
    s = soglia([("G1", "provvisorio:kappa", "kappa", m), ("G1", "logico", "kappa", m), ("G1", "debugger", "kappa", m)])
    prova("l'esperto provvisorio non conta per la propria creazione (F10)", not s["kappa"]["da_creare"])


AGENTI_FINTI = ""


def main():
    global AGENTI_FINTI
    with tempfile.TemporaryDirectory() as base:
        ag = Path(base) / "_agenti"
        ag.mkdir()
        for r in RUOLI_FINTI:
            (ag / f"sciame-{r}.md").write_text("finto\n")
        AGENTI_FINTI = str(ag)
        batteria(base)
    falliti = [n for n, ok in esiti if not ok]
    print(f"\n{len(esiti) - len(falliti)}/{len(esiti)} controlli passati")
    sys.exit(1 if falliti else 0)


if __name__ == "__main__":
    main()
