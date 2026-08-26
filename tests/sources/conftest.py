"""
Fixtures for the source adapter tests.

Every test here is offline. The Federal Register payloads are recorded
responses from the real API (2026-08-26, publication week 2026-08-17 to
2026-08-21) so that a test failure means our code changed, not that the
Federal Register had a quiet morning.
"""

import json
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import sessionmaker

from src.sources.federal_register import FederalRegisterFilter, FederalRegisterQuery

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_rss_response() -> bytes:
    """A two-item RSS feed. Kept local rather than shared with tests/rss/, so
    that changing an RSS-fetcher test cannot silently change an adapter test."""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <link>https://example.com</link>
            <item>
                <title>Test Article 1</title>
                <link>https://example.com/article1</link>
                <description>Description of article 1</description>
                <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                <guid>article-1</guid>
            </item>
            <item>
                <title>Test Article 2</title>
                <link>https://example.com/article2</link>
                <description>Description of article 2</description>
                <pubDate>Mon, 01 Jan 2024 13:00:00 GMT</pubDate>
                <guid>article-2</guid>
            </item>
        </channel>
    </rss>
    """


@pytest.fixture
def sample_rss_response_html() -> bytes:
    """An RSS feed whose content carries HTML markup."""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <item>
                <title>Article with HTML</title>
                <link>https://example.com/html-article</link>
                <description><![CDATA[<p>This is <strong>HTML</strong> content</p>]]></description>
                <content:encoded><![CDATA[<div><h1>Full Content</h1><p>More HTML here</p></div>]]></content:encoded>
                <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                <guid>html-article</guid>
            </item>
        </channel>
    </rss>
    """


@pytest.fixture
def empty_rss_response() -> bytes:
    """A well-formed feed with no items -- reachable, but nothing to report."""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Empty Feed</title>
            <link>https://example.com</link>
        </channel>
    </rss>
    """


@pytest.fixture
def fr_week_payload() -> dict:
    """A recorded documents.json response: six real documents, one page."""
    with open(FIXTURES / "federal_register_week.json", encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture
def fr_empty_payload() -> dict:
    """What the API actually returns for a query that matched nothing.

    Note the absent "results" key -- recorded from the live API on 2026-08-26.
    Any code that assumes results is always present would break on a quiet day.
    """
    return {"description": "Documents matching 'zzzqqq'", "count": 0}


@pytest.fixture
def single_query_filter() -> FederalRegisterFilter:
    """One query, so a test's request count is predictable."""
    return FederalRegisterFilter(
        queries=(
            FederalRegisterQuery(name="test-query", agencies=("general-services-administration",)),
        ),
        per_page=100,
        max_pages=3,
    )


def make_client(handler) -> httpx.AsyncClient:
    """An httpx client whose transport is a plain function of the request."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def json_responder(*payloads, status: int = 200):
    """A handler returning each payload in turn, recording the requests seen."""
    seen: list[httpx.Request] = []
    remaining = list(payloads)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        payload = remaining.pop(0) if len(remaining) > 1 else remaining[0]
        return httpx.Response(status, json=payload)

    handler.seen = seen  # type: ignore[attr-defined]
    return handler


@pytest.fixture
def db_factory(test_engine):
    """A ``get_db``-shaped factory bound to the throwaway per-test SQLite file.

    Mirrors tests/context/test_synthesizer.py::isolated_db. Nothing in these
    tests may touch whatever DATABASE_URL names -- in a developer shell that is
    the real database.
    """
    Session = sessionmaker(bind=test_engine)

    @contextmanager
    def _get_db():
        db = Session()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    return _get_db
