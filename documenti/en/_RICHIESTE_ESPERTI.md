# Requests for experts that do not exist yet

Each row is a request. It is brought here by the coordinator, from the `ESPERTO-MANCANTE` (missing expert) lines of
the deliverables, or by whoever convenes a provisional expert. The reason says which roles were examined and why they
do not cover the skill: a row without a reason does not count. `bash sciame/sciame.sh richieste` lists the skills
that have reached the threshold:
- 3 distinct roles in one convening, 5 in a plenary;
- or 3 requests in 2 convenings from 2 roles.

The coordinator counts once per skill. The convening is the path of its folder in `.sciame/`,
relative to the project root.

| date | convening | requester | skill | subject | reason |
|---|---|---|---|---|---|

## Closed

One row per skill: `` - `sigla`: created, no. NN (date) `` or `` - `sigla`: merged into `altra`, reason ``.
