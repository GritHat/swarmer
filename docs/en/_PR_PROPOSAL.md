## Proposal of new professionals for the swarm

This pull request adds to the `db/professionals.json` database:

{entries}

- [ ] Every entry has complete English texts (mandatory); the other languages are optional, and complete if present.
- [ ] The id is new, lowercase, and is not the name of a strategy.
- [ ] A sub-professional has as parent a professional of the same core.
- [ ] No details of a private project, no secrets: `python3 -I -B engine/swarmer.py --swarm . verify` passes.
- [ ] `swarmer.sh` is rebuilt: `python3 -I -B engine/swarmer.py --swarm . build --output swarmer.sh`.
- [ ] The reason: which skill the swarm lacks, and why the neighbouring roles do not cover it.
