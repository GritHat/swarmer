# The jury, new experts and the plenary (protocol G, version 4.0 of the swarm)

This document gives the full rules of three strategies: **jury** (§2–§3), **new expert** (§4) and **plenary**
(§5). The tools are `giuria.py` and the skill's test batteries (§8). The short strategies are in
`PIPELINE.md`.

## 1. Authority, delegation and the goal clause

**What a jury decides.** A proposed decision: a choice among options, the text of an act, a
clarification, a rule. `giuria.json` declares `autorita`:
- **`raccomandazione`** (recommendation), by default: consensus yields **RACCOMANDATA** (recommended), and the user decides;
- **`vincolante`** (binding), only if the user has delegated the decision in writing, item by item (the `delega` field cites the
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
table, item by item: `delegata` (delegated), `riservata` (reserved) or `mista` (mixed), with the reason. Reserved and mixed items go to
recommendation. A narrow reading of the delegation is presented to the user as one reading, not as the only one.

**The goal clause (mandatory): the T-OB test.** Every proposal carries at its head, for each decision, four
points, each with a [V] proof (file and line):
1. **Target.** The exit criterion of the project's current phase that the decision serves, cited by
   identifier from the project's exit-criteria file (normally `sciame/locale/USCITE.md`, written by the user or with
   them), or a principle of the project. A phase without written exit criteria fails the test by construction:
   the criteria are written first, once per phase.
2. **Chain.** "With Dk criterion U moves from state a to state b", or "Dk removes blocker B, which lies on the
   critical path of U", with the file that shows B among the open blockers.
3. **Counterfactual.** Without Dk the criterion stays put or slips, and by how much. "No effect" fails the test,
   except for a zero-cost error correction.
4. **Cost.** The figures with their source, compared with what remains of the cap, and no shorter path already authorized.

The clause holds only if all four points pass. The goal guardian writes the four outcomes in their vote.
Every juror votes **no** if the clause does not hold.

## 2. The jury

**Composition.** The coordinator chooses it and writes it in `giuria.json` before opening the proposal. The file does
not change afterwards: `giuria.py` records its sha256 and rejects every round counted with a different composition.
- **Number of jurors:** from 5 to 9, an odd number.
- **Always present:**
  - the goal guardian;
  - an adversary (adversarial generator or inverter);
  - the debugger if the decision touches code;
  - the statistician if it touches thresholds, power or figures;
  - in a binding jury, the logician, the debugger and an adversary.
- **Mandatory fields:** `tocca_codice` and `tocca_numeri` (yes or no), `autorita`, `delega`, `classificazione`
  (`ordinaria` or `plenaria`).
- **Admitted roles:** only the codes of the swarm's roles (`.claude/agents/sciame-*.md`), professionals or
  sub-professionals. A provisional expert (§4) is
  marked `provvisorio` and has the sealed card `SCHEDA_<ruolo>.md` in the folder; they make up at most a third of the
  jurors.
- **New instances:** at least half of the jurors are new instances on the subject, that is, they have not written reports, passes or
  validations on the proposal or on its direct sources (`nuovo_sull_oggetto`).
- **The rapporteur** writes the proposal and the revisions, and does not vote. The rapporteur is not the coordinator.
- **The clerk** is an instance of the arbiter: does not vote, checks and counts with `giuria.py`.

**Competence.** A juror who does not consider themselves competent writes so **before** reading the proposal, in
`RINUNCIA_<ruolo>.md`. The coordinator replaces them before writing `giuria.json`: whoever withdraws cannot be a
juror. After reading, abstention does not exist.

**Independence.**
- Jurors are launched in parallel, each with their own folder.
- Each is briefed not to read the other jurors' folders or the outcomes.
- The revised proposal carries no names or vote counts: only the REVISIONE and CONDIZIONE lines, without the author.

## 3. The procedure and the vote

**The protocol lines** count only outside ``` blocks. A line that starts with a keyword but does not
conform is an error, not an ignored line.

**Round 0.**
1. The rapporteur writes `giro_0/PROPOSTA.md`, sealed. For each decision `Dk`:
   - `OPZIONI Dk (a) | (b) | …`: the closed list of the question's options;
   - `OPZIONE Dk <etichetta>`: the proposed option, taken from that list;
   - `DISPOSITIVO Dk <una riga>`: the operative core of the act, which no revision can change;
   - `DIPENDE Dk Dj`, if Dk presupposes Dj;
   - the full text that would become the act;
   - the T-OB test;
   - the line `PLENARIA no: <motivo>` (or `sì`);
   - the risks with their source;
   - the rejected alternatives.
2. Each juror, blind, writes `giro_0/VOTO_<ruolo>.md`, sealed. For each `Dk`:
   - `VOTO Dk si|no` ("sì" with the accent counts as si);
   - the rationale, with [V] or [I] proofs. A no without any [V] proof goes back to the juror once; after that it stands and is
     flagged;
   - for a no, `REVISIONE Dk <la revisione più piccola che mi farebbe votare sì>` (the smallest revision that would make me vote yes), or `REVISIONE Dk nessuna` (none);
   - for a yes, `CONDIZIONE Dk <che cosa una revisione non deve toccare>` (what a revision must not touch), or `CONDIZIONE Dk nessuna`;
   - `CLASSE Dk ordinaria|plenaria`: a single "plenaria" is enough to send the decision to the plenary;
   - optional, `PREFERISCO Dk <altra opzione dell'elenco>` (another option from the list).
3. **Each juror reports** the seals of their files in their final answer. The clerk writes them in `SIGILLI.md`,
   one line `SIGILLO giro_<r>/<file> <hex>` each, before the count. `giuria.py` rejects a file whose seal is not
   the one reported.

**The count** (`giuria.py conta`), with n jurors and s yes votes:

| votes | outcome |
|---|---|
| s = n (full consensus) | **APPROVATA** (approved), or RACCOMANDATA if the authority is a recommendation |
| n/2 < s < n (majority) | **REVISIONE** (revision): move on to the next round |
| s ≤ n/2 (minority), including s = 0 (consensus on no) | **RESPINTA** (rejected) |

**Three exceptions to consensus:**
- a `CLASSE plenaria` yields **DA_PLENARIA** (to the plenary);
- if more than half of the jurors prefer the same other option, the outcome is **DA_RIPROPORRE** (to be re-proposed): start again from round 0
  with that option;
- an approved decision that depends on one not approved does not become an act:
  - if the other is in REVISIONE, they are voted again together;
  - if the other is rejected or non-convergent, the outcome is **SOSPESA** (suspended) and the decision goes back to the user together with the other.

**Revision rounds (1, 2, 3)**, for decisions in REVISIONE:
1. The rapporteur writes `giro_<r>/PROPOSTA.md` with only the decisions under revision. `OPZIONE`, `DISPOSITIVO` and `DIPENDE`
   stay identical; clauses, conditions, order and wording change. Every changed piece cites the REVISIONE line
   it answers, with the diff from the previous round's text.
2. **It does not touch the CONDIZIONE lines of the yes votes**, which remain binding in all later rounds. If a REVISIONE
   requested by a no contradicts a CONDIZIONE of a yes, the rapporteur writes
   `INCOMPATIBILE Dk <le due righe in conflitto>` (the two conflicting lines). If the clerk verifies it, and writes the line
   `INCOMPATIBILE-VERIFICATO giro_<r> Dk` in `SIGILLI.md`, the decision is immediately **NON_CONVERGENTE**
   (non-convergent) and the votes on it do not count; without that verification the round is counted as a revision round.
3. All jurors vote again, blind, on the revised text. Whoever moves from no to yes writes `CAMBIO Dk <la modifica che
   risponde alla mia REVISIONE>` (the change that answers my REVISIONE); without this line the round is rejected. The move is measured
   against the juror's last expressed vote, even if it fell in a round discarded as regressive. A no on principle (`REVISIONE nessuna`)
   changes only in the face of new evidence, which the `CAMBIO` cites.
4. **The outcomes of the revision round:**

   | how the round goes | outcome |
   |---|---|
   | consensus | APPROVATA (with the exceptions above) |
   | the yes votes fall into a minority | **RESPINTA**: the counting rule, a minority rejects |
   | a yes is lost but the majority holds | **regressive** revision: it is discarded; the decision returns to the previous round's text and votes, stays in REVISIONE, and the round counts toward the limit |
   | otherwise | REVISIONE |

**The limit: three revision rounds**, that is, the second, third and fourth pass, fixed by the protocol. A
decision still in REVISIONE after round 3 is **NON_CONVERGENTE**:
- it is not approved;
- it goes back to the user with the votes and the remaining REVISIONE lines;
- "convergence is not forced".

**After a RESPINTA.** The rapporteur may bring another option from the same `OPZIONI` list, as a new proposal:
- once per option;
- in a new jury, which cites the previous one in `giuria.json` (`precedenti`);
- the clerk certifies `DIVERSA Dk <motivo>` (different, with the reason) with respect to the rejected text.

If all options are rejected, the question goes back to the user.

**`giuria.py` is the only source of the outcome.** It recomputes every round from the sealed files each time. It rejects:
- an ESITO already written that does not match, that is, a revote, a changed vote or a retouched ESITO;
- a round counted out of order;
- a foreign entry in the round's folder.

**The act.** The coordinator records in `.sciame/<giuria>/ATTO.md` the APPROVATA decisions with the final proposal, the outcome
(`ESITO_giro_<r>.json`) and the seals. Then carries them out, if the request allows it. The others are recorded with their outcome. The user receives a
short report. Every jury lives in `.sciame/<data>-giuria-<oggetto>/`. Agents write in their own folder; the
coordinator copies and checks.

## 3bis. The light jury

For small decisions with little influence (reversible, local, no reserved items), or where a mistake shows up with a
quick test (five minutes at most), a light jury costs less and tests before voting.
- **The jury**: `"forma": "leggera"` in `giuria.json`; three jurors: the role most competent for the feature, a critic
  (adversary, inverter or debugger) and the goal guardian; plus the rapporteur and the clerk. Not for a plenary; for a
  reserved item it gives at most a recommendation. The ordinary jury's composition rules on the debugger, the
  statistician and the binding pass do not apply: the test replaces them.
- **The test before the vote**: for each `Dk`, `PROVA Dk <command or check>` with the expected result written first,
  and `ESITO-PROVA Dk passa|fallisce` (passes or fails) after running it, before the vote. Without the two lines the
  count is refused.
- **The outcomes**: unanimity and a passing test, APPROVATA (or RACCOMANDATA); a failing test, RESPINTA; majority, a
  single revision round and then **DA_GIURIA** (the ordinary jury, from round 0, with the proposal and the votes as
  input); one juror's `CLASSE ordinaria`, DA_GIURIA at once; a `CLASSE plenaria`, DA_PLENARIA.
- **The goal clause** stays, in brief: the goal guardian checks it as in the ordinary jury.

## 4. Experts that do not exist yet

**The request.** A line in `sciame/RICHIESTE_ESPERTI.md` with six fields:
- the date;
- the convening: the path of its folder in `.sciame/`, which must exist;
- the requester: the code of a role, `coordinatore` or `provvisorio:<sigla>`;
- the competence, as a lowercase code;
- the subject it was needed for;
- the reason, at least ten characters long: which roles were considered and why they do not cover the competence.

`giuria.py richieste` normalizes the spellings of the requester, rejects non-conforming lines instead of ignoring them, and flags
similar codes.

**When two codes are the same expert.** The clerk merges two codes with a line
`` - `x`: unito a `y`, <motivo> `` (merged into y, with the reason): the requests for x are added to y.

**Convening an expert that does not exist.** The coordinator convenes a **provisional expert**:
1. writes the provisional card before reading the question in detail, and seals it;
2. launches a generic agent with the preamble and the card;
3. marks the contribution as [provvisorio];
4. records the convening itself as a request.

The provisional expert does not count toward their own creation.

**The creation threshold.** Either of two conditions applies:
- **(a) simultaneous:** in one convening at least 3 distinct roles ask for it; in a plenary, at least 5, because
  there everyone receives the same invitation;
- **(b) accumulated:** at least 3 requests in at least 2 convenings, from at least 2 distinct roles.

How requests are counted:
- a role counts once per code and per convening;
- the coordinator counts for at most one request per code, and never as a distinct role;
- the user can order the creation directly.

**The creation**, after the user's approval (or that of a jury the user delegated it to):
1. the card in a JSON file, in the database format, with the texts in every language of the skill and, for a
   sub-professional, its parent;
2. `bash sciame/sciame.sh approva <card.json>`: the entry joins the database, agents, skills and documents are
   regenerated, `sciame.sh` is rebuilt, and the requests for the code name are closed with «creato: n. NN»;
3. `bash sciame/sciame.sh proponi <code>` prepares the pull request to the public repository; with `--invia --si` it opens it.

A skill that matters only to the project stays a local card (`sciame/locale/AGENTI.md`) and is not approved.

In the session in which it is born, the role is launched as a generic agent with the card.

## 5. The plenary convening

**When.** Only in two cases:
1. **The transition from one major phase of the project to the next**, as the project defines them.
2. **A choice of enormously important impact.** A choice is such if it changes a goal, the principle or a
   directive; opens or closes a line of work, a candidate or a phase; is irreversible; commits resources beyond the authorized
   caps.

How a decision reaches the plenary:
- the coordinator proposes the classification with the reason, in the `PLENARIA` line of each proposal;
- a wrong classification is a reason for no;
- a single juror's `CLASSE plenaria` is enough to bring the decision to the plenary;
- a serious choice is not cut into ordinary slices: the goal guardian checks this.

**The five levels.** Each level passes a sealed dossier to the next, with the predictions sealed before
starting.
1. **The whole swarm.** The coordinator writes the question, sealed, with the T-OB test. Every role, including the
   new ones and the requested provisional experts, writes a short opinion (at most one page) and the expert requests.
2. **The usual convening** of the protocol in force for the subject, on the level 1 opinions:
   - the classic one for hypotheses, measurements and research;
   - the jury for a proposal already prepared.

   **If level 2 does not converge, the plenary stops** and goes to the user with the causes.
3. **The general critical pass** on the outcome of level 2: adversary, inverter, debugger, creative and goal guardian,
   plus the experts of the systems involved.
4. **The arbiters.** Two independent instances of the arbiter each write a convergence; the social-choice
   expert checks the procedure. A disagreement on a fact is settled with a proof. If there is no proof, it becomes a
   declared risk, or two distinct options in the final proposal. The rapporteur of the vote is one of the two
   arbiters.
5. **The final vote.** New instances of the **relevant professionals** vote: those who at level 1 did not
   write "non pertinente" (not relevant), minus the rapporteur and the clerk. A sub-professional votes only on written delegation from their
   professional, in their place and never together with them. Every voter reads the final proposal and the dossiers of levels
   1–4. The rules are those of §3, with the consensus of all voters; a tie is not a majority, and there is no
   drawing of lots. Revision rounds redo only the vote, not levels 3–4. `giuria.json` lists the voters and the level 1
   file that establishes their relevance.

**Cost.** About 60–70 agents, plus about 25 for each revision round. The coordinator announces it beforehand.

## 6. Declared limits

- **A single model.** If the jurors are instances of the same model, Condorcet's theorem does not apply:
  APPROVATA means "no juror found an objection that holds", not "verified". Where the environment
  allows it, jurors from different models make the vote more independent.
- **Trust in the coordinator remains at three points:**
  - `SIGILLI.md` is written by the clerk from the jurors' final answers, which the coordinator receives;
  - `nuovo_sull_oggetto` is self-declared;
  - the blind vote rests on the brief, not on a technical separation.

  The coordinator declares them in every report and never uses them for their own benefit.
- **The veto.** The veto of a single juror is intended: only consensus approves. In plenaries the typical outcome will be
  REVISIONE or NON_CONVERGENTE.
- **Strategic voting** is made visible (CAMBIO, PREFERISCO, CONDIZIONE), but not eliminated.

## 7. The choices of form, which a project can change

A project can change these choices in `sciame/locale/GIURIA.md` (§9), declaring it:
1. three revision rounds before NON_CONVERGENTE;
2. a revision that falls into a minority is RESPINTA;
3. the expert creation thresholds: 3 in one convening, 5 in a plenary; or 3 requests in 2
   convenings from 2 roles;
4. in the plenary a tie is RESPINTA, and the consensus of the relevant voters applies.

## 8. Tools

- `python3 -I sciame/giuria.py conta <cartella> <giro>`: recomputes every round, writes `ESITO_giro_<r>.json`. Exits
  with 0 if everything passes, with 2 and an "ERRORE:" otherwise.
- `python3 -I sciame/giuria.py richieste [registro]`: the codes at the §4 threshold and the similar codes.
- `bash sciame/sciame.sh prove`: the skill's batteries, including the jury ones; to be run before every
  jury.

## 9. The local overrides

A project can have its own roles with the same code as a generic role, and its own rules. They live in
`sciame/locale/`, which is never sent to the skill's public repository and may contain the project's details:
- `sciame/locale/AGENTI.md`: cards in the `AGENTI.md` format; for the same code the local card **always** takes
  priority over the generic role, in all strategies, in juries and in plenaries;
- `sciame/locale/GIURIA.md`, `PIPELINE.md`, `PREAMBOLO.md`: rules that add to the generic ones or
  replace them, declaring it;
- `sciame/locale/USCITE.md`: the exit criteria of the project's phases, for the goal clause.

A role created by the project with the new expert strategy has two cards: the local one, with the details, and the
generic one, without them, which alone enters the database and the proposal to the repository.

## 10. The G2 protocol (the default)

Every new jury follows the G2 protocol; `"protocollo": "G1.1"` in `giuria.json` is only for recounting juries voted
before it, that is with an `ESITO_giro_0.json` without the «protocollo» key (the variable `SCIAME_G11_PROVE=1` is
only for the test batteries, and an ESITO written with it is not recounted without it). With G2:
- `giuria.json` is sealed before round 0: the line `SIGILLO giuria.json <sha>` in `SIGILLI.md`; no orphan SIGILLO;
- a binding jury has `"delega": "DELEGA.md"`, sealed, with one line `DELEGATA Dk` for every delegated decision; the
  others give at most RACCOMANDATA (recommended);
- `PREFERISCO` only among the `OPZIONI` of round 0;
- `"precedenti"`: the earlier juries on the same question; an option already RESPINTA (rejected) is not proposed
  again, and a second DA_RIPROPORRE becomes DA_UTENTE (to the user);
- in a plenary the relevant members of `PERTINENZA.md` vote (lines `PERTINENTE <role>`, `DELEGA <sub> <parent>`), and
  `CLASSE plenaria` is informative only; a light jury never counts as a plenary.
