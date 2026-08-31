# Delete the briefing product -- beats, questions, predictions, frames, synthesis, rendering -- porting only five modules whose mechanics the new tiers need.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: large
ACCEPTANCE: `make check` passes, plus: roughly 8,900 lines of source are **deleted, not archived** -- `src/render/`, `src/prompts/`, `src/config/beats.py`, the beat/question/prediction/standing-agenda/institutional-activity/frame/synthesis modules in `src/context/`, and every CLI command except what the new pipeline needs; their tests are deleted with them; **`src/render/email.py`'s `smtplib` send path goes with the rest**, closing the standing violation of invariant 1; the five modules named below are **moved and kept**, with their tests, because the new tiers need their mechanics; a migration drops the tables belonging to deleted concepts; `insightweaver --help` lists only surviving commands; and the deletion lands as **one commit** with a message naming what went and why, so `git log` is the record rather than an `archive/` directory.
OUT OF SCOPE: An `archive/` directory. Superseded on 2026-08-31: the operator's call is that git history is the rollback path and a directory of dead code in the tree is a liability, not documentation. Deleting `src/sources/`, `SOURCES.md`, `src/database/connection.py`, `src/config/feed_matcher.py`, `src/config/settings.py`, `src/rss/`, or the five ported modules. Building any part of the new pipeline. Dropping the `articles` table -- that is task 014's decision.
LANDMINES: **Five modules encode findings that cost real debugging and must be ported, not rewritten.** `src/context/entity_matcher.py` (168) carries word-boundary matching: across the live corpus, 5,364 titles contain the substring `nist` and 73 match at a word boundary, and its boundary test was found to pass with the anchors deleted from the codebase because case-sensitivity rejected the collisions first -- a rewrite reintroduces both. `src/context/claude_client.py` (212) carries the retired-model outage of 2026-06-15 and the `ThinkingBlock` parsing failure, each of which cost a live run. `src/context/coverage_probe.py` (488) is a "did anything match this in N days" engine, which is what task 018's staleness check is. `src/utils/cadence.py` (117) is interval parsing for task 013. `src/processors/deduplicator.py` (433) is an explicit keep. **Do not delete a module because its concept died if its mechanics are load-bearing downstream** -- name each ported module in the PR with the task that needs it. **The database still holds 55,249 articles, 46 questions, 33 predictions and 42 frames**; dropping tables is destructive and irreversible against that data, so back up before the migration and say in the PR that you did. `main` is protected -- open a PR.
---
Rewritten 2026-08-31 after the operator's decision: beats and questions are removed, Position
replaces them, and the old code is deleted rather than archived because git already holds it.

## What goes

| area | lines |
|---|---|
| `src/context/` -- synthesis, topics, curation, frames, questions, predictions, standing agenda, beat scope, institutional activity, decision routing | ~3,900 |
| `src/cli/` -- brief, frames, diet, questions, predictions, forecast, decisions, beat, stake, scope | ~3,000 |
| `src/render/` -- terminal, markdown, html, email, document | 1,834 |
| `src/config/beats.py` | 665 |
| `src/prompts/` | 508 |

Plus most of 844 tests. This is a deletion of roughly the whole product built to date.

## What is ported, and why it is not sentiment

Five modules whose concepts die and whose mechanics the new tiers need:

- **`entity_matcher.py` -> Tier 1 routing.** Word boundaries are the difference between 73 and
  5,364 matches on one term in this corpus. Its test class was also found to pass with anchoring
  removed, because shouted terms were rejected by case-sensitivity before the anchors ran. Both
  findings are encoded here and a blank-file rewrite loses them.
- **`claude_client.py` -> Tier 2.** Encodes a retired model that failed silently for ten weeks and
  a response-shape change that discarded a completed synthesis.
- **`coverage_probe.py` -> task 018.** A staleness check is "did anything match this in N days",
  which is what this already is.
- **`cadence.py` -> task 013.** Interval parsing and next-review arithmetic.
- **`deduplicator.py` -> Tier 0.** Explicit keep in the brief.

## Why one commit and no `archive/`

A directory of dead code is read as current by every future reader and every agent, and it drags
the old product's shape forward -- which is the outcome the rewrite exists to avoid. `git log` is
the rollback path, and the commit message is where the reasoning lives.
