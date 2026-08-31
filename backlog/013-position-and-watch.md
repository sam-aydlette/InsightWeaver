# Introduce Position and Watch as the system's atomic units, with so_what enforced in the schema.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: medium
ACCEPTANCE: `make check` passes, plus: `position.yaml` is loaded from git, hand-authored, and validated -- decisions carry a deadline, and a Position over two pages **warns loudly rather than failing**, naming the drift from stakes into interests; a `watches` table and loader exist carrying `id`, `claim`, `belief`, `so_what`, `triggers`, `expires`, `staleness_alert_days`; **a Watch with an empty, whitespace-only, or absent `so_what` is rejected at load with a clear error and is not stored**, with a test that bites; a Watch whose `so_what` names no decision present in the Position is rejected the same way; `belief` outside 0.0-1.0, an `expires` in the past, and a `staleness_alert_days` under 1 are each rejected; `insightweaver watch list` shows each watch, its belief, its decision, and days to expiry; and no command can create a Watch except from the checked-in files.
OUT OF SCOPE: Routing, adjudication, state transitions, alerts, or notification -- this task defines the units and nothing that acts on them. Migrating existing Questions, Predictions, Decisions or Beats onto the new model; that is task 014's decision to make once Observations exist. Any LLM call. Proposing candidate watches. A web or TUI editor for `position.yaml` -- it is human-edited in git, deliberately.
LANDMINES: **The system never authors its own watches (invariant 6), so every write path here must be closed, not merely unused.** A `watch add` CLI command would satisfy no acceptance criterion and would be the seam through which auto-generation later arrives; do not build one. **`so_what` enforcement must reject rather than default.** Task 011 established this pattern for a different field and its landmine applies verbatim: the ledger accumulated 25 unfalsifiable predictions precisely because a missing field was tolerated. **The existing schema already contains most of this and it is empty.** `decision_factors` has columns `name`, `what_would_update_me`, `current_state_note` -- which is a trigger, a belief state, and a decision link under different names -- and `decisions` and `decision_evidence` both hold **0 rows** as of 2026-08-31. Read `docs/CONCEPTS.md` § "Decisions, Factors, and Evidence" before designing a new table; if Watch is better expressed as an evolution of Decision+Factor than as a parallel structure, say so in the PR rather than building both. `main` is protected -- open a PR.
---
Written 2026-08-31.

## The finding the implementer needs before touching the schema

The brief describes Watch as a new atomic unit. The audit found the repository already models
something very close, and never populated it:

| brief's concept | existing column | rows |
|---|---|---|
| `so_what` naming a decision | `decision_evidence.decision_id` -> `decisions.name` | 0 |
| trigger | `decision_factors.what_would_update_me` | 0 |
| belief state | `decision_factors.current_state_note` | 0 |
| evidence direction | `decision_evidence.direction` | 0 |
| trigger predicate | `predictions.trigger_condition` | 33 rows, 25 unfalsifiable |

That is not an argument for reusing the tables as they stand -- `current_state_note` is prose where
`belief` is a float, and the 33 predictions demonstrate what happens when a trigger field accepts
prose. It **is** an argument that the implementer should decide deliberately between evolving
Decision+Factor and creating Watch alongside it, and record the reasoning. Two overlapping models
for the same idea is the outcome to avoid; the repository already has that problem between
`README.md` and `CLAUDE.md` and this task should not add a third instance of it.

## Why the Position size check warns rather than fails

The brief says a Position over two pages "has drifted into describing interests rather than stakes;
flag that, do not silently accept it." A hard length limit would be enforcing a proxy: a
three-page Position full of genuine deadlines is better than a one-page Position of vague
interests. The check names the drift and lets the human judge, which is the same reason
`coverage_probes` reports INCONCLUSIVE rather than dropping a probe.
