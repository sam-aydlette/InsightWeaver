# Let a beat declare standing questions up front, so the brief answers a persistent intelligence agenda instead of only reporting what the coverage happened to raise.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
ACCEPTANCE: `make check` passes, plus: a beat's `standing_questions` are seeded into the `questions` graph on first run and bound to that beat; each run reports **movement against each standing question** — what changed, what did not, and explicitly that nothing did when nothing did; a standing question with no coverage this run still appears, marked as unmoved, rather than silently vanishing; emergent questions from coverage continue to be created exactly as today; and tests cover seeding, binding coverage to a standing question, and the no-movement path.
OUT OF SCOPE: Answering the questions, scoring them, or attaching confidence to them. Auto-generating standing questions from coverage — they are declared by the human, deliberately. Retiring or closing standing questions automatically. Changing how emergent Questions work. Predictions, which already key off Questions and need no change here. Any judgement about whether a standing question is well-posed.
LANDMINES: **A standing question that silently disappears on a quiet day is the failure mode this whole feature exists to prevent** — the point of a persistent agenda is that "no movement on CMMC Phase 2 this week" is itself information, and the most likely bug is that quiet questions get filtered out as empty sections. Test that path first. Questions today are emergent from coverage and matched by similarity in the question-matching pass; seeded questions enter that same matcher and may get spuriously bound to unrelated coverage, so the binding threshold needs to be tighter for declared questions than for emergent ones. If beat scoping from task 004 was left implicit, standing questions will collide with the personal brief's Question graph and corrupt appearance counts — check that before starting. Sequenced last on purpose: it needs several runs of real coverage to tune the binding against, so do not attempt it before 005 is delivering content. Local `main` is 11 commits ahead of `origin`; do not push.
---
Step 5 of five, and the one that makes this a brief rather than a digest.

A President's Daily Brief is not a summary of events — it is a delta against a standing
intelligence agenda. InsightWeaver already has the machinery: `docs/CONCEPTS.md` describes the
graph accumulating and the brief being "the diff view onto it." What is missing is that today the
agenda is *emergent* — the graph notices what coverage leaves unresolved. A beat should be able
to *declare* what it is watching, whether or not this week's coverage mentions it.

Examples for the compliance beat, to make the shape concrete:

- Does CMMC Phase 2 slip past its statutory date?
- Which CSPs move to FedRAMP authorized, and at which impact level?
- Does any CISA BOD create a compliance obligation with a deadline inside 90 days?
- Where do GovRAMP and TX-RAMP diverge from FedRAMP in ways that matter to a multi-state CSP?

The right output is closer to an analyst's standing-agenda review than a news roundup: each
question, what moved, what did not, and what would have to be observed next to change the picture.
