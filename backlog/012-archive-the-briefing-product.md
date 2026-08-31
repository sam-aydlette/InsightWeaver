# Move the briefing product's synthesis machinery to archive/ in one commit, so the monitoring rewrite does not inherit its shape.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: medium
ACCEPTANCE: `make check` passes, plus: `src/context/frame_manager.py`, `cross_cluster_reconciler.py`, `topic_matcher.py`, `curator.py`, `synthesizer.py`, `src/prompts/{synthesis,frames,meta_frames}.py`, `src/render/` and the `brief`/`frames`/`diet` CLI commands are moved under `archive/` in a single commit with an `archive/README.md` explaining what each was for and why a state machine has no use for it; the `brief` command is gone from `insightweaver --help`; **`src/render/email.py`'s `smtplib` send path is deleted, not archived**, because invariant 1 says only an Alert may generate mail and a dormant sender is a latent violation; every test covering archived code is archived with it rather than deleted, so the suite still passes and the behaviour stays readable; and the surviving suite is green with no skips added.
OUT OF SCOPE: Deleting anything -- this is a move, and `git mv` keeps the history legible. Archiving `src/sources/`, `src/config/`, `src/database/`, `src/utils/`, `src/rss/`, `src/processors/deduplicator.py`, or the question/prediction/decision/beat modules; those are kept or ported by later tasks. Changing the schema or dropping tables. Touching `SOURCES.md`. Building any part of the new pipeline.
LANDMINES: **`src/context/` mixes both products and must not be moved wholesale.** Measured 2026-08-31: it is 4,843 lines across 16 files, of which the briefing machinery (`synthesizer` 915, `topic_matcher` 611, `curator` 461, `frame_manager` 324, `cross_cluster_reconciler` 104) is ~2,415 lines and the rest (`coverage_probe` 488, `beat_scope` 325, `institutional_activity` 306, `standing_agenda` 260, `question_matcher` 295, `prediction_tracker` 175, `decision_router` 158, `entity_matcher` 168, `claude_client` 212) is machinery the new product either keeps or ports. Cut file by file. **`src/pipeline/orchestrator.py` is the only importer of the synthesizer** (verified by grep, one line: `orchestrator.py:13`), so the archive boundary is genuinely clean -- but the orchestrator itself contains the fetch stage the new Tier 0 needs, so archive the synthesis stage and keep the file. `src/context/entity_matcher.py` is imported by `coverage_probe.py`, which is kept: do not archive it with the frame code. Coverage is 79% overall; archiving high-coverage files will move the number and that is expected, not a regression. `main` is protected (5 required checks, `enforce_admins: true`) -- open a PR.
---
Written 2026-08-31 as step 1 of the monitoring re-architecture.

The rewrite's stated risk is that porting the briefing product's parts drags its shape into the new
one. This task front-loads the cut so every later task is written against a tree that no longer
contains a briefing generator.

**Why `email.py`'s sender is deleted rather than archived.** Everything else here is a `git mv`.
The send path is the exception because invariant 1 -- only an Alert may generate an email -- is a
property of the whole system, and an archived `smtplib.SMTP_SSL` call reachable from an archived
CLI command is still a code path in the repository. It ships nothing and it is one import away from
being reachable again. The renderers move; the sender goes.

**What the audit found that changes this task's shape.** `src/render/` is 1,834 lines and its
`--from-run` offline path was built in task 003 as a deliberately deterministic, no-API surface. It
is genuinely useful engineering that has no place in the new product, which notifies rather than
renders documents. It is archived rather than deleted so a future decision to render a weekly
receipt as HTML can start from working code instead of a blank file.
