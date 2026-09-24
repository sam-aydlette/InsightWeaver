# The brief: what moved, what is due, what is watched, what went quiet, every line citing the observations it rests on, deterministic to the byte.
REPO: InsightWeaver
STATUS: DONE              # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
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

## Done (2026-09-22 and 2026-09-23)

`src/brief/` (`sections.py`, `select.py`, `render.py`), `src/cli/brief.py`, `src/cli/run.py`, the
`briefs` table in the monitor migration, and the golden end-to-end test in `tests/brief/`
(recorded Federal Register week, a two-item feed that reprints one notice, an empty feed, an
unreachable feed, a scripted model client, a frozen clock). `make golden` rewrites the golden
files; read the diff before committing it.

### Decisions taken here, for the reader to overturn

- **DUE looks 30 days ahead** (`HORIZON_DAYS`). Neither this file nor `docs/PLAN.md` gives a
  number; "the window ahead" could also be read as the brief's own window mirrored forward. The
  constant is the one assumption in the brief and is marked as such in the code.
- **A Position that cannot be read does not stop the brief.** The header prints every problem
  the loader found, DUE says its decisions are missing, the review banner is up, and the exit
  code is 0, so `run` continues to the brief and records it. The alternative, refusing to render,
  would hide the watches' state behind the config error. Reversible in `src/cli/brief.py`.
- **`run` does not include `watch sync`.** The plan names four steps. Syncing is an edit to the
  private files followed by one command, not a morning step.
- **Staleness is tested on when routing last linked something** (`routes.routed_at`), not on the
  item's publication date, and that is the date QUIET prints after "nothing routed since". A
  backfilled document published three weeks ago and routed yesterday is not silence.
- **MOVED shows every watch with evidence in the window, live or not**, labelled `[expired ...,
  unresolved]`, `[resolved yes]` or `[retired]`. The plan's wording has no liveness qualifier and
  grading an expired watch needs the evidence that arrived.
- **The header prints the last attempt, labelled.** `rss_feeds.last_fetched` is stamped by every
  attempt, success or failure, and the row keeps no separate time of the last success, so the
  line reads `fetched <stamp>` or `LAST ATTEMPT FAILED <stamp>: <error>`, never a failure as a
  fetch. "Last successful fetch" in this file's acceptance is met only when the last attempt
  succeeded; keeping the last success through a failure needs a column, deferred.

### Review (2026-09-23): five lenses, every finding tried by two refuters

Twenty-five findings survived both refuters; three were refuted as the specified behaviour
(the default window's UTC day boundary, the collapsed "went silent" line, failed adjudications
leaving QUIET after the window). What changed:

- **QUIET tested staleness on the observation's date**, so a watch routed yesterday read as
  silent or never routed. Now `routes.routed_at`, bounded by `as_of`.
- **Evidence for a watch that expired or was resolved inside the window was cited nowhere.**
  MOVED now shows it with the watch's state.
- **A failed fetch printed as a fetch.** Labelled as above; `store.record_attempt` is the one
  stamp for the three writers (items stored, nothing returned, failure).
- **An observation judged under two prompt versions counted as its own near-duplicate.** The
  count is over distinct observations.
- **Routed pairs no adjudication had answered were invisible**, byte-identical to pairs judged
  not evidence. QUIET prints them, per watch, under any prompt version.
- **A 200 carrying a landing page, a challenge page or JSON was a clean empty fetch** and, with
  the new stamp, would have cleared the source's error and listed it as quiet. `RSSAdapter`
  raises when feedparser recognises no feed at all.
- **WATCHING's belief ignored `--as-of`**; `current_beliefs` takes `as_of`.
- **A brief whose `--output` could not be written was recorded as delivered.** Delivery now
  precedes the row, and the write error is a message.
- **Only the first line of a Position error reached the header.** The whole message does, and
  DUE and the banner say so as well.
- **Tests that could not fail**: MOVED order satisfied by hash alone, the 90-day banner unpinned
  between 50 and 261 days, DUE and WATCHING order equal to insertion order, the empty-fetch
  runner test unable to see its own stamp. Each now has rows inserted out of order and a case on
  each side of the boundary.
- Sources going silent are marked "HAS PRODUCED BEFORE; check the source" versus "never
  produced", the distinction the runner keeps and the brief had dropped.
- `docs/PLAN.md` gained `--dry-run` and `sections.py`; the pinned command and table sets in
  `tests/cli/test_app.py` and `tests/database/test_models.py` name `brief` and `briefs`.

Recorded, not changed: `src/sources/runner.py` and its test were over 300 lines before this
task and gained a few lines each; the stamp helper moved to `store.py` to keep it from growing
further. The row cannot hold the last success once a failure overwrote it (above).

## Addendum (2026-09-24): the header's default became compact

After a first real run against 72 configured sources, the operator asked for the per-source
header to be shorter by default -- 72 lines of mostly-successful status was burying the four
sections worth reading daily. The fix keeps the LANDMINES rule intact rather than relaxing it:
**a source whose last attempt failed is still named in full, every time, with no flag needed**;
only a source that *answered* (whatever it returned) is folded into a summary count. `--verbose`
restores the original always-list-everything behaviour. `src/brief/render.py`'s module
docstring and `src/cli/brief.py`'s carry the detail; the golden files were regenerated and the
README's embedded excerpt resynced.
