# Add federal-IT trade press to the compliance beat, so it can see events and not only published documents.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
ACCEPTANCE: `make check` passes, plus: at least four federal-IT trade outlets are configured in `config/feeds/` with the beat's existing tags (`regulatory`, `federal_policy`, `cybersecurity`); each has a row in `SOURCES.md` recording its basis for use; the `us-public-sector-compliance` beat resolves them; a live fetch retrieves a non-zero article count from each, and that count is reported in the PR; and `tests/config/test_beats.py` asserts the beat's resolved set now contains at least one non-`.gov` trade source, so a future feed-config edit that silently drops them fails CI.
OUT OF SCOPE: Any source whose terms forbid automated retrieval. Commercial wire services (AP, Reuters) -- rule 2 in `SOURCES.md` stands unchanged and is separate from this task. HTML scraping adapters; every outlet in scope publishes RSS, and if one does not, drop it rather than writing a scraper. Paywalled content. Changing clustering, synthesis, entity matching, or standing questions. Re-tuning the Federal Register filter. Backfilling history.
LANDMINES: **The failure this task fixes was invisible for exactly the reason it will be tempting to declare this done early.** Adding feeds makes article counts go up, and a rising count is not evidence the beat can see an event -- that was the mistake in task 005, which measured 469 documents narrowed to 24 and called the domain covered. Verify against task 010's known-event test, not against volume. Trade RSS feeds are often truncated to a summary with the body behind a click: check that `content` is populated and not just `description`, because a title-only corpus will match entity aliases while giving synthesis nothing to analyze. Several federal-IT outlets publish very high volume including vendor press releases and sponsored posts, which will drown the beat's 50-article curation window if unfiltered -- prefer a topic or category feed over a firehose where the outlet offers one. `main` is protected (5 required checks, `enforce_admins: true`) -- open a PR, do not push to it.
---
Written 2026-08-27, after the beat's first live brief missed the reinstatement of the FedRAMP
director -- the single largest event in the beat's declared domain that week.

## The diagnosis

The tool never had the story. Across 50,983 stored articles there are **3** mentions of FedRAMP,
all incidental (a Schneier post about Microsoft, a vendor's Chief Business Officer hire, an AWS
region launch), and **zero** within two weeks of the event.

Across **207 configured feeds there is not one federal-IT trade outlet**: no Federal News Network,
FedScoop, NextGov, FCW, MeriTalk, Washington Technology, or Government Executive. Every source
matching "Fed" is a primary-document publisher -- Federal *Register*, Federal *Reserve*, Federal
*Trade* Commission, Federal Circuit.

The beat's nine sources produced articles from exactly two in the run's window: Federal Register
(21) and SCOTUSblog (21). CISA advisories, White House, both chambers of Congress, Education, and
SEC Press Releases all returned zero.

**The beat can see published rules. It cannot see news.** A director being reinstated is not a
Federal Register document, a CISA advisory, or a court opinion.

## Why the gap survived task 005

Three decisions compounded, and none was wrong on its own terms:

1. **005 measured document coverage and reported it as domain coverage.** "469 documents narrowed
   to 24" and "38 documents in 7 days" prove the beat can see *rules*. Neither tests whether it can
   see an *event*. Non-empty was treated as solved.
2. **005's `OUT OF SCOPE` deferred HTML adapters to prove the interface against a structured API
   first.** Defensible sequencing -- but structured APIs are what *governments* publish and trade
   press publishes RSS, so deferring scrapers deferred the whole category of source that reports
   news rather than records rules.
3. **`SOURCES.md` rule 1 said "prefer government sources."** Correct about licensing, and it
   silently became a rule about editorial coverage. Corrected in the same commit as this file.

## What is not the cause

**Task 006's person boundary is not why this was missed**, and it is the first place anyone will
look. Entity matching counts mentions in articles already ingested; with no article there is no
mention, whether or not persons are tracked. Had the article been ingested the pipeline would have
handled it correctly -- clustered into a situation, analyzed by synthesis, counted as FedRAMP PMO
activity. **Do not relax the person boundary in response to this gap.** It is an ingestion problem
and the fix is ingestion.

## Candidate outlets

Federal News Network, FedScoop, NextGov/FCW, MeriTalk, Government Executive, Washington Technology.
Each publishes RSS. Confirm the licence basis for each in `SOURCES.md` before it ships -- a source
with no recorded basis does not ship, and that rule is unchanged.

## The standing questions have the same blind spot

All four declared questions are rule-shaped: statutory dates, authorization status, directive
deadlines, framework divergence. None asks who runs a program or whether an office changed posture.
That is a spec-authoring blind spot mirroring the source one. Out of scope here, noted so it is not
lost: it belongs with a revision of `config/beats/us-public-sector-compliance.json`.
