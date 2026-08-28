# Sources

Every source InsightWeaver retrieves, and the recorded basis on which retrieval and derived
analysis are permitted. Added 2026-08-26 with backlog task 005.

**Why this file exists.** `sam-aydlette/InsightWeaver` is a public repository and the intended end
state is a published feed. That makes ingestion a licensing question, not only an engineering one.
A source with no recorded basis does not ship. When a new adapter is added, its sources are added
here in the same commit.

**This is not legal advice.** It is the minimum posture that keeps the project defensible while the
operator gets actual counsel before anything publishes.

## The classes of basis used below

| Class | What it means |
| --- | --- |
| **US Government work** | A work of the US federal government, which is generally not subject to copyright (17 U.S.C. 105), retrieved through the agency's own published feed or documented API. The strongest basis available, and the reason Federal Register is the first non-RSS adapter. |
| **US public body** | A publication of a US state or local government body, retrieved through its own published feed. Not federal, so 17 U.S.C. 105 does not apply; the basis is the published feed. |
| **Intergovernmental org** | Public-information output of an intergovernmental organization, retrieved through its own published feed. |
| **Publisher RSS** | A feed the publisher chose to publish. Offering an RSS feed is an explicit syndication offer for headline, summary and link. It is **not** a licence to republish full text, and InsightWeaver does not: it stores what the feed served and produces analysis over it. |
| **Publisher RSS — personal use only** | A publisher's own feed, offered on terms that limit use of the feed to personal, non-commercial purposes and ask for attribution. Retrieval and analysis for the private brief are expressly permitted; the licence does **not** reach a published product, and doing so needs the publisher's written permission first. Added 2026-08-27 for the Government Executive Media Group titles, whose terms grant the feeds explicitly and narrowly. |
| **Commercial wire** | Associated Press and Reuters. Their terms are restrictive about derivative works and redistribution. **They may remain in the personal brief, which is private use. They must not be selected into a beat whose output is published.** |

## Rules this file encodes

1. **Prefer government sources and official APIs when choosing between equivalent sources of the
   same fact.** The Federal Register has a real API and its documents are US Government works, so
   where a primary document exists, read it rather than a report about it.

   **This is a licensing rule. It is not a coverage strategy, and it was misread as one.** Applied
   as sourcing guidance it selects for the sources that structurally cannot report an event: a
   primary document records a *rule*, and a great deal of what matters in this domain is *news*
   first -- who leads a program, whether a deadline is actually being enforced, whether an
   authorization was pulled -- and sometimes never becomes a document at all.

   Corrected 2026-08-27, after the beat's first live brief missed the reinstatement of the FedRAMP
   director. The corpus held 3 incidental FedRAMP mentions in 50,983 articles and none within two
   weeks, because no federal-IT trade outlet was configured at all. Preferring a primary source
   over a secondary one covering the same fact is correct. Preferring primary sources *as a
   category* leaves the beat unable to see anything that is not a published document. See
   `backlog/009-federal-it-trade-press.md`.
2. **Commercial wire content must not feed a beat intended for publication.** AP and Reuters are
   tagged `general_news` / `international` in `config/feeds/core.json` and carry no `regulatory`,
   `federal_policy`, `legislative`, `judicial` or `cybersecurity` tag, so the
   `us-public-sector-compliance` beat's tag selectors do not reach them. This is asserted by
   `tests/config/test_beats.py::test_resolves_to_a_small_us_federal_feed_set`, which fails if
   either wire is ever pulled into that beat. If a future beat's selectors do reach them, exclude
   them explicitly and record the reason here.
3. **No HTML scraping adapters exist yet, and none may be added without following this file's
   rules.** When they land: honour `robots.txt`, identify the client honestly in the User-Agent
   with a contact URL, rate-limit conservatively, and never route around an access control.
   Scraping carries no implied syndication licence the way a published feed does — the absence of
   a technical barrier is not permission.
4. **Identify the client honestly.** The Federal Register adapter sends
   `InsightWeaver/0.1 (+https://github.com/sam-aydlette/InsightWeaver)` and rate-limits itself to
   one request per second. The Federal Register API requires no key and publishes no quota, so
   that discipline is ours to impose.
5. **A publisher's own stated wishes outrank the fact that a feed is technically fetchable.**
   Added 2026-08-27 with backlog task 009. Six federal-IT trade outlets were assessed for that
   task and three were rejected, none of them for a technical reason — the RSS was reachable and
   parsed in every case. The record of what was read, and what it said, is in
   *Federal-IT trade press — the detailed basis* below. **Every licence claim there carries the
   URL it was read at, the date, and whether it was confirmed by retrieving that URL**, because a
   quoted licence term with no traceable source is the same defect as a synthesis claim with no
   citation — and `src/prompts/ANALYSIS_RULES.md`, injected into every synthesis prompt, already
   requires that a single-source claim "name the source explicitly". Hold a licence claim in this
   file to the standard the tool holds its own output to. Rejecting a source on its terms is a
   normal outcome, and the absence of a source from this file's table is not evidence that nobody
   looked at it.

## Adapters

| Adapter | Module | What it reads |
| --- | --- | --- |
| `rss` | `src/sources/rss_adapter.py` (wrapping `src/rss/fetcher.py`) | Any RSS or Atom feed. The default for every source without an explicit `adapter` key in `config/feeds/`. |
| `federal_register` | `src/sources/federal_register.py` | `federalregister.gov/api/v1/documents.json`, filtered server-side by the named queries in `config/sources/federal_register.json`. |

### Federal Register documents API — the detailed basis

- **URL:** `https://www.federalregister.gov/api/v1/documents.json`
- **Key required:** none.
- **Basis for use:** Federal Register documents are works of the US federal government and are
  generally not subject to copyright (17 U.S.C. 105). The Office of the Federal Register publishes
  the API as a public developer interface with no registration and no key.
- **Obligations we impose on ourselves:** honest User-Agent with a contact URL; one request per
  second; the run's whole query budget is one request per configured query (eight as of
  2026-08-26), not per document.
- **What is stored:** the API's own metadata fields — title, abstract, agencies, topics, action,
  docket, comment and effective dates, citation and `html_url`. Document full text is **not**
  fetched.
- **Volume control:** measured 2026-08-26 against the publication week Mon 2026-08-17 to Fri
  2026-08-21, the API reports 469 documents for that week unfiltered and 24 through the configured
  filter. The filter is data, not code, and each query records its rationale in
  `config/sources/federal_register.json`.

### Federal-IT trade press — the detailed basis

Added 2026-08-27 with backlog task 009, which exists because the `us-public-sector-compliance`
beat's first live brief missed the reinstatement of the FedRAMP director. Not a ranking failure:
the article was never ingested, because none of the 207 configured feeds was a federal-IT trade
outlet. Everything matching "Fed" was a primary-document publisher.

Six candidates were assessed. Every one of them serves reachable, parseable RSS, so the decisions
below are about terms and about what the feed actually carries, never about whether the fetch
worked.

**Provenance of every licence claim below.** This file is what says a source is permitted to be
used, and a verbatim quote with no traceable source is the licensing equivalent of a synthesis
claim with no citation. So each claim carries the URL it was read at, the date, and whether it was
confirmed by retrieving that URL. Every retrieval used the honest User-Agent from rule 4.

| # | Claim | URL read | Read on | Status |
| --- | --- | --- | --- | --- |
| 1 | FedScoop `robots.txt`: wildcard group is an empty `Disallow:`; only `GPTBot` is blocked | `https://fedscoop.com/robots.txt` | 2026-08-27 | **Verified** — fetched, HTTP 200 |
| 2 | DefenseScoop `robots.txt`: same | `https://defensescoop.com/robots.txt` | 2026-08-27 | **Verified** — fetched, HTTP 200 |
| 3 | CyberScoop `robots.txt`: same | `https://cyberscoop.com/robots.txt` | 2026-08-27 | **Verified** — fetched, HTTP 200 |
| 4 | Scoop News Group publishes no findable terms page | `https://fedscoop.com/terms-of-service/`, `/terms-of-use/`, `/terms/`, `/privacy-policy/`, and `https://scoopnewsgroup.com/terms/` | 2026-08-27 | **Verified as "not found", not as "does not exist"** — all five returned HTTP 404, and a link scan of the `fedscoop.com` homepage found no terms, privacy, legal or copyright link. A terms page that exists somewhere I did not look would not have shown up. Treat this basis as the feed alone. |
| 5 | Nextgov/FCW `robots.txt`: wildcard group is `Crawl-delay: 1` plus five `Disallow:` paths, none matching `/rss/`; `GPTBot` blocked | `https://www.nextgov.com/robots.txt` | 2026-08-27 | **Verified** — fetched, HTTP 200 |
| 6 | Washington Technology `robots.txt`: **30 bytes, `User-agent: GPTBot` / `Disallow: /` and nothing else — there is no wildcard group at all** | `https://www.washingtontechnology.com/robots.txt` | 2026-08-27 | **Verified** — fetched, HTTP 200. Corrected 2026-08-27: an earlier revision of this file wrongly recorded `Crawl-delay: 1` here by carrying it over from the `govexec.com` and `nextgov.com` files. |
| 7 | Government Executive `robots.txt`: `Crawl-delay: 1`, same five `Disallow:` paths as Nextgov | `https://www.govexec.com/robots.txt` | 2026-08-27 | **Verified** — fetched, HTTP 200 |
| 8 | GEMG terms: the RSS grant, the `except as expressly permitted by GEMG` clause, the automated-access prohibition, and `feedback@govexec.com` | `https://www.govexec.com/about/terms-and-conditions/` | 2026-08-27 | **Verified** — fetched, HTTP 200; each quoted phrase confirmed present by exact substring match against the page text. **Note the path**: `govexec.com/terms/`, `/terms-service/`, `/about/terms/` and the `nextgov.com` and `washingtontechnology.com` equivalents all 404. This page is reachable from the Nextgov and Washington Technology footers as "Terms and Conditions" and is the only copy found. |
| 9 | MeriTalk terms: the automated-access prohibition, and that the page contains no RSS carve-out | `https://www.meritalk.com/terms-of-use/` | 2026-08-27 | **Verified** — fetched, HTTP 200; quote confirmed by exact substring match, and the string "RSS" does not appear anywhere on the page, which is what makes "no carve-out" a checked claim rather than an inference |
| 10 | Federal News Network `robots.txt`: `ClaudeBot`, `Claude-Web`, `anthropic-ai` and `Claude` each `Disallow: /` | `https://federalnewsnetwork.com/robots.txt` | 2026-08-27 | **Verified** — fetched, HTTP 200 |
| 11 | MeriTalk `robots.txt`: permissive; no AI-crawler block | `https://www.meritalk.com/robots.txt` | 2026-08-27 | **Verified** — fetched, HTTP 200. The prohibition on MeriTalk is in its terms, not its `robots.txt`. |

Nothing quoted in this section is unverified. If a future edit adds a licence claim that cannot be
traced to a URL someone actually retrieved, label it unverified in this table rather than leaving
it bare.

**Configured** — `config/feeds/domains/federal_it.json`:

| Outlet | Publisher | `robots.txt` for `*` | Terms | What the feed carries |
| --- | --- | --- | --- | --- |
| FedScoop | Scoop News Group | `Disallow:` (nothing disallowed) | none found — claim 4 | Full `content:encoded`; median 410 stored words |
| DefenseScoop | Scoop News Group | `Disallow:` | none found — claim 4 | Full `content:encoded`; median 586 stored words |
| CyberScoop | Scoop News Group | `Disallow:` | none found — claim 4 | Full `content:encoded`; median 599 stored words |
| Nextgov/FCW — Cybersecurity | Government Executive Media Group | `Crawl-delay: 1`; no `Disallow:` matches `/rss/` | claim 8 | Headline, one-sentence dek, link. **No body** — see the truncation note |
| Washington Technology | Government Executive Media Group | no wildcard group; only `GPTBot` blocked | claim 8 | Headline, one-sentence dek, link. **No body** |

- **Scoop News Group (FedScoop, DefenseScoop, CyberScoop)** — basis: the publisher's own RSS feed,
  the ordinary `Publisher RSS` class. `robots.txt` disallows `GPTBot` and nothing else; the
  wildcard group is an empty `Disallow:` (claims 1-3). No terms page was found (claim 4), so the
  basis is the feed alone and there is no per-site reading to record. Because that is a negative
  finding rather than a positive grant, it is the weaker of the two bases in this section.
- **Government Executive Media Group (Nextgov/FCW, Washington Technology)** — class
  `Publisher RSS — personal use only`. Their terms, read at
  `https://www.govexec.com/about/terms-and-conditions/` on 2026-08-27 (claim 8), grant the feeds
  in these words: *"Some of the Sites may provide an RSS feed (the 'Feeds'). Individuals may use
  the Feeds free of charge - unless otherwise specified - for their personal, non-commercial use
  only,"* with a request for attribution to the specific brand and an address for commercial-use
  requests (`feedback@govexec.com`). The same page otherwise prohibits *"Obtain, copy, monitor,
  index or data mine through the use of a robot, spider, any automated device, or any manual
  process, the Sites or the contents (except as expressly permitted by GEMG)"* — and the Feeds
  clause is that express permission, for personal non-commercial use. **This is a real limit and
  it is recorded, not waived: the current brief is private use and is inside it. Before any beat
  carrying these sources publishes, the operator must either get written permission or drop
  them.** The `us-public-sector-compliance` beat is the beat this file already treats as
  publication-bound (rule 2), so this is the constraint most likely to bite, and it is the one an
  operator should resolve rather than a reviewer wave through.
- **The truncation note.** The GEMG feeds do ship a `<content:encoded>` element, but its CDATA
  markers are themselves escaped, so `feedparser` sanitizes the element to an empty string and the
  stored `content` and `normalized_content` are empty with `word_count` 0. Verified 2026-08-27 by
  storing them: 0 of 5 Nextgov rows and 0 of 11 Washington Technology rows have non-empty content,
  while `description` is populated on every row with the publisher's own one-sentence dek. So they
  are headline-plus-dek sources, not full-text ones. They are still configured, because the
  headline and dek are what makes an *event* visible to the beat at all, and that was the gap.
  They are recorded here so nobody mistakes them for analysable body text. Not fixed here:
  correcting `src/rss/fetcher.py` to recover the escaped CDATA would change ingestion for all
  configured feeds and is outside task 009.

**Assessed and rejected** — deliberately not configured. Recorded so the absences read as
decisions:

| Outlet | Why not |
| --- | --- |
| Federal News Network | Their `robots.txt` (`https://federalnewsnetwork.com/robots.txt`, read 2026-08-27, claim 10) carries an AI-crawler blocklist naming Anthropic's agents specifically: `ClaudeBot`, `Claude-Web`, `anthropic-ai` and `Claude`, each `Disallow: /`, under the comment *"Claude bot used to collect training data for Anthropic LLMs"*. InsightWeaver does not send those User-Agents and the wildcard group does allow the feed path, so this is not a technical prohibition. It is a plainly stated wish not to have this publisher's content collected for LLM processing, which is what this pipeline does with it, and rule 5 says the wish wins. **In fairness to the other reading:** the blocklist is a third-party template that still contains its own instructions (*"Remove comments before publishing - Prepared by ORDO DIGITAL"*), so it may be boilerplate rather than a considered position. The call was made conservatively; their feed is also summary-only (median ~22 words), so little is lost. Revisit if the publisher's position changes. |
| MeriTalk | Their terms of use (`https://www.meritalk.com/terms-of-use/`, read 2026-08-27, claim 9) prohibit: *"Obtain, copy, monitor, index, or data mine through the use of a robot, spider, any automated device, or any manual process, the Web site or the contents (except as expressly permitted by MeriTalk)."* Unlike GEMG there is no clause granting the feed — the string "RSS" does not appear on the page at all — so automated retrieval is forbidden and the source is out of scope by task 009's own terms. Full-text feed and good federal-IT coverage; a written permission request is the only route in. |
| Government Executive | Same publisher and same terms as Nextgov/FCW (claim 8), so it could have shipped on the same basis. Left out on editorial grounds instead: its all-content feed is federal workforce and management news, which is a different subject from this beat's, and 25 items a fetch of it would crowd the curation window without adding compliance signal. Add it if a workforce beat is ever declared. |

**Volume.** The five configured feeds returned 46 items on the first live fetch across a four-day
lookback (10 + 10 + 10 + 5 + 11), which is roughly 15 to 20 new items a day in steady state
against the beat's 50-article curation window. Topic feeds were preferred over firehoses where the
outlet offered one: Nextgov/FCW is its cybersecurity feed rather than `/rss/all/`. Washington
Technology has no topic feeds — `/rss/cybersecurity/` and `/rss/topic/policy/` both 404 — so it is
configured as `/rss/all/`.

## All configured sources

Generated from `config/feeds/**/*.json` on 2026-08-26, and updated 2026-08-27 with the five
federal-IT trade sources added by task 009. Duplicate entries (the same source listed in more than
one tag file) appear once.

| Source | URL | Adapter | Class | Basis for retrieval and derived analysis |
| --- | --- | --- | --- | --- |
| Bureau of Labor Statistics - Employment Situation | `https://www.bls.gov/feed/empsit.rss` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| Bureau of Labor Statistics - News Releases | `https://www.bls.gov/feed/bls_latest.rss` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| CISA Cybersecurity Advisories | `https://www.cisa.gov/cybersecurity-advisories/rss.xml` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| Congress.gov - House Floor Updates | `https://www.congress.gov/rss/house-floor-today.xml` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| Congress.gov - Senate Floor Updates | `https://www.congress.gov/rss/senate-floor-today.xml` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| Fairfax County Board of Supervisors | `https://www.fairfaxcounty.gov/rssfeeds/?show=feedDetails&feedId=876` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| Fairfax County Business News | `https://www.fairfaxcounty.gov/rssfeeds/?show=feedDetails&feedId=862` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| Fairfax County Government NewsWire | `https://www.fairfaxcounty.gov/news/rss/all-newswire.htm` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| Fairfax County Police News | `https://www.fairfaxcounty.gov/rssfeeds/?show=feedDetails&feedId=911` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| Fairfax County Transportation News | `https://www.fairfaxcounty.gov/RSSFeeds/?show=feedDetails&feedId=810` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| Federal Register - Documents API | `https://www.federalregister.gov/api/v1/documents.json` | `federal_register` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| Federal Register - Public Inspection | `https://www.federalregister.gov/documents/feeds/public-inspection.xml` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| Federal Reserve Press Releases | `https://www.federalreserve.gov/feeds/press_all.xml` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| SEC Press Releases | `https://www.sec.gov/news/pressreleases.rss` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| Supreme Court of Virginia Opinions | `https://www.vacourts.gov/static/rss/rss_scv_opinions.xml` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| U.S. Census Bureau | `https://www.census.gov/rss/www/census_blog.xml` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| U.S. Department of Education | `https://www.ed.gov/feed` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| USAGov Blog | `https://blog.usa.gov/feed` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| Virginia Court of Appeals Published Opinions | `https://www.vacourts.gov/static/rss/rss_cav_p_opinions.xml` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| White House News | `https://www.whitehouse.gov/feed/` | `rss` | US Government work | Public domain (17 U.S.C. 105) plus the agency's own published feed. |
| Fairfax County Public Schools News | `https://www.fcps.edu/feeds/news.rss` | `rss` | US public body | Publication of a US public school division, plus its own published feed. |
| European Union News | `https://www.consilium.europa.eu/en/press/rss/` | `rss` | Intergovernmental org | Publisher's own published feed; IGO public-information output. |
| IMF News | `https://www.imf.org/en/News/RSS` | `rss` | Intergovernmental org | Publisher's own published feed; IGO public-information output. |
| United Nations News | `https://news.un.org/feed/subscribe/en/news/all/rss.xml` | `rss` | Intergovernmental org | Publisher's own published feed; IGO public-information output. |
| World Bank News | `https://www.worldbank.org/en/news/rss` | `rss` | Intergovernmental org | Publisher's own published feed; IGO public-information output. |
| Al Jazeera English | `https://www.aljazeera.com/xml/rss/all.xml` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| ALXnow - Alexandria News | `https://www.alxnow.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Arlington County Government News | `https://www.arlingtonva.us/About-Arlington/Newsroom/news-rss-category` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| ARLnow | `https://www.arlnow.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| ARLnow - Arlington Local News | `https://www.arlnow.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Ars Technica | `https://feeds.arstechnica.com/arstechnica/index` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| AWS News Blog | `https://aws.amazon.com/blogs/aws/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Bacon's Rebellion | `https://baconsrebellion.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| BBC News | `https://feeds.bbci.co.uk/news/rss.xml` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Bleeping Computer | `https://www.bleepingcomputer.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Blue Virginia | `https://bluevirginia.us/feed` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Cardinal News | `https://cardinalnews.org/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| CyberScoop | `https://cyberscoop.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). `robots.txt` read 2026-08-27: wildcard group is an empty `Disallow:`, only `GPTBot` blocked. No terms page found (five candidate URLs tried 2026-08-27, all 404) — see claim 4 in *Federal-IT trade press*. Added 2026-08-27 (task 009). |
| Cybersecurity Dive | `https://www.cybersecuritydive.com/feeds/news/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Dark Reading | `https://www.darkreading.com/rss.xml` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| DCist | `https://dcist.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| DefenseScoop | `https://defensescoop.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). `robots.txt` read 2026-08-27: wildcard group is an empty `Disallow:`, only `GPTBot` blocked. No terms page found (five candidate URLs tried 2026-08-27, all 404) — see claim 4 in *Federal-IT trade press*. Added 2026-08-27 (task 009). |
| Education Week | `https://www.edweek.org/feed` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| El Faro English (El Salvador) | `https://elfaro.net/en/feed` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| FedScoop | `https://fedscoop.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). `robots.txt` read 2026-08-27: wildcard group is an empty `Disallow:`, only `GPTBot` blocked. No terms page found (five candidate URLs tried 2026-08-27, all 404) — see claim 4 in *Federal-IT trade press*. Added 2026-08-27 (task 009). |
| FFXnow - Fairfax County News | `https://www.ffxnow.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| France 24 English | `https://www.france24.com/en/rss` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Greater Greater Washington | `https://ggwash.org/feed` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Hacker News | `https://news.ycombinator.com/rss` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Inside Nova - Northern Virginia News | `https://www.insidenova.com/search/?f=rss` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Kathimerini English Edition (Greece) | `https://www.ekathimerini.com/rss` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Krebs on Security | `https://krebsonsecurity.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| MIT Technology Review | `https://www.technologyreview.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Nextgov/FCW - Cybersecurity | `https://www.nextgov.com/rss/cybersecurity/` | `rss` | Publisher RSS — personal use only | **Limited.** Publisher's own feed, granted by GEMG's terms for *personal, non-commercial use only*, with attribution requested — terms read at `https://www.govexec.com/about/terms-and-conditions/` on 2026-08-27 and quotes verified against that page (claim 8). Fine for the private brief; **must not be carried into a published beat without written permission** (`feedback@govexec.com`). Headline and dek only -- no body text survives parsing. Added 2026-08-27 (task 009). |
| NHK World Japan | `https://www3.nhk.or.jp/nhkworld/en/news/rss.xml` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Potomac Local News | `https://www.potomaclocal.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Prince William Living | `https://princewilliamliving.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Supreme Court Blog | `https://www.scotusblog.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| TechCrunch | `https://techcrunch.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| The Hacker News | `https://feeds.feedburner.com/TheHackersNews` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| The Verge | `https://www.theverge.com/rss/index.xml` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| The Zebra (Arlington) | `https://thezebra.org/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Threatpost | `https://threatpost.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Virginia Mercury | `https://virginiamercury.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Virginia Mercury | `https://www.virginiamercury.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Washington Post - Local (DC/MD/VA) | `https://feeds.washingtonpost.com/rss/local` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Washington Post Local (DC/MD/VA) | `https://feeds.washingtonpost.com/rss/local` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Washington Technology | `https://washingtontechnology.com/rss/all/` | `rss` | Publisher RSS — personal use only | **Limited.** Publisher's own feed, granted by GEMG's terms for *personal, non-commercial use only*, with attribution requested — terms read at `https://www.govexec.com/about/terms-and-conditions/` on 2026-08-27 and quotes verified against that page (claim 8). Fine for the private brief; **must not be carried into a published beat without written permission** (`feedback@govexec.com`). Headline and dek only -- no body text survives parsing. Added 2026-08-27 (task 009). |
| WAVY Virginia Politics | `https://www.wavy.com/news/politics/virginia-politics/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| What's Up Prince William (Woodbridge) | `https://whatsupwoodbridge.com/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Wired | `https://www.wired.com/feed/rss` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| WTOP News - Virginia | `https://wtop.com/virginia/feed/` | `rss` | Publisher RSS | Publisher's own published RSS feed (an explicit syndication offer). |
| Associated Press | `https://feeds.ap.org/rss/apf-topnews.rss` | `rss` | Commercial wire | **Restricted.** Personal brief only; excluded from any published beat. |
| Reuters | `https://feeds.reuters.com/reuters/topNews` | `rss` | Commercial wire | **Restricted.** Personal brief only; excluded from any published beat. |

<!-- 74 distinct sources -->

## What has and has not been verified

Stated plainly, because an unverified claim recorded as a fact is worse than no record:

- **Verified by reading:** that the Federal Register API is keyless, reachable and returns the
  fields listed above (exercised 2026-08-26); that AP and Reuters carry no tag the
  `us-public-sector-compliance` beat selects on.
- **Verified by retrieval, 2026-08-27 (task 009):** every licence claim in *Federal-IT trade
  press — the detailed basis*. Eight `robots.txt` files and two terms pages were fetched, each
  returning HTTP 200, and every phrase quoted from them was confirmed present by exact substring
  match against the retrieved page. The URL and read-date for each are in the provenance table in
  that section. **No quote in this file is unattributed, and none is unverified.** Also verified by
  fetching: that each of the five configured trade feeds returns a non-zero article count and
  stores rows, and that `content` is empty on the two GEMG feeds and populated on the three Scoop
  News Group feeds. Verified by reading the stored row: that the FedScoop feed carried the
  FedRAMP leadership change of 2026-08-26 with 320 words of body text -- the specific event the
  beat was blind to. The headline names the official; it is not reproduced here, because a durable
  project artifact is not the "attribute of a specific document event" that
  `backlog/006-institutional-activity.md` permits a person's name to appear as.
- **Verified only as a negative:** that Scoop News Group publishes no terms page. Five candidate
  URLs were tried and all returned 404, and a link scan of the `fedscoop.com` homepage found no
  terms, privacy, legal or copyright link (claim 4). A page that exists somewhere those checks did
  not reach would not have been found, so this is "not found", never "does not exist" — and it
  makes FedScoop, DefenseScoop and CyberScoop the weaker-based of the five configured sources,
  resting on the published feed alone.
- **Corrected 2026-08-27:** an earlier revision of this file recorded `Crawl-delay: 1` for
  Washington Technology's `robots.txt`. It does not say that. The file is 30 bytes, blocks
  `GPTBot`, and has no wildcard group at all; the `Crawl-delay` was carried over in error from the
  `govexec.com` and `nextgov.com` files. Found by re-fetching every cited URL rather than by
  re-reading the prose.
- **Not individually verified:** the terms of service of each of the ~60 `Publisher RSS` sources.
  Their basis is the general one — the publisher chose to publish a feed — not a per-site reading.
  Any source promoted into a beat that publishes needs its own reading before that beat publishes.
- **Not legal advice**, as stated at the top.

## The attribution condition is recorded but not yet met in rendered output

The Government Executive Media Group grant of the Feeds is conditional: it asks for *"attribution
to the specific GEMG brand, including at a minimum a linked logo, a link that returns to the
original URL."*

**The renderers do not currently emit article URLs.** A brief names its sources -- situations carry
numbered citations and thin-coverage entries name the feed -- but no rendered format links back to
the original. For the private terminal brief that is defensible, since there is no audience the
attribution would reach. It is **not** defensible for anything published, and it is a second
condition on top of the personal-use limit already recorded above.

Recorded 2026-08-27, verified against `https://www.govexec.com/about/terms-and-conditions/` the
same day. Before any GEMG-sourced content is published, both must be satisfied: written permission
via `feedback@govexec.com`, and linked attribution in the rendered output.
