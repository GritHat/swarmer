#!/usr/bin/env python3
"""Il database unico dei professionisti e dei sottoprofessionisti dello sciame.

`db/professionisti.json` è la sola fonte dei ruoli: ogni voce ha la sigla, il tipo (`professionista` o
`sottoprofessionista`), il genitore (per un sottoprofessionista), il nucleo, la versione in cui è entrata, lo stato e i
testi in ogni lingua (nome, in breve, parole chiave, corpo della scheda). `db/nuclei.json` dà l'ordine e i nomi dei
nuclei. Da qui si generano `AGENTI.md` in ogni lingua, il catalogo, gli agenti e le skill.

Gli override locali (`sciame/locale/AGENTI.md`, o la cartella che dice la configurazione) sono schede nel formato di
`AGENTI.md`: per la stessa sigla hanno sempre la priorità sul ruolo generico, e non entrano mai nel database né nel
repository pubblico.

    python3 -I motore/professionisti.py valida [DB]            # controlla il database
    python3 -I motore/professionisti.py schede LINGUA [DB]     # stampa AGENTI.md nella lingua
    python3 -I motore/professionisti.py elenco [DB]            # sigle, tipi, genitori
    python3 -I motore/professionisti.py importa AGENTI.md LINGUA [DB]   # da un AGENTI.md 3.x al database
Solo libreria standard.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

QUI = Path(__file__).resolve().parent
DB_PREDEFINITO = QUI.parent / "db"
SIGLA = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
TIPI = ("professionista", "sottoprofessionista")
STATI = ("attivo", "ritirato")
LINGUA = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")
# Sigle riservate: i nomi delle strategie e delle skill.
RISERVATE = {"singolo", "ventaglio", "classica", "giuria", "giuria-leggera", "leggera", "completa", "plenaria",
             "esperto", "auto", "locale"}
TITOLO = re.compile(r"^### (\d+(?:\.\d+)?)\. (.+?) — `sciame-([a-z0-9-]+)`\s*$")
CAMPI_TESTO = ("nome", "breve", "parole", "corpo")
# Le etichette della testa di una scheda, per lingua; le lingue nuove le aggiungono qui con una proposta.
ETICHETTE = {
    "it": {"breve": "In breve", "nucleo": "Nucleo", "parole": "Parole chiave", "genitore": "Specializzazione di",
           "versione": "Nello sciame dalla versione", "sotto": "Sottoprofessionisti"},
    "en": {"breve": "In short", "nucleo": "Core", "parole": "Keywords", "genitore": "Specialization of",
           "versione": "In the swarm since version", "sotto": "Sub-professionals"},
}


CONTROLLO = re.compile(r"[\x00-\x1f\x7f\u2028\u2029]")


class Errore(Exception):
    pass


def problemi_riga(x: str) -> list[str]:
    """Un campo di una riga sola: niente a capo né caratteri di controllo, niente «|» (romperebbe le tabelle), niente
    commenti HTML né segni dei blocchi."""
    out = []
    if CONTROLLO.search(x):
        out.append("a capo o caratteri di controllo")
    if "|" in x:
        out.append("contiene «|»")
    if "<!--" in x or "-->" in x:
        out.append("contiene un commento HTML")
    if x.lstrip().startswith("#"):
        out.append("comincia con «#»")
    return out


def carica(db: Path = DB_PREDEFINITO) -> dict:
    db = Path(db)
    try:
        voci = json.loads((db / "professionisti.json").read_text(encoding="utf-8"))
        nuclei = json.loads((db / "nuclei.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise Errore(f"database illeggibile in {db}: {e}")
    return {"voci": voci.get("voci", []), "nuclei": nuclei.get("nuclei", []), "lingue": lingue_di(voci, nuclei)}


def lingue_di(voci: dict, nuclei: dict) -> list[str]:
    tutte = set()
    for v in voci.get("voci", []):
        tutte |= set(v.get("testi", {}))
    return sorted(tutte)


def valida(d: dict, lingue: list[str] | None = None) -> list[str]:
    """Gli errori del database: struttura, sigle, genitori, nuclei, testi completi in ogni lingua richiesta."""
    errori = []
    lingue = lingue or ["it"]
    nuclei = {n.get("id") for n in d["nuclei"]}
    for n in d["nuclei"]:
        for l in lingue:
            if not n.get("testi", {}).get(l, {}).get("nome"):
                errori.append(f"nucleo {n.get('id')}: manca il nome in «{l}»")
    viste, per_sigla = set(), {}
    for i, v in enumerate(d["voci"]):
        s = v.get("sigla", "")
        dove = f"voce {i + 1} ({s or '?'})"
        if not SIGLA.match(s):
            errori.append(f"{dove}: sigla non conforme a {SIGLA.pattern}")
        if s in RISERVATE:
            errori.append(f"{dove}: la sigla è riservata a una strategia")
        if s in viste:
            errori.append(f"{dove}: sigla doppia")
        viste.add(s)
        per_sigla[s] = v
        if v.get("tipo") not in TIPI:
            errori.append(f"{dove}: tipo «{v.get('tipo')}» non in {TIPI}")
        if v.get("stato", "attivo") not in STATI:
            errori.append(f"{dove}: stato «{v.get('stato')}» non in {STATI}")
        if v.get("nucleo") not in nuclei:
            errori.append(f"{dove}: nucleo «{v.get('nucleo')}» sconosciuto")
        if not re.match(r"^\d+\.\d+$", str(v.get("versione", ""))):
            errori.append(f"{dove}: versione mancante o non nella forma «4.0»")
        for l in lingue:
            t = v.get("testi", {}).get(l)
            if not t:
                errori.append(f"{dove}: mancano i testi in «{l}»")
                continue
            for c in CAMPI_TESTO:
                if not t.get(c):
                    errori.append(f"{dove}: testo «{c}» vuoto in «{l}»")
            if not isinstance(t.get("parole", []), list):
                errori.append(f"{dove}: «parole» non è un elenco in «{l}»")
            corpo = t.get("corpo", "")
            if re.search(r"^\s*#", corpo, re.M):
                errori.append(f"{dove}: il corpo in «{l}» contiene righe che cominciano con «#», che romperebbero AGENTI.md")
            if CONTROLLO.search(corpo.replace("\n", "").replace("\t", "")):
                errori.append(f"{dove}: il corpo in «{l}» contiene caratteri di controllo (per esempio \\r)")
            if "<!--" in corpo:
                errori.append(f"{dove}: il corpo in «{l}» contiene «<!--»")
            for c in ("nome", "breve"):
                errori += [f"{dove}: «{c}» in «{l}»: {x}" for x in problemi_riga(str(t.get(c, "")))]
            for w in t.get("parole", []) if isinstance(t.get("parole", []), list) else []:
                errori += [f"{dove}: una parola chiave in «{l}»: {x}" for x in problemi_riga(str(w))]
    for v in d["voci"]:
        s, g = v.get("sigla"), v.get("genitore")
        if v.get("tipo") == "professionista" and g:
            errori.append(f"{s}: un professionista non ha genitore")
        if v.get("tipo") == "sottoprofessionista":
            if not g:
                errori.append(f"{s}: un sottoprofessionista ha un genitore")
            elif g not in per_sigla:
                errori.append(f"{s}: genitore «{g}» inesistente")
            elif per_sigla[g].get("tipo") != "professionista":
                errori.append(f"{s}: il genitore «{g}» non è un professionista (un livello solo)")
            elif per_sigla[g].get("nucleo") != v.get("nucleo"):
                errori.append(f"{s}: il nucleo non è quello del genitore «{g}»")
    return errori


def ordinate(d: dict) -> list[dict]:
    """Le voci attive in ordine: per nucleo, i professionisti nell'ordine del database, ciascuno seguito dai suoi
    sottoprofessionisti. Assegna il numero: «7» a un professionista, «7.2» al suo secondo sottoprofessionista."""
    attive = [v for v in d["voci"] if v.get("stato", "attivo") == "attivo"]
    figli = {}
    for v in attive:
        if v["tipo"] == "sottoprofessionista":
            figli.setdefault(v["genitore"], []).append(v)
    out, n = [], 0
    for nucleo in d["nuclei"]:
        for v in attive:
            if v["tipo"] != "professionista" or v["nucleo"] != nucleo["id"]:
                continue
            n += 1
            out.append(dict(v, numero=str(n)))
            for k, f in enumerate(figli.get(v["sigla"], []), 1):
                out.append(dict(f, numero=f"{n}.{k}"))
    return out


def testo(v: dict, lingua: str, ripiego: str = "it") -> dict:
    t = v["testi"].get(lingua) or v["testi"].get(ripiego) or next(iter(v["testi"].values()))
    return t


def nome_nucleo(d: dict, nid: str, lingua: str) -> str:
    for n in d["nuclei"]:
        if n["id"] == nid:
            t = n["testi"].get(lingua) or n["testi"].get("it")
            return t["nome"]
    return nid


def scheda(d: dict, v: dict, lingua: str) -> str:
    """La scheda di una voce, nel formato di AGENTI.md."""
    e = ETICHETTE.get(lingua, ETICHETTE["en"])
    t = testo(v, lingua)
    righe = [f"### {v['numero']}. {t['nome']} — `sciame-{v['sigla']}`", "",
             f"- **{e['breve']}:** {t['breve']}",
             f"- **{e['nucleo']}:** {nome_nucleo(d, v['nucleo'], lingua)}."]
    if v["tipo"] == "sottoprofessionista":
        g = next(x for x in d["voci"] if x["sigla"] == v["genitore"])
        righe.append(f"- **{e['genitore']}:** {testo(g, lingua)['nome']} (`sciame-{g['sigla']}`).")
    righe += [f"- **{e['parole']}:** {', '.join(t['parole'])}.", f"- **{e['versione']}:** {v['versione']}.", "",
              t["corpo"].strip(), ""]
    return "\n".join(righe)


def agenti_md(d: dict, lingua: str, testa: str = "") -> str:
    """AGENTI.md completo nella lingua: la testa (dai documenti della lingua), poi i nuclei con le schede."""
    parti = [testa.rstrip() + "\n"] if testa else []
    for nucleo in d["nuclei"]:
        voci = [v for v in ordinate(d) if v["nucleo"] == nucleo["id"]]
        if not voci:
            continue
        parti.append(f"## {intestazione_nucleo(lingua)} {nome_nucleo(d, nucleo['id'], lingua)}\n")
        parti += [scheda(d, v, lingua) for v in voci]
    return "\n".join(parti).rstrip() + "\n"


def intestazione_nucleo(lingua: str) -> str:
    return {"it": "Nucleo", "en": "Core:"}.get(lingua, "Core:")


# --- Gli override locali ---

def schede_locali(percorso: Path) -> dict[str, dict]:
    """Le schede di un AGENTI.md locale (formato `### N. Nome — `sciame-sigla``): sigla → {nome, breve, scheda}.
    La numerazione è libera. Non entrano mai nel database."""
    p = Path(percorso)
    if not p.is_file():
        return {}
    righe = p.read_text(encoding="utf-8").splitlines()
    inizi = [i for i, r in enumerate(righe) if TITOLO.match(r)]
    out = {}
    for i in inizi:
        fine = len(righe)
        for j in range(i + 1, len(righe)):
            if TITOLO.match(righe[j]) or righe[j].startswith("## ") or righe[j] == "---":
                fine = j
                break
        n, nome, sigla = TITOLO.match(righe[i]).groups()
        blocco = righe[i:fine]
        breve = ""
        for k, r in enumerate(blocco):
            m = re.match(r"^- \*\*(In breve|In short):\*\*\s*(.*)$", r)
            if m:
                breve = " ".join([m.group(2)] + [s.strip() for s in blocco[k + 1:]
                                                  if s.startswith("  ") and not s.lstrip().startswith("- ")][:0])
                testo_breve = [m.group(2)]
                for s in blocco[k + 1:]:
                    if not s.startswith("  ") or s.lstrip().startswith("- "):
                        break
                    testo_breve.append(s.strip())
                breve = " ".join(testo_breve)
                break
        if sigla in out:
            raise Errore(f"{p}: due schede locali con la sigla «{sigla}»")
        out[sigla] = {"sigla": sigla, "numero": n, "nome": nome, "breve": breve, "scheda": "\n".join(blocco).strip()}
    return out


# --- Importazione da un AGENTI.md 3.x (migrazione) ---

def importa(percorso: Path, lingua: str, d: dict) -> list[str]:
    """Aggiunge al database le schede di un AGENTI.md 3.x che il database non ha. Le altre le segnala."""
    fatti = []
    righe = Path(percorso).read_text(encoding="utf-8").splitlines()
    nuclei_per_nome = {nome_nucleo(d, n["id"], lingua).lower(): n["id"] for n in d["nuclei"]}
    sigle = {v["sigla"] for v in d["voci"]}
    for sigla, s in schede_locali(percorso).items():
        if sigla in sigle:
            fatti.append(f"{sigla}: c'è già, non la tocco")
            continue
        blocco = s["scheda"].splitlines()

        def campo(nome):
            for k, r in enumerate(blocco):
                if r.startswith(f"- **{nome}:**"):
                    t = [r[len(f"- **{nome}:**"):].strip()]
                    for x in blocco[k + 1:]:
                        if not x.startswith("  ") or x.lstrip().startswith("- "):
                            break
                        t.append(x.strip())
                    return " ".join(t)
            return ""
        nucleo = nuclei_per_nome.get(campo("Nucleo").rstrip(".").strip().lower())
        if not nucleo:
            fatti.append(f"{sigla}: nucleo sconosciuto, non importata")
            continue
        corpo = "\n".join(r for r in blocco[1:] if not re.match(r"^- \*\*(In breve|Nucleo|Parole chiave|Origine):\*\*", r)
                          and not (r.startswith("  ") and not r.lstrip().startswith("- "))).strip()
        d["voci"].append({"sigla": sigla, "tipo": "professionista", "genitore": None, "nucleo": nucleo,
                          "versione": "4.0", "stato": "attivo",
                          "testi": {lingua: {"nome": s["nome"], "breve": campo("In breve"),
                                             "parole": [x.strip() for x in campo("Parole chiave").rstrip(".").split(",") if x.strip()],
                                             "corpo": corpo + "\n"}}})
        fatti.append(f"{sigla}: importata")
    return fatti


def salva(d: dict, db: Path = DB_PREDEFINITO) -> None:
    (Path(db) / "professionisti.json").write_text(
        json.dumps({"formato": 1, "voci": d["voci"]}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> None:
    a = sys.argv[1:]
    try:
        if a[:1] == ["valida"]:
            d = carica(Path(a[1]) if len(a) > 1 else DB_PREDEFINITO)
            errori = valida(d, d["lingue"])
            print("\n".join(errori) if errori else
                  f"database valido: {len(d['voci'])} voci, lingue {', '.join(d['lingue'])}")
            sys.exit(1 if errori else 0)
        elif a[:1] == ["schede"] and len(a) >= 2:
            d = carica(Path(a[2]) if len(a) > 2 else DB_PREDEFINITO)
            print(agenti_md(d, a[1]), end="")
        elif a[:1] == ["elenco"]:
            d = carica(Path(a[1]) if len(a) > 1 else DB_PREDEFINITO)
            for v in ordinate(d):
                print(f"{v['numero']:>6}  sciame-{v['sigla']:<28} {v['tipo']:<20} {v.get('genitore') or ''}")
        elif a[:1] == ["importa"] and len(a) >= 3:
            db = Path(a[3]) if len(a) > 3 else DB_PREDEFINITO
            d = carica(db)
            print("\n".join(importa(Path(a[1]), a[2], d)))
            salva(d, db)
        else:
            print(__doc__)
            sys.exit(2)
    except Errore as e:
        print(f"professionisti: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
