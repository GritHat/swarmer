#!/usr/bin/env python3
"""Batteria dell'installazione dello sciame 4.0: python3 -I prove/prova_skill.py

In cartelle temporanee controlla l'installazione, la generazione, le lingue, gli override locali, la convivenza con
uno sciame di progetto (nessun file del progetto toccato o cancellato), l'aggiornamento da una 3.x e fra due 4.0 con i
file protetti, l'approvazione di un professionista nuovo con la ricostruzione di sciame.sh, i controlli prima di
pubblicare (segreti, parole vietate, file locali) e sciame.sh dall'inizio alla fine. Esce con 1 se un controllo fallisce.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

QUI = Path(__file__).resolve().parent
SORGENTE = QUI.parent
MOTORE = SORGENTE / "motore" / "sciame.py"
esiti = []


def prova(nome, ok, dettaglio=""):
    esiti.append((nome, bool(ok)))
    print(("ok   " if ok else "FALLITO ") + nome + ("" if ok or not dettaglio else f"\n     {dettaglio[:600]}"))


def py(*arg, cwd=None, env=None):
    p = subprocess.run([sys.executable, "-I", "-B", *map(str, arg)], capture_output=True, text=True, cwd=cwd,
                       stdin=subprocess.DEVNULL, env=env)
    return p.returncode, p.stdout + p.stderr


def sciame(s: Path, *arg, env=None):
    return py(s / "motore" / "sciame.py", "--sciame", s, *arg, env=env)


def installa(radice: Path, *extra):
    radice.mkdir(parents=True, exist_ok=True)
    return py(MOTORE, "installa", "--da", SORGENTE, "--radice", radice, *extra)


def lingue():
    return sorted(p.stem for p in (SORGENTE / "i18n").glob("*.json") if (SORGENTE / "documenti" / p.stem).is_dir())


def albero(radice: Path) -> dict[str, str]:
    return {p.relative_to(radice).as_posix(): p.read_text(encoding="utf-8", errors="replace")
            for p in sorted(radice.rglob("*")) if p.is_file()}


def batteria(base: Path):
    d = json.loads((SORGENTE / "db" / "professionisti.json").read_text(encoding="utf-8"))
    attive = [v for v in d["voci"] if v.get("stato", "attivo") == "attivo"]

    # 1. installazione semplice
    r = base / "semplice"
    rc, out = installa(r)
    prova("installazione semplice", rc == 0, out)
    agenti = sorted((r / ".claude" / "agents").glob("sciame-*.md"))
    prova(f"un agente per voce attiva ({len(attive)})", len(agenti) == len(attive), str(len(agenti)))
    skill = sorted(p.parent.name for p in (r / ".claude" / "skills").glob("*/SKILL.md"))
    prova("nove skill", skill == sorted(["sciame", "sciame-singolo", "sciame-ventaglio", "sciame-classica", "sciame-giuria",
                                          "sciame-giuria-leggera", "sciame-completa", "sciame-plenaria", "sciame-esperto"]), str(skill))
    rc, out = sciame(r / "sciame", "controlla")
    prova("controlla dopo l'installazione: allineato", "allineati" in out or "in line" in out, out)
    rc, out = py(r / "sciame" / "genera_agenti.py", "--controlla")
    prova("genera_agenti.py --controlla di sempre funziona", "allineati" in out or "in line" in out, out)
    rc, out = py(r / "sciame" / "convoca.py", "ruoli", "--domanda", "un filtro di Kalman")
    prova("convoca.py ruoli di sempre funziona", rc == 0 and "sciame-kalman" in out, out)
    rc, out = sciame(r / "sciame", "classica", "--mostra", "--profilo", "codice", "prova")
    prova("avvio con --mostra (come la 3.1)", rc == 0 and "/sciame-classica profilo=codice prova" in out, out)
    rc, out = sciame(r / "sciame", "ventaglio", "--mostra", "--ruoli", "sviluppatore", "--lingua", "en", "x")
    prova("avvio del ventaglio con ruoli e lingua", rc == 0 and "ruoli=sviluppatore lingua=en" in out, out)
    rc, out = sciame(r / "sciame", "giuria-leggera", "--mostra", "x")
    prova("avvio della giuria leggera", rc == 0 and "/sciame-giuria-leggera x" in out, out)
    gl = (r / ".claude" / "skills" / "sciame-giuria-leggera" / "SKILL.md").read_text()
    prova("la skill della giuria leggera porta la prova prima del voto", "ESITO-PROVA" in gl and "DA_GIURIA" in gl)
    rc, out = sciame(r / "sciame", "singolo", "--mostra", "--ruoli", "inesistente", "x")
    prova("un ruolo sconosciuto si rifiuta prima di aprire Claude", rc == 1, out)
    plen = (r / ".claude" / "skills" / "sciame-plenaria" / "SKILL.md").read_text()
    prova("plenaria e completa solo su richiesta dell'utente", "disable-model-invocation: true" in plen and
          "disable-model-invocation: true" in (r / ".claude" / "skills" / "sciame-completa" / "SKILL.md").read_text()
          and "disable-model-invocation" not in (r / ".claude" / "skills" / "sciame-singolo" / "SKILL.md").read_text())
    sotto = [v for v in attive if v["tipo"] == "sottoprofessionista"]
    if sotto:
        t = (r / ".claude" / "agents" / f"sciame-{sotto[0]['sigla']}.md").read_text()
        prova("un sottoprofessionista dice il suo genitore", f"sciame-{sotto[0]['genitore']}" in t)
    rc, out = py(r / "sciame" / "convoca.py", "prepara", "--nome", "v", "--strategia", "ventaglio", "--profilo", "codice",
                 "--domanda", "d", "--n", "3", "--forma", "gara", "--regola", "primo", "--dest", base / "conv")
    prova("convoca.py prepara il ventaglio (gara, 3 agenti)", rc == 0 and out.count("agente-") >= 3, out)
    rc, out = py(r / "sciame" / "convoca.py", "prepara", "--nome", "v2", "--strategia", "ventaglio", "--profilo", "codice",
                 "--domanda", "d", "--n", "3", "--forma", "gara", "--dest", base / "conv")
    prova("il ventaglio in gara senza regola di scelta si rifiuta", rc != 0, out)

    # 2. le lingue, avanti e indietro
    prima = albero(r / ".claude")
    for l in lingue():
        rc, out = sciame(r / "sciame", "lingua", l)
        prova(f"lingua {l}", rc == 0, out)
        rc, out = sciame(r / "sciame", "controlla")
        prova(f"controlla in {l}", "allineati" in out or "in line" in out, out)
    rc, _ = sciame(r / "sciame", "lingua", "it")
    prova("tornare all'italiano rigenera esattamente gli stessi file", albero(r / ".claude") == prima)
    rc, out = sciame(r / "sciame", "lingua", "xx")
    prova("una lingua che non c'è si rifiuta", rc == 1, out)

    # 3. override locali: priorità, ruoli solo locali, nessun file del progetto toccato
    r = base / "locale"
    (r / ".claude" / "agents").mkdir(parents=True)
    agente_progetto = "---\nname: sciame-proprio\ndescription: x\n---\nagente scritto a mano dal progetto\n"
    (r / ".claude" / "agents" / "sciame-proprio.md").write_text(agente_progetto)
    rc, out = installa(r)
    prova("installazione con un agente del progetto", rc == 0, out)
    prova("l'agente del progetto non è toccato", (r / ".claude" / "agents" / "sciame-proprio.md").read_text() == agente_progetto)
    (r / "sciame" / "locale" / "AGENTI.md").write_text(
        "# schede locali\n\n### 1. Garante del progetto X — `sciame-garante`\n\n- **In breve:** garante con i dettagli "
        "del progetto.\n- **Nucleo:** decisione.\n\nScheda locale riservata.\n\n### 2. Esperto solo locale — `sciame-solo-qui`\n\n"
        "- **In breve:** esiste solo nel progetto.\n\nNiente altro.\n")
    rc, out = sciame(r / "sciame", "rigenera")
    t = (r / ".claude" / "agents" / "sciame-garante.md").read_text()
    prova("la scheda locale ha la priorità sul ruolo generico", "Scheda locale riservata" in t and "Garante del progetto X" in t, t[:300])
    prova("un ruolo solo locale diventa un agente", (r / ".claude" / "agents" / "sciame-solo-qui.md").is_file())
    rc, out = sciame(r / "sciame", "controlla")
    prova("controlla con gli override", "allineati" in out or "in line" in out, out)
    (r / "sciame" / "locale" / "AGENTI.md").write_text("# nessuna scheda\n")
    sciame(r / "sciame", "rigenera")
    prova("tolto l'override, torna il ruolo generico", "Scheda locale riservata" not in (r / ".claude" / "agents" / "sciame-garante.md").read_text())
    prova("tolto il ruolo solo locale, il suo agente generato sparisce", not (r / ".claude" / "agents" / "sciame-solo-qui.md").exists())
    prova("l'agente del progetto c'è ancora", (r / ".claude" / "agents" / "sciame-proprio.md").read_text() == agente_progetto)

    # 4. un progetto con uno sciame proprio (cartella sciame/ sua, agenti generati da sé con una nota simile)
    r = base / "progetto"
    (r / "sciame").mkdir(parents=True)
    (r / ".claude" / "agents").mkdir(parents=True)
    propria = "# Le schede del progetto\n\n### 1. Formalista — `sciame-formalista`\n\n- **In breve:** dimostra cose del progetto.\n- **Nucleo:** teorico.\n\nDettagli del progetto.\n"
    (r / "sciame" / "AGENTI.md").write_text(propria)
    for s in ("formalista", "dlm"):
        (r / ".claude" / "agents" / f"sciame-{s}.md").write_text(
            f"---\nname: sciame-{s}\ntools: Read\n---\n<!-- Generato da sciame/genera_agenti.py dalla scheda «1. X» di sciame/AGENTI.md: non modificare a mano. -->\nprogetto\n")
    prima_progetto = albero(r)
    rc, out = installa(r, "--cartella", "sciame/skill", "--locale", "sciame", "--gestiti-dal-progetto")
    prova("installazione sovrapposta in un progetto con uno sciame proprio", rc == 0, out)
    dopo = albero(r)
    toccati = [k for k, v in prima_progetto.items() if dopo.get(k) != v]
    prova("nessun file del progetto toccato o cancellato", not toccati, str(toccati))
    prova("gli override gestiti dal progetto non si scrivono",
          (r / ".claude" / "agents" / "sciame-formalista.md").read_text() == prima_progetto[".claude/agents/sciame-formalista.md"])
    prova("i ruoli generici in più si aggiungono", (r / ".claude" / "agents" / "sciame-architetto.md").is_file())
    rc, out = sciame(r / "sciame" / "skill", "controlla")
    prova("controlla nel progetto sovrapposto", "allineati" in out or "in line" in out, out)
    rc, out = sciame(r / "sciame" / "skill", "rimuovi")
    dopo = albero(r)
    prova("rimuovi toglie solo i file dello sciame", all(dopo.get(k) == v for k, v in prima_progetto.items())
          and not (r / ".claude" / "agents" / "sciame-architetto.md").exists(), out)

    # 5. aggiornamento da una 3.x: le sue schede e i suoi agenti si sostituiscono, quelli del progetto no
    r = base / "da31"
    (r / "sciame").mkdir(parents=True)
    (r / ".claude" / "agents").mkdir(parents=True)
    (r / ".claude" / "skills" / "sciame-singolo").mkdir(parents=True)
    (r / "sciame" / "VERSIONE").write_text("3.1 abcdef\n")
    (r / "sciame" / "AGENTI.md").write_text("### 1. Formalista — `sciame-formalista`\n")
    prompt31 = "Sei il ruolo «Formalista» (scheda 1) dello sciame di agenti: rende precisi gli enunciati"
    (r / "sciame" / "catalogo.json").write_text(json.dumps({"ruoli": [{"sigla": "formalista", "prompt": prompt31}]}))
    (r / ".claude" / "agents" / "sciame-formalista.md").write_text(
        "---\nname: sciame-formalista\n---\n\n<!-- Generato da sciame/genera_agenti.py dalla scheda «1. Formalista» di sciame/AGENTI.md: non modificare a mano. -->\n\n" + prompt31 + "\n")
    (r / ".claude" / "agents" / "sciame-mio.md").write_text(
        "---\nname: sciame-mio\n---\n<!-- Generato da sciame/genera_agenti.py dalla scheda «9. Mio» di sciame/AGENTI.md: non modificare a mano. -->\naltro\n")
    (r / ".claude" / "skills" / "sciame-singolo" / "SKILL.md").write_text("<!-- Generato da sciame/genera_agenti.py dai documenti di sciame/: non modificare a mano. -->\n")
    rc, out = installa(r)
    prova("aggiornamento da una 3.x, con la copia di sicurezza", rc == 0 and "copia di sicurezza" in out, out)
    prova("l'agente della 3.x si sostituisce", "sciame-4 GENERATO" in (r / ".claude" / "agents" / "sciame-formalista.md").read_text())
    prova("la skill della 3.x si sostituisce", "sciame-4 GENERATO" in (r / ".claude" / "skills" / "sciame-singolo" / "SKILL.md").read_text())
    prova("un agente con la stessa nota ma fuori dal catalogo 3.x non si tocca", "altro" in (r / ".claude" / "agents" / "sciame-mio.md").read_text())
    prova("la copia di sicurezza della 3.x c'è", any(p.name.startswith("sciame.prima-") for p in r.iterdir()))

    # 6. aggiornamento fra due 4.0: file protetti e database unito
    r = base / "semplice"
    s = r / "sciame"
    leggi = s / "documenti" / "it" / "SCHEDA_IPOTESI.md"
    leggi.write_text(leggi.read_text() + "\nUna riga del progetto.\n")
    rc, out = installa(r)
    prova("aggiornamento: un file cambiato nel progetto è protetto", rc == 0 and "Una riga del progetto." in leggi.read_text()
          and (leggi.parent / "SCHEDA_IPOTESI.md.nuovo").is_file(), out)

    # 7. approvazione di un professionista nuovo: database, agenti, sciame.sh, richieste chiuse
    voce = {"sigla": "prova-nuova", "tipo": "sottoprofessionista", "genitore": "statistico", "nucleo": "sperimentale",
            "testi": {l: {"nome": f"Prova {l}", "breve": "una voce di prova.", "parole": ["prova"],
                          "corpo": "**Missione.** Provare.\n"} for l in lingue()}}
    f = base / "voce.json"
    f.write_text(json.dumps(voce))
    (s / "RICHIESTE_ESPERTI.md").write_text((s / "RICHIESTE_ESPERTI.md").read_text())
    rc, out = sciame(s, "approva", f)
    prova("approva un sottoprofessionista nuovo", rc == 0, out)
    prova("il nuovo agente c'è", (r / ".claude" / "agents" / "sciame-prova-nuova.md").is_file())
    prova("sciame.sh ricostruito con la voce nuova", (s / "sciame.sh").is_file() and "prova-nuova" in (s / "sciame.sh").read_text())
    prova("la proposta per il repository c'è", (s / "proposte" / "prova-nuova.json").is_file())
    rc, out = sciame(s, "approva", f)
    prova("la stessa sigla due volte si rifiuta", rc == 1, out)
    voce2 = dict(voce, sigla="prova-segreta")
    finto = "gh" + "p_" + "a1B2" * 9  # costruito qui, perché il file stesso non contenga un segreto finto
    voce2["testi"] = {l: dict(t, corpo=f"chiave {finto}\n") for l, t in voce["testi"].items()}
    f.write_text(json.dumps(voce2))
    rc, out = sciame(s, "approva", f)
    prova("una voce con un segreto si rifiuta", rc == 1 and "segreto" in out, out)
    riservata = " ".join(["progetto", "riservato", "zeta"])  # costruita qui, come il segreto finto
    (s / "locale" / "VIETATE.txt").write_text(riservata + "\n")
    voce3 = dict(voce, sigla="prova-vietata")
    voce3["testi"] = {l: dict(t, breve=f"lavora sul {riservata.title()}.") for l, t in voce["testi"].items()}
    f.write_text(json.dumps(voce3))
    rc, out = sciame(s, "approva", f)
    prova("una voce con una parola vietata dal progetto si rifiuta", rc == 1 and "vietata" in out, out)
    voce4 = dict(voce, sigla="prova-orfana", genitore="non-esiste")
    f.write_text(json.dumps(voce4))
    rc, out = sciame(s, "approva", f)
    prova("un sottoprofessionista con un genitore inesistente si rifiuta", rc == 1, out)
    if len(lingue()) > 1:
        voce5 = dict(voce, sigla="prova-monolingue")
        voce5["testi"] = {"it": voce["testi"]["it"]}
        f.write_text(json.dumps(voce5))
        rc, out = sciame(s, "approva", f)
        prova("una voce senza tutte le lingue si rifiuta", rc == 1, out)

    # 8. sciame.sh dall'inizio alla fine
    sh = s / "sciame.sh"
    nuovo = base / "da_sh"
    nuovo.mkdir()
    p = subprocess.run(["bash", str(sh), "-C", str(nuovo), "installa"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    prova("sciame.sh installa in un progetto nuovo", p.returncode == 0, p.stdout + p.stderr)
    prova("il progetto installato da sciame.sh ha il professionista approvato",
          (nuovo / ".claude" / "agents" / "sciame-prova-nuova.md").is_file())
    prova("sciame.sh non porta la cartella locale né le parole vietate",
          riservata not in sh.read_text().lower()
          and not any(r.startswith("#==== sciame.sh: file locale/") for r in sh.read_text().splitlines()))
    p = subprocess.run(["bash", str(nuovo / "sciame" / "sciame.sh"), "controlla"], capture_output=True, text=True,
                       cwd=nuovo, stdin=subprocess.DEVNULL)
    prova("sciame.sh controlla dalla copia installata", "allineati" in p.stdout or "in line" in p.stdout, p.stdout + p.stderr)
    p = subprocess.run(["bash", str(nuovo / "sciame" / "sciame.sh"), "single", "--show", "x"], capture_output=True, text=True,
                       cwd=nuovo, stdin=subprocess.DEVNULL)
    p = subprocess.run(["bash", str(nuovo / "sciame" / "sciame.sh"), "single", "--mostra", "x"], capture_output=True,
                       text=True, cwd=nuovo, stdin=subprocess.DEVNULL)
    prova("gli alias inglesi dei comandi (single)", p.returncode == 0 and "/sciame-singolo" in p.stdout, p.stdout + p.stderr)

    # 10. i denti della passata di validazione
    import importlib
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(SORGENTE / "motore"))
    S = importlib.import_module("percorsi")
    # B1: una cartella sciame/ che non è uno sciame non si tocca
    r = base / "b1"
    (r / "sciame").mkdir(parents=True)
    (r / "sciame" / "convoca.py").write_text("del progetto\n")
    prima = albero(r)
    rc, out = installa(r)
    prova("B1: una cartella sciame/ estranea si rifiuta e resta intatta", rc == 1 and albero(r) == prima, out)
    rc, out = installa(r, "--cartella", "sciame/skill")
    prova("B1: con --cartella sciame/skill si installa accanto", rc == 0 and (r / "sciame" / "convoca.py").read_text() == "del progetto\n", out)
    # B2: -C … aggiorna rispetta la cartella di config.json
    prima = albero(r / "sciame")
    sh = SORGENTE / "sciame.sh"
    q = subprocess.run(["bash", str(sh), "-C", str(r), "aggiorna"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    dopo = albero(r / "sciame")
    prova("B2: -C <progetto> aggiorna scrive in sciame/skill, non in sciame/",
          q.returncode == 0 and dopo.get("convoca.py") == "del progetto\n" and not (r / "sciame" / "motore").exists(), q.stdout + q.stderr)
    # B4: le parole vietate della cartella locale configurata
    r = base / "b4"
    (r / "proj").mkdir(parents=True)
    (r / "proj" / "AGENTI.md").write_text("### 1. Mio — `sciame-mio`\n\n- **In breve:** locale.\n")
    (r / "proj" / "VIETATE.txt").write_text("parolasegreta\n")
    rc, out = installa(r, "--cartella", "skill", "--locale", "proj")
    voce = {"sigla": "dente-b4", "tipo": "professionista", "nucleo": "critico",
            "testi": {l: {"nome": "Dente", "breve": "parla di ParolaSegreta.", "parole": ["x"], "corpo": "**Missione.** x.\n"}
                      for l in lingue()}}
    f = base / "b4.json"
    f.write_text(json.dumps(voce))
    rc, out = sciame(r / "skill", "approva", f)
    prova("B4: VIETATE.txt della cartella locale configurata ferma approva", rc == 1 and "vietata" in out, out)
    (r / "proj" / "VIETATE.txt").unlink()
    voce["testi"] = {l: dict(x, breve="pulito.") for l, x in voce["testi"].items()}
    f.write_text(json.dumps(voce))
    rc, out = sciame(r / "skill", "approva", f)
    prova("B4: con override locali e senza VIETATE.txt approva si ferma", rc == 1 and "VIETATE" in out, out)
    # G1: importa-schede porta le schede negli override locali, mai nel database
    db_prima = (r / "skill" / "db" / "professionisti.json").read_text()
    vecchio = base / "agenti31.md"
    vecchio.write_text("### 9. Privato — `sciame-privato`\n\n- **In breve:** del progetto.\n- **Nucleo:** critico e divergente.\n")
    (r / "proj" / "VIETATE.txt").write_text("# niente\n")
    rc, out = sciame(r / "skill", "importa-schede", vecchio)
    prova("G1: importa-schede va negli override locali e il database non cambia",
          rc == 0 and (r / "skill" / "db" / "professionisti.json").read_text() == db_prima
          and "sciame-privato" in (r / "proj" / "AGENTI.md").read_text(), out)
    voce2 = dict(voce, sigla="privato")
    f.write_text(json.dumps(voce2))
    rc, out = sciame(r / "skill", "approva", f)
    prova("G1: approva rifiuta la sigla di una scheda locale", rc == 1 and "scheda locale" in out, out)
    # G11: approva atomica
    voce3 = dict(voce, sigla="dente-g11", genitore="non-esiste", tipo="sottoprofessionista")
    f.write_text(json.dumps(voce3))
    rc, out = sciame(r / "skill", "approva", f)
    prova("G11: approva fallita lascia il database com'era", rc == 1 and (r / "skill" / "db" / "professionisti.json").read_text() == db_prima, out)
    # G12: i testi generati citano la cartella vera
    sk = (r / ".claude" / "skills" / "sciame-classica" / "SKILL.md").read_text()
    prova("G12: nell'installazione in skill/ le skill citano skill/convoca.py, non sciame/convoca.py",
          "skill/convoca.py" in sk and "sciame/convoca.py" not in sk)
    # G3: una copia del repository senza .git non è una copia installata
    copia = base / "repo-main"
    shutil.copytree(SORGENTE, copia, ignore=shutil.ignore_patterns(".git", "_lavoro", "_v31", "__pycache__"))
    lavoro = base / "g3"
    lavoro.mkdir()
    q = subprocess.run(["bash", str(copia / "sciame.sh"), "installa"], capture_output=True, text=True, cwd=lavoro,
                       stdin=subprocess.DEVNULL)
    prova("G3: lo ZIP del repository installa nella cartella da cui si lancia",
          q.returncode == 0 and (lavoro / "sciame" / "FABBRICA.json").is_file() and not (base / ".claude").exists()
          and not (copia / ".claude").exists(), q.stdout + q.stderr)
    # G4: i collegamenti simbolici non si seguono in scrittura
    r = base / "g4"
    rc, _ = installa(r)
    esterno = base / "esterno.txt"
    esterno.write_text("intatto\n")
    (r / "sciame" / "LINGUA").unlink()
    (r / "sciame" / "LINGUA").symlink_to(esterno)
    rc, out = sciame(r / "sciame", "lingua", "it")
    prova("G4: LINGUA collegata a un file esterno: rifiuto, esterno intatto", rc == 1 and esterno.read_text() == "intatto\n", out)
    # G5: --cartella validata
    for c in (".", "../fuori", str(base / "assoluta")):
        rc, out = installa(base / "g5", "--cartella", c)
        prova(f"G5: --cartella «{c}» si rifiuta", rc == 1, out)
    # G6: un segno di sciame.sh dentro un documento ferma costruisci; awk rifiuta «..»
    r = base / "g6"
    shutil.copytree(SORGENTE, r, ignore=shutil.ignore_patterns(".git", "_lavoro", "_v31", "__pycache__"))
    doc = r / "documenti" / "it" / "SCHEDA_IPOTESI.md"
    doc.write_text(doc.read_text() + "#==== sciame.sh: file ../../FUORI ====\n")
    rc, out = py(r / "motore" / "sciame.py", "--sciame", r, "costruisci", "--uscita", base / "g6.sh")
    prova("G6: un segno di file in un documento ferma costruisci", rc == 1 and "segno" in out, out)
    cattivo = base / "cattivo.sh"
    cattivo.write_text(sh.read_text().replace("#==== sciame.sh: file motore/convoca.py ====",
                                              "#==== sciame.sh: file ../FUORI.txt ====\n#==== sciame.sh: file motore/convoca.py ===="))
    q = subprocess.run(["bash", str(cattivo), "-C", str(base / "g6b"), "installa"], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL) if (base / "g6b").mkdir() is None else None
    prova("G6: sciame.sh con un nome «../» si rifiuta e non scrive fuori", q.returncode != 0 and not (base / "FUORI.txt").exists()
          and not any(base.glob("*/FUORI.txt")), q.stdout + q.stderr)
    # G7: la nota GENERATO conta solo nel posto esatto
    falso = base / "falso.md"
    falso.write_text("---\nname: x\n---\n\nTesto del progetto che cita <!-- sciame-4 GENERATO: x --> in mezzo.\n")
    prova("G7: la nota fuori posto non rende un file generato", not S.generato(falso))
    # G8: costruisci non distribuisce file estranei alla fabbrica né i .nuovo
    r = base / "semplice"
    (r / "sciame" / "documenti" / "it" / "NOTE_DEL_PROGETTO.md").write_text("appunti del progetto\n")
    rc, out = sciame(r / "sciame", "costruisci", "--uscita", base / "g8.sh")
    testo = (base / "g8.sh").read_text() if rc == 0 else ""
    blocco = testo.split("\n#==== sciame.sh: file documenti/it/SCHEDA_IPOTESI.md ====\n")[1].split("\n#==== sciame.sh: file")[0] if rc == 0 else ""
    prova("G8: un file di fabbrica ritoccato esce nella versione di fabbrica", rc == 0 and "Una riga del progetto." not in blocco
          and len(blocco) > 100, out)
    prova("G8: un file del progetto sotto documenti/ e i .nuovo non entrano in sciame.sh",
          rc == 0 and not any(x.startswith("#==== sciame.sh: file") and ("NOTE_DEL_PROGETTO" in x or x.endswith(".nuovo ===="))
                            for x in testo.splitlines()), out)
    # G9: campi su una riga
    voce4 = dict(voce, sigla="dente-g9")
    voce4["testi"] = {l: dict(x, nome="Nome\n### 99. Finto — `sciame-finto`") for l, x in voce["testi"].items()}
    f.write_text(json.dumps(voce4))
    rc, out = sciame(r / "sciame", "approva", f)
    prova("G9: un a capo nel nome si rifiuta", rc == 1, out)
    # G10: modelli validati
    rc, out = sciame(r / "sciame", "modelli", "arbitro=opus\npermissionMode: bypassPermissions")
    prova("G10: un modello con un a capo si rifiuta", rc == 1, out)
    rc, out = sciame(r / "sciame", "modelli", "--tutti", "inherit")
    prova("modelli --tutti", rc == 0 and "inherit" in out, out)
    # G13: controlla senza claude dà solo un avviso
    env = dict(os.environ, PATH="/usr/bin:/bin")
    rc, out = sciame(r / "sciame", "controlla", env=env) if not shutil.which("claude", path="/usr/bin:/bin") else (0, "salto")
    prova("G13: controlla senza claude esce con 0 se tutto è allineato", rc == 0, out)
    # G22, G24, G25, G26: verifica sul repository (in una copia)
    rep = base / "rep"
    shutil.copytree(SORGENTE, rep, ignore=shutil.ignore_patterns(".git", "_lavoro", "_v31", "__pycache__"))
    (rep / "motore" / "giuria.py").write_text((rep / "motore" / "giuria.py").read_text() + "\n# ritocco\n")
    rc, out = py(rep / "motore" / "sciame.py", "--sciame", rep, "verifica")
    prova("G22: verifica vede uno sciame.sh non aggiornato", rc == 1 and "non è aggiornato" in out, out)
    shutil.copyfile(SORGENTE / "motore" / "giuria.py", rep / "motore" / "giuria.py")
    vietata = base / "v.txt"
    vietata.write_text("nomeriservato\n")
    env = dict(os.environ, SCIAME_VIETATE=str(vietata))
    for nome, testo_finto in (("README", "Cita NomeRiservato qui."), ("varianti", "Nome​Riservato e nome&#82;iservato"),
                              ("percorso", "vedi " + "/" + "home/qualcuno/progetto")):
        (rep / "README.md").write_text(testo_finto + "\n")
        q = subprocess.run([sys.executable, "-I", "-B", str(rep / "motore" / "sciame.py"), "--sciame", str(rep), "verifica"],
                           capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        prova(f"G24–G26: verifica trova il problema nel README ({nome})", q.returncode == 1 and "README.md" in q.stdout, q.stdout)
    rc, out = py(rep / "motore" / "sciame.py", "--sciame", rep, "verifica", "--pubblicazione")
    (rep / "_lavoro").mkdir()
    rc2, out2 = py(rep / "motore" / "sciame.py", "--sciame", rep, "verifica", "--pubblicazione")
    prova("G2: verifica --pubblicazione rifiuta le cartelle di lavoro", rc2 == 1 and "_lavoro" in out2, out2)

    # 11. i denti della seconda passata
    rep = base / "rep2"
    shutil.copytree(SORGENTE, rep, ignore=shutil.ignore_patterns(".git", "_lavoro", "_v31", "__pycache__"))
    strano = rep / "documenti" / "it" / "nome con spazio.md"
    strano.write_text("x\n")
    rc, out = py(rep / "motore" / "sciame.py", "--sciame", rep, "costruisci", "--uscita", base / "n1.sh")
    prova("N1: un nome di file con uno spazio ferma costruisci", rc == 1 and "nome di file" in out, out)
    strano.unlink()
    (rep / "NOTE.md").write_text("appunto su " + "nome" + "riservato\n")
    vietata = base / "v2.txt"
    vietata.write_text("nomeriservato\n")
    q2 = subprocess.run([sys.executable, "-I", "-B", str(rep / "motore" / "sciame.py"), "--sciame", str(rep), "verifica"],
                        capture_output=True, text=True, env=dict(os.environ, SCIAME_VIETATE=str(vietata)), stdin=subprocess.DEVNULL)
    prova("N9: verifica esamina anche un NOTE.md nella radice", q2.returncode == 1 and "NOTE.md" in q2.stdout, q2.stdout)
    # N5: CARTELLA dall'ambiente non conta
    r = base / "n5"
    (r / "sciame").mkdir(parents=True)
    (r / "sciame" / "README.md").write_text("del progetto\n")
    rc, out = installa(r, "--cartella", "sciame/skill")
    q3 = subprocess.run(["bash", str(SORGENTE / "sciame.sh"), "-C", str(r), "aggiorna"], capture_output=True, text=True,
                        env=dict(os.environ, CARTELLA="sciame"), stdin=subprocess.DEVNULL)
    prova("N5: CARTELLA nell'ambiente non cambia la cartella", q3.returncode == 0
          and (r / "sciame" / "README.md").read_text() == "del progetto\n" and not (r / "sciame" / "motore").exists(), q3.stdout + q3.stderr)
    # N6: dopo approva, aggiorna aggiorna ancora sciame.sh (non lo protegge come se fosse del progetto)
    r = base / "n6"
    rc, _ = installa(r)
    voce = {"sigla": "dente-n6", "tipo": "professionista", "nucleo": "critico",
            "testi": {l: {"nome": "Dente", "breve": "prova.", "parole": ["x"], "corpo": "**Missione.** x.\n"} for l in lingue()}}
    f = base / "n6.json"
    f.write_text(json.dumps(voce))
    rc, out = sciame(r / "sciame", "approva", f)
    rc, out = installa(r)
    prova("N6: dopo approva, aggiorna non protegge sciame.sh né il database", rc == 0 and "sciame.sh" not in out.split("protetti")[-1]
          and (r / ".claude" / "agents" / "sciame-dente-n6.md").is_file(), out)
    # G1 residuo: il testo di una scheda locale non entra nel pubblico sotto un'altra sigla
    r = base / "g1b"
    rc, _ = installa(r)
    privato = "questa frase molto particolare del progetto privato descrive un metodo interno che non deve uscire mai"
    (r / "sciame" / "locale" / "AGENTI.md").write_text("### 1. Mio — `sciame-mio`\n\n- **In breve:** locale.\n\n" + privato + "\n")
    voce2 = dict(voce, sigla="dente-g1b")
    voce2["testi"] = {l: dict(x, corpo="**Missione.** " + privato + ".\n") for l, x in voce["testi"].items()}
    f.write_text(json.dumps(voce2))
    rc, out = sciame(r / "sciame", "approva", f)
    prova("G1: il testo di una scheda locale non entra nel database pubblico", rc == 1 and "in comune" in out, out)

    # 12. i denti della terza passata
    rep = base / "rep3"
    shutil.copytree(SORGENTE, rep, ignore=shutil.ignore_patterns(".git", "_lavoro", "_v31", "__pycache__"))
    esterna = base / "esterna3"
    esterna.mkdir()
    (rep / "collegamento").symlink_to(esterna)
    rc, out = py(rep / "motore" / "sciame.py", "--sciame", rep, "verifica", "--pubblicazione")
    prova("X1: verifica --pubblicazione rifiuta un collegamento simbolico", rc == 1 and "collegamento" in out, out)
    (rep / "collegamento").unlink()
    vietata = base / "v3.txt"
    vietata.write_text("nomeriservato\n")
    (rep / "documenti" / "it" / ("nome" + "riservato.md")).write_text("x\n")
    q3 = subprocess.run([sys.executable, "-I", "-B", str(rep / "motore" / "sciame.py"), "--sciame", str(rep), "verifica"],
                        capture_output=True, text=True, env=dict(os.environ, SCIAME_VIETATE=str(vietata)), stdin=subprocess.DEVNULL)
    prova("X5: un nome di file con una parola vietata ferma verifica", q3.returncode == 1, q3.stdout)
    r = base / "x2"
    rc, _ = installa(r)
    testa = r / "sciame" / "motore" / "testa.sh"
    testa.write_text(testa.read_text() + "\n# appunto del progetto x2\n")
    rc, out = sciame(r / "sciame", "costruisci", "--uscita", base / "x2.sh")
    prova("X2: una testa.sh ritoccata nel progetto non esce in sciame.sh", rc == 0 and "appunto del progetto x2" not in (base / "x2.sh").read_text().split("\nexit\n")[0], out)
    privato = "questa frase molto particolare del progetto privato descrive un metodo interno che non deve uscire mai"
    (r / "sciame" / "locale" / "AGENTI.md").write_text("### 1. Mio — `sciame-mio`\n\n- **In breve:** locale.\n\n" + privato + "\n")
    voce = {"sigla": "dente-x3", "tipo": "professionista", "nucleo": "critico", "nota": privato,
            "testi": {l: {"nome": "Dente", "breve": "prova.", "parole": ["x"], "corpo": "**Missione.** x.\n"} for l in lingue()}}
    f = base / "x3.json"
    f.write_text(json.dumps(voce))
    rc, out = sciame(r / "sciame", "approva", f)
    prova("X3: una frase locale in un campo fuori da testi si rifiuta", rc == 1 and "in comune" in out, out)
    # X4: un repository locale che non si costruisce lascia tutto com'era
    r = base / "x4"
    rc, _ = installa(r)
    rotto = base / "rep_rotto"
    shutil.copytree(SORGENTE, rotto, ignore=shutil.ignore_patterns(".git", "_lavoro", "_v31", "__pycache__"))
    (rotto / "motore" / "testa.sh").unlink()
    cfg = r / ".sciame" / "config.json"
    cfg.parent.mkdir(exist_ok=True)
    cfg.write_text(json.dumps({"repository_locale": str(rotto)}))
    prima = albero(r)
    voce4 = dict(voce, sigla="dente-x4")
    del voce4["nota"]
    f.write_text(json.dumps(voce4))
    rc, out = sciame(r / "sciame", "approva", f)
    dopo = albero(r)
    prova("X4: approva con un repository locale rotto non scrive niente", rc == 1 and dopo == prima
          and "dente-x4" not in (rotto / "db" / "professionisti.json").read_text(), out)
    # X6: dopo un aggiorna con un file protetto approva funziona
    r = base / "x6"
    rc, _ = installa(r)
    doc = r / "sciame" / "documenti" / "it" / "SCHEDA_IPOTESI.md"
    doc.write_text(doc.read_text() + "\nriga del progetto x6\n")
    nuova = base / "sorgente_x6"
    shutil.copytree(SORGENTE, nuova, ignore=shutil.ignore_patterns(".git", "_lavoro", "_v31", "__pycache__"))
    d6 = nuova / "documenti" / "it" / "SCHEDA_IPOTESI.md"
    d6.write_text(d6.read_text() + "\nriga nuova di fabbrica\n")
    py(nuova / "motore" / "sciame.py", "--sciame", nuova, "costruisci", "--uscita", nuova / "sciame.sh")
    rc, out = py(nuova / "motore" / "sciame.py", "installa", "--da", nuova, "--radice", r)
    voce6 = dict(voce4, sigla="dente-x6")
    f.write_text(json.dumps(voce6))
    rc, out = sciame(r / "sciame", "approva", f)
    prova("X6: dopo un aggiorna con un file protetto, approva e costruisci funzionano", rc == 0, out)

    # 13. i denti della quarta passata
    casa = base / "casa_y1"
    casa.mkdir()
    (casa / ".gitconfig").write_text("[user]\n\tname = Globale\n\temail = globale@example.org\n")
    r = base / "x6"
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.name", "Locale"], check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.email", "locale@example.org"], check=True)
    rc, out = sciame(r / "sciame", "proponi", "dente-x6", "--invia", env=dict(os.environ, HOME=str(casa)))
    prova("Y1: l'identità mostrata prima di --si è quella globale che firma il commit",
          "Globale" in out and "Locale" not in out, out)
    viet = base / "v4.txt"
    viet.write_text("alfafinta betafinta\n")
    env4 = dict(os.environ, SCIAME_VIETATE=str(viet))
    r = base / "y2"
    installa(r)
    voce = {"sigla": "dente-y2", "tipo": "professionista", "nucleo": "critico",
            "testi": {l: {"nome": "Dente", "breve": "prova.", "parole": ["x"],
                          "corpo": "**Missione.** x alfafinta\nbetafinta y.\n"} for l in lingue()}}
    f = base / "y2.json"
    f.write_text(json.dumps(voce))
    rc, out = sciame(r / "sciame", "approva", f, env=env4)
    prova("Y2: una voce vietata spezzata da un a capo si rifiuta", rc == 1, out)
    rep = base / "rep4"
    shutil.copytree(SORGENTE, rep, ignore=shutil.ignore_patterns(".git", "_lavoro", "_v31", "__pycache__"))
    (rep / ".venv" / "bin").mkdir(parents=True)
    (rep / ".venv" / "bin" / "python").symlink_to(sys.executable)
    with open(rep / ".gitignore", "a") as g:
        g.write(".venv/\n")
    rc, out = py(rep / "motore" / "sciame.py", "--sciame", rep, "verifica", "--pubblicazione")
    prova("Y6: un collegamento in una cartella ignorata non ferma verifica --pubblicazione", rc == 0, out)
    (rep / "documenti" / "it" / "alfafinta-betafinta.md").write_text("x\n")
    rc, out = py(rep / "motore" / "sciame.py", "--sciame", rep, "verifica", env=env4)
    prova("Y7: una voce di più parole in un nome di file ferma verifica", rc == 1, out)
    r = base / "y3"
    installa(r)
    if (r / "sciame" / "UPSTREAM").is_file():
        (r / "sciame" / "UPSTREAM").write_text("progetto/ritoccato\n")
        rc, out = sciame(r / "sciame", "costruisci", "--uscita", base / "y3.sh")
        prova("Y3: un UPSTREAM ritoccato nel progetto non esce in sciame.sh",
              rc == 0 and (base / "y3.sh").read_text().split("#==== sciame.sh: file UPSTREAM ====\n")[1].split("\n")[0]
              != "progetto/ritoccato", out)
    r = base / "d7"
    rc, out = installa(r, "--cartella", "sciame//skill/")
    cfg = json.loads((r / ".sciame" / "config.json").read_text()) if (r / ".sciame" / "config.json").is_file() else {}
    prova("d7: la cartella salvata è quella normalizzata", rc == 0 and cfg.get("cartella") == "sciame/skill", out + str(cfg))

    # 14. i denti della quinta passata
    viet5 = base / "v5.txt"
    viet5.write_text("nfinta\nalfafinta-betafinta\nsegretofinto\n")
    env5 = dict(os.environ, SCIAME_VIETATE=str(viet5))
    rep = base / "rep5"
    shutil.copytree(SORGENTE, rep, ignore=shutil.ignore_patterns(".git", "_lavoro", "_v31", "__pycache__"))
    doc = rep / "documenti" / "it" / "W1.md"
    doc.write_text("percorso C:\\nfinta\n")
    rc, out = py(rep / "motore" / "sciame.py", "--sciame", rep, "verifica", env=env5)
    prova("W1: una voce vietata dopo una barra rovescia resta trovata", rc == 1 and "vietata" in out, out)
    doc.unlink()
    (rep / "documenti" / "it" / "alfafinta-betafinta.md").write_text("x\n")
    rc, out = py(rep / "motore" / "sciame.py", "--sciame", rep, "verifica", env=env5)
    prova("W2: una voce con il trattino in un nome di file resta trovata", rc == 1 and "vietata" in out, out)
    (rep / "documenti" / "it" / "alfafinta-betafinta.md").unlink()
    esterno = base / "upstream_esterno"
    esterno.write_text("segretofinto/esterno\n")
    (rep / "UPSTREAM").unlink()
    (rep / "UPSTREAM").symlink_to(esterno)
    rc, out = py(rep / "motore" / "sciame.py", "--sciame", rep, "costruisci", "--uscita", base / "w6.sh")
    prova("W6: un UPSTREAM collegamento si rifiuta", rc == 1 and not (base / "w6.sh").exists(), out)
    (rep / "UPSTREAM").unlink()
    (rep / "UPSTREAM").write_text("GritHat/swarmer\n")
    subprocess.run(["git", "init", "-q", str(rep)], check=True)
    (rep / "extra").mkdir()
    (rep / "extra" / "dati.txt").write_text("segretofinto\n")
    with open(rep / ".gitignore", "a") as g:
        g.write("dati.txt\n")
    subprocess.run(["git", "-C", str(rep), "add", "-f", "extra/dati.txt"], check=True)
    rc, out = py(rep / "motore" / "sciame.py", "--sciame", rep, "verifica", "--pubblicazione", env=env5)
    prova("W7: un file tracciato anche se ignorato per nome si esamina", rc == 1 and "extra/dati.txt" in out, out)

    # 15. i denti della sesta passata
    rep = base / "rep6"
    shutil.copytree(SORGENTE, rep, ignore=shutil.ignore_patterns(".git", "_lavoro", "_v31", "__pycache__"))
    with open(rep / ".gitignore", "a") as g:
        g.write("SCHEDA_IPOTESI.md\n")
    subprocess.run(["git", "init", "-q", str(rep)], check=True)
    r = base / "n1"
    installa(r)
    (r / ".sciame").mkdir(exist_ok=True)
    (r / ".sciame" / "config.json").write_text(json.dumps({"repository_locale": str(rep)}))
    voce = {"sigla": "dente-n1", "tipo": "professionista", "nucleo": "critico",
            "testi": {l: {"nome": "Dente", "breve": "prova.", "parole": ["x"], "corpo": "**Missione.** x.\n"} for l in lingue()}}
    f = base / "n1.json"
    f.write_text(json.dumps(voce))
    rc, out = sciame(r / "sciame", "approva", f)
    prova("N1: un file distribuito ignorato da .gitignore non rompe approva con un repository git",
          rc == 0 and "dente-n1" in (rep / "sciame.sh").read_text(), out)
    viet6 = base / "v6.txt"
    viet6.write_text("segretofinto\n")
    env6 = dict(os.environ, SCIAME_VIETATE=str(viet6))
    rep = base / "rep7"
    shutil.copytree(SORGENTE, rep, ignore=shutil.ignore_patterns(".git", "_lavoro", "_v31", "__pycache__"))
    (rep / "extra").mkdir()
    (rep / "extra" / "dati.txt").write_text("segretofinto\n")
    with open(rep / ".gitignore", "a") as g:
        g.write("/altro/extra\n")
    rc, out = py(rep / "motore" / "sciame.py", "--sciame", rep, "verifica", "--pubblicazione", env=env6)
    prova("N2: un'ancora di .gitignore non esclude un file che git pubblicherebbe", rc == 1 and "extra/dati.txt" in out, out)
    with open(rep / ".gitignore", "a") as g:
        g.write("!tenuto.txt\n")
    rc, out = py(rep / "motore" / "sciame.py", "--sciame", rep, "verifica", "--pubblicazione", env=env6)
    prova("N2: una negazione in .gitignore senza .git ferma verifica", rc == 1 and "negazione" in out, out)

    # 9. verifica prima di pubblicare, sulla sorgente
    rc, out = py(MOTORE, "--sciame", SORGENTE, "verifica")
    prova("verifica della sorgente: nessun problema", rc == 0, out)


def main():
    with tempfile.TemporaryDirectory() as base:
        batteria(Path(base))
    falliti = [n for n, ok in esiti if not ok]
    print(f"\n{len(esiti) - len(falliti)}/{len(esiti)} controlli passati")
    sys.exit(1 if falliti else 0)


if __name__ == "__main__":
    main()
