# Contributing

*[Italiano](CONTRIBUTING.it.md)*

Three kinds of contribution are welcome, each as a pull request.

## 1. A new professional or sub-professional

Add one entry to `db/professionisti.json`:

```json
{"sigla": "code-name", "tipo": "professionista|sottoprofessionista", "genitore": null,
 "nucleo": "<core id from db/nuclei.json>", "versione": "4.0", "stato": "attivo",
 "testi": {"it": {"nome": "...", "breve": "...", "parole": ["..."], "corpo": "**Missione.** ...\n"},
           "en": {"nome": "...", "breve": "...", "parole": ["..."], "corpo": "**Mission.** ...\n"}}}
```

- `sigla`: lowercase, words joined by `-`, new, not a strategy name.
- A sub-professional has `genitore` = a professional of the same core (one level only).
- Texts in **every** language of the repository; the body follows the card structure (mission, skills, questions it
  always asks, methods and tools, typical deliverables, limits, works with), with no `#` headings.
- Say in the pull request which skill is missing from the swarm and why the neighbouring roles do not cover it.
- No details of private projects, no secrets, no personal data.

Before opening it:

```
python3 -I motore/sciame.py --sciame . verifica
python3 -I motore/sciame.py --sciame . costruisci --uscita sciame.sh
for p in prove/prova_*.py; do python3 -I "$p"; done
```

From a project with the swarm installed, `bash sciame/sciame.sh approva card.json` and
`bash sciame/sciame.sh proponi <code> --invia` do the same and open the pull request with `gh`.

## 2. A new language

- `i18n/<code>.json` with exactly the keys of `i18n/it.json`;
- `documenti/<code>/` with every document of `documenti/it/`, the same `<!-- … -->` block markers byte for byte, and
  the same protocol keywords (`VOTO`, `OPZIONE`, `REVISIONE`, … are read by programs and are never translated);
- the texts of every entry of `db/professionisti.json` and `db/nuclei.json` in the new language;
- the card labels for the language in `motore/professionisti.py` (`ETICHETTE`).

`verifica` checks that blocks and keys match across languages.

## 3. Fixes and improvements

Engine changes come with a test in `prove/` that fails before and passes after. Keep the standard library only.
