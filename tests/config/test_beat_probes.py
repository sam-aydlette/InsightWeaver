"""
Tests for the ``coverage_probes`` block of a beat file.

A probe is a claim that a match means the beat saw a specific event. The loader
is therefore the first place that claim can be weakened, so what is pinned here
is mostly refusal: a probe is rejected rather than repaired, and in particular a
probe resting on one bare term is rejected outright. A probe that passes on
generic terms manufactures exactly the confidence backlog task 010 exists to
remove.

Every fixture here writes its own beat file. Nothing reads the shipped beat's
probe list, because that list is about live corpus state and would make this
suite fail for reasons unrelated to the loader.
"""

import json
from datetime import date

import pytest

from src.config.beats import (
    DEFAULT_PROBE_WINDOW_DAYS,
    MIN_PROBE_EVIDENCE,
    BeatValidationError,
    load_beat,
)


@pytest.fixture
def beats_dir(tmp_path):
    directory = tmp_path / "beats"
    directory.mkdir()
    return directory


def write(beats_dir, probes, name="probe-beat"):
    payload = {
        "name": name,
        "description": "A beat with probes.",
        "sources": [{"adapter": "rss", "feed_tags": ["regulatory"]}],
        "coverage_probes": probes,
    }
    (beats_dir / f"{name}.json").write_text(json.dumps(payload))
    return name


def load(beats_dir, probes):
    return load_beat(write(beats_dir, probes), beats_dir)


VALID = {
    "date": "2026-08-24",
    "what": "FedRAMP director reinstated",
    "terms": ["FedRAMP"],
    "any_of": [["director", "administrator"], ["reinstat*", "return*", "restored"]],
}


class TestProbesLoad:
    def test_a_beat_may_declare_no_probes_at_all(self, beats_dir):
        assert load_beat(write(beats_dir, []), beats_dir).coverage_probes == ()

    def test_the_block_is_optional(self, beats_dir):
        name = "no-probe-key"
        (beats_dir / f"{name}.json").write_text(
            json.dumps({"name": name, "sources": [{"adapter": "rss", "feed_tags": ["regulatory"]}]})
        )
        assert load_beat(name, beats_dir).coverage_probes == ()

    def test_a_probe_carries_a_date_a_description_and_its_terms(self, beats_dir):
        (probe,) = load(beats_dir, [VALID]).coverage_probes
        assert probe.date == date(2026, 8, 24)
        assert probe.what == "FedRAMP director reinstated"
        assert probe.terms == ("FedRAMP",)
        assert probe.any_of == (
            ("director", "administrator"),
            ("reinstat*", "return*", "restored"),
        )

    def test_the_window_defaults_and_is_symmetric_around_the_event(self, beats_dir):
        (probe,) = load(beats_dir, [VALID]).coverage_probes
        assert probe.window_days == DEFAULT_PROBE_WINDOW_DAYS
        assert probe.window == (date(2026, 8, 10), date(2026, 9, 7))

    def test_the_window_can_be_widened_per_probe(self, beats_dir):
        (probe,) = load(beats_dir, [{**VALID, "window_days": 1}]).coverage_probes
        assert probe.window == (date(2026, 8, 23), date(2026, 8, 25))

    def test_terms_are_deduplicated_but_keep_their_order(self, beats_dir):
        (probe,) = load(
            beats_dir, [{**VALID, "terms": ["FedRAMP", "PMO", "FedRAMP"]}]
        ).coverage_probes
        assert probe.terms == ("FedRAMP", "PMO")

    def test_describe_reads_back_the_requirement_as_written(self, beats_dir):
        (probe,) = load(beats_dir, [VALID]).coverage_probes
        assert probe.describe() == (
            "FedRAMP AND (director OR administrator) AND (reinstat* OR return* OR restored)"
        )


class TestASingleGenericTermIsRefused:
    """
    The load-bearing refusal.

    `FedRAMP` on its own is matched by an AWS region-launch post. A probe that
    would pass on that is worse than no probe, because a green tick from it is
    read as coverage.
    """

    def test_one_term_and_no_groups_is_rejected(self, beats_dir):
        with pytest.raises(BeatValidationError) as exc:
            load(beats_dir, [{"date": "2026-08-24", "what": "x", "terms": ["FedRAMP"]}])
        assert "single term" in str(exc.value)
        assert str(MIN_PROBE_EVIDENCE) in str(exc.value)

    def test_two_required_terms_is_enough(self, beats_dir):
        probes = load(
            beats_dir, [{"date": "2026-08-24", "what": "x", "terms": ["FedRAMP", "PMO"]}]
        ).coverage_probes
        assert probes[0].evidence_count == 2

    def test_one_term_plus_one_group_is_enough(self, beats_dir):
        probes = load(
            beats_dir,
            [
                {
                    "date": "2026-08-24",
                    "what": "x",
                    "terms": ["FedRAMP"],
                    "any_of": [["director"]],
                }
            ],
        ).coverage_probes
        assert probes[0].evidence_count == 2

    def test_a_repeated_term_does_not_count_twice(self, beats_dir):
        """Deduplication happens before the floor is checked, not after."""
        with pytest.raises(BeatValidationError, match="single term"):
            load(
                beats_dir,
                [{"date": "2026-08-24", "what": "x", "terms": ["FedRAMP", "FedRAMP"]}],
            )


class TestRejections:
    def test_unknown_probe_key(self, beats_dir):
        with pytest.raises(BeatValidationError, match="unknown key"):
            load(beats_dir, [{**VALID, "author": "someone"}])

    def test_missing_date(self, beats_dir):
        with pytest.raises(BeatValidationError, match="missing required key"):
            load(beats_dir, [{"what": "x", "terms": ["a", "b"]}])

    def test_unparseable_date_is_refused_not_defaulted(self, beats_dir):
        with pytest.raises(BeatValidationError, match="not a 'YYYY-MM-DD' date"):
            load(beats_dir, [{**VALID, "date": "last August"}])

    def test_empty_description(self, beats_dir):
        with pytest.raises(BeatValidationError, match="non-empty description"):
            load(beats_dir, [{**VALID, "what": "   "}])

    def test_empty_terms(self, beats_dir):
        with pytest.raises(BeatValidationError, match="terms must not be empty"):
            load(beats_dir, [{**VALID, "terms": []}])

    def test_an_empty_any_of_group_is_refused(self, beats_dir):
        """An empty group is satisfied by nothing, so it would silently kill the probe."""
        with pytest.raises(BeatValidationError, match="must not be empty"):
            load(beats_dir, [{**VALID, "any_of": [["director"], []]}])

    def test_a_bare_stem_marker_is_refused(self, beats_dir):
        with pytest.raises(BeatValidationError, match="stem marker with no stem"):
            load(beats_dir, [{**VALID, "terms": ["FedRAMP", "*"]}])

    def test_non_string_term(self, beats_dir):
        with pytest.raises(BeatValidationError, match="only non-empty strings"):
            load(beats_dir, [{**VALID, "terms": ["FedRAMP", 7]}])

    def test_window_days_must_be_a_positive_integer(self, beats_dir):
        with pytest.raises(BeatValidationError, match="positive integer"):
            load(beats_dir, [{**VALID, "window_days": 0}])

    def test_window_days_rejects_a_bool(self, beats_dir):
        with pytest.raises(BeatValidationError, match="positive integer"):
            load(beats_dir, [{**VALID, "window_days": True}])

    def test_probe_list_must_be_a_list(self, beats_dir):
        with pytest.raises(BeatValidationError, match="must be a list"):
            load(beats_dir, {"date": "2026-08-24"})

    def test_probe_must_be_an_object(self, beats_dir):
        with pytest.raises(BeatValidationError, match="must be an object"):
            load(beats_dir, ["FedRAMP director reinstated"])
