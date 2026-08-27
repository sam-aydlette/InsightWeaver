"""
Tests for beat loading and validation.

Two things are being pinned here. First, that a beat file is either loaded
whole or rejected with a message naming the problem -- a beat that half-loads
would produce a brief nobody can account for. Second, that beat source
selection runs through the existing ``applicability`` tags on real feed
configuration rather than through a parallel selector.
"""

import json
from urllib.parse import urlparse

import pytest

from src.config.beats import (
    ENTITY_KINDS,
    SUPPORTED_ADAPTERS,
    BeatConfig,
    BeatNotFound,
    BeatSource,
    BeatValidationError,
    CoverageEntity,
    available_beats,
    load_beat,
)
from src.config.feed_matcher import Feed

# The beat that ships with the repo. Referenced by name so the tests fail if it
# is renamed or removed rather than silently testing nothing.
SHIPPED_BEAT = "us-public-sector-compliance"


def _host(url):
    """The lowercased hostname of a feed URL, minus any trailing dot."""
    return (urlparse(url).hostname or "").lower().rstrip(".")


def write_beat(directory, name, payload):
    """Write a beat file, accepting a dict or a raw string (for bad JSON)."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.json"
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload))
    return path


@pytest.fixture
def beats_dir(tmp_path):
    directory = tmp_path / "beats"
    directory.mkdir()
    return directory


def valid_payload(name="test-beat", **overrides):
    payload = {
        "name": name,
        "description": "A test beat.",
        "sources": [{"adapter": "rss", "feed_tags": ["regulatory"], "geo_tags": ["usa"]}],
        "coverage": {},
        "standing_questions": [],
        "channels": ["terminal"],
    }
    payload.update(overrides)
    return payload


def make_feed(**overrides):
    fields = {
        "name": "Feed",
        "url": "https://example.test/feed",
        "scope": ["always"],
        "geo_tags": ["usa"],
        "domain_tags": ["regulatory"],
        "specialty_tags": [],
        "relevance_score": 0.5,
        "source_file": "core.json",
    }
    fields.update(overrides)
    return Feed(**fields)


class TestLoadingAValidBeat:
    def test_loads_every_declared_field(self, beats_dir):
        write_beat(beats_dir, "test-beat", valid_payload())

        beat = load_beat("test-beat", beats_dir)

        assert isinstance(beat, BeatConfig)
        assert beat.name == "test-beat"
        assert beat.description == "A test beat."
        assert beat.channels == ("terminal",)
        assert beat.config_path.endswith("test-beat.json")
        assert beat.sources == (
            BeatSource(adapter="rss", feed_tags=("regulatory",), geo_tags=("usa",), scope=()),
        )

    def test_optional_fields_default_without_being_required(self, beats_dir):
        write_beat(
            beats_dir,
            "minimal",
            {"name": "minimal", "sources": [{"adapter": "rss", "feed_tags": ["regulatory"]}]},
        )

        beat = load_beat("minimal", beats_dir)

        assert beat.description == ""
        assert beat.coverage == {}
        assert beat.standing_questions == ()
        assert beat.channels == ("terminal",)

    def test_coverage_and_standing_questions_both_round_trip(self, beats_dir):
        """
        Neither block is reserved any more. ``coverage`` is read by task 006
        and round-trips verbatim, so nothing downstream has to reconstruct the
        file; ``standing_questions`` is read by task 007 as the beat's declared
        agenda. This pins that loading one does not disturb the other.
        """
        write_beat(
            beats_dir,
            "reserved",
            valid_payload(
                name="reserved",
                coverage={"orgs": ["CISA"]},
                standing_questions=["Will the rule land?"],
            ),
        )

        beat = load_beat("reserved", beats_dir)

        assert beat.coverage == {"orgs": ["CISA"]}
        assert beat.standing_questions == ("Will the rule land?",)

    def test_standing_questions_keep_declaration_order(self, beats_dir):
        """Order is the human's agenda order, and the brief reports it that way."""
        declared = [
            "Does CMMC Phase 2 slip past its statutory date?",
            "Which CSPs move to FedRAMP authorized?",
            "Does any CISA BOD create an obligation inside 90 days?",
        ]
        write_beat(beats_dir, "ordered", valid_payload("ordered", standing_questions=declared))

        assert load_beat("ordered", beats_dir).standing_questions == tuple(declared)

    def test_standing_questions_are_stripped(self, beats_dir):
        write_beat(
            beats_dir, "spacey", valid_payload("spacey", standing_questions=["  Will it?  "])
        )

        assert load_beat("spacey", beats_dir).standing_questions == ("Will it?",)

    def test_available_beats_lists_files(self, beats_dir):
        write_beat(beats_dir, "b-beat", valid_payload("b-beat"))
        write_beat(beats_dir, "a-beat", valid_payload("a-beat"))

        assert available_beats(beats_dir) == ["a-beat", "b-beat"]

    def test_available_beats_on_missing_directory(self, tmp_path):
        assert available_beats(tmp_path / "nope") == []


class TestMalformedBeatFiles:
    """Every one of these must fail loudly, not load a partial beat."""

    def test_missing_file(self, beats_dir):
        write_beat(beats_dir, "real-beat", valid_payload("real-beat"))

        with pytest.raises(BeatNotFound) as exc:
            load_beat("no-such-beat", beats_dir)

        # The error tells the user what they could have meant.
        assert "real-beat" in str(exc.value)

    def test_not_json(self, beats_dir):
        write_beat(beats_dir, "broken", "{ not json ,,,")

        with pytest.raises(BeatValidationError, match="not valid JSON"):
            load_beat("broken", beats_dir)

    def test_top_level_not_an_object(self, beats_dir):
        write_beat(beats_dir, "listy", ["nope"])

        with pytest.raises(BeatValidationError, match="must be a JSON object"):
            load_beat("listy", beats_dir)

    def test_missing_required_key(self, beats_dir):
        write_beat(beats_dir, "nosources", {"name": "nosources"})

        with pytest.raises(BeatValidationError, match="missing required key\\(s\\): sources"):
            load_beat("nosources", beats_dir)

    def test_unknown_top_level_key(self, beats_dir):
        write_beat(beats_dir, "typo", valid_payload("typo", channelz=["terminal"]))

        with pytest.raises(BeatValidationError, match="unknown key\\(s\\): channelz"):
            load_beat("typo", beats_dir)

    def test_name_must_match_filename(self, beats_dir):
        write_beat(beats_dir, "on-disk", valid_payload("in-file"))

        with pytest.raises(BeatValidationError, match="but the file is named"):
            load_beat("on-disk", beats_dir)

    def test_empty_sources(self, beats_dir):
        write_beat(beats_dir, "empty", valid_payload("empty", sources=[]))

        with pytest.raises(BeatValidationError, match="'sources' must be a non-empty list"):
            load_beat("empty", beats_dir)

    def test_unsupported_adapter(self, beats_dir):
        """Task 005 adds adapters; until then an unknown one is an error."""
        write_beat(
            beats_dir,
            "future",
            valid_payload("future", sources=[{"adapter": "scraper", "feed_tags": ["regulatory"]}]),
        )

        with pytest.raises(BeatValidationError, match="adapter 'scraper' is not supported"):
            load_beat("future", beats_dir)

    def test_source_missing_feed_tags(self, beats_dir):
        write_beat(beats_dir, "notags", valid_payload("notags", sources=[{"adapter": "rss"}]))

        with pytest.raises(BeatValidationError, match=r"sources\[0\] missing required key"):
            load_beat("notags", beats_dir)

    def test_source_with_empty_feed_tags(self, beats_dir):
        write_beat(
            beats_dir,
            "blanktags",
            valid_payload("blanktags", sources=[{"adapter": "rss", "feed_tags": []}]),
        )

        with pytest.raises(BeatValidationError, match=r"sources\[0\].feed_tags must not be empty"):
            load_beat("blanktags", beats_dir)

    def test_source_with_non_string_tag(self, beats_dir):
        write_beat(
            beats_dir,
            "numtag",
            valid_payload("numtag", sources=[{"adapter": "rss", "feed_tags": [7]}]),
        )

        with pytest.raises(BeatValidationError, match="only non-empty strings"):
            load_beat("numtag", beats_dir)

    def test_source_with_unknown_key(self, beats_dir):
        write_beat(
            beats_dir,
            "extrakey",
            valid_payload(
                "extrakey", sources=[{"adapter": "rss", "feed_tags": ["x"], "wat": True}]
            ),
        )

        with pytest.raises(BeatValidationError, match=r"sources\[0\] has unknown key\(s\): wat"):
            load_beat("extrakey", beats_dir)

    def test_coverage_wrong_shape(self, beats_dir):
        write_beat(beats_dir, "badwatch", valid_payload("badwatch", coverage=["CISA"]))

        with pytest.raises(BeatValidationError, match="'coverage' must be an object"):
            load_beat("badwatch", beats_dir)

    def test_standing_questions_wrong_shape(self, beats_dir):
        write_beat(beats_dir, "badsq", valid_payload("badsq", standing_questions={"a": 1}))

        with pytest.raises(BeatValidationError, match="'standing_questions' must be a list"):
            load_beat("badsq", beats_dir)

    def test_standing_question_must_be_a_non_empty_string(self, beats_dir):
        write_beat(beats_dir, "blanksq", valid_payload("blanksq", standing_questions=["  "]))

        with pytest.raises(
            BeatValidationError, match=r"standing_questions\[0\] must be a non-empty"
        ):
            load_beat("blanksq", beats_dir)

    def test_standing_question_must_not_be_an_object(self, beats_dir):
        write_beat(
            beats_dir, "objsq", valid_payload("objsq", standing_questions=[{"question": "x"}])
        )

        with pytest.raises(
            BeatValidationError, match=r"standing_questions\[0\] must be a non-empty"
        ):
            load_beat("objsq", beats_dir)

    def test_duplicate_standing_questions_are_refused(self, beats_dir):
        """
        Refused, not deduplicated: two identical declarations mean the author
        lost track of the agenda, and collapsing them would hide that.
        """
        write_beat(
            beats_dir,
            "dupsq",
            valid_payload("dupsq", standing_questions=["Will it land?", "will it land?"]),
        )

        with pytest.raises(BeatValidationError, match="duplicates an earlier standing question"):
            load_beat("dupsq", beats_dir)

    def test_unknown_channel(self, beats_dir):
        write_beat(beats_dir, "badchan", valid_payload("badchan", channels=["carrier-pigeon"]))

        with pytest.raises(BeatValidationError, match="unknown channel"):
            load_beat("badchan", beats_dir)


class TestSourceMatching:
    """
    Matching reuses the applicability families: ANY within a family, ALL across
    the families a source constrains.
    """

    def test_feed_tags_match_domain_tags(self):
        source = BeatSource(adapter="rss", feed_tags=("regulatory",))

        assert source.matches(make_feed(domain_tags=["regulatory"]))
        assert not source.matches(make_feed(domain_tags=["general_news"]))

    def test_feed_tags_also_match_specialty_tags(self):
        source = BeatSource(adapter="rss", feed_tags=("threat_intelligence",))

        assert source.matches(
            make_feed(domain_tags=["cybersecurity"], specialty_tags=["threat_intelligence"])
        )

    def test_geo_tags_narrow_rather_than_widen(self):
        source = BeatSource(adapter="rss", feed_tags=("cybersecurity",), geo_tags=("usa",))

        assert source.matches(make_feed(domain_tags=["cybersecurity"], geo_tags=["usa"]))
        assert not source.matches(make_feed(domain_tags=["cybersecurity"], geo_tags=[]))

    def test_scope_narrows_too(self):
        source = BeatSource(adapter="rss", feed_tags=("regulatory",), scope=("national",))

        assert source.matches(make_feed(domain_tags=["regulatory"], scope=["national"]))
        assert not source.matches(make_feed(domain_tags=["regulatory"], scope=["local"]))

    def test_adapter_narrows_as_well(self):
        """Added 2026-08-26 (task 005): a source selects one ingestion kind.

        Without this, an RSS source declaration would silently select the
        Federal Register API endpoint and the RSS fetcher would be handed a
        JSON URL.
        """
        rss_source = BeatSource(adapter="rss", feed_tags=("regulatory",))
        api_source = BeatSource(adapter="federal_register", feed_tags=("regulatory",))

        assert rss_source.matches(make_feed(adapter="rss"))
        assert not rss_source.matches(make_feed(adapter="federal_register"))
        assert api_source.matches(make_feed(adapter="federal_register"))
        assert not api_source.matches(make_feed(adapter="rss"))

    def test_a_feed_without_an_adapter_key_is_rss(self):
        """Every pre-2026-08-26 feed entry keeps its exact behaviour."""
        assert BeatSource(adapter="rss", feed_tags=("regulatory",)).matches(make_feed())


class TestShippedBeat:
    """
    The beat that ships with the repo, resolved against the real
    config/feeds/ tree. This is deliberately an assertion about the actual
    corpus: the beat coming out thin is the finding, not a defect.
    """

    def test_loads(self):
        beat = load_beat(SHIPPED_BEAT)

        assert beat.name == SHIPPED_BEAT
        assert beat.channels == ("terminal",)
        # Was "every source is rss" until 2026-08-26. Backlog task 005 added the
        # Federal Register adapter because the RSS half of this beat is nearly
        # empty; the assertion is now that every declared adapter is one this
        # build actually implements, which is the property that mattered.
        assert {source.adapter for source in beat.sources} == {"rss", "federal_register"}
        assert all(source.adapter in SUPPORTED_ADAPTERS for source in beat.sources)

    def test_resolves_to_a_small_us_federal_feed_set(self):
        feeds = load_beat(SHIPPED_BEAT).resolve_feeds()
        names = {feed.name for feed in feeds}

        # Thin by construction: the domain does not publish much RSS. The
        # ceiling was 12 until 2026-08-27, when backlog task 009 added five
        # federal-IT trade feeds; raised to 20 to leave headroom for one more
        # outlet without becoming a licence to grow indefinitely. If this ever
        # exceeds 20, the beat has drifted into being a general news beat and
        # the selector needs re-reading.
        assert 0 < len(feeds) <= 20
        assert "Federal Register - Public Inspection" in names
        assert "CISA Cybersecurity Advisories" in names
        # Added 2026-08-26 (task 005). The RSS half of this beat is nearly
        # empty; the API source is the reason the beat has content at all.
        assert "Federal Register - Documents API" in names

        # And nothing from outside the beat's subject. The two commercial wires
        # are asserted by name: SOURCES.md records that they must never be
        # selected into a beat whose output is published, and this is where
        # that rule is enforced rather than merely written down.
        assert "Associated Press" not in names
        assert "Reuters" not in names
        assert "Krebs on Security" not in names
        assert "ARLnow - Arlington Local News" not in names

    def test_resolves_at_least_one_non_gov_trade_source(self):
        """
        Added 2026-08-27 (task 009). Until then every source this beat resolved
        was a primary-document publisher on a `.gov` host, and the beat's first
        live brief missed the reinstatement of the FedRAMP director: across
        50,983 stored articles there were three incidental FedRAMP mentions and
        none within two weeks of the event, because no federal-IT trade outlet
        was configured at all.

        This asserts the property that was missing, not the volume that was
        already there. A `.gov` feed publishes rules; only a trade outlet
        reports who runs a program, whether a deadline is being enforced, or
        whether an authorization was pulled. A future edit to config/feeds/
        that drops the trade press fails here rather than showing up as a brief
        that is quietly blind again.
        """
        feeds = load_beat(SHIPPED_BEAT).resolve_feeds()

        non_gov = [feed for feed in feeds if not _host(feed.url).endswith(".gov")]
        assert non_gov, (
            "the beat resolves only .gov sources, so it can see published "
            "documents and no reported news -- see backlog/009-federal-it-trade-press.md"
        )

        # Named, so dropping one is a failure and not a shrug. Each has a row
        # in SOURCES.md recording its basis for use.
        names = {feed.name for feed in feeds}
        trade = {
            "FedScoop",
            "DefenseScoop",
            "CyberScoop",
            "Nextgov/FCW - Cybersecurity",
            "Washington Technology",
        }
        assert trade <= names, f"federal-IT trade outlets missing from the beat: {trade - names}"

        # And they are still not wires: SOURCES.md rule 2 is unchanged, and
        # widening the beat to reach trade press must not widen it to reach AP
        # or Reuters. Asserted here as well as above because this test is the
        # one that argues for more non-.gov sources.
        assert "Associated Press" not in names
        assert "Reuters" not in names

    def test_resolution_is_deduplicated_by_url(self):
        feeds = load_beat(SHIPPED_BEAT).resolve_feeds()
        urls = [feed.url for feed in feeds]

        assert len(urls) == len(set(urls))

    def test_resolve_feed_urls_matches_resolve_feeds(self):
        beat = load_beat(SHIPPED_BEAT)

        assert beat.resolve_feed_urls() == [feed.url for feed in beat.resolve_feeds()]


class TestPeopleAreNotTrackable:
    """A beat tracks institutions, never individuals.

    This is enforced by the loader rather than by convention, because the
    repository is public and covers a domain the operator works in: a
    per-person activity ledger would read as surveillance of colleagues
    regardless of the mechanism. Offices are also the better signal --
    personnel rotate, so a name goes silently dark on reassignment and the
    absence reads as inactivity, which is a wrong answer that looks like a
    real one. See backlog/006-institutional-activity.md.
    """

    def test_a_coverage_block_with_people_is_rejected(self, tmp_path):
        beat = tmp_path / "surveil.json"
        beat.write_text(
            json.dumps(
                {
                    "name": "surveil",
                    "sources": [{"adapter": "rss", "feed_tags": ["general_news"]}],
                    "coverage": {"people": ["Some Official"], "orgs": ["GSA"]},
                }
            )
        )
        with pytest.raises(BeatValidationError) as exc:
            load_beat("surveil", beats_dir=tmp_path)
        message = str(exc.value)
        assert "people" in message
        assert "never individuals" in message

    def test_a_coverage_block_without_people_still_loads(self, tmp_path):
        beat = tmp_path / "fine.json"
        beat.write_text(
            json.dumps(
                {
                    "name": "fine",
                    "sources": [{"adapter": "rss", "feed_tags": ["general_news"]}],
                    "coverage": {"orgs": ["GSA"], "programs": ["FedRAMP 20x"]},
                }
            )
        )
        loaded = load_beat("fine", beats_dir=tmp_path)
        assert loaded.coverage == {"orgs": ["GSA"], "programs": ["FedRAMP 20x"]}

    def test_a_person_shaped_key_by_any_other_name_is_also_rejected(self, tmp_path):
        """
        The `people` rejection is specific; the kind vocabulary is closed.
        Renaming the block does not get a person list past the loader, which
        is what keeps the boundary from depending on one blacklisted word.
        """
        beat = tmp_path / "renamed.json"
        beat.write_text(
            json.dumps(
                {
                    "name": "renamed",
                    "sources": [{"adapter": "rss", "feed_tags": ["general_news"]}],
                    "coverage": {"officials": ["A Name"]},
                }
            )
        )
        with pytest.raises(BeatValidationError) as exc:
            load_beat("renamed", beats_dir=tmp_path)
        message = str(exc.value)
        assert "officials" in message
        assert "never individuals" in message

    def test_no_entity_can_carry_a_person_kind(self, tmp_path):
        """There is no spelling of `kind` that produces a person entity."""
        beat = tmp_path / "kinds.json"
        beat.write_text(
            json.dumps(
                {
                    "name": "kinds",
                    "sources": [{"adapter": "rss", "feed_tags": ["general_news"]}],
                    "coverage": {"orgs": ["GSA"], "programs": [], "document_types": []},
                }
            )
        )
        loaded = load_beat("kinds", beats_dir=tmp_path)
        assert {entity.kind for entity in loaded.entities} <= ENTITY_KINDS
        assert "person" not in ENTITY_KINDS
        assert "people" not in ENTITY_KINDS


class TestCoverageEntities:
    """
    The parsed view of `coverage`: what the institutional activity pass reads.

    The raw block still round-trips on `BeatConfig.coverage`; `entities` is the
    same content typed, with the plural config key mapped to the singular kind.
    """

    def test_short_form_entry_is_a_bare_canonical_name(self, beats_dir):
        write_beat(beats_dir, "short", valid_payload("short", coverage={"orgs": ["GSA"]}))

        entities = load_beat("short", beats_dir).entities

        assert entities == (CoverageEntity(kind="org", name="GSA"),)
        assert entities[0].terms == ("GSA",)

    def test_long_form_entry_carries_aliases(self, beats_dir):
        write_beat(
            beats_dir,
            "long",
            valid_payload(
                "long",
                coverage={
                    "orgs": [
                        {
                            "name": "CISA",
                            "aliases": ["Cybersecurity and Infrastructure Security Agency"],
                        }
                    ]
                },
            ),
        )

        entity = load_beat("long", beats_dir).entities[0]

        assert entity.kind == "org"
        assert entity.name == "CISA"
        assert entity.aliases == ("Cybersecurity and Infrastructure Security Agency",)
        assert entity.terms[0] == "CISA", "canonical name comes first"

    def test_each_block_maps_to_its_kind(self, beats_dir):
        write_beat(
            beats_dir,
            "kinds",
            valid_payload(
                "kinds",
                coverage={
                    "orgs": ["GSA"],
                    "programs": ["CMMC"],
                    "document_types": ["Emergency Directive"],
                },
            ),
        )

        entities = load_beat("kinds", beats_dir).entities

        assert [(e.kind, e.name) for e in entities] == [
            ("org", "GSA"),
            ("program", "CMMC"),
            ("document_type", "Emergency Directive"),
        ]

    def test_terms_deduplicate_a_repeated_alias(self, beats_dir):
        write_beat(
            beats_dir,
            "dupe",
            valid_payload("dupe", coverage={"orgs": [{"name": "GSA", "aliases": ["GSA", "GSA"]}]}),
        )

        assert load_beat("dupe", beats_dir).entities[0].terms == ("GSA",)

    def test_an_absent_coverage_block_yields_no_entities(self, beats_dir):
        write_beat(beats_dir, "none", valid_payload("none"))

        assert load_beat("none", beats_dir).entities == ()

    def test_the_shipped_beat_declares_only_institutions(self):
        entities = load_beat(SHIPPED_BEAT).entities

        assert entities, "the shipped beat should declare coverage"
        assert {entity.kind for entity in entities} <= ENTITY_KINDS


class TestMalformedCoverage:
    def test_block_must_be_a_list(self, beats_dir):
        write_beat(beats_dir, "bad", valid_payload("bad", coverage={"orgs": "GSA"}))

        with pytest.raises(BeatValidationError, match="'coverage.orgs' must be a list"):
            load_beat("bad", beats_dir)

    def test_entry_must_be_a_string_or_an_object(self, beats_dir):
        write_beat(beats_dir, "bad", valid_payload("bad", coverage={"orgs": [17]}))

        with pytest.raises(BeatValidationError, match=r"coverage\.orgs\[0\] must be a string"):
            load_beat("bad", beats_dir)

    def test_entry_object_needs_a_name(self, beats_dir):
        write_beat(beats_dir, "bad", valid_payload("bad", coverage={"orgs": [{"aliases": []}]}))

        with pytest.raises(BeatValidationError, match="missing required key 'name'"):
            load_beat("bad", beats_dir)

    def test_entry_object_rejects_unknown_keys(self, beats_dir):
        write_beat(
            beats_dir,
            "bad",
            valid_payload("bad", coverage={"orgs": [{"name": "GSA", "role": "signs things"}]}),
        )

        with pytest.raises(BeatValidationError, match="unknown key"):
            load_beat("bad", beats_dir)

    def test_empty_name_is_rejected(self, beats_dir):
        write_beat(beats_dir, "bad", valid_payload("bad", coverage={"orgs": ["  "]}))

        with pytest.raises(BeatValidationError, match="non-empty 'name'"):
            load_beat("bad", beats_dir)

    def test_alias_must_be_a_non_empty_string(self, beats_dir):
        write_beat(
            beats_dir,
            "bad",
            valid_payload("bad", coverage={"orgs": [{"name": "GSA", "aliases": [""]}]}),
        )

        with pytest.raises(BeatValidationError, match="non-empty strings"):
            load_beat("bad", beats_dir)

    def test_a_duplicated_entity_is_rejected(self, beats_dir):
        write_beat(
            beats_dir,
            "bad",
            valid_payload("bad", coverage={"orgs": ["GSA", {"name": "GSA"}]}),
        )

        with pytest.raises(BeatValidationError, match="declares 'GSA' more than once"):
            load_beat("bad", beats_dir)
