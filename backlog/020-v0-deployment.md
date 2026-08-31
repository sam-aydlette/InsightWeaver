# Deploy v0: one scheduled Lambda, SQLite in S3, five watches, two adapters, SES delivery.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: large
BLOCKED-ON: the persistence decision in backlog/022-open-questions.md
ACCEPTANCE: `make check` passes, plus: one Lambda runs the full pipeline on an EventBridge daily schedule; persistence is whatever the operator chose (see BLOCKED-ON) and the choice is recorded in the PR with its cost; **five hand-authored watches** drawn from decisions falling inside 90 days are live; two adapters run -- Federal Register API and one existing RSS set; secrets are in SSM Parameter Store, never in the image or environment; the dead-man's switch from task 018 is live and its non-SES channel verified by **deliberately breaking the mail path and confirming the alarm arrives**; and after three weeks of operation the PR is updated with the observed email count against the acceptance bar of **fewer than two per week, every one naming a decision**.
OUT OF SCOPE: Multi-tier Lambda decomposition, SQS between tiers, or per-tier DLQs -- v0 is one Lambda, and the tier boundaries are enforced in code rather than infrastructure until volume justifies otherwise. Bedrock migration or batch mode. IaC beyond what one Lambda and a schedule require. Any sixth watch. Any third adapter.
LANDMINES: **The acceptance bar is a measurement over three weeks of real operation, not a property of the code**, so this task cannot be marked DONE at merge -- it opens, ships, and is updated with the observed number. If v0 emits more than two emails a week the fix is watch tightening or hysteresis, **not features**; if it emits nothing for three weeks *and* staleness alerts are also quiet, the sources do not cover the stakes and adapter work is the real project. Say which of the three outcomes occurred rather than declaring success. **SES production access is a support request with a turnaround** -- see task 019. **The audit found that adding a feed to `config/feeds/` does not add it to the database**: `FeedManager.load_feeds_to_database()` syncs config into `rss_feeds` and the fetcher reads the table, so a deployment that ships config without running the sync fetches nothing while every test passes. That exact failure happened on 2026-08-28. `main` is protected -- open a PR.
---
Written 2026-08-31.

v0 exists to answer one question: does notification volume track live watches rather than news
volume? Everything in the acceptance is instrumentation for that question, and the three-week
observation window is not padding -- it is the measurement.

**Why one Lambda rather than the tier-per-Lambda target shape.** The tier boundaries are semantic
and are already enforced by tasks 015 through 019 in code. Splitting them across Lambdas with SQS
between adds five failure surfaces and a distributed-debugging problem in exchange for scaling
headroom that one user does not need. Take the decomposition when a tier's runtime or failure
profile demands it, and let the DLQ requirement in task 018 be satisfied by the single queue until
then.

**The three outcomes, stated in advance so the result cannot be reinterpreted afterwards:**

| observed | means | do |
|---|---|---|
| fewer than 2/week, each naming a decision | the property holds | stop; run it |
| more than that | watches too loose or hysteresis too weak | tighten, do not add features |
| nothing for 3 weeks, staleness also quiet | sources do not cover the stakes | adapter work is the real project |
