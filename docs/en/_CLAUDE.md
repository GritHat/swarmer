## Agent swarm

This project has a swarm of specialist agents in `swarmer/`: professionals and sub-professionals, agents
`swarmer-<id>` (in `.claude/agents/`, `.codex/agents/`, `.agents/agents/` or `.gemini/agents/`, by tool). It is
convened only when the user asks, with the skill of a strategy (in `.claude/skills/` or `.agents/skills/`; in Claude
Code also a slash command): **single** (`swarmer-single`), **fan-out** (`swarmer-fan-out`), **classic**
(`swarmer-classic`), **jury** (`swarmer-jury`), **light jury** (`swarmer-light-jury`), **full** (`swarmer-full`),
**plenary** (`swarmer-plenary`), **new expert** (`swarmer-expert`) or **auto** (`swarmer`).
The rules are in `swarmer/PREAMBLE.md`, the strategies in `swarmer/PIPELINE.md`, jury and plenary in
`swarmer/JURY.md`, the cards in `swarmer/AGENTS.md`; the local cards in `swarmer/local/` take priority.
