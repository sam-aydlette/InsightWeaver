"""
Tests for beat loading and validation.

Two things are being pinned here. First, that a beat file is either loaded
whole or rejected with a message naming the problem -- a beat that half-loads
would produce a brief nobody can account for. Second, that beat source
selection runs through the existing ``applicability`` tags on real feed
configuration rather than through a parallel selector.
"""

import json

import pytest

from src.config.beats import (
    BeatConfig,
    BeatNotFound,
    BeatSource,
    BeatValidationError,
    available_beats,
    load_beat,
)
from src.config.feed_matcher import Feed

# The beat that ships with the repo. Referenced by name so the tests fail if it
# is renamed or removed rather than silently testing nothing.
SHIPPED_BEAT = "us-public-sector-compliance"


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

    def test_coverage_and_standing_questions_are_reserved_not_read(self, beats_dir):
        """
        Task 006 and 007 own these. They round-trip so those tasks need no
        migration, but nothing in this codebase consumes them yet.
        """
        write_beat(
            beats_dir,
            "reserved",
            valid_payload(
                name="reserved",
                coverage={"entities": ["CISA"]},
                standing_questions=["Will the rule land?"],
            ),
        )

        beat = load_beat("reserved", beats_dir)

        assert beat.coverage == {"entities": ["CISA"]}
        assert beat.standing_questions == ("Will the rule land?",)

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
        assert all(source.adapter == "rss" for source in beat.sources)

    def test_resolves_to_a_small_us_federal_feed_set(self):
        feeds = load_beat(SHIPPED_BEAT).resolve_feeds()
        names = {feed.name for feed in feeds}

        # Thin by construction: the domain does not publish much RSS. If this
        # ever exceeds a dozen feeds, the beat has drifted into being a
        # general news beat and the selector needs re-reading.
        assert 0 < len(feeds) <= 12
        assert "Federal Register - Public Inspection" in names
        assert "CISA Cybersecurity Advisories" in names

        # And nothing from outside the beat's subject.
        assert "Associated Press" not in names
        assert "Krebs on Security" not in names
        assert "ARLnow - Arlington Local News" not in names

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
