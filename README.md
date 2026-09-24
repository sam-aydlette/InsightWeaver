# InsightWeaver

A compass for insight at cybernetic speed.

In land navigation you don't walk with your face in the compass. You shoot an azimuth to a
point you can actually see, drop the compass to your side, and walk to it -- counting paces,
reading the terrain, following a handrail where the ground gives you one. You picked that
azimuth once, at the start point, relative to where you actually stood and where you actually
needed to go. The compass doesn't know what's out there. It only gives you a bearing, and the
bearing only means anything once you've oriented it to your own position on the map -- there's
no reading a compass from nowhere.

Most information tools skip the orientation step. They hand you volume in the general direction
of "everything," which isn't a bearing at all -- it's what you get when you start walking before
you've found your position on the map. InsightWeaver asks for the start point first: the
decisions you are actually carrying, each with a real deadline. A **watch** is the azimuth shot
to one of them -- a specific claim, at a specific bearing, that would move you if it turned out
true. Routing is pacing toward it. Adjudication is terrain association: does what you're
passing actually confirm the bearing, or is it a lookalike a keyword caught without being on
the route. And when nothing has confirmed the route in longer than expected, that's not
silence to read as "all clear" -- it's the catching feature telling you that you may have
drifted, and the tool says so instead of staying quiet about its own quiet.

Nothing in it authors a watch, moves a belief, or sends anything anywhere. It runs on your
laptop, from the command line, when you run it.

```
insightweaver run
```

## Status, stated plainly

- The monitor runs end to end: ingestion, deterministic routing, one structured model call per
  candidate pair, an append-only belief ledger, hand grading, and the brief. `make check` runs
  lint, types and the suite, and a golden-file test drives a recorded Federal Register week and
  a recorded feed through `watch sync`, `ingest`, `route`, `adjudicate` and `brief` with a
  scripted model and a frozen clock.
- Track record builds from your own watches resolving against your own coverage, week over
  week (`docs/PLAN.md`, section 5, is the plan it's measured from). Read the QUIET section of
  every brief; it's where a run tells you where it might be missing something, instead of
  staying quiet about its own silence.
- `articles` is the table the product this one replaced ingested into. Ingest still writes a
  row there beside each new observation, and `sources list` counts them; the rows written before
  the rewrite have no observation and nothing in the monitor reads them. The rule is in
  `src/database/models/__init__.py`.
- The earlier product, a daily synthesis over questions, predictions and frames, was deleted on
  2026-08-31 in one commit. Git history is where it lives; `docs/RECONCILIATION.md` says why.

## The idea

Every platform you use is already a feedback loop: it reads what moves you, adjusts what it
shows you, and reads the result -- steering, continuously, at whatever speed its infrastructure
allows. That's not a metaphor; it's how a recommendation system is built, and it is cybernetics
in the original sense of the word, steering. The asymmetry is that the loop steers toward the
platform's ends, not yours, and it moves faster than you can audit it.

The individual-scale answer isn't to opt out of information -- that just hands the steering to
someone else's loop by default. It's to build your own, deliberately, at the same speed, and
keep it in view instead of behind an interface. A watch is the stake in the ground: a claim,
tied to a decision you're actually carrying, that you commit to caring about before anything
happens, so that what arrives afterward has a bearing to be measured against instead of just
adding to the pile. Routing, one model judgment per candidate, and an append-only record of what
you believed and when are the loop itself, running for you, on your terms, on your machine.

The design follows from five principles the project has kept since it began. Each is stated
with how this build carries it, or does not.

1. **Insight over information.** The brief has no headline list. Its unit is a watch that gained
   evidence, and a watch exists only because a decision needs it.
2. **Warranted trust over projected confidence.** Every evidence line carries the observation
   hash it rests on, the source, the direction, a magnitude, and the prompt version that judged
   it. A belief is a number the operator wrote, with a date and a note, never one the tool
   inferred.
3. **Frame visibility over false balance.** Not implemented in this build. The monitor has no
   notion of a frame; it returns, if it does, with the deferred synthesis pass (`docs/PLAN.md`,
   section 8).
4. **Epistemic autonomy as the goal.** There is no view from nowhere for the tool to hand you a
   conclusion from -- it reports that an item bears on a claim and how strongly, from the bearing
   you already staked. What that means for the decision is the operator's, and the `so_what` the
   operator wrote is printed back, not paraphrased.
5. **Honest self-awareness about the tool's own narrative.** A brief that looks the same when
   nothing happened and when the pipeline is broken is the failure the design exists to prevent.
   The header names every source whose last attempt failed, in full, by default; a summary
   count covers the rest (`--verbose` lists every source). QUIET prints every watch that
   heard nothing, every source that ran and returned nothing, every routed pair no adjudication
   has answered, and every model call that failed, with zeros when there are none. Every model
   request is written to a local audit log before it is sent, and each response's usage after.

## How a morning runs

| step | command | what it does | writes | model |
|---|---|---|---|---|
| 1 | `insightweaver ingest` | reads every configured source through the adapter layer and stores what is new, content-addressed | `observations`, `articles`, `rss_feeds` | no |
| 2 | `insightweaver route` | compiles each live watch's triggers to word-boundary rules and links matching observations | `routes` | no |
| 3 | `insightweaver adjudicate` | one structured call per routed pair that this prompt version has not answered; records every outcome, retries nothing | `adjudications`, `evidence`, audit log | yes |
| 4 | `insightweaver brief` | renders the brief as of now, deterministic to the byte | `briefs` | no |

`insightweaver run` chains the four and stops at the first that fails. Belief and grading are
separate, by hand: `watch believe` appends to the ledger, `watch resolve` grades a claim yes or
no, once.

The brief, in fixed order:

```
BRIEF AS OF 2026-08-24 06:00
window: since 2026-08-17 06:00
position: reviewed 2026-08-01 (23 days ago)
sources: 4 configured, 3 fetched, 1 failed, 0 never fetched (--verbose for every source)
* Broken Feed: LAST ATTEMPT FAILED 2026-08-24 06:00: HTTP error: connection refused; 0 in window

MOVED
-----
* nist-site-rules-loosen: NIST relaxes the conduct rules at its sites before the visit is scheduled.
  * supports 0.80  2026-08-21  Federal Register - Documents API: Traffic and Conduct on the Grounds of Certain National Institute of Standards and Technology Sites  [sha256:841e04c37028, claude-v1] (+1 near-duplicate)
    * also supports 0.80  2026-08-21  Compliance Weekly: Traffic and Conduct on the Grounds of Certain National Institute of Standards and Technology Sites  [sha256:8f54b09130d9, claude-v1]
* opm-benefit-forms-change: OPM reopens comment on the retirement benefit application forms.
  * supports 0.55  2026-08-20  Federal Register - Documents API: Submission for Review: 3206-0156, Application for Death Benefits Under the Civil Service Retirement System, (SF 2800); Documentation in Support of Application for Death Benefits When Deceased was an Employee at the Time of Death, (SF 2800A) and Applying for Death Benefits Under CSRS Pamphlet, (SF 2800-1)  [sha256:c2fcbdff3a66, claude-v1]

DUE
---
* decision schedule-site-visit: Schedule the NIST site visit before or after the conduct rule changes (2026-09-10, 17 days)
  * stake: Two travel days and the assessor's calendar, against a visit under rules that change mid-stay.
* watch nist-site-rules-loosen: NIST relaxes the conduct rules at its sites before the visit is scheduled. (expires 2026-09-15, 22 days)

WATCHING
--------
* dfars-cyber-reporting: belief 0.20 (file, 2026-08-24); serves renew-authorization; expires in 160 days; evidence in window 0, last never
  * DFARS adds a cyber incident reporting collection before the renewal.
* nist-site-rules-loosen: belief 0.30 (file, 2026-08-24); serves schedule-site-visit; expires in 22 days; evidence in window 2, last 2026-08-24
  * NIST relaxes the conduct rules at its sites before the visit is scheduled.
* opm-benefit-forms-change: belief 0.50 (file, 2026-08-24); serves renew-authorization; expires in 219 days; evidence in window 1, last 2026-08-24
  * OPM reopens comment on the retirement benefit application forms.

QUIET
-----
watches with nothing routed inside their staleness window: 1
* dfars-cyber-reporting: never routed (alert after 7 days)
sources that ran in the window and returned nothing: 1
* Agency Newsroom (never produced)
routed pairs no adjudication has answered: 0
failed adjudications in the window: 1
* sha256:ebf02a3e9ea4 / opm-benefit-forms-change [claude-v1]: Model declined the request (category: scripted)
```

That is `tests/brief/golden/brief.txt`, whole, which the suite regenerates only through
`make golden` so that a change to the brief is a diff a reviewer reads.

## The model

Two hand-authored files, kept in a private repository and pointed at by `POSITION_PATH` and
`WATCHES_PATH`, are the whole input the operator writes. `config/position.example.yaml` and
`config/watches.example.yaml` show the shape.

- A **Position** is the decisions being carried. A decision has a key, a name, a deadline and a
  stake. A decision without a deadline is an interest, and the loader refuses it.
- A **Watch** is one pre-registered claim serving one decision: the claim, the operator's belief
  at registration, why it matters to that decision, structured triggers, an expiry, and how many
  days of silence should be reported. Triggers are a list of clauses over `terms`, `entities`
  and `sources`; within a clause every populated field must match, across clauses any one
  firing is enough, and a trigger that cannot be compiled is refused rather than stored.
- An **Observation** is one thing a source published, keyed by a content hash, immutable once
  written, with a MinHash signature so near-duplicates from different outlets group as one
  story.
- A **Route** links an observation to a watch by the clause that fired. Deterministic,
  rebuildable, no model.
- An **Adjudication** is one model call about one routed pair, whatever it answered, with its
  audit id and token cost. **Evidence** is the subset that bore on the claim: direction,
  magnitude, prompt version. Evidence is derived; `replay` rebuilds it for a prompt version
  and diffs it against what is stored.
- The **belief ledger** is append-only. The file's belief is the prior; every later value is
  the operator's, with a note. **Resolution** is the operator grading the claim yes or no.
  A watch removed from the file is retired, never deleted, because history hangs off it.
- A **brief** is a derived view. A row per render sets the next brief's default window to the
  last brief before today, so a second run the same morning reproduces the first.

`docs/CONCEPTS.md` has the entity-by-entity reference.

## Six invariants

Each is a test, not a convention.

1. **Nothing sends.** No email, no webhook, no listener. The one outbound call is to the model
   API, and every payload that leaves is in `data/llm-audit/` first.
2. **Every watch names a decision.** A watch whose `so_what.decision` is not a key in the
   Position is refused.
3. **Observations are immutable; evidence is derived.** An update to an observation raises in
   the ORM and is refused by a database trigger. Evidence can be deleted and rebuilt, per prompt
   version, by `replay --commit` and nothing else.
4. **One stochastic component.** Adjudication is the only model call. Routing before it and
   the brief after it are pure functions of the database.
5. **Silence is distinguishable from breakage.** The header and QUIET sections, above.
6. **The system never authors watches.** There is no `watch add`; the file is the only way a
   watch reaches the table, and the onboarding skill transcribes what the operator says.

## Commands

| command | does |
|---|---|
| `auth set / status / clear` | the Anthropic key in the OS keychain; never printed, never in `.env` |
| `sources list / show` | configured feeds and what each has contributed |
| `ingest [--since] [--source]` | every configured source; per source: fetched, inserted, unreachable, went silent |
| `watch sync / list` | file to table; retire, never delete |
| `watch believe ID P --note` | append an operator belief |
| `watch resolve ID --outcome yes/no --note` | grade a claim, once |
| `route [--since] [--dry-run] [--rebuild]` | link candidates; report the unrouted clusters |
| `adjudicate [--dry-run] [--limit]` | one structured call per pending pair; `--dry-run` prints what would be sent |
| `replay --prompt-version V [--against] [--adjudicator] [--limit] [--commit]` | rebuild evidence and diff it; writes only with `--commit` |
| `brief [--since] [--as-of] [--format] [--output] [--dry-run]` | the document |
| `run` | ingest, route, adjudicate, brief, stopping at the first failure |

## Sources

Input arrives through the adapter layer in `src/sources/`: RSS and Atom feeds from
`config/feeds/`, and the Federal Register documents API filtered server-side by
`config/sources/federal_register.json`. Every adapter emits the same normalized item and
stores it through one path, so routing, adjudication and the brief do not know adapters exist.
An adapter that cannot reach or cannot understand its upstream raises; it never returns an
empty list, and a 200 that carries no feed is an error, not a quiet day.

Which sources may be retrieved at all, and on what basis, is recorded in `SOURCES.md`. A source
with no recorded basis does not ship.

## Privacy and safety

- The API key lives in the OS keychain (`insightweaver auth set anthropic`). There is no
  environment fallback.
- Every model request is written, in full, to `data/llm-audit/` before it is sent, and each
  response's usage and stop reason after; one JSONL file per day. Keep that directory, and the
  database, out of cloud-synced folders; `LLM_AUDIT_DIR` and `DATABASE_URL` move them.
- The Position and watch files name real decisions and deadlines. They live outside the
  checkout, and `.gitignore` refuses them at the root and under `config/`.
- Nothing listens on any interface and nothing writes to an external service. The pre-commit
  hooks and CI scan for secrets.

## What is deliberately not built

Recorded in `docs/PLAN.md`, section 8, each with what would bring it back: a belief update rule
(the operator moves beliefs; auto-updating one without resolved watches to calibrate against
would be inferring calibration that doesn't exist), a synthesis pass over the brief, sensors
beyond published sources, an MCP server, and any integration that writes anywhere.

## Development

```
python -m venv .venv && source .venv/bin/activate
make install-dev    # dependencies, editable install, pre-commit hooks, into the active interpreter
make db-init        # every table a fresh database lacks
make check          # ruff, mypy, pytest
make golden         # regenerate the brief's golden files; read the diff
```

`CONTRIBUTING.md` has the workflow; `backlog/` holds one task file per change, with its
acceptance, its out-of-scope and its landmines, and `docs/PLAN.md` is the plan they implement.

## Requirements

Python 3.11 or newer, an Anthropic API key, and network access for `ingest` and `adjudicate`.
Everything else runs offline, including the whole test suite.

## License

See `LICENSE`.
