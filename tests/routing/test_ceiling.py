"""
The ceiling: 1,000 observations against 5 watches route fewer than K.

**Why this test exists.** "Most observations match nothing and die in Tier 1" is
an architectural claim, and an architectural claim that is only observable in
production metrics is one that regresses between releases and is noticed at the
invoice. A routing predicate that is too loose does not raise, does not log and
does not fail any test that only checks it matches what it should. This test
attaches a number to the claim and makes it a gate.

================================================================================
HOW K WAS MEASURED, AND AGAINST WHAT
================================================================================

**The corpus is real article text, not synthesised.** ``ceiling_corpus.jsonl.gz``
holds 1,000 rows taken from the 55,249-article pre-rewrite archive in this
repository's own database, read through a read-only (``immutable=1``) SQLite
handle on 2026-08-31. Nothing was written back and nothing was backfilled; the
extraction was a measurement harness, and what survives it is this fixture plus
the numbers below. Each row carries the article's title, its body
(``normalized_content``, falling back to ``description``, truncated to 4,000
characters), its publication date, and the name and URL of the feed that carried
it. The test loads them through the real write path,
``src.sources.observation.store_observation``, so the observations it routes have
real content hashes, real payload shape and real MinHash signatures.

**The sample is stratified by feed category, deliberately not by trigger word.**
400 rows come from the feeds categorised as this operator's domain
(cybersecurity, security_news, security_alerts, security_analysis,
security_standards, federal_policy, federal_government, legislative, oversight,
budget, fiscal_policy, judicial -- 3,228 articles in total) and 600 from the
whole corpus. Stratifying on the trigger words instead would have been circular:
the corpus would have been defined by the answer. Stratifying on feed category
models what is actually true of an operator -- their feed list is weighted toward
their subject, so a day's ingestion is not a uniform sample of the news.
Selection within each stratum is by BLAKE2b of ``(article id, guid)``, so it is
deterministic and does not depend on row order or on a PRNG.

**The watch side is fixed** by ``ceiling_watches.yaml``: three watches copied
verbatim from the shipped ``config/watches.example.yaml`` and two written for the
fixture. See that file for the provenance of each.

**The measured baseline, 2026-08-31:** 5 of 1,000 observations route, producing
5 links, a fan-out of 0.0050 adjudications per observation considered. All 5 are
attributable to ``cisa-kev-cadence-holds`` (4 on clause 0, 1 on clause 1). The
three shipped watches route zero. That is a real finding about the feed list
rather than a defect in the fixture: across the *entire* 55,249-article corpus,
"fedramp" occurs as a substring in 5 articles and "cmmc" in 6, so a conjunctive
FedRAMP trigger has nothing to match. It is exactly the kind of thing the
unrouted-cluster report exists to make visible.

**K = 20, and here is why that number and not another.** The four widening
regressions below were each measured against this same fixture on 2026-08-31 by
monkeypatching the shipped code:

    baseline (as shipped)                      5 routed,     5 links
    word boundaries deleted                    5 routed,     5 links
    shouted-acronym case rule deleted          5 routed,     5 links
    boundaries and case both deleted           6 routed,     6 links
    clause AND became OR                      33 routed,    37 links
    term/entity constraints dropped        1,000 routed, 5,000 links

K = 20 sits at four times the baseline and below the cheapest of the two
regressions this test can see. It is a gate on *over-routing*, which is the
failure that costs money.

**What this test does NOT gate, stated plainly.** Deleting the word boundaries
moves this number by zero, and deleting boundaries and case together moves it by
one. It cannot gate them, because every surface form in a realistic compliance
watch set is either a shouted acronym (protected by the case rule) or a phrase
with no common host word. Word-boundary regression is gated by
``tests/routing/test_predicate.py::TestWordBoundariesAreLoadBearing``, whose
cases are all non-shouted terms and which was verified to fail with the anchors
deleted. Saying this test covers boundaries would be false.

Added 2026-08-31 for backlog task 015.
"""

from __future__ import annotations

import gzip
import json
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, RSSFeed
from src.position import load_position, load_watches
from src.routing import route
from src.sources.base import RawItem
from src.sources.observation import store_observation

FIXTURES = Path(__file__).parent / "fixtures"
CORPUS = FIXTURES / "ceiling_corpus.jsonl.gz"
WATCHES = FIXTURES / "ceiling_watches.yaml"
EXAMPLE_POSITION = Path(__file__).resolve().parents[2] / "config" / "position.example.yaml"

TODAY = date(2026, 8, 31)

# The gate. See the module docstring for how it was measured and what it can and
# cannot see. Lowering it is a tightening and is welcome; raising it is a claim
# that Tier 1 should hand the adjudicator more work, and needs the same kind of
# measurement that produced it.
CEILING = 20

# The baseline as measured on 2026-08-31. Pinned separately from the ceiling: the
# ceiling is the gate, this is the tripwire, and a change in either direction is
# worth seeing rather than absorbing into the headroom.
MEASURED_ROUTED = 5
MEASURED_LINKS = 5


def _parse_published(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


class _WatchRow:
    def __init__(self, watch):
        self.id = watch.id
        self.triggers = watch.triggers_json()
        self.expires = watch.expires


@pytest.fixture(scope="module")
def corpus_rows():
    with gzip.open(CORPUS, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


@pytest.fixture(scope="module")
def ceiling_watches():
    position = load_position(EXAMPLE_POSITION, today=TODAY)
    return load_watches(WATCHES, position=position, today=TODAY)


@pytest.fixture(scope="module")
def routed(corpus_rows, ceiling_watches):
    """
    The whole corpus stored as real observations, then routed. Built once.

    Module-scoped because storing 1,000 observations computes 1,000 MinHash
    signatures, and doing that per test would make the suite slow for no extra
    confidence.
    """
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    feeds: dict[str, RSSFeed] = {}
    for index, row in enumerate(corpus_rows):
        key = row["source_url"] or row["source_name"]
        if key not in feeds:
            feed = RSSFeed(
                url=row["source_url"] or f"about:blank#{row['source_name']}",
                name=row["source_name"] or "unknown",
            )
            session.add(feed)
            session.flush()
            feeds[key] = feed
        store_observation(
            session,
            feeds[key],
            RawItem(
                guid=row["guid"] or f"row-{index}",
                url=row["url"],
                title=row["title"],
                normalized_content=row["body"],
                published_date=_parse_published(row["published_date"]),
                language=row["language"],
            ),
        )
    session.flush()

    report = route(session, today=TODAY, watches=[_WatchRow(watch) for watch in ceiling_watches])
    yield report
    session.close()


class TestTheFixtureIsWhatTheCeilingWasMeasuredAgainst:
    """
    If the corpus or the watch set drifts, K is a number about something else.

    A ceiling measured against one corpus and asserted against another is not a
    gate, it is a coincidence.
    """

    def test_the_corpus_is_one_thousand_rows(self, corpus_rows):
        assert len(corpus_rows) == 1000
        assert len({row["guid"] for row in corpus_rows}) == 1000

    def test_the_corpus_is_real_article_text(self, corpus_rows):
        """
        Real, not synthesised: 86 distinct feeds and bodies of realistic length.

        Synthetic strings written by whoever wrote the test would make K a
        number about the test author's imagination.
        """
        assert len({row["source_name"] for row in corpus_rows}) == 86
        bodies = [len(row["body"]) for row in corpus_rows]
        assert sum(bodies) // len(bodies) == 896

    def test_there_are_five_watches(self, ceiling_watches):
        assert [w.id for w in ceiling_watches] == [
            "fedramp-conmon-scope-expands",
            "fedramp-20x-supersedes-rev5",
            "compliance-hiring-market-tightens",
            "cisa-kev-cadence-holds",
            "nist-800-53-revision-lands",
        ]

    def test_every_observation_was_stored_and_considered(self, routed):
        assert routed.considered == 1000


class TestTheCeiling:
    def test_fewer_than_k_observations_route(self, routed):
        assert routed.routed_count < CEILING, (
            f"{routed.routed_count} of {routed.considered} observations routed, ceiling is "
            f"{CEILING}. Tier 1 is the cost control and every routed observation is one "
            f"adjudication. Per watch: {routed.per_watch}. Per clause: {routed.per_clause}."
        )

    def test_fewer_than_k_links_are_produced(self, routed):
        """
        Links, not routed observations, are what the adjudicator is billed for.

        One observation routed to three watches is three adjudications. The two
        numbers diverge exactly when a term is added to several watches at once,
        which is why both are asserted.
        """
        assert len(routed.links) < CEILING, (
            f"{len(routed.links)} links from {routed.considered} observations, ceiling is "
            f"{CEILING}. Per clause: {routed.per_clause}."
        )

    def test_the_measured_baseline_has_not_moved(self, routed):
        """
        The tripwire. Any change to selectivity shows up here before the gate.

        If this fails and the ceiling test still passes, routing changed within
        the headroom -- which may be entirely correct, and should be re-measured
        and re-recorded rather than absorbed.
        """
        assert (routed.routed_count, len(routed.links)) == (MEASURED_ROUTED, MEASURED_LINKS)

    def test_almost_everything_dies_here(self, routed):
        """The architectural claim, in the direction it is claimed."""
        assert routed.unrouted_count == routed.considered - routed.routed_count
        assert routed.unrouted_count / routed.considered > 0.95

    def test_the_unrouted_are_reported_as_hashes_not_as_a_number(self, routed):
        """A bare integer is not a coverage-gap signal. See src/routing/gaps.py."""
        assert len(routed.unrouted) == routed.unrouted_count
        assert all(h.startswith("sha256:") for h in routed.unrouted)


class TestWideningIsAttributable:
    def test_every_link_names_the_clause_that_produced_it(self, routed):
        """
        "Watch X routed 400" is a bill. "Clause 2 of watch X routed 400" is a diff.

        Without the clause index there is no way to tell which line of the
        watch file to edit.
        """
        assert sum(routed.per_clause.values()) == len(routed.links)
        for (watch_id, clause_index), count in routed.per_clause.items():
            assert watch_id in routed.per_watch
            assert clause_index >= 0
            assert count > 0
