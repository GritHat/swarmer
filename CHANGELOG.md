# Changelog

*[Italiano](CHANGELOG.it.md)*

## 5.3.0

Backward compatible: every gate is recomputed under the rules it was approved with, so every gate approved before
stays valid. The gate rules 3 apply only to a new convening and to a gate run with `--rules 3`. The `hooks` key is not
part of 5.3.

### The gate rules 3: the order of f4 read from the seals (ENG-19, COORD-1, ENG-21, COORD-2)
- A new convening is born with `gate_rules` 3; `gate C PHASE --rules 3` applies them to one gate of an older one.
- Under the rules 3, G4 orders f4 by the seal times of `SEALS.jsonl`, never by an mtime, which a copy or a touch moves:
  - a `PREDICTIONS.md` of the counterchecks' folder (`01-`) is sealed before `COUNTERCHECKS.md` is first sealed;
  - one of a role that works after the counterchecks (the owner's revision, the debugger, the measurements, V2, the
    arbiter) is sealed before that role's own output is first sealed;
  - every block of a `PREDICTIONS.md` has a seal of its own, the outputs it is ordered against are sealed, and two
    seals in the same second show no order.
- Under the rules 3, G4 refuses a `REVISION.md` that is not first sealed after every `COUNTERCHECKS.md` and
  `DEFECTS.md` of its round.
- The briefs of f4 name the kind of each role's predictions. Under the rules 1 and 2, which order every
  `PREDICTIONS.md` of f4 before the counterchecks, the roles that work after them are asked for their predictions at
  the top of their output instead, and the owner's brief no longer asks for a `PREDICTIONS.md` it could not seal.

### The rounds of a branch (ENG-18, ENG-22)
- `repin C H-00x [--owner ID]` (Italian: `rifissa`) opens round 2, then 3, …, of the f4 of a funded branch, in
  `f4_2/<H#>/`. It writes every brief of f4 again, with the previous round among the inputs, and a dossier of its own.
  No file of an earlier round changes, nor `f3/<H#>/<H#>.md`, nor a seal or a gate.
- `gate C f4/H-00x` is then the G4 of the branch's latest round, `GATE_f4_2_<H#>.json`. It runs only under the rules 3
  and binds and counts only the round's own files. G5 and `status` read the latest round.
- A second `select` is refused: it wrote the empty card over a completed dossier and replaced the recorded selection.

### A later closure after a G5 «not closed» (E12)
- After a G5 that holds and records a non-closure, `fund`, `close-branch` and `repin` act again. A non-closure is
  «closed» false under the rules 2 and 3, or a closure that says «not closed» under the rules 1.
- They brief the next closure beside the first, in `f5_2/` (then `f5_3/`, …). Once that folder exists, `gate C f5`
  checks `f5_2/CLOSURE.md` and its sentinel `f5_2/00-sentinel/SENTINEL.md`, binds every file of `f5_2/`, and writes
  `GATE_f5_2.json`, created exclusively. `GATE_f5.json` and every file it binds stay byte-identical, and the first G5
  still holds.
- The latest G5 is the one of the highest ordinal in its file name, ASCII digits read as an integer; never the newest
  mtime, the gate's time or the last of the sorted names.
- Every reader of G5 reads the latest: `fund`, `close-branch`, `repin`, `select`, `status` and `gate f5`. The lock
  opens only on a latest G5 that holds and records a non-closure.
- A gate file of f5 that is empty, starts with a BOM, is not UTF-8 or is not JSON stops every reader with exit 1 and
  nothing written. So does a second name for one ordinal (`GATE_f5_02.json`).
- Before the next closure is briefed, `gate C f5 --verify` checks the latest G5 again, as in 5.2, and a gate f5 that
  would write over a recorded non-closure is refused.

### The chain to the contract (ENG-26)
- Under the rules 3 every gate checks G0 again, not only the gate just before it: a contract or a file of `f0/`
  changed after G1 refuses every later gate. An amendment's gate checks the other gated amendments again, as every
  other gate already did under the rules 2; an amendment without a gate is not waited for.
- Under the rules 1 and 2 a gate checks only the gate just before it, as in 5.2. `--rules` only raises the rules of
  a gate, never below those of its convening.

### Robustness (ENG-13, ENG-24, ENG-25)
- A file name that is not UTF-8 is bound by its own bytes, as a file of a phase and inside a workspace, where `_tree`,
  `_bind` and the gate's JSON used to stop with a UnicodeEncodeError. The JSON files of a convening write such a name
  as its JSON escape (`\udcff`), so they stay UTF-8; every other byte is written as before, and every tree entry of a
  UTF-8 name keeps its fingerprint.
- Gates, the snapshot, the map, an early closure and the manifest are written to a temporary file beside them and
  moved into place, so a write that fails leaves the old file as it was, never a gate file of 0 bytes. A later gate f5,
  created exclusively, is removed if its write fails.
- `jury.py count .` (or `..`) reads the previous juries beside the jury folder, not inside it: the folder is made
  absolute before its parent is taken. An absolute folder reads them where it did.
- A deliverable, a closure or a contract that only quotes the placeholder `<to fill in>` (in a code span, a fenced
  or indented code block or a sentence) is filled. The placeholder alone on a line, as the whole value of a field
  (`- Results: <to fill in>`, `Slice 1 of 14: <to fill in>`) or as a whole table cell still leaves it unfilled, also
  when a punctuation mark follows it (`- Goal: <to fill in>.`) and when it is indented as the content of a list item.
  This is a relaxation, so it holds under every rule.

### The version (ENG-14)
- The version of swarmer is written in one place, `engine/generate.py` (5.3); the swarm's `VERSION`, the catalog,
  the manifest of a new convening and `convene --help` read it from there. `plugin.json`, from which the Claude Code
  plugin and the Agensi package take theirs, is 5.3.0. The wrappers, the alias stubs and the docstrings of the engine
  no longer state a version, and `tests/test_robustness.py` checks that every document that states one agrees.
- The manifest's `version` is not a format version: no engine reads it. It records the swarmer that prepared the
  convening; 5.0, 5.1 and 5.2 all wrote 5.0 there, and 5.3 writes 5.3.

### The sentinels of f2, f3 and f4, and their draw (ENG-17, ENG-16)
- Chosen with the evidence: PIPELINE is kept, and the engine briefs the sentinels it describes, rather than PIPELINE
  being reduced to f5. Four classic convenings of the lab ran sentinels of f2, f3 and f4 by hand, in
  `<phase>/00-sentinel/` with no brief on disk (so their draw could not be audited), and the f4 sentinel of one of them
  refuted its three G4s as they stood.
- `prepare` briefs the sentinel of f2 in every classic and full, `f2/00-sentinel/TASK.md`: the branches are not known
  before the selection, and the cards and the triage are what every branch inherits. Under the rules 3, G2 wants its
  `SENTINEL.md`, or `--not-delivered <role>`: G2 binds every file of f2, so a sentinel delivered later would
  invalidate it.
- Under the rules 3, with at least two funded branches, `select` and `fund` brief the sentinels of f3 and f4,
  `f3/00-sentinel/` and `f4/00-sentinel/`, once and before any G5. G3 and G4 warn while theirs is missing. The first G5
  wants both, or «Declared missing: sentinel: <reason>», and binds their folders, which no gate of a branch binds. A
  later closure, and a round opened by `repin`, get no new phase sentinel: the closure's own sentinel reads them.
  `sentinel_found` accepts the sentinel of a phase, and the closure brief lists their deliverables.
- Under the rules 3 every sentinel (f2, f3, f4 and each closure's) is drawn with the convening's seed among the free
  roles: named by no brief of the convening and not convened by its profile. Of those, the roles fit for the question
  come first (a keyword of their own in it, as `roles --question` finds them), professionals before sub-professionals;
  all the free roles when none is fit. The brief records the draw: the seed, the pool and the keywords of the role
  drawn, or that no free role was fit. `fund` and `repin` refuse a sentinel as `--owner`. Under the rules 1 and 2 the
  closure's sentinel is drawn as in 5.2.

### The K# of a convening (ENG-15)
- `contradiction C FILE… --question TEXT` (Italian: `contraddizione … --domanda`) allocates the next K# of the
  convening, `K-001`, `K-002`, …, in `CONTRADICTIONS.jsonl` at its root (`CONTRADDIZIONI.jsonl` in an Italian one), with
  the binary question and the files of its two sides. There is one numbering for every branch, where numbering per
  branch verdict had given one K# to two questions. One writer at a time, as for `SEALS.jsonl`: the coordinator.
- The engine reads it. `status` lists the K#. A line that is not a K# record, or a K# written twice, stops every
  reader with exit 1. Under the rules 3, G5 wants every allocated K# named in the closure, resolved or open, and G4 and
  G5 warn on a K# cited and never allocated; the briefs of the verdict, the closure, the consolidation and the
  sentinels name the registry.

### The briefs (ENG-20, ENG-23, ENG-12)
- Every f3 brief asks for the line «decides: yes|no» that G3 wants in every `PREDICTIONS.md` of f3: the companions'
  (proof, measurement plan, attack) as the owner's. A classic whose f3 roles follow their briefs passes G3 with no line
  appended afterwards.
- The closure brief says what G5 checks of a non-closure: every branch without a valid G4 of its latest round nor an
  early closure, and a radical never funded nor closed. It names the branches it checks it on, where it used to say
  «every branch without a verdict» and name none.
- In a fan-out race, and in a mixed one, every arm's brief starts with a canary of its own, recorded in the lane map.
  G1 checks it as it checks the lanes of a classic: a deliverable without its canary or with another arm's is
  refused, and the snapshot of the reads is required. A fan-out of slices has none, as before. The map of an Italian
  convening writes `agente-<k>`, as its manifest does.

### What a 5.2 engine sees
- The rounds are read from the folders and the gate files, and the manifest keeps the keys of 5.2, so a 5.2 engine
  still loads a convening of 5.3.
- It reads G5 from `GATE_f5.json` alone. A convening closed again by a later closure is still «not closed» for it,
  and `fund` and `close-branch` stay refused. A branch closed after the first G5 shows as closed early, and it ignores
  `f5_<n>/` and `f4_<n>/`, so a re-pinned branch shows its round 1.
- 5.3 opens the lock after a G5 of the rules 1 whose closure says «not closed», where 5.2 refuses after any G5.
- On a convening born with the rules 3, a 5.2 engine checks a gate with the conditions of the rules 2 but records
  `rules` 3 in it, and 5.3 then reads that gate as approved. Gate such a convening with 5.3 only.
- 5.2 reads a gate file that 5.3 wrote over a name that is not UTF-8 bound as a file, and holds it; a workspace that
  holds such a name still stops 5.2 with exit 1, as before. 5.2 still refuses a deliverable that only quotes the
  placeholder, and does not check G0 again from a later gate.
- It ignores the sentinels of f3 and f4 and the K# registry, and has no `contradiction`; its G2 binds the folder of the
  sentinel of f2 without requiring it. A G5 that 5.2 approves on a convening born with the rules 3 binds f5 alone, so
  5.3 reads it as no longer holding once the sentinels of f3 and f4 exist (read from the code, not run).
- It checks the canary of every arm of a race in an English convening, from the lane map. In an Italian one it does
  not read back the keys `agente-<k>` of the map, so it checks only the snapshot of the reads (read from the code, not
  run).
