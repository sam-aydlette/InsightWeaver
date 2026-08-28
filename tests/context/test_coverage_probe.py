"""
Tests for running a beat's coverage probes against the corpus.

Every corpus here is synthetic and built by the test that reads it. None of it
touches the live database, and no test names an event that has to still be in
retention: this is a test of the matcher and the verdict logic, not of what the
operator's corpus happens to hold today. Pinning live events into CI would make
the suite fail for reasons that have nothing to do with the code under test.

The collision surface is the point of interest, and it is measured rather than
asserted from intuition. On this repository's corpus on 2026-08-27, of 54,044
stored articles 657 titles contain the substring ``nist`` and exactly 4 are
about NIST. :class:`TestSubstringMatchingWouldLie` reproduces that ratio in
miniature and shows both matchers side by side.
"""

from datetime import date, datetime

import pytest
from sqlalchemy.orm import sessionmaker

from src.config.beats import BeatConfig, BeatSource, CoverageProbe
from src.config.feed_matcher import Feed
from src.context.coverage_probe import (
    STATUS_INCONCLUSIVE,
    STATUS_MATCHED,
    STATUS_UNMATCHED,
    compile_probe,
    run_coverage_probes,
)
from src.database.models import Article, RSSFeed

# Titles that contain "nist" as a substring and are about nothing of the kind.
# Drawn from the words the real collision was made of: administration, minister,
# Afghanistan, communist, sinister, columnist, agonist.
NIST_COLLISIONS = [
    "The administration reshuffles its priorities",
    "Prime minister addresses the assembly",
    "Afghanistan aid package clears committee",
    "A communist party congress opens",
    "A sinister turn in the negotiations",
    "Our columnist on the week in politics",
    "Beta agonist trial results published",
    "Administrative law judges face a backlog",
    "Ministry of Defence confirms the order",
]
NIST_REAL = [
    "NIST is rethinking its role in analyzing software vulnerabilities",
    "NIST and MITRE partner to test AI defense technology",
]


def probe(**overrides):
    fields = {
        "date": date(2026, 8, 24),
        "what": "an event",
        "terms": ("NIST",),
        "any_of": (("vulnerabilit*", "partner*"),),
        "window_days": 14,
    }
    fields.update(overrides)
    return CoverageProbe(**fields)


def text_of(title):
    return title


class TestTermMatching:
    """Pure matching, no database."""

    def test_a_required_term_must_be_present(self):
        compiled = compile_probe(probe(terms=("FedRAMP", "PMO"), any_of=()))
        assert compiled.matches("The FedRAMP PMO published guidance")
        assert not compiled.matches("The FedRAMP program published guidance")

    def test_each_any_of_group_needs_one_member(self):
        compiled = compile_probe(
            probe(terms=("FedRAMP",), any_of=(("director", "administrator"), ("reinstat*",)))
        )
        assert compiled.matches("FedRAMP director reinstated after review")
        assert compiled.matches("FedRAMP administrator reinstatement confirmed")
        assert not compiled.matches("FedRAMP director named after review")

    def test_missing_reports_which_requirement_went_unmet(self):
        compiled = compile_probe(probe(terms=("FedRAMP",), any_of=(("director", "administrator"),)))
        absent, unsatisfied = compiled.missing("CISA director named")
        assert absent == ("FedRAMP",)
        assert unsatisfied == ()

        absent, unsatisfied = compiled.missing("FedRAMP authorizations paused")
        assert absent == ()
        assert unsatisfied == (("director", "administrator"),)


class TestSubstringMatchingWouldLie:
    """
    The word-boundary requirement, shown biting.

    Both matchers are run over the same nine collisions and two real articles.
    The substring matcher reports 11 of 11; the probe matcher reports 2 of 11.
    """

    def test_substring_matching_reports_every_collision(self):
        naive = [t for t in NIST_COLLISIONS + NIST_REAL if "nist" in t.lower()]
        assert len(naive) == 11

    def test_probe_matching_reports_only_the_real_ones(self):
        compiled = compile_probe(probe(terms=("NIST",), any_of=(("rethinking", "partner*"),)))
        matched = [t for t in NIST_COLLISIONS + NIST_REAL if compiled.matches(text_of(t))]
        assert matched == NIST_REAL

    @pytest.mark.parametrize("title", NIST_COLLISIONS)
    def test_no_collision_matches_even_the_bare_term(self, title):
        """For these lowercase collisions it is the case rule, not the boundary, that rejects them: every term here is shouted, so the compiled pattern is case-sensitive and never reaches the anchors. Verified 2026-08-27 by deleting LEFT_BOUNDARY/RIGHT_BOUNDARY from entity_matcher and re-running this class -- all 12 still passed. See TestBoundariesAreLoadBearingForShoutedTermsToo, which holds case constant so only the anchor can refuse the match."""
        compiled = compile_probe(probe(terms=("NIST", "the"), any_of=()))
        assert not compiled.matches(title)

    def test_an_acronym_only_matches_when_it_is_shouted(self):
        """Inherited from entity matching: BOD is a directive, bod is not."""
        compiled = compile_probe(probe(terms=("BOD", "issued"), any_of=()))
        assert compiled.matches("CISA issued BOD 22-01")
        assert not compiled.matches("A bod issued a statement")


# All-caps collisions, for holding case constant while the boundary is tested.
# Each headline embeds a shouted probe term inside a longer shouted word, so
# case-sensitivity cannot be the thing that rejects it. The words are the ones
# the hazard is actually made of: DOPMA is the Defense Officer Personnel
# Management Act, PRECISA is ordinary Portuguese, and an all-caps headline is a
# normal thing for a wire feed to emit.
SHOUTED_COLLISIONS = [
    # (probe term, second required term that IS present, headline)
    ("OPM", "REPORT", "COMPTROLLER REPORT ON DOPMA REFORM ADVANCES"),
    ("OPM", "REPORT", "AGENCY REPORT NAMES TOPMOST PRIORITIES"),
    ("BOD", "CISA", "BODY CAMERA RULE ADVANCES AT CISA"),
    ("BOD", "CISA", "CISA ISSUES BODY CAMERA GUIDANCE"),
    ("OMB", "FBI", "FBI CONFIRMS BOMBING SUSPECT IN CUSTODY"),
    ("CISA", "RELATORIO", "GOVERNO PRECISA DE NOVO RELATORIO SOBRE SEGURANCA"),
]


class TestBoundariesAreLoadBearingForShoutedTermsToo:
    """
    The boundary isolated from the case rule.

    Every collision in :data:`NIST_COLLISIONS` is lowercase, so a shouted term
    like ``NIST`` is already rejected by case-sensitivity before the boundary
    anchors are consulted -- those cases would stay green if the anchors were
    deleted outright. That is not a hypothetical gap: the shipped beat's probes
    are shouted (``OPM``, ``CISA``), so it is exactly the term type in
    production whose anchoring would go unguarded.

    Here the headline and the term are both ALL CAPS. Case is held constant, so
    the boundary anchor is the only thing left that can reject the match. Each
    case was checked against the production regex with the anchors stripped and
    case matching unchanged: all six then match, which is what makes these
    assertions load-bearing rather than incidental.
    """

    @pytest.mark.parametrize(("term", "other", "title"), SHOUTED_COLLISIONS)
    def test_a_shouted_term_inside_a_shouted_word_is_not_a_match(self, term, other, title):
        compiled = compile_probe(probe(terms=(term, other), any_of=()))
        assert not compiled.matches(title)

    @pytest.mark.parametrize(("term", "other", "title"), SHOUTED_COLLISIONS)
    def test_the_second_required_term_is_present_so_only_the_collision_fails(
        self, term, other, title
    ):
        """
        Pins *why* the case above fails. Without this, a headline that simply
        lacked both terms would satisfy the assertion and prove nothing about
        the boundary.
        """
        compiled = compile_probe(probe(terms=(term, other), any_of=()))
        absent, _ = compiled.missing(title)
        assert absent == (term,)

    @pytest.mark.parametrize(
        ("term", "other", "title"),
        [
            ("OPM", "REPORT", "OPM REPORT ON DOPMA REFORM ADVANCES"),
            ("BOD", "CISA", "CISA ISSUES BOD 22-01"),
            ("OMB", "FBI", "FBI CITES OMB MEMO M-26-01"),
            ("CISA", "RELATORIO", "CISA PUBLICA NOVO RELATORIO SOBRE SEGURANCA"),
        ],
    )
    def test_the_same_probe_still_matches_the_term_standing_alone(self, term, other, title):
        """
        The other half of the claim: the anchors reject the collision without
        rejecting the event. A matcher that failed both would pass the tests
        above and be useless.
        """
        compiled = compile_probe(probe(terms=(term, other), any_of=()))
        assert compiled.matches(title)

    def test_the_right_hand_anchor_is_exercised_at_position_zero(self):
        """
        ``BODY CAMERA...`` puts the collision at offset 0, where there is no
        preceding character for the left-hand lookbehind to reject. Only the
        right-hand anchor can refuse it.
        """
        compiled = compile_probe(probe(terms=("BOD",), any_of=()))
        assert not compiled.matches("BODY CAMERA RULE ADVANCES")
        assert compiled.matches("BOD 22-01 ADVANCES")


class TestStems:
    def test_a_stem_must_be_marked(self):
        assert not compile_probe(probe(terms=("reinstat", "x"), any_of=())).matches(
            "x reinstated today"
        )
        assert compile_probe(probe(terms=("reinstat*", "x"), any_of=())).matches(
            "x reinstated today"
        )

    def test_a_stem_still_has_to_start_a_word(self):
        """The left boundary is what does the collision filtering; a stem keeps it."""
        compiled = compile_probe(probe(terms=("ramp*", "the"), any_of=()))
        assert not compiled.matches("the FedRAMP authorization")
        assert compiled.matches("the ramp-up of authorizations")


# ---------------------------------------------------------------------------
# Corpus-backed verdicts
# ---------------------------------------------------------------------------

FEED_URL = "https://example.test/beat-feed"
FEED_NAME = "In-Beat Wire"
OTHER_URL = "https://example.test/other-feed"
OTHER_NAME = "Out-of-Beat Wire"


@pytest.fixture
def session(test_engine):
    maker = sessionmaker(bind=test_engine)
    db = maker()
    yield db
    db.close()


@pytest.fixture
def corpus(session):
    """Two sources, empty. Tests add the articles they need."""
    in_beat = RSSFeed(url=FEED_URL, name=FEED_NAME, category="test")
    outside = RSSFeed(url=OTHER_URL, name=OTHER_NAME, category="test")
    session.add_all([in_beat, outside])
    session.commit()
    return in_beat, outside


def add_article(session, feed, title, when, body=""):
    session.add(
        Article(
            feed_id=feed.id,
            guid=f"{feed.id}-{title}",
            title=title,
            description="",
            normalized_content=body,
            published_date=when,
        )
    )
    session.commit()


def beat_with(probes, feed_urls=(FEED_URL,)):
    return BeatConfig(
        name="test-beat",
        description="",
        sources=(BeatSource(adapter="rss", feed_tags=("regulatory",)),),
        coverage={},
        standing_questions=(),
        channels=("terminal",),
        config_path="<test>",
        coverage_probes=tuple(probes),
    ), list(feed_urls)


def run(session, probes, feed_urls=(FEED_URL,)):
    beat, urls = beat_with(probes, feed_urls)
    return run_coverage_probes(session, beat, feed_urls=urls)


class TestVerdicts:
    def test_a_match_names_the_feed_that_carried_it(self, session, corpus):
        in_beat, _ = corpus
        add_article(
            session, in_beat, "NIST publishes vulnerability guidance", datetime(2026, 8, 25)
        )
        report = run(session, [probe(terms=("NIST",), any_of=(("vulnerabilit*",),))])

        (result,) = report.results
        assert result.status == STATUS_MATCHED
        assert result.match_count == 1
        assert result.matches[0].feed_name == FEED_NAME
        assert result.matches[0].title == "NIST publishes vulnerability guidance"

    def test_articles_in_the_window_that_do_not_match_are_a_failure(self, session, corpus):
        in_beat, _ = corpus
        add_article(session, in_beat, "An unrelated procurement notice", datetime(2026, 8, 25))
        (result,) = run(session, [probe()]).results
        assert result.status == STATUS_UNMATCHED
        assert result.articles_in_window == 1
        assert result.missing_terms == ("NIST",)

    def test_a_match_outside_the_window_does_not_count(self, session, corpus):
        in_beat, _ = corpus
        add_article(session, in_beat, "NIST publishes vulnerability guidance", datetime(2026, 6, 1))
        add_article(session, in_beat, "Something else entirely", datetime(2026, 8, 25))
        (result,) = run(session, [probe()]).results
        assert result.status == STATUS_UNMATCHED

    def test_a_match_on_another_beats_feed_does_not_count_but_is_reported(self, session, corpus):
        in_beat, outside = corpus
        add_article(session, in_beat, "An unrelated procurement notice", datetime(2026, 8, 25))
        add_article(
            session, outside, "NIST publishes vulnerability guidance", datetime(2026, 8, 25)
        )
        (result,) = run(session, [probe()]).results

        assert result.status == STATUS_UNMATCHED
        assert result.elsewhere_count == 1
        assert result.elsewhere[0].feed_name == OTHER_NAME
        assert result.elsewhere[0].in_beat_sources is False

    def test_no_one_carried_it_is_distinguishable_from_someone_else_did(self, session, corpus):
        in_beat, _ = corpus
        add_article(session, in_beat, "An unrelated procurement notice", datetime(2026, 8, 25))
        (result,) = run(session, [probe()]).results
        assert result.status == STATUS_UNMATCHED
        assert result.elsewhere == ()

    def test_the_body_is_searched_not_only_the_title(self, session, corpus):
        in_beat, _ = corpus
        add_article(
            session,
            in_beat,
            "This week in federal cyber",
            datetime(2026, 8, 25),
            body="Elsewhere, NIST said it was rethinking its vulnerability analysis role.",
        )
        (result,) = run(session, [probe(any_of=(("vulnerabilit*",),))]).results
        assert result.status == STATUS_MATCHED

    def test_an_undated_article_can_never_satisfy_a_probe(self, session, corpus):
        """
        An article with no published_date cannot be placed in any window, so it
        must not be able to turn an inconclusive probe into a pass or a failure.
        """
        in_beat, _ = corpus
        add_article(session, in_beat, "NIST vulnerability guidance", None)
        (result,) = run(session, [probe()]).results
        assert result.status == STATUS_INCONCLUSIVE


class TestInconclusive:
    def test_a_probe_predating_the_corpus_is_inconclusive(self, session, corpus):
        in_beat, _ = corpus
        add_article(session, in_beat, "Recent news", datetime(2026, 8, 25))
        (result,) = run(session, [probe(date=date(2021, 11, 3))]).results
        assert result.status == STATUS_INCONCLUSIVE
        assert "predates the corpus" in result.reason

    def test_a_probe_the_corpus_has_not_reached_is_inconclusive(self, session, corpus):
        in_beat, _ = corpus
        add_article(session, in_beat, "Old news", datetime(2026, 1, 5))
        (result,) = run(session, [probe(date=date(2026, 8, 24))]).results
        assert result.status == STATUS_INCONCLUSIVE
        assert "has not reached the event yet" in result.reason

    def test_a_gap_in_the_middle_is_inconclusive_and_says_so(self, session, corpus):
        in_beat, _ = corpus
        add_article(session, in_beat, "Before", datetime(2026, 1, 5))
        add_article(session, in_beat, "After", datetime(2026, 12, 5))
        (result,) = run(session, [probe(date=date(2026, 8, 24))]).results
        assert result.status == STATUS_INCONCLUSIVE
        assert "gap in the corpus" in result.reason

    def test_a_beat_whose_feeds_have_no_rows_is_inconclusive_not_failed(self, session, corpus):
        _, outside = corpus
        add_article(session, outside, "NIST vulnerability guidance", datetime(2026, 8, 25))
        (result,) = run(session, [probe()]).results
        assert result.status == STATUS_INCONCLUSIVE
        assert not result.conclusive


class TestInconclusiveDoesNotShrinkTheProbeSet:
    """
    The landmine: a probe set that quietly decays to the events still in
    retention is a green light that means nothing. The counts must always sum
    back to the number of probes the beat declared.
    """

    @pytest.fixture
    def mixed(self, session, corpus):
        in_beat, _ = corpus
        add_article(
            session, in_beat, "NIST publishes vulnerability guidance", datetime(2026, 8, 25)
        )
        add_article(session, in_beat, "An unrelated notice", datetime(2026, 8, 26))
        return run(
            session,
            [
                probe(what="matches"),
                probe(what="misses", terms=("FedRAMP",), any_of=(("director",),)),
                probe(what="too old", date=date(2021, 11, 3)),
                probe(what="also too old", date=date(2020, 1, 1)),
            ],
        )

    def test_every_declared_probe_appears_in_the_results(self, mixed):
        assert mixed.total == 4
        assert [r.probe.what for r in mixed.results] == [
            "matches",
            "misses",
            "too old",
            "also too old",
        ]

    def test_the_three_counts_sum_to_the_number_declared(self, mixed):
        assert len(mixed.matched) + len(mixed.unmatched) + len(mixed.inconclusive) == mixed.total
        assert (len(mixed.matched), len(mixed.unmatched), len(mixed.inconclusive)) == (1, 1, 2)

    def test_conclusive_is_a_smaller_set_and_says_so(self, mixed):
        assert len(mixed.conclusive) == 2
        assert len(mixed.conclusive) < mixed.total


class TestItNeverWrites:
    """
    The corpus is shared. A question about it must not alter it.
    """

    def test_running_probes_leaves_the_row_counts_alone(self, session, corpus):
        in_beat, _ = corpus
        add_article(session, in_beat, "NIST vulnerability guidance", datetime(2026, 8, 25))
        before = (session.query(Article).count(), session.query(RSSFeed).count())

        run(session, [probe(), probe(date=date(2021, 1, 1))])

        session.expire_all()
        assert (session.query(Article).count(), session.query(RSSFeed).count()) == before

    def test_the_session_is_never_flushed_dirty(self, session, corpus):
        """Nothing is added to the session, so a rollback loses nothing."""
        in_beat, _ = corpus
        add_article(session, in_beat, "NIST vulnerability guidance", datetime(2026, 8, 25))
        run(session, [probe()])
        assert not session.new
        assert not session.deleted
        assert not session.dirty


class TestFeedResolution:
    def test_feed_urls_default_to_the_beats_own_resolution(self, session, corpus, monkeypatch):
        """
        With no explicit ``feed_urls`` the beat resolves its own feeds through
        FeedMatcher, so the command reflects the beat file rather than a caller's
        idea of it.
        """
        in_beat, _ = corpus
        add_article(
            session, in_beat, "NIST publishes vulnerability guidance", datetime(2026, 8, 25)
        )

        class FakeMatcher:
            all_feeds = [
                Feed(
                    name=FEED_NAME,
                    url=FEED_URL,
                    scope=[],
                    geo_tags=[],
                    domain_tags=["regulatory"],
                    specialty_tags=[],
                    relevance_score=0.9,
                    source_file="fake.json",
                )
            ]

        monkeypatch.setattr("src.config.beats.FeedMatcher", FakeMatcher)
        beat, _urls = beat_with([probe(any_of=(("vulnerabilit*",),))])
        report = run_coverage_probes(session, beat)

        assert report.feed_names == (FEED_NAME,)
        assert report.results[0].status == STATUS_MATCHED
