# InsightWeaver

**A tool for building warranted, inspectable understanding from RSS feeds.**

---

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
- **Question matching.** Each situation's unresolved questions are bound to a persistent graph. Returning questions surface their identity inline (`Q47 (run 4, asked 2026-03-12)`).
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
  "coverage": {},
  "standing_questions": [],
  "channels": ["terminal"]
}
```

A beat's brief is drawn only from that beat's sources, renders through the same
`BriefDocument` as every other brief, and accumulates its own slice of the graph:
its Questions and Predictions are kept apart from the default brief's, so a
returning question's run number means "the Nth time *this subject* raised it".

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

Running your first beat needs the two new tables:

```bash
python -m src.database.migrations.add_beats     # or: insightweaver brief setup
```

The migration is additive and reversible (`... add_beats down`). Until you run it,
`--beat` stops with a clear error and every other command -- including plain
`insightweaver brief` -- carries on exactly as before.

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
