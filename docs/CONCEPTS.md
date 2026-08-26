# InsightWeaver Concepts

A one-page reference for the entities the tool persists, how they relate, and when each one gets created. Read this once and the CLI commands will make sense.

---

## The core idea: a commitment graph

InsightWeaver is built around a small graph of **commitments** — things the system or the user has bound itself to track. Each daily brief is a diff against this graph, not a standalone artifact. The unit of value is the running record, not the morning report.

The graph has five primary entity types. Everything in the CLI is either creating one of these, updating one, or reading the graph back out.

A sixth concept, the **Beat**, is not a commitment but a *scope* over them: it says which sources a run reads and which slice of the graph that run accumulates into. See "Beats" below.

---

## Questions

A **Question** is an unresolved epistemic thread the coverage is implicitly tracking. Most situations end with one — "Will the Fed cut rates in June?" — and that question persists across daily runs until it resolves.

**When created.** Each situation's `unresolved_questions.primary` (and optional secondaries) is matched against the open question graph by a Haiku call. If today's question is the same underlying question as one already open, today's situation gets bound to that existing Question. Otherwise a new Question is created.

**When resolved.** Manually, via `insightweaver questions resolve <id> --note "..."`. The tool never auto-resolves; deciding a thread has closed is editorial.

**Reappearance.** When a previously resolved Question's text appears again in fresh coverage, a *new* Question is created with `previous_question_id` pointing at the resolved one. Resolution is never silently undone.

**CLI.** `questions list | show <id> | resolve <id> --note ...`

**In the brief.** Returning questions surface their identity inline: `Q47 (run 4, asked 2026-03-12)` for repeat appearances, `Q47 (new)` for first ones.

---

## Predictions

A **Prediction** is a falsifiable observable the synthesis committed to watching for. Each `what_to_watch` entry in a situation's output becomes a Prediction keyed to that situation's primary Question.

**When created.** During synthesis, after questions are resolved. Each `{observable, trigger_condition}` pair in `where_this_goes.what_to_watch` becomes a Prediction row.

**When resolved.** Before each new synthesis, a check pass grades the open ledger against today's coverage: triggered (observable appeared), contradicted (coverage explicitly went the other way), expired (no signal after 90 days), or still open.

**Why it matters.** This makes the tool's forward-looking statements auditable. The `predictions track-record` command shows the calibration: of N predictions resolved in the last 90 days, what fraction triggered vs. were contradicted.

**CLI.** `predictions open | triggered | contradicted | track-record`

**In the brief.** A transparency line at the top of each brief reports the check results: "Prediction check: 8 open observables graded — 1 triggered, 0 contradicted, 7 still open."

---

## Decisions, Factors, and Evidence

These three together form the **decision journal** — the user-side input that turns daily news into accumulating per-decision context.

A **Decision** is a standing decision the user is carrying (e.g., "housing market timing"). A **DecisionFactor** is a specific variable inside that decision the user is tracking (e.g., "interest rates"). Each factor has a free-text `what_would_update_me` clause — this is the user's stated rule for what evidence would change their read, and it's what makes routing tractable.

**DecisionEvidence** records that a specific situation contained evidence bearing on a specific factor, in a specific direction (`supports`, `complicates`, `neutral`), with an `epistemic_status` label.

**When created.** Decisions and Factors are added by the user via CLI. Evidence is created automatically: after each synthesis's Pass 2, a Haiku router matches situations against open factors and writes Evidence rows for genuine connections.

**Why it matters.** Real decisions accumulate over weeks of evidence, not a single brief. The decision journal is what turns the tool from a daily artifact into a working memory.

**CLI.** `decisions list | show <id> | add | resolve <id> --note ... | factor add <decision-id> --name ... --update-when ...`

**In the brief.** A "Your decisions" section shows which factors moved today and which direction.

---

## Frames

A **NarrativeFrame** is a coherent way of organizing a story: what it emphasizes, what it backgrounds, and what it takes for granted. Frames are structural features of coverage, not opinions.

The frame layer has several related entities:

- **TopicCluster.** A topical area (e.g., "fed policy"). Frames live inside clusters.
- **NarrativeFrame.** A discovered or validated frame for a cluster. Has `validated: bool` — discovered frames start unvalidated until the user approves them via `frames edit`.
- **ArticleFrame.** Maps an article to the frame it most exhibits, with a confidence in `[0, 1]`. Populated by a Haiku classifier on each run.
- **FrameGap.** A frame consistently absent from coverage. A feed-curation signal — if a known frame stops appearing, the gap is recorded.

**Why it matters.** Once `article_frames` is populated, you can ask structural questions about your information diet: which frames does each feed carry, which frames does only one feed supply (single point of exposure), which frames have been absent for weeks. That's what `diet` shows.

**CLI.** `frames list | show <topic> | edit <id> | gaps`, and `diet feeds | gaps | overlap`.

---

## Meta-fractures

A **meta-fracture** is a single underlying frame conflict that surfaces across multiple topically distinct situations on the same day. Computed in Pass 3 (cross-cluster reconciliation) and not persisted as its own table — lives in the synthesis JSON.

Most days have none. When one appears, it's structural insight: the same disagreement is shaping coverage in places you wouldn't have connected.

**In the brief.** A META-FRACTURES section appears when results exist.

---

## Beats

A **Beat** is a *subject* the tool runs briefs for, as opposed to the *person* the user profile models. `config/user_profile.json` describes a location, a profession, a voting context and a set of civic interests; `config/beats/<name>.json` describes a topic and the sources that cover it. The two coexist. The person path is unchanged and `insightweaver brief` with no `--beat` behaves exactly as it always has.

**Shape.** A beat file is small on purpose:

```json
{
  "name": "us-public-sector-compliance",
  "description": "...",
  "sources": [
    { "adapter": "rss", "feed_tags": ["regulatory", "federal_policy"], "geo_tags": ["usa"] }
  ],
  "watchlist": {},
  "standing_questions": [],
  "channels": ["terminal"]
}
```

**Source selection reuses the feed `applicability` tags**, it does not invent a parallel selector. `feed_tags` is matched against a feed's `domain_tags` and `specialty_tags`; the optional `geo_tags` and `scope` narrow against the families of the same name. Within a family the match is ANY, across families it is ALL, and multiple `sources` entries union. A beat is deliberately *not* validated by `src/utils/profile_loader.py` — that validator enforces a person-shaped schema, and a beat is a different shape.

**`watchlist` and `standing_questions` are reserved.** They are validated for shape so that entity watchlists and standing questions need no migration later, but nothing reads them yet.

**Run recording.** `beats` holds one row per subject; `beat_runs` holds one row per brief run, carrying the `analysis_run_id`, the `synthesis_id`, the article count and the number of feeds the beat resolved to. A run is attributed in the same transaction that stores its synthesis, so a stored synthesis is either attributed or does not exist.

**CLI.** `brief --beat NAME`. `--beat` and `--from-run` are mutually exclusive: a stored run replays exactly as recorded.

**Expect a beat to be thin.** RSS is the only adapter today, and specialist domains publish little of it. The shipped `us-public-sector-compliance` beat resolves to eight feeds. That thinness is a finding about the source layer, not a defect in the beat.

### Scoping decision: the graph is scoped by derivation, not by a `beat_id` column

Questions, Predictions and their join rows carry **no `beat_id` column**. A row's beat is derived from `beat_runs`: a synthesis belongs to a beat when a `beat_runs` row says so; a Question belongs to a beat when it appeared in one of that beat's syntheses; a Prediction inherits the beat of the Question it keys off. Two scopes exist — a beat's scope, and the **default scope**, which is everything no beat run ever touched.

This is scoping, not collision-acceptance. The question matcher only ever binds within one scope, the prediction check only grades and expires within one scope, and — the load-bearing part — **appearance counts are counted within a scope**, so `Q47 (run 4, asked 2026-03-12)` means "the fourth time *this subject* raised it".

Why derivation rather than a column:

- **A Question's beat is not an independent fact.** It is discovered from coverage, and the only thing that knows which subject surfaced it is the run. A `beat_id` column would be a second, denormalized copy of something `beat_runs` already determines, and the two could disagree.
- **The same question can legitimately belong to two scopes.** A CISA directive can be both a compliance question and a personal-news question. A column forces a duplicate Question row and severs the link between them; derivation keeps one Question with an independent appearance count in each scope.
- **It is additive.** No existing table is altered, so an unmigrated database keeps working for every non-beat command, and the migration cannot lose data. On a database with no `beat_runs` rows — every database that predates this feature — the default scope is the whole graph and every scope filter is an identity filter. That is what makes the no-beat path provably unchanged rather than merely believed to be.

What stays **global**, deliberately:

- **Decisions, DecisionFactors and DecisionEvidence.** A standing decision belongs to the user, not to a subject; the point of routing beat coverage into it is that a compliance development can move the user's career-timing factor. Scoping the decision journal per beat would break exactly the connection it exists to make.
- **TopicClusters and NarrativeFrames.** A frame is a structural property of coverage, not of a subject. The same "national-security framing" appears in both the compliance beat and the general brief, and it is the same frame. Splitting the glossary per beat would fragment the frame vocabulary and weaken the `diet` signals, which depend on comparing feeds across the whole corpus.
- **Article content filtering.** Stage 3 still filters articles against the person profile's `excluded_topics` before a beat brief selects from what remains. A beat scopes which *sources* are read, not who the brief is for.

---

## Sources

Each RSSFeed carries derived **calibration signals**, computed on demand from ArticleFrame and FrameGap data. No new schema for this — purely a view:

- **Frame uniqueness:** fraction of this feed's tagged articles whose frame is carried by no other feed. High score = single point of exposure.
- **Gap-filling:** fraction of recorded gap labels this feed's articles cover. High score = this source brings perspectives the rest of your corpus lacks.

**CLI.** `sources list | show <name>`

---

## How a daily brief flows through the graph

With `--beat`, step 0 is registering the beat and resolving its sources; every graph read and write below is then confined to that beat's scope, and step 8 also writes the `beat_runs` row. Without `--beat` the run operates in the default scope, which on a database with no beat runs is the whole graph.

1. **Prediction check** — open Predictions are graded against today's coverage. Resolutions written to the ledger.
2. **Pass 1** — articles clustered into topic groups.
3. **Pass 2** — each cluster gets a situation analysis (with frame-aware prompting if known frames exist) and its articles get tagged into ArticleFrame.
4. **Pass 3** — cross-cluster reconciliation looks for meta-fractures.
5. **Question matching** — situation `unresolved_questions` matched against the open Question graph; new Questions created or existing ones bound.
6. **Prediction creation** — situation `what_to_watch` observables become new open Predictions keyed to the matched Questions.
7. **Decision routing** — situations matched against open DecisionFactors; Evidence rows written for genuine connections.
8. **Render** — the brief renders, surfacing question identity, the prediction-check summary, the decision routing, and any meta-fractures.

After this loop runs, the graph has accumulated:
- new Questions or returning ones marked with appearance counts
- new open Predictions plus today's resolutions to the ledger
- new ArticleFrame rows
- DecisionEvidence linking today's situations to your standing decisions

That accumulation is the point. The brief is the diff view onto it.

---

## What's not modeled

A few things deliberately don't exist as entities:

- **Unknown unknowns.** The Rumsfeld bucket is excluded by design. The tool does not fabricate observables it cannot ground.
- **Claim survival.** Computing per-source claim survival would require structured claim extraction we have not built. The `sources` command omits this signal honestly rather than computing a fake one.
- **Truth.** No entity stores a truth value. Predictions are graded for whether they *resolved*, not whether they were *right*. Frames have no "correct" status. The tool surfaces structure, not verdicts.
