# sciame — an agent swarm for Claude Code

*[Italiano](README.it.md)*

**sciame** (Italian for *swarm*) is a team of specialist agents for Claude Code that a coordinator convenes for one
request, with one of eight strategies. The roles are **professionals** (general skills) and **sub-professionals**
(their specialisations), kept in one database in every language the skill supports. The whole skill — documents,
database and engine — fits in a single file, `sciame.sh`, using only bash and the Python standard library.

## Install

```
# one file, into any project
curl -fsSLO https://raw.githubusercontent.com/GritHat/swarmer/main/sciame.sh
bash sciame.sh installa --lingua en          # or --lingua it

# or as a Claude Code plugin
/plugin marketplace add GritHat/swarmer
/plugin install sciame
/sciame-installa en
```

Then reopen the Claude Code session and convene the swarm:

| strategy | skill | for | agents |
|---|---|---|---|
| single | `/sciame-singolo` | one clear question in one field | 1 |
| fan-out | `/sciame-ventaglio` | divisible work in parallel slices, or a race with a selection rule declared first | 2–16 |
| classic | `/sciame-classica` | decide, design, fix, prove, measure: blind lanes, triage, falsifier tournament, branches, verdicts | 6–15 |
| jury | `/sciame-giuria` | decide a prepared proposal: unanimity approves, majority revises (≤ 3 rounds, no regressions), minority rejects | 7–11 |
| light jury | `/sciame-giuria-leggera` | small, low-influence decisions, or where a quick test exposes a mistake: three jurors, test before the vote, one round, then the ordinary jury | 5 |
| full | `/sciame-completa` | strategic or open questions: every professional, blind, no vote, then a classic | all + classic |
| plenary | `/sciame-plenaria` | phase transitions and enormously important choices: full, usual convening, critical pass, two arbiters, final vote | 60–80+ |
| new expert | `/sciame-esperto` | a skill the swarm lacks: provisional card, request logged, role created at the threshold | 1 |
| auto | `/sciame` | the coordinator picks the cheapest strategy that suffices, and says so | — |

From the shell: `bash sciame/sciame.sh <strategy> "request"`; English aliases work (`single`, `fan-out`, `classic`,
`jury`, `full`, `plenary`, `expert`). `bash sciame/sciame.sh help` lists every command.

## What makes it different

- **Every brief is self-contained**: goal and done criterion, inputs, writable and forbidden scope, the check to run,
  and an answer that starts with DONE, ISSUES or BLOCKED. Agent reports are evidence, not proof: the coordinator
  re-runs the promised checks on the integrated result.
- **Decisions are verifiable**: jury votes are sealed (sha256), blind, recounted from the files by `giuria.py`, with a
  goal clause (target, chain, counterfactual, cost) that every proposal must pass.
- **The swarm grows when it must**: missing skills are requested with a reason; three requesters in one convening, or
  three requests across two convenings, make a new professional — added to the database, the agents and `sciame.sh`.
- **Local overrides**: a project's own cards live in `sciame/locale/`, always take priority over the generic roles,
  may contain private project details, and are never published.
- **Honest about the host**: no sub-agents, no shell or no writes? The coordinator keeps the steps and says what was
  reduced (`AMBIENTE.md`).

## Languages

Italian and English. Switch with `bash sciame/sciame.sh lingua en` (agents, skills and documents are regenerated),
or per convening with `lingua=en`. New languages are welcome as pull requests: see [CONTRIBUTING.md](CONTRIBUTING.md).

## Propose a new professional

Open a pull request that adds an entry to `db/professionisti.json` with texts in every language of the repository
(template: `.github/PULL_REQUEST_TEMPLATE/new_professional.md`), or from a project with the swarm installed:
`bash sciame/sciame.sh approva card.json` then `bash sciame/sciame.sh proponi <code> --invia`.

## Repository layout

| path | content |
|---|---|
| `db/` | the single database of professionals, sub-professionals and cores |
| `documenti/<lang>/` | the documents, one folder per language |
| `i18n/<lang>.json` | generator and command texts |
| `motore/` | the engine: `sciame.py` (CLI), `genera.py`, `professionisti.py`, `convoca.py`, `giuria.py`, `testa.sh` |
| `prove/` | the test batteries |
| `sciame.sh` | the single-file build: `python3 -I motore/sciame.py --sciame . costruisci --uscita sciame.sh` |
| `skills/`, `.claude-plugin/` | the Claude Code plugin (installer skill and manifests) |

License: MIT.
