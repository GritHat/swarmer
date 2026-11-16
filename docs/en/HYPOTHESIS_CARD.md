# Dossier of a hypothesis (the template: one is made for each H#)

`convene.py select` copies it into `f3/<H#>/<H#>.md`. The arbiter completes it with the verdict, field by field, with a
reference to the team's file that supports it. An empty field is written "missing", not omitted.

## Identity and contract

- ID: H-000
- Short title:
- Origin: role, lane or round, phase, file. If the same idea comes from several roles (identical statement and type), all
  the origins:
- Signature of each author ("faithful" or "lost: …"), with the file:
- Question of the contract and criterion that decides:
- Principles and constraints of the project that concern it:
- Provenance: versions, configurations, input data with the sha256; environment in which it is tested:

## The statement

- Type: solution, correction, decision, representation, procedure, explanation, text, other:
- Depends on (H#, F#, components):
- Invalidated if it changes:
- Claim in words:
- Precise statement, with the quantifiers and the domain:
- Necessary assumptions:
- Mechanism or solution (reference to the team's file):

## The evidence

- Baseline and oracle:
- Common modes: for each check, what it shares with the candidate (code, data, specification, author, model); the
  dissimilar check and its outcome:
- Registered prediction: measurement, threshold, domain, time, file; sha256 at gate G3, or seal before the test if it
  was born in f4:
- Premise of the prediction; if it has changed, "premise changed":
- Cheapest falsifier and outcome of the tournament; for a refutation, the check that does not share the prototype:
- Minimal counterexample or adversarial search:
- Results: command, file, fingerprints, counts, intervals:
- Anomalies and their causes (debugger), or "unexplained" with the discarded hypotheses:
- Costs: time, memory, money, people:
- Checks of the founding results: V1 rereading, V2 audit of hidden assumptions, V3 counterexamples, V4 consolidation
  (file and outcome of each):

## The verdict

- State per property, each with the domain and the file:

  | correctness | completeness | effectiveness | cost |
  |---|---|---|---|
  | | | | |

  States: proven (in the model …), verified (on a declared set, exhaustively), supported by data,
  refuted, unresolved (with the cause). Zero errors on a sample are not a universal proof.
- Adoptable? Yes only with correctness proven or verified on the domain of use, and no K# open on it.
  An acceptance by default is not "unresolved":
- Limits and possible confounders:
- Open K#:
- Next test that changes the decision (class and cost):
- Verified by: role, file of the test, what it shares with the candidate:
- Sentinel, if it checked this dossier: file and outcome:
- Verdict of the arbiter (file):
- Decision of the user and integration (by the coordinator):
