# Sweep: delete what has no caller, fold `estate` into `insightweaver`, and leave one command over a tree that reads as current.
REPO: InsightWeaver
STATUS: DONE              # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: small
PLAN: docs/PLAN.md (section 5, task 027; section 6 item 1 and 2)
ACCEPTANCE: `make check` passes, plus: every module, config file and fixture listed below is gone from the tree, with its own tests; no module under `src/` is unreachable from a console script, a migration, or another live module -- asserted by a test that walks imports from those roots, which lands with task 029, because on 2026-09-22 the test found fourteen modules unreachable -- the whole source, routing and model stack -- and the last of them (`src/llm/`) gains its caller only when the adjudicator exists; the `estate` console script and `src/estate/` no longer exist, `auth` is a subcommand of `insightweaver`, and credentials live in `src/config/credentials.py`; `insightweaver` with no subcommand prints help and exits rather than entering a REPL; `FeedMatcher` loads `config/feeds/` and does nothing else; `tests/conftest.py` carries no fixture that patches or describes a module that does not exist; and the mypy override list in `pyproject.toml` names no deleted module.
OUT OF SCOPE: Anything the decision monitor will add (routing, adjudication, brief). Rewriting `README.md`, `GETTING_STARTED.md`, `docs/CONCEPTS.md`, `CONTRIBUTING.md` -- task 033; they keep their superseded banners until then. Deleting `src/rss/fetcher.py` (the RSS adapter reads feeds through it), `src/matching/entity_matcher.py` (routing needs it), or the `articles` table. Changing what `config/feeds/` contains.
LANDMINES: **`deduplicator.py` was an "explicit keep" in task 012's brief.** It reads the legacy `articles` table, which tiers built after task 014 must not, and `src/sources/minhash.py` records why a stored MinHash signature superseded it: the pairwise Jaccard produced nothing storable, so a grouping computed today and after a replay could differ. The keep is overridden on that reasoning, recorded here, and the operator approved the sweep list on 2026-09-22. **`coverage_probe.py` was ported "for task 018's staleness check."** The staleness check in `docs/PLAN.md` is a query over `routes` ("nothing routed for N days"), not a probe match over `articles`; 018 as rewritten on 2026-09-22 names no probe. The word-boundary rules the probe engine relied on live in `entity_matcher.py`, which stays. **Every deletion was adversarially reviewed** by an agent per candidate instructed to find a live caller, a build step, a CI step, a packaging entry or a standing commitment; none was found. The review's own list of what the sweep missed is recorded below and folded in. **The reachability test is the thing that keeps this from recurring**: a module nothing imports fails the suite, so the next leftover is caught at the PR rather than a month later. `main` is protected -- open a PR.
---
Written 2026-09-22, after the plan was cut to the decision monitor.

## What goes, and why each

| path | why |
|---|---|
| `src/processors/content_filter.py` | keyword filter keyed off the deleted `user_profile.json`; no caller |
| `src/processors/deduplicator.py` | superseded by MinHash (task 014); reads `articles`; no caller |
| `src/utils/profile_loader.py` | loads the deleted product's profile; only `feed_manager` imported it |
| `src/feed_manager.py` | profile-matched feed sync; `store.py::ensure_source` registers sources when an adapter runs, which removes the "adding a feed does not add it to the database" trap by construction |
| `src/config/feeds.py` | an 813-line Python dict of 112 feeds from 2025-09; `config/feeds/*.json` is the live configuration; no caller |
| `src/utils/logging.py`, `src/utils/profiler.py` | 0% coverage, no caller |
| `src/rss/parallel_fetcher.py` | drove `fetch_all_active_feeds`, whose write path task 025 closed |
| `src/matching/coverage_probe.py`, `CoverageProbe` in `terms.py` | see LANDMINES |
| `migrations/` (top level) | targets tables dropped in task 012; the live directory is `src/database/migrations/` |
| `config/user_profile.example.json`, `config/context_modules/`, `config/probes/` | the deleted product's profile, context and probes |
| `main.py`, `src/__main__.py` | legacy entry points; the console script is `insightweaver = src.cli.app:cli` |
| the REPL in `src/cli/app.py` | ASCII art, a 2.5-second sleep and a prefix dispatcher; a scripted command has no use for any of it |
| `data/forecasts/`, `data/newsletters/` | placeholders for deleted subsystems |
| `tests/conftest.py` fixtures `mock_claude_client`, `mock_web_fetch`, `mock_authoritative_sources`, `sample_response`, `mock_settings`, `temp_yaml_file`; `tests/utils/conftest.py` | describe or patch modules that do not exist |
| `src/estate/` and the `estate` script | folded into `insightweaver`; one command |

`FeedMatcher.match_feeds_to_profile`, `_calculate_match_score`, `_get_default_preferences`,
`get_feed_statistics`, `get_available_tags` go with `feed_manager`; the class keeps `Feed` and the
loader.

## What the adversarial review found that the list missed

Fifteen refuters, one per candidate above, found no blocker. Three independent hunters (by call
graph, by product history, by coverage) then found what the list had not named. Folded in:

| path | evidence |
|---|---|
| `src/config/feeds.py`, `tests/config/test_feeds.py` | 813-line static feed dict from 2025-09; only its own tests import it |
| `src/database/migrations/drop_forecast_tables.py`, `drop_memory_facts.py`, `drop_orphan_tables.py` | one-off drops from the pre-August stages; no Makefile target, no test, no importer; the tables they drop have no model. A database that predates those stages can still run them from git history |
| `src/config/settings.py` fields `debug`, `log_level`, `enable_smart_rss_fetch`, `smart_rss_fetch_threshold_minutes`, `logs_dir` (and its `mkdir`), `src/logs/.gitkeep`; their tests in `tests/config/test_settings.py` | no reader anywhere in `src/`: the `--debug` flag goes through `src/cli/output.py`, which never consults settings, and the logging module that read `log_level` and `logs_dir` is deleted above |
| `src/utils/colors.py` merged into `src/cli/colors.py` | the two-module split existed for a `src/render` import cycle that no longer exists; `success`, `emphasis`, `colorize_priority`, `colorize_confidence` have no caller |
| `src/rss/fetcher.py::create_test_feed` and `TestCreateTestFeed` | a development helper in production code, called only by its own tests |
| `src/database/connection.py::create_tables` and `TestCreateTables` | called only by its own tests; the models module warns against calling it |
| `tests/config/conftest.py`; the unused fixtures in `tests/rss/conftest.py` | zero consumers |
| `pyproject.toml` dependencies `aiohttp`, `rich`, `requests`, `lxml`; dev `aioresponses`; `types-requests` in the pre-commit mypy hook; the `slow`/`integration`/`unit` markers | nothing imports or uses them; requirements recompiled |
| `.gitignore` entries for `config/api_sources.json`, `/reports/forecasts/*`, `src/logs/*.log` | name things that no longer exist |

Left for task 033 (docs), not this sweep: `README.md`, `GETTING_STARTED.md`, `CONTRIBUTING.md`,
`docs/CONCEPTS.md`, `SOURCES.md` lines that cite deleted files, and `.claude/skills/review-tests/`
whose worked examples come from a deleted test module. Left alone on purpose: the unread columns
on `articles` (it is the pre-rewrite archive and its shape is the rule), and
`src/matching/entity_matcher.py`, which has no caller until task 028's compiler. The reachability
test was built here, run, and found fourteen modules unreachable from any command: `src/sources/`,
`src/rss/fetcher.py`, `src/matching/`, `src/llm/`, `src/config/feed_matcher.py`. That is the
finding, stated plainly: the repository has had no command that ingests since 2026-08-31 and none
that calls a model since ever. The test is removed from this commit and lands with task 029, when
the last of those modules is wired to a command.
