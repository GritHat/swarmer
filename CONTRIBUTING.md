# Contributing

*[Italiano](CONTRIBUTING.it.md)*

Three kinds of contribution are welcome, each as a pull request.

## 1. A new professional or sub-professional

Add one entry to `db/professionals.json` (format 2):

```json
{"id": "role-id", "type": "professional|subprofessional", "parent": null,
 "core": "<core id from db/cores.json>", "version": "5.0", "status": "active",
 "texts": {"en": {"name": "...", "short": "...", "keywords": ["..."], "body": "**Mission.** ...\n"},
           "it": {"name": "...", "short": "...", "keywords": ["..."], "body": "**Missione.** ...\n"}}}
```

- `id`: lowercase, words joined by `-`, new, not a strategy name (in English or Italian), nor `local`, `light` or
  their Italian names. Role ids are data: they are the same in every language.
- A sub-professional has `parent` = a professional of the same core (one level only).
- Texts in **English**, complete (the CI refuses an entry without them); the other languages are optional, and complete
  if present: an installation in a language the entry lacks generates the agent from English with the mark
  `translation-pending: <language>` and translates it locally at its first use (`translate`). The body follows the
  card structure (mission, skills, questions it always asks, methods and tools, typical deliverables, limits, works
  with), with no `#` headings.
- Say in the pull request which skill is missing from the swarm and why the neighbouring roles do not cover it.
- No details of private projects, no secrets, no personal data.

Before opening it:

```
python3 -I -B engine/swarmer.py --swarm . verify
python3 -I -B engine/swarmer.py --swarm . build --output swarmer.sh
for t in tests/test_*.py; do python3 -I -B "$t"; done
```

`build` writes `swarmer.sh` and its copy `sciame.sh`; `build --check` tells whether both are up to date. From a
project with the swarm installed, `bash swarmer/swarmer.sh approve card.json` and
`bash swarmer/swarmer.sh propose <id> --send` do the same and open the pull request with `gh`. The engine also reads
a card in the format 1 of 4.0 (`sigla`, `tipo`, `testi`, …) and writes format 2.

## 2. A new language

- `i18n/<code>.json` with exactly the keys and placeholders of `i18n/en.json`, including the sections `commands`,
  `options` and `values` (the names of the language, as aliases of the English names: no alias may equal another
  canonical name or another alias in the same namespace) and `files` (the names of the documents and project files);
- `docs/<code>/` with every document of `docs/en/`, under the same canonical names and with the same `<!-- … -->`
  block markers byte for byte; `_HELP.txt` has a line for every command;
- the texts of every entry of `db/professionals.json` and `db/cores.json` in the new language;
- the card labels for the language in `engine/compat.py` (`LABELS`).

The protocol lines of juries and convenings (`VOTE`, `OPTION`, `REVISION`, … and their Italian forms) are read by
programs: a language that wants its own words adds them to `engine/compat.py`, with the tests. `verify` checks that
blocks, keys and placeholders match across languages and that no alias collides.

## 3. Fixes and improvements

Engine changes come with a test in `tests/` that fails before and passes after. Keep the standard library only;
code, comments and messages are in English, and every user message comes from `i18n/`. Italian words in code live only
in `engine/compat.py` (and in the blocks of `engine/head.sh` that `build` generates from `i18n/`).
