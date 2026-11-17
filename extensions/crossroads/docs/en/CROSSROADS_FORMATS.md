# CROSSROADS_FORMATS: the shared formats of swarmer-crossroads 1.0

This document is the contract between crossroads and every consumer of it (the next extension included). §1–§6 are the
sealed text of the formats of the convening crossroads-r2 (slice 1), verbatim: the paths they cite (`f4/…`, `work/…`)
are the design record of those convenings, kept as they were written. §7 is the consumer interface, §8 the glossary,
§9 the bodies of the three records, §10 amendment F, which changes §3 where it says so and is the only text that does.
Where §1–§6 and §10 disagree, §10 applies. The store is `<state>/crossroads/` (Italian `<state>/incroci/`), where
`<state>` is the project's `.swarmer/` (Italian `.sciame/`); the names inside it are canonical in every language.

## 1. Format (a): the dependency line [=, Δ B adopted]
`DEPENDS-ON <id> <id>…` at column 0 of a designated file, outside ``` blocks. Italian alias `RICHIEDE` (B's f4 change, now binding on
both; `DIPENDE-DA` is withdrawn because `DIPENDE DA D1` breaks `jury.py count`, A-7). One line may carry several ids; the edge is
`depends_on` from the decision that owns the line to each id. A bare *locator* resolves inside the same file.

## 2. Format (b): ids [Δ B: jury anchor]
| thing | id grammar | example |
|---|---|---|
| convening anchor | `<name>@<created>` (MANIFEST `name`, `created` ISO 8601 with offset) | `crossroads@2026-11-17T08:03:16+01:00` |
| convening decision | `<conv anchor>/<relpath>#<loc>`, *locator* `loc` = `D\d+` \| `H-\d{3}` \| `select` | `…/f2/03-triage/TRIAGE.md#H-001` |
| **jury anchor [Δ B, K-104, user decision 3]** | `jury:<dir>@<sha256(jury.json)[:12]>`; `dir` = POSIX path of the jury folder relative to the project root; inside each segment `%`, `@`, `#`, `(`, `)`, whitespace and C0/C1 controls are percent-encoded (`@` → `%40`) | `jury:.swarmer/j-auth@4bac0fa6380c` |
| jury decision | `<jury anchor>#<loc>` | `jury:.swarmer/j-auth@4bac0fa6380c#D1` |
| canonical record | `U-` \| `R-` \| `N-` + `sha256(body bytes)[:12]` (regex `^[URN]-[0-9a-f]{12}$`) | `R-c418a7941dd2` |
| option | `<decision id>(<label>)`; `label` = 1+ chars without `(`, `)`, `\|`, controls; inner spaces allowed (B2), outer trimmed | `U-4fe64b59b127(a)` |
| value nodes | `who:<role>`, `concern:<name>` (never dangling) | `concern:engine` |
| evidence ref | `<anchor>/<relpath>@<sha12 of the file>` or any id above | `…/TRIAGE.md@5f26f5cd7553` |
| source position | `<anchor>/<relpath>:<line>` or `records/<id>.md` (field `src`, display only) | |
Not ids (display keys only, never stored in records): *handle* `h(id)` = `sha256(id)[:HLEN]`, HLEN ≥ 12, +2 until no collision
(`index/HLEN`); *member index* `m<k>`; branch `crossroads/<h(D′)>`. Trailers: `Crossroads-Decision`, `Crossroads-Concern`,
`Crossroads-Reverts` (git trailer syntax, one value each). Two jury folders with byte-identical jury.json now get two anchors, so
DUPLICATE-ANCHOR fires only for the same `dir` twice (test: `work/a12`, both roads in the graph).

## 3. Format (c′): ONE hunk sha, the R record and its TSV projection [Δ A, Δ B]
**3.1 The diff** (both branches, every hunk sha, `realize` and every commit scan, `check-commits`, `plan`, `--realized`).
Environment `GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_ATTR_NOSYSTEM=1 LC_ALL=C`, and
```
git -c core.quotePath=false -c core.attributesFile=/dev/null -c diff.algorithm=myers -c diff.indentHeuristic=false
    -c diff.interHunkContext=0 -c diff.suppressBlankEmpty=false -c diff.noprefix=false -c diff.mnemonicPrefix=false
    -c diff.relative=false -c diff.external= -c diff.orderFile= -c color.ui=never -C <repo>
    diff-tree -r --root --no-commit-id <FLAGS> <commit>        # a commit against its single parent (merges: none, NONLINEAR)
    diff --cached <FLAGS>                                     # realize: index against HEAD
FLAGS = -p --raw -z -U0 --no-renames --no-ext-diff --no-textconv --diff-algorithm=myers --no-indent-heuristic
        --inter-hunk-context=0 --src-prefix=a/ --dst-prefix=b/ --ignore-submodules=none --no-color
```
**[Δ A]** A's `changes()` used `git log -p -U0` with the repo's own `diff.algorithm`, `diff.interHunkContext`, indent heuristic and
textconv (K-dbg-1, must-fix 9). **[Δ B]** B's pins are kept, plus `-z --raw`, `core.attributesFile`, `diff.external`, `diff.orderFile`.
**3.2 Path.** The path is the NUL-terminated field of the `--raw -z` record (post-image path; with `--no-renames` it equals the
pre-image path), as raw bytes. It is **never** parsed from `---`/`+++` lines. **[Δ B]** B parsed `+++ b/x y.txt\t` and hashed the TAB
(measured, `out_hs_test.json` HS3: 2 of 19 hunks differ, both on the path with a space; acceptance B6). Raw record *i* pairs with
patch section *i*.
**3.3 hunk_sha256** = lowercase hex `sha256(P ‖ LF ‖ L₁ ‖ LF ‖ … ‖ Lₙ ‖ LF)`, where P is the path bytes and L₁…Lₙ are the hunk's
lines in git's output order (all `-` then all `+`), each the exact bytes git prints including its `-`/`+` sign, without the final
LF (a CR stays); a `\` marker line counts as the exact bytes `\ No newline at end of file`. **[Δ A]** A dropped the marker (HS4: the
3 no-EOL hunks differ even on a clean config). Binary section (`Binary files … differ`): hunk_sha256 = the literal `BINARY`, no lines.
Mode-only changes have no hunk (A: MODE); a `160000` mode is UNSUPPORTED, no hunk. Reference implementation: `hunksha.py` (stdlib).
**3.4 Hunk header** `a,b c,d` = the `@@` numbers with the omitted count written as `1`. **3.5 Hunk key** = (path, header,
hunk_sha256). **Hunk occurrence** = (commit sha40, path, ordinal k within that path, header, hunk_sha256). **hunk_sha256 alone is a
content hash, never an identity** (B7, K-403): two decisions that add the same text get the same sha. A commit *carries* an R record
when every hunk key of the R is among the commit's occurrences; an R realized by several carrying commits is resolved by an
assignment that prefers the commit whose trailer names the R's decision, and TRAILER-MISMATCH is reported only when no carrying
commit names it (the algorithm is Branch B's; this file fixes only the keys it uses). Entanglement in A may keep comparing
hunk_sha256 by content.
**3.6 Line atom** `LINE <path> +|- <sha256(line bytes without sign and LF)>` [=]; markers make no atom.
**3.7 R record body** (B's writer; one key per line, keys in this order, multi-valued keys sorted): `KIND realization`,
`TIME <ISO 8601 with offset>`, `DECISION <id>`, `CONCERN <name>`, `MODE git|nogit`, `HUNK <qpath> <hunk_sha256|BINARY> <header>`…,
`LINE <qpath> +|- <sha256>`…. `qpath` = the path, C-quoted git style (`"…"` with `\t \n \" \\` and octal for other controls) when it
contains a space, TAB, `"`, `\` or a control; raw UTF-8 otherwise **[Δ B]** (B split on spaces, A9/B6). `nogit` hunks (difflib with
git-like headers) compare only with `nogit` hunks; LINE atoms compare across modes [=].
**3.8 TSV projection** `realized.tsv` (A's `--realized` input), one row per HUNK, TAB-separated, `\t \n \\` escaped:
`decision  concern  commit|-  path  hunk_sha256  header` **[Δ A: column 6 added; A keyed rows by hunk_sha256 alone]**. `commit` is the
assigned carrying commit, `-` while none. B writes it from the graph (derived, P4); A never writes it.

## 4. Format (d): cursors [=]
A cursor is a record id or a snapshot hash `SNAPSHOT_<sha256(graph.jsonl)[:12]>` under `.swarmer/crossroads/log/`, never a byte
offset. An unknown cursor answers "full resync" (exit 1).

## 5. Format (e): the derived graph `.swarmer/crossroads/view/graph.jsonl` [new; K-404, J1]
One JSON object per node and line, UTF-8, LF, keys sorted, nodes sorted by `id`, `ensure_ascii=false`. Disposable: a pure function
of the sources, records, git objects and tree (P4). Scalars missing in the source are the string `NR` = `"not recorded"`; **lists
missing are `[]`, never a split of NR** **[Δ B]** (2 nodes carry `depends_on: ["not","recorded"]`: `H-001/01-avversario/work/b_ud3`
l.4 and `00-architetto/tests/work/pa12` l.1). Decision kinds: `user`, `jury`, `triage`, `selection`; containers: `convening`,
`jury`; others: `option`, `realization`, `note`. A decision node is one with `node_class` ∉ {container, option, record}.
| # | (e) field | type | on kinds | source (B) | A f4 name (stub, `proto/README.md` l.9–13) | read by A in |
|---|---|---|---|---|---|---|
| e1 | `id` | str, format (b) | all | ids §2 | `{id: record}` key | all |
| e2 | `kind` | enum above | all | source type | — | radius, brief |
| e3 | `node_class` **[Δ B: was `base`]** | enum container, decided, recommended, open, not_decided, rejected, invalid, option, record (STATUS_MAP, B proto l.18) | all | status map | — (A's `base` is a git commit) | radius |
| e4 | `lifecycle` **[Δ A: was `status`]** | enum: the e3 values plus `superseded` | all | §3.1 overlay | `status` | brief member line |
| e5 | `depends_on` | [id], sorted | decisions | format (a), U DEPENDS-ON, jury DEPENDS | `depends_on` | radius, plan, CYCLE, D′ draft |
| e6 | `supersedes` | [id], sorted | decisions | SUPERSEDES/SOSTITUISCE, jury `previous` | `supersedes` | Δ (S(Rad)), D′ draft |
| e7 | `time` | str ISO 8601 with offset, or NR | decisions, R, N | TIME, MANIFEST, SEALS.jsonl (jury, K-103) | `time` | Δ |
| e8 | `impact` **[Δ A: was `area`]** | [concern name], sorted | decisions | IMPACT/IMPATTO | `area` (str or list) | brief, check-commits R2, D′ draft |
| e9 | `evidence` **[Δ A: was `cites`]** | [evidence ref], sorted | decisions, options | EVIDENCE/EVIDENZA | `cites` | Δ (E(D)), index |
| e10 | `options` | [label] in source order | decisions | OPTIONS | `options` (A: a list of objects; A joins e10 with e12–e14 by label) `options[].label` | brief |
| e11 | `chosen` | label or NR | decisions | CHOSE, OUTCOME option | `chose` | D′ draft |
| e12 | `rejected` | {label: reason or NR} for every label ≠ chosen | decisions | REJECTED/SCARTATA | `options[].reason` | brief discarded options |
| e13 | `text` **[Δ B: new]** | str (the option's text) or NR | options | OPTIONS `(<label>) <text>` | `options[].text` | brief discarded options |
| e14 | option `evidence` | as e9 | options | EVIDENCE `<loc>(<opt>)` | `options[].cites` | brief, index |
| e15 | `l0` **[Δ B: now in graph]** | str, one line, ≤ L0 bound in bytes | decisions | `show --level 0` row | `l0` | brief member line |
| e16 | `l1` **[Δ B: now in graph]** | str, ≤ 1200 B | decisions | `show --level 1` card | `l1` | brief page 1 |
| e17 | `decision` | id | R | R DECISION | `realized.tsv` col 1 | `--realized` |
| e18 | `concern` | str | R | R CONCERN | `realized.tsv` col 2 | `--realized` |
| e19 | `hunks` | ["<qpath> <hunk_sha256\|BINARY> <header>"] | R | R HUNK | `realized.tsv` cols 4–6 | `--realized` |
| e20 | `lines` | ["<qpath> +\|- <sha256>"] | R | R LINE | — | (K-102 evidence) |
| e21 | `mode` | git \| nogit | R | R MODE | — | `--realized` (git only) |
| e22 | `withdraws` | [R id] | N | N WITHDRAWS | — | `--realized` drops withdrawn R |
Carried by B, not read by A (listed so the table is the whole node): `edges`, `rev` ([edge, id] pairs, the closed edge table of
`f4/H-001/00-architetto/APPENDIX.md` §A), `superseded_by`, `question`, `rationale`, `by`, `authority`, `delegated`, `source_status`,
`history`, `subject`, `src`, `realization` (none, live, reverted, path-gone), `live` (int), `label` (options), `about`, `adds` (N).
**Withdrawn from the interface [Δ A]:** the stub-only `commits` and `concern` on decisions (commits come from trailers; with no
repo the brief reads R nodes). A writes its D′ draft (`plan.json` `dprime_draft`) with the (e) names `question`, `chosen`,
`rejected`, `supersedes`, `depends_on`, `impact`.

## 6. The page bound and its unit [Δ A, Δ B; user decision 2]
`PAGE_MAX = 7276` **bytes** of UTF-8, every LF included, per page file: A's brief `p<n>.md`, `PLAN.md`, `PLAN_p<n>.md`, and every
B output an agent is pointed to read by id (`show` levels 0–1). 7276 B ≤ 4000 tokens at the worst measured 1.819 B/token
(cl100k; for Claude **not verified**, class 5). All other bounds are stated in bytes too: L1 ≤ 1200 B **[Δ B: was chars]**, the L0
bound in bytes **[Δ B: was "56 tokens" chars/4]**, A's line caps already in bytes. A token figure may appear only as a derived
value with its ratio. Reading the whole radius costs O(|Rad|) pages, independent of N (contract criterion 3). **Consequence for
slice A:** the f4 caps (page 1 10428 B, page n 11916 B, PLAN 7820/11252 B) exceed 7276 and must be re-summed; `PAGE_MAX = 12000`
in `crossroads_proto.py` l.13 is superseded.

## 7. The consumer interface (for the next extension)
A consumer (the planned context optimizer, or any tool) reads crossroads only through what this section names, and
writes only under its own state folder (for example `.swarmer/context/`). Nothing else is an interface.
- **Stable ids:** §2. An id never changes; a handle is a display key, never stored.
- **Levels:**
  - L0: one row of `crossroads/view/INDEX.tsv`, at most 224 bytes with its LF (fields: id, lifecycle, chosen,
    question; TAB, backslash and LF escaped);
  - L1: the card of a decision, at most 1200 bytes with its LF, in the field `l1` of its node (e16), also printed by
    `crossroads show ID --level 1`;
  - L2: `crossroads show ID --level 2`, at most 7276 bytes with its LF (the whole node is in the graph).
- **The change log:** `crossroads changes --since SNAPSHOT_<sha12>` prints the ids added, removed, changed and whose
  status changed since that snapshot; the cursors live in `crossroads/log/` (the last 20 are kept). An unknown
  cursor exits 1 with "full resync": the consumer then reads `INDEX.tsv` again.
- **The graph:** `crossroads/view/graph.jsonl`, format (e) of §5.
- **Lossless, never compressed or rewritten:** `crossroads/records/` (U, R, N) and the swarm's sources (convenings,
  juries). A consumer never edits them; a correction is a new record.
- **Disposable and regenerable:** `crossroads/view/`, `crossroads/log/`, `crossroads/stage/` and any derived file of a
  consumer. `crossroads derive` writes them again from the records, the sources and git.
- **Writes:** a consumer writes only under its own state folder.

## 8. Glossary (one meaning per term)
The symbol `R` means only the realization record; `D` and `D′` only the upstream decision and its reversal; "token"
only an LLM token; "holds" says that a stated property is true, never that a defect was found (that is "defect
confirmed"). `D` followed by digits is never a symbol: it appears only inside an id (`…#D1`) or with a prefix.

| # | term | definition |
|---|---|---|
| G1 | **D** | the upstream decision whose reversal is being prepared: the argument of `radius`, `brief`, `plan` |
| G2 | **D′** | the new decision that reverses D; it supersedes Rad(D)∖keep and depends on depends_on(D)∖Rad |
| G3 | **Rad(D)**, the radius | D plus every decision reachable from D over reversed `depends_on` edges (exact BFS) |
| G4 | **C_Rad** | the commits that realize members of Rad∖keep, revert-chain tails at even depth, newest first |
| G5 | **R**, R record | a realization record: canonical file `records/R-<hex12>.md`, kind `realization`, §3.7 and §9 |
| G6 | **hunk sha** (`hunk_sha256`) | the content hash of §3.3, under the pinned diff of §3.1 and §10 F-1 |
| G6b | **hunk key / hunk occurrence** | (path, header, hunk sha) / the same plus commit and ordinal |
| G7 | **realized** | a commit realizes decision X when its single `Crossroads-Decision` is X and it is the tail of a revert chain at even depth. "Still realized" means realized |
| G8 | **live**, `live(X)` | textual presence: the count of X's `+` line atoms still in the tree. Evidence, and the rule only without git |
| G9 | **token** | an LLM token, under a named tokenizer. Every bound is in bytes; a token figure is derived, with its ratio |
| G10 | **file entry** | an element of the weave recording a file's creation or deletion |
| G11 | **holds** | a stated property of the design is true on the declared set: an invariant, a bound, a prediction phrased as a property |
| G12 | **page**, **PAGE_MAX** | one file an agent reads in one go; at most 7276 bytes of UTF-8 with every LF |
| G13 | **byte** | one octet of the UTF-8 encoding, LF included. The only unit of a size bound |
| G14 | **derived** (source class) | a field taken from a file the swarm already writes. The classes are derived, line, record, NR |
| G15 | **convening size** | the bytes of a convening's files, the denominator of overhead ratios |
| G16 | **decision** | a graph node with `node_class` ∉ {container, option, record}; kinds user, jury, triage, selection |
| G17 | **record** | an immutable canonical file `U-`/`R-`/`N-` + hex12; corrected only by a new record that supersedes or annotates it |
| G18 | **lifecycle** | the derived state of a node (e4) |
| G19 | **evidence** | the refs a decision or option rests on (edge `rests_on`, field e9) |
| G20 | **impact** | the concerns a decision touches (e8) |
| G21 | **concern** | a named area of the code, defined in `crossroads/CONCERNS.md` by lines `CONCERN <name> <glob>…` |
| G22 | **discarded option** | an option of the decision other than `chosen`; its reason is `rejected[label]` |
| G23 | **Δ** ("changed since") | records citing D's evidence or superseding a radius member, later than D as instants |
| G24 | **handle**, **member index** | display keys on pages: `h(id)` hex prefix, `m<k>`. Never stored as ids |
| G25 | **id**, **anchor**, **locator** | §2: the stable name / the container prefix / the in-file key (`D\d…`, `H-\d{3}`, `select`) |
| G26 | **blocking issue / warning / finding** | backtrack: a blocking issue stops plan or apply, a warning does not. derive: a finding is hard, report or info |
| G27 | **NR** | the literal `not recorded`, for a scalar the sources do not give; a list is `[]` |
| G28 | **proven / verified / supported / refuted / unresolved** | the five states of the swarm's preamble, rule 2 |
| G29 | prefixed labels | debugger defects `DBG-…`, closure decisions `CL-…`; attack cases keep their names |

## 9. The bodies of the records
A record body is UTF-8, LF, one `KEY value` per line, keys in the order below, a multi-valued key once per value with
its values sorted; no CR, no BOM. The id is the kind letter, `-` and the first 12 hex digits of the sha256 of the
body bytes; the file is `crossroads/records/<id>.md`, created with O_EXCL and never edited.
- **U** (a user decision; `crossroads decide`), keys in order: `KIND user`, `TIME <ISO 8601 with offset>`,
  `BY <role>`, `AUTHORITY owner|delegated:<ref>|…`, `QUESTION <text>`, `OPTIONS (<label>) <text> | (<label>) <text>…`,
  `CHOSE (<label>)`, `REJECTED (<label>) <reason>`… (or `REJECTED none`), `RATIONALE <text>`, `IMPACT <concern>…|none`,
  `EVIDENCE <ref>…|none`, `DEPENDS-ON <id>…|none`, and, optionally, `SUPERSEDES <id>…`. Every key but SUPERSEDES
  is required; CHOSE is one of OPTIONS; a REJECTED label is an option that is not chosen. Multi-valued: REJECTED.
- **R** (a realization; `crossroads realize`): `KIND realization`, `TIME`, `DECISION <id>`, `CONCERN <name>`,
  `MODE git|nogit`, `HUNK <qpath> <hunk_sha256|BINARY> <header>`…, `LINE <qpath> +|- <sha256>`… (§3.7).
  Multi-valued: HUNK, LINE.
- **N** (a note; `crossroads note`): `KIND note`, `TIME`, `BY`, `ABOUT <id>`, `WITHDRAWS <R id>`…, then optionally
  `QUESTION`, `REJECTED`…, `RATIONALE`, `IMPACT`, `EVIDENCE`. Multi-valued: WITHDRAWS, REJECTED. A note carries no
  DEPENDS-ON and no SUPERSEDES: a note with either is INVALID-RECORD and adds no edge, so every edge of the graph that
  comes from a record comes from that record's own bytes. A note fills only a field its decision left NR, marked
  "added later by N-…"; it never overwrites a recorded value: a correction is a new U that supersedes.
A record whose file name is not the sha256 of its bytes is quarantined (INTEGRITY, hard); one that breaks a rule above
is kept as INVALID-RECORD (report) with lifecycle invalid.

## 10. Amendment F (2026-11-17)
The verdict of crossroads-r2 named seven missing items. Amendment F settles the format ones; each item names the test of
`tests/test_crossroads.py` that checks it.
- **F-1 (K-501), the order file pin.** On git 2.53 the pin `-c diff.orderFile=` makes porcelain `diff`, `log`, `show`
  and `fast-import` exit 128 ("failed to read orderfile ''"); only `diff-tree` accepts it. The pin stays only on
  `diff-tree`: the commit line of §3.1 is unchanged, byte for byte. The realize line becomes
  `diff --cached <FLAGS> -O/dev/null`, without the pin, and `hunksha.staged()` does the same. The other git commands
  (`log`, `show`, `ls-tree`, `cat-file`, `fast-import`, `switch`) run without the pin and print no hashed diff.
  Test: rc 0, and the staged hunk key equals the `diff-tree` key of the commit made from that index (`K-501`).
- **F-2 (K-502), typechange.** A raw record with status `T` is consumed with both of its patch sections; raw records
  and patch sections are paired by consuming the sections of each record, never by position. A typechange yields one
  entry `(path, "UNSUPPORTED", "UNSUPPORTED", 0)` and no hunk sha; so does a gitlink (mode 160000). Consequences:
  `realize` refuses with UNSUPPORTED (exit 1, nothing written); derive's commit scan gives the info finding
  UNSUPPORTED; the backtrack plan gives the blocking issue UNSUPPORTED, as before. Test: `K-502`.
- **F-3 (K-506), a writer rule.** Every page size counts the final LF. L2 cuts long scalar strings inside the JSON
  (halving the longest) before ever cutting the text, so the fence always closes (two fence lines). Every writer raises
  if a page is over 7276 bytes. Test: `K-506` (the 7277-byte case gives at most 7276 with two fence lines).
- **F-4 (K-505), the seal of a jury.** The time of a jury decision comes from a SEALS.jsonl row only when the row names
  the OUTCOME file itself (a relative row against the folder of the SEALS file) and its sha256 equals the sha256 of
  that file's current bytes. Otherwise the time is NR. Test: `K-505` (a wrong sha or a same-named folder under
  another parent gives NR).
- **F-5 (K-102), "still realized".** With git, "still realized" is G7: a commit whose single `Crossroads-Decision` is X
  and that is the tail of a revert chain at even depth, full reverts recognised as in A1 (git's own `This reverts
  commit <sha40>` line or a `Crossroads-Reverts` trailer, same paths, swapped blobs or line multisets).
  SUPERSEDED-STILL-REALIZED fires on G7; `live` (G8) is printed as evidence; when G7 and G8 disagree on a decision with
  R records, the info finding LIVE-DISAGREES is given. Without git, the rule falls back to G8. Cost: G7 is computed
  only for decisions whose lifecycle is superseded or rejected, with one `git log` for the trailers and the revert
  lines and the full-revert check on the revert candidates only. Test: `K-102`.
- **F-6 (K-507), edge sets.** CYCLE runs over `depends_on ∪ supersedes`. The radius runs over `depends_on` (e5) only;
  it never uses `rests_on` or notes. Test: `K-507`.
- **F-7, smaller items.** `stage` refuses any path with a `.git` component, besides the root, the state folder and
  paths outside the root. A convening or a jury found below the read depth (down to three levels) gives the report
  SOURCE-SKIPPED, never silence. Tests: `B4 stage`, `F-7 SOURCE-SKIPPED`.
