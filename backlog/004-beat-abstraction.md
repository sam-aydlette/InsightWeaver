# Add a "beat" abstraction so a brief can be scoped to a subject with its own sources, rather than only to a person with a location and a profession.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
ACCEPTANCE: `make check` passes, plus: `config/beats/<name>.json` defines a beat; `insightweaver brief --beat us-public-sector-compliance` produces a brief drawn only from that beat's sources; `insightweaver brief` with no `--beat` behaves exactly as it does today (prove it — capture output before and diff); a `beats` table records runs per beat so the graph accumulates per subject rather than globally; and tests cover beat loading, validation of a malformed beat file, and the no-beat default path.
OUT OF SCOPE: Non-RSS sources — this task uses only feeds that already exist in `config/feeds/`, so the first beat will be thin, and that is intended. The source-adapter layer is task 005. Entity coverages (006) and standing questions (007). Migrating the existing person-profile to a beat, or deprecating `user_profile.json` — both concepts coexist and the person path must keep working untouched. Multi-user or multi-tenant concerns. Any change to clustering, frames, or synthesis prompts.
LANDMINES: The graph is currently global — `questions`, `predictions`, `decisions`, `narrative_frames` have no beat scoping, so a compliance Question and a personal-news Question would collide in the same table and pollute each other's appearance counts. Decide the scoping explicitly: either add `beat_id` to those tables with a migration, or accept collision and document why. Do not leave it implicit. `src/utils/profile_loader.py` validates `REQUIRED_SECTIONS`/`REQUIRED_FIELDS` against a person-shaped schema; a beat is a different shape and must not be forced through that validator. Feed selection today runs through `applicability` tags (`scope`/`geo_tags`/`domain_tags`/`specialty_tags`) — reuse that mechanism rather than inventing a parallel one. `docs/CONCEPTS.md` documents the graph model and will be wrong after this; update it in the same commit. `main` is protected (5 required checks, `enforce_admins: true`) — open a PR, do not push to it. Note also that tasks 003 and 008 have landed since this spec was written: `src/render/` now holds a `BriefDocument` model plus terminal/markdown/HTML/email renderers, and `insightweaver brief --from-run <id>` replays a stored run without the pipeline. A beat's brief should flow through that same `BriefDocument`, not a parallel rendering path.
---
Step 2 of five. The profile today models a *person* — `geographic_context`, `voting_context`,
`civic_interests`, `congressional_district`. The ask is a *subject*. Those are different shapes
and the second one is also what the informed-citizenry feed needs later, since that is many
beats, not many people.

```json
{
  "name": "us-public-sector-compliance",
  "sources": [ { "adapter": "rss", "feed_tags": ["govtech", "cybersecurity"] } ],
  "coverage": {},
  "standing_questions": [],
  "channels": ["terminal"]
}
```

`coverage` and `standing_questions` are declared empty here on purpose — the schema reserves
them so 006 and 007 do not need a migration, but nothing reads them yet.

The honest expectation: this beat will be thin, because the domain does not publish much RSS.
That thinness is the evidence that task 005 is necessary, and seeing it firsthand is worth more
than taking my word for it.
