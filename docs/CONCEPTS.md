# InsightWeaver Concepts

The entity-by-entity reference for the decision monitor. Rewritten 2026-09-23 (backlog task
033) from the code as it stands; the earlier commitment graph of questions, predictions and
frames was deleted on 2026-08-31 and is described only in git history and
`docs/RECONCILIATION.md`.

## The shape of the thing

Decisions are the root. A watch is a claim that would change one decision, written before any
document arrives. Observations are what sources published. Routing links observations to
watches by rule. Adjudication asks a model whether a linked pair is evidence. Beliefs and
grades are the operator's. The brief is a view over all of it, as of a moment.

```
Position (decisions)            hand-authored, private
   |
Watch (claim, triggers)         hand-authored, private; the join key
   |
Observation <-- Route --> Watch     deterministic, no model
   |
Adjudication --> Evidence           one model call per routed pair
   |
Belief ledger, Resolution           operator only
   |
Brief                               derived view, deterministic to the byte
```

## Position and Decision

`position.yaml`, at `POSITION_PATH`, outside this repository. It holds `version`, `reviewed`
(the date the operator last sat down with the file) and `decisions`. A decision has:

- `key`: a slug, referenced by watches;
- `name`: one sentence the operator could act on;
- `deadline`: a date. The loader refuses a decision without one, because a decision with no
  date is an interest, and interests are not what the system is for;
- `stake`: what is worse if the decision goes wrong. Missing, the loader warns.

The loader (`src/position/position.py`) refuses structural problems, all of them at once, and
warns rather than refuses on drift: a file past two pages, a deadline already passed, a
decision with no stake. The brief carries a banner when `reviewed` is more than 90 days old, or
absent, or when the file could not be read at all.

## Watch

`watches.yaml`, at `WATCHES_PATH`, beside the Position. A watch is one pre-registered claim
serving one decision. Every field is required and none defaults (`src/position/_validate.py`):

- `id`: a slug; the name every brief line carries;
- `claim`: the thing that is or is not true, phrased so that afterwards the operator could say
  which;
- `belief`: the operator's probability at registration, 0.0 to 1.0. This is the prior; the
  ledger below holds every later value;
- `so_what.decision`: a key from the Position. A watch naming no decision, or an unknown one,
  is refused (invariant 2);
- `so_what.because`: what changes for that decision if the claim resolves. Printed back in the
  adjudication prompt as the operator wrote it, never paraphrased;
- `triggers`: a list of clauses, below;
- `expires`: when the question stops mattering. Routing ignores an expired watch, and the brief
  lists an expired, unresolved watch under DUE. The loader refuses a file that holds a watch
  whose `expires` has passed, so the next `watch sync` fails until the operator grades the
  watch (`watch resolve`) and then moves its date or removes it; removing it retires it, and a
  retired watch leaves DUE;
- `staleness_alert_days`: after how many days with nothing routed the silence is itself
  reported. A whole number of days or a cadence string such as `2w`.

**Triggers.** A clause is a mapping over `terms`, `entities` and `sources`. Within a clause
every populated field must match; within a field any listed value will do; across clauses any
one firing routes the observation, and the first that fires is recorded. `terms` and
`entities` compile to word-boundary patterns (`CISA` is not inside `precisa`), and an all-caps
term matches case-sensitively (`BOD` matches, `body` does not). `sources` is a case-insensitive
exact match on a configured source's name. A trigger written as prose is refused by the loader
and again by the compiler (`src/routing/compile.py`), because a trigger that cannot be compiled
never fires, and the deleted prediction ledger held 33 free-text triggers that were never
graded for exactly that reason.

**Sync.** `insightweaver watch sync` is the only path from the file to the `watches` table. A
watch that leaves the file is retired (`retired_at`), never deleted, because ledger rows and
evidence hang off it; a watch that returns is restored. There is no `watch add` (invariant 6).

## Source and Observation

A source is a row in `rss_feeds`: a configured feed from `config/feeds/`, or an adapter such
as the Federal Register documents API. Every adapter (`src/sources/`) emits the same
normalized item and stores it through one path, `src/sources/store.py`. An adapter that
cannot reach or cannot understand its upstream raises `SourceUnavailable`; it never returns an
empty list. Each attempt stamps the source row with its time and its error, if any, which is
what the brief's header prints.

An observation (`observations`) is one thing a source published:

- keyed by `content_hash`, a SHA-256 over the normalized payload, which includes the item's URL
  and the source's URL, so re-fetching an unchanged document is a no-op while the same text from
  two sources is two rows: who said it is part of what was observed, and grouping the pair back
  together is the MinHash signature's job;
- immutable: an ORM update raises `ObservationIsImmutable`, and a database trigger refuses an
  `UPDATE` issued any other way (invariant 3);
- signed: a MinHash over five-word shingles is written beside the payload, and
  `NEAR_DUPLICATE_THRESHOLD` (default 0.7) decides when two observations are one story. The
  brief groups a watch's evidence by these clusters, so twelve outlets carrying one wire story
  are one item with twelve citations.

`published_date` is the source's date when it gave one; `observed_at` is when the row was
written. Ordering in the brief is by published date, then observed date, then hash, so it is
total.

## Route

Tier 1. `insightweaver route` compiles every live watch's triggers, evaluates them over the
observations in the window, and writes one `routes` row per (observation, watch) that
matched, with the clause index that fired and when it was routed. The table is derived and
rebuildable (`route --rebuild` discards the live watches' links and routes the whole corpus
again; the new rows carry the rebuild's time, so QUIET's silence clock restarts for every watch
that matches anything). No model is involved; the routing regression test plants exact matches and near-miss substrings
and asserts which route.

Everything that does not route is reported, grouped by near-duplicate cluster and by source,
because a trigger that misses is the operator's to fix and the report is where they see it.

## Adjudication and Evidence

Tier 2, and the only model call in the system (invariant 4). `insightweaver adjudicate` takes
every routed pair on an open watch that the current prompt version has not answered and asks
the model one structured question: does this item bear on this claim, in which direction, how
strongly, satisfying which clause, and why. The question is `src/evidence/prompt.py`; the
answer is validated against a pydantic schema (`src/evidence/claude_adjudicator.py`).

- An **adjudication** (`adjudications`) is one call about one pair, whatever it answered:
  `evidence`, `none`, or `failed`, with the audit id, the token counts the API reported, and
  the rationale. A pair is asked once per prompt version, with one gap: `replay --commit`
  writes evidence and no adjudication row, so a pair a replay judged not to be evidence is asked
  once more by `adjudicate`. A failed call is recorded, not retried; retrying until an answer
  looks right would make the replay below meaningless.
- **Evidence** (`evidence`) is the subset that bore on the claim: `direction` (`supports` or
  `contradicts`; there is no neutral row), `magnitude` (a strength of bearing, not a
  probability), and the `prompt_version` that produced it, per row.
- An API outage or a rejected request is neither an answer nor a verdict: the run stops with
  the pair left pending, and the brief counts pending pairs under QUIET.

**Prompt versions and replay.** The version written on every row is a hand-maintained label
(`claude-v1`). The prompt, its effort level, its caps and the schema are hashed into a
fingerprint that a test pins to that label, so a change to any of them fails the suite until
the label is bumped; a version cannot drift under the rows that carry it. `insightweaver replay
--prompt-version V` rebuilds evidence for a version over the routed pairs and diffs it against
what is stored, writing nothing; `--commit` replaces that version's rows and is the only path
that deletes evidence. The test suite's adjudicators are keyword stubs that live in the test
tree on purpose, so the replay machinery is exercised without a key.

**The audit log.** `src/llm/audit.py` writes every request, in full, to `data/llm-audit/`
before it is sent, and the usage and stop reason of every response after. There is no way to
send a request without writing it. The log is for the operator's eyes; it is not a cache.

## Belief ledger and Resolution

`watch_beliefs` is append-only, enforced by database triggers and ORM guards. The first row
for a watch is the file's `belief`, labelled `file`, written at sync. `insightweaver watch
believe ID P --note` appends a row labelled `principal`; it refuses a retired watch (put it back
in the file and sync first). The file stays authoritative: whenever a sync finds the file's
belief different from the current belief, including after the operator moved it, it appends a
`file` row with a note naming the value it replaced. That is a recorded change, never a silent
overwrite, and it means the number in the file should be kept in step with the ledger or the
next sync moves the belief back (decided in backlog task 030). No code path in the tool moves a
belief on its own; a belief update rule is deferred until there are resolved watches to
calibrate one against.

`insightweaver watch resolve ID --outcome yes|no --note` grades the claim, once, and sets
`resolved_at` on the watch. A resolved watch takes no further belief and leaves routing. A
retired watch may still be graded, because the operator may learn the answer after removing
the claim from the file.

## Brief

`insightweaver brief` is a pure function of the database, `--since` and `--as-of`
(`src/brief/select.py` selects, `src/brief/render.py` prints). No clock is read in the render
path, no iteration is unordered, and the golden test renders twice and compares bytes. Five
parts, in fixed order:

1. **Header**: as of, the window, the Position's reviewed date with days since and the banner,
   and one line per source with its last attempt (labelled as a failure when it was one) and
   its count in the window.
2. **MOVED**: every watch that gained evidence in the window, live or not, with each cluster of
   near-duplicate observations as one item citing hash, source, date, title, direction,
   magnitude and prompt version.
3. **DUE**: decisions with a deadline inside the next 30 days or already past; open watches
   expiring inside that horizon or already expired and unresolved.
4. **WATCHING**: every live watch with its belief as of the moment, its source and date, the
   decision it serves, days to expiry, evidence in the window and the date of the last
   evidence.
5. **QUIET**: watches with nothing routed inside their staleness window, sources that ran and
   returned nothing, routed pairs no adjudication has answered, failed adjudications. Printed
   with zeros; that is when the section carries information (invariant 5).

A row in `briefs` records each render. The next brief's default window opens at the last brief
delivered before the start of today, so a second run the same morning reproduces the first
instead of reporting "nothing since ten minutes ago". `--dry-run` renders without recording.

## Invariants

1. Nothing sends.
2. Every watch names a decision.
3. Observations are immutable; evidence is derived.
4. One stochastic component.
5. Silence is distinguishable from breakage.
6. The system never authors watches.

Each has a test that would fail if a change broke it; the tests are the specification.

## What is not modeled

- **Unknown unknowns.** The tool does not fabricate observables it cannot ground. A claim with
  no trigger words is a claim that will never route, and the loader says so.
- **Truth.** No entity stores a truth value. A resolution records that the operator graded the
  claim, not that the tool judged it; evidence records bearing, not correctness.
- **Frames.** The earlier product modeled the frame each source exhibits. The monitor does
  not, and README.md says so under the third principle.
- **Automatic belief.** Every belief row was written by a person.
