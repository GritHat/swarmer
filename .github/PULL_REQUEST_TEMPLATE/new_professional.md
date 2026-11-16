## New professional(s) for the swarm

Entries added to `db/professionals.json`:

- `swarmer-<id>` (professional | sub-professional of `swarmer-<parent>`): <name>

- [ ] Complete English texts (mandatory: the CI refuses an entry without them); the other languages are optional.
- [ ] The id is new, lowercase, and not a strategy name.
- [ ] A sub-professional has a professional of the same core as parent.
- [ ] No private project details, no secrets: `python3 -I -B engine/swarmer.py --swarm . verify` passes.
- [ ] `swarmer.sh` rebuilt: `python3 -I -B engine/swarmer.py --swarm . build --output swarmer.sh`.
- [ ] Why: which skill the swarm lacks, and why the neighbouring roles do not cover it.
- [ ] The texts name no single tool: the role works in every target (Claude Code, Codex, Antigravity,
      Gemini CLI, the open standard); `python3 -I -B tests/test_targets.py` passes.
