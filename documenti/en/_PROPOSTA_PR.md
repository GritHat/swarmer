## Proposal of new professionals for the swarm

This pull request adds to the `db/professionisti.json` database:

{voci}

- [ ] Every entry has its texts in all the languages of the repository (currently Italian and English).
- [ ] The code name is new, lowercase, and is not the name of a strategy.
- [ ] A sub-professional has as parent a professional of the same core.
- [ ] No details of a private project, no secrets: `python3 -I motore/sciame.py --sciame . verifica` passes.
- [ ] `sciame.sh` is rebuilt: `python3 -I motore/sciame.py --sciame . costruisci --uscita sciame.sh`.
- [ ] The reason: which skill the swarm lacks, and why the neighbouring roles do not cover it.
