# Track declared organizations, programs, and document types across a beat's coverage, and surface which institutions are unusually active — never which people.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
ACCEPTANCE: `make check` passes, plus: a beat's `coverage` block declares entities with `kind` restricted to `org` | `program` | `document_type`, a canonical name, and aliases; new `beat_entities` and `entity_mentions` tables record matches per run, keyed to those entities only; the brief gains a section reporting entities whose mention count this run **deviates from their trailing average**, not a flat list; matching is deterministic word-boundary alias matching with no LLM call; a schema containing a `people` key is **rejected with a clear error**, and a test asserts that rejection; and tests cover alias matching, the delta computation, an entity with zero mentions (which must not appear), and the acronym-collision cases named below.
OUT OF SCOPE: **Any per-person tracking of any kind.** No `people` field, no persons table, no per-individual mention counts, no record about a named natural person that persists across runs. This is a hard boundary, not a preference — see the reasoning below. Identity resolution, disambiguation, or merging. Extracting entities not declared in the beat. Relationship modelling between entities. Any LLM-based extraction; if alias matching proves insufficient, park and say so rather than reaching for a model. Sentiment, stance, characterisation, or any judgement about an entity. Inferring intent, motive, or significance from activity. Backfilling mentions from historical articles.
LANDMINES: **A flat mention count is noise** — the FedRAMP PMO appears every day and that is not news. The signal is the delta against the trailing average, which is why this cannot be evaluated until several runs have accumulated: expect it to look useless on day one and do not tune it against a single run. **Alias matching is a substring-collision minefield.** "CISA" appears inside unrelated words; short agency acronyms over-match; "OMB" collides with ordinary text. Require word-boundary matching and test the collision cases explicitly. The tool's north star says "no entity stores a truth value" — mention counts are observations, not verdicts, and the rendered section must not imply that activity means significance. **Do not let this become a leaderboard.** If a person's name appears in an alias list, in a test fixture, or in a database row that outlives the run that produced it, this task has failed regardless of whether the tests pass. `main` is protected (5 required checks, `enforce_admins: true`) — open a PR, do not push to it.
---
Step 4 of five. **Rewritten 2026-08-26**, before implementation, after the operator raised the
critique that decided it. The original version declared a `watchlist` with a `people` array, created
`entity_mentions` rows keyed to individuals, and had a goal line reading "surface **who** is
unusually active."

## Why it was rewritten

`sam-aydlette/InsightWeaver` is a **public repository**, and the operator works professionally in
this domain — alongside people at the FedRAMP PMO, at 3PAOs, and in the agencies this beat covers.

The original design would have placed, in a public repo, a file named `watchlist` containing a list
of named federal officials, backed by database tables recording their mentions over time, producing
a report on whose activity was unusual.

The mechanism was innocuous: count word-boundary matches in publicly published RSS articles. That
defence is true and unusable — the artifact argues before the explanation gets a hearing, and
"watchlist" shares vocabulary with no-fly lists. **A design whose defensibility depends on a
paragraph of context is the wrong design when a different one is available.**

## Why the replacement is better on the merits, not merely safer

The interesting signal was never a person. It is whether **an office moved**. "A named official was
quoted six times" is noise; "the FedRAMP PMO issued three documents this week against a baseline of
zero" is signal. A person mattered only ever as evidence about institutional activity.

- **Better signal.** Personnel rotate; offices persist. Tracking `FedRAMP PMO` survives a staffing
  change. Tracking a name goes silently dark on reassignment and the absence reads as inactivity —
  a wrong answer that looks like a real one.
- **Better ethics.** No per-person profiling, because no per-person record exists to profile with.
- **Consistent with the North Star.** *"The tool equips reasoning, it does not deliver conclusions."*
  A per-individual activity ledger is a conclusion about a person.
- **The artifact simply does not exist.** There is no list of names in the repo, because the schema
  has no field that could hold one.

## Where named individuals may legitimately appear

Only as an attribute of a specific document event, never accumulated. "The CUI rule was signed by
the Deputy Director" is a fact about the rule. It may appear in a rendered brief where the source
document names a signatory, and it must not create or update any persistent row keyed to that
person. The distinction is not stylistic: a document attribute expires with the document, a person
row accumulates into a file on someone.

## Config shape

```json
"coverage": {
  "orgs":           ["FedRAMP PMO", "CISA", "DoD CIO", "GSA", "OMB"],
  "programs":       ["FedRAMP 20x", "CMMC", "StateRAMP", "TX-RAMP"],
  "document_types": ["BOD", "Emergency Directive", "OMB Memorandum", "SRG revision"]
}
```

Note `coverage`, not `watchlist`. The rename is not cosmetic — the schema **must reject** a `people`
key rather than ignore it, so the boundary is enforced by the loader and not by convention. Task 004
reserved a `watchlist` field in the beat schema; rename it and update the validator accordingly.

## Rendering

Report movement, not a ranking. Closer to an analyst noting a change than to a dashboard:

> `FedRAMP PMO` appeared in 6 items this run, against a trailing average of 1.
> `CMMC` appeared in 0, unchanged.

An entity with no mentions and no history does not appear at all. An entity that is quiet **when it
has been active** does appear, marked unchanged — silence is information, and dropping it is the
same class of bug as a standing question vanishing on a quiet day (see task 007).

## The test to apply to any future change here

**Would the operator be comfortable if the person or organization named in this config read the
repository?** If answering requires explanation, the design is wrong regardless of whether the
explanation is correct.
