# Let the operator stake and resolve their own falsifiable predictions, so the track record measures the person rather than the model.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
ACCEPTANCE: `make check` passes, plus: four new write commands -- `questions add`, `predict`, `resolve`, and `forecast --due` -- let a human declare a question, stake a claim against it with a **required** resolution date and a confidence, see what has come due, and record an outcome with a note; a prediction with no date is **rejected at entry**, not stored; predictions carry an author (`operator` | `model`) and `predictions track-record` counts **operator predictions only**, with model predictions reported separately and never mixed into the calibration figure; every command works with no `ANTHROPIC_API_KEY` and makes no network call; and tests cover the date requirement, the author split in track-record, resolving a prediction that is not yet due, and resolving one twice.
OUT OF SCOPE: Changing how the model generates predictions, or the synthesis prompts -- the model's predictions stay exactly as they are and simply stop counting toward calibration. Scoring, weighting, or Brier-style aggregate math beyond a plain hit rate; that is a later decision once there is real data. Auto-resolving a prediction from coverage -- the human resolves, deliberately, because a tool that grades its own operator's calls is not a calibration instrument. Reminders, notifications, email, or scheduling. Editing or deleting a resolved prediction. Any change to beats, sources, adapters, entity matching, or the standing agenda.
LANDMINES: **The reason the ledger is empty today is not that nobody ran a resolver.** Of 33 model-generated predictions, 25 are phrased "X would signal Y" -- interpretation rules, which cannot be wrong -- and only 3 contain a date. 19 expired ungraded because there was nothing gradeable in them. If `predict` accepts a claim with no date or no observable outcome, this task rebuilds that failure with a nicer interface, which is why the date is a hard reject rather than a default. Do not add a confidence *default*: a stake with an unstated confidence is the same non-commitment in a different costume. `resolve` must record the resolution date separately from the due date -- resolving three months late is itself calibration data. The existing `predictions` table has `observable_text`, `trigger_condition`, `status`, `resolved_at`, `resolution_note`: extend it, do not build a parallel table. `main` is protected (5 required checks, `enforce_admins: true`) -- open a PR, do not push to it.
---
Written 2026-08-27. Comes out of a direct question from the operator -- *what makes this better
than simply asking an LLM* -- and the measurement that followed.

## The finding that motivated it

| | |
|---|---|
| syntheses ever run | 2 |
| predictions made | 33 |
| **predictions ever graded** | **0** |
| expired without a verdict | 19 |
| contain a date | 3 |
| contain a number or threshold | 5 |
| phrased "X would signal Y" | **25** |

The best prediction the tool has produced in its life:

> *"If 2+ additional similar events occur within 6 months, this signals systematic soft power
> campaign rather than isolated cultural diplomacy"*

That is a reading instruction. It says how to interpret an event; it does not claim the event will
happen. **An interpretation rule cannot be wrong**, which is why nineteen of them aged out unjudged.

## What this changes

Every existing command is read-only: `questions list|show`, `predictions open|triggered|track-record`,
`forecast`. The model writes the graph and the human reads it. For a calibration instrument that is
backwards -- the thing being calibrated should be the operator's judgment, and the operator
currently has no way to stake anything.

```
questions add "Does CMMC Phase 2 slip past its statutory date?"
predict 23 "Yes -- slips" --by 2026-12-31 --confidence 0.7
forecast --due
resolve 41 --outcome no --note "DFARS class deviation published 2026-11-14"
```

The division of labor this settles:

- **The model** surfaces what changed against declared questions, and says so when nothing did.
- **The operator** makes the call.
- **The tool** remembers, and asks at the right time.

That last one is what asking a language model structurally cannot do -- not for lack of capability,
but because it holds no record of what you said three months ago and has no reason to raise it.

## Why the author split matters

A track record mixing model predictions with the operator's measures nothing. The model's stay in
the ledger as *prompts* -- suggestions about what is worth holding an opinion on -- and are reported
under their own heading. The calibration figure counts only claims a human staked.

## Why the human resolves

Auto-resolution from coverage is out of scope on purpose. A tool that grades its operator's calls
using the same corpus that produced them is measuring agreement with itself. The friction of
resolving by hand is the instrument, not an obstacle to it.

## Relationship to the weekly cadence

The intended loop is weekly: grade what came due, read the diff on standing questions, stake
anything new. **The brief is optional to that loop.** That is deliberate -- ingestion coverage is
the fragile half (see 009, 010), and the ledger should keep working on a week where the sources
returned nothing worth reading.
