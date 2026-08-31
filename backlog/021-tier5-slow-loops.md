# Weekly slow loops: resolve due watches, score calibration and source contribution, propose candidate watches for human acceptance.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: medium
ACCEPTANCE: `make check` passes, plus: watches past `expires` surface for resolution with a score attached, and resolution is a **human action** with no auto-resolve path; Brier score is computed by domain over resolved watches and appears in the weekly receipt; source contribution is scored along the chain routed -> adjudicated as evidence -> contributed to a resolved watch, so a source that routes heavily and never contributes is visible; unrouted observation clusters from task 015 are surfaced as **candidate** watches that a human accepts or rejects, and **no code path creates a Watch from a candidate without an explicit human accept**; and a test asserts that accepting a candidate requires a distinct operator action and that rejection is recorded rather than discarded.
OUT OF SCOPE: Auto-accepting candidates under any confidence threshold -- invariant 6, and a threshold is just a slower path to the same place. Auto-resolving a watch from coverage. Scoring models beyond Brier until there is enough resolved data to justify one. Retiring sources automatically on low contribution; surface it and let the human cut.
LANDMINES: **Invariant 6 is enforced here or nowhere.** The candidate-proposal feature is the exact seam through which auto-authored watches arrive, and it will arrive as a convenience -- an accept-all flag, a confidence threshold, a "just create the obvious ones" shortcut. The acceptance criterion is written as "no code path creates a Watch without an explicit human accept" rather than "candidates require approval" for that reason. **Calibration needs resolved watches and there will be almost none for months.** A Brier score over two resolutions is noise presented as measurement; the receipt must state the denominator and suppress the figure below a stated minimum rather than printing a number that looks authoritative. The repository has a standing example of the failure this avoids: 33 predictions, zero graded, and a `track-record` command that would have happily printed a rate. `main` is protected -- open a PR.
---
Written 2026-08-31. Not required for v0; the weekly receipt shell from task 018 is.

**Why source contribution is scored along a chain rather than by volume.** A source that routes
into many watches and never produces evidence that contributes to a resolution is expensive and
useless, and it looks identical to a valuable source on any volume metric. The audit found the
repository has already made this mistake in the other direction: task 005 reported "469 documents
narrowed to 24" as evidence the beat covered its domain, and the beat then missed the largest event
in that domain because document volume was never the thing to measure.
