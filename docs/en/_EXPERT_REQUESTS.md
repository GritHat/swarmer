# Requests for experts that do not exist yet

Each row is a request. It is brought here by the coordinator, from the `MISSING-EXPERT` lines of the deliverables,
or by whoever convenes a provisional expert. The reason says which roles were examined and why they do not cover the
skill: a row without a reason does not count. `bash swarmer/swarmer.sh requests` lists the skills that have reached
the threshold:
- 3 distinct roles in one convening, 5 in a plenary;
- or 3 requests in 2 convenings from 2 roles.

The coordinator counts once per skill. The convening is the path of its folder in `.swarmer/`,
relative to the project root. The requester is a role id, `coordinator` or `provisional:<id>`.

| date | convening | requester | skill | subject | reason |
|---|---|---|---|---|---|

## Closed

One row per skill: `` - `id`: created, no. NN (date) `` or `` - `id`: merged into `other`, reason ``.
