# Onboarding as a skill: an interview that transcribes the operator's decisions and watches into the private files, validates them, and syncs.
REPO: InsightWeaver
STATUS: DONE              # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: small
PLAN: docs/PLAN.md (section 5, task 032; replaces the interview half of backlog/024)
ACCEPTANCE: `make check` passes, plus: `.claude/skills/onboard/SKILL.md` exists with the frontmatter the other skills use; it interviews for decisions (name, deadline, stake, key) and, per decision, for watches (claim, belief, because, structured triggers, expiry, staleness), writes `position.yaml` and `watches.yaml` to `POSITION_PATH` and `WATCHES_PATH` with the structure of the two example files, shows a diff before replacing an existing file, and ends by running `insightweaver watch sync` and `watch list`; every value written is one the operator stated and heard read back; the skill names no command that does not exist (asserted by `tests/test_docs.py`).
OUT OF SCOPE: A `setup` command in the CLI. Ranking decisions, suggesting beliefs, proposing claims. The quarterly review loop of backlog/024 (deferred until there are resolved watches to review). Any write to the database other than through `watch sync`.
LANDMINES: **The interview is the seam through which the system starts authoring its own watches** (invariant 6). A drafting interview is one helpful suggestion away from a generator; the skill says, in its first paragraph and its last, that it transcribes and never fills a field. **A trigger written as a sentence never fires**: the skill explains the clause rule and asks for the actual words. **The files must not land in the checkout**: the defaults point outside it and `.gitignore` refuses the names, but the skill checks the path it is about to write. `main` is protected -- open a PR.
---
Written 2026-09-23.

## Why a skill and not a command

The interview is a conversation, and the operator asked for it to happen in this terminal with
Claude asking the questions. A `setup` command would be a form; a skill is the conversation with
the rules written down: what to ask, in what order, what to refuse, and where to write. The
loaders (`src/position/`) remain the only validation and `watch sync` the only write path, so
the skill cannot put a watch in the table that the file would not.

## What replaced backlog/024

Task 024 had two halves: an interview that wrote a draft Position to a scratch path, and a
quarterly review loop. The interview is this skill, writing to the real private path because the
operator is present and confirms each value; the draft-to-scratch rule was for an unattended
command. The review loop is deferred: the 90-day banner (task 031) is the part that degrades
visibly, and a review that records "what changed" has nothing to record until watches have
resolved. Task 024 is parked with that note.
