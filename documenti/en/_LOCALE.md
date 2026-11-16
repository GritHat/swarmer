# The swarm's local folder

This folder belongs to the project and **must never** go into the public swarm repository. It holds:
- `AGENTI.md`: cards in the format of `sciame/AGENTI.md` (heading `### N. Name — `sciame-sigla``, lines **In breve**,
  **Nucleo**, **Parole chiave**). For the same code name a local card **always** takes priority over the generic role;
  a code name that exists only here is a local-only role. The cards may contain project details.
- `GIURIA.md`, `PIPELINE.md`, `PREAMBOLO.md`: the project's own rules, which add to the generic ones or
  replace them, saying so.
- `USCITE.md`: the exit criteria of the project's phases, which the goal clause of the juries cites.
- `VIETATE.txt`: one word or expression per line that must never leave the project (names, codes, people).
  `approva`, `proponi`, `costruisci` and `verifica` reject any public text that contains them.

After a change: `bash sciame/sciame.sh rigenera`.
