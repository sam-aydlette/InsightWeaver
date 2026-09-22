# Ingest every configured source through the adapter path, then route observations to watches with compiled deterministic predicates.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: medium
PLAN: docs/PLAN.md (section 4; section 5, task 028; supersedes backlog/015 as rescoped)
ACCEPTANCE: `make check` passes, plus: `insightweaver ingest` builds an adapter for **every** feed in `config/feeds/` (RSS through `RSSAdapter`, others through `ADAPTER_FACTORIES`), runs them with bounded concurrency, stores through the one adapter store path, and prints per source fetched / inserted / unreachable / went-silent, with the `SOURCE ALERT` lines the runner already produces; a `routes` table links `(observation, watch)` with the index of the first trigger clause that fired, unique per pair, so routing twice produces one link; every clause compiles through `entity_matcher.term_pattern` with its shouted-term case rule and word boundaries, `entities` compiling exactly as `terms` do, `sources` matching the source name case-insensitively, every populated field in a clause required and any clause sufficient; `insightweaver route --dry-run` reports per watch how many observations in the window would route and reports the **unrouted count grouped by near-duplicate cluster and by source**, writing nothing; **no LLM call anywhere in this tier**, proved by a test that removes `src.llm` from `sys.modules` and blocks its import while driving the full routing path; and a regression test plants twenty whole-word trigger matches and one hundred substring look-alikes in a thousand synthetic observations against five watches and asserts exactly twenty route -- a test whose docstring records that it was verified to fail with `LEFT_BOUNDARY` and `RIGHT_BOUNDARY` stripped.
OUT OF SCOPE: Adjudication (task 029). Belief, retirement, resolution (task 030) -- until then a live watch is one whose `expires` is not past. The brief (task 031). An alias registry for entities; an entity compiles as a term until a watch needs aliases, and that is its own task. Tuning any configured feed. Numeric or `series` trigger clauses. Deleting `run_configured_adapters` or `build_configured_adapters`; they gain an `include_rss` switch and keep their callers.
LANDMINES: **A routing predicate that is too loose does not fail, it bills** -- every routed pair is a model call in task 029. The planted-substring test is the gate, and it must be verified by deleting the boundary anchors and watching it fail, because task 010 found a boundary test that passed for the wrong reason: shouted terms were rejected by case-sensitivity before the anchors were consulted. Plant lower-case look-alikes for shouted terms too (`precisa` for `CISA` proves nothing; `Cisa` inside `Cisak` does). **Concurrency and SQLite.** Five adapters awaiting network at once is fine; five sessions writing at once is not what happens, because each `run_adapter` does its database work synchronously between awaits, so writes never interleave mid-transaction. Do not introduce threads. **The unrouted report is the coverage-gap signal.** A bare integer is useless; cluster it with the stored MinHash signatures and name the source, or task 032's onboarding cannot tell "no source covers this" from "the trigger is wrong". **`published_date` can be null** (feeds without dates); the window falls back to `observed_at` for those rows rather than dropping them. `main` is protected -- open a PR.
---
Written 2026-09-22.

## Why ingest is here and not its own task

Task 025 closed the legacy write path and task 012 deleted the orchestrator that called it, so the
repository has had no way to grow its corpus since 2026-08-31. Routing over an empty corpus proves
nothing. The two land together so the tier can be exercised end to end on a real feed the same day.

Every feed in `config/feeds/` is ingested. The profile-driven selection that used to pick a subset
went with the profile; curation is now editing that directory, which is what `SOURCES.md` already
says it is. `store.py::ensure_source` registers the source row the first time an adapter runs, so
the "adding a feed to config does not add it to the database" trap recorded in tasks 020 and 025
closes by construction.

## Clause semantics, restated so the compiler and the file agree

A watch's `triggers` is a list of clauses. A clause may populate `terms`, `entities`, `sources`.
Within a clause, **every** populated field must match; within a field, **any** value matches. Any
clause matching routes the observation. The clause index stored is the first that matched. The text
matched is the observation payload's title followed by its `normalized_content`, or its
`description` when there is no content -- the same text `ObservationView.text` exposes to the
adjudicator, so Tier 1 and Tier 2 read the same words.
