# The swarm's local folder

This folder belongs to the project and **must never** go into the public swarm repository. It holds:
- `AGENTS.md`: cards in the format of `swarmer/AGENTS.md` (heading `### N. Name — `swarmer-id``, lines **In short**,
  **Core**, **Keywords**). For the same role id a local card **always** takes priority over the generic role;
  an id that exists only here is a local-only role. The cards may contain project details. Their text also goes
  into the agents generated for every active target (`.claude/agents/`, `.codex/agents/`, `.agents/agents/`,
  `.gemini/agents/`): those files have the same confidentiality as this folder, and `.agents/` is read by many tools.
- `JURY.md`, `PIPELINE.md`, `PREAMBLE.md`: the project's own rules, which add to the generic ones or
  replace them, saying so.
- `EXIT_CRITERIA.md`: the exit criteria of the project's phases, which the goal clause of the juries cites.
- `FORBIDDEN.txt`: one word or expression per line that must never leave the project (names, codes, people).
  `approve`, `propose`, `build` and `verify` reject any public text that contains them.

- `translations/<language>/<id>.json`: the translations of the roles that the public database does not have in the
  language of the installation, registered by `bash swarmer/swarmer.sh translate <id> <file.json>` (the coordinator
  makes them the first time it convenes a role marked `translation-pending`). They are never distributed nor
  published and survive the updates. When the public database later brings its own translation, **the public one
  wins**, unless the local one was modified by hand after `translate` (its fingerprint, `written_sha256`, no longer
  matches): then the local one stays.

After a change: `bash swarmer/swarmer.sh regenerate`.
