"""
Processors-specific test fixtures
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def sample_html_content():
    """Sample HTML content for normalization testing"""
    return """
    <html>
    <head><style>body { color: red; }</style></head>
    <body>
        <header>Site Header</header>
        <nav>Navigation Menu</nav>
        <main>
            <article>
                <h1>Article Title</h1>
                <p>This is the main article content.</p>
                <p>It has multiple paragraphs.</p>
            </article>
        </main>
        <aside>Sidebar Content</aside>
        <footer>Site Footer</footer>
        <script>console.log('test');</script>
    </body>
    </html>
    """


@pytest.fixture
def clean_text_content():
    """Expected clean text after HTML normalization"""
    return "Article Title This is the main article content. It has multiple paragraphs."


_UNSET = object()  # Sentinel for unset values


@pytest.fixture
def sample_article_factory():
    """Factory for creating mock Article objects for testing"""

    def create_article(
        id=1,
        title="Test Article",
        url="https://example.com/article",
        description="Test description",
        content="<p>Test content</p>",
        normalized_content="Test content",
        published_date=_UNSET,
        fetched_at=_UNSET,
        feed_id=1,
        guid="test-guid-1",
        priority_score=0.5,
        priority_metadata=None,
        filtered=False,
        filter_reason=None,
    ):
        article = MagicMock()
        article.id = id
        article.title = title
        article.url = url
        article.description = description
        article.content = content
        article.normalized_content = normalized_content
        # Use default datetime only if not explicitly passed
        article.published_date = (
            datetime.utcnow() if published_date is _UNSET else published_date
        )
        article.fetched_at = datetime.utcnow() if fetched_at is _UNSET else fetched_at
        article.feed_id = feed_id
        article.guid = guid
        article.priority_score = priority_score
        article.priority_metadata = priority_metadata
        article.word_count = len(normalized_content.split()) if normalized_content else 0
        article.language = "en"
        article.filtered = filtered
        article.filter_reason = filter_reason
        return article

    return create_article


@pytest.fixture
def duplicate_article_pair(sample_article_factory):
    """Create a pair of duplicate articles with same content"""
    now = datetime.utcnow()
    original = sample_article_factory(
        id=1,
        title="Breaking News: Major Event",
        url="https://source1.com/news",
        normalized_content="This is the breaking news content about a major event.",
        fetched_at=now - timedelta(hours=1),
    )
    duplicate = sample_article_factory(
        id=2,
        title="Breaking News: Major Event",
        url="https://source2.com/news",
        normalized_content="This is the breaking news content about a major event.",
        fetched_at=now,
    )
    return original, duplicate


@pytest.fixture
def near_duplicate_pair(sample_article_factory):
    """Create a pair of near-duplicate articles with same URL"""
    now = datetime.utcnow()
    original = sample_article_factory(
        id=1,
        title="Original Article Title",
        url="https://example.com/same-url",
        normalized_content="Original content here.",
        fetched_at=now - timedelta(hours=1),
    )
    duplicate = sample_article_factory(
        id=2,
        title="Original Article Title",
        url="https://example.com/same-url",
        normalized_content="Slightly modified content.",
        fetched_at=now,
    )
    return original, duplicate


@pytest.fixture
def sports_article(sample_article_factory):
    """Article with sports content"""
    return sample_article_factory(
        id=10,
        title="NFL Playoff Preview: Quarterback Battle Expected",
        description="The upcoming NFL playoff game features star quarterbacks",
        normalized_content="Football fans eagerly await the NFL playoffs.",
    )


@pytest.fixture
def clickbait_article(sample_article_factory):
    """Article with clickbait title"""
    return sample_article_factory(
        id=11,
        title="You Won't Believe What Happens Next!!!",
        description="Shocking revelation",
        normalized_content="Normal content here.",
    )


@pytest.fixture
def entertainment_article(sample_article_factory):
    """Article with entertainment content"""
    return sample_article_factory(
        id=12,
        title="Celebrity Red Carpet Fashion at the Oscars",
        description="Hollywood stars dazzle at awards ceremony",
        normalized_content="Movie star fashion trends.",
    )


@pytest.fixture
def normal_article(sample_article_factory):
    """Normal news article that should not be filtered"""
    return sample_article_factory(
        id=13,
        title="City Council Approves New Infrastructure Plan",
        description="Local government invests in transportation",
        normalized_content="The city council voted to approve the new infrastructure plan.",
    )


@pytest.fixture
def mock_user_profile():
    """Mock user profile for content filtering"""
    profile = MagicMock()
    profile.get_excluded_topics.return_value = ["crypto", "nft"]
    return profile
