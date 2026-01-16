"""
RSS-specific test fixtures
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def sample_rss_response():
    """Sample RSS feed response content"""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <link>https://example.com</link>
            <description>Test RSS Feed</description>
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
def sample_rss_response_html():
    """Sample RSS feed with HTML content"""
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
            </item>
        </channel>
    </rss>
    """


@pytest.fixture
def empty_rss_response():
    """Empty RSS feed response"""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Empty Feed</title>
            <link>https://example.com</link>
        </channel>
    </rss>
    """


@pytest.fixture
def malformed_rss_response():
    """Malformed RSS content"""
    return b"<not valid xml"


@pytest.fixture
def mock_rss_feed():
    """Mock RSSFeed database object"""
    feed = MagicMock()
    feed.id = 1
    feed.name = "Test Feed"
    feed.url = "https://example.com/feed.rss"
    feed.category = "news"
    feed.is_active = True
    feed.last_fetched = None
    feed.last_error = None
    feed.error_count = 0
    return feed


@pytest.fixture
def mock_inactive_feed():
    """Mock inactive RSSFeed"""
    feed = MagicMock()
    feed.id = 2
    feed.name = "Inactive Feed"
    feed.url = "https://example.com/inactive.rss"
    feed.is_active = False
    return feed


@pytest.fixture
def mock_feed_with_errors():
    """Mock RSSFeed with error history"""
    feed = MagicMock()
    feed.id = 3
    feed.name = "Error Feed"
    feed.url = "https://example.com/error.rss"
    feed.is_active = True
    feed.error_count = 9
    feed.last_error = "Previous error"
    return feed


@pytest.fixture
def sample_feedparser_entry():
    """Sample feedparser entry object"""
    entry = MagicMock()
    entry.title = "Test Article"
    entry.link = "https://example.com/article"
    entry.id = "article-guid-123"
    entry.summary = "Article summary text"
    entry.content = [MagicMock(value="<p>Full content</p>")]
    entry.published_parsed = (2024, 1, 15, 12, 0, 0, 0, 15, 0)
    entry.author = "Test Author"
    entry.tags = [MagicMock(term="news"), MagicMock(term="tech")]
    return entry


@pytest.fixture
def sample_feedparser_entry_minimal():
    """Sample feedparser entry with minimal fields"""
    entry = MagicMock(spec=[])
    entry.title = "Minimal Article"
    entry.link = "https://example.com/minimal"
    return entry


@pytest.fixture
def mock_http_response_success(sample_rss_response):
    """Mock successful HTTP response"""
    response = MagicMock()
    response.status_code = 200
    response.content = sample_rss_response
    response.raise_for_status = MagicMock()
    return response


@pytest.fixture
def mock_http_response_error():
    """Mock HTTP error response"""
    import httpx

    response = MagicMock()
    response.status_code = 500
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Internal Server Error",
        request=MagicMock(),
        response=response,
    )
    return response
