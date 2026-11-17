# swarmer: the universal agent swarm for coding agents (version 5.2)

A swarm of specialist professionals and sub-professionals, which a coordinator convenes for a request with
one of eight strategies. The coordinator is the session of the coding agent open in the project (Claude Code, Codex,
Antigravity, Gemini CLI, or another tool that reads `AGENTS.md` and Agent Skills); the agents are its
`swarmer-<id>` subagents.

**Setup and launch all live in `swarmer.sh`:** `bash swarmer/swarmer.sh help` prints them. In short:

```
bash swarmer.sh install [--language en|it]           # once per project
bash swarmer/swarmer.sh single     "request"         # single expert
bash swarmer/swarmer.sh fan-out    "request"         # N agents in parallel: slices or a race
bash swarmer/swarmer.sh classic    "request"         # the graph pipeline
bash swarmer/swarmer.sh jury       "request"         # one proposal, one vote
bash swarmer/swarmer.sh light-jury "request"         # three jurors, the test before the vote
bash swarmer/swarmer.sh full       "request"         # the whole swarm, no vote, then the classic
bash swarmer/swarmer.sh plenary    "request"         # the gravest choices: five levels and the final vote
bash swarmer/swarmer.sh expert     "request"         # a skill the swarm does not have yet
bash swarmer/swarmer.sh auto       "request"         # the coordinator chooses
```

From the shell, `--cli claude|codex|agy|gemini` chooses the tool to open (default: the `cli` key of
`.swarmer/config.json`, otherwise the first one in that order whose target is active and that is found in the PATH).
The options go before or after the request; only what follows `--` is passed to the tool. Inside the tool the same
convenings are the skills `swarmer-single`, `swarmer-fan-out`, `swarmer-classic`, `swarmer-jury`,
`swarmer-light-jury`, `swarmer-full`, `swarmer-plenary`, `swarmer-expert` and `swarmer` (in Claude Code also as
slash commands, `/swarmer-single` …).

## The targets

The agents and the skills are generated for the targets of the project (`bash swarmer/swarmer.sh targets`):

| target | agents | skills | instructions |
|---|---|---|---|
| `claude` | `.claude/agents/swarmer-<id>.md` | `.claude/skills/` | `CLAUDE.md` |
| `codex` | `.codex/agents/swarmer-<id>.toml` | `.agents/skills/` | `AGENTS.md` |
| `antigravity` | `.agents/agents/swarmer-<id>.md` | `.agents/skills/` | `AGENTS.md` |
| `gemini` | `.gemini/agents/swarmer-<id>.md` | `.agents/skills/` | `GEMINI.md` |
| `agents` | — | `.agents/skills/` | `AGENTS.md` |

A new installation takes the targets it finds in the project (`.claude/`, `.codex/`, `.gemini/`, `.agents/`,
`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`) plus `agents`, or every target if it finds none; `--targets` chooses them.
An update of an installation without the `targets` key stays Claude Code only. `targets --add X`, `--remove X` or a
list change them: the generated files of a removed target go, the project's own files never.

## The strategies

They are defined in `PIPELINE.md`; the jury, new experts and the plenary are detailed in `JURY.md`.

| strategy | for | agents |
|---|---|---|
| single | a clear question in one field | 1 |
| fan-out | divisible work, or several attempts racing under a selection rule declared in advance | 2–16 |
| classic | deciding, designing, fixing, proving, measuring | 6–15 |
| jury | deciding a proposal already prepared: consensus approves, majority revises, minority rejects | 7–11 |
| light-jury | small decisions, or ones a quick test can check: three jurors, the test before the vote, one round | 5 |
| full | strategic or open questions, every point of view, no vote | all professionals plus the classic |
| plenary | phase transitions and choices of enormously important impact | 60–80 and more |
| expert | a missing skill: provisional card, recorded request, creation at the threshold | 1 |
| auto | unknown which: the coordinator chooses the cheapest one that suffices | — |

Every brief follows the same template (`PIPELINE.md`, «The brief, in every strategy»): goal and done criterion,
inputs, write scope and forbidden scope, verification, a response with DONE, ISSUES or BLOCKED at the top.

## The roles: professionals and sub-professionals

The single database is `db/professionals.json`: each entry has the role id, the type, the parent (for a
sub-professional), the core, the version and the texts: English always and complete, the other languages optional.
A role without the language of the installation is generated from English with the mark `translation-pending:
<language>`, and the coordinator translates it at its first convening with `bash swarmer/swarmer.sh translate <id>
<file.json>` (local overlay `local/translations/`, never published: `local/LOCAL_README.md` of this folder). `AGENTS.md`, the agents, the skills and the
catalog are generated from it, in the chosen language: they are not edited by hand. The role ids are data and are the
same in every language (`arbitro`, `avversario`, `debugger`, …).

`bash swarmer/swarmer.sh professionals` prints the tree; `bash swarmer/swarmer.sh roles "question"` the roles that a
question calls up.

## Languages

`bash swarmer/swarmer.sh language it` switches to Italian, `language en` to English: agents, skills and documents
are regenerated, with the names of the language. At installation: `--language`. For a single convening:
`language=it` at the start of the request, or `--language`. The Italian names of the commands and options
(`installa`, `--cartella`, …) are accepted in every installation. A new language is added with a pull request to the
swarm repository (`CONTRIBUTING.md`).

## Local overrides

A project's own cards live in `swarmer/local/AGENTS.md`. For the same role id a local card **always** takes
priority over the generic role; an id that exists only there is a local-only role. The `local/` folder may
contain project details and never goes into the public repository: `build`, `approve`, `propose` and
`verify` do not distribute it, and they reject any public text containing the words in `local/FORBIDDEN.txt`. In a
project that already has its own swarm:

```
bash swarmer.sh install --folder swarmer/skill --local swarmer --project-managed
```

installs the skill in a folder of its own, takes the project's cards as overrides, and neither writes nor deletes the
agents that the project generates itself in `.claude/agents/`; in the other targets (Codex, Antigravity, Gemini CLI)
it generates them from the local cards, unless the project has its own file there without the note. `check` reports
an override the project has not generated. The local cards reach the agents of every target: those files have the
confidentiality of `local/`.

## New experts

A missing skill is requested: in briefs with the `MISSING-EXPERT` line, by the coordinator with the expert
strategy. Requests go into `swarmer/EXPERT_REQUESTS.md`; `bash swarmer/swarmer.sh requests` tells which have reached
the threshold. Once creation is approved, `bash swarmer/swarmer.sh approve <card.json>`:
1. adds it to the database;
2. regenerates agents, skills and documents;
3. rebuilds `swarmer.sh`, so the portable copy is always up to date;
4. writes the proposal in `swarmer/proposals/`.

`bash swarmer/swarmer.sh propose <id> --send` opens the pull request to the public swarm repository (requires `gh`),
always in English: an entry without complete English texts is refused until `translate <id> <file.json> --language en`.

## Extensions
An extension adds commands, a skill, documents and a block of instructions for the coordinator, and keeps its own
state under `.swarmer/`. Every extension ships inside `swarmer.sh` (folder `extensions/`); enabling one is a choice of
the project: `bash swarmer/swarmer.sh extensions` lists them, `extensions --add <name>` enables one (key `extensions`
of `.swarmer/config.json`, then regenerate), `extensions --remove <name>` disables it and leaves its state folder,
which is the project's. The first one is **crossroads** (`bash swarmer/swarmer.sh crossroads …`, skill
`swarmer-crossroads`, documents `CROSSROADS.md` and `CROSSROADS_FORMATS.md`): the decisions of the user, the swarm and
the juries as a graph, commits by concern, and the way back to an upstream fork on a new branch.

## The files in this folder

| file | what it contains |
|---|---|
| `swarmer.sh` | a single file: installs, launches, updates; carries all the others with it |
| `db/` | the single database of professionals and cores (`professionals.json`, `cores.json`) |
| `docs/<language>/` | the documents in the skill's languages |
| `i18n/<language>.json` | the texts of the generator and of the commands, and the names of each language |
| `engine/` | the code: `swarmer.py` (the command line), `generate.py` (the generators of every target), `professionals.py`, `convene.py`, `jury.py`, `compat.py` (the Italian names of 4.0) |
| `tests/` | the test batteries: `bash swarmer/swarmer.sh tests` |
| `AGENTS.md`, `PIPELINE.md`, `PREAMBLE.md`, `JURY.md`, `ENVIRONMENT.md`, `COORDINATOR_INSTRUCTIONS.md`, `HYPOTHESIS_CARD.md` | generated in the chosen language |
| `convene.py`, `jury.py`, `generate_agents.py` | the usual commands, which hand over to the engine |
| `catalog.json`, `VERSION`, `LANGUAGE`, `ROOT`, `FACTORY.json` | generated and state files |
| `local/`, `EXPERT_REQUESTS.md`, `proposals/` | the project's own: never distributed |

## Updating

`bash swarmer.sh -C <project> update`, with the new `swarmer.sh`. Factory files that the project has not changed are
updated. Those it has changed stay as they were, and the new version goes alongside them with the `.new` suffix. The
database is merged: new entries are added and the project's entries remain. From a 3.x the cards are kept in a backup
copy, and `import-cards` brings into the database those that the project had added.

**From 4.0 (`sciame`).** The same command updates an installation of the 4.0: the internal state, the engine and the
database take their 5.0 names, while the project's files (configuration, local cards, expert register, forbidden
words, convenings and juries) are never renamed. An Italian 4.0 stays Italian, with the same agents and skills
(`sciame-*`); an English 4.0 moves to `swarmer-*`, with `sciame.sh`, `convoca.py` and `giuria.py` kept as aliases.
Going back to 4.0 is not supported.

**From 5.0.** The update to 5.1 or later keeps a 5.0 installation as it was: Claude Code only, the same agents byte for
byte, the same skills (with the new section on delegating in each tool). Other targets are added on request: `bash swarmer/swarmer.sh targets --add codex,gemini`.

**From 5.1.** The update to 5.2 enables no extension (`bash swarmer/swarmer.sh extensions --add crossroads` when you
want it) and leaves every gate already approved valid: a convening started before keeps the rules 1 of its gates, a
new one is born with the rules 2 (`PIPELINE.md`, §«The rules of the gates»).
