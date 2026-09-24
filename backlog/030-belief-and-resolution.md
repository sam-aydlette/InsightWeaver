# One belief ledger the operator writes, resolution as a human action, and retirement instead of deletion.
REPO: InsightWeaver
STATUS: DONE              # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: small
PLAN: docs/PLAN.md (section 3; section 5, task 030; replaces backlog/017 and the resolution half of 021)
ACCEPTANCE: `make check` passes, plus: a `watch_beliefs` table is append-only, enforced by `BEFORE UPDATE` and `BEFORE DELETE` triggers and an ORM guard, tested from the ORM and from raw SQL; `sync_watches` writes a `source = 'file'` row when a watch is first stored or when its file belief differs from the latest ledger row, and **stops overwriting `watches.belief`**, which becomes the value at registration; `insightweaver watch believe ID P --note TEXT` writes a `source = 'principal'` row and refuses a belief outside [0, 1], a blank note, or an unknown, retired or resolved watch; `insightweaver watch resolve ID --outcome yes|no --note TEXT` sets `resolved_at`, `outcome` and `resolution_note` once and refuses a second resolution; `sync_watches` sets `retired_at` on a watch absent from the file **instead of deleting the row**, clears it if the id returns, and reports both; routing and every listing treat retired, resolved and expired watches as not live; `watch list` shows the current belief, its source and date, and the registration belief when they differ; and a test asserts no code path other than `sync_watches` and the two commands writes to `watch_beliefs` or the resolution columns.
OUT OF SCOPE: Any automatic movement of belief from evidence -- there is no update rule, no hysteresis, no debouncing; the brief groups near-duplicates and the operator moves belief. Brier or any calibration score; the brief states the resolved count and nothing else until there are enough resolutions for a score to mean something, and "enough" is a later decision with a stated denominator. Candidate watches.
LANDMINES: **This is the task where the `sync_watches` delete becomes destructive**, because history hangs off the row from here on; the soft retire must land in the same change as the ledger, not after. **A belief written by the file after the operator moved it is a real conflict**, not a merge: the ledger records both with their sources and the listing shows the latest, so the operator sees that the file is behind and fixes the file. Do not silently prefer either. **Resolution is one-way and human.** There is no `--force`, no unresolve, and no path from evidence to `outcome`; the 33 predictions graded zero times are the standing reason the grading has to be a deliberate act, and invariant 6's cousin is that the tool never grades itself. `main` is protected -- open a PR.
---
Written 2026-09-22.

## Why belief has no update rule

Task 017 specified hysteresis, debouncing, N independent sources and append-only transitions. All
of it exists to let the system move belief without the operator. The decision of 2026-09-22 is
that it should not, yet: there are zero resolved watches to calibrate any rule against, and a rule
built ahead of the data is the pattern that left 25 unfalsifiable predictions in the old ledger.
What survives of 017 is its one non-negotiable: belief history is append-only and reconstructable.
The rest returns as its own task when there are resolutions to judge it by.

## Decisions made while building (2026-09-22)

- **A retired watch can be graded but takes no new belief.** The acceptance listed retired
  watches only under `believe`; the review noticed that `resolve` refused them too, silently.
  Settling a claim after dropping it from the file is an ordinary order of events, so `resolve`
  accepts a retired watch; a retired watch is not being held, so `believe` refuses one.
- **Liveness is two clauses.** `live_clause(today)` (open and not expired) gates routing;
  `open_clause()` (not retired, not resolved) gates adjudication and replay, which read routed
  pairs and must not depend on the day they run. Expired-but-open watches keep their routed pairs
  and are still judged; the asymmetry is stated in the ledger module and pinned by tests.
- **`models.py` became a package** (`src/database/models/`), one module per table family,
  mechanically, when the single file passed 480 lines. Nothing about any table changed; the review
  compared the generated DDL.
- **The `outcome` CHECK is a column constraint**, not a table constraint, because SQLite refuses
  to drop a column a table constraint names and the migration's way down drops these columns.

## What the adversarial review found, and what was done

Four reviewers read the worktree against this file. Fixed before commit:

- **The tree-scan test could not see the callers it was named for**: it matched constructors and
  attribute assignments, not calls to `record_belief` or `resolve_watch` or a bulk `update()`. It
  now matches all of them and allows exactly three writers by path.
- **The expiry test had no expired watch in it.** It does now, and pins that an expired watch's
  routed pairs are still asked and still replayed.
- **`downgrade()` broke half-way on any table created from the model**, because the table-level
  CHECK on `outcome` blocked `DROP COLUMN` after the ledgers were already gone. The constraint moved
  to the column, the columns are dropped first in one transaction, the ALTER names the constraint
  so a migrated table matches a fresh one, and a test downgrades a full model-built schema.
- **`replay --commit` would have deleted a retired watch's evidence**: rebuild skipped closed
  watches, commit deleted every row the replay did not produce. Stored evidence is now read for
  open watches only when comparing and committing; a closed watch's rows are outside the replay.
- **An orphaned ledger row crashed `watch list` and `watch sync` with a `KeyError`**; it now fails
  by name. **`sync` reported `updated` for every watch on every run**, so "no change" was
  unreachable; it now reports what changed. Docstrings that said "nothing else writes here" and
  "three tables" were corrected; the replay report counts open watches.

Recorded, not changed: resolution's one-way rule is enforced in Python and by the absence of any
other writer, not by a database trigger on `watches` (the plan mandates triggers for the ledger
only); a raw `UPDATE` from a shell can un-resolve a watch, as it can edit any other column there.
