# Test a beat against events that actually happened, so "can it see the domain" stops being answered with article counts.
REPO: InsightWeaver
STATUS: DONE              # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
LANDED: PR #17, merged 2026-08-28
ACCEPTANCE: `make check` passes, plus: a beat may declare a `coverage_probes` list of known past events, each with a date, a short description, and the distinctive terms that would appear in any report of it; a new `insightweaver beat coverage NAME` command reports, per probe, whether the corpus contains a matching article and which feed carried it; the command exits **non-zero when any probe is unmatched**, so it can gate; matching is deterministic word-boundary term matching with no LLM call; and a probe whose window predates the corpus is reported as `INCONCLUSIVE` rather than counted as either a pass or a failure.
OUT OF SCOPE: Running the pipeline, synthesis, or any Anthropic call -- this command reads the article corpus only and must work with no API key. Judging whether a *brief* covered an event well; this measures ingestion reach, not analysis quality. Auto-generating probes. Fetching anything. Changing feeds, adapters, clustering, or the standing agenda. Backfilling history to make an old probe match.
LANDMINES: **A probe that passes because its terms are generic is worse than no probe**, since it manufactures the exact confidence this task exists to remove -- require terms distinctive enough that a match is evidence, and test the collision cases the way task 006 did (of 50,983 stored articles, 617 titles contain the substring "nist" and 2 are about NIST). The corpus is shared and read-only: this command must never write. A probe list will rot as the corpus ages past its retention -- that is what `INCONCLUSIVE` is for, and an inconclusive probe must not be silently dropped from the count, because a probe set that quietly shrinks to the ones that still match is a green light that means nothing. Do not make this a pytest fixture with hardcoded events; it is an operator command about live corpus state, and pinning it into CI would make the suite fail for reasons unrelated to the code under test. `main` is protected (5 required checks, `enforce_admins: true`) -- open a PR, do not push to it.
---
Written 2026-08-27, alongside `backlog/009-federal-it-trade-press.md`, from the same failure.

## Why this exists

Task 005 asked "can the beat reach its domain" and answered it with **document counts**: 469
Federal Register documents narrowed to 24 by the filter, 38 retrieved in a 7-day window. Both
numbers are real. Both are green. Neither could have detected that the beat was structurally unable
to see a personnel change, a program pause, or an enforcement action -- because those are not
documents.

The beat's first live brief then missed the reinstatement of the FedRAMP director, the largest
event in its declared domain that week. The corpus held 3 incidental FedRAMP mentions in 50,983
articles and none within two weeks.

**Article count measures whether ingestion is running. It does not measure whether ingestion
reaches the domain.** Those were conflated, and the conflation was invisible precisely because the
number went up.

## The test this replaces

> Name three things that actually happened in this domain this month, then check whether the beat
> can see them.

That question would have caught this on day one. It is cheap, it needs no API call, and unlike a
volume metric it cannot be satisfied by ingesting more of what the beat already reads.

## Shape

```json
"coverage_probes": [
  {
    "date": "2026-08-24",
    "what": "FedRAMP director reinstated",
    "terms": ["FedRAMP"],
    "any_of": [["director", "administrator"], ["reinstat", "return", "restored"]]
  }
]
```

`terms` must all appear; each `any_of` group needs one match. The point of the two-level shape is
that `FedRAMP` alone is too weak to be evidence -- an AWS region-launch post mentions it -- while
requiring an exact headline is too brittle to survive different outlets' phrasing.

## Output

Report the feed that carried each match, not just a boolean. "Matched" tells you the beat saw it;
*which source* tells you whether that was the source you expected or a lucky incidental mention,
and those have different implications for what to fix.

## Relationship to 009

009 adds the sources. **010 is what proves 009 worked.** They should not be verified against each
other's assumptions: 009's PR must report probe results from this command rather than an article
count, which is exactly the substitution that let this gap survive 005. If 009 lands first, this
command's first run is the honest measurement of what it bought.
