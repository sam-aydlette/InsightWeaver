# Deliver Alerts by email, one per firing batch, each naming the decision it bears on.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: medium
ACCEPTANCE: `make check` passes, plus: **only an Alert can cause mail to be sent**, enforced by a single send function that takes an Alert and by a test asserting no other module can reach the transport; Alerts are grouped by watch into one email per firing batch; the body states what changed, what it does to the named decision, **what would have to be true for this to be wrong**, and a link to resolve or adjust the watch; SES domain verification, DKIM, and a custom MAIL FROM are configured and verified against live AWS, with the verification output in the PR rather than asserted; a dry-run mode renders the exact body without sending; and a send failure is loud and lands in the DLQ from task 018, never swallowed.
OUT OF SCOPE: HTML templating beyond what is needed for a readable message; this is not a newsletter. Unsubscribe or preference management at one-user scale. Retry policy beyond DLQ. Alert silencing. Any content the model authors beyond what Tier 2 already produced -- the body is assembled deterministically from Alert fields, with no LLM call.
LANDMINES: **The repository already contains a live `smtplib` send path** at `src/render/email.py:124`, reachable from `brief --format email`. Task 012 deletes it; if 012 has not landed, this task inherits an existing invariant-1 violation and must not add a second transport beside it. **"What would have to be true for this to be wrong" is the field that makes the email worth reading**, and it is the one most likely to degrade into boilerplate. It must come from the Watch's own trigger conditions -- what would move the belief the other way -- not from a template sentence. If it cannot be derived from Watch state, say so rather than shipping a constant string. **SES has a sandbox.** A new SES identity can only send to verified addresses until production access is granted, which is a support request with a turnaround -- start it early or v0 delivery blocks on it. `main` is protected -- open a PR.
---
Written 2026-08-31.

Invariant 1 is the narrowest invariant in the brief and the easiest to satisfy structurally: one
function, one caller, one test asserting nothing else reaches the transport. Doing it any other way
-- a notification service, a mailer class with several entry points -- reintroduces the question
this invariant exists to close.

**On the "what would have to be true for this to be wrong" field.** This is the epistemic
discipline from the old product's `ANALYSIS_RULES.md` surviving into the new one in a much smaller
form. In the briefing generator it was a labelling rule applied to prose. Here it is a field
derived from the watch's own triggers, which makes it checkable rather than stylistic.
