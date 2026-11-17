# swarmer-crossroads 1.0: the decisions of the project as a graph, and the way back

crossroads is an extension of swarmer (5.2 or later). It records the decisions of the user, of the swarm (triage,
selection) and of the juries as a navigable graph, with their discarded options and reasons, rationale, impact,
evidence and dependencies. It ties each decision to the commits that realize it, one concern per commit. When the
project is stuck, it finds the upstream decision D, gives its brief in bounded pages and plans its reversal on a new
branch, without rebuilding the context. The formats are in `CROSSROADS_FORMATS.md`; the skill `swarmer-crossroads`
tells the coding agent when to use each command.

## Enabling it
`bash swarmer/swarmer.sh extensions --add crossroads` (Italian `estensioni --aggiungi incroci`) writes the key
`extensions` of `.swarmer/config.json` and regenerates: the skill `swarmer-crossroads` appears in every active target
and every strategy skill gets the coordinator block below. `extensions --remove crossroads` takes them away again; the
store `.swarmer/crossroads/` stays, because it is the project's.

## The store
`.swarmer/crossroads/` (Italian `.sciame/incroci/`):
- `records/`: the canonical records, immutable and content-addressed: `U-…` (a user decision), `R-…` (a realization:
  the hunks of one decision in one concern), `N-…` (a note). Commit them, in a commit of their own;
- `view/`: derived and disposable: `graph.jsonl` (format (e)), `INDEX.tsv` (one L0 row per node), `REPORT.md` (one
  page: the hard and report findings, the info ones counted), `REPORT.tsv` (every finding), `realized.tsv` (one row per realized hunk), and the brief, plan and index files of the backtrack;
- `log/`: the snapshots of the graph (the last 20) and the list of every record ever seen;
- `stage/`: the before-images of the no-git mode;
- `CONCERNS.md`, optional, written by the project: lines `CONCERN <name> <glob>…`.
`view/`, `log/` and `stage/` are git-ignored by the `.gitignore` crossroads writes in the store.

## The commands
`bash swarmer/swarmer.sh crossroads <command>` (Italian `incroci`). Exit codes: 0 ok, 1 error or blocking issue,
2 findings, stale plan or dry run. The commands that read the view derive it again first when it is missing or stale.

| command | Italian | does |
|---|---|---|
| `derive [--source DIR]… [--git auto\|yes\|no] [--strict] [-v]` | `deriva` | writes `view/` and `log/`; prints the snapshot and the findings that are not info |
| `check [--reverse ID,…]` | `controlla` | prints every finding, writes nothing |
| `decide --question Q --options "(a) t \| (b) t" --chose a --rationale T [--reject "(b) reason"]… [--impact "c…"] [--evidence "id-or-ref…"] [--depends "id…"] [--supersedes "id…"] [--authority owner\|delegated:<ref>]` | `decidi` | writes a U record, prints its id. Every reference is resolved when written, against `records/` and the sources (a record written a moment ago counts, before any derive): `--evidence` takes space-separated ids (records, options, anchors, decisions), `who:<role>`, `concern:<name>` or `<anchor>/<relpath>[@sha12]` of a source file; `--depends`, `--supersedes` take decision ids; `delegated:<ref>` takes one evidence ref. A token that does not resolve is refused (exit 1, nothing written, the token and the remedy printed): free text goes in `--rationale`, a source file is cited as `<anchor>/<relpath>@<sha12>` (printed for you), a project file outside the sources and a git commit are named in `--rationale`; a reference holding a space (an option label, a file name) cannot be stored, since §2 splits references on whitespace: cite its decision or anchor |
| `note --about ID [--rationale T] [--reject "(b) r"]… [--withdraws R-…]…` | `nota` | writes an N record; `--about` must be a known id, `--withdraws` a known R record, `--evidence` as in `decide`: refused otherwise, nothing written |
| `stage FILE…` | `prepara` | no git: the before-images, before editing |
| `realize ID --concern C [--mode auto\|git\|nogit]` | `realizza` | writes an R record from the staged diff (git) or the stage (no git); ID must be a known decision, refused otherwise, nothing written |
| `trailers ID CONCERN` | `trailer` | prints the two trailer lines of the commit; never commits |
| `show ID\|HANDLE [--level 0\|1\|2]` | `mostra` | the L0 row, the L1 card or the L2 page of a node |
| `changes --since SNAPSHOT_<sha12>` | `modifiche` | what changed since a snapshot |
| `lint FILE… [--lexicon]` | `lint` | the near-misses of the protocol lines; FOREIGN-H in a triage or selection |
| `radius ID` | `raggio` | Rad(ID) |
| `brief ID` | `sintesi` | the paged brief `view/brief/<h>/p<n>.md` (each page ≤ 7276 B) |
| `plan ID [--keep X…] [--margin N]` | `piano` | the read-only plan `view/plan/<h>/PLAN.md` and `plan.json`, with the D′ draft and the `decide` command to record it |
| `apply PLAN.json --dprime ID [--tests CMD] [--execute]` | `applica` | without `--execute` a dry run (exit 2); with it, after the user's yes, the branch `crossroads/<h12(D′)>` |
| `verify PLAN.json --dprime ID [--tests CMD]` | `verifica` | I1–I3 blocking; I4, I5 and the tests reported: OK, OK-BROKEN or FAILED |
| `check-commits RANGE` | `controlla-commit` | the trailer rules: one decision and one concern per commit, concerns, plain reverts, TRAILER-MISMATCH |

## The protocol lines
In a triage (`TRIAGE.md`), a selection (`SELECTION.md`, `SELEZIONE.md`), a jury proposal (`PROPOSAL.md`,
`PROPOSTA.md`) and in the side file `CROSSROADS.md` (Italian `INCROCI.md`) next to a triage or a selection, at column
0 and outside ``` blocks, written before the seal or never (a late line is a note):
```
QUESTION|DOMANDA <loc> <text>            RATIONALE|MOTIVAZIONE <loc> <text>
REJECTED|SCARTATA <loc> (<label>) <reason>
EVIDENCE|EVIDENZA <loc>[(<label>)] <ref>…   IMPACT|IMPATTO <loc> <concern>…
DEPENDS-ON|RICHIEDE <loc> <id>…          SUPERSEDES|SOSTITUISCE <loc> <id>…
TRIAGE H-### TEST|REFORMULATE|OPEN|REFUTED (TESTARE/PROVA, RIFORMULARE, APERTA, SMENTITA/CONFUTATA) [text]
loc = D<digit>… | H-### | select
```
`DIPENDE-DA` is never read. The lines are invisible to `jury count`. A line of a triage or a selection that names an H#
of another convening goes into the side file, which convene.py does not read (FOREIGN-H otherwise).

<!-- coordinator -->
**crossroads is enabled in this project** (`bash swarmer/swarmer.sh crossroads …`, skill `swarmer-crossroads`).
- In the brief of the triage arbiter, of the selection arbiter and of a jury's rapporteur, paste the protocol lines
  below and ask, for each decision, its question, its discarded options with reasons, its impact, its evidence and
  what it depends on:
  `QUESTION <loc> <text>` · `REJECTED <loc> (<label>) <reason>` · `RATIONALE <loc> <text>` ·
  `IMPACT <loc> <concern>…` · `EVIDENCE <loc>[(<label>)] <ref>…` · `DEPENDS-ON <loc> <id>…` ·
  `SUPERSEDES <loc> <id>…` · `TRIAGE H-### TEST|REFORMULATE|OPEN|REFUTED [text]` (`loc` = `D1…`, `H-###`, select;
  column 0, outside code blocks; an H# of another convening goes in `CROSSROADS.md` next to the file).
- Before sealing those files run `crossroads lint FILE…` and fix every NEAR-MISS and FOREIGN-H.
- After every seal of a phase or of a jury outcome, and before answering the user, run `crossroads derive` and read
  the hard findings of `view/REPORT.md`.
- Record every answer of the user to a decision question with `crossroads decide` (with `--supersedes` when it
  replaces an earlier choice).
<!-- /coordinator -->

## Commits by concern
A commit carries one decision and one concern. Stage the changes of one decision in one concern, run
`realize ID --concern C`, then `trailers ID C`, and propose to the user the `git commit` with those two trailer lines:
the user runs it, or approves an explicit command. Then `check-commits <range>`: a commit without trailers that
touches only the store (the records commit) is not flagged; any other commit without them is R1. swarmer never commits.

## The way back
`show` or `view/INDEX.tsv` finds D; `radius D` and `brief D` give the radius and page 1 (the L1 card of D, its
discarded options with reasons, what changed since, the members); `plan D` gives the commits, the blocking issues and
the D′ draft. The user chooses; `decide … --supersedes` records D′; `apply plan.json --dprime D′` is a dry run, and
`--execute` (only on the user's explicit yes) writes one commit per commit of C_Rad on a new branch through one
`git fast-import`: HEAD, the current branch and the worktree change only at the end (`git switch`). The new commits
carry the user's git identity (`user.name`, `user.email`) and the current time; without an identity `apply` refuses.
`verify` checks it: I1 protects the files (no path outside the plan's files changes), I2 the lines (every plan file
equals the weave, so the lines of outside decisions inside radius files stay), I3 the trailers. OK means byte-safe,
OK-BROKEN that the tests fail.

## Limits
- **Merges:** a merge in the range is a stop (NONLINEAR). Merge commits are skipped by the commit scan; a hunk resolved
  inside a merge is R-UNMATCHED.
- **Renames:** none is followed (`--no-renames`). The safe stops are REALIZATION-PATH-GONE, copies with edits (RN1)
  and a squash tagged with one decision without realization records (M2b).
- **Not supported:** a typechange, a symbolic link (mode 120000) or a gitlink (mode 160000) on a radius path is
  UNSUPPORTED; `realize` refuses them.
- **Case-insensitive filesystems:** CASE-COLLISION blocks two tracked paths that differ only by case; this is not
  verified on APFS or NTFS.
- **"OK" means byte-safe, not behaviour-safe.** The radius is the declared one: a dependency nobody declared is caught
  only by the tests (OK-BROKEN). I4 and MISSING-DEPENDS are heuristics.
- **Page bound:** 7276 bytes per page, which guarantees at most 7276 tokens. "At most 4000 tokens" holds only at the
  measured 1.819 bytes per token (cl100k) and is not verified for Claude. The calibration of Claude's tokenizer and the
  juror bias of the lines (jurors read them) are out of scope: they need the user's yes to send data to a third party.
- **Ids:** the 48-bit ids protect against accidental edits only. `log/` is disposable, so RECORD-VANISHED needs `log/`
  to survive. A backdated TIME is not detected.
- **Not built:** no Mermaid or HTML export, no CONCERNS editor, no revert engine, no patch of the swarmer engine
  beyond the extension mechanism (that is a separate patch).
- **Commits:** swarmer never commits, merges or pushes; `apply --execute` only creates a branch, on an explicit yes.
- **An agent's first reversal:** whether a fresh agent with only the failure text, the skill and the help finds D and
  plans its reversal within the page bound is unresolved until the run described in the tests' `--make-fixture` is
  made, with the user's yes.
