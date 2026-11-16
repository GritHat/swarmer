# The agent swarm for Claude Code (version 4.0)

A swarm of specialist professionals and sub-professionals, which a coordinator convenes for a request with
one of eight strategies. The coordinator is the Claude Code session open in the project; the agents are its
`sciame-<sigla>` subagents.

**Setup and launch all live in `sciame.sh`:** `bash sciame/sciame.sh aiuto` prints them. In short:

```
bash sciame.sh installa [--lingua it|en]       # once per project
bash sciame/sciame.sh singolo   "request"       # single expert
bash sciame/sciame.sh ventaglio "request"       # N agents in parallel: slices or a race
bash sciame/sciame.sh classica  "request"       # the graph pipeline
bash sciame/sciame.sh giuria    "request"       # one proposal, one vote
bash sciame/sciame.sh completa  "request"       # the whole swarm, no vote, then the classic
bash sciame/sciame.sh plenaria  "request"       # the gravest choices: five levels and the final vote
bash sciame/sciame.sh esperto   "request"       # a skill the swarm does not have yet
bash sciame/sciame.sh auto      "request"       # the coordinator chooses
```

Inside Claude Code the same convenings are `/sciame-singolo`, `/sciame-ventaglio`, `/sciame-classica`,
`/sciame-giuria`, `/sciame-completa`, `/sciame-plenaria`, `/sciame-esperto` and `/sciame`.

## The strategies

They are defined in `PIPELINE.md`; the jury, new experts and the plenary are detailed in `GIURIA.md`.

| strategy | for | agents |
|---|---|---|
| singolo | a clear question in one field | 1 |
| ventaglio | divisible work, or several attempts racing under a selection rule declared in advance | 2–16 |
| classica | deciding, designing, fixing, proving, measuring | 6–15 |
| giuria | deciding a proposal already prepared: consensus approves, majority revises, minority rejects | 7–11 |
| giuria-leggera | small decisions, or ones a quick test can check: three jurors, the test before the vote, one round | 5 |
| completa | strategic or open questions, every point of view, no vote | all professionals plus the classic |
| plenaria | phase transitions and choices of enormously important impact | 60–80 and more |
| esperto | a missing skill: provisional card, recorded request, creation at the threshold | 1 |
| auto | unknown which: the coordinator chooses the cheapest one that suffices | — |

Every brief follows the same template (`PIPELINE.md`, «La consegna, in ogni strategia»): goal and done criterion,
inputs, write scope and forbidden scope, verification, a response with DONE, ISSUES or BLOCKED at the top.

## The roles: professionals and sub-professionals

The single database is `db/professionisti.json`: each entry has the code name, the type, the parent (for a
sub-professional), the core, the version and the texts in every language. `AGENTI.md`, the agents, the skills and the
catalogue are generated from it, in the chosen language: they are not edited by hand.

`bash sciame/sciame.sh professionisti` prints the tree; `bash sciame/sciame.sh ruoli "question"` the roles that a
question calls up.

## Languages

`bash sciame/sciame.sh lingua en` switches to English, `lingua it` to Italian: agents, skills and documents are
regenerated. At installation: `--lingua`. For a single convening: `lingua=en` at the start of the request, or
`--lingua`. A new language is added with a pull request to the swarm repository (`CONTRIBUTING.md`).

## Local overrides

A project's own cards live in `sciame/locale/AGENTI.md`. For the same code name a local card **always** takes
priority over the generic role; a code name that exists only there is a local-only role. The `locale/` folder may
contain project details and never goes into the public repository: `costruisci`, `approva`, `proponi` and
`verifica` do not distribute it, and they reject any public text containing the words in `locale/VIETATE.txt`. In a
project that already has its own swarm:

```
bash sciame.sh installa --cartella sciame/skill --locale sciame --gestiti-dal-progetto
```

installs the skill in a folder of its own, takes the project's cards as overrides, and neither writes nor deletes the
agents that the project generates itself.

## New experts

A missing skill is requested: in briefs with the `ESPERTO-MANCANTE` line (missing expert), by the coordinator with
the esperto strategy. Requests go into `sciame/RICHIESTE_ESPERTI.md`; `bash sciame/sciame.sh richieste` tells which
have reached the threshold. Once creation is approved, `bash sciame/sciame.sh approva <scheda.json>`:
1. adds it to the database;
2. regenerates agents, skills and documents;
3. rebuilds `sciame.sh`, so the portable copy is always up to date;
4. writes the proposal in `sciame/proposte/`.

`bash sciame/sciame.sh proponi <sigla> --invia` opens the pull request to the public swarm repository (requires `gh`).

## The files in this folder

| file | what it contains |
|---|---|
| `sciame.sh` | a single file: installs, launches, updates; carries all the others with it |
| `db/` | the single database of professionals and cores |
| `documenti/<lingua>/` | the documents in the skill's languages |
| `i18n/<lingua>.json` | the texts of the generator and of the commands |
| `motore/` | the code: `sciame.py` (the command line), `genera.py`, `professionisti.py`, `convoca.py`, `giuria.py` |
| `prove/` | the test suites: `bash sciame/sciame.sh prove` |
| `AGENTI.md`, `PIPELINE.md`, `PREAMBOLO.md`, `GIURIA.md`, `AMBIENTE.md`, `ISTRUZIONI_COORDINATORE.md`, `SCHEDA_IPOTESI.md` | generated in the chosen language |
| `convoca.py`, `giuria.py`, `genera_agenti.py` | the usual commands, which hand over to the engine |
| `catalogo.json`, `VERSIONE`, `LINGUA`, `FABBRICA.json` | generated and state files |
| `locale/`, `RICHIESTE_ESPERTI.md`, `proposte/` | the project's own: never distributed |

## Updating

`bash sciame-nuovo.sh -C <progetto> aggiorna`. Factory files that the project has not changed are updated.
Those it has changed stay as they were, and the new version goes alongside them with the `.nuovo` suffix. The
database is merged: new entries are added and the project's entries remain. From a 3.x the cards are kept in a backup
copy, and `importa-schede` brings into the database those that the project had added.
