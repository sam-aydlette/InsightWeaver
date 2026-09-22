# Estate briefing: plan

Written 2026-09-22. A plan, not code. Section 7 records the decisions taken on 2026-09-22; Phase 0 is
approved and everything after it pauses for review at each PR.

Throughout, **observed** means read from the tree or git history on 2026-09-22; **assumed** means
I could not verify it here and am saying so.

---

## 1. What the codebase is today

### 1.1 The brief you wrote describes a product that no longer exists

The request describes InsightWeaver as "RSS in, frame-analyzed synthesis out", with collection,
deduplication, context curation, clustering, three synthesis passes, and `ANALYSIS_RULES.md`
injected into every prompt.

**Observed:** that product was deleted on 2026-08-31 in one commit (`ed12869`, PR #20, backlog
task 012): roughly 8,900 lines of source and most of 844 tests. There is no `src/prompts/`, no
`src/render/`, no `src/context/`, no clustering, no curation, no synthesis, and no `brief` command.
`ANALYSIS_RULES.md` lived at `src/prompts/ANALYSIS_RULES.md` and is recoverable from git
(`git show ed12869^:src/prompts/ANALYSIS_RULES.md`, 85 lines); it is not in the tree. `README.md`,
`GETTING_STARTED.md` and `docs/CONCEPTS.md` all open with a "Superseded" banner and describe the
deleted product below it.

What replaced it is a **monitoring re-architecture**, planned in PR #19 (`docs/RECONCILIATION.md`
plus backlog tasks 012 through 025) and partly built:

| task | status | what it built |
|---|---|---|
| 012 | done (#20) | deleted the briefing product; ported five mechanics modules |
| 013 | done (#21) | Position (decisions with deadlines, private YAML) and Watch (claim, belief, so_what -> decision, structured triggers, expires, staleness_alert_days) |
| 014 | done (#22) | immutable content-addressed `observations`, derived `evidence` with per-row `prompt_version`, MinHash near-dup grouping, `replay` command, pluggable `Adjudicator` seam |
| 025 | done (#23) | closed the legacy article write path so every article has an observation |
| 015 | queued | Tier 1: deterministic routing of observations to watches, no LLM |
| 016 | queued | Tier 2: one LLM adjudication prompt, structured output, token accounting |
| 017 | queued | Tier 3: belief updates, hysteresis, debouncing, transitions, Alerts |
| 018 | queued | staleness alerts, dead-man's switch, weekly receipt |
| 019 | queued | Tier 4: Alert delivery by **SES email** |
| 020 | queued | v0 deployment: **one AWS Lambda, SQLite in S3, EventBridge schedule** |
| 021 | queued | weekly slow loops, Brier scoring, candidate watches |
| 023 | queued | **S3-hosted state feed behind Cognito** |
| 024 | queued | `setup` interview drafting Position; quarterly review loop |
| 022 | parked | open questions; Q1, Q2, Q4, Q5 answered, Q3 answered by 014, Q6 open |

That plan carries six invariants, referenced throughout the code and tests. Observed from the task
files and docstrings (there is no single file that lists them):

1. Only an Alert can cause mail to be sent, through one function.
2. Every Watch names a decision in the Position (enforced by loader and CHECK constraint).
3. Observations are immutable and content-addressed; Evidence is derived and replayable.
4. Exactly one stochastic component: adjudication. Every other tier is deterministic.
5. Silence must be distinguishable from breakage.
6. The system never authors its own watches. Tested by asserting `watch add` does not exist.

**The estate brief you are asking for is mostly a re-expression of this plan with the estate half
added, and three of its queued tasks (019, 020, 023) contradict your operational constraints
outright.** Section 2 goes through the overlaps; section 7 asks which plan is canonical.

### 1.2 What exists, module by module (observed)

**Ingestion** (`src/sources/`, `src/rss/`): a `SourceAdapter` protocol (`name`, `source_url`,
`category`, `async fetch(since) -> list[RawItem]`), two adapters (RSS, Federal Register API), a
runner that distinguishes "quiet" from "went silent" from "unreachable", and one store path
(`store.py::store_items`) that writes an `articles` row and its `observations` row in one
transaction. The rule for the two tables is written in `src/database/models.py`: `articles` is the
pre-rewrite archive; `observations` is authoritative for everything new. Unreachable raises, never
returns empty. A tree-grep test asserts only one module constructs `Observation` and only one
constructs `Article`.

**Deduplication**: two mechanisms. Exact identity is the content hash over `OBSERVATION_FIELDS`
(everything the adapter emitted, minus derived `word_count`, plus `source_url`; nothing per-fetch).
Near-duplicates are MinHash signatures over 5-word shingles, stored per observation, grouped at
threshold `settings.near_duplicate_threshold` (0.7, measured against real pairs). The older
`src/processors/deduplicator.py` (pairwise Jaccard over `articles`) is kept but has no caller.

**Context curation, clustering, synthesis**: do not exist. `src/processors/content_filter.py`
(sports/clickbait keyword filter keyed off `user_profile.json`) survives with no caller.

**Position and Watch** (`src/position/`): hand-authored YAML, loaded from outside the checkout
(`POSITION_PATH`, `WATCHES_PATH`, defaults under `~/.config/insightweaver/`), validated with
accumulate-all-problems-then-reject loaders that never default a missing field. Frozen dataclasses,
not pydantic. `sync_watches` makes the `watches` table match the file and **deletes** rows for
watches removed from the file (a landmine task 017 already names). Decisions live only in Position;
there is no decisions table.

**Evidence and replay** (`src/evidence/`): `Adjudicator` protocol (`prompt_version`,
`adjudicate(ObservationView, watches) -> list[Verdict]`), a registry keyed by prompt version, a
`NullAdjudicator`, and a replay harness that rebuilds evidence in fixed order, diffs against stored
rows, refuses to commit a nondeterministic version. This *is* the "pluggable scorer interface" your
brief asks for.

**LLM** (`src/llm/claude_client.py`): async client, default model `claude-sonnet-5`, effort passed
through `extra_body` because the pinned SDK (`anthropic>=0.39.0`) predates `output_config`.
Returns text only, so token usage is discarded. No audit log of outbound payloads. No structured
output. `_json.py::parse_claude_json` returns `{}` on parse failure, which is a silent fallback.

**Matching** (`src/matching/`): word-boundary, case-aware entity matcher and the coverage-probe
engine ("did anything match this in N days"), both kept for Tier 1 routing and the staleness check.

**Storage**: SQLite via SQLAlchemy 2.x with pre-2.0 `Column()` style (models excluded from mypy).
`DATABASE_URL` defaults to `sqlite:///./data/insightweaver.db`, i.e. inside the checkout. **Two
migration directories exist**: `migrations/` (top level, tasks 001/002, targets tables that were
dropped in task 012; dead) and `src/database/migrations/` (live; additive migrations created from
the model so DDL cannot drift, `--confirm` on the way down). Task 014 already flagged the
duplication. SQLite on this machine is 3.46.1 (window functions, recursive CTEs, JSON1 all fine).

**CLI**: click, entry point `insightweaver = src.cli.app:cli`, three commands (`sources`, `watch`,
`replay`) plus an interactive mode with ASCII art and a 2.5s sleep.

**Tests**: 554 tests, per-test SQLite via `Base.metadata.create_all`, frozen `TODAY` dates, offline
fixtures recorded from real APIs, no API key required. `tests/conftest.py` still carries dead
fixtures that patch modules deleted in task 012 (`mock_web_fetch`).

**Hygiene**: `.gitignore` covers `*.db`, `.env`, `position.yaml`, `watches.yaml`, and the private
profile files. Pre-commit runs ruff, standard file checks, mypy, and `detect-private-key` **only**;
there is no secret scanner (no gitleaks, no detect-secrets). CI's "security" job runs
`safety check || true`, which is a dependency-vulnerability scan that cannot fail the build.

**Environment on this machine** (observed): Python 3.14.4 system interpreter, no `venv/`, no
`.venv/`, none of the project's dependencies installed, no `data/insightweaver.db`. I could not run
`make check`. The 55,249-row corpus the docs cite is not in this checkout.

### 1.3 Reuse, wrap, replace

| existing | disposition | why |
|---|---|---|
| `observations` + content hash + immutability trigger | **reuse as the world-document store**; copy the pattern for grid observations | it is exactly the append-only, hashed, immutable row your grid needs |
| `Adjudicator` protocol, registry, replay | **reuse as the triage scorer interface** | "pluggable scorer, default Claude, room for a cheap classifier" is one `register()` call per implementation |
| Position + Watch loaders and schema | **reuse; Watch becomes the PIR** (section 2.2) | it already enforces "queries bound to nodes, not prose" and invariant 2 |
| `src/sources/` adapters and runner | **reuse unchanged** for the outside realm | your "RSS sensor" is these adapters plus triage; they should not learn about the grid |
| `entity_matcher`, `coverage_probe`, `minhash` | **reuse** in Tier 1 routing and staleness | already ported for that purpose |
| `ClaudeClient` | **wrap and extend**: audit log, usage capture, structured output | section 6.1 |
| `cadence.py` | **reuse** for horizon parsing (`35d`, `1y`) | one interval grammar |
| `content_filter.py`, `deduplicator.py`, `feed_manager.py`, `profile_loader.py` | **leave alone** | no caller, out of scope, not in the way |
| `migrations/` (top level) | **leave alone, propose deletion separately** | dead; deleting it is its own small task |
| `ANALYSIS_RULES.md` | **restore from git** into the estate package, trimmed (section 2.4) | the epistemic-label rules apply; the narrative-layer sections do not |
| interactive CLI mode | **not inherited** by `estate` | a scripted, idempotent command should not sleep 2.5s and print a banner |

---

## 2. Where your architecture and the repo disagree, and what I recommend

### 2.1 Deployment target (blocking)

Your constraints: laptop, on demand, no daemon, loopback only, nothing sends mail, credentials in
the OS keychain. Queued tasks 019 (SES), 020 (Lambda + S3 + EventBridge + SSM), 023 (S3 + Cognito
state feed) and 018's "dead-man's switch off the mail path" all assume a cloud deployment with an
email transport. These cannot both be the plan.

**Recommendation:** the laptop plan is canonical. Retire 019, 020 and 023 as written. What they
were for survives in smaller form: 023's "state, not stream" card list becomes `estate status`;
018's weekly receipt becomes the brief's `unknown` section plus a header line stating when each
sensor last ran; the dead-man's switch is unnecessary when the operator runs the command by hand and
sees it fail. Invariant 1 tightens from "only an Alert sends mail" to "nothing sends anything."

### 2.2 PIRs, threats, indicators versus Watch (blocking; changes the schema)

Your brief lists `threat`, `indicator` and `decision` as node types, `threatens` and `indicated_by`
as edge types, and defines PIRs as "queries bound to specific nodes and the indicators that would
answer them", the threat register as the `threat -> indicated_by -> indicator` subgraph, and the
decision agenda as unresolved `decision` nodes.

**Observed:** Watch already is that. `claim` is the threat, `triggers` are its indicators (structured
clauses, compiled to predicates, prose rejected at load), `so_what.decision` is the `threatens` edge
to a decision, `expires` and `staleness_alert_days` are the horizon, and `belief` is the operator's
prior. Decisions already exist in Position with deadlines and stakes. Both are hand-authored YAML in
the private repo, which satisfies invariant 6 for free.

Building `threat` and `indicator` node types beside Watch produces two models of one idea. The repo
spent the last month collapsing exactly that (README vs CLAUDE.md; Decision+Factor vs Watch, see
`backlog/022` Q2), and the reason it kept happening was that each new brief re-described the old
concept under a new name.

**Recommendation (disagreeing with the brief):**

- Node types: `asset`, `person`, `institution`, `obligation`, `interest`, `decision`. Six, not eight.
- `decision` nodes are a **projection of Position** into the grid, written by the manual sensor, so
  edges (`requires`, `party_to`) can reference them. Position stays the source of truth.
- **PIR = Watch.** Extend the trigger clause vocabulary from `terms | entities | sources` with a
  fourth axis, `grid`, that Tier 1 evaluates against current state with no model:
  `{node: mortgage-main, field: rate, op: ">", value: 6.5}` or
  `{node: hoa-assessment, field: due, within: 30d}`. A watch may mix document clauses and grid
  clauses.
- Threat register and indicator graph are **views** over `watches` joined to `nodes`, presented as
  edge-shaped rows (`threatens`, `indicated_by`) by `estate query threats`. Nothing stores them
  twice.
- Two standing PIRs need no authoring at all and are not watches: "what is due or deciding within N
  days" and "what has not been observed within its horizon." Those are the `decide` and `unknown`
  sections and are pure grid queries.

If you overrule this and want `threat`/`indicator` as first-class nodes, say so and I will replan
section 3; the honest cost is that Watch then has to be retired, not kept alongside.

### 2.3 A second LLM pass versus invariant 4 (blocking)

Your analyst layer has two passes: triage (scored, structured) and synthesis (Claude writes brief
items from the subgraph plus the rules). The Stage 0 plan puts exactly one stochastic component in
the system and makes every downstream tier deterministic, on the argument that a fixed-length
narrative document emitted daily cannot carry information about whether anything happened.

**Observed:** every section you specified (`changed`, `decide`, `watch`, `unknown`) is computable
from grid state, evidence rows and watch state with no model call, and each item can cite the
observation ids it rests on by construction rather than by instruction. The one thing a synthesis
pass adds is prose over the world-side evidence: "this happened, and it matters because of that."
Note that the *join* itself ("matters because of that") is already the `so_what.decision` key plus
the routed evidence; the model would be writing it out, not discovering it.

**Recommendation:** ship the brief deterministic first (Phase 1c), then add synthesis as a
separately-flagged pass over the world-join section only (Phase 1e), with three rules: it never
gates the deterministic sections, every item it returns must cite observation ids that exist or the
item is rejected outright, and its prompt version is recorded on the output like evidence is. That
keeps invariant 4 honest (adjudication is still the only place a judgement is *made*; synthesis only
phrases judgements already recorded) and lets you read a brief without it to see whether it earns
its cost.

### 2.4 `ANALYSIS_RULES.md`

The epistemic-status labels, the "default to the weaker label" rule, the uncertainty-as-structure
rule, "do not recommend actions", and "do not anthropomorphize" all transfer directly. The
narrative-layers, fractures, bridges, and "what the coverage makes hard to see" sections belong to
the deleted product and have no input to operate on (there is no cluster of articles per
situation). Proposal: restore the file into `src/estate/ANALYSIS_RULES.md` with those sections
removed and a dated note saying what was cut and why. The four labels become the
`epistemic_status` enum, so the rule is a schema constraint on estate observations and a prompt rule
for synthesis, the same vocabulary in both places.

### 2.5 Smaller mismatches (observed)

- **Python version.** Brief says 3.10+. `pyproject.toml` requires `>=3.11`, ruff targets py311, CI
  runs 3.11 and 3.12, and `src/utils/__init__.py` uses `datetime.UTC` (3.11+). Plan assumes 3.11+.
- **Pydantic.** Only `pydantic-settings` is a declared dependency; no domain model uses pydantic.
  Position and Watch use frozen dataclasses with hand-written validators that report every problem
  at once. Pydantic v2's `ValidationError` collects all errors natively, so the new models can keep
  that property. I propose pydantic for everything under `src/estate/` and leaving Position/Watch
  as they are; converting them is churn with no behaviour change.
- **CLI.** click, not typer. The `estate` command will be click.
- **Package location.** Everything is imported as `src.*` and `pyproject.toml` packages `src*`
  only. A top-level `estate/` package would need packaging changes and would be the only module
  outside `src/`. I propose `src/estate/` with console script `estate = src.estate.cli:cli`.
- **"Situation analysis where it joins to estate nodes."** There is no situation analysis to join.
  The fifth section becomes "world-side evidence routed to watches this period", which is what Tier
  1 and Tier 2 produce.
- **Storage is SQLite already**; the live migrations directory is `src/database/migrations/`, and
  the pattern (create from model, `--confirm` on downgrade) is the one to follow.
- **The database file is inside the checkout** (`./data/insightweaver.db`). If the checkout is ever
  in a synced folder, so is the grid. `GETTING_STARTED.md` will say to set `DATABASE_URL` to a path
  outside any synced directory; I do not propose changing the default, because moving it silently
  would orphan an existing corpus.

---

## 3. Proposed schema

Three new tables, one view, one trigger, and one extension to an existing JSON column. Everything
additive; nothing existing is altered or dropped. Names carry a `grid_` prefix where an unprefixed
name would collide with or be confused for the world-side tables.

### 3.1 The rule for `observations` versus `grid_observations`

Stated up front, because task 014 found that two tables with no stated rule is the failure to
avoid:

- `observations` holds **what a source published**: a document, hashed over its content, in the
  outside realm. Written only by `src/sources/observation.py`.
- `grid_observations` holds **what a sensor asserted about a node**: one (subject, field, value) at
  one time, hashed over that assertion. Written only by `src/estate/store.py`.
- A grid observation that was grounded in a document carries `document_hash` pointing at it. A
  document never becomes a node and is never a subject.
- Evidence (`evidence` table) is the bridge from documents to watches and is unchanged.

### 3.2 DDL (SQLite)

```sql
CREATE TABLE nodes (
    id            TEXT PRIMARY KEY,                        -- operator slug, as watches.id is
    type          TEXT NOT NULL CHECK (type IN
                    ('asset','person','institution','obligation','interest','decision')),
    realm         TEXT NOT NULL CHECK (realm IN ('self','estate','outside')),
    label         TEXT NOT NULL CHECK (length(trim(label)) > 0),
    horizon_days  INTEGER NOT NULL CHECK (horizon_days >= 1),  -- per-type default, per-node override
    declared_at   DATETIME NOT NULL,
    retired_at    DATETIME                                  -- soft retire; never DELETE
);

CREATE TABLE grid_observations (
    id               TEXT PRIMARY KEY,                     -- 'sha256:' over the six hashed fields
    subject          TEXT NOT NULL REFERENCES nodes(id),
    field            TEXT NOT NULL CHECK (length(trim(field)) > 0),
    value            JSON NOT NULL,                        -- scalar or small object
    source           TEXT NOT NULL,                        -- sensor name: principal, google.calendar, simplefin, ...
    observed_at      DATETIME NOT NULL,                    -- when the source says it was true
    epistemic_status TEXT NOT NULL CHECK (epistemic_status IN
                       ('reported_fact','single_source_claim','consensus_view','speculation')),
    confidence       REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    document_hash    TEXT REFERENCES observations(content_hash),   -- grounding document, if any
    recorded_at      DATETIME NOT NULL                     -- when we stored it; NOT in the hash
);
CREATE INDEX idx_grid_obs_subject_field ON grid_observations(subject, field, observed_at);
CREATE INDEX idx_grid_obs_recorded ON grid_observations(recorded_at);

-- Same enforcement as observations: ORM guard plus a trigger, so sqlite3 cannot UPDATE either.
CREATE TRIGGER grid_observations_are_immutable BEFORE UPDATE ON grid_observations
BEGIN SELECT RAISE(ABORT, 'grid observations are immutable; insert a new one'); END;

CREATE TABLE edges (
    id           INTEGER PRIMARY KEY,
    src          TEXT NOT NULL REFERENCES nodes(id),
    type         TEXT NOT NULL CHECK (type IN
                   ('owns','depends_on','exposed_to','party_to','requires')),
    dst          TEXT NOT NULL REFERENCES nodes(id),
    asserted_by  TEXT NOT NULL REFERENCES grid_observations(id),
    retracted_by TEXT REFERENCES grid_observations(id),   -- set once, by a later observation
    UNIQUE (src, type, dst, asserted_by)
);
```

**Why edges are rows and not only observations.** "Nothing edits current state directly" holds:
an edge row is written by the same store path when it stores an observation whose field is
`edge:<type>` (value = `dst`, or `{dst, retract: true}`), and the row carries the observation that
asserted it and, later, the one that retracted it. The projection exists because a recursive CTE
over a JSON-valued observation table is unreadable, and the brief says to reach for `networkx` only
if SQL becomes unreadable. This is the cheaper fix. Current edges are `retracted_by IS NULL`.

**Hash.** `id = sha256(subject | field | canonical_json(value) | source | observed_at |
epistemic_status)` using the existing `content_hash()` from `src/sources/base.py`. `confidence`,
`document_hash` and `recorded_at` are outside the hash. Consequences, stated so they are tested
rather than discovered: re-running the manual sensor over an unchanged file inserts nothing,
because the file carries its own `as_of` dates; an API sensor that re-observes the same value with a
newer upstream timestamp inserts a new row, which is correct, because "seen again today" is what
refreshes staleness.

### 3.3 Current state

```sql
CREATE VIEW grid_current AS
SELECT o.id AS observation_id, o.subject, o.field, o.value, o.source, o.observed_at,
       o.epistemic_status, o.confidence, n.type, n.realm, n.horizon_days
FROM grid_observations o
JOIN nodes n ON n.id = o.subject
WHERE n.retired_at IS NULL
  AND o.field NOT LIKE 'edge:%'
  AND o.id = (
      SELECT o2.id FROM grid_observations o2
      WHERE o2.subject = o.subject AND o2.field = o.field
      ORDER BY o2.observed_at DESC, o2.id ASC LIMIT 1);
```

Staleness is **not** in the view, deliberately. The test suite freezes `TODAY`, and a view that
compared against `julianday('now')` would make the state of a fixture grid depend on the wall
clock. Freshness is computed by one function, `state(db, as_of)`, which reads `grid_current` and
labels each row `fresh` (age within horizon), `stale` (age past horizon; the brief prints "not
observed since <date>, horizon <n>d"), and reports `unknown` for any (node, required field) with no
observation at all. Per-type default horizons live in one dict in `src/estate/model.py`; a node's
YAML may override with `horizon: 90d` (parsed by `cadence.py`). Proposed defaults, to be confirmed
(Q9): asset 35d, obligation 35d, interest 180d, person 365d, institution 365d, decision = its
deadline, outside-realm nodes 35d.

### 3.4 Graph queries

Exposure surface, the query most triage reduces to:

```sql
SELECT e.src, e.type, e.dst, a.realm AS src_realm, b.realm AS dst_realm
FROM edges e JOIN nodes a ON a.id = e.src JOIN nodes b ON b.id = e.dst
WHERE e.retracted_by IS NULL AND a.realm <> b.realm;
```

Reach from an outside node into the estate (recursive CTE, depth-bounded):

```sql
WITH RECURSIVE reach(node, depth, path) AS (
    SELECT :start, 0, :start
    UNION ALL
    SELECT e.dst, r.depth + 1, r.path || '>' || e.dst
    FROM reach r JOIN edges e ON e.src = r.node
    WHERE e.retracted_by IS NULL AND r.depth < 6 AND instr(r.path, e.dst) = 0
)
SELECT r.node, r.depth, r.path FROM reach r JOIN nodes n ON n.id = r.node
WHERE n.realm IN ('estate','self');
```

### 3.5 The Watch extension

`watches.triggers` is JSON already. One new clause field, `grid`, validated in
`src/position/_validate.py` beside `terms | entities | sources`:

```yaml
triggers:
  - grid: { node: mortgage-main, field: rate, op: ">", value: 6.5 }
  - grid: { node: hoa-assessment, field: due, within: 30d }
  - entities: [Fairfax County]
    terms: [real estate tax, assessment]
```

`op` is one of `= != > < >= <= changed`; `within` is a cadence string against a date-valued field.
A `grid` clause naming a node or field that does not exist in the loaded estate is rejected at
load, the way `so_what.decision` naming an unknown decision is.

---

## 4. Models and the sensor interface

### 4.1 Pydantic models (`src/estate/model.py`)

```python
class Realm(StrEnum):            self = "self"; estate = "estate"; outside = "outside"
class NodeType(StrEnum):         asset, person, institution, obligation, interest, decision
class EdgeType(StrEnum):         owns, depends_on, exposed_to, party_to, requires
class EpistemicStatus(StrEnum):  reported_fact, single_source_claim, consensus_view, speculation

class Node(BaseModel, frozen=True):
    id: Slug                      # same regex Position uses for decision keys
    type: NodeType
    realm: Realm
    label: NonBlankStr
    horizon_days: PositiveInt     # defaulted from type at load, overridable

class Edge(BaseModel, frozen=True):
    src: Slug; type: EdgeType; dst: Slug

class GridObservation(BaseModel, frozen=True):
    subject: Slug
    field: NonBlankStr            # 'edge:<type>' is reserved
    value: JsonScalarOrObject
    source: NonBlankStr
    observed_at: datetime
    epistemic_status: EpistemicStatus
    confidence: Confidence        # 0.0..1.0
    document_hash: str | None = None
    @computed_field def id(self) -> str: ...   # sha256 per 3.2

class StateRow(BaseModel, frozen=True):        # what state(db, as_of) returns
    subject, field, value, source, observed_at, epistemic_status, confidence,
    observation_id, freshness: Literal["fresh", "stale", "unknown"], age_days: int | None
```

Every field is required; there are no defaults for `epistemic_status`, `confidence`, `observed_at`
or `source`. That matches the loader rule the repo already follows (reject, never default). The
manual YAML format lets a *file* declare `epistemic_status:` and `confidence:` once at the top and
each entry inherit them; that is still an explicit operator statement, not a code default.

### 4.2 Sensor interface (`src/estate/sensors/base.py`)

```python
@runtime_checkable
class Sensor(Protocol):
    name: str                                  # written to grid_observations.source
    def collect(self, since: datetime | None) -> list[GridObservation]: ...
```

Rules, each tested rather than documented:

- A sensor **returns observations and nothing else**. It receives no session and cannot write.
  The runner stores through the one path, records per-sensor counts, and logs "returned zero after
  returning some before" the way `src/sources/runner.py` does for adapters.
- A sensor that cannot reach its upstream **raises** `SensorUnavailable`; it never returns `[]` for
  an outage. Same rule as `SourceUnavailable`, same reason.
- A sensor names only nodes that exist. An observation whose subject is not a declared node is
  rejected by the store, not auto-created; sensors observe, the operator declares.
- Sync, not async. The Google and SimpleFIN client libraries are synchronous, and the whole set is
  a handful of requests. The RSS adapters stay async and stay separate.
- Registry: `SENSOR_FACTORIES: dict[str, Callable[[], Sensor]]`, mirroring `ADAPTER_FACTORIES`.
  An unknown sensor name in config is an error, not a skip.

The **manual sensor** reads a directory (`ESTATE_PATH`, default `~/.config/insightweaver/estate/`,
in the private repo beside Position):

```
estate/
  position.yaml        # existing; projected to decision nodes (realm self)
  watches.yaml         # existing; PIRs
  nodes/*.yaml         # declarations + hand-entered observations
```

```yaml
# nodes/housing.yaml
epistemic_status: single_source_claim     # file-level; entries may override
confidence: 0.9
nodes:
  - id: house-main
    type: asset
    realm: estate
    label: Primary residence
    edges:
      - { type: owns, from: principal }          # principal is the required realm-self person node
      - { type: exposed_to, to: fairfax-county }
    observe:
      - { field: assessed_value, value: 812000, as_of: 2026-07-01, source: "county notice" }
      - { field: insurer, value: acme-mutual, as_of: 2026-01-15 }
```

`as_of` is required on every hand-entered value and is `observed_at`; the sensor never substitutes
the clock. `source` on an entry is appended to the sensor's own name (`principal: county notice`)
so the provenance says where the principal got it.

The **existing RSS and Federal Register adapters** are not sensors and do not change. They produce
documents; Tier 1 routes documents to watches; Tier 2 adjudicates; evidence is what the brief
reads. If a world fact should become a node field (for example an `institution` node in the outside
realm with a `last_action` field), that is a grid observation carrying `document_hash`, written by
the operator through `estate validate`, or later by a sensor that is explicitly built to do it.
Nothing in Phase 1 writes grid observations from a model response.

---

## 5. Phased delivery

Every phase lands as one or more pull requests, each specified first as `backlog/NNN-*.md` with
ACCEPTANCE, OUT OF SCOPE and LANDMINES, per the repo's convention. Sizes use `CLAUDE.md`'s scale.
Nothing merges itself.

### Phase 0: hygiene and decisions (small; one PR)

- `.gitignore`: `data/llm-audit/`, `data/exports/`, `estate/` (a real one at the repo root),
  `*.sqlite`, OAuth token files by name.
- Secret scanning in pre-commit and CI. `detect-private-key` is not it. Proposal: `detect-secrets`
  (pip-installable, fits `requirements-dev.txt`, baseline file committed); gitleaks is the
  alternative if you prefer a compiled scanner. Make the CI security job fail on a hit.
- Add `keyring` and `pydantic` (explicit) to dependencies. Raise the `anthropic` pin so
  `output_config` is a real parameter (section 6.1); this is the moment to do it because the
  `extra_body` workaround and structured output cannot both be sent.
- `ClaudeClient` gains the outbound audit log and returns usage (section 6.1). No caller yet.
- Backlog: write tasks 026 onward; mark 019/020/023 superseded (pending Q1); rescope 015/016 as
  Phase 1d.
- `docs/RECONCILIATION.md` gets a dated addendum saying the estate plan is now the plan.

### Phase 1: the smallest real brief

**1a: the grid (medium).** `src/estate/model.py`, `store.py` (one write path, tree-grep test like
`TestOneWritePath`), `graph.py` (state, exposure, reach), the migration
`src/database/migrations/add_grid_tables.py` (created from models, `--confirm` down), the fixture
estate in `tests/estate/fixtures/` (a fictional household: one principal, a house, a mortgage, two
institutions, one obligation, one interest, two decisions, three watches), and `estate status`,
`estate query {node,state,exposure,reach,threats,changes}`. No sensors yet; the fixture is loaded by
the tests.

**1b: the manual sensor and feedback (medium).** YAML format and loader (reject-not-default;
every problem reported at once), projection of Position into decision nodes, sensor runner,
`estate observe [--sensor NAME] [--dry-run]`, `estate validate <node> <field> [--value] --as-of`,
`estate decide <decision> --outcome`. Both feedback commands write observations with
`source = principal` and nothing else. `estate observe` twice over an unchanged directory inserts
zero rows, tested.

**1c: the brief, deterministic (medium).** `estate brief [--since] [--as-of] [--format terminal|md]
[--output PATH]`. Sections in fixed order:

1. `changed`: (subject, field) pairs whose current value differs from the value before `since`,
   with old and new, source, label; watch belief transitions once 017 exists.
2. `decide`: decision nodes with deadline within the window or past; obligations with `due` in the
   window; each listing the nodes it `requires` and their freshness.
3. `watch`: every live watch: belief, decision, days to expiry, evidence count since `since`, most
   recent evidence, staleness state.
4. `unknown`: stale rows ("not observed since"), required fields never observed, watches with zero
   routed observations for `staleness_alert_days`, sensors that did not run or returned nothing.
5. `world`: evidence rows since `since` grouped by watch, each with document title, source,
   published date, direction, magnitude, prompt version. Empty until 1d lands, and says so.

Every item prints the observation ids it rests on. The brief is a pure function of (database,
`as_of`, `since`); a test renders the fixture twice and asserts identical bytes. It records its own
delivery as a grid observation on the principal node (`field: brief.delivered`), which is how
"since last run" is derived and is harmless to repeat. `ANALYSIS_RULES.md` is restored here in its
trimmed form because the epistemic labels are printed on every line.

**1d: triage (large; this is tasks 015 and 016, rescoped).** Tier 1 routing with the `grid` clause
axis; `estate route --dry-run` reporting per-watch candidate counts and the unrouted count; the
ceiling test. Tier 2 `ClaudeAdjudicator` registered under a prompt version, structured output
validated against a pydantic `Verdict` schema, a failed validation recorded as a failed
adjudication and never retried into a different answer, every request written to the audit log
with node ids and the fields the watch needs and nothing else, tokens and cost recorded per run.
`estate brief` section 5 fills in. Replay from 014 reproduces the evidence.

**1e: synthesis (medium; conditional on Q2).** `estate brief --synthesize`: hands Claude the
world-join items, the relevant subgraph as (node id, field, value, epistemic label) rows, and the
rules; receives structured items each with `cites: [ids]`; rejects any item citing an id that does
not exist; prints them under section 5 with the prompt version. Off by default.

### Phase 2: Google sensors (large)

Three sensors under `src/estate/sensors/google/`, scopes `gmail.readonly`, `calendar.readonly`,
`drive.metadata.readonly` (metadata only unless a node binding needs content; assumed sufficient,
to be confirmed). OAuth installed-app flow: the consent step opens a temporary loopback listener
once, which your constraints permit; refresh token stored under `keyring` service
`insightweaver`, never on disk in the clear. **The real work is the binding**, not the client: each
node's YAML declares what the sensor may observe about it (`google.calendar: {match: ["HOA"],
field: next_meeting}`; `google.gmail: {from: ["*@acme-mutual.example"], field: last_contact}`),
and the sensor emits only the bound fields. Message bodies never leave the machine and never enter
a prompt. Each sensor is tested against recorded API responses, offline.

### Phase 3: finance (medium)

**Recommendation: SimpleFIN, with one caveat to verify before enrolling.** Reasons: the protocol
has no write operations at all, so "read-only by construction" is a property of the API surface
rather than of a scope you request; access is a single bearer-style URL, which fits `keyring`
exactly; there is no developer application, production-access review, or per-item billing, which
Plaid requires and which is disproportionate for one principal; and Plaid's API surface includes
money-movement products, so proving nothing in this system can move money means proving a negative
about scopes rather than about the protocol. The caveat (assumed, not verified here): SimpleFIN
Bridge is a small operator relying on an upstream aggregation provider, and its institution
coverage and data-retention terms should be checked against your actual institutions before
Phase 3 starts. If a needed institution is missing, Plaid is the fallback and the sensor interface
does not change. Observations per account node: `balance`, `available`, `last_transaction_at`, with
`observed_at` from the aggregator's own timestamp and `epistemic_status: single_source_claim`.

### Phase 4: MCP server (medium)

`src/estate/mcp.py`, stdio transport, `mcp` SDK dependency, four read-only tools (`query_grid`,
`changes_since`, `list_pirs`, `list_decisions`) that call the same `src/estate/graph.py` functions
the CLI does. No tool writes. A test asserts the server registers no tool whose handler reaches the
store module.

### Deferred

FastAPI on loopback: not planned until asked. Deleting `migrations/` (top level): its own small
task. Backfilling observations for the pre-rewrite `articles` rows: unchanged from task 014's
decision.

---

## 6. Every change to existing behaviour

1. **`src/llm/claude_client.py`.** (a) Every request is appended to `data/llm-audit/<date>.jsonl`
   before it is sent: model, system, messages, schema, prompt version if any, payload sha256; the
   response usage is appended after. There is no way to call the client without logging. (b)
   `analyze()` returns usage alongside text (a small result object) instead of discarding it; the
   only current callers are tests. (c) Effort moves from `extra_body` to `output_config` once the
   SDK pin is raised, and structured output goes in `output_config.format` beside it. (d) Model
   default stays `claude-sonnet-5` unless you say otherwise (Q11). (e) `parse_claude_json` is not
   used by triage; returning `{}` on failure is a silent fallback and triage records failures.
2. **`src/position/_validate.py`, `watches.py`, `config/watches.example.yaml`.** The `grid` clause
   axis. Existing files stay valid; the four-axis vocabulary is a superset.
3. **`src/position/watches.py::sync_watches`.** Delete becomes soft retire (`retired_at`), before
   any history hangs off the rows. Task 017 already names this; the brief citing watch ids makes it
   due now.
4. **`src/config/settings.py`.** New settings: `estate_path`, `llm_audit_dir`, keyring service
   name. `POSITION_PATH` and `WATCHES_PATH` keep working and may point inside `estate_path`.
5. **`pyproject.toml`.** Second console script `estate`; dependencies `pydantic`, `keyring`; later
   `google-api-python-client`, `google-auth-oauthlib`, `mcp`; `anthropic` pin raised; new mypy
   override only if the models module needs one (the goal is that `src/estate/` does not).
6. **`.gitignore`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`.** Section 5, Phase 0.
7. **Backlog.** 015/016 rescoped into Phase 1d; 019/020/023 superseded (Q1); 018 rewritten for a
   laptop; 022 gains the answers to section 7; new tasks 026+.
8. **`README.md`, `GETTING_STARTED.md`, `docs/CONCEPTS.md`.** All three carry a superseded banner
   today. Q12 asks whether Phase 1 rewrites them or only adds the required sections.
9. **`CLAUDE.md` North Star.** The "Questions are the join key" paragraph describes deleted
   entities. The estate version is: nodes are the join key; watches key off decision nodes;
   evidence keys off watches; the brief is a derived view over grid state and evidence. Proposed as
   a one-paragraph edit in Phase 0, for your approval, since `CLAUDE.md` is your file.

Not changed: `observations`, `evidence`, replay, the adapters, `entity_matcher`, `minhash`,
`cadence`, `articles`, `rss_feeds`, the `insightweaver` command and its three subcommands.

---

## 7. Open questions

### Decided 2026-09-22

**Q1. Laptop plan is canonical.** Tasks 019, 020 and 023 are retired as written; 018 is rewritten
for a laptop; 022's Q6 (dead-man's switch channel) is closed as moot.

**Q2. Deterministic brief first; synthesis is an opt-in pass in Phase 1e, still inside Phase 1.**
Operator's answer was "whatever works best based on my intent", so the reading of intent is
recorded here so it can be corrected: the brief's value is the join between an outside event and
an estate node, and that join is structural (evidence -> watch -> `so_what.decision` -> node), not
prose. The deterministic brief carries the join on every line and cites the observation ids it
rests on. Synthesis phrases judgements already recorded; it never makes one, never gates a section,
and is rejected item-by-item if it cites an id that does not exist. It ships in Phase 1 rather than
later so the operator can read the same morning with and without it and decide whether it becomes
the default. If the deterministic brief reads as a table rather than a brief, that is the signal to
flip the default, and it costs one flag.

**Q3. PIR = Watch.** Six node types, five edge types, `grid` trigger axis; threat register and
indicator graph are views over `watches` joined to `nodes`.

**Q4 / Q7. Two observation tables, no rename.** `observations` stays what a source published;
`grid_observations` is what a sensor asserted about a node; the rule in section 3.1 is written into
`src/database/models.py` beside task 014's rule. Judgement call: the rename would touch task 014's
code, tests, docs and the `replay` command for a vocabulary gain only, and the repo has been bitten
by churn that changed names without changing behaviour.

**Q5 / Q13. Belief has one ledger.** A new append-only `watch_beliefs` table (`watch_id`, `belief`,
`source`, `observed_at`, `note`), written from exactly two places: `sync_watches` writes a row with
`source = file` when a watch is added or its file belief changes, and `estate validate --watch <id>
--belief X` writes a row with `source = principal`. `watches.belief` stops being overwritten by
sync and becomes the value at registration; current belief is the latest ledger row. Task 017's
transitions append to the same ledger with `source = evidence:<prompt_version>`. Every belief value
therefore has a provenance and a date, the file is the prior, and there is no second path. This is
the "holistic" reading: one mechanism for operator feedback (`validate`, `decide`) whichever ledger
the subject lives in, and no grid observation with a subject that is not a node.

**Q8. Edges as provenance-carrying rows**: accepted under Q4's "use your judgment".

**Q12. Docs.** `README.md`, `GETTING_STARTED.md` and `docs/CONCEPTS.md` are rewritten for the
estate product in Phase 1c, when there is a brief to describe. They are already banner-marked
superseded, so a partial edit would leave a document that is half history and half current, which
is worse than either.

**Q15.** Closed as moot with Q1.

**Q4 (package). `src/estate/`** with console script `estate = src.estate.cli:cli`.

**Q5 (key). The Anthropic key moves to `keyring`** (service `insightweaver`, username
`anthropic_api_key`) in Phase 0, set once with `estate auth set anthropic`. The `.env` path is
removed, not kept as a fallback. A missing key fails at the point a model call is constructed,
never at import.

**Q6 (YAML). One private directory**, `ESTATE_PATH`, holding `position.yaml`, `watches.yaml` and
`nodes/`. `POSITION_PATH` and `WATCHES_PATH` keep working.

**Q9 (horizons). The defaults in 3.3 stand** until real nodes say otherwise; a node overrides in
its own YAML.

**Q10 (labels). File-level declaration, entries inherit**, `single_source_claim` in the examples.

**Q11 (models). Opus 5 (`claude-opus-5`) for synthesis, Sonnet 5 (`claude-sonnet-5`) for
adjudication**, as two named settings so neither is chosen at a call site.

**Q14 (corpus). Triage starts against an empty `observations` table here**; the operator points
`DATABASE_URL` at the real corpus when running it.

**Go.** Phase 0 approved 2026-09-22.

### Still open

Nothing blocking. Questions raised by later phases are added here as they arise.

---

## 8. What I assumed

- That the private-repo pattern for Position is the pattern you want for all estate YAML.
- That your laptop is the only runtime and you will run `estate observe` and `estate brief` by
  hand; nothing here schedules anything.
- That Google Drive metadata (names, modified times, owners) is enough for the bindings you have in
  mind; content scopes are a different conversation.
- SimpleFIN's current provider, coverage and retention terms, which I did not verify.
- That `make check` passes on `main` today; I could not run it here (no environment).
