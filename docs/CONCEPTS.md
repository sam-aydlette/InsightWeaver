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

**CLI.** `questions list [--beat NAME] | show <id> | resolve <id> --note ...`

**In the brief.** Returning questions surface their identity inline: `Q47 (run 4, asked 2026-03-12)` for repeat appearances, `Q47 (new)` for first ones.

---

## Predictions

A **Prediction** is a falsifiable observable the synthesis committed to watching for. Each `what_to_watch` entry in a situation's output becomes a Prediction keyed to that situation's primary Question.

**When created.** During synthesis, after questions are resolved. Each `{observable, trigger_condition}` pair in `where_this_goes.what_to_watch` becomes a Prediction row.

**When resolved.** Before each new synthesis, a check pass grades the open ledger against today's coverage: triggered (observable appeared), contradicted (coverage explicitly went the other way), expired (no signal after 90 days), or still open.

**Why it matters.** This makes the tool's forward-looking statements auditable. The `predictions track-record` command shows the calibration: of N predictions resolved in the last 90 days, what fraction triggered vs. were contradicted.

**CLI.** `predictions open | triggered | contradicted | track-record`, each taking `--beat NAME`

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
  "coverage": {},
  "standing_questions": [],
  "channels": ["terminal"]
}
```

**Source selection reuses the feed `applicability` tags**, it does not invent a parallel selector. `feed_tags` is matched against a feed's `domain_tags` and `specialty_tags`; the optional `geo_tags` and `scope` narrow against the families of the same name. Within a family the match is ANY, across families it is ALL, and multiple `sources` entries union. A beat is deliberately *not* validated by `src/utils/profile_loader.py` — that validator enforces a person-shaped schema, and a beat is a different shape.

**`coverage` declares the institutions the beat tracks; `standing_questions` is still reserved.** See "Institutional activity" below for what `coverage` does. `standing_questions` is validated for shape so it needs no migration later, but nothing reads it yet.

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

### Reading the graph back out: `questions`, `predictions`, `forecast`

Scoping the write path is only half the boundary. `brief` writes the graph; `questions`, `predictions` and `forecast` read it back out, and an unscoped read would surface a beat's ledger as though it were the user's own. That is the same silent-wrong-answer failure the scoping exists to prevent, so these commands answer the same way `brief` does:

**No `--beat` means your own ledger, `--beat NAME` means that subject's.** One flag, the same meaning everywhere.

| Command | Scoped? |
| --- | --- |
| `questions list` | yes |
| `predictions open` / `triggered` / `contradicted` | yes |
| `predictions track-record` | yes |
| `forecast` | yes |
| `questions show <id>` | no -- id-addressed, discloses its ledger |
| `questions resolve <id> --note ...` | no -- id-addressed, reports its ledger |

`track-record` is the case that matters most. A calibration figure is only meaningful within one ledger: folding a compliance beat's resolved observables into the user's personal hit rate would corrupt the single number the tool exists to be honest about. `forecast` is a derived view over the predictions ledger, so it inherits the ledger's scoping rather than defining its own.

**The two exceptions are deliberate, and they are not "left global by omission".** `questions show 47` and `questions resolve 47` name one specific row. Refusing to find it because it belongs to another ledger would be obstructive, and silently scoping the lookup would make a valid id look nonexistent — addressing a row by id is an explicit act, not a browse. So both operate on the whole graph, and both **disclose** the ledger the row belongs to: `show` prints a `Ledger:` line, and `resolve` names the beat in its confirmation. The appearance history inside `show` is likewise unscoped, because it is the full history of the row the user asked about. Scoping is thereby always either applied or stated, never assumed.

**`--beat` on the read side resolves against the `beats` table, not `config/beats/`.** A ledger you have already accumulated stays readable after its config file is edited or deleted; reading is about what ran, not about what is currently configured to run. An unrecognised name is an error naming the beats that have runs, rather than an empty result that would read as "you have nothing here".

On a database with no `beat_runs` rows these commands behave exactly as they always have, for the same reason the brief does: the default scope is the whole graph.

---

## Institutional activity

A beat's `coverage` block names the **institutions** it tracks: organizations, programs, and types of document. Each run counts how many of its items mention each one, and the brief reports the entities whose count **departed from their trailing average**.

```json
"coverage": {
  "orgs":           [{ "name": "CISA", "aliases": ["Cybersecurity and Infrastructure Security Agency"] }],
  "programs":       ["FedRAMP 20x", "CMMC"],
  "document_types": [{ "name": "Binding Operational Directive", "aliases": ["BOD"] }]
}
```

An entry is either a bare canonical name or `{"name": ..., "aliases": [...]}`. The three block names are the whole vocabulary: `kind` is `org`, `program` or `document_type`.

**There is no person kind, and that is the design, not an omission.** The loader rejects a `coverage.people` key — and any other unrecognised block — with an error rather than ignoring it, so the boundary is enforced by the schema and cannot be reintroduced by convention. `beat_entities` has no person kind and there is no persons table, so no per-individual record exists to profile with. A named individual may appear inside a rendered situation where the source document names a signatory; that is an attribute of a document and expires with it, whereas a person row would accumulate across runs into a file on someone.

The reasoning is on the merits as well as the ethics. Personnel rotate and offices persist: tracking `FedRAMP PMO` survives a staffing change, while tracking a name goes silently dark on reassignment and the absence reads as inactivity — a wrong answer that looks like a real one. The interesting signal was never a person; it is whether an office moved.

**The signal is the delta, never the count.** A flat tally is noise: the entities a beat declares are the ones that appear most days, so "FedRAMP PMO: 6" reproduces a standing fact every morning. What the brief says is `FedRAMP PMO appeared in 6 items this run, against a trailing average of 1`. The baseline is the last five recorded runs, and a move must clear both one whole item and half the baseline before it is reported as movement. **Expect this to look useless on day one** — there is no baseline until several runs have accumulated, and it must not be tuned against a single run.

**Matching is deterministic word-boundary alias matching. No model is involved.** A count a model produced is not reproducible from the same articles tomorrow, and an unreproducible baseline cannot support a delta. Acronyms collide badly — `CISA` sits inside "precisa", `OMB` inside "bombing" and "combat", `BOD` inside "body" — so every term is anchored between non-alphanumeric positions, and a term written entirely in capitals matches case-sensitively, because an acronym is only itself when it is shouted. Hyphens and slashes are boundaries, so "CISA-issued" counts. A mention is counted per *item*, not per occurrence: an article naming CISA nine times is one item.

**What appears and what does not.** An entity with no mentions and no history does not appear — declaring it was a hypothesis about where news comes from, and one that has never paid out is a note about the config, not a line in the brief. An entity that **has** been active and is now quiet does appear: silence is information, and dropping it is the same class of bug as a standing question vanishing on a quiet day. `entity_mentions` records a row per entity per run including the zeroes, because a baseline that averaged only the busy days would always read as normal.

**It is not a leaderboard.** Entries are ordered by kind then name, never by count, and the section states that a count is an observation rather than a measure of significance. Consistent with "no entity stores a truth value": activity is not importance, and the tool does not infer intent, motive or significance from it.

**Schema.** `beat_entities` holds one row per declared institution per beat, carrying `kind`, the canonical `name` and the configured `aliases`. `entity_mentions` holds one row per entity per run, carrying `item_count`, `items_scanned` and the `beat_run_id` and `synthesis_id` of the run — written in the same transaction as the synthesis, so a stored run is either fully recorded or does not exist. An entity dropped from the config keeps its rows; deleting them would silently rewrite the record of what was observed.

**Migration.** `python -m src.database.migrations.add_beat_entities`. Purely additive; a database without it keeps working and the activity section is simply absent.

---

## Sources

Each RSSFeed carries derived **calibration signals**, computed on demand from ArticleFrame and FrameGap data. No new schema for this — purely a view:

- **Frame uniqueness:** fraction of this feed's tagged articles whose frame is carried by no other feed. High score = single point of exposure.
- **Gap-filling:** fraction of recorded gap labels this feed's articles cover. High score = this source brings perspectives the rest of your corpus lacks.

**CLI.** `sources list | show <name>`

---

## How a daily brief flows through the graph

With `--beat`, step 0 is registering the beat and resolving its sources; every graph read and write below is then confined to that beat's scope, and step 8 also writes the `beat_runs` row. Without `--beat` the run operates in the default scope, which on a database with no beat runs is the whole graph.

0. **Coverage pass** (beats with a `coverage` block only) — the run's items are matched against the beat's declared institutions and read against their trailing averages. Deterministic, no model call.
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
