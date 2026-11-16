# The jury, new experts and the plenary (protocol G, version 5.0 of swarmer)

This document gives the full rules of three strategies: **jury** (§2–§3), **new expert** (§4) and **plenary**
(§5). The tools are `jury.py` and the skill's test batteries (§8). The short strategies are in
`PIPELINE.md`.

## 1. Authority, delegation and the goal clause

**What a jury decides.** A proposed decision: a choice among options, the text of an act, a
clarification, a rule. `jury.json` declares `authority`:
- **`recommendation`**, by default: consensus yields **RECOMMENDED**, and the user decides;
- **`binding`**, only if the user has delegated the decision in writing, item by item (the `delegation` field cites the
  written statement), or if the decision is only the way to carry out a decision the user has already taken.

**What always stays with the user**, unless there is an explicit, specific delegation for that item:
- paid, irreversible or outward-facing actions (publishing, sending data, paid services, rented GPUs);
- runs on real systems or data that cannot be undone;
- new compute caps or quotas beyond those already authorized;
- adopting or abandoning a candidate, a line of work, a goal, a phase;
- exceptions to the project's principles;
- text the user signs.

A plenary (§5) on these items yields a recommendation. The user can revoke a jury decision at any
time.

**The delegation table.** Before a jury on decisions delegated as a block, the coordinator writes and seals a
table, item by item: `delegated`, `reserved` or `mixed`, with the reason. Reserved and mixed items go to
recommendation. A narrow reading of the delegation is presented to the user as one reading, not as the only one.

**The goal clause (mandatory): the T-OB test.** Every proposal carries at its head, for each decision, four
points, each with a [V] proof (file and line):
1. **Target.** The exit criterion of the project's current phase that the decision serves, cited by
   identifier from the project's exit-criteria file (normally `swarmer/local/EXIT_CRITERIA.md`, written by the user or with
   them), or a principle of the project. A phase without written exit criteria fails the test by construction:
   the criteria are written first, once per phase.
2. **Chain.** "With Dk criterion U moves from state a to state b", or "Dk removes blocker B, which lies on the
   critical path of U", with the file that shows B among the open blockers.
3. **Counterfactual.** Without Dk the criterion stays put or slips, and by how much. "No effect" fails the test,
   except for a zero-cost error correction.
4. **Cost.** The figures with their source, compared with what remains of the cap, and no shorter path already authorized.

The clause holds only if all four points pass. The goal guarantor writes the four outcomes in their vote.
Every juror votes **no** if the clause does not hold.

## 2. The jury

**Composition.** The coordinator chooses it and writes it in `jury.json` before opening the proposal. The file does
not change afterwards: `jury.py` records its sha256 and rejects every round counted with a different composition.
- **Number of jurors:** from 5 to 9, an odd number.
- **Always present:**
  - the goal guarantor;
  - an adversary (adversarial generator or inverter);
  - the debugger if the decision touches code;
  - the statistician if it touches thresholds, power or figures;
  - in a binding jury, the logician, the debugger and an adversary.
- **Mandatory fields:** `touches_code` and `touches_numbers` (yes or no), `authority`, `delegation`, `classification`
  (`ordinary` or `plenary`); every new jury also writes `"lexicon": 5` (§11).
- **Admitted roles:** only the ids of the swarm's roles (`swarmer-*` in `.claude/agents/`, `.codex/agents/`, `.agents/agents/` or `.gemini/agents/`, or `sciame-*` in an installation with that prefix), professionals or
  sub-professionals. A provisional expert (§4) is
  marked `provisional` and has the sealed card `CARD_<role>.md` in the folder; they make up at most a third of the
  jurors.
- **New instances:** at least half of the jurors are new instances on the subject, that is, they have not written reports, passes or
  validations on the proposal or on its direct sources (`fresh_on_subject`).
- **The rapporteur** writes the proposal and the revisions, and does not vote. The rapporteur is not the coordinator.
- **The clerk** is an instance of the arbiter: does not vote, checks and counts with `jury.py`.

**Competence.** A juror who does not consider themselves competent writes so **before** reading the proposal, in
`RECUSAL_<role>.md`. The coordinator replaces them before writing `jury.json`: whoever withdraws cannot be a
juror. After reading, abstention does not exist.

**Independence.**
- Jurors are launched in parallel, each with their own folder.
- Each is briefed not to read the other jurors' folders or the outcomes.
- The revised proposal carries no names or vote counts: only the REVISION and CONDITION lines, without the author.

## 3. The procedure and the vote

**The protocol lines** count only outside ``` blocks. A line that starts with a keyword but does not
conform is an error, not an ignored line. The lines are written here in English; their Italian forms are
accepted too (§11).

**Round 0.**
1. The rapporteur writes `round_0/PROPOSAL.md`, sealed. For each decision `Dk`:
   - `OPTIONS Dk (a) | (b) | …`: the closed list of the question's options;
   - `OPTION Dk <label>`: the proposed option, taken from that list;
   - `OPERATIVE Dk <one line>`: the operative core of the act, which no revision can change;
   - `DEPENDS Dk Dj`, if Dk presupposes Dj;
   - the full text that would become the act;
   - the T-OB test;
   - the line `PLENARY no: <reason>` (or `yes`);
   - the risks with their source;
   - the rejected alternatives.
2. Each juror, blind, writes `round_0/VOTE_<role>.md`, sealed. For each `Dk`:
   - `VOTE Dk yes|no`;
   - the rationale, with [V] or [I] proofs. A no without any [V] proof goes back to the juror once; after that it stands and is
     flagged;
   - for a no, `REVISION Dk <the smallest revision that would make me vote yes>`, or `REVISION Dk none`;
   - for a yes, `CONDITION Dk <what a revision must not touch>`, or `CONDITION Dk none`;
   - `CLASS Dk ordinary|plenary`: a single "plenary" is enough to send the decision to the plenary;
   - optional, `PREFER Dk <another option from the list>`.
3. **Each juror reports** the seals of their files in their final answer. The clerk writes them in `SEALS.md`,
   one line `SEAL round_<r>/<file> <hex>` each, before the count. `jury.py` rejects a file whose seal is not
   the one reported.

**The count** (`jury.py count`), with n jurors and s yes votes:

| votes | outcome |
|---|---|
| s = n (full consensus) | **APPROVED**, or RECOMMENDED if the authority is a recommendation |
| n/2 < s < n (majority) | **REVISION**: move on to the next round |
| s ≤ n/2 (minority), including s = 0 (consensus on no) | **REJECTED** |

**Three exceptions to consensus:**
- a `CLASS plenary` yields **TO_PLENARY**;
- if more than half of the jurors prefer the same other option, the outcome is **TO_REPROPOSE**: start again from round 0
  with that option;
- an approved decision that depends on one not approved does not become an act:
  - if the other is in REVISION, they are voted again together;
  - if the other is rejected or non-convergent, the outcome is **SUSPENDED** and the decision goes back to the user together with the other.

**Revision rounds (1, 2, 3)**, for decisions in REVISION:
1. The rapporteur writes `round_<r>/PROPOSAL.md` with only the decisions under revision. `OPTION`, `OPERATIVE` and `DEPENDS`
   stay identical; clauses, conditions, order and wording change. Every changed piece cites the REVISION line
   it answers, with the diff from the previous round's text.
2. **It does not touch the CONDITION lines of the yes votes**, which remain binding in all later rounds. If a REVISION
   requested by a no contradicts a CONDITION of a yes, the rapporteur writes
   `INCOMPATIBLE Dk <the two conflicting lines>`. If the clerk verifies it, and writes the line
   `INCOMPATIBLE-VERIFIED round_<r> Dk` in `SEALS.md`, the decision is immediately **NOT_CONVERGED** and the votes on it do not count; without that verification the round is counted as a revision round.
3. All jurors vote again, blind, on the revised text. Whoever moves from no to yes writes `CHANGE Dk <the change that
   answers my REVISION>`; without this line the round is rejected. The move is measured
   against the juror's last expressed vote, even if it fell in a round discarded as regressive. A no on principle (`REVISION none`)
   changes only in the face of new evidence, which the `CHANGE` cites.
4. **The outcomes of the revision round:**

   | how the round goes | outcome |
   |---|---|
   | consensus | APPROVED (with the exceptions above) |
   | the yes votes fall into a minority | **REJECTED**: the counting rule, a minority rejects |
   | a yes is lost but the majority holds | **regressive** revision: it is discarded; the decision returns to the previous round's text and votes, stays in REVISION, and the round counts toward the limit |
   | otherwise | REVISION |

**The limit: three revision rounds**, that is, the second, third and fourth pass, fixed by the protocol. A
decision still in REVISION after round 3 is **NOT_CONVERGED**:
- it is not approved;
- it goes back to the user with the votes and the remaining REVISION lines;
- "convergence is not forced".

**After a REJECTED.** The rapporteur may bring another option from the same `OPTIONS` list, as a new proposal:
- once per option;
- in a new jury, which cites the previous one in `jury.json` (`previous`);
- the clerk certifies `DIFFERENT Dk <reason>` with respect to the rejected text.

If all options are rejected, the question goes back to the user.

**`jury.py` is the only source of the outcome.** It recomputes every round from the sealed files each time. It rejects:
- an OUTCOME already written that does not match, that is, a revote, a changed vote or a retouched OUTCOME;
- a round counted out of order;
- a foreign entry in the round's folder.

**The act.** The coordinator records in `.swarmer/<jury>/ACT.md` the APPROVED decisions with the final proposal, the outcome
(`OUTCOME_round_<r>.json`) and the seals. Then carries them out, if the request allows it. The others are recorded with their outcome. The user receives a
short report. Every jury lives in `.swarmer/<date>-jury-<subject>/`. Agents write in their own folder; the
coordinator copies and checks.

## 3bis. The light jury

For small decisions with little influence (reversible, local, no reserved items), or where a mistake shows up with a
quick test (five minutes at most), a light jury costs less and tests before voting.
- **The jury**: `"form": "light"` in `jury.json`; three jurors: the role most competent for the feature, a critic
  (adversary, inverter or debugger) and the goal guarantor; plus the rapporteur and the clerk. Not for a plenary; for a
  reserved item it gives at most a recommendation. The ordinary jury's composition rules on the debugger, the
  statistician and the binding pass do not apply: the test replaces them.
- **The test before the vote**: for each `Dk`, `TEST Dk <command or check>` with the expected result written first,
  and `TEST-OUTCOME Dk pass|fail` after running it, before the vote. Without the two lines the
  count is refused.
- **The outcomes**: unanimity and a passing test, APPROVED (or RECOMMENDED); a failing test, REJECTED; majority, a
  single revision round and then **TO_JURY** (the ordinary jury, from round 0, with the proposal and the votes as
  input); one juror's `CLASS ordinary`, TO_JURY at once; a `CLASS plenary`, TO_PLENARY.
- **The goal clause** stays, in brief: the goal guarantor checks it as in the ordinary jury.

## 4. Experts that do not exist yet

**The request.** A line in `swarmer/EXPERT_REQUESTS.md` with six fields:
- the date;
- the convening: the path of its folder in `.swarmer/`, which must exist;
- the requester: the id of a role, `coordinator` or `provisional:<id>`;
- the competence, as a lowercase id;
- the subject it was needed for;
- the reason, at least ten characters long: which roles were considered and why they do not cover the competence.

`jury.py requests` normalizes the spellings of the requester (also the Italian `coordinatore`, `provvisorio:` and
the `sciame-` prefix), rejects non-conforming lines instead of ignoring them, and flags
similar ids.

**When two ids are the same expert.** The clerk merges two ids with a line
`` - `x`: merged into `y`, <reason> ``: the requests for x are added to y.

**Convening an expert that does not exist.** The coordinator convenes a **provisional expert**:
1. writes the provisional card before reading the question in detail, and seals it;
2. launches a generic agent with the preamble and the card;
3. marks the contribution as [provisional];
4. records the convening itself as a request.

The provisional expert does not count toward their own creation.

**The creation threshold.** Either of two conditions applies:
- **(a) simultaneous:** in one convening at least 3 distinct roles ask for it; in a plenary, at least 5, because
  there everyone receives the same invitation;
- **(b) accumulated:** at least 3 requests in at least 2 convenings, from at least 2 distinct roles.

How requests are counted:
- a role counts once per id and per convening;
- the coordinator counts for at most one request per id, and never as a distinct role;
- the user can order the creation directly.

**The creation**, after the user's approval (or that of a jury the user delegated it to):
1. the card in a JSON file, in the database format, with the English texts (mandatory for the public database; the
   other languages are optional, and an entry with only the language of the installation stays local until it has
   the English ones) and, for a sub-professional, its parent;
2. `bash swarmer/swarmer.sh approve <card.json>`: the entry joins the database, agents, skills and documents are
   regenerated, `swarmer.sh` is rebuilt, and the requests for the id are closed with «created: no. NN»;
3. `bash swarmer/swarmer.sh propose <id>` prepares the pull request to the public repository; with `--send --yes` it opens it.

A skill that matters only to the project stays a local card (`swarmer/local/AGENTS.md`) and is not approved.

In the session in which it is born, the role is launched as a generic agent with the card.

## 5. The plenary convening

**When.** Only in two cases:
1. **The transition from one major phase of the project to the next**, as the project defines them.
2. **A choice of enormously important impact.** A choice is such if it changes a goal, the principle or a
   directive; opens or closes a line of work, a candidate or a phase; is irreversible; commits resources beyond the authorized
   caps.

How a decision reaches the plenary:
- the coordinator proposes the classification with the reason, in the `PLENARY` line of each proposal;
- a wrong classification is a reason for no;
- a single juror's `CLASS plenary` is enough to bring the decision to the plenary;
- a serious choice is not cut into ordinary slices: the goal guarantor checks this.

**The five levels.** Each level passes a sealed dossier to the next, with the predictions sealed before
starting.
1. **The whole swarm.** The coordinator writes the question, sealed, with the T-OB test. Every role, including the
   new ones and the requested provisional experts, writes a short opinion (at most one page) and the expert requests.
2. **The usual convening** of the protocol in force for the subject, on the level 1 opinions:
   - the classic one for hypotheses, measurements and research;
   - the jury for a proposal already prepared.

   **If level 2 does not converge, the plenary stops** and goes to the user with the causes.
3. **The general critical pass** on the outcome of level 2: adversary, inverter, debugger, creative and goal guarantor,
   plus the experts of the systems involved.
4. **The arbiters.** Two independent instances of the arbiter each write a convergence; the social-choice
   expert checks the procedure. A disagreement on a fact is settled with a proof. If there is no proof, it becomes a
   declared risk, or two distinct options in the final proposal. The rapporteur of the vote is one of the two
   arbiters.
5. **The final vote.** New instances of the **relevant professionals** vote: those who at level 1 did not
   write "not relevant", minus the rapporteur and the clerk. A sub-professional votes only on written delegation from their
   professional, in their place and never together with them. Every voter reads the final proposal and the dossiers of levels
   1–4. The rules are those of §3, with the consensus of all voters; a tie is not a majority, and there is no
   drawing of lots. Revision rounds redo only the vote, not levels 3–4. `jury.json` lists the voters and the level 1
   file that establishes their relevance.

**Cost.** About 60–70 agents, plus about 25 for each revision round. The coordinator announces it beforehand.

## 6. Declared limits

- **A single model.** If the jurors are instances of the same model, Condorcet's theorem does not apply:
  APPROVED means "no juror found an objection that holds", not "verified". Where the environment
  allows it, jurors from different models make the vote more independent.
- **Trust in the coordinator remains at three points:**
  - `SEALS.md` is written by the clerk from the jurors' final answers, which the coordinator receives;
  - `fresh_on_subject` is self-declared;
  - the blind vote rests on the brief, not on a technical separation.

  The coordinator declares them in every report and never uses them for their own benefit.
- **The veto.** The veto of a single juror is intended: only consensus approves. In plenaries the typical outcome will be
  REVISION or NOT_CONVERGED.
- **Strategic voting** is made visible (CHANGE, PREFER, CONDITION), but not eliminated.
- **A jury in sequence.** In a tool without subagents the coordinator performs every juror: consensus there is a
  self-approval. Its outcome is only a recommendation to the user, never a delegated decision.

## 7. The choices of form, which a project can change

A project can change these choices in `swarmer/local/JURY.md` (§9), declaring it:
1. three revision rounds before NOT_CONVERGED;
2. a revision that falls into a minority is REJECTED;
3. the expert creation thresholds: 3 in one convening, 5 in a plenary; or 3 requests in 2
   convenings from 2 roles;
4. in the plenary a tie is REJECTED, and the consensus of the relevant voters applies.

## 8. Tools

- `python3 -I swarmer/jury.py count <folder> <round>`: recomputes every round, writes `OUTCOME_round_<r>.json`
  (`ESITO_giro_<r>.json` in an Italian jury). Exits with 0 if everything passes, with 2 and an "ERROR:" otherwise.
- `python3 -I swarmer/jury.py requests [register]`: the ids at the §4 threshold and the similar ids.
- `bash swarmer/swarmer.sh tests`: the skill's batteries, including the jury ones; to be run before every
  jury.

## 9. The local overrides

A project can have its own roles with the same id as a generic role, and its own rules. They live in
`swarmer/local/`, which is never sent to the skill's public repository and may contain the project's details:
- `swarmer/local/AGENTS.md`: cards in the `AGENTS.md` format; for the same id the local card **always** takes
  priority over the generic role, in all strategies, in juries and in plenaries;
- `swarmer/local/JURY.md`, `PIPELINE.md`, `PREAMBLE.md`: rules that add to the generic ones or
  replace them, declaring it;
- `swarmer/local/EXIT_CRITERIA.md`: the exit criteria of the project's phases, for the goal clause.

A role created by the project with the new expert strategy has two cards: the local one, with the details, and the
generic one, without them, which alone enters the database and the proposal to the repository.

## 10. The G2 protocol (the default)

Every new jury follows the G2 protocol; `"protocol": "G1.1"` is only for recounting juries voted
before it, that is a `giuria.json` without `"lessico"` with an outcome of round 0 without the protocol key (never a
`jury.json`, which exists only from 5.0; the variable `SWARMER_G11_TESTS=1`, or
`SCIAME_G11_PROVE=1`, is
only for the test batteries, and an OUTCOME written with it is not recounted without it). With G2:
- `jury.json` is sealed before round 0: the line `SEAL jury.json <sha>` in `SEALS.md`; no orphan SEAL;
- a binding jury has `"delegation": "DELEGATION.md"`, sealed, with one line `DELEGATED Dk` for every delegated
  decision; the others give at most RECOMMENDED;
- `PREFER` only among the `OPTIONS` of round 0;
- `"previous"`: the earlier juries on the same question; an option already REJECTED is not proposed
  again, and a second TO_REPROPOSE becomes TO_USER;
- in a plenary the relevant members of `RELEVANCE.md` vote (lines `RELEVANT <role>`, `PROXY <sub> <parent>`), and
  `CLASS plenary` is informative only; a light jury never counts as a plenary.

## 11. The two languages of the lines: the lexicons L4 and L5

A jury has a **dialect**, fixed by its root file: `jury.json` is English, `giuria.json` is Italian (both together are
an error). A new jury is born in the language of the installation. The dialect fixes the file names (`round_<r>/`,
`PROPOSAL.md`, `VOTE_<role>.md`, `SEALS.md`, `OUTCOME_round_<r>.json`, `DELEGATION.md`, `RELEVANCE.md`,
`CARD_<r>.md`, `RECUSAL_<r>.md`; in Italian `giro_<r>/`, `PROPOSTA.md`, `VOTO_<ruolo>.md`, `SIGILLI.md`,
`ESITO_giro_<r>.json`, `DELEGA.md`, `PERTINENZA.md`, `SCHEDA_<r>.md`, `RINUNCIA_<r>.md`), the keys of the root file
and the form of the outcome. A file with the name of the other dialect next to its own (`SIGILLI.md` with `SEALS.md`)
is an error; inside a round, a `VOTO_x.md` next to `VOTE_x.md` stays a foreign entry.

`jury.py count` reads the lines with one of two lexicons:
- **L4**, exactly the lexicon of 4.0: Italian words only. It applies to every round of a `giuria.json` without the key
  `"lessico"` (`"lexicon"`): so every jury voted with 4.0 is recounted identical byte for byte, also after the loss of
  an outcome, and an English line inside a vote of that time (for example `VOTE D1 yes`) stays free text, as it was.
- **L5**, the words of both languages: it applies to every round of a `giuria.json` with `"lessico": 5` and of every
  `jury.json` jury. The key is in the root file, sealed before round 0: an outcome never chooses the lexicon (the
  outcomes written in L5 carry `"lexicon": 5` too).

The words of L5, English ← Italian:

| English | Italian |
|---|---|
| `OPTION`, `OPTIONS Dk a \| b` | `OPZIONE`, `OPZIONI` |
| `OPERATIVE`, `DEPENDS Dk Dj`, `INCOMPATIBLE` | `DISPOSITIVO`, `DIPENDE`, `INCOMPATIBILE` |
| `TEST`, `TEST-OUTCOME Dk pass\|fail` | `PROVA`, `ESITO-PROVA Dk passa\|fallisce` |
| `VOTE Dk yes\|no`, `REVISION`, `CONDITION` | `VOTO Dk si\|sì\|no`, `REVISIONE`, `CONDIZIONE` |
| `CLASS Dk light\|ordinary\|plenary`, `CHANGE`, `PREFER` | `CLASSE Dk leggera\|ordinaria\|plenaria`, `CAMBIO`, `PREFERISCO` |
| `SEAL [round_<r>/]<file> <sha>`, `INCOMPATIBLE-VERIFIED <round> Dk` (in `SEALS.md`) | `SIGILLO`, `INCOMPATIBILE-VERIFICATO` (in `SIGILLI.md`) |
| `DELEGATED Dk` (in `DELEGATION.md`) | `DELEGATA Dk` (in `DELEGA.md`) |
| `RELEVANT <role>`, `PROXY <sub> <parent>` (in `RELEVANCE.md`) | `PERTINENTE`, `DELEGA` (in `PERTINENZA.md`) |
| `sha256 of the bytes before this line: <hex>` | `sha256 dei byte che precedono questa riga: <hex>` |

The rules of L5:
- **the keyword and the value are normalized independently**: `VOTE D1 sì` and `VOTO D1 yes` are accepted (`no` is
  the same in both languages). The check «two lines of the same kind for Dk» comes after: `VOTE D1 yes` and
  `VOTO D1 no` in the same vote are an error;
- **round tokens** `round_<r>` and `giro_<r>` are accepted in both dialects; one that names no existing round, or is
  malformed, is an error;
- **almost-conforming lines** (a protocol word at the start of the line, but the line does not conform) are an error
  in every file with lines: proposal, votes, `SEALS.md`, `DELEGATION.md`, `RELEVANCE.md`; the natural variants
  `DELEGATE` and `Delegated` too;
- **for the English words only** a line counts, or is almost conforming, only if the word is followed by a decision id,
  `D` and a digit (`D1`, `D2a`, …): so `## Test Design` or `Change Detection` stay prose. The Italian words follow the
  rule of 4.0;
- the protocol key is looked for among the keys of the outcome (`protocol` or `protocollo`), not as a substring of the
  text (L4 stays as in 4.0).

The printout of `count` (`D1: APPROVED — yes 5/5 — …`) is in the language of the installation; the outcome file stays
in the dialect of the jury.
