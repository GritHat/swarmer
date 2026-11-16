# Swarm convenings: eight strategies

**Status.** Version 5.0 (swarmer) of 16 November 2026: the strategies and rules of 4.0, with English names for
commands, files and protocol lines (§«What changes»). Version 4.0 added to the four strategies of 3.1 (single,
classic, full, auto):
- the **jury**, which decides a proposal by vote;
- the **plenary**, for phase transitions and choices of enormously important impact;
- the **fan-out**, which splits a job into parallel slices or puts several agents in a race on the same brief;
- the **new expert**, which convenes a competence the swarm does not have yet and grows it when it is truly needed.

The roles are **professionals** (the general competences) and **sub-professionals** (their specializations), in a
single database, `db/professionals.json`. Its public form is English: every entry has complete English texts, the
other languages are optional. An entry without the language of the installation is generated from the English text
and marked `translation-pending: <language>`; the coordinator translates it the first time it convenes it
(`bash swarmer/swarmer.sh translate <id> <file.json>`), and the translation stays in the local overlay
of the swarm folder, `local/translations/<language>/<id>.json`, never distributed nor published, which survives the updates.
When the public database later brings its own translation, the public one wins, unless the local one was modified
by hand.

| strategy | what it does | when | how many agents | cost |
|---|---|---|---|---|
| **single** | one specialist, the best suited | clear question in one field, small task, named role | 1 | low |
| **fan-out** | N agents in parallel: slices of a job, or a race with the selection rule declared beforehand | broad coverage, divisible jobs, several independent attempts | 2–16 | low or medium |
| **classic** | the graph pipeline: contract, two blind lanes, triage, tournament, teams per hypothesis, tests, verdicts | decision, design, defect, proof, alternatives, risk | 6–15 | medium |
| **jury** | one proposal, a jury that votes: consensus approves, majority revises, minority rejects | deciding among options already prepared, the text of an act, a rule | 7–11 | medium |
| **full** | the whole swarm together in one blind round, without a vote; the consolidation feeds into the classic | strategic or open question, many fields, "every point of view" | all the professionals plus the classic | high |
| **plenary** | full, usual convening, critical pass, two arbiters, final vote with consensus | phase transitions, enormously important choices, irreversible ones | 60–80 and more | very high |
| **expert** | an expert that does not exist yet, with a provisional card; the request is recorded | a competence is missing | 1 plus the card | low |
| **auto** | the coordinator chooses among the others, and the roles | always, when unsure | depends on the choice | depends on the choice |

The blocks between the `<!-- strategy:… -->` markers are the text the generator copies into the convening skills and
into the catalog: they must be kept complete and short. The rest of the document explains and motivates them.

<!-- brief -->
## The brief, in every strategy

Every agent starts from zero: the brief must be enough on its own. It always contains:
- **the role** and the phase;
- **the purpose**, in one sentence, and the **done criterion**: the check that says whether the work is finished and good,
  written beforehand;
- **the inputs**: the full text of the request and the absolute paths of the files to read;
- **the write scope**: the only folder the agent writes to, different for each agent that writes;
- **the forbidden scope**: what it does not touch, read or run;
- **the verification**: the command or check the agent runs before delivering, if it has the tools;
- **the shape of the answer**, headed by one of the three outcome words:
  - **DONE**: the done criterion is met, with the evidence;
  - **ISSUES**: the work is there, but with listed defects, one per line, each with its evidence;
  - **BLOCKED**: it cannot go on, with the cause and what would be needed;
- **the limits**: time, length, resources.

An agent's report is evidence, not proof: the coordinator reruns the promised checks on the integrated result
before declaring it. An agent that stops or does not answer is declared as such: the work goes on without it and
its part stays uncovered, written down as uncovered. Never say that an agent, a review or a test has worked
if the environment has not reported it.
<!-- /brief -->

<!-- strategy:single -->
## Single, in brief

When: the request belongs to one field and is clear (an explanation, a review, a translation, a calculation, a
small task), or the user names the role.
1. Choose the best-suited role, from its "in brief" and its keywords. If the user names one, that is the one.
2. Write a complete brief, because the specialist sees nothing else:
   - the question;
   - the inputs, including the full text of the request;
   - the expected result and its shape;
   - the limits and the prohibitions.
3. The specialist works and rereads its work with its "questions it always asks itself".
4. You check the result against the question. If something is missing or there is an obvious error, do a single retry,
   with the precise request.
5. Answer with the result, with the outcome word (DONE, ISSUES, BLOCKED) and what is not verified.
<!-- /strategy:single -->

<!-- strategy:fan-out -->
## Fan-out, in brief (N agents in parallel)

When: the job splits into independent parts (files, modules, chapters, cases, sources), or several independent
attempts at the same task are needed to choose one.
1. **The form**, written before launching:
   - **slices** (`slices`): each agent has a different part; coverage requires an outcome for every slice;
   - **race** (`race`): all have the same brief; the **selection rule** is declared beforehand: the first that meets
     the done criterion (`first`), the ranking of all with the written criterion (`ranking`), or the best of N (`best`);
   - **mixed** (`mixed`): slices, with a race on some of them.
2. **N** is the total number of agents, not how many run together: at most five at a time. Each agent's role
   comes from the profile, or is the one named; in a race between different roles or models, each arm is declared beforehand.
3. **The briefs** follow "The brief, in every strategy", with the slice or the arm of the race. Each agent that
   writes has its own folder, `.swarmer/<convening>/agent-<n>/`, or a branch or working copy of its own.
4. **The collection.** Read only the final outcomes:
   - in slices, every slice must have an outcome; those without an outcome are uncovered and you say so;
   - in a race you apply the declared rule, never a different choice afterwards.
5. **The answer** is a table, one row per slice or per arm (outcome, evidence, file); then the issues, one per line
   with the evidence; then the uncovered parts; then, in a race, the rule applied. No copy of the raw reports.
6. **The final verification** is yours, on the integrated result: the agents' evidence is not proof.
<!-- /strategy:fan-out -->

<!-- strategy:classic -->
## Classic, in brief (the graph pipeline, extended)

When: something must be decided, designed, fixed, proved or measured; there are alternatives; an error is costly; there is a
risk to control. The roles of each phase come from the task profile (table "Profiles").

**f0, the contract (yours).** It contains:
- the question, a single one;
- the criterion that decides whether the answer is good: a measure or a check, never a mechanism;
- the inputs;
- the principles and constraints of the project, and the exclusions;
- the quota of agents and time, split into three thirds;
- the profile.

If the request is ambiguous, the requirements analyst clarifies it. If the criterion is a measure, the metrologist checks
that it measures what it claims.

**f1, two blind lanes, in parallel.** Each role receives only its own brief and the contract.
- Lane A, conservative, has one or two specialists of the profile: diagnosis, constraints, two proposals with the
  possible counterexamples.
- Lane B, divergent, has the creative (at most four translated ideas) and the inverter (at most two inversions).
- Every idea carries the statement, the expected gain, the constraints, who can test it and the cheapest falsifier:
  at most five minutes, with the expected outcome written beforehand.
- The lanes do not read each other, and you read nothing until they have all delivered.

**f2, translation, signatures, triage, tournament, selection.**
1. A role with no ideas in the competition (the profile's translator) writes one card per idea:
   - the object;
   - the precise statement;
   - the type;
   - the risks;
   - the critical hypothesis and the candidate counterexample;
   - how it is verified.

   No merging: two ideas are the same only if statement and type coincide.
2. Each author signs the cards of their ideas: "faithful" or "lost: …", and an author who marks "lost" gets their version
   as a separate card.
3. The arbiter does the triage: assigns the H# with a class among TEST, REFORMULATE, OPEN and REFUTED (only with
   evidence), and ranks the top three.
4. The adversary runs the falsifier of every H# marked TEST or OPEN (without tools, it carries it out by reasoning).
   A refutation counts for the idea only if a check that does not share the prototype decides it.
5. The arbiter proposes at most three H# plus one radical one, and you decide.

**f3, one team per chosen H#.** Each branch is independent of the others.
- The lead writes the solution: steps, invariants, cost, "depends on", "invalidated if it changes".
- Another role writes the proof or the verification.
- The metrologist writes the measurement plan, with the thresholds, before the tests.
- The adversary prepares the attack.
- If needed, the cost is estimated (economic analyst, performance engineer).

**f4, the tests, cheapest first.** The test classes:
1. by hand, or exhaustive on a small case (at most five minutes);
2. with an independent oracle;
3. a realistic test;
4. a test at scale;
5. a paid or irreversible test, only with the user's yes.

Class k starts only after the outcome of class k−1. The order of the tasks:
- first the adversary's counter-tests;
- then the debugger on the anomalies and, if the counter-tests hold, the measurements;
- then the statistician on the numbers.

A failure stops the branch and preserves its counterexample.

**f5, verdicts and closure.**
- For each H#, the dossier with the status per property: correctness, completeness, effectiveness, cost.
- Every foundational result passes four verifications:
  1. the reread;
  2. the hidden-assumption audit, by a role not involved;
  3. the counterexamples;
  4. the arbiter's consolidation.
- The arbiter closes only if these three conditions hold:
  - at least one H# proved;
  - no open contradiction on an adopted conclusion;
  - every prediction resolved, or declared unresolved with the test that would decide it.

**f6, the integration (yours).** You integrate only what the request permits, and bring the user at most three
high-leverage decisions.

**Always.**
- An anomaly goes to the debugger before being used.
- A K# contradiction goes to the two roles that hold it and to the adversary, with a binary question and at most two
  passes.
- At most five agents at a time.
- Once the first third of the quota is spent, you move to the verdict with what there is.
<!-- /strategy:classic -->

<!-- strategy:full -->
## Full, in brief (the whole swarm, then the classic)

When: the question is strategic or open, touches many fields, asks for every point of view, or a classic has not
been enough.
1. **f0, the contract**, as in the classic.
2. **Wide f1, the global round.**
   - All the roles of the swarm take part, except the arbiter, in waves of at most five.
   - Each is blind to the others and has the same brief: the contract, and a contribution from its own point of view of at
     most half a page. That is one to three observations or proposals, each with its evidence or its falsifier.
   - A role that has nothing to say writes "not relevant: …" in one line, and that is fine.
3. **f1c, the arbiter's consolidation.** First per core, then overall:
   - the facts F#, with their status;
   - the contradictions K#;
   - the candidate ideas, with their origin;
   - the open questions.

   There is no vote.
4. **The graft onto the classic.** The candidate ideas enter f2 as input cards, and from there it proceeds as
   in the classic: translation, signatures, triage, tournament, selection, f3, f4, f5, f6. Lane A and lane B are not
   redone: the global round contains them.
<!-- /strategy:full -->

<!-- strategy:auto -->
## Auto, in brief (the coordinator's choice)

Choose before launching agents, and write the choice in one line at the top of the answer, for example: "Swarm: auto,
chose classic, profile code (there are two fixes to choose between)."
- **single:** the request is clear, belongs to one field, and an error is visible and cheap; or it asks for an
  explanation, a translation, a review, a summary, a calculation.
- **classic:** something must be decided, designed, fixed, proved or measured; there are alternatives; an error is costly;
  there is a risk to control.
- **full:** the question is strategic or open, touches at least three cores, asks for every point of view, or a
  previous classic has not been enough.
- **fan-out:** the job splits into independent parts, or several attempts at the same task are needed.
- **jury:** there is a proposal already prepared, with clear options, to decide; the outcome is a recommendation, unless the
  user has delegated in writing.
- **light jury:** the decision is small and of little influence, or a mistake shows up with a quick test: three
  jurors, the test before the vote, a single round, then the ordinary jury if needed.
- **plenary:** only for a transition from one major phase to another or for a choice of enormously important
  impact (it changes a goal, opens or closes a line, is irreversible, commits resources beyond the given limits); the
  coordinator proposes it, the user confirms it.
- **expert:** the request asks for a competence no role has (as the search through the keywords and the
  "in brief" shows).

When in doubt between two strategies, choose the cheapest one that meets the success criterion. Never the full for a
request of a few lines with a verifiable answer.

The roles are those of the profile, plus those whose keywords appear in the request. A sub-professional
is convened instead of its professional when the request falls within its specialization; otherwise the
professional is convened.
<!-- /strategy:auto -->

<!-- strategy:jury -->
## Jury, in brief (one proposal, one vote)

When: a proposal already prepared must be decided: a choice among options, the text of an act, a rule. The
complete rules are in `JURY.md`; here is what is needed to convene it.
1. **The authority.** Normally the outcome is a **recommendation** to the user. It becomes **binding** only if the user has
   delegated in writing, item by item. Paid, irreversible or outward-facing actions always remain
   with the user.
2. **The jury**, written in `jury.json` before the proposal is opened, sealed (`SEAL jury.json <sha>` in `SEALS.md`, G2 protocol of `JURY.md` §10) and unchanged from then on:
   - from 5 to 9 jurors, an odd number, at least half of them new instances on the subject;
   - always the goal guarantor and an adversary; the debugger if the decision touches code, the statistician if it
     touches numbers; in a binding jury also the logician and the debugger;
   - a rapporteur who writes the proposal and does not vote; an arbiter as clerk, who counts and does not vote.
3. **The proposal**, sealed, has for each decision `Dk` the lines `OPTIONS`, `OPTION` (the proposed option),
   `OPERATIVE` (the operative text) and possibly `DEPENDS`, the text of the act, the **goal clause** (target, chain, counterfactual,
   cost, each with evidence) and the line `PLENARY no|yes` with the reason.
4. **The votes**, blind and sealed: for each `Dk` the lines `VOTE`, `REVISION` (for a no) or `CONDITION` (for a yes),
   `CLASS ordinary|plenary`, and optionally `PREFER`. Each juror reports their own seals in the final
   answer, and the clerk writes them into `SEALS.md`. The Italian forms of the lines are accepted too (`JURY.md` §11).
5. **The count** is done by `python3 -I swarmer/jury.py count <folder> <round>`:
   - full consensus: APPROVED, or RECOMMENDED if the authority is a recommendation;
   - majority: REVISION, that is a round with a small revision that does not touch the CONDITION lines of the yes votes;
   - minority or consensus on no: REJECTED.
6. **At most three revision rounds.** A revision that loses a yes is discarded; one that puts the yes votes in the minority
   rejects; after the third round the decision is NOT_CONVERGED and goes back to the user.
7. **The answer**: the decisions with their outcome, the votes, the revisions, the declared limits of the procedure.
<!-- /strategy:jury -->

<!-- strategy:light-jury -->
## Light jury, in short (small decisions, test before the vote)

When: a small decision with little influence (reversible, local, no reserved items), or a choice where a mistake shows
up with a quick test, five minutes at most. Testing first with little coordination is preferred.
1. **The jury**, in `jury.json` with `"form": "light"`: three jurors, that is the role most competent for the
   feature, a critic (adversary, inverter or debugger) and the goal guarantor; plus the rapporteur and the clerk.
2. **The test before the vote.** For each `Dk` the proposal carries, besides `OPTIONS`, `OPTION`, `OPERATIVE` and
   the goal clause in brief:
   - `TEST Dk <command or check>`, with the expected result written first;
   - `TEST-OUTCOME Dk pass|fail`, after running it and before the vote.
3. **The votes** as in the jury, with `CLASS Dk light|ordinary|plenary`.
4. **The outcomes** (`jury.py count`):
   - unanimity and a passing test: APPROVED, or RECOMMENDED;
   - a failing test: REJECTED, even with unanimity;
   - majority: a single revision round, then **TO_JURY**, that is the ordinary jury;
   - a juror who writes `CLASS ordinary` sends it to the ordinary jury at once (TO_JURY); `plenary`, to the
     plenary.
5. **The cost** is five agents. Not for reserved items in binding form, nor for a plenary.
<!-- /strategy:light-jury -->

<!-- strategy:plenary -->
## Plenary, in brief (for the gravest choices)

When: only for the transition from one major phase of a project to another, or for a choice of enormously important
impact. The coordinator proposes it with the reason, and the user confirms it. It costs from 60 to 80 agents and more:
declare it beforehand.
1. **Level 1, the full:** all the professionals, in waves, blind, with a short opinion and the requests for
   experts; those not concerned write "not relevant".
2. **Level 2, the usual convening** for the subject: the classic, or the jury if the question is a proposal already
   prepared. If it does not converge, the plenary stops and goes back to the user with the causes.
3. **Level 3, the critical pass:** adversary, inverter, debugger, creative, guarantor and the experts of the systems
   affected, on the outcome of level 2.
4. **Level 4, two independent arbiters** each write a convergence; where they disagree on a fact, a test
   separates them, otherwise the disagreement becomes a declared risk or two options.
5. **Level 5, the final vote** with the jury's rules and consensus among the voters: the voters are new instances of the
   professionals that did not write "not relevant" at level 1; a sub-professional votes only on delegation from its
   professional, and never together with it.
<!-- /strategy:plenary -->

<!-- strategy:expert -->
## New expert, in brief (a competence the swarm does not have)

When: the request asks for a competence that no professional or sub-professional covers.
1. **Search first**: `bash swarmer/swarmer.sh roles "<the request>"` and the "in brief" texts. If a role covers it, use
   that one.
2. **The provisional card**, written before reading the question in detail, in the card format: name,
   in brief, parent (the closest professional, if it is a specialization), keywords, mission,
   competences, questions, limits. It is sealed.
3. **Launch** a generic agent with the preamble and the card; its contribution is marked [provisional].
4. **Record the request** in `swarmer/EXPERT_REQUESTS.md`, with the reason: which roles you looked at and why they are not
   enough. Agents that, during a convening, ask for an expert that does not exist do the same.
5. **The threshold.** `bash swarmer/swarmer.sh requests` says which competences have reached the threshold: three roles in the
   same convening (five in a plenary), or three requests in two convenings from two roles.
6. **The approval.** At the threshold, propose the creation to the user, with the final card in English (mandatory for the public database) and, if you want, in the language of the
   installation.
   Once approved, `bash swarmer/swarmer.sh approve <card file>` adds it to the database, regenerates agents, skills and
   `swarmer.sh`, and prepares the proposal for the public repository.
<!-- /strategy:expert -->

<!-- profiles -->
## Profiles by task type

| profile | for | f1, lane A | f1, lane B | f2, translates | f3, per H# | f4, per H# |
|---|---|---|---|---|---|---|
| `code` | writing or changing code | architetto, sviluppatore | creativo, rovesciatore | logico | sviluppatore (solution), tester (verification), avversario | avversario, debugger, tester |
| `defect` | bugs, errors, anomalies | debugger, sviluppatore | rovesciatore | logico | debugger (cause), tester (test that fails first), avversario | avversario, debugger, prestazioni if it is slowness |
| `architecture` | design of a system, technical choices | architetto, requisiti | creativo, rovesciatore | logico | architetto (solution), sicurezza, ottimizzazione, avversario | avversario, prestazioni, economista |
| `test` | mathematics, logic, correctness | formalista, matematico | rovesciatore | logico | formalista (proof), logico (reread), avversario | avversario |
| `data` | analysis, statistics, measurements, experiments | statistico, metrologo | creativo, rovesciatore | logico | dati (solution), metrologo (plan), statistico, avversario | avversario, debugger, statistico |
| `ai` | models, prompts, agents, training | llm, ml | creativo, rovesciatore | logico | llm or ml (solution), metrologo, sicurezza, avversario | avversario, statistico, debugger |
| `research` | state of the art, comparisons | ricercatore, esperto-dominio | creativo, machine-intelligence | logico | ricercatore (synthesis), fonti, avversario | fonti, avversario |
| `writing` | texts, documents, letters | redattore, esperto-dominio | creativo, rovesciatore | requisiti | redattore (text), lettore, fonti, avversario | lettore, fonti |
| `study` | explaining, learning, revising | didatta, esperto-dominio | creativo, visualizzatore | redattore | didatta (explanation), visualizzatore, lettore | lettore, avversario |
| `decision` | choosing among options, purchases, investments | requisiti, economista | rovesciatore, creativo | logico | economista (comparison), normativo, pianificatore, avversario | avversario, statistico |
| `plan` | projects, organization, calendars | pianificatore, requisiti | rovesciatore | logico | pianificatore (plan), economista, avversario | avversario |
| `security` | risks, privacy, permissions | sicurezza, infrastruttura | rovesciatore, creativo | logico | sicurezza (countermeasures), normativo, avversario | avversario, debugger |
| `device` | hardware, firmware, tablets, protocols | embedded, infrastruttura | creativo, rovesciatore | logico | embedded (procedure), sicurezza, metrologo, avversario | avversario, debugger, metrologo |
| `interface` | UX, panels, flows, interface copy | interfacce, requisiti | creativo, rovesciatore | logico | interfacce (proposal), lettore, redattore, avversario | lettore, avversario |
| `perception` | detecting, segmenting and recognizing from images and point clouds | visione, nuvole-punti | creativo, rovesciatore | logico | visione (solution), validazione, metrologo, avversario | avversario, debugger, validazione, statistico |
| `motion` | scenes that change with motion: moving objects, changes, events | scene-dinamiche, slam | creativo, rovesciatore | logico | scene-dinamiche (solution), validazione, tracciamento, metrologo, avversario | avversario, debugger, validazione, statistico |
| `estimation` | state estimators, Kalman filters, measurement fusion | kalman, fusione | rovesciatore, creativo | logico | kalman (solution), matematico, metrologo, avversario | avversario, debugger, statistico |
| `tracking` | following multiple objects over time: association, identity, prediction | tracciamento, kalman | creativo, rovesciatore | logico | tracciamento (solution), validazione, metrologo, avversario | avversario, debugger, statistico |
| `localization` | ego-motion, odometry, SLAM, maps | slam, kalman | creativo, rovesciatore | logico | slam (solution), fusione, metrologo, avversario | avversario, debugger, statistico |
| `sensors` | selection, mounting, synchronization and calibration of LiDAR, cameras, radar, inertial units | lidar, sensori | rovesciatore, creativo | logico | lidar (solution), fusione, metrologo, avversario | avversario, debugger, metrologo |
| `latency` | real-time perception: latency, stream synchronization, onboard computation | tempo-reale, prestazioni | creativo, rovesciatore | logico | tempo-reale (solution), ottimizzazione, metrologo, avversario | avversario, debugger, prestazioni |
| `general` | everything else | logico, machine-intelligence | creativo, rovesciatore | formalista | as the case requires, metrologo, logico (proof), avversario | avversario, debugger, statistico |

In every profile:
- in f2, the authors' signatures, the arbiter's triage and selection, the adversary's tournament;
- in f4, the debugger on every anomaly from any phase;
- in f5, the arbiter for the closure.

The translator must not have ideas in the competition: if it is already in lane A, the formalist translates, or the logician if the formalist is
in the competition. Every role whose keywords appear in the request is added, within the quota. The domain expert
has in its brief the field it speaks about.

In the perception profiles (`perception`, `motion`, `estimation`, `tracking`, `localization`, `sensors`,
`latency`) the lead of f3 is the first role listed. If the task belongs to another field (a point cloud in the
`perception` profile, a camera in the `sensors` profile), change it with `select --owner`.
<!-- /profiles -->

---

## Why eight strategies

The first versions of the swarm knew two modes.
- **The v1 rounds**: all the roles on the same question, and an arbiter who reads everything. They were costly: a single open
  point made everyone redo the round.
- **The v2 graph convening**: a few separate hypotheses, stopped early when they fall, with checkable gates.

The two serve different purposes, and most everyday requests need neither: the
right specialist is enough.
- **Single:** for small requests, one well-written brief to the right specialist is worth more than a swarm.
- **Classic:** it is v2 made general. It separates the hypotheses, tests them cheapest first and declares what
  is proved.
- **Full:** it is the v1 global round, without a vote. It serves when it is not yet known where to look, and its
  result is not a conclusion: it enters the classic as material to be screened.
- **Auto:** it makes the choice in the user's place, with the rules written above, and declares it.
- **Fan-out:** when the job is large but divisible, or when it pays to compare independent attempts. The
  selection rule written beforehand prevents choosing, afterwards, the result one likes.
- **Jury:** a decision already prepared does not call for more hypotheses, but for an independent and verifiable judgment. The vote
  with consensus, the small revisions without regression and the limit on rounds make it so.
- **Plenary:** the gravest choices deserve every point of view, a critical test and a vote, in that order.
- **New expert:** a fixed swarm ages. Missing competences are requested with a reason, and become roles
  only when several convenings ask for them.

## Non-negotiable principles

- **The criterion before the mechanism.** The contract says how a good answer is recognized, never which solution
  to adopt.
- **Evidence before conclusions.** The rules of `PREAMBLE.md`: distinct states, predictions timestamped before the
  tests, numbers with their file.
- **Independence by error class.** Every check declares what it shares with what it checks. Only a
  check that does not share the defect can rule it out. A common mode (two checks that fail in the same
  way) is closed on the class, not on the single witness.
- **Frozen predictions.**
  - They are written before the test that decides them, with the time and the threshold.
  - If the premise changes (version, data, configuration), the prediction stays, marked "premise changed", and tests
    the model, not the mechanism.
  - A test decides only if it starts after the recording.
- **Writes.**
  - Agents write only in the convening's space.
  - The coordinator integrates, and only what the request permits.
  - Irreversible, paid or outward-facing actions are decided by the user.
- **Convergence is not forced.** An incomplete solution is declared with its causes. An acceptance by default
  (time is up, take what there is) is not an "unresolved": it is a missing decision, and it is declared.

## The classic strategy in detail

The graph is f0 → f1 → f2 → one f3 → f4 branch for each chosen H# → f5 → f6. The dependencies are between files and gates, not
between role names: a task starts as soon as its inputs are frozen. The H# branches do not wait for each other;
only f5 waits for all the branches.

### The gates

Every phase ends with a gate, which the coordinator approves after reading the files. With files, it is checked by
`convene.py gate`, which binds the phase's files with sha256: a file changed after
approval makes the gate invalid. A gate is not approved because the files exist.

| gate | conditions |
|---|---|
| G0 | complete contract: question, criterion, inputs, constraints, quota, profile |
| G1 | deliverables from all the lanes (or "not delivered" after two stops), no canary of one lane in the other, the snapshot of the reads taken before reading |
| G2 | authors' signatures before the triage seal, seal before the tournament, selection only among the triage's H#, the arbiter's countersignature |
| G3 (per H#) | solution, verification, measurement plan and predictions frozen; the thresholds reachable and with a test that can decide them |
| G4 (per H#) | counter-tests before any cost; classes in order; predictions sealed before their tests; anomalies explained or declared; dossier complete |
| G5 | the arbiter's closure conditions and the four verifications of the foundational results |

### Lane blindness

- Each lane writes in a randomly named folder. Only the coordinator knows the folder map.
- Every deliverable begins with its lane's canary: G1 rejects if the canary of one lane appears in the other.
  The canary detects a copy, not a read.
- As soon as the lanes have delivered, before reading, `convene.py snapshot` records for each file whether it was read
  after its last write. It is a clue, not proof.
- The agents all run as the same user: permissions do not prevent reading, so blindness lies
  in the briefs, in the canaries and in the coordinator's discipline.
- Without files (agents without tools), blindness comes from each agent receiving only its own brief.

### The sentinel

In classics with at least two branches, in f2, f3 and f4 a role that was not convened works, drawn at random. It has twenty minutes in
read-only mode and delivers:
- a shared assumption, put to the test with an external check;
- the figures and identifiers of the dossier, recounted from the files.

A K# of its own enters only with a file. It serves to find what no profile would have convened.

### Anomalies: the debugger

- **What an anomaly is:**
  - an outcome that contradicts a prediction;
  - a time or a memory use out of scale with respect to a nearby case;
  - a divergence between two implementations or with an oracle;
  - an error, an "undecided" or a default value that nobody explains.
- **It goes to the debugger** before entering a verdict, with only the files involved, the symptom with its figure and the
  nearby case that works.
- **The debugger delivers** the proven cause: a minimal reproduction that fails before the fix and passes after.
  It also delivers the class of the defect, where else it may be, and the fix with its test.
- **Without a proven cause** the anomaly stays "unexplained", and supports no claim.

### Contradictions: the local cycles

- A K# goes to the two roles that hold it and to the adversary, with only the files involved, a binary question and the test
  that decides it. If it is an anomaly in the code, the third is the debugger.
- At most two passes are made; then the K# stays OPEN, with the cost of the decisive experiment.
- If it touches an adopted conclusion, the adoption is suspended and the K# goes to the user.

### The hidden-assumption audit

It applies to every **foundational result**, that is a statement on which a certification, an adoption or a
closure rests. The four verifications are distinct:

| | verification | who | what |
|---|---|---|---|
| V1 | the reread | a non-author role | the validity of the steps with respect to the declared premises |
| V2 | the hidden-assumption audit | a role involved neither in the construction nor in V1 (normally the inverter or a new instance of the debugger) | the unstated necessary conditions: versions, data representations, encodings, caches and state, call order, edges, empty domains, operational limits, differences between the theory and the behavior of the system |
| V3 | the counterexamples | a non-author adversary | minimal and limit cases, metamorphic and differential tests, with the predictions beforehand |
| V4 | the consolidation | the arbiter | the status, among five: unconditional proof; conditional proof, with the premises and the domain; experimental evidence, with the set examined; certified counterexample; open question |

Independence is per instance: a new instance of a role, which has not read the others' judgments, counts as
independent. A negative audit ("no hidden assumption found") is a procedural requirement, not a guarantee.

### The dossier

Every H# has a stable ID (H-001) and a dossier based on the `HYPOTHESIS_CARD.md` template, which the arbiter completes with the verdict,
field by field, with references to the branch's files. An empty field is written "missing".

## The full strategy in detail

- **The waves.** At most five agents at a time, core by core, in this order:
  1. the critical core (without the arbiter);
  2. the profile's cores;
  3. the others.

  Each agent sees only its own brief.
- **The brief** is the same for all, only the role changes: the contract, the request, and "from your point of view:
  at most three observations or proposals, each with its evidence or its falsifier; if your field is not concerned,
  "not relevant" and why, in one line".
- **The arbiter's consolidation** is done per core and then overall. It contains:
  - the facts with their status;
  - the contradictions;
  - the candidate ideas with their origin (role and file);
  - the open questions;
  - the roles to call in the following phases.
- **The graft.** The candidate ideas become input cards for f2, and their authors sign them as in the classic.
  The translator must be a role with no ideas among the candidates: normally a new instance of the logician.
- **The costs.** A full costs as much as a v1 round plus a classic. That is why "auto" chooses it only in the cases
  written above.

## Resources

- **The quota.** The contract sets the number of agents and the time, and splits them into three thirds:
  1. the phases up to f3;
  2. verdict and answer;
  3. a reserve for retries and stopped agents.

  Once the first third is spent, you move to the verdict with what there is.
- **The reference maximum times:** single 15 minutes, classic 60, full 120 (eleven waves, then the classic).
  The contract sets them, and the user can stop at any moment.
- **The agents** are at most five at a time. A stopped agent is relaunched with only its brief and its
  `status.md`; after two stops its brief is "not delivered".
- **Heavy processes** run one at a time per agent, with `timeout`. GPUs and paid services only with the
  user's yes.

## How it runs in different environments

- **In a project, with files.** The coordinator is the Claude Code session opened at the root of the project, and
  the agents are its `swarmer-<id>` subagents.
  - The convening lives in `.swarmer/<YYYYMMDD-HHMM>-<name>/` inside the project.
  - `swarmer/convene.py` prepares the skeleton and checks the gates.
  - The complete documents are in `swarmer/`.
- **Without a shell or without writes.** The phases are the same. The briefs live in the prompts, the agents' answers
  are the deliverables, and the coordinator checks the gates with the conditions written above.
- **With a model reached through an API,** which does not launch agents: a program of your own acts as the coordinator, one call
  per role, with the texts of `swarmer/catalog.json` (`COORDINATOR_INSTRUCTIONS.md` says which calls). Phases f3 and
  f4 are condensed: no executions, only critiques and verifications by reasoning.
- **Isolation.** The agents work with the permissions of the session that launches them. Where a task runs untrusted
  code, installs packages or touches a device, the session must be opened in an isolated environment (a container,
  a disposable machine): the swarm does not do this by itself.

## Dossiers and briefs

- Briefs do not say "examine the project". They give:
  - the inputs, with the absolute path or the text;
  - the output file;
  - the minimal test, the threshold and the time;
  - the maximum test class;
  - the prohibitions and the recipient.
- Provisional IDs carry the role's prefix (`creativo-2`); the final H#, F# and K# are assigned by the arbiter.
- The answer to the user begins with a line "Swarm: <strategy>. Roles: <roles>.". Then comes the result, with
  the status of what it claims, the open items and at most three decisions that are theirs to make.

## What changes

**Compared with 4.0.**
- **The name** is swarmer: the script is `swarmer.sh` (`sciame.sh` stays as an alias), the code is in `engine/`, the
  documents in `docs/<language>/`, the database in `db/professionals.json` (format 2; format 1 is still read).
- **Two full languages.** Every command, option and value has an English and an Italian name, and both work in every
  installation; abbreviated options are no longer accepted. English is the default; in an Italian installation
  everything written into the project is Italian (`sciame/`, `.sciame/`, `sciame-<id>`, `MANIFESTO.json`,
  `giuria.json`).
- **The protocol lines** are read in both languages (`JURY.md`, §11); juries already voted are recounted identical.
- **The profiles** have English ids (`code`, `defect`, …); the Italian names are accepted as aliases.

**Compared with 3.1.**
- **Professionals and sub-professionals** in a single database (`db/professionisti.json` in 4.0), in the languages of the skill;
  `AGENTS.md` is generated from it.
- **Four new strategies:** fan-out, jury, plenary, new expert; the full remains the exploration without a
  vote and becomes level 1 of the plenary.
- **The common brief** for all strategies, with the done criterion, the write scope and the forbidden scope, the
  verification and the three outcome words.
- **The languages:** Italian and English, chosen with `bash swarmer/swarmer.sh language <code>` or at installation; other
  languages are added with a proposal to the repository.
- **The overlay installation** in a project that already has its own swarm: it does not touch its files and its agents.
- **The environment** (`ENVIRONMENT.md`): what to do when an environment lacks subagents, the shell or writes.

**Compared with 3.0.**
- **It is portable.** Everything lives in the project's `swarmer/` folder. The agents and the skills are generated in `.claude/`.
- **The perception core.** Eleven roles and seven profiles: `perception`, `motion`, `estimation`, `tracking`,
  `localization`, `sensors`, `latency`.
- **`convene.py`.** The `roles` command and the `--owner` option of `select`.

**Compared with v2.** Project-specific content has been removed: in its place are the principles that the contract
of every convening declares. The gates G0–G5, the blind lanes with the canaries, the seals and selection
only from the triage remain.
