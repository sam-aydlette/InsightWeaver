# InsightWeaver plan: the decision monitor

Written 2026-09-22. Replaces `docs/ESTATE_PLAN.md` (written and deleted the same day), which
planned an estate graph with sensors. That plan was reviewed the same afternoon and cut to the scope below; section 8 records
what was cut and why, and section 7 keeps the decisions that still stand.

**Observed** means read from the tree or git history; **assumed** means unverified and said so.

---

## 1. Where the codebase stands

The briefing product was deleted on 2026-08-31 (task 012). The monitoring re-architecture that
replaced it has three tasks built and the rest queued:

| built | what |
|---|---|
| 013 | Position (decisions with deadlines, private YAML) and Watch (claim, belief, `so_what` -> decision, structured triggers, expires, staleness) with loaders that reject rather than default |
| 014 | immutable content-addressed `observations`, derived `evidence` with a per-row `prompt_version`, MinHash near-duplicate grouping, `replay`, a pluggable `Adjudicator` seam |
| 025 | the legacy article write path closed, so every stored article has an observation |
| 026 | credentials in the OS keychain, an audited model client that returns usage, secret scanning that can fail CI, the SDK on 1.x |

Six invariants are enforced by tests and constraints: nothing sends anything; every Watch names a
decision; observations are immutable and evidence is derived; exactly one stochastic component;
silence is distinguishable from breakage; the system never authors its own watches.

**What has never happened: the loop has never been run to a graded watch.** The ledger before the
rewrite held 33 predictions graded zero times. Position exists as an example. There is no command
today that ingests, routes, adjudicates or renders anything. Every earlier version stopped at this
point, and this plan is written to stop *after* it.

## 2. The product

A **decision monitor**. The operator writes down the decisions they are carrying, each with a
deadline and a stake, and the claims (watches) whose truth would change those decisions, each with
structured triggers and an expiry. Sources are read through adapters into an immutable corpus.
Deterministic routing selects the few observations that could bear on a watch. One model call
per routed pair judges whether it is evidence. A brief, run by hand, says what moved, what is due,
what is being watched, and what has gone quiet, and every line cites the observation hashes it
rests on. The operator adjusts belief and resolves watches; the tool never does either.

**The measurable property** is inherited from the re-architecture: output scales with live watches,
not with news volume. The test of it is three weeks of real operation on the operator's own
professional watches, with the brief's own header counting moved items per period and at least one
watch resolved. That measurement is the deliverable this plan ends on.

**What is deliberately not here.** No estate graph, no sensors beyond the two adapters, no belief
update rule, no synthesis pass, no MCP server, no cloud. Section 8 says why each was cut and what
would bring it back.

## 3. Schema additions

All additive, one migration created from the models (the `add_watches_table` pattern),
`--confirm` on the way down. Nothing existing is altered except `watches`, which gains columns.

```sql
-- Tier 1 output: which observations are candidates for which watch. Derived and rebuildable.
CREATE TABLE routes (
    id               INTEGER PRIMARY KEY,
    observation_hash TEXT NOT NULL REFERENCES observations(content_hash),
    watch_id         TEXT NOT NULL REFERENCES watches(id),
    clause_index     INTEGER NOT NULL,          -- the first trigger clause that fired
    routed_at        DATETIME NOT NULL,
    UNIQUE (observation_hash, watch_id)
);

-- Tier 2 run ledger: every pair the model was asked about, whatever it answered.
-- `evidence` (task 014) keeps holding the verdicts; this table is why a pair is not asked twice
-- and where the tokens went. outcome: 'evidence' | 'none' | 'failed'.
CREATE TABLE adjudications (
    id               INTEGER PRIMARY KEY,
    observation_hash TEXT NOT NULL REFERENCES observations(content_hash),
    watch_id         TEXT NOT NULL REFERENCES watches(id),
    prompt_version   TEXT NOT NULL,
    outcome          TEXT NOT NULL CHECK (outcome IN ('evidence','none','failed')),
    error            TEXT,                      -- validation or API failure text; never retried
    audit_id         TEXT,                      -- the src/llm/audit.py entry
    input_tokens     INTEGER NOT NULL DEFAULT 0,
    output_tokens    INTEGER NOT NULL DEFAULT 0,
    created_at       DATETIME NOT NULL,
    UNIQUE (observation_hash, watch_id, prompt_version)
);

-- Belief history, append-only. source: 'file' (from watches.yaml at sync) | 'principal'.
CREATE TABLE watch_beliefs (
    id          INTEGER PRIMARY KEY,
    watch_id    TEXT NOT NULL REFERENCES watches(id),
    belief      REAL NOT NULL CHECK (belief >= 0.0 AND belief <= 1.0),
    source      TEXT NOT NULL,
    note        TEXT,
    observed_at DATETIME NOT NULL
);
-- BEFORE UPDATE and BEFORE DELETE triggers refuse, as observations does for UPDATE.

ALTER TABLE watches ADD COLUMN retired_at DATETIME;     -- sync sets this; it never deletes
ALTER TABLE watches ADD COLUMN resolved_at DATETIME;
ALTER TABLE watches ADD COLUMN outcome TEXT CHECK (outcome IN ('yes','no'));
ALTER TABLE watches ADD COLUMN resolution_note TEXT;

-- One row per brief rendered. Default `since` of the next brief is the last row before today.
CREATE TABLE briefs (
    id            INTEGER PRIMARY KEY,
    as_of         DATETIME NOT NULL,
    since         DATETIME NOT NULL,
    moved         INTEGER NOT NULL,
    quiet         INTEGER NOT NULL,
    rendered_sha  TEXT NOT NULL
);
```

`watches.belief` becomes the value at registration. Current belief is the latest `watch_beliefs`
row. `sync_watches` writes a `file` row when a watch is added or its file belief changes, and
stops overwriting the column.

## 4. Commands and modules

One console script, `insightweaver`. The `estate` script and `src/estate/` from task 026 are
folded in: credentials move to `src/config/credentials.py`, `auth` to `src/cli/auth.py`.

| command | does | writes | network | model |
|---|---|---|---|---|
| `auth set/status/clear` | keychain | keychain | no | no |
| `sources list/show` | inventory | no | no | no |
| `ingest [--since] [--source]` | every configured source through the adapter path; per-source fetched/inserted/unreachable/went-silent | `articles`, `observations`, `rss_feeds` | yes | no |
| `watch sync/list` | file -> table; retire, never delete | `watches`, `watch_beliefs` | no | no |
| `watch believe ID P --note` | operator belief | `watch_beliefs` | no | no |
| `watch resolve ID --outcome yes/no --note` | operator grading | `watches` | no | no |
| `route [--dry-run] [--rebuild]` | compile triggers, link candidates, report the unrouted clusters | `routes` | no | no |
| `adjudicate [--dry-run] [--limit]` | one structured call per routed pair without a verdict for this prompt version | `adjudications`, `evidence`, audit log | no | yes |
| `replay` | as today, over routed pairs | `evidence` with `--commit` | no | depends |
| `brief [--since] [--as-of] [--format] [--output]` | the document | `briefs` | no | no |
| `run` | ingest, route, adjudicate, brief, in that order | all of the above | yes | yes |

Modules, each under 300 lines:

- `src/routing/compile.py`: a watch's trigger clauses to predicates. `terms` and `entities` both
  compile through `entity_matcher.term_pattern` with its shouted-term case rule; `sources` is a
  case-insensitive exact match on the source name. Within a clause every populated field must
  match; any clause fires the watch. There is no alias registry: an entity is a term until a watch
  needs aliases, and that is its own task.
- `src/routing/route.py`: evaluate live watches over observations in a window, insert missing
  links, report unrouted observations grouped by MinHash cluster and source.
- `src/evidence/claude_adjudicator.py`: the one `ClaudeAdjudicator`, prompt version `claude-v1`,
  structured output validated against a pydantic verdict, failures recorded not retried.
- `src/evidence/adjudicate.py`: select pairs, call, write the ledger and evidence, total tokens.
- `src/brief/`: `select.py` (the four sections as data), `render.py` (plain text and markdown, no
  timestamps beyond `as_of` and the data's own dates, deterministic to the byte).
- `src/cli/{ingest,route,adjudicate,brief,run,auth}.py`: thin.

The brief, in fixed order, each item citing observation hashes:

1. **Header.** As of, window, Position reviewed date and days since (a banner past 90 days), each
   source's last successful fetch and whether it returned nothing this window.
2. **MOVED.** Watches with new evidence in the window; evidence grouped by near-duplicate cluster
   so twelve outlets carrying one story are one item; each item: direction, magnitude, prompt
   version, source, date, title, hash.
3. **DUE.** Decisions with a deadline inside the window ahead or already past; watches expiring.
4. **WATCHING.** Every live watch: current belief and its source, decision, days to expiry,
   evidence count in window, last evidence date.
5. **QUIET.** Watches with nothing routed for `staleness_alert_days`, with the date of the last
   routed observation or "never"; sources that ran and returned nothing; adjudications that
   failed. Printed even when every count is zero.

The adjudication prompt carries the epistemic rules from the deleted `ANALYSIS_RULES.md` that
still apply to a single judgement: direction is two-valued or absent; magnitude is a strength
of bearing, not a probability; a claim the observation does not address is not evidence; no
recommendation, no inference beyond the text. The observation text sent is capped and the cap is
recorded in the audit entry.

## 5. Delivery order

Each task is a `backlog/NNN-*.md` with acceptance, out of scope and landmines, one commit each
on `estate/026-phase0-hygiene` (renamed to `monitor/phase1` at the end), reviewed as one PR or
split. `make check` passes at every commit. The user pushes; nothing here pushes.

| task | size | content |
|---|---|---|
| 027 sweep | small | delete the dead modules and files in section 6; fold `estate` into `insightweaver`; trim `FeedMatcher` to loading; drop the REPL; fix the dead test fixtures |
| 028 ingest and route | medium | `ingest` over every configured feed with bounded concurrency; `routes`; `route --dry-run`; the whole-word regression test (planted matches route, planted substrings do not) |
| 029 adjudicate | medium | `ClaudeAdjudicator`, `adjudications`, `adjudicate --dry-run`, token totals, replay over routed pairs, the no-retry rule tested |
| 030 belief and resolution | small | `watch_beliefs`, `watch believe`, `watch resolve`, `retired_at` on sync |
| 031 brief | medium | the four sections, `briefs`, `run`, golden-file end-to-end test over recorded fixtures with a stub adjudicator |
| 032 onboarding | small | a `.claude/skills/onboard/` skill that interviews for stakes, writes Position and watches to the private directory, and ends by running `watch sync` |
| 033 docs | medium | README, GETTING_STARTED and CONCEPTS rewritten from what exists; SOURCES unchanged |

Then: run it for three weeks. Task 034 is written after that with the observed numbers.

## 6. Changes to existing behaviour

1. **Deleted** (task 027): `src/processors/` (content filter, pairwise deduplicator), `src/utils/
   profile_loader.py`, `src/feed_manager.py`, `src/utils/logging.py`, `src/utils/profiler.py`,
   `src/rss/parallel_fetcher.py`, `src/matching/coverage_probe.py` and `CoverageProbe`, the
   top-level `migrations/`, `config/user_profile.example.json`, `config/context_modules/`,
   `config/probes/`, `main.py`, `src/__main__.py`, the interactive REPL in `src/cli/app.py`, the
   `data/forecasts` and `data/newsletters` placeholders, and the `tests/conftest.py` fixtures that
   patch deleted modules. Each has no live caller (verified by tree search and by an adversarial
   review recorded in the task file). `deduplicator.py` was an "explicit keep" in task 012; it
   reads the legacy `articles` table and task 014 recorded why MinHash superseded it.
2. **`src/estate/` folded into `insightweaver`** (task 027). One command.
3. **`sync_watches` retires instead of deleting**, and stops overwriting belief (task 030).
4. **`replay` rebuilds over routed pairs**, not every (observation, watch) product (task 029).
   The stub tests route their fixture corpus through the real router.
5. **`ClaudeClient` becomes synchronous.** Its only consumer is a synchronous adjudication loop
   inside a click command; the async client was a leftover from the deleted pipeline.
6. **`FeedMatcher` loses profile matching**; it loads `config/feeds/` and nothing else. Every feed
   in that directory is ingested. Curation is editing that directory.
7. **`run_adapters` gains bounded concurrency** for RSS (a semaphore of five). Sequential was
   right for two API adapters; it is not right for forty feeds with thirty-second timeouts.

## 7. Decisions on record (2026-09-22)

- Laptop only; nothing sends anything; tasks 019, 020, 023 superseded, 018 rewritten (Q1).
- PIR = Watch; no threat or indicator types (Q3).
- One belief ledger, file as prior, operator writes, no automatic update (Q5, and the 017 cut).
- Two observation tables would have had a stated rule; there is now one table, because the grid is
  deferred (Q4, superseded).
- Package location `src/`, one console script (Q4, revised from `src/estate/`).
- Anthropic key in the keychain, no fallback (Q5). Sonnet 5 adjudicates; Opus 5 is named for
  synthesis but synthesis is deferred (Q11).
- Triage starts against an empty corpus on this machine (Q14).
- Docs rewritten from scratch in task 033 (Q12).

## 8. Deferred, with what would bring each back

- **The estate graph** (nodes, edges, grid observations, current-state view, recursive CTEs).
  Deferred because without a sensor other than the operator, the graph records what the operator
  typed and the brief diffs it. Returns in the same task as the first sensor that writes to it,
  sized to what that sensor observes.
- **Sensors.** Ranked on 2026-09-22 by whether they reveal what the operator would otherwise miss:
  email metadata bound per institution (the notice not opened, and absence: "the insurer has not
  written in 400 days"); a finance aggregator (runway against a dated decision); public rate
  series (a threshold the operator set, weekly). Calendar, property records and weather were judged
  not worth building. Correction to what was said in conversation: the FRED API requires a free
  key; the keyless options are the Treasury Fiscal Data API and the Freddie Mac PMMS download. A
  numeric series needs a `series` trigger clause evaluated in Tier 1, which is one small task when
  a watch needs it.
- **A belief update rule** (task 017's hysteresis and debouncing). The brief already collapses
  near-duplicates into one item; whether beliefs should move without the operator is a question to
  answer after there are resolved watches to calibrate against.
- **Synthesis** (a second model pass phrasing the world-join section). After a deterministic brief
  has been read for three weeks.
- **MCP server.** After the CLI is used.
- **Google and finance integrations.** After a graded watch, one sensor per task, recorded
  fixtures, off by default.

## 9. Assumptions

- The operator's private repository holds `position.yaml` and `watches.yaml`, at `POSITION_PATH`
  and `WATCHES_PATH`, and the professional watches in it are the ones the three-week run uses.
- `config/feeds/` is the operator's curated source list. Some URLs in it are old and will report
  unreachable; that is the brief's job to show, not this plan's job to fix.
- Sonnet 5 accepts `output_config.format` structured output; verified against the SDK skill docs,
  not against a live call from this machine.
