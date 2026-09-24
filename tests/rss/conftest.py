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
