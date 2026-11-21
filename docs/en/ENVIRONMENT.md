# The environment: what the swarm does with the tools it finds

The swarm is universal: its rules apply in every coding agent that reads skills in the `<name>/SKILL.md` format (Agent
Skills). The installation generates the agents and the skills for the targets of the project: Claude Code, Codex,
Antigravity, Gemini CLI, and the open standard (`AGENTS.md` and `.agents/skills/`) that many other tools read. This
document says how the coordinator adapts a convening to what the environment actually offers.

| target | agents | skills | instructions | started by `--cli` |
|---|---|---|---|---|
| `claude` (Claude Code) | `.claude/agents/<prefix>-<id>.md` | `.claude/skills/<name>/SKILL.md` | `CLAUDE.md` | `claude "<prompt>"` |
| `codex` (Codex CLI) | `.codex/agents/<prefix>-<id>.toml` | `.agents/skills/<name>/SKILL.md` | `AGENTS.md` | `codex "<prompt>"` |
| `antigravity` (Antigravity, `agy`) | `.agents/agents/<prefix>-<id>.md` | `.agents/skills/<name>/SKILL.md` | `AGENTS.md` | `agy -i "<prompt>"` |
| `gemini` (Gemini CLI) | `.gemini/agents/<prefix>-<id>.md` | `.agents/skills/<name>/SKILL.md` | `GEMINI.md` | `gemini -i "<prompt>"` |
| `agents` (open standard) | — | `.agents/skills/<name>/SKILL.md` | `AGENTS.md` | — |

`bash swarmer/swarmer.sh targets` shows and changes them; the instruction files are written only by
`bash swarmer/swarmer.sh instructions`.

<!-- environment -->
## Capabilities, and what to do when they are missing

Before convening, the coordinator looks at what the environment actually grants, not at what one would expect.
It uses only the capabilities the environment exposes. When one is missing, it keeps the strategy's phases and checks and takes the
closest honest path, declaring it in the answer.

| capability | if present | if missing |
|---|---|---|
| subagents | one agent per role, with the tool the environment offers (Claude Code: Agent with `subagent_type: "swarmer-<id>"`; Codex: the agent spawned by name; Antigravity: `invoke_subagent`; Gemini CLI: the tool with the subagent's name; `@swarmer-<id>` is the user's syntax, not the coordinator's) | the coordinator performs the roles one after another in the same session, each with its own brief, and writes at the top of the answer "roles performed in sequence by the coordinator: independence is reduced" |
| parallel subagents | the independent phases in the same message, at most five at a time | one after another, in the same order as the waves |
| model choice per role | the model written in `.swarmer/config.json` (`bash swarmer/swarmer.sh models`; it goes into the Claude Code agents, the other tools use the model of the session) | the session's model, declared |
| shell | `convene.py` and `jury.py` prepare and check | the coordinator checks the gates against the written conditions, draws the sentinels among the free roles fit for the question and numbers the K# in one list for the convening, writing the draw and the list down, and declares it |
| writes | each agent in its own folder in `.swarmer/` | the briefs in the prompts; the answers are the deliverables |
| structured questions to the user | the environment's tool (in Claude Code: AskUserQuestion), with the options and the recommended one first | a single clear question in the text |
| network | reading documentation and public sources | "not verified" on what needed checking outside |
| long-running work | the environment's mechanisms for resuming (reminders, waits, loops) | a `JOURNAL.md` in the convening's folder, with the done criterion and the resume points |

**Never fake a capability.** Do not write that an agent, a review, a test or a check has run if
the environment has not reported it. A fact the coordinator can check on its own is not asked of the user: it is
checked.

**The coordinator remains responsible.** Questions to the user, approvals, integration and final verification
are the coordinator's. Agents' reports are evidence: before saying "done", the coordinator looks at the files produced and
reruns the promised checks on the integrated result.

**Where not to look.** No convening reads the conversations or files of other projects, or the environment's global
folders, unless the request asks for it and says where.
<!-- /environment -->

## Models per role

`bash swarmer/swarmer.sh models` shows and changes the model of each role or each class of roles, in
`.swarmer/config.json`:

```
bash swarmer/swarmer.sh models                        # what is there
bash swarmer/swarmer.sh models arbitro=opus           # one role
bash swarmer/swarmer.sh models critico=opus           # one core
bash swarmer/swarmer.sh models --all=inherit          # all like the session
```

The value ends up in the `model` field of the generated agents. A name the environment does not know does no harm by itself, but
the agent does not start: after the change, `bash swarmer/swarmer.sh check`.

## Other environments

- **Limits of the tools.** A Gemini CLI subagent cannot call other agents: the coordinator, the main session,
  launches them all. Codex agents inherit the permissions, the sandbox and the MCP servers of the session that
  spawns them. Antigravity and Gemini CLI read the agents of their own folder; Codex and the open standard read
  `.agents/skills/`.
- **Plugin.** For Claude Code the repository is also a plugin, one of the ways to install it:
  `/plugin marketplace add <owner>/<repository>`, then `/plugin install swarmer` and `/swarmer-install`. The plugin
  brings the installer skills; the local overrides stay in the project.
- **Skills only.** Copy the generated `.agents/skills/` (or `.claude/skills/`) folder into the environment's skills
  folder: the strategies work even without project agents, with the roles performed as the table above says.
- **A model via API**, without subagents: a program of your own acts as the coordinator, one call per role, with the
  texts of `swarmer/catalog.json` (see `COORDINATOR_INSTRUCTIONS.md`).
