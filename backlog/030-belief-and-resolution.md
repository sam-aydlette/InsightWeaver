# One belief ledger the operator writes, resolution as a human action, and retirement instead of deletion.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
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
