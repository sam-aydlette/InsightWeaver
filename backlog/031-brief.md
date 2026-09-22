# The brief: what moved, what is due, what is watched, what went quiet, every line citing the observations it rests on, deterministic to the byte.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: medium
PLAN: docs/PLAN.md (section 4; section 5, task 031; absorbs backlog/018 as rewritten)
ACCEPTANCE: `make check` passes, plus: `insightweaver brief [--since] [--as-of] [--format terminal|md] [--output PATH]` renders five parts in fixed order -- header, MOVED, DUE, WATCHING, QUIET -- and every evidence item prints its observation hash, source, published date, title, direction, magnitude and prompt version; evidence in MOVED is grouped by MinHash near-duplicate cluster so one story from twelve outlets is one item with twelve citations; QUIET names every live watch with nothing routed for its `staleness_alert_days` with the date of its last routed observation or "never routed", every source that ran in the window and returned nothing, and every failed adjudication, **and prints those headings with zeros when there is nothing**; the header states `as_of`, the window, the Position's `reviewed` date with days since and a banner past 90 days, and each source's last successful fetch; the rendered bytes are a pure function of the database, `--since` and `--as-of`, asserted by rendering twice; `--since` defaults to the `as_of` of the most recent brief delivered before the start of `as_of`'s day, else seven days, so a second run the same morning reproduces the first; a `briefs` row is written per render unless `--dry-run` is given; `insightweaver run` chains ingest, route, adjudicate and brief and stops at the first that fails; and an end-to-end test drives recorded RSS and Federal Register fixtures through ingest, route, a stub adjudicator and the brief, comparing against a committed golden file.
OUT OF SCOPE: Synthesis or any model call in the render path. Colour, boxes, or terminal width handling beyond plain text and markdown. Email, HTML, or any delivery. Calibration figures. Anything the brief would show that the data does not contain.
LANDMINES: **A brief that looks the same when nothing happened and when the pipeline is broken is the failure this whole design exists to prevent** (invariant 5). The header's source-by-source line and the QUIET section are the receipt task 018 specified; they are the parts most likely to be cut for tidiness and must not be. **Determinism is a test, not a hope**: no wall-clock reads inside rendering, no unordered iteration over dicts or query results, `as_of` passed in explicitly, and the golden file regenerated only by a deliberate command whose diff a reviewer reads. **The window rule is what makes `run` idempotent within a day**; without it a second run reports "nothing since ten minutes ago" and reads as a broken pipeline. **`published_date` may be null**; order by `(published_date or observed_at, hash)` so the order is total. `main` is protected -- open a PR.
---
Written 2026-09-22.

## What each section answers

| section | question | source of truth |
|---|---|---|
| header | did the machinery run, and against a current Position | `rss_feeds.last_fetched`, `last_error`, articles in window; `position.reviewed` |
| MOVED | which watches gained evidence, and what it was | `evidence` joined to `observations` in window, grouped by `near_duplicate_groups` |
| DUE | what has a date on it inside the horizon | Position decisions by `deadline`; watches by `expires` |
| WATCHING | what is being held, at what belief, with what recent support | live watches, latest `watch_beliefs`, evidence counts |
| QUIET | where silence might be breakage | `routes` recency per watch, sources with zero items, `adjudications.outcome = 'failed'` |

The three-week measurement the plan ends on is read off the header: moved items per brief, and
the resolved count. Task 034 is written from those numbers.
