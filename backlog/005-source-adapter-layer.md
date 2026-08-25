# Generalize ingestion behind a source-adapter interface and add a Federal Register adapter, so the beat can reach sources that do not publish RSS.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
ACCEPTANCE: `make check` passes, plus: `src/sources/base.py` defines a `SourceAdapter` protocol with `fetch(since) -> list[RawItem]`; the existing RSS fetcher is wrapped as `RSSAdapter` with **no behaviour change** (the existing feed tests must pass untouched); a `FederalRegisterAdapter` pulls from the documents API filtered by agency and topic; both adapters normalize to the same `articles` row shape the RSS path already produces, so nothing downstream changes; re-running an adapter over unchanged upstream content inserts **zero** new articles (prove the dedup, do not assume it); and an adapter returning zero items when it previously returned some emits a loud warning rather than a silent thin brief.
OUT OF SCOPE: HTML scraping adapters (FedRAMP Marketplace, CISA BODs, DoD CIO) — those are a separate task once the interface is proven against a structured API first. GovTrack. Changing clustering, frames, questions, synthesis, or any processor — if this task touches `src/processors/` or `src/prompts/`, the abstraction is in the wrong place. Backfilling history; `since` starts from the run. Rate-limit or backoff frameworks beyond what the existing fetcher already does.
LANDMINES: **The zero-items-is-silent failure is the one that matters.** A misconfigured filter or a changed API contract yields an empty fetch, a thin brief, and no error — the same failure class as the deploy `notify` job that reported success through 12 consecutive failed nights. Every adapter must distinguish "nothing new upstream" from "I could not reach upstream" and treat the second as an error. Federal Register volume is high; without aggressive agency and topic filtering the brief will drown in unrelated rulemaking, and over-filtering will silently hide the documents that matter — tune it against a known week where you can name what *should* appear. Dedup must be content-hash based, not URL based: the same document appears at multiple Federal Register URLs. `src/rss/fetcher.py` normalizes via `normalize_article()`; adapters must produce that same shape or the pipeline will accept malformed rows without complaint. Cost scales with clusters — the last full run cost $10.28, and more sources means more synthesis calls; consider a per-run cluster ceiling before this runs daily. Local `main` is 11 commits ahead of `origin`; do not push.
---
Step 3 of five, and the one that decides whether the beat is real. `CLAUDE.md:45` said "RSS is
the only input source"; that rule was relaxed deliberately on 2026-08-25 because the domain does
not publish enough RSS to support the brief. Update that line in the same commit — leaving it
stale would make the file lie about its own architecture.

The trick that keeps this from becoming a rewrite: **adapters change ingestion, not the pipeline.**
Every adapter emits the same normalized article shape the RSS path already produces. Clustering,
frames, questions, predictions, and synthesis are untouched. If you find yourself editing a
processor, stop — the seam is wrong.

Federal Register first because it is structured, documented, stable, and the single highest-value
source for this domain. Prove the interface against it before writing anything that parses HTML.
