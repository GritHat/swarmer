#!/usr/bin/env python3
"""Il generatore dello sciame 4.0: dal database, dai documenti della lingua e dagli override locali genera, nella
radice del progetto, il catalogo, gli agenti, le skill e i documenti nella lingua scelta.

Le fonti:
- `<sciame>/db/`: il database unico dei professionisti e dei sottoprofessionisti;
- `<sciame>/documenti/<lingua>/`: i documenti (PREAMBOLO, PIPELINE, ISTRUZIONI_COORDINATORE, GIURIA, AMBIENTE,
  SCHEDA_IPOTESI, README, la testa di AGENTI);
- `<sciame>/i18n/<lingua>.json`: i testi del generatore e dei comandi;
- gli override locali (`<sciame>/locale/AGENTI.md`, o la cartella di `config.json`): una scheda locale vale sempre al
  posto del ruolo generico con la stessa sigla, e un ruolo solo locale si aggiunge.

Ciò che scrive porta sempre la nota `GENERATO`: un file senza la nota (per esempio un agente del progetto) non si
tocca né si cancella mai. Si usa da `motore/sciame.py`; solo libreria standard.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI))
import professionisti as P  # noqa: E402
import percorsi as S  # noqa: E402

VERSIONE = "4.0"
STRATEGIE = ("singolo", "ventaglio", "classica", "giuria", "giuria-leggera", "completa", "plenaria", "esperto", "auto")
SKILL = {"auto": "sciame", **{s: f"sciame-{s}" for s in STRATEGIE if s != "auto"}}
# Le strategie costose si avviano solo per richiesta esplicita dell'utente.
SOLO_UTENTE = {"completa", "plenaria"}
DOCUMENTI = ("PREAMBOLO.md", "PIPELINE.md", "ISTRUZIONI_COORDINATORE.md", "GIURIA.md", "AMBIENTE.md",
             "SCHEDA_IPOTESI.md", "README.md")
BLOCCO = re.compile(r"<!-- ([a-z-]+(?::[a-z-]+)?) -->\n(.*?)\n<!-- /\1 -->", re.S)
GENERATO = S.GENERATO
MODELLO = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
CARTELLA_AGENTI = ".claude/agents"
CARTELLA_SKILL = ".claude/skills"


class Errore(Exception):
    pass


def i18n(sciame: Path, lingua: str) -> dict:
    base = json.loads((sciame / "i18n" / "it.json").read_text(encoding="utf-8"))
    p = sciame / "i18n" / f"{lingua}.json"
    if p.is_file():
        base.update(json.loads(p.read_text(encoding="utf-8")))
    return base


def lingue_disponibili(sciame: Path) -> list[str]:
    doc = {p.name for p in (sciame / "documenti").iterdir() if p.is_dir()} if (sciame / "documenti").is_dir() else set()
    return sorted(l for l in doc if (sciame / "i18n" / f"{l}.json").is_file())


def config(radice: Path) -> dict:
    p = radice / ".sciame" / "config.json"
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def blocchi(testo: str) -> dict[str, str]:
    return {m.group(1): m.group(2).strip() for m in BLOCCO.finditer(testo)}


def profili(testo: str, sigle: set[str]) -> dict[str, dict]:
    trovati = {}
    for riga in testo.splitlines():
        m = re.match(r"^\| `([a-z-]+)` \|(.*)\|\s*$", riga)
        if not m:
            continue
        celle = [c.strip() for c in m.group(2).split("|")]
        if len(celle) != 6:
            raise Errore(f"profilo {m.group(1)}: {len(celle)} colonne invece di 6")
        per, a, b, traduce, f3, f4 = celle

        def ruoli_di(cella):
            nomi = re.findall(r"[a-z]+(?:-[a-z]+)*", cella)
            return [n for n in dict.fromkeys(nomi) if n in sigle]
        if m.group(1) in trovati:
            raise Errore(f"due profili con il nome {m.group(1)}")
        trovati[m.group(1)] = {"per": per, "A": ruoli_di(a), "B": ruoli_di(b), "traduce": ruoli_di(traduce),
                               "f3": ruoli_di(f3), "f4": ruoli_di(f4)}
    if "generale" not in trovati:
        raise Errore("manca il profilo generale")
    return trovati


def catalogo(sciame: Path, radice: Path, lingua: str) -> dict:
    """Tutto ciò che serve a generare: ruoli (generici e locali, con la priorità ai locali), profili, testi."""
    sciame, radice = Path(sciame), Path(radice)
    cfg = config(radice)
    d = P.carica(sciame / "db")
    errori = P.valida(d, [lingua])
    if errori:
        raise Errore("database non valido:\n  " + "\n  ".join(errori[:20]))
    t = i18n(sciame, lingua)
    cartella_doc = sciame / "documenti" / lingua
    if not cartella_doc.is_dir():
        raise Errore(f"lingua «{lingua}» senza documenti: le lingue sono {', '.join(lingue_disponibili(sciame))}")
    testi = {n: (cartella_doc / n).read_text(encoding="utf-8") for n in DOCUMENTI if (cartella_doc / n).is_file()}
    for n in DOCUMENTI:
        if n not in testi:
            raise Errore(f"documenti/{lingua}/{n} manca")
    pre, pipe, istr, amb = (blocchi(testi[n]) for n in ("PREAMBOLO.md", "PIPELINE.md", "ISTRUZIONI_COORDINATORE.md",
                                                         "AMBIENTE.md"))
    for chiave, dove in (("regole-in-breve", pre), ("profili", pipe), ("consegna", pipe), ("coordinatore", istr),
                         ("claude-code", istr), ("ambiente:progetto", istr), ("ambiente", amb)):
        if chiave not in dove:
            raise Errore(f"documenti/{lingua}: manca il blocco «{chiave}»")
    for s in STRATEGIE:
        if f"strategia:{s}" not in pipe:
            raise Errore(f"documenti/{lingua}/PIPELINE.md: manca il blocco strategia:{s}")
    file_locale = S.file_agenti_locale(radice, sciame)
    locali = P.schede_locali(file_locale)
    regole = pre["regole-in-breve"]
    ruoli = []
    for v in P.ordinate(d):
        tv = P.testo(v, lingua)
        r = {"n": v["numero"], "sigla": v["sigla"], "nome": tv["nome"], "nucleo": v["nucleo"], "tipo": v["tipo"],
             "genitore": v.get("genitore"), "breve": tv["breve"], "parole": tv["parole"],
             "scheda": P.scheda(d, v, lingua).strip(), "origine": "generico"}
        if v["sigla"] in locali:
            loc = locali.pop(v["sigla"])
            r.update({"nome": loc["nome"], "breve": loc["breve"] or r["breve"], "scheda": loc["scheda"],
                      "origine": "locale"})
        ruoli.append(r)
    for sigla, loc in locali.items():  # i ruoli solo locali
        ruoli.append({"n": f"L{loc['numero']}", "sigla": sigla, "nome": loc["nome"], "nucleo": "locale",
                      "tipo": "professionista", "genitore": None, "breve": loc["breve"], "parole": [],
                      "scheda": loc["scheda"], "origine": "solo-locale"})
    sigle = {r["sigla"] for r in ruoli}
    nomi_nuclei = {n["id"]: P.nome_nucleo(d, n["id"], lingua) for n in d["nuclei"]}
    nomi_nuclei["locale"] = t["nucleo_locale"]
    for r in ruoli:
        r["descrizione"] = descrizione(dict(r, nucleo=nomi_nuclei.get(r["nucleo"], r["nucleo"]).lower()), t)
        r["prompt"] = prompt_ruolo(r, regole, t, lingua)
    tabella = profili(pipe["profili"], sigle)
    impronta = hashlib.sha256(json.dumps([d["voci"], d["nuclei"], sorted(testi.items()),
                                          [(r["sigla"], r["scheda"]) for r in ruoli if r["origine"] != "generico"]],
                                         ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    nuclei = [{"id": n["id"], "nome": P.nome_nucleo(d, n["id"], lingua)} for n in d["nuclei"]]
    if any(r["nucleo"] == "locale" for r in ruoli):
        nuclei.append({"id": "locale", "nome": t["nucleo_locale"]})
    for chi, m in cfg.get("modelli", {}).items():
        if not MODELLO.match(str(m)) or not re.match(r"^[a-z0-9*][a-z0-9-]*$", str(chi)):
            raise Errore(f"modelli: «{chi}={m}» non è un nome di ruolo e di modello valido")
    try:
        cartella = sciame.resolve().relative_to(radice.resolve()).as_posix()
    except ValueError:
        cartella = "sciame"
    try:
        loc = S.cartella_locale(radice, sciame).resolve().relative_to(radice.resolve()).as_posix()
        loc_file = file_locale.resolve().relative_to(radice.resolve()).as_posix()
    except ValueError:
        loc, loc_file = f"{cartella}/locale", f"{cartella}/locale/AGENTI.md"
    return {
        "cartella": cartella, "cartella_locale": loc, "file_locale": loc_file,
        "versione": VERSIONE, "lingua": lingua, "impronta": impronta, "nuclei": nuclei, "ruoli": ruoli,
        "profili": tabella, "modelli": cfg.get("modelli", {}), "gestiti_dal_progetto": cfg.get("gestiti_dal_progetto", False),
        "testi": {"regole": regole, "consegna": pipe["consegna"], "coordinatore": istr["coordinatore"],
                  "strategie": {s: pipe[f"strategia:{s}"] for s in STRATEGIE}, "profili": pipe["profili"],
                  "claude_code": istr["claude-code"], "ambiente": amb["ambiente"],
                  "ambienti": {"progetto": istr["ambiente:progetto"]},
                  "ambienti_agenti": {"progetto": t["ambiente_agente"], "senza-strumenti": t["ambiente_senza_strumenti"]}},
        "documenti": testi, "testa_agenti": t["testa_agenti"], "i18n": t,
    }


def descrizione(r: dict, t: dict) -> str:
    tipo = t["sotto_di"].format(genitore=r["genitore"]) if r["tipo"] == "sottoprofessionista" else ""
    return f"{r['nome']}: {r['breve']}{tipo} {t['descrizione_coda'].format(nucleo=r['nucleo'])}"


def prompt_ruolo(r: dict, regole: str, t: dict, lingua: str) -> str:
    return t["prompt_ruolo"].format(nome=r["nome"], n=r["n"], breve=r["breve"]) + f"\n\n{regole}\n\n## {t['la_tua_scheda']}\n\n{r['scheda']}\n"


def adatta(dati: dict, testo: str) -> str:
    """I testi parlano di `sciame/` e di `sciame/locale/`: in un'installazione in un'altra cartella diventano quelle vere."""
    if dati.get("cartella", "sciame") == "sciame" and dati.get("cartella_locale", "sciame/locale") == "sciame/locale":
        return testo
    testo = testo.replace("sciame/locale/AGENTI.md", "\0LOCALEF\0").replace("sciame/locale/", "\0LOCALED\0")
    testo = re.sub(r"(?<![A-Za-z0-9_.-])sciame/(?=[A-Za-z_.`])", dati["cartella"] + "/", testo)
    return testo.replace("\0LOCALEF\0", dati["file_locale"]).replace("\0LOCALED\0", dati["cartella_locale"] + "/")


def modello(dati: dict, r: dict) -> str:
    m = dati["modelli"]
    return m.get(r["sigla"]) or m.get(r["nucleo"]) or m.get("*") or "inherit"


def agente(dati: dict, r: dict) -> str:
    t = dati["i18n"]
    nota = S.nota(t["nota_agente"].format(n=r["n"], nome=" ".join(r["nome"].split())))
    return (f"---\nname: sciame-{r['sigla']}\ndescription: {json.dumps(r['descrizione'], ensure_ascii=False)}\n"
            f"model: {modello(dati, r)}\n---\n\n{nota}\n\n"
            + adatta(dati, f"{r['prompt']}\n{dati['testi']['ambienti_agenti']['progetto']}\n"))


def indice_ruoli(dati: dict) -> str:
    t = dati["i18n"]
    nomi = {n["id"]: n["nome"] for n in dati["nuclei"]}
    righe = [f"## {t['i_ruoli']}", "", t["indice_spiega"], "", t["indice_testa"], "|---|---|---|---|---|"]
    for r in dati["ruoli"]:
        tipo = t["tipo_sotto"].format(genitore=r["genitore"]) if r["tipo"] == "sottoprofessionista" else t["tipo_prof"]
        if r["origine"] != "generico":
            tipo += f" ({t['origine_' + r['origine'].replace('-', '_')]})"
        righe.append(f"| `sciame-{r['sigla']}` | {r['nome']} | {nomi.get(r['nucleo'], r['nucleo']).lower()} | {tipo} | "
                     f"{', '.join(r['parole'])} |")
    return "\n".join(righe)


def skill(dati: dict, strategia: str) -> str:
    t, x = dati["i18n"], dati["testi"]
    testa = ["---", f"name: {SKILL[strategia]}", f"description: {json.dumps(t['skill_descrizione'][strategia], ensure_ascii=False)}",
             f"argument-hint: {json.dumps(t['skill_argomenti'], ensure_ascii=False)}"]
    if strategia in SOLO_UTENTE:
        testa.append("disable-model-invocation: true")
    testa.append("---")
    parti = ["\n".join(testa), S.nota(t["nota_skill"]), f"# {t['skill_titolo'][strategia]}",
             x["coordinatore"], x["consegna"], x["ambiente"]]
    if strategia == "auto":
        parti += [t["auto_premessa"]] + [x["strategie"][s] for s in ("auto", "singolo", "ventaglio", "classica",
                                                                       "giuria", "giuria-leggera", "completa", "plenaria",
                                                                       "esperto")]
    elif strategia == "completa":
        parti += [t["completa_premessa"], x["strategie"]["completa"], x["strategie"]["classica"]]
    elif strategia == "plenaria":
        parti += [t["plenaria_premessa"], x["strategie"]["plenaria"], x["strategie"]["completa"],
                  x["strategie"]["giuria"]]
    else:
        parti += [t["strategia_e"].format(strategia=strategia), x["strategie"][strategia]]
    if strategia not in ("singolo", "esperto"):
        parti.append(x["profili"])
    parti += [indice_ruoli(dati), x["claude_code"], x["ambienti"]["progetto"], t["la_richiesta"]]
    testo = "\n\n".join(parti) + "\n"
    testa_yaml, _, corpo = testo.partition("\n---\n")
    return testa_yaml + "\n---\n" + adatta(dati, corpo)


def file_generati(dati: dict) -> dict[str, str]:
    """Percorso relativo alla radice del progetto → testo. Gli agenti dei ruoli che il progetto genera da sé (i suoi
    override, se `gestiti_dal_progetto`) non si scrivono."""
    file = {}
    for r in dati["ruoli"]:
        if dati["gestiti_dal_progetto"] and r["origine"] != "generico":
            continue
        file[f"{CARTELLA_AGENTI}/sciame-{r['sigla']}.md"] = agente(dati, r)
    for s, nome in SKILL.items():
        file[f"{CARTELLA_SKILL}/{nome}/SKILL.md"] = skill(dati, s)
    return file


def file_sciame(dati: dict) -> dict[str, str]:
    """I file generati dentro la cartella dello sciame: catalogo, versione, documenti nella lingua, AGENTI.md."""
    ruoli_cat = [{k: v for k, v in r.items()} for r in dati["ruoli"]]
    cat = {k: v for k, v in dati.items() if k not in ("documenti", "i18n", "testa_agenti", "ruoli")}
    cat["ruoli"] = ruoli_cat
    out = {"catalogo.json": json.dumps(cat, ensure_ascii=False, indent=1) + "\n",
           "VERSIONE": f"{dati['versione']} {dati['impronta'][:12]} {dati['lingua']}\n"}
    nota = S.nota(dati["i18n"]["nota_documento"]) + "\n"
    for n, testo in dati["documenti"].items():
        out[n] = nota + adatta(dati, testo)
    return out


def agenti_md(sciame: Path, dati: dict) -> str:
    d = P.carica(Path(sciame) / "db")
    return S.nota(dati["i18n"]["nota_documento"]) + "\n" + adatta(dati, P.agenti_md(d, dati["lingua"], dati["testa_agenti"]))


generato = S.generato


def _sicuro(base: Path, relativo: str) -> Path:
    try:
        return S.senza_collegamenti(base, Path(base) / relativo)
    except S.Errore as e:
        raise Errore(str(e))


def scrivi(sciame: Path, radice: Path, dati: dict, sostituibili: frozenset = frozenset()) -> list[str]:
    """Scrive ciò che genera. Non sovrascrive mai un file che non porta la nota GENERATO; toglie solo i propri file
    che non servono più."""
    sciame, radice = Path(sciame), Path(radice)
    fatti, saltati = [], []
    file = file_generati(dati)
    for relativo, testo in file.items():
        p = _sicuro(radice, relativo)
        if p.exists() and not generato(p) and relativo not in sostituibili:
            saltati.append(relativo)
            continue
        S.scrivi(radice, p, testo)
        fatti.append(relativo)
    for p in sorted((radice / CARTELLA_AGENTI).glob("sciame-*.md")) if (radice / CARTELLA_AGENTI).is_dir() else []:
        rel = p.relative_to(radice).as_posix()
        if rel not in file and (generato(p) or rel in sostituibili):
            S.togli(radice, p)
            fatti.append(f"-{rel}")
    for relativo, testo in {**file_sciame(dati), "AGENTI.md": agenti_md(sciame, dati)}.items():
        p = _sicuro(sciame, relativo)
        if p.exists() and not generato(p) and relativo not in ("catalogo.json", "VERSIONE") and f"sciame/{relativo}" not in sostituibili:
            saltati.append(f"{sciame.name}/{relativo}")
            continue
        S.scrivi(sciame, p, testo)
    return fatti + [f"saltato (non generato dallo sciame): {s}" for s in saltati]


def controlla(sciame: Path, radice: Path, dati: dict) -> list[str]:
    diversi = []
    for relativo, testo in file_generati(dati).items():
        p = radice / relativo
        if not p.is_file():
            diversi.append(f"manca {relativo}")
        elif generato(p) and p.read_text(encoding="utf-8") != testo:
            diversi.append(f"diverso {relativo}")
    for relativo, testo in {**file_sciame(dati), "AGENTI.md": agenti_md(sciame, dati)}.items():
        p = Path(sciame) / relativo
        if p.is_file() and (generato(p) or relativo in ("catalogo.json", "VERSIONE")) and p.read_text(encoding="utf-8") != testo:
            diversi.append(f"diverso {Path(sciame).name}/{relativo}")
    return diversi


def sostituibili_31(sciame: Path, radice: Path) -> frozenset:
    """I file di un'installazione 3.x da sostituire: gli agenti delle sigle del suo catalogo con la nota della 3.x, le
    sue quattro skill e i suoi documenti. Mai un file per la sola nota: la stessa nota la usano anche altri generatori."""
    v = Path(sciame) / "VERSIONE"
    if not v.is_file() or not v.read_text(encoding="utf-8").startswith("3."):
        return frozenset()
    try:
        cat = json.loads((Path(sciame) / "catalogo.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return frozenset()
    out = set()
    for r in cat.get("ruoli", []):
        rel = f"{CARTELLA_AGENTI}/sciame-{r['sigla']}.md"
        p = Path(radice) / rel
        if p.is_file() and "Generato da sciame/genera_agenti.py dalla scheda" in p.read_text(encoding="utf-8")[:800] \
                and r.get("prompt", "")[:80] in p.read_text(encoding="utf-8"):
            out.add(rel)
    for nome in ("sciame", "sciame-singolo", "sciame-classica", "sciame-completa"):
        rel = f"{CARTELLA_SKILL}/{nome}/SKILL.md"
        p = Path(radice) / rel
        if p.is_file() and "Generato da sciame/genera_agenti.py dai documenti di sciame/" in p.read_text(encoding="utf-8")[:800]:
            out.add(rel)
    for n in ("AGENTI.md", "PREAMBOLO.md", "PIPELINE.md", "ISTRUZIONI_COORDINATORE.md", "SCHEDA_IPOTESI.md", "README.md"):
        out.add(f"sciame/{n}")
    return frozenset(out)


def togli(radice: Path) -> list[str]:
    tolti = []
    for p in sorted((radice / CARTELLA_AGENTI).glob("sciame-*.md")) if (radice / CARTELLA_AGENTI).is_dir() else []:
        if generato(p):
            S.togli(radice, p)
            tolti.append(p.relative_to(radice).as_posix())
    for nome in SKILL.values():
        p = radice / CARTELLA_SKILL / nome / "SKILL.md"
        if generato(p):
            S.togli(radice, p)
            tolti.append(p.relative_to(radice).as_posix())
            if not any(p.parent.iterdir()):
                p.parent.rmdir()
    return tolti
