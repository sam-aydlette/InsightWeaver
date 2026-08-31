# InsightWeaver

> **Superseded 2026-08-31 (backlog task 012).** The briefing product this
> document describes -- `brief`, beats, questions, predictions, frames,
> synthesis and rendering -- has been **deleted**. Roughly 8,900 lines of source
> and most of the test suite went with it, in a single commit, because the
> operator's call was that git history is the rollback path and dead code in the
> tree reads as current. `insightweaver` now exposes one command, `sources`.
>
> What survives is ingestion: `src/sources/`, `src/rss/`, `src/processors/`, the
> feed config, and five modules ported for tiers not yet built
> (`src/matching/entity_matcher.py`, `src/matching/coverage_probe.py`,
> `src/llm/claude_client.py`, `src/utils/cadence.py`,
> `src/processors/deduplicator.py`).
>
> **Everything below this banner describes the deleted product and has not been
> rewritten.** Rewriting it needs the new pipeline to exist first, which task 012
> explicitly puts out of scope. Read it as history until it is replaced.

---

**A tool for building warranted, inspectable understanding from RSS feeds.**

---

## Current state

**A research prototype under active development, not a finished product.** It runs, it is tested,
and parts of it do not yet work. This section says which is which, and is updated when that
changes. Last updated 2026-08-27.

**What works today**

- The pipeline runs end to end and produces a brief: RSS and Federal Register ingestion, dedup,
  filtering, clustering, three synthesis passes, and rendering to terminal, Markdown, HTML, or
  email. The most recent live run analysed 50 articles into 9 situations in about ten minutes.
- Beats scope a brief to a subject rather than a person, without a `beat_id` column on any graph
  table -- scope is derived from a join, so one question can belong to two scopes with independent
  counts (`backlog/004`).
- Ingestion is behind an adapter interface, so a source that publishes no RSS can still be read
  (`backlog/005`).
- Standing questions: a beat declares what it watches, and a question that did **not** move is
  reported rather than dropped (`backlog/007`).
- Institutional activity is reported as movement against a trailing average, never as a tally,
  and tracks organizations, programs, and document types -- **never individuals** (`backlog/006`).
- A stored brief can be re-rendered offline in any format with no API key and no network call.
- 852 tests; `make check` runs lint, typecheck, and the suite. `main` requires a pull request and
  five green checks, enforced for administrators.

**Known limitations, stated plainly**

- **The calibration record is still empty, though the machinery now exists.** 33 model-generated
  predictions have been graded zero times; 25 are phrased "X would signal Y", an interpretation
  rule that cannot be wrong. As of `backlog/011` an operator can stake a dated, confidence-bearing
  claim and resolve it, and those are counted separately from the model's. **Nothing has been
  staked yet.** Until something is, the tool's central claim remains unmet -- the fix is a
  mechanism, not a result.
- **Adding a feed to `config/feeds/` does not add it to the database.** `FeedManager.load_feeds_to_database()`
  syncs config into the `rss_feeds` table, and the fetcher reads the table, not the config. A beat
  resolves feeds from config, so a newly added source will resolve, pass its tests, and fetch
  nothing until that sync is run. This was found on 2026-08-28 when five trade outlets were
  configured, CI was green, and the corpus stayed empty of them.
- **Questions declared in a beat config carry no review cadence.** The four standing questions on
  the `us-public-sector-compliance` beat -- including the CMMC one -- predate cadences, and there is
  no `questions set-cadence`. They are invisible to `forecast --due` until re-declared with
  `questions add --cadence`. Per-question cadences otherwise work (`backlog/011`).
- **Per-run cost is unmeasured.** There is no token accounting.
- **Delta-based features need history to mean anything.** Institutional activity reports "no
  trailing average yet" until several runs have accumulated. This is by construction, not a bug.

**How the work is recorded**

Every change lands as a pull request, and every non-trivial one is specified first in
`backlog/NNN-*.md` with a goal, acceptance criteria, explicit out-of-scope boundaries, and known
landmines. Those files are kept after the work ships, including where a later task documents that
an earlier one measured the wrong thing -- `backlog/009` and `backlog/010` exist because
`backlog/005` reported document counts as domain coverage, and that is written down rather than
quietly corrected.

## The Problem

The dominant narratives in daily news coverage preclude alternatives without the reader knowing it. This is a structural feature of how information is produced and distributed. Every article frames its subject: it foregrounds certain facts, backgrounds others, and takes certain premises for granted. When your information sources all use the same frame, you are not exposed to the alternatives. You cannot evaluate what you cannot see.

The traditional response to this problem -- aggregating more sources -- does not solve it. More articles using the same frame is not more perspective. It is more volume.

Information overload is a real problem, but it is a symptom. The deeper problem is that the reader has no way to see the editorial structure of their information diet: which frames are present, which are absent, and what assumptions are embedded in the coverage they consume.

---

## What You Get

You read your morning brief and come away understanding:

1. **What is actually happening** -- not just what is being reported. The underlying situation, not the headline.
2. **Who is doing what to whom, and why** -- named actors with identified interests, not abstract forces.
3. **What the coverage makes easy to see and what it makes hard to see** -- the narrative layers in the reporting, where they conflict, and what is structurally absent from the sources you read.
4. **Where the story could go** -- the branching paths, what would have to be true for each one, and the unresolved question that determines which way it breaks.
5. **What you would need to know to make a good decision about this** -- the specific information gaps, why they exist, and what kind of source would fill them.

This is the value proposition. Everything else -- the architecture, the frame glossary, the clustering -- exists to deliver these five outcomes.

---

## Two ways to use it

**Just stay informed.** Run `insightweaver brief` in the morning. Read the output. You get all five outcomes above, plus a transparency line at the top reporting which of yesterday's flagged observables resolved overnight. That's the whole rhythm.

**Track threads across time.** Behind the brief is a persistent commitment graph: Questions the coverage is still tracking, Predictions whose triggers may yet fire, Decisions you're carrying, Frames each feed exhibits. The graph accumulates whether or not you ever query it -- but you can query it. `insightweaver questions list`, `decisions show housing`, `predictions track-record`, `diet gaps`. The brief itself surfaces returning question identity inline (`Q47 (run 4, asked 2026-03-12)`), so the graph is visible even from the minimal flow.

The deeper layer is optional. Most readers will never touch it. The architecture exists so that the brief is grounded in accumulated context rather than reset every morning.

See [docs/CONCEPTS.md](docs/CONCEPTS.md) for the one-page reference if you want to understand the persistent layer.

---

## Principles

### 1. Insight over information

The output should help you understand what story is being told and what it assumes -- not just what was reported. A list of headlines is not a briefing. A briefing that tells you what happened without surfacing the frame through which "what happened" was constructed has done half the job.

### 2. Warranted trust over projected confidence

Transparency about sourcing, epistemic status, and uncertainty is the mechanism. Every claim carries a label: reported fact, single-source claim, consensus view, or speculation. When the label is ambiguous, the system defaults to the weaker one. False confidence is a violation even when the underlying claim is accurate. A synthesis that honestly maps what it does not know is more useful than one that papers over holes.

### 3. Frame visibility over false balance

Balance does not mean equal treatment of all positions. It means making the frames present in the corpus visible, naming their assumptions, and explicitly flagging what is absent. Bothsidesism is itself a framing choice -- one that treats the number of perspectives presented as a proxy for fairness while obscuring the structural question of which perspectives were available in the first place. InsightWeaver surfaces frames as structural features of coverage: what a frame emphasizes, what it de-emphasizes, and what it takes for granted. It does not evaluate which frame is "correct."

### 4. Epistemic autonomy as the goal

The system equips the user to reason. It does not hand them conclusions. Synthesis is not the same as manipulation. When information is insufficient to draw a conclusion, the system says what is missing and stops. It does not fill gaps with plausible-sounding inferences. The user decides what the information means.

### 5. Honest self-awareness about the tool's own narrative

InsightWeaver makes editorial choices: which feeds to include, how to cluster topics, which frame candidates to surface for validation. Those choices shape the output. They are surfaced to the user, not hidden behind a veneer of objectivity. RSS feed selection is explicitly the user's responsibility. Frame validation requires human review. The system's own assumptions are part of what it reports on.

---

## What InsightWeaver Does

InsightWeaver is a CLI tool that runs on your computer. It fetches RSS feeds you configure, synthesizes them into daily briefings using Claude (Anthropic's AI), and makes the narrative structure of the coverage visible.

The output is organized around **situations**, not headlines. A situation is a mini-narrative with examined characters: who are the actors, what are their interests, what are they doing, who benefits, who is harmed, who decides. The actors and interests emerge from sourced evidence, not from the tool's editorial preference. When the evidence is ambiguous about who benefits, the tool says so rather than picking a side or retreating into "there are many perspectives."

**Epistemic labeling.** Every claim carries a status: reported fact, single-source claim, consensus view, or speculation. Uncertainty is expressed as a structural feature of the information -- what is missing and why it matters -- not hidden behind hedging language.

**Frame analysis.** For each situation, the system identifies the dominant frame in today's coverage, names its assumptions, and flags which frames are absent. It also identifies the causal structure that determines outcomes regardless of how the coverage frames it -- the forces, constraints, and dependencies that matter whether or not the articles mention them.

**An emergent frame glossary** built from your actual corpus over time. When a topic cluster has no known frames, the system discovers candidates. You validate them interactively: accept, reject, or edit. Nothing enters the glossary without your review.

**Gap detection as a feed curation signal.** When a frame is consistently absent from your feeds, the system logs the gap and recommends a type of source that would carry the missing perspective. It does not attempt to fill the gap itself. It does not search the web. Source control stays with the user.

**Transparency about the tool's own choices.** Every briefing tells you which feeds contributed, what was filtered, how articles were clustered into situations, and which frames are known versus newly discovered. The system's editorial decisions are part of what it reports on.

---

## How It Works

InsightWeaver uses context engineering: it curates optimal context for Claude and bakes analytical guardrails into the prompt rather than checking outputs after the fact. The pipeline has three synthesis passes (clustering, situation analysis, cross-cluster reconciliation) plus supporting passes that maintain the persistent layer.

The synthesis path (what produces the brief you read):

1. **Collection** -- RSS feeds are fetched in parallel from sources you configure
2. **Deduplication** -- duplicate and near-duplicate articles are removed
3. **Context curation** -- articles are selected based on your profile (location, profession, interests)
4. **Pass 1 -- Clustering and frame discovery** -- articles are grouped into situations. For each situation, the system checks for known frames or discovers new ones. This pass is auditable: you can inspect which articles landed in which cluster.
5. **Pass 2 -- Situation synthesis** -- Claude analyzes each situation with known frames injected, producing examined narratives with actors, interests, power dynamics, frame analysis, and information gaps. `ANALYSIS_RULES.md` is injected into every prompt, enforcing epistemic labeling and structural honesty.
6. **Pass 3 -- Cross-cluster reconciliation** -- looks for meta-fractures: a single underlying frame conflict appearing across multiple topically distinct situations. Empty result is common and expected.

The persistent-layer maintenance that runs alongside (you don't have to read any of this -- it just makes the next brief grounded in accumulated context):

- **Pre-pass: prediction check.** Before any new analysis, the open-prediction ledger is graded against today's coverage. Observables flagged in past runs are marked triggered, contradicted, or still open. A transparency line at the top of every brief reports the result.
- **Question matching.** Each situation's unresolved questions are bound to a persistent graph. Returning questions surface their identity inline (`Q47 (run 4, asked 2026-03-12)`). A beat can also declare standing questions it always reports against, moved or not.
- **Prediction creation.** `what_to_watch` observables from each situation become open predictions, keyed to their question.
- **Frame classification.** Each article in each cluster is tagged with the frame it most exhibits.
- **Decision routing.** Situations are matched against the factors of standing decisions you've registered. Today's coverage gets recorded as evidence per decision, so each run updates an accumulating record.

RSS is the only input source. The `forecast` command is a derived view over the predictions ledger -- not a separate engine.

See [docs/CONCEPTS.md](docs/CONCEPTS.md) for the entity-by-entity reference.

---

## Who This Is For

People who want to understand the structure of the news they consume, not just its content. People who want to know who benefits, who is harmed, and what the coverage makes hard to see. People who are willing to curate their own sources and validate the system's frame discoveries. People who prefer tools that are transparent about their own editorial choices.

---

## Getting Started

```bash
git clone https://github.com/YOUR_USERNAME/InsightWeaver.git
cd InsightWeaver
python -m venv venv && source venv/bin/activate
pip install -e .
cp .env.example .env  # Add your ANTHROPIC_API_KEY
insightweaver brief   # Generate your first briefing
```

See [GETTING_STARTED.md](GETTING_STARTED.md) for detailed setup instructions.

---

## Re-rendering a Stored Brief

`insightweaver brief` runs the whole pipeline: it fetches feeds and re-synthesizes,
so two invocations never produce the same brief. When you want *last night's* brief
again -- as HTML, as email, or just on screen -- render the stored run instead:

```bash
insightweaver brief --from-run 176                            # terminal
insightweaver brief --from-run 176 --format html --output out.html  # self-contained page
insightweaver brief --from-run 176 --format email             # send via SMTP
insightweaver brief --from-run 176 --save brief.md            # markdown archive
```

The id is a `narrative_syntheses` row id; an unknown id lists the recent ones. This
path is offline and deterministic -- no feeds, no Claude call, no `ANTHROPIC_API_KEY`
required, and the same id always renders the same bytes. Email uses the SMTP
variables in `.env` (`SMTP_SERVER`, `SMTP_PORT`, `EMAIL_USERNAME`, `EMAIL_PASSWORD`,
`FROM_EMAIL`, `RECIPIENT_EMAIL`); a failed send reports why and exits non-zero,
with no retry or outbox.

Rendering lives in `src/render/`: one `BriefDocument` model plus a renderer per
medium (`terminal.py`, `html.py`, `markdown.py`, `email.py`). The live pipeline path
builds the same document and uses the same renderers, so there is exactly one place
that decides what a brief looks like.

---

## The calibration loop: staking and grading your own calls

Every other ledger command reads. These four write, and they are what makes the graph
a calibration instrument rather than a reading list -- the thing being calibrated is
*your* judgement.

```bash
questions add "Does CMMC Phase 2 slip past its statutory date?" --cadence 90d
predict 23 "Yes -- slips" --by 2026-12-31 --confidence 0.7
forecast --due
resolve 41 --outcome no --note "DFARS class deviation published 2026-11-14"
```

All four are local database work: no `ANTHROPIC_API_KEY`, no network call. The loop is
`forecast --due` (what is due right now, at each question's own speed), grade what
resolved, read the diff on whatever came up for review, stake anything new. **The brief
is optional to that loop** -- ingestion is the fragile half, and the ledger should keep
working on a week where the sources returned nothing worth reading.

**A date and a confidence are required, and rejected at entry.** Nothing is stored
without them. The tool's first 33 predictions were graded zero times: 25 were phrased
"X would signal Y" -- an interpretation rule, which cannot be wrong -- and only 3
carried a date, so 19 aged out unjudged. A claim with no resolution date can never come
due. There is no confidence default either; an unstated confidence is a non-commitment
in a different costume.

**A cadence is not a deadline.** A question's `--cadence` says how often it is worth
re-examining; a prediction's `--by` says when a specific claim resolves. A question
reviewed quarterly can hold a claim resolving in three weeks. `forecast --due` tests
each question against its *own* interval -- a 7d question and a 90d question come due
independently -- and **stamps a question as reviewed whether or not anything moved**,
because a quiet question that reappears every day trains you to skim.

**`predictions track-record` counts your predictions only.** The model's are reported
under a separate heading and never folded into the figure; a hit rate that blends the
two measures nothing. Nothing auto-resolves from coverage: a tool that grades its
operator's calls using the corpus that produced them is measuring agreement with itself.

Schema: `questions.cadence`, `questions.last_reviewed_at`, and
`predictions.author | due_by | confidence | outcome`, added by
`python -m src.database.migrations.add_calibration_loop` (reversible; the downgrade
refuses rather than misattributing an operator claim). Commands live in
`src/cli/stake.py`, `src/cli/questions.py` and `src/cli/forecast.py`; interval
arithmetic in `src/utils/cadence.py`.

---

## Beats: briefing a subject instead of a person

The user profile models *you* -- a location, a profession, a voting context. A **beat**
models a *subject*: a standing topic with its own sources. Both coexist, and the
person path is unchanged.

```bash
insightweaver brief --beat us-public-sector-compliance
```

A beat lives in `config/beats/<name>.json` and selects its feeds through the same
`applicability` tags (`scope` / `geo_tags` / `domain_tags` / `specialty_tags`) that
`config/feeds/` already uses:

```json
{
  "name": "us-public-sector-compliance",
  "sources": [
    { "adapter": "rss", "feed_tags": ["regulatory", "federal_policy"], "geo_tags": ["usa"] }
  ],
  "coverage": {
    "orgs": [{ "name": "CISA", "aliases": ["Cybersecurity and Infrastructure Security Agency"] }],
    "programs": ["FedRAMP 20x", "CMMC"],
    "document_types": [{ "name": "Binding Operational Directive", "aliases": ["BOD"] }]
  },
  "standing_questions": [
    "Does CMMC Phase 2 slip past its statutory date?",
    "Which CSPs move to FedRAMP authorized, and at which impact level?"
  ],
  "channels": ["terminal"]
}
```

A beat's brief is drawn only from that beat's sources, renders through the same
`BriefDocument` as every other brief, and accumulates its own slice of the graph:
its Questions and Predictions are kept apart from the default brief's, so a
returning question's run number means "the Nth time *this subject* raised it".

### Standing questions

`standing_questions` is what makes the output a brief rather than a digest. A
question there is *declared*, not discovered: the beat carries it whether or not
this week's coverage mentions it, and every run reports what moved against it.

```
STANDING AGENDA
What this beat declared it is watching. Unmoved items are reported, not dropped.

  [MOVED] Does CMMC Phase 2 slip past its statutory date?
    Q1 (declared 2026-08-26, run 2)
    Moved in: Situation 1: DoD signals CMMC Phase 2 timeline pressure[3]
    Watching for: A DFARS class deviation naming CMMC Phase 2 -- published before the statutory date

  [NO MOVEMENT] Which CSPs move to FedRAMP authorized, and at which impact level?
    Q2 (declared 2026-08-26, never moved)
    No coverage this run bore on this question, and none ever has.
```

The second entry is the whole point: **"no movement on CMMC Phase 2 this week" is
itself information**, so a quiet standing question is reported as unmoved rather
than dropped as an empty section. Declared questions are still bound to coverage
by the same matcher emergent questions use, but on a tighter threshold, because a
standing question that falsely reads "moved" is worse than one that misses a
match. Nothing is auto-generated and nothing is auto-retired: the agenda is the
human's. See `docs/CONCEPTS.md`, "Standing questions", for the binding rule.

The ledger commands read the same way. `questions list`, `predictions`, and
`forecast` show your own ledger by default and never surface a beat's rows;
pass `--beat NAME` to read that subject's instead:

```bash
insightweaver questions list --beat us-public-sector-compliance
insightweaver predictions track-record --beat us-public-sector-compliance
insightweaver forecast --beat us-public-sector-compliance
```

`questions show <id>` and `questions resolve <id>` are addressed by id, so they
stay global and disclose which ledger the row belongs to.
Run attribution lives in the `beats` and `beat_runs` tables -- no existing table
grew a `beat_id` column. See `docs/CONCEPTS.md` for the scoping rationale and for
what stays deliberately global (the decision journal, the frame glossary).

RSS was the only adapter until 2026-08-26, and the first beats were thin because
of it. See "Source adapters" below for what changed.

### Institutional activity

The `coverage` block names the **institutions** a beat tracks: organizations, programs
and document types. Each run counts how many items mention each one and the brief
reports what departed from its trailing average, not a tally:

```
INSTITUTIONAL ACTIVITY
Movement against each entity's trailing average. A count is an observation, not a measure of significance.

  FedRAMP PMO appeared in 4 items this run, against a trailing average of 0.
  CISA appeared in 0 items this run, against a trailing average of 1.

  GSA appeared in 1, unchanged.
```

A flat count would be noise -- these are the entities that appear most days. Matching is
deterministic word-boundary alias matching with no model call, because a count a model
produced is not reproducible tomorrow and an unreproducible baseline cannot support a
delta. Expect it to look uninformative until several runs have accumulated.

**There is no person kind and no persons table.** `kind` is `org`, `program` or
`document_type`; a `coverage.people` key is rejected by the loader with an error rather
than ignored. Personnel rotate and offices persist, so tracking `FedRAMP PMO` survives a
staffing change while tracking a name goes silently dark on reassignment and the absence
reads as inactivity. A named individual may appear inside a rendered situation where the
source document names a signatory -- an attribute of a document, which expires with it --
but never as a stored row, which would accumulate. See `docs/CONCEPTS.md`.

### Coverage probes: can the beat actually see its domain?

Added 2026-08-27. An article count tells you ingestion is *running*. It does not tell
you ingestion *reaches the domain*, and the two were conflated once already: a beat
resolving hundreds of Federal Register documents missed the reinstatement of the
FedRAMP director, because a personnel change is not a document. The corpus held three
incidental FedRAMP mentions across 50,983 articles and none within two weeks. Every
volume number was green.

A **coverage probe** is the test that catches it: name something that actually happened
in this domain, then check whether the beat can see it.

```json
"coverage_probes": [
  {
    "date": "2026-08-24",
    "what": "FedRAMP director reinstated",
    "terms": ["FedRAMP"],
    "any_of": [["director", "administrator"], ["reinstat*", "return*", "restored"]]
  }
]
```

```bash
insightweaver beat coverage us-public-sector-compliance
```

```
[MATCHED] OPM issued corrections to its final rules on reduction-in-force appeals
  event 2026-08-25 | window 2026-08-11 .. 2026-09-08
  4 matching article(s); earliest shown
    seen by Federal Register - Documents API (2026-08-25)
      Suitability Action Appeals; Correction

[UNMATCHED] FedRAMP director reinstated
    no article from this beat's feeds matched
      closest article lacked: FedRAMP
      and no feed anywhere in the corpus carried it either.

2 matched + 1 unmatched + 1 inconclusive of 4 probe(s) declared
```

`terms` must all appear in one article; each `any_of` group needs one member. The two
levels exist because `FedRAMP` alone is too weak to be evidence -- an AWS region-launch
post mentions it -- while an exact headline is too brittle to survive a second outlet's
phrasing. A probe resting on one bare term is **rejected by the loader**, not accepted:
a probe that passes on generic terms manufactures the confidence this command exists to
remove.

Matching is deterministic word-boundary matching, no model call. That anchoring is what
makes a match evidence: of 54,044 articles stored on 2026-08-27, 657 titles contain the
substring `nist` -- "administration", "minister", "Afghanistan", "communist" -- and four
are about NIST. A trailing `*` marks a stem (`reinstat*` matches "reinstatement"); the
marker is explicit rather than inferred so the widening is visible to whoever has to
trust the result.

The command reports **which feed carried each match**, because "your expected source
carried it" and "an unrelated outlet mentioned it in passing" are different findings
with different repairs. An unmatched probe is re-checked across the whole corpus, so the
output distinguishes "nobody had it" from "feeds you do not subscribe to had it".

It exits non-zero so it can gate: `1` if any probe is unmatched, `2` if nothing could be
measured. A probe whose window predates the corpus is `INCONCLUSIVE` -- neither pass nor
fail -- and stays in the denominator, because a probe set that quietly decays to the
events still in retention is a green light that means nothing. That is also why an
all-inconclusive run and a beat with no probes both exit `2` rather than `0`.

Reads the article corpus only. No API key, no network, and it never writes.

Running your first beat needs the two beat tables, plus one each for institutional
activity and standing questions:

```bash
python -m src.database.migrations.add_beats                # or: insightweaver brief setup
python -m src.database.migrations.add_beat_entities
python -m src.database.migrations.add_standing_questions
```

All are additive and reversible (`... down`). Until you run `add_beats`, `--beat`
stops with a clear error naming what is missing, and every other command --
including plain `insightweaver brief` -- carries on exactly as before. Without
`add_beat_entities` a beat brief still runs and simply has no activity section;
`add_standing_questions` is required before a beat that declares an agenda will
run, because a declared question that cannot be recorded must not be silently
dropped.

---

## Source adapters: ingestion beyond RSS

Added 2026-08-26. The `us-public-sector-compliance` beat resolved eight RSS feeds
and only two of them carried any articles at all -- 346 of 50,983 in the corpus.
The regulatory sources that matter most (CISA advisories, Federal Register public
inspection, the White House, the Department of Education) returned zero rows.
The domain does not publish enough usable RSS to support a brief.

`src/sources/` fixes that without touching the pipeline. An adapter answers one
question -- "what has this upstream published since `<when>`?" -- and answers it
in the same normalized article row `src/rss/fetcher.py` has always produced.
Clustering, frames, questions, predictions and synthesis are unaware adapters
exist.

| Adapter | Reads |
| --- | --- |
| `rss` | Any RSS or Atom feed. The default for every source in `config/feeds/`. |
| `federal_register` | The Federal Register documents API, filtered server-side by the named queries in `config/sources/federal_register.json`. |

Three properties are the point of the layer, and each is tested rather than
assumed:

- **Unreachable is not empty.** An adapter that cannot reach or cannot
  understand its upstream raises; it never returns an empty list. An empty list
  means "reachable, nothing new".
- **A source that goes quiet says so.** An adapter returning zero items when it
  has produced articles before logs an error and the brief prints a
  `SOURCE ALERT` banner. A thin brief with no stated cause is the failure this
  layer exists to prevent.
- **Identity is content, not URL.** The same Federal Register document is
  reachable at several URLs, so items are keyed by a content hash. Re-running an
  adapter over unchanged upstream content inserts zero new articles.

Which sources may be retrieved at all, and on what basis, is recorded in
[`SOURCES.md`](SOURCES.md). A source with no recorded basis does not ship.

To add a source that is not RSS: give its `config/feeds/` entry an `"adapter"`
key, register a factory in `src/sources/runner.py`, add its row to `SOURCES.md`,
and add the adapter name to `SUPPORTED_ADAPTERS` in `src/config/beats.py` so a
beat can select it.

---

## Observations, Evidence, and replay

Added 2026-08-31 (`backlog/014`). Adjudication -- deciding whether an item bears
on a pre-registered Watch -- is the only stochastic component in the system.
Everything either side of it is deterministic and unit-testable. This layer is
what makes the stochastic part reviewable: hold the inputs fixed, change the
prompt, and diff the outputs.

**Observations are immutable and content-addressed.** An observation is one
thing a source published, keyed by a SHA-256 hash of the normalized adapter
output. Nothing per-fetch is in the hashed payload -- not the fetch time, not a
session id -- so re-fetching an unchanged document is a no-op rather than a
second row. Once written, a row cannot be changed: an ORM update raises
`ObservationIsImmutable`, and a `BEFORE UPDATE` trigger refuses an `UPDATE`
issued from anywhere else, including the `sqlite3` shell.

**Evidence is derived, and every row records the prompt version that produced
it.** `evidence` links `(observation, watch)` with a direction and a magnitude.
The `prompt_version` column is per row, not per run, so "where did this
judgement come from" is answerable six weeks later.

```bash
# Rebuild v2's evidence and diff it against what v1 stored. Writes nothing.
insightweaver replay --prompt-version v2 --against v1

# Re-run v1 against its own stored rows. An empty diff is the reproducibility check.
insightweaver replay --prompt-version v1

# Persist. --commit is required; a replay that wrote by default would destroy
# the before-state at the moment you wanted to compare against it.
insightweaver replay --prompt-version v2 --commit
```

Replay needs no `ANTHROPIC_API_KEY`. The adjudicator is a plug-in seam
(`src/evidence/adjudicator.py`); the adjudication prompt itself is a later task,
and the only version this build ships is `null-v0`, which returns no verdicts.
An adjudicator that guessed a direction from a keyword match would put
fabricated judgements into the table whose whole purpose is to make judgements
reviewable.

**Near-duplicate detection.** Two feeds carrying the same wire story with
different boilerplate have different content hashes, correctly. A MinHash
signature over 5-word shingles is written beside each observation and groups
them: `settings.near_duplicate_threshold` (default 0.7, `NEAR_DUPLICATE_THRESHOLD`)
is the tunable. Measured on two real corpus pairs, a genuine near-duplicate
scores 0.89 and the hardest distinct pair 0.016.

**`observations` versus the 55,249-row `articles` table.** They coexist, with one
stated rule: `articles` is the pre-rewrite archive and keeps the row shape the
older code reads; `observations` is authoritative for everything built from task
014 onward. Exactly one code path writes an observation
(`src/sources/observation.py`, called from the adapter store path), and each new
article gets an observation in the same transaction, linked by
`observations.article_id`. The pre-existing rows have no observation and are not
migrated -- the hash is a pure function of columns they already carry, so a
backfill is mechanical and is left to its own task.

Create the tables with `make db-add-observations` (additive; it does not touch
`articles`).

---

## Tier 1: deterministic routing

Added 2026-08-31 (`backlog/015`). Adjudication is the only tier that calls a
model, and it costs money per item. Tier 1 is what decides which items it ever
sees, so **notification volume scales with the number of live watches rather
than with news volume** -- and that is a property of the code in `src/routing/`,
not an aspiration.

**Triggers compile; they are not interpreted and not read by a model.** A
watch's `triggers` is a list of clauses over `terms`, `entities` and `sources`.
Within a clause every populated field must match (AND) and any value in a field
will do (OR); across clauses, any clause firing fires the watch. That compiles
directly into two regex alternations and a set-membership test. Nothing in
`src/routing/` imports an Anthropic client, and the test that says so removes it
from the interpreter entirely and drives the whole path
(`tests/routing/test_no_model.py`).

**Word boundaries are load-bearing.** Every pattern comes from
`src/matching/entity_matcher.py`'s `compile_terms`, which owns the anchors and
the shouted-acronym case rule -- there is deliberately no second matcher. The
scale being defended, measured on this repository's own 55,249-article corpus:
`nist` appears as a substring in 5,364 titles and at a word boundary in 73;
`mail` is 1,842 against 339.

**Routing is idempotent.** A match becomes a `route_candidates` row, unique on
`(observation_hash, watch_id)`; routing the same observation twice produces one
link. The row also records which clause fired, which is the difference between
"this watch routed 400 observations" and "clause 2 of this watch routed 400".

```bash
# Per watch, how many of the last 500 observations would route -- plus the
# unrouted count and its clusters. Writes no route_candidates rows.
insightweaver route --dry-run

# The same, over every stored observation, recording the links.
insightweaver route --limit 0
```

**Read the unrouted number first.** A high one is the healthy state. A low one
means a trigger is too loose, and a trigger that is too loose does not fail --
it bills. The unrouted observations are clustered by their stored MinHash
signatures and written to `data/routing/unrouted_clusters.json` alongside a
document-frequency histogram of their salient terms. That file is the
coverage-gap signal: the only place a *missing* watch is visible before a
staleness alert fires. `backlog/021` reads it.

**The ceiling test.** `tests/routing/test_ceiling.py` asserts that 1,000
observations against 5 watches route fewer than 20. The number was measured, not
guessed: the corpus is 1,000 real articles sampled from the pre-rewrite archive
and stratified by feed category, the measured baseline is 5 routed / 5 links,
and a clause whose AND became an OR routes 33. The test's docstring records the
measurement and is explicit about what it cannot see.

Create the table with `make db-add-routes` (additive).

---

## Requirements

- Python 3.10+
- Anthropic API key
- Internet connection
- ~100MB disk space

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

See [LICENSE](LICENSE) for details.
