# Getting Started

From a clean checkout to a first brief. Rewritten 2026-09-23 (backlog task 033).

## What you need

- Python 3.11 or newer.
- An Anthropic API key, for the one model call the tool makes (`adjudicate`). Everything else,
  including the whole test suite, runs without one.
- A place outside this checkout for two private files, described in step 3.

## 1. Install

```bash
git clone https://github.com/sam-aydlette/InsightWeaver.git
cd InsightWeaver
python -m venv .venv
source .venv/bin/activate
make install-dev
```

`make install-dev` installs the pinned dependencies, the package in editable mode so that
`insightweaver` is on your path, and the pre-commit hooks. Check it worked:

```bash
insightweaver --help
make check
```

`make check` runs the linter, the type checker and the test suite. It needs no key and no
network.

## 2. Store the key

```bash
insightweaver auth set anthropic
```

You are prompted for the key, hidden, and it is written to the OS keychain. It is never read
from `.env` and never printed; `insightweaver auth status` says whether it is set.

## 3. Write your Position and watches

The tool's whole input is two hand-authored YAML files: the decisions you are carrying, with
deadlines, and the claims you want watched, with the words a document would contain if it
bore on them. They name real decisions and real deadlines, so they belong in a private
repository of your own, not in this one. Tell the tool where they are:

```bash
cp .env.example .env
# edit POSITION_PATH and WATCHES_PATH in .env, or leave the defaults:
#   ~/.config/insightweaver/position.yaml
#   ~/.config/insightweaver/watches.yaml
```

Two ways to write them:

- **Interview.** In Claude Code, run the `/onboard` skill. It asks for each decision and each
  watch, field by field, writes the two files from your answers, and ends by syncing them. It
  transcribes; it does not suggest decisions, beliefs or claims.
- **By hand.** Copy `config/position.example.yaml` and `config/watches.example.yaml` to the
  private paths and edit them. The comments in both files explain every field, and the loader
  refuses a file with a missing or malformed field, all problems at once, so a mistake is a
  message rather than a silent default. One thing it cannot check: a `sources` trigger names a
  source by its exact registered name (the `name` in `config/feeds/`, or `Federal Register -
  Documents API`), and a misspelling is a clause that never fires. `insightweaver sources list`
  shows the names once a first `ingest` has run.

Then create the database and load the watches:

```bash
make db-init
insightweaver watch sync
insightweaver watch list
```

## 4. The first morning

```bash
insightweaver run
```

This runs four commands in order and stops at the first that fails:

1. `ingest` reads every configured source and stores what is new. Each source is reported as
   fetched, inserted, unreachable, or went silent.
2. `route` links each new observation to the watches whose triggers it matches, and reports
   what routed nowhere, grouped by story and by source, so you can see what your triggers miss.
3. `adjudicate` asks the model, once per routed pair, whether the item bears on the claim.
   Every request is written to `data/llm-audit/` before it is sent.
4. `brief` prints the brief.

Read the brief top to bottom. The header says whether every source ran; MOVED is what gained
evidence; DUE is what has a date on it; WATCHING is every live claim and your current belief;
QUIET is where silence might be breakage. A brief whose QUIET section is all zeros and whose
sources all fetched is a quiet week. A brief with a source marked `LAST ATTEMPT FAILED` or a
watch marked `never routed` is telling you where to look.

To see what would be sent before spending anything:

```bash
insightweaver adjudicate --dry-run
```

## Daily use

```bash
insightweaver run                              # the morning
insightweaver watch believe my-watch 0.6 --note "the notice narrows the scope"
insightweaver watch resolve my-watch --outcome yes --note "final rule published 2026-10-02"
insightweaver brief --format md --output ~/briefs/today.md
```

Beliefs are yours to move and are appended, never edited. A watch is graded once. When a
decision closes or a claim stops mattering, edit the private files and run `watch sync`; a
watch removed from the file is retired, not deleted, so its history stays.

The default window of a brief opens at the last brief before today, so running `brief` twice
in a morning reports the same window and the same items; only the as-of stamp in the first
line moves. With `--as-of` fixed, the bytes are identical, and the suite asserts it.

## Troubleshooting

- **`insightweaver: command not found`**: the virtual environment is not active. Run
  `source .venv/bin/activate`.
- **`no credential 'anthropic_api_key' in the keychain`**: run `insightweaver auth set anthropic`.
- **`No Position at ...` or `No watch set at ...`**: `POSITION_PATH` or `WATCHES_PATH` does not
  point at a file. Check `.env`.
- **`no such table`**: run `make db-init`.
- **`unable to open database file`**: the database path is relative to the directory you run
  from. Run commands from the checkout, or set `DATABASE_URL` in `.env` to an absolute path
  (`sqlite:////home/you/insightweaver/data/insightweaver.db`).
- **A source reports UNREACHABLE every morning**: `insightweaver sources show NAME` prints its
  URL and last error. Old feeds in `config/feeds/` do go dark; remove the entry and `ingest`
  stops asking it. Its row stays in the database, so the header keeps printing its last attempt
  and `sources list` keeps listing it; there is no command to remove a source yet.
- **The run stopped at `adjudicate` with "the API was unavailable"**: nothing was recorded for
  the pair it stopped on; run `insightweaver adjudicate` again later and it resumes.

## Privacy

- The database is `data/insightweaver.db`, relative to the directory you run from, and the audit
  log is `data/llm-audit/` under the checkout. Keep both out of cloud-synced folders;
  `DATABASE_URL` and `LLM_AUDIT_DIR` in `.env` move them.
- The only network calls are fetching your configured sources and the model API. Nothing
  listens, nothing sends mail, nothing writes to any external service.
- The audit log holds every request that left the machine, in full, and each response's usage
  and stop reason. It is yours to read and to delete.
- Delete `data/` to wipe all accumulated state. Your Position and watches are elsewhere and are
  untouched.
