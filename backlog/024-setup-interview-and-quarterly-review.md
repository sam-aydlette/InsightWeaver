# An interview that drafts Position, and a quarterly review loop that degrades visibly when it lapses -- the outermost loop, which sets the thresholds every inner loop steers against.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: medium
ACCEPTANCE: `make check` passes, plus: `insightweaver setup` runs a question-and-answer interview that **writes a draft `position.yaml` to a scratch path and prints it for the operator to edit and commit** -- it never writes to the live Position and never creates a Watch, so invariant 6 holds; the interview elicits decisions with deadlines, refuses to record a decision with no date, and asks for each what evidence would change it; `insightweaver review` opens the quarterly loop, showing each decision, whether it is still live, each watch derived from it with its belief history since last review, and every watch that expired or went stale in the period; completing a review stamps `position.reviewed` and **records what changed, including "nothing"**; the weekly receipt shows days since last review; past 90 days every alert email and every feed card carries a visible staleness banner naming the review date; and a test drives a review with no changes and asserts it still stamps and still records.
OUT OF SCOPE: The interview authoring watches, ranking decisions, or suggesting beliefs. It elicits and transcribes; the operator decides. Suppressing alerts when review lapses -- see the reasoning below. Auto-extending expiry dates. Any calendar integration, reminder service, or notification outside the receipt and the banner. Auto-retiring a decision because its deadline passed; surface it in the review and let the human close it.
LANDMINES: **The interview is the seam through which the system starts authoring its own watches.** It will arrive as convenience -- "it already knows the decision, why not draft the watch too". Invariant 6 exists because auto-generated watches are the path back to a firehose with extra steps, and a drafting interview is one commit from being a generator. The acceptance says it writes a draft Position to a **scratch path**, not the live file, for that reason. **A review that can be completed by pressing return teaches nothing**; requiring a recorded outcome, including an explicit "nothing changed", is what makes the loop a loop rather than a checkbox. **Do not make review a hard gate on alerting.** See below -- it is the one place in this plan where "mandatory" is the wrong mechanism. `main` is protected -- open a PR.
---
Written 2026-08-31, answering the setup-and-maintenance question directly.

## Why this is the outermost loop, not just a chore

The system now runs several loops at different periods. Listed by speed:

| loop | period | corrects |
|---|---|---|
| ingest -> alert | daily | did anything change |
| watch cadence | 7d - 1y, per watch | is this still worth watching at this rate |
| weekly receipt | 7d | is the system alive |
| resolution | at expiry | was I right |
| **Position review** | **90d** | **are these still my stakes** |

The quarterly loop is outermost, and it is the only one that corrects the *inputs* to all the
others. Every inner loop steers against thresholds this one sets. If it stops, nothing breaks --
the daily loop keeps running, alerts keep firing, the receipt keeps arriving. They just gradually
stop being about anything that matters, and **nothing in the system can detect that from inside**.
That is precisely why it needs a mechanism rather than an intention.

## Why review is not a hard gate on alerting

The instinct is to make it mandatory by suppressing alerts when review lapses. That is wrong here,
and the reasoning is the same one that governs the rest of this architecture.

The cost of a stale Position is a **wrongly-prioritised** alert -- a watch serving a decision
already made. The cost of suppression is a **missed** alert. Those are not symmetric, and a system
that goes silent because you were busy for a quarter is a system that punishes you at the moment
you have least attention to spare. Worse, it reintroduces the ambiguity invariant 5 exists to
remove: suppressed-for-staleness looks exactly like nothing-happened.

So the mechanism is **visible degradation, not suppression**: the receipt leads with the review
date, and past 90 days every alert and every feed card is banded with it. The alert still arrives.
You just cannot read one without being told the frame it was judged against is out of date.

## What the interview is and is not

It is a **transcription aid for a hard authoring task**, which is the actual barrier to this system
existing. Writing `position.yaml` from a blank file is the kind of task that does not get done, and
five watches with real deadlines is a real morning's work.

It is not a drafting assistant with opinions. It asks:

- What decisions are you carrying that have a date on them?
- What is the date, and what happens if you get it wrong?
- What would change your mind?
- Where would you find out?

Then it writes what you said into the schema, to a scratch path, for you to edit and commit. The
last question is the one that most often reveals there is no sensor -- which is a finding worth
having before the watch is registered rather than 45 days later when its staleness alert fires.
