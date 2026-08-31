# Close the legacy article write path that bypasses observations, before Tier 1 depends on the corpus being complete.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: small
BLOCKS: 015-tier1-deterministic-routing
ACCEPTANCE: `make check` passes, plus: `RSSFetcher.fetch_and_store_feed` either routes through `src/sources/store.py:store_items` so every article it writes gets an observation in the same transaction, **or** raises rather than writing -- whichever the implementer judges correct, with the reasoning in the PR; the "one write path" test from task 014 is extended so it would fail if a second article-writing path is reintroduced; and a test drives the legacy entry point and asserts the observation count moves in step with the article count, or that the call refuses.
OUT OF SCOPE: Backfilling observations for the 55,249 pre-existing articles -- that is a separate, bounded, mechanical task and task 014 states the rule that makes it safe to defer. Rewriting the RSS fetcher, changing its normalization, or touching `src/sources/rss_adapter.py`, which already goes through the correct path. Deleting `src/rss/` wholesale.
LANDMINES: **This is unreachable today and that is exactly why it is dangerous.** Task 012 deleted the orchestrator that called `fetch_all_active_feeds`, so no in-repo caller remains and the reviewer confirmed it -- but the function is live, exported, and is the obvious thing to reach for when someone wants to refresh the corpus. The lead ran that path twice on 2026-08-28 to fetch feeds. An article written through it has **no observation**, so Tier 1 cannot route it, and the failure is silent: the corpus grows, routing finds nothing, and the coverage gap looks like a source problem rather than an ingestion one. **Do not fix this by adding a second observation write.** Task 014's invariant is that exactly one code path constructs an `Observation`; a parallel write here satisfies the symptom and destroys the property. `main` is protected -- open a PR.
---
Written 2026-08-31, from task 014's review.

Task 014 established that adapters emit observations through exactly one path, enforced by a test
that greps the source tree. The reviewer confirmed the property holds **as shipped**, and flagged
the one residual: `src/rss/fetcher.py`'s `fetch_and_store_feed` writes articles directly, and
`fetch_all_active_feeds` still reaches it.

The IC disclosed this rather than widening its own diff to fix it, which was correct. It is closed
here because task 015 makes it consequential: routing reads observations, so a corpus refreshed
through the legacy path produces articles that can never route, and nothing surfaces that.

The likely right answer is to raise. The RSS adapter already covers this ground and goes through
`store_items`; a second, older entry point that does the same job worse is a hazard whether or not
it currently has a caller. But the implementer should check whether anything outside this
repository -- a cron entry, a systemd timer, a shell script on the operator's machine -- calls it
before removing the ability to call it at all. The reviewer could only verify there is no in-repo
caller.
