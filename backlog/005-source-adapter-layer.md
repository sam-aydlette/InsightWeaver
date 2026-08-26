# Generalize ingestion behind a source-adapter interface and add a Federal Register adapter, so the beat can reach sources that do not publish RSS.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
ACCEPTANCE: `make check` passes, plus: `src/sources/base.py` defines a `SourceAdapter` protocol with `fetch(since) -> list[RawItem]`; the existing RSS fetcher is wrapped as `RSSAdapter` with **no behaviour change** (the existing feed tests must pass untouched); a `FederalRegisterAdapter` pulls from the documents API filtered by agency and topic; both adapters normalize to the same `articles` row shape the RSS path already produces, so nothing downstream changes; re-running an adapter over unchanged upstream content inserts **zero** new articles (prove the dedup, do not assume it); and an adapter returning zero items when it previously returned some emits a loud warning rather than a silent thin brief.
OUT OF SCOPE: HTML scraping adapters (FedRAMP Marketplace, CISA BODs, DoD CIO) — those are a separate task once the interface is proven against a structured API first. GovTrack. Changing clustering, frames, questions, synthesis, or any processor — if this task touches `src/processors/` or `src/prompts/`, the abstraction is in the wrong place. Backfilling history; `since` starts from the run. Rate-limit or backoff frameworks beyond what the existing fetcher already does. **Any source whose terms forbid automated retrieval or derivative use** — see the licensing section below; this is a hard boundary, not a preference.
LANDMINES: **The zero-items-is-silent failure is the one that matters.** A misconfigured filter or a changed API contract yields an empty fetch, a thin brief, and no error — the same failure class as the deploy `notify` job that reported success through 12 consecutive failed nights. Every adapter must distinguish "nothing new upstream" from "I could not reach upstream" and treat the second as an error. Federal Register volume is high; without aggressive agency and topic filtering the brief will drown in unrelated rulemaking, and over-filtering will silently hide the documents that matter — tune it against a known week where you can name what *should* appear. Dedup must be content-hash based, not URL based: the same document appears at multiple Federal Register URLs. `src/rss/fetcher.py` normalizes via `normalize_article()`; adapters must produce that same shape or the pipeline will accept malformed rows without complaint. Cost scales with clusters — more sources means more clusters means more synthesis calls, so consider a per-run cluster ceiling before this runs daily. **A "$10.28 per run" figure appeared in an earlier draft of this spec and was wrong**: it was the cost of a Claude Code *development session* in this repo, not of an `insightweaver brief` run. InsightWeaver has no token accounting of its own, so the real per-run cost is unmeasured. Measure it before scaling source count, and do not quote the old number. `main` is protected (5 required checks, `enforce_admins: true`) — open a PR, do not push to it.
---

## Source licensing — a hard constraint on this task

`sam-aydlette/InsightWeaver` is a **public repository**, and the intended end state is a published
feed. That makes ingestion a licensing question, not only an engineering one, and this is the task
that sets the pattern every later adapter will copy.

**Every source must have a recorded basis for use.** Add `SOURCES.md` at the repo root: one row per
source, giving the URL, the adapter, and *why retrieval and derived analysis are permitted* — public
domain (US Government works), an explicit syndication offer (a published RSS feed), or a documented
API's terms. A source with no recorded basis does not ship.

**Prefer government sources, and prefer official APIs over anything else.** For this beat that is
also the better product: Federal Register has a real API, and US Government works are generally not
subject to copyright. Task 005's first adapter is Federal Register precisely because it is the case
where structure and licence are both cleanest.

**Commercial wire content must not feed a beat intended for publication.** `config/feeds/core.json`
carries Associated Press and Reuters. Their terms are restrictive about derivative works and
redistribution. They may remain for the personal brief, which is private use; they must not be
selected into a beat whose output is published. If the beat's tag selection pulls them in, exclude
them explicitly and say why in `SOURCES.md`.

**When HTML adapters land** (a later task, out of scope here): honour `robots.txt`, identify the
client honestly in the User-Agent with a contact URL, rate-limit conservatively, and never route
around an access control. Scraping carries no implied syndication licence the way a published feed
does — the absence of a technical barrier is not permission.

**None of this is legal advice.** It is the minimum posture that keeps the project defensible while
the operator gets actual counsel before anything publishes.

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
