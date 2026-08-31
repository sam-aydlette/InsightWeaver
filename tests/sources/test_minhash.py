"""
Near-duplicate detection, checked against four real articles from the corpus.

The four items in ``fixtures/near_duplicates.json`` were pulled from the
operator's 55,249-row database on 2026-08-31, not written for this test:

* ``near_duplicate_a`` / ``near_duplicate_b`` -- the same press release about a
  county clerk's Valentine's Day event, carried by two different feeds (Prince
  William Living and What's Up Prince William). The bodies are identical; they
  differ in the leading photo credit and in the "appeared first on <publisher>"
  footer. Exactly the case content-addressing cannot catch, because the bytes
  genuinely differ.
* ``distinct_a`` / ``distinct_b`` -- two articles from the *same* publisher.
  ``distinct_a`` is deliberately the hard case: it is about the same county
  clerk, the same kind of civil wedding event, carries the same publisher
  boilerplate, and even mentions the Valentine's Day Bash by name. If a
  threshold is going to over-group anything, it will over-group this.

Fabricated near-duplicates would have proved the algorithm runs. These prove it
separates the two cases on text nobody wrote to be separable.
"""

import json
from pathlib import Path

import pytest

from src.config.settings import settings
from src.sources.minhash import (
    PERMUTATIONS,
    group_near_duplicates,
    shingles,
    signature,
    similarity,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def corpus() -> dict:
    return json.loads((FIXTURES / "near_duplicates.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def signatures(corpus) -> dict:
    return {
        key: signature(f"{item['title']} {item['normalized_content']}")
        for key, item in corpus.items()
    }


class TestRealNearDuplicates:
    def test_the_two_near_duplicates_score_far_above_the_threshold(self, signatures):
        score = similarity(signatures["near_duplicate_a"], signatures["near_duplicate_b"])
        assert score > settings.near_duplicate_threshold
        # Measured 0.891 on 2026-08-31. Asserted loosely so that a change to the
        # shingle size shows up as a failure here rather than as a silent drift.
        assert score == pytest.approx(0.89, abs=0.05)

    def test_the_two_distinct_items_score_far_below_the_threshold(self, signatures):
        score = similarity(signatures["distinct_a"], signatures["distinct_b"])
        assert score < settings.near_duplicate_threshold
        assert score == pytest.approx(0.0, abs=0.05)

    def test_the_hardest_distinct_pair_still_does_not_group(self, signatures):
        """Same publisher, same subject, same boilerplate, different article."""
        score = similarity(signatures["near_duplicate_a"], signatures["distinct_a"])
        assert score < settings.near_duplicate_threshold

    def test_grouping_puts_the_pair_together_and_leaves_the_others_alone(self, signatures):
        groups = group_near_duplicates(signatures, settings.near_duplicate_threshold)
        assert groups == [
            ["distinct_a"],
            ["distinct_b"],
            ["near_duplicate_a", "near_duplicate_b"],
        ]

    def test_the_configured_threshold_sits_in_the_gap(self, signatures):
        """
        The threshold is only meaningful if there is room on both sides of it.

        Measured: the near-duplicate pair is 0.89, the closest distinct pair is
        0.016. Any threshold in that gap gives the same grouping, which is what
        makes 0.7 a choice rather than a fitted constant.
        """
        near = similarity(signatures["near_duplicate_a"], signatures["near_duplicate_b"])
        worst_distinct = max(
            similarity(signatures[a], signatures[b])
            for a, b in (
                ("near_duplicate_a", "distinct_a"),
                ("near_duplicate_a", "distinct_b"),
                ("near_duplicate_b", "distinct_a"),
                ("near_duplicate_b", "distinct_b"),
                ("distinct_a", "distinct_b"),
            )
        )
        assert worst_distinct < settings.near_duplicate_threshold < near
        assert near - worst_distinct > 0.5


class TestSignatureProperties:
    def test_a_signature_is_the_declared_width(self, signatures):
        assert all(len(sig) == PERMUTATIONS for sig in signatures.values())

    def test_the_same_text_always_signs_the_same(self, corpus):
        text = corpus["distinct_b"]["normalized_content"]
        assert signature(text) == signature(text)

    def test_a_document_is_identical_to_itself(self, signatures):
        assert similarity(signatures["distinct_a"], signatures["distinct_a"]) == 1.0

    def test_empty_text_has_an_empty_signature_and_matches_nothing(self, signatures):
        assert signature("") == ()
        assert signature("   ") == ()
        assert similarity((), ()) == 0.0
        assert similarity((), signatures["distinct_a"]) == 0.0

    def test_short_text_still_produces_one_shingle(self):
        assert len(shingles("three short words")) == 1
        assert len(signature("three short words")) == PERMUTATIONS

    def test_comparing_signatures_of_different_widths_raises(self):
        with pytest.raises(ValueError, match="different PERMUTATIONS"):
            similarity((1, 2, 3), (1, 2, 3, 4))


class TestGrouping:
    def test_singletons_are_returned_too(self):
        sigs = {"a": signature("wholly unrelated text about persimmons and frost dates")}
        assert group_near_duplicates(sigs, 0.7) == [["a"]]

    def test_the_output_order_does_not_depend_on_input_order(self, signatures):
        forward = group_near_duplicates(signatures, 0.7)
        reversed_input = dict(reversed(list(signatures.items())))
        assert group_near_duplicates(reversed_input, 0.7) == forward

    def test_grouping_is_transitive(self):
        base = "the agency finalized the continuous monitoring rule this morning " * 10
        sigs = {
            "a": signature(base),
            "b": signature(base + " Filed by the desk."),
            "c": signature("Filed by the desk. " + base),
        }
        assert group_near_duplicates(sigs, 0.7) == [["a", "b", "c"]]

    def test_an_out_of_range_threshold_is_refused(self, signatures):
        with pytest.raises(ValueError, match="must be in"):
            group_near_duplicates(signatures, 1.5)

    def test_an_empty_corpus_groups_to_nothing(self):
        assert group_near_duplicates({}, 0.7) == []


class TestConfiguredThreshold:
    def test_the_threshold_is_configuration_not_a_literal(self):
        assert 0.0 < settings.near_duplicate_threshold < 1.0
        assert settings.near_duplicate_threshold == 0.7

    def test_the_threshold_is_overridable_by_environment(self, monkeypatch):
        from src.config.settings import Settings

        monkeypatch.setenv("NEAR_DUPLICATE_THRESHOLD", "0.95")
        assert Settings().near_duplicate_threshold == 0.95

    def test_a_stricter_threshold_splits_the_near_duplicate_pair(self, signatures):
        assert group_near_duplicates(signatures, 0.95) == [
            ["distinct_a"],
            ["distinct_b"],
            ["near_duplicate_a"],
            ["near_duplicate_b"],
        ]
