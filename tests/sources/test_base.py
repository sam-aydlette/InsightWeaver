"""
The adapter contract itself.

The load-bearing test here is the shape parity one: if ``RawItem`` and
``RSSFetcher.normalize_article()`` ever disagree about which fields an article
row has, an adapter writes a malformed row and nothing downstream complains.
"""

from datetime import datetime

import pytest

from src.rss.fetcher import RSSFetcher
from src.sources.base import (
    ARTICLE_FIELDS,
    RawItem,
    SourceAdapter,
    SourceUnavailable,
    content_hash,
    normalize_for_hash,
)


class FakeEntry:
    """The attribute duck-type feedparser hands to normalize_article."""

    def __init__(self):
        self.id = "entry-1"
        self.link = "https://example.com/a"
        self.title = "A Title"
        self.summary = "<p>A <b>summary</b></p>"
        self.author = "Someone"
        self.published_parsed = (2026, 8, 20, 12, 0, 0, 0, 0, 0)
        self.tags = []


class TestShapeParity:
    def test_raw_item_fields_match_the_rss_normalizer_exactly(self):
        """The two producers of an articles row must agree on its columns."""
        rss_shape = set(RSSFetcher().normalize_article(FakeEntry(), {}))
        adapter_shape = set(RawItem(guid="g", url="u", title="t").as_article_fields())

        assert rss_shape == adapter_shape == set(ARTICLE_FIELDS)

    def test_article_fields_are_all_real_article_columns(self):
        from src.database.models import Article

        columns = {column.name for column in Article.__table__.columns}

        assert set(ARTICLE_FIELDS) <= columns

    def test_word_count_matches_the_rss_expression(self):
        item = RawItem(guid="g", url="u", title="t", normalized_content="one two three")

        assert item.as_article_fields()["word_count"] == 3

    def test_empty_normalized_content_is_zero_words(self):
        item = RawItem(guid="g", url="u", title="t", normalized_content="")

        assert item.as_article_fields()["word_count"] == 0


class TestFromNormalized:
    def test_round_trips_a_normalized_rss_article(self):
        normalized = RSSFetcher().normalize_article(FakeEntry(), {})

        item = RawItem.from_normalized(normalized)

        assert item.as_article_fields() == normalized

    def test_unknown_field_is_an_error_not_a_silent_drop(self):
        normalized = RSSFetcher().normalize_article(FakeEntry(), {})
        normalized["surprise"] = "value"

        with pytest.raises(ValueError, match="unknown to RawItem"):
            RawItem.from_normalized(normalized)


class TestContentHash:
    def test_same_content_hashes_the_same(self):
        assert content_hash("Title", "Body") == content_hash("Title", "Body")

    def test_hash_ignores_punctuation_case_and_whitespace(self):
        """Matches ArticleDeduplicator._normalize_text, so the two agree."""
        assert content_hash("The  Rule.") == content_hash("the rule")

    def test_different_content_hashes_differently(self):
        assert content_hash("Title", "Body") != content_hash("Title", "Other body")

    def test_field_boundaries_are_not_collapsible(self):
        """Two fields must not be confusable with one longer field."""
        assert content_hash("ab", "c") != content_hash("a", "bc")

    def test_normalize_for_hash_on_empty(self):
        assert normalize_for_hash("") == ""


class TestSourceUnavailable:
    def test_carries_source_and_reason(self):
        exc = SourceUnavailable("Some Source", "HTTP 503")

        assert exc.source == "Some Source"
        assert exc.reason == "HTTP 503"
        assert "Some Source" in str(exc)
        assert "HTTP 503" in str(exc)


class TestProtocol:
    def test_both_shipped_adapters_satisfy_the_protocol(self):
        from src.sources.federal_register import FederalRegisterAdapter, FederalRegisterFilter
        from src.sources.federal_register import FederalRegisterQuery as Q
        from src.sources.rss_adapter import RSSAdapter

        rss = RSSAdapter(name="F", url="https://example.com/feed")
        fr = FederalRegisterAdapter(
            source_filter=FederalRegisterFilter(queries=(Q(name="q", term="x"),))
        )

        assert isinstance(rss, SourceAdapter)
        assert isinstance(fr, SourceAdapter)

    def test_a_type_missing_fetch_is_not_an_adapter(self):
        class NotAnAdapter:
            name = "x"
            source_url = "y"
            category = "z"

        assert not isinstance(NotAnAdapter(), SourceAdapter)


class TestRawItemDefaults:
    def test_published_date_may_be_absent(self):
        fields = RawItem(guid="g", url="u", title="t").as_article_fields()

        assert fields["published_date"] is None
        assert fields["language"] == "en"
        assert fields["categories"] == []

    def test_categories_become_a_list_for_the_json_column(self):
        item = RawItem(guid="g", url="u", title="t", categories=("a", "b"))

        assert item.as_article_fields()["categories"] == ["a", "b"]

    def test_published_date_passes_through(self):
        when = datetime(2026, 8, 20)

        assert (
            RawItem(guid="g", url="u", title="t", published_date=when).as_article_fields()[
                "published_date"
            ]
            == when
        )
