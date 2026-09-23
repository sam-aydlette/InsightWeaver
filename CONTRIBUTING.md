# Contributing to InsightWeaver

## Development setup

Requires Python 3.11 or higher.

1. Create a virtual environment and activate it:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install development dependencies:
   ```bash
   make install-dev
   ```
   This runs `pip install -r requirements-dev.txt`, then `pip install -e .` (editable install,
   so CLI changes are picked up immediately), then `pre-commit install` (registers the git hooks
   in `.pre-commit-config.yaml`).

3. Set the Anthropic API key. It is never read from `.env` -- it lives in the OS keychain:
   ```bash
   insightweaver auth set anthropic
   ```
   `insightweaver auth status` shows which known credentials are set, without printing values;
   `insightweaver auth clear` removes one.

4. Copy `.env.example` to `.env` and, if you keep your Position and watch set outside the
   default location, point the two paths at them:
   - `POSITION_PATH` (default `~/.config/insightweaver/position.yaml`)
   - `WATCHES_PATH` (default `~/.config/insightweaver/watches.yaml`)

   These are private, hand-authored files and do not live in this repository.

5. Create a fresh database:
   ```bash
   make db-init
   ```
   This runs `src.database.migrations.create_schema`, which creates every table the SQLAlchemy
   models declare that the database is missing, and touches nothing that already exists. If you
   are working from an older checkout instead of a fresh one, the additive migrations
   (`make db-add-watches`, `make db-add-observations`, `make db-add-monitor`) add whatever those
   earlier stages introduced; each is safe to re-run.

6. Verify the setup:
   ```bash
   make check
   ```

## Project structure

```
src/
    brief/       render the brief (header, MOVED, DUE, WATCHING, QUIET) from the database
    cli/         one module per command group (adjudicate, auth, brief, ingest, replay, route,
                 run, sources, watch), wired together in app.py
    config/      settings, OS-keychain credentials, feed matching
    database/    SQLAlchemy models and the migrations under database/migrations/
    evidence/    the one adjudication model call and its prompt, plus the replay harness
    llm/         the Claude client, audit logging, JSON parsing helpers
    matching/    entity matching used by routing
    position/    the Position and watch-set loaders, validation, and the belief/resolution ledger
    routing/     compiles watch triggers and routes observations to the watches they match
    rss/         RSS fetching
    sources/     the adapter layer -- every source (RSS, Federal Register, ...) normalizes to
                 one observation shape and stores it through one path

tests/           mirrors src/ one-to-one, plus tests/cli/ for command-level tests

backlog/         task files (see Workflow, below)
config/          non-secret configuration checked into the repo
docs/            CONCEPTS.md (entity model), PLAN.md (architecture and delivery record), and
                 other reference docs
```

## Workflow

Branch from `main`. `main` is protected and takes changes only through pull requests.

The convention is one backlog task per PR. A task lives as a file under `backlog/`, for example
`backlog/031-brief.md`. Its first line is a `#` title stating the task in one sentence, then a
fixed set of header fields:

- `REPO` -- the repository the task belongs to
- `STATUS` -- `QUEUED`, `IN_PROGRESS`, `PARKED`, `DONE`, or `FAILED`
- `SIZE` -- roughly how large the change is
- `ACCEPTANCE` -- the specific, checkable conditions the task is done against; this is the
  approved plan, not a suggestion
- `OUT OF SCOPE` -- what the task deliberately does not touch, so a reviewer can tell scope
  creep from the intended change
- `LANDMINES` -- known ways the task could be gotten subtly wrong, written down in advance
- `PLAN` -- where in `docs/PLAN.md` the task comes from, when it does

A PR that closes a task updates that task's file (`STATUS: DONE` and any notes worth keeping)
as part of the same change. Commits are ordinary commits with an informative message; there is
no required commit format beyond that.

## Quality gate

```bash
make check
```
runs lint, typecheck, and test, in that order, and stops if any of them fails.

- **ruff** (`make lint`) runs `ruff check src/ tests/` and `ruff format --check src/ tests/`.
  Rule set: pycodestyle, pyflakes, isort, flake8-bugbear, flake8-comprehensions, pyupgrade, and
  flake8-unused-arguments/flake8-simplify (see `[tool.ruff.lint]` in `pyproject.toml`). Line
  length is unenforced by the linter (left to the formatter); `make format` (alias `make fmt`)
  applies fixes and formatting.
- **mypy** (`make typecheck`) runs `mypy src/ --show-error-codes --pretty`. Several modules
  (`src.database.models`, `src.database.connection`, `src.rss.*`, `src.matching.*`, `src.llm.*`,
  `src.cli.*`, `src.utils.*`, `src.config.*`) carry `ignore_errors` overrides in `pyproject.toml`;
  new code outside those modules is checked in full.
- **pytest** (`make test`) runs `pytest tests/ -v`.
- **detect-secrets** is not part of `make check` -- it runs as a pre-commit hook and in CI (see
  below), scanning against `.secrets.baseline`. A false positive gets an inline
  `pragma: allowlist secret` next to it rather than a baseline edit that hides it.

The pre-commit hooks (`.pre-commit-config.yaml`, installed by `make install-dev` or run on demand
with `make pre-commit`) run ruff (with `--fix`) and ruff-format, the standard
trailing-whitespace/end-of-file/check-yaml/check-json/check-toml/check-merge-conflict/
detect-private-key/mixed-line-ending hooks, check-added-large-files (1000 kB, which a recorded
fixture can reach), detect-secrets, and mypy. The pre-commit mypy hook is
informational (`verbose: true`, no failure on type errors); `make typecheck` is the real gate.

CI (`.github/workflows/ci.yml`) runs on push and PR to `main` and `develop`, as four jobs: `test`
(pytest with coverage, on Python 3.11 and 3.12), `lint` (ruff check and ruff format --check),
`typecheck` (mypy -- `continue-on-error: true`, so a type error there does not fail the build),
and `security` (detect-secrets over every tracked file, which does fail the build on a new
secret, plus a `safety` dependency check that only reports and never fails the build).

## Tests

Each test gets its own SQLite database through `tests/conftest.py`; no test needs a real key or
the network. `tests/evidence/stubs.py` states the rule directly in its module docstring:

> Nothing here makes an LLM call and nothing here needs an API key. The whole point of the
> harness is that adjudication is pluggable and that the replay machinery can be exercised
> without the stochastic part.

Anything that would otherwise touch the OS keychain uses the `memory_keyring` fixture from
`tests/conftest.py`, a keyring that forgets everything when the test ends.

The brief has a golden end-to-end test, `tests/brief/test_end_to_end.py`, which drives recorded
RSS and Federal Register fixtures (`tests/brief/fixtures/` and
`tests/sources/fixtures/federal_register_week.json`) through `watch sync`, ingest, route, a stub
adjudicator, and the brief renderer, and compares the output byte-for-byte against
`tests/brief/golden/`. Regenerate the golden files with:
```bash
make golden
```
and read the diff before committing it -- a golden file that changed is the test reporting a
behavior change, not noise to clear.

Run a single test file directly, e.g.:
```bash
pytest tests/brief/test_end_to_end.py -v
```

## Database migrations

The modules under `src/database/migrations/`:

- `create_schema.py` -- the one bootstrap for a fresh database. Creates every table the models
  declare that is currently absent (`Base.metadata.create_all`); adds no columns to an existing
  table. Run with `make db-init`.
- `add_watches_table.py` -- additive; creates the `watches` table from `Watch.__table__` so the
  migration and the model cannot drift. Run with `make db-add-watches`.
- `add_observations_and_evidence.py` -- additive; creates `observations` and `evidence`, and
  does not read, rewrite, or migrate the pre-existing `articles` table. Run with
  `make db-add-observations`.
- `add_monitor_tables.py` -- additive; creates whichever of the decision monitor's tables
  (`routes`, `adjudications`, `watch_beliefs`, `briefs`) are absent and adds the lifecycle
  columns an older `watches` table lacks. Run with `make db-add-monitor`.
- `drop_briefing_tables.py` -- destructive; drops the tables belonging to the deleted briefing
  product. This one refuses to run without `--confirm`; `make db-drop-briefing` deliberately
  does not pass it, so the target only shows what would be destroyed and the operator has to
  type the real command themselves.

## Documentation

- `README.md` -- what the tool is and why
- `GETTING_STARTED.md` -- first-run walkthrough
- `docs/CONCEPTS.md` -- the entity model (Watch, Evidence, Position, etc.)
- `docs/PLAN.md` -- the architecture and the delivery record it was built from
- `SOURCES.md` -- every source InsightWeaver retrieves and its recorded basis for use; a source
  with no recorded basis does not ship
- Comments that record a decision carry the date the decision was made, so a later reader can
  tell whether the reasoning still applies.

## Pull requests

A reviewer checks:

- `make check` is green
- the backlog task file is updated (`STATUS`, and notes on what changed vs. what the task
  described)
- no fallback or mock data is hiding a problem that should fail loudly instead
- changed files stay under roughly 200-300 lines; a file that grew past that is a refactor
  candidate, not an exception
