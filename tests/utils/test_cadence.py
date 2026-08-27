"""
Tests for review-cadence parsing (backlog task 011).

A cadence is not a deadline: it says how often a question is worth
re-examining. These tests pin the interval arithmetic that `forecast --due`
depends on to surface two questions on different cadences independently.
"""

from datetime import datetime, timedelta

import pytest

from src.utils.cadence import (
    InvalidCadence,
    describe_next_review,
    is_due,
    next_review_at,
    normalize_cadence,
    parse_cadence,
)

NOW = datetime(2026, 8, 27, 12, 0, 0)


class TestParse:
    @pytest.mark.parametrize(
        ("raw", "days"),
        [("7d", 7), ("30d", 30), ("90d", 90), ("2w", 14), ("3m", 90), ("1y", 365)],
    )
    def test_reads_the_forms_the_help_text_advertises(self, raw, days):
        assert parse_cadence(raw) == timedelta(days=days)

    @pytest.mark.parametrize("raw", [" 7d ", "7D", "1Y"])
    def test_tolerates_case_and_whitespace(self, raw):
        assert parse_cadence(raw) > timedelta(0)

    @pytest.mark.parametrize("raw", ["", None, "soon", "d", "7", "7x", "-3d", "0d", "1.5y"])
    def test_refuses_anything_it_cannot_read(self, raw):
        with pytest.raises(InvalidCadence):
            parse_cadence(raw)

    def test_normalizes_to_a_canonical_spelling(self):
        assert normalize_cadence(" 90D ") == "90d"


class TestNextReview:
    def test_counts_from_first_asked_when_never_reviewed(self):
        first_asked = NOW - timedelta(days=3)
        assert next_review_at("7d", None, first_asked) == first_asked + timedelta(days=7)

    def test_counts_from_the_last_review_once_reviewed(self):
        first_asked = NOW - timedelta(days=300)
        reviewed = NOW - timedelta(days=2)
        assert next_review_at("7d", reviewed, first_asked) == reviewed + timedelta(days=7)

    def test_no_cadence_means_no_next_review(self):
        assert next_review_at(None, None, NOW) is None


class TestIsDue:
    def test_not_due_before_the_interval_elapses(self):
        assert not is_due("90d", None, NOW - timedelta(days=10), NOW)

    def test_due_once_the_interval_elapses(self):
        assert is_due("7d", None, NOW - timedelta(days=10), NOW)

    def test_two_cadences_are_independent_at_the_same_instant(self):
        first_asked = NOW - timedelta(days=10)
        assert is_due("7d", None, first_asked, NOW)
        assert not is_due("90d", None, first_asked, NOW)

    def test_a_question_with_no_cadence_is_never_due(self):
        assert not is_due(None, None, NOW - timedelta(days=4000), NOW)


class TestDescribe:
    def test_says_how_long_until_the_next_review(self):
        assert describe_next_review("90d", None, NOW - timedelta(days=10), NOW) == (
            "next review in 80d"
        )

    def test_says_how_overdue_it_is(self):
        assert describe_next_review("7d", None, NOW - timedelta(days=10), NOW) == (
            "due now (3d overdue)"
        )

    def test_says_no_cadence_rather_than_inventing_one(self):
        assert describe_next_review(None, None, NOW, NOW) == "no cadence"
