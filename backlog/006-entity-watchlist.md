# Track declared people, organizations, and programs across a beat's coverage, and surface who is unusually active rather than merely who was mentioned.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
ACCEPTANCE: `make check` passes, plus: a beat's `watchlist` declares entities with `kind` (person/org/program), a canonical name, and aliases; new `beat_entities` and `entity_mentions` tables record matches per run; the brief gains a section reporting entities whose mention count this run **deviates from their trailing average**, not a flat list of mentions; matching is deterministic alias matching with no LLM call; and tests cover alias matching, the delta computation, and an entity with zero mentions (which must not appear).
OUT OF SCOPE: Identity resolution, disambiguation, or merging — "the FedRAMP PMO director" and a named person stay separate rows, deliberately. Extracting entities that are not on the watchlist. Relationship modelling between entities. Any LLM-based extraction; if alias matching proves insufficient, park and say so rather than reaching for a model. Sentiment, stance, or any judgement about an entity. Backfilling mentions from historical articles.
LANDMINES: A flat mention count is noise — the FedRAMP PMO is mentioned every day and that is not news. **The signal is the delta against the trailing average**, which is also why this task cannot be evaluated until several runs have accumulated; expect it to look useless on day one and do not tune it against a single run. Alias matching is a substring-collision minefield: "CISA" appears inside unrelated words, short agency acronyms produce false positives, and a person's surname alone will over-match. Require word-boundary matching and test the collision cases explicitly. The tool's north star says "no entity stores a truth value" — mention counts are observations, not verdicts, and the rendered section must not imply that activity means significance. Do not let this become a leaderboard. Local `main` is 11 commits ahead of `origin`; do not push.
---
Step 4 of five. You asked for "people," and the graph has no entity model at all — 17 tables and
none of them for actors.

The design decision worth defending: **deterministic alias matching, no resolution.** A full
entity graph with alias resolution and org membership is more powerful and is also a new failure
mode — bad merges silently corrupt history in a way that is hard to notice and harder to undo.
Alias matching is boring, inspectable, and delivers the thing you actually asked for, which is
knowing who moved this week.

The rendered section should read like an analyst noting movement, not a dashboard. Something
closer to "X appeared in 6 items this run against a trailing average of 1" than a bar chart.
