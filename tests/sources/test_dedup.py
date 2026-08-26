"""
The dedup proof.

Backlog task 005 acceptance: "re-running an adapter over unchanged upstream
content inserts zero new articles (prove the dedup, do not assume it)". These
tests run the real adapter against a recorded API response twice, through the
real store path, into a real (throwaway) SQLite database, and count rows.
"""

from datetime import datetime

from src.database.models import Article, RSSFeed
from src.sources.federal_register import FederalRegisterAdapter
from src.sources.runner import run_adapter

from .conftest import json_responder, make_client

SINCE = datetime(2026, 8, 17)


def adapter_for(filter_, handler):
    return FederalRegisterAdapter(
        source_filter=filter_, client=make_client(handler), requests_per_second=0
    )


def article_count(db_factory) -> int:
    with db_factory() as db:
        return db.query(Article).count()


class TestReRunInsertsNothing:
    async def test_second_run_over_unchanged_content_inserts_zero(
        self, db_factory, single_query_filter, fr_week_payload
    ):
        adapter = adapter_for(single_query_filter, json_responder(fr_week_payload))

        first = await run_adapter(adapter, SINCE, db_factory=db_factory)
        assert first.fetched == 6
        assert first.inserted == 6
        assert article_count(db_factory) == 6

        second = await run_adapter(adapter, SINCE, db_factory=db_factory)

        assert second.fetched == 6
        assert second.inserted == 0
        assert second.duplicates == 6
        assert second.error is None
        assert article_count(db_factory) == 6

    async def test_a_third_run_is_still_zero(
        self, db_factory, single_query_filter, fr_week_payload
    ):
        adapter = adapter_for(single_query_filter, json_responder(fr_week_payload))

        for _ in range(3):
            await run_adapter(adapter, SINCE, db_factory=db_factory)

        assert article_count(db_factory) == 6

    async def test_the_same_document_at_a_new_url_is_not_a_new_article(
        self, db_factory, single_query_filter, fr_week_payload
    ):
        """The landmine: Federal Register serves one document at several URLs."""
        await run_adapter(
            adapter_for(single_query_filter, json_responder(fr_week_payload)),
            SINCE,
            db_factory=db_factory,
        )

        moved = {
            **fr_week_payload,
            "results": [
                {**doc, "html_url": doc["html_url"].replace("/documents/", "/d/")}
                for doc in fr_week_payload["results"]
            ],
        }
        second = await run_adapter(
            adapter_for(single_query_filter, json_responder(moved)),
            SINCE,
            db_factory=db_factory,
        )

        assert second.inserted == 0
        assert article_count(db_factory) == 6

    async def test_genuinely_new_content_does_insert(
        self, db_factory, single_query_filter, fr_week_payload
    ):
        """The dedup must not be a blanket refusal to insert."""
        await run_adapter(
            adapter_for(single_query_filter, json_responder(fr_week_payload)),
            SINCE,
            db_factory=db_factory,
        )

        extended = {
            **fr_week_payload,
            "results": [
                *fr_week_payload["results"],
                {
                    "document_number": "2026-99999",
                    "title": "Controlled Unclassified Information; Proposed Rule",
                    "abstract": "A new document that was not in the first response.",
                    "type": "Proposed Rule",
                    "agencies": [{"name": "National Archives and Records Administration"}],
                    "publication_date": "2026-08-21",
                    "html_url": "https://www.federalregister.gov/documents/2026/08/21/2026-99999/x",
                    "topics": [],
                    "docket_ids": [],
                    "citation": "91 FR 99999",
                },
            ],
        }
        second = await run_adapter(
            adapter_for(single_query_filter, json_responder(extended)),
            SINCE,
            db_factory=db_factory,
        )

        assert second.inserted == 1
        assert second.duplicates == 6
        assert article_count(db_factory) == 7

    async def test_two_queries_returning_the_same_document_insert_it_once(
        self, db_factory, fr_week_payload
    ):
        from src.sources.federal_register import FederalRegisterFilter, FederalRegisterQuery

        overlapping = FederalRegisterFilter(
            queries=(
                FederalRegisterQuery(name="a", term="x"),
                FederalRegisterQuery(name="b", term="y"),
            )
        )
        result = await run_adapter(
            adapter_for(overlapping, json_responder(fr_week_payload)),
            SINCE,
            db_factory=db_factory,
        )

        assert result.fetched == 6
        assert result.inserted == 6
        assert article_count(db_factory) == 6


class TestStoredRowShape:
    async def test_rows_land_under_one_source_with_the_adapters_identity(
        self, db_factory, single_query_filter, fr_week_payload
    ):
        adapter = adapter_for(single_query_filter, json_responder(fr_week_payload))

        await run_adapter(adapter, SINCE, db_factory=db_factory)

        with db_factory() as db:
            sources = db.query(RSSFeed).all()
            assert len(sources) == 1
            assert sources[0].name == "Federal Register - Documents API"
            assert sources[0].url == adapter.source_url
            assert sources[0].category == "federal_policy"
            assert sources[0].last_error is None

            article = db.query(Article).filter(Article.title.like("%Defense Federal%")).one()
            assert article.feed_id == sources[0].id
            assert article.language == "en"
            assert article.word_count > 0
            assert article.filtered is False
            assert isinstance(article.categories, list)
