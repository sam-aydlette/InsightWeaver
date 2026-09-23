# Documentation rewritten from what exists: README, GETTING_STARTED, CONCEPTS, CONTRIBUTING, the skills, and a test that the docs name only things in the tree.
REPO: InsightWeaver
STATUS: DONE              # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: medium
PLAN: docs/PLAN.md (section 5, task 033; decision Q12 in section 7)
ACCEPTANCE: `make check` passes, plus: README.md describes the decision monitor as built, states its status without claims about results it has not produced, carries the five principles each with how this build does or does not implement it, shows a real brief (an excerpt of the golden file), lists every registered command and no other, and names the six invariants; GETTING_STARTED.md takes a reader from a clean clone to a first brief with commands that exist, in an order that works on a fresh database; docs/CONCEPTS.md is the entity-by-entity reference for the monitor with no entity the code lacks; CONTRIBUTING.md matches the Makefile, the pre-commit hooks and CI; `.claude/skills/` name no deleted code; SOURCES.md keeps its licensing content with the deleted beat and its test no longer cited as present; and `tests/test_docs.py` fails when any of those documents names a command, an option, a make target or a repository path that does not exist.
OUT OF SCOPE: Rewriting SOURCES.md beyond the stale sentences (its basis-for-use content stands, per the plan). docs/PLAN.md and docs/RECONCILIATION.md, which are records. Screenshots, badges, a changelog.
LANDMINES: **A README that describes the deleted product as present.** Every sentence was written from the tree on 2026-09-23, and the drift test is the guard against the next rewrite drifting. **Numbers rot**: no test counts, no line counts, no costs. **A guide that cannot be followed on a fresh machine**: writing it found that nothing created `rss_feeds` and `articles` on a clean database, so `make db-init` (`src/database/migrations/create_schema.py`) was added here; the guide's sequence was then run against an empty database. `main` is protected -- open a PR.
---
Written 2026-09-23.

## What was written from scratch and what was kept

README.md, GETTING_STARTED.md and docs/CONCEPTS.md are new text. The five principles keep their
headings from the earlier product because the operator's stated aims did not change; each body
now says what this build does about it, and the third says plainly that it is not implemented.
CONTRIBUTING.md and the review-tests skill were rewritten by a Sonnet 5 writer from the Makefile,
CI, pre-commit and the current suite, then reviewed. SOURCES.md lost only the sentences that
cited the deleted beat and its deleted test.

## The bootstrap gap

`get_db` opens a session; nothing created the schema. The three additive migrations create the
tables they were written for and `Base.metadata.create_all` ran only in the tests and in the
deleted pipeline's startup. On a clean checkout `ingest` failed on its first insert. `make
db-init` creates every declared table that is absent and touches nothing that exists; the
additive targets remain for older databases that need columns added.

## Review (2026-09-23): five lenses, every finding tried by two refuters

Twenty-nine findings survived both refuters, two split, two were refuted (the README's
`so_what` sentence, which `watch list` makes true; the onboard skill proposing slugs, which
its own scoping sentence allows). What changed: the README no longer says the golden test
drives "every command" or that `make install-dev` creates a venv, shows the golden file whole
rather than a trimmed excerpt, and says `ingest` writes `articles` too; CONCEPTS says what the
observation hash contains (the item and source URLs, so one text from two sources is two rows),
that a file holding an expired watch fails `watch sync` until the watch is graded and its date
moved or the entry removed, that a rebuild restarts QUIET's silence clock, that a replayed
not-evidence pair is asked once more, that the version is a pinned label rather than the
fingerprint itself, that `watch believe` refuses a retired watch, and that a file behind the
operator's belief re-applies the file value as a recorded row (task 030's decision, which the
first draft had reversed); GETTING_STARTED names the exact source names a `sources` clause
needs and says the loader does not check them, that the database path is relative to the
working directory, what "the same brief twice" means, and that removing a feed from config
does not remove its row; the onboard skill says the same about source names;
CONTRIBUTING's fixture path, module count, hook list, task-file fields and migration
description were corrected; SOURCES.md's sentence about the deleted analysis rules was
rewritten and the file joined the drift test. The example watches file named `Federal
Register`, which matches no registered source; it now names `Federal Register - Documents
API`. `.env.example` gained the `DATABASE_URL` line the guide refers to.

Two invariants the README called tests were not: `tests/test_invariants.py` now pins that
nothing in `src/` imports anything that sends, serves or listens, that only the two fetchers
open an HTTP client, and that only `replay` deletes evidence. `tests/test_docs.py` now also
checks the README's commands table and top-level file names.

Recorded, not changed: no command removes a source row (a feed dropped from config keeps its
header line); a `route --rebuild` resets `routed_at` and with it QUIET's staleness; both are
noted in the guide and the concepts reference.
