# swarmer — a universal agent swarm for coding agents

*[Italiano](README.it.md)*

**swarmer** is a team of specialist agents for coding agents — Claude Code, Codex, Antigravity, Gemini CLI and every
tool that reads `AGENTS.md` and Agent Skills — that a coordinator convenes for one request, with one of eight
strategies. The roles are **professionals** (general skills) and **sub-professionals** (their
specialisations), kept in one database, in English and optionally in the other languages of the skill. The whole skill — documents, database
and engine — fits in a single file, `swarmer.sh`, using only bash and the Python standard library. Version 5.1 makes it universal (5.0
was for Claude Code only, and the successor of `sciame` 4.0, which it updates in place).

## Install

```
# one file, into any project
curl -fsSLO https://raw.githubusercontent.com/GritHat/swarmer/main/swarmer.sh
bash swarmer.sh install                      # English; --language it for Italian
bash swarmer.sh install --targets codex,gemini   # only some tools (default: the ones found in the project)

# or, in Claude Code, as a plugin (one of the ways to install it)
/plugin marketplace add GritHat/swarmer
/plugin install swarmer
/swarmer-install en

# or from Agensi (agensi.io): SKILL.md and a small script that reads the roles and the protocol on demand
# from the catalog published on GitHub Pages (nothing to install)
```

Then reopen the session of your coding agent and convene the swarm with a skill (in Claude Code also a slash command;
in Codex, Antigravity and Gemini CLI name the skill in the prompt):

| strategy | skill | for | agents |
|---|---|---|---|
| single | `/swarmer-single` | one clear question in one field | 1 |
| fan-out | `/swarmer-fan-out` | divisible work in parallel slices, or a race with a selection rule declared first | 2–16 |
| classic | `/swarmer-classic` | decide, design, fix, prove, measure: blind lanes, triage, falsifier tournament, branches, verdicts | 6–15 |
| jury | `/swarmer-jury` | decide a prepared proposal: unanimity approves, majority revises (≤ 3 rounds, no regressions), minority rejects | 7–11 |
| light jury | `/swarmer-light-jury` | small, low-influence decisions, or where a quick test exposes a mistake: three jurors, test before the vote, one round, then the ordinary jury | 5 |
| full | `/swarmer-full` | strategic or open questions: every professional, blind, no vote, then a classic | all + classic |
| plenary | `/swarmer-plenary` | phase transitions and enormously important choices: full, usual convening, critical pass, two arbiters, final vote | 60–80+ |
| new expert | `/swarmer-expert` | a skill the swarm lacks: provisional card, request logged, role created at the threshold | 1 |
| auto | `/swarmer` | the coordinator picks the cheapest strategy that suffices, and says so | — |

From the shell: `bash swarmer/swarmer.sh <strategy> "request" [--cli claude|codex|agy|gemini]` opens the tool with
the skill. The options of the swarm go before or after the request; only what follows `--` is passed to the tool
(`… single "request" --cli claude -- --permission-mode plan`), and any other extra word is an error.
`bash swarmer/swarmer.sh help` lists every command.
Every command, option and value also has an Italian name (`installa`, `singolo`, `--cartella`, …), accepted in every
installation; abbreviated options are not accepted.

## Works with

swarmer is not tied to one tool: it generates its agents and skills for every **target** of the project, and the
coordinator is whatever coding agent you open there.

| target | tool | agents | skills | instructions | open it with |
|---|---|---|---|---|---|
| `claude` | Claude Code | `.claude/agents/swarmer-<id>.md` | `.claude/skills/<skill>/SKILL.md` | `CLAUDE.md` | `claude` |
| `codex` | Codex CLI (OpenAI) | `.codex/agents/swarmer-<id>.toml` | `.agents/skills/<skill>/SKILL.md` | `AGENTS.md` | `codex` |
| `antigravity` | Antigravity (app and `agy`) | `.agents/agents/swarmer-<id>.md` | `.agents/skills/<skill>/SKILL.md` | `AGENTS.md` | `agy` |
| `gemini` | Gemini CLI | `.gemini/agents/swarmer-<id>.md` | `.agents/skills/<skill>/SKILL.md` | `GEMINI.md` | `gemini` |
| `agents` | any tool that reads the open standard | — | `.agents/skills/<skill>/SKILL.md` | `AGENTS.md` | — |

A new installation picks the targets it finds in the project (`.claude/`, `.codex/`, `.gemini/`, `.agents/`,
`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`) plus `agents`, or all of them in an empty project; `--targets
claude,codex,…` chooses them, and `bash swarmer/swarmer.sh targets [--add X] [--remove X]` changes them later (the
generated files of a removed target go, the project's own files never; an inactive target is neither touched nor
examined). `disable-model-invocation` (full, plenary) exists only in Claude Code: in the shared skills the
restriction is in the description. The skills shared by Codex, Antigravity,
Gemini CLI and the open standard are written once, in `.agents/skills/`. In a tool without subagents the coordinator
performs the roles in sequence and says so. `instructions` writes the swarm's paragraph into the instruction file of
each active target, only when asked.

## What makes it different

- **Every brief is self-contained**: goal and done criterion, inputs, writable and forbidden scope, the check to run,
  and an answer that starts with DONE, ISSUES or BLOCKED. Agent reports are evidence, not proof: the coordinator
  re-runs the promised checks on the integrated result.
- **Decisions are verifiable**: jury votes are sealed (sha256), blind, recounted from the files by `jury.py`, with a
  goal clause (target, chain, counterfactual, cost) that every proposal must pass.
- **The swarm grows when it must**: missing skills are requested with a reason; three requesters in one convening, or
  three requests across two convenings, make a new professional — added to the database, the agents and `swarmer.sh`.
- **Local overrides**: a project's own cards live in `swarmer/local/`, always take priority over the generic roles,
  may contain private project details, and are never published.
- **Honest about the host**: no sub-agents, no shell or no writes? The coordinator keeps the steps and says what was
  reduced (`ENVIRONMENT.md`). It knows how each tool delegates (Agent in Claude Code, spawning by name in Codex,
  `invoke_subagent` in Antigravity, the subagent's tool in Gemini CLI, where `@name` is the user's own shortcut) and its limits.

## Languages

English (the default) and Italian. Switch with `bash swarmer/swarmer.sh language it` (agents, skills and documents
are regenerated with the names of the language), or per convening with `language=it`. In an Italian installation
everything written into the project is Italian: the `sciame/` folder, `sciame-*` agents and skills, `GIURIA.md`,
the Italian protocol lines. The protocol lines of juries and convenings are read in both languages. New languages are
welcome as pull requests: see [CONTRIBUTING.md](CONTRIBUTING.md).

## Updating from sciame 4.0

```
curl -fsSLO https://raw.githubusercontent.com/GritHat/swarmer/main/swarmer.sh
bash swarmer.sh -C <project> update
```

The old `sciame.sh aggiorna`, downloaded again, does the same. The update renames only what belongs to the swarm (the
engine, the database, the internal state: `FABBRICA.json` → `FACTORY.json`, `catalogo.json` → `catalog.json`, …) and
never the project's files: configuration, local cards, expert register, forbidden words, convenings and juries keep
their names, and every jury outcome already voted is recounted byte for byte. An Italian 4.0 stays Italian, with the
same `sciame-*` agents and skills; an English 4.0 moves to `swarmer-*` and English names, with `sciame.sh`,
`convoca.py` and `giuria.py` kept as aliases. An interrupted update resumes with the same command.

## Updating from swarmer 5.0

The same `update` keeps a 5.0 installation as it was: Claude Code only, the same agents byte for byte, the same
skills (their text gains the section on delegating in each tool), the configuration untouched; the folders of the
other tools are neither touched nor examined. Add other tools when you want them: `bash swarmer/swarmer.sh targets --add codex,gemini`.

**Going back to 4.0 is not supported**: a 4.0 `sciame.sh` does not recognise `FACTORY.json`, `engine/` or the 5.0
markers. Other breaking changes: abbreviated options are rejected; new juries also read English protocol lines, and
almost-conforming lines in `SEALS.md`, `DELEGATION.md` and `RELEVANCE.md`, or round tokens that name no round, are
errors.

## Propose a new professional

Open a pull request that adds an entry to `db/professionals.json` with complete English texts (mandatory; the other
languages are optional, and an installation translates a missing one at its first use)
(template: `.github/PULL_REQUEST_TEMPLATE/new_professional.md`), or from a project with the swarm installed:
`bash swarmer/swarmer.sh approve card.json` then `bash swarmer/swarmer.sh propose <id> --send`.

## Repository layout

| path | content |
|---|---|
| `db/` | the single database of professionals, sub-professionals and cores (`professionals.json`, `cores.json`) |
| `docs/<lang>/` | the documents, one folder per language, under their canonical names |
| `i18n/<lang>.json` | generator and command texts, and the localized names of commands, options, values and files |
| `engine/` | the engine: `swarmer.py` (CLI), `generate.py` (the generators of every target), `professionals.py`, `convene.py`, `jury.py`, `compat.py` (the Italian names and the 4.0 formats), `head.sh` |
| `wrappers/` | `convene.py` and `jury.py`, copied to the root of an installation |
| `tests/` | the test batteries |
| `swarmer.sh` | the single-file build: `python3 -I -B engine/swarmer.py --swarm . build --output swarmer.sh` |
| `sciame.sh` | a byte-for-byte copy of `swarmer.sh`, so the 4.0 download URL keeps working |
| `agensi/` | the Agensi edition: `SKILL.md` and `scripts/swarm.py`, which reads on demand the catalog that `.github/scripts/agensi.py` generates from `db/` and `docs/en/` (one JSON file per role, strategy and document) and `.github/workflows/agensi.yml` publishes on GitHub Pages (`gh-pages`, `api/v1/`), with the package as a release |
| `skills/` | the installer skills `swarmer-install` and `sciame-installa` (Agent Skills format: any tool that reads skills) |
| `.claude-plugin/` | the manifests of the Claude Code plugin, one of the ways to install |

## Support

swarmer is free and MIT-licensed. If it saves you time, you can support its development on
[Ko-fi](https://ko-fi.com/GritHat).

License: MIT.
