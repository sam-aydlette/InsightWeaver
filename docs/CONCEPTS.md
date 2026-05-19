# InsightWeaver Concepts

A one-page reference for the entities the tool persists, how they relate, and when each one gets created. Read this once and the CLI commands will make sense.

---

## The core idea: a commitment graph

InsightWeaver is built around a small graph of **commitments** — things the system or the user has bound itself to track. Each daily brief is a diff against this graph, not a standalone artifact. The unit of value is the running record, not the morning report.

The graph has five primary entity types. Everything in the CLI is either creating one of these, updating one, or reading the graph back out.

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

## Sources

Each RSSFeed carries derived **calibration signals**, computed on demand from ArticleFrame and FrameGap data. No new schema for this — purely a view:

- **Frame uniqueness:** fraction of this feed's tagged articles whose frame is carried by no other feed. High score = single point of exposure.
- **Gap-filling:** fraction of recorded gap labels this feed's articles cover. High score = this source brings perspectives the rest of your corpus lacks.

**CLI.** `sources list | show <name>`

---

## How a daily brief flows through the graph

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
