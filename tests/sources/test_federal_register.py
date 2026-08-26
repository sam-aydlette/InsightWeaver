"""
The Federal Register documents API adapter.

Payloads are recorded responses from the real API (see conftest); no test here
opens a socket.
"""

import json
from datetime import datetime

import httpx
import pytest

from src.sources.base import SourceUnavailable
from src.sources.federal_register import (
    DOCUMENTS_ENDPOINT,
    USER_AGENT,
    FederalRegisterAdapter,
    FederalRegisterConfigError,
    FederalRegisterFilter,
    FederalRegisterQuery,
    load_federal_register_filter,
)

from .conftest import json_responder, make_client

SINCE = datetime(2026, 8, 17)


def build(filter_, handler) -> FederalRegisterAdapter:
    return FederalRegisterAdapter(
        source_filter=filter_, client=make_client(handler), requests_per_second=0
    )


class TestShippedConfig:
    """The filter that actually ships must load and must constrain something."""

    def test_loads(self):
        loaded = load_federal_register_filter()

        assert loaded.queries
        assert all(query.agencies or query.term for query in loaded.queries)

    def test_query_names_are_unique(self):
        names = [query.name for query in load_federal_register_filter().queries]

        assert len(names) == len(set(names))


class TestConfigValidation:
    def _write(self, tmp_path, payload):
        path = tmp_path / "federal_register.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_missing_file(self, tmp_path):
        with pytest.raises(FederalRegisterConfigError, match="No Federal Register filter config"):
            load_federal_register_filter(tmp_path / "nope.json")

    def test_not_json(self, tmp_path):
        path = tmp_path / "federal_register.json"
        path.write_text("{not json", encoding="utf-8")

        with pytest.raises(FederalRegisterConfigError, match="not valid JSON"):
            load_federal_register_filter(path)

    def test_empty_queries_is_rejected(self, tmp_path):
        """A filter that selects nothing would fetch nothing, silently."""
        path = self._write(tmp_path, {"queries": []})

        with pytest.raises(FederalRegisterConfigError, match="non-empty list"):
            load_federal_register_filter(path)

    def test_a_query_that_constrains_nothing_is_rejected(self, tmp_path):
        path = self._write(tmp_path, {"queries": [{"name": "everything"}]})

        with pytest.raises(FederalRegisterConfigError, match="constrains nothing"):
            load_federal_register_filter(path)

    def test_duplicate_query_names_rejected(self, tmp_path):
        path = self._write(
            tmp_path, {"queries": [{"name": "a", "term": "x"}, {"name": "a", "term": "y"}]}
        )

        with pytest.raises(FederalRegisterConfigError, match="is used twice"):
            load_federal_register_filter(path)

    def test_unknown_query_key_rejected(self, tmp_path):
        path = self._write(tmp_path, {"queries": [{"name": "a", "term": "x", "agency": "typo"}]})

        with pytest.raises(FederalRegisterConfigError, match="unknown key"):
            load_federal_register_filter(path)

    def test_non_string_agency_rejected(self, tmp_path):
        path = self._write(tmp_path, {"queries": [{"name": "a", "agencies": [7]}]})

        with pytest.raises(FederalRegisterConfigError, match="non-empty strings"):
            load_federal_register_filter(path)

    def test_bad_per_page_rejected(self, tmp_path):
        path = self._write(tmp_path, {"queries": [{"name": "a", "term": "x"}], "per_page": 0})

        with pytest.raises(FederalRegisterConfigError, match="positive integer"):
            load_federal_register_filter(path)

    def test_per_page_over_api_maximum_rejected(self, tmp_path):
        path = self._write(tmp_path, {"queries": [{"name": "a", "term": "x"}], "per_page": 5000})

        with pytest.raises(FederalRegisterConfigError, match="1000 or fewer"):
            load_federal_register_filter(path)

    def test_rationale_is_an_accepted_key(self, tmp_path):
        path = self._write(
            tmp_path, {"queries": [{"name": "a", "term": "x", "rationale": "because"}]}
        )

        assert load_federal_register_filter(path).queries[0].name == "a"


class TestRequestConstruction:
    async def test_sends_the_configured_conditions_and_an_honest_user_agent(
        self, single_query_filter, fr_week_payload
    ):
        handler = json_responder(fr_week_payload)

        await build(single_query_filter, handler).fetch(SINCE)

        request = handler.seen[0]
        params = request.url.params
        assert str(request.url).startswith(DOCUMENTS_ENDPOINT)
        assert params["conditions[publication_date][gte]"] == "2026-08-17"
        assert params["conditions[agencies][]"] == "general-services-administration"
        assert request.headers["User-Agent"] == USER_AGENT

    async def test_term_and_type_conditions_are_sent(self, fr_week_payload):
        filter_ = FederalRegisterFilter(
            queries=(FederalRegisterQuery(name="q", term="FedRAMP", types=("RULE",)),)
        )
        handler = json_responder(fr_week_payload)

        await build(filter_, handler).fetch(SINCE)

        params = handler.seen[0].url.params
        assert params["conditions[term]"] == "FedRAMP"
        assert params["conditions[type][]"] == "RULE"

    async def test_one_request_per_query(self, fr_week_payload):
        filter_ = FederalRegisterFilter(
            queries=(
                FederalRegisterQuery(name="a", term="x"),
                FederalRegisterQuery(name="b", term="y"),
            )
        )
        handler = json_responder(fr_week_payload)

        await build(filter_, handler).fetch(SINCE)

        assert len(handler.seen) == 2


class TestNormalization:
    async def test_recorded_week_normalizes_into_article_rows(
        self, single_query_filter, fr_week_payload
    ):
        items = await build(single_query_filter, json_responder(fr_week_payload)).fetch(SINCE)

        assert len(items) == 6
        titles = {item.title for item in items}
        assert "Privacy Act of 1974; Re-Established Matching Program" in titles

        dfars = next(item for item in items if "Defense Federal Acquisition" in item.title)
        assert dfars.url.startswith("https://www.federalregister.gov/documents/")
        assert dfars.author  # agency names
        assert dfars.published_date == datetime(2026, 8, 17)
        assert dfars.language == "en"
        assert dfars.as_article_fields()["word_count"] > 0

    async def test_normalized_content_carries_the_structured_fields(
        self, single_query_filter, fr_week_payload
    ):
        items = await build(single_query_filter, json_responder(fr_week_payload)).fetch(SINCE)
        text = next(item for item in items if "Defense Federal Acquisition" in item.title)

        assert "Document type:" in text.normalized_content
        assert "Agencies:" in text.normalized_content
        assert "Federal Register citation:" in text.normalized_content

    async def test_categories_carry_topics_and_document_type(self, single_query_filter):
        payload = {
            "count": 1,
            "results": [
                {
                    "document_number": "2026-1",
                    "title": "A Rule",
                    "type": "Rule",
                    "topics": ["Privacy", "Reporting and recordkeeping requirements"],
                    "publication_date": "2026-08-20",
                    "html_url": "https://example.gov/a",
                }
            ],
        }

        items = await build(single_query_filter, json_responder(payload)).fetch(SINCE)

        assert items[0].categories == (
            "Privacy",
            "Reporting and recordkeeping requirements",
            "Rule",
        )

    async def test_a_document_with_no_title_is_dropped(self, single_query_filter):
        payload = {"count": 1, "results": [{"document_number": "2026-1", "title": ""}]}

        assert await build(single_query_filter, json_responder(payload)).fetch(SINCE) == []

    async def test_unparseable_publication_date_becomes_none_not_a_guess(self, single_query_filter):
        payload = {
            "count": 1,
            "results": [{"title": "T", "publication_date": "last Tuesday", "type": "Rule"}],
        }

        items = await build(single_query_filter, json_responder(payload)).fetch(SINCE)

        assert items[0].published_date is None


class TestContentIdentity:
    """Dedup must key on content, because one document has several URLs."""

    async def test_same_document_at_two_urls_is_one_item(self, single_query_filter):
        document = {
            "document_number": "2026-1",
            "title": "Controlled Unclassified Information",
            "abstract": "NARA proposes a rule.",
            "type": "Proposed Rule",
            "agencies": [{"name": "National Archives and Records Administration"}],
            "publication_date": "2026-08-20",
        }
        payload = {
            "count": 2,
            "results": [
                {**document, "html_url": "https://www.federalregister.gov/d/2026-1"},
                {**document, "html_url": "https://www.federalregister.gov/documents/2026/08/20/x"},
            ],
        }

        items = await build(single_query_filter, json_responder(payload)).fetch(SINCE)

        assert len(items) == 1

    async def test_identical_boilerplate_titles_from_different_agencies_stay_distinct(
        self, single_query_filter
    ):
        """'Sunshine Act Meetings' recurs verbatim across unrelated agencies."""
        payload = {
            "count": 2,
            "results": [
                {
                    "title": "Sunshine Act Meetings",
                    "type": "Notice",
                    "agencies": [{"name": "Tennessee Valley Authority"}],
                },
                {
                    "title": "Sunshine Act Meetings",
                    "type": "Notice",
                    "agencies": [{"name": "Securities and Exchange Commission"}],
                },
            ],
        }

        items = await build(single_query_filter, json_responder(payload)).fetch(SINCE)

        assert len({item.guid for item in items}) == 2

    async def test_guid_is_not_derived_from_the_url(self, single_query_filter, fr_week_payload):
        items = await build(single_query_filter, json_responder(fr_week_payload)).fetch(SINCE)

        for item in items:
            assert item.guid.startswith("sha256:")
            assert item.url not in item.guid


class TestEmptyVersusUnavailable:
    async def test_a_matchless_query_returns_an_empty_list(
        self, single_query_filter, fr_empty_payload
    ):
        """The live API omits 'results' entirely; that is a quiet day, not an error."""
        items = await build(single_query_filter, json_responder(fr_empty_payload)).fetch(SINCE)

        assert items == []

    async def test_http_error_status_raises(self, single_query_filter):
        handler = json_responder({"status": 400, "message": "bad"}, status=400)

        with pytest.raises(SourceUnavailable, match="HTTP 400"):
            await build(single_query_filter, handler).fetch(SINCE)

    async def test_transport_error_raises(self, single_query_filter):
        def handler(request):
            raise httpx.ConnectError("no route to host")

        with pytest.raises(SourceUnavailable, match="no route to host"):
            await build(single_query_filter, handler).fetch(SINCE)

    async def test_non_json_response_raises(self, single_query_filter):
        def handler(request):
            return httpx.Response(200, text="<html>maintenance</html>")

        with pytest.raises(SourceUnavailable, match="not JSON"):
            await build(single_query_filter, handler).fetch(SINCE)

    async def test_a_nonzero_count_with_no_results_is_a_contract_change(self, single_query_filter):
        """Not 'nothing today' -- the API changed shape and we must not guess."""
        handler = json_responder({"count": 40, "total_pages": 2})

        with pytest.raises(SourceUnavailable, match="contract may have changed"):
            await build(single_query_filter, handler).fetch(SINCE)

    async def test_a_non_list_results_raises(self, single_query_filter):
        handler = json_responder({"count": 1, "results": {"title": "x"}})

        with pytest.raises(SourceUnavailable, match="non-list"):
            await build(single_query_filter, handler).fetch(SINCE)


class TestPagination:
    async def test_follows_next_page_url(self, single_query_filter):
        page_one = {
            "count": 2,
            "results": [{"title": "One", "type": "Rule"}],
            "next_page_url": "https://www.federalregister.gov/api/v1/documents?page=2",
        }
        page_two = {"count": 2, "results": [{"title": "Two", "type": "Rule"}]}
        handler = json_responder(page_one, page_two)

        items = await build(single_query_filter, handler).fetch(SINCE)

        assert {item.title for item in items} == {"One", "Two"}
        assert len(handler.seen) == 2

    async def test_truncation_at_the_page_ceiling_is_logged_loudly(self, caplog):
        endless = {
            "count": 9999,
            "results": [{"title": "One", "type": "Rule"}],
            "next_page_url": "https://www.federalregister.gov/api/v1/documents?page=2",
        }
        filter_ = FederalRegisterFilter(
            queries=(FederalRegisterQuery(name="q", term="x"),), max_pages=2
        )

        with caplog.at_level("WARNING"):
            await build(filter_, json_responder(endless)).fetch(SINCE)

        assert any("TRUNCATED" in record.message for record in caplog.records)


class TestAdapterMetadata:
    def test_source_row_fields(self):
        adapter = FederalRegisterAdapter(
            source_filter=FederalRegisterFilter(queries=(FederalRegisterQuery(name="q", term="x"),))
        )

        assert adapter.name == "Federal Register - Documents API"
        assert adapter.source_url == DOCUMENTS_ENDPOINT
        assert adapter.category == "federal_policy"
