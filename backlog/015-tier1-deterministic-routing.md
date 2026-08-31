# Route Observations to Watches with compiled deterministic predicates, so the model never sees the bulk of the corpus.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: medium
ACCEPTANCE: `make check` passes, plus: each Watch's triggers compile to a deterministic predicate over entities, terms and source allowlists, with **no LLM call anywhere in this tier** -- proved by a test that removes the Anthropic client and drives the full routing path; word-boundary matching is used throughout and reuses `src/context/entity_matcher.py`'s primitives rather than a second implementation; `insightweaver route --dry-run` reports, per watch, how many of the last N observations would route, and reports the **unrouted count and its clusters**; routing is idempotent -- the same observation routed twice produces one link; a test asserts that a corpus of 1,000 observations against 5 watches routes fewer than a stated ceiling, so a regression that widens routing fails rather than merely costing money; and the unrouted cluster output is written somewhere task 021 can consume it.
OUT OF SCOPE: Adjudication -- routing decides *candidacy*, not whether something is evidence. Any change to what the adjudication prompt says. Proposing watches from unrouted clusters; that is task 021, and this task only has to make the signal available. Tuning the shipped watches' triggers. Belief updates or state transitions.
LANDMINES: **This tier is the cost control, and a routing predicate that is too loose does not fail -- it bills.** The ceiling test exists because "most observations match nothing and die here" is an architectural claim that needs a number attached or it decays silently. **Word boundaries are load-bearing and the repository has already been bitten**: of 55,249 articles, 5,364 contain the substring `nist` and 73 match it at a word boundary; `mail` is 1,842 versus 339. Task 010 also found that a boundary test can pass for the wrong reason -- its shouted-term cases were rejected by case-sensitivity before the anchors were consulted, so the class passed with anchoring deleted from the codebase. Any boundary test written here must be verified by stripping `LEFT_BOUNDARY`/`RIGHT_BOUNDARY` and confirming it fails. **The unrouted count is the coverage-gap signal and is the only place a missing sensor becomes visible before a staleness alert fires**; logging it as a bare integer with no clustering makes it useless. `main` is protected -- open a PR.
---
Written 2026-08-31.

Tier 1 is where the rewrite's central property -- notification volume scaling with live watches
rather than news volume -- is actually enforced. Tiers 2 through 4 can only preserve it.

**Why a ceiling test rather than a dashboard.** An architectural property that is only observable
in production metrics is one that regresses between releases and is noticed at the invoice. A test
asserting that N observations against M watches routes fewer than K makes the property a gate.
Pick K from a measured baseline, not from intuition, and record how it was measured.
