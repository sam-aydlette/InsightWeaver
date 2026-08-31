"""
Database models.

Two tables: the feeds we read and the articles we stored from them.

Everything else was deleted by backlog task 012 along with the briefing product
that owned it -- syntheses, context snapshots, provenance, topic clusters,
narrative frames, questions, predictions, decisions and beats. The tables are
dropped by ``src.database.migrations.drop_briefing_tables``; the models are
removed here so that ``create_tables()`` cannot quietly recreate a concept the
rewrite removed.

``articles`` is deliberately untouched. It holds the corpus (55,249 rows as of
2026-08-31) and what becomes of it is backlog task 014's decision, not this
one's.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from ..utils import utcnow

Base = declarative_base()


class RSSFeed(Base):
    """RSS feed sources - unchanged"""

    __tablename__ = "rss_feeds"

    id = Column(Integer, primary_key=True)
    url = Column(String(500), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    category = Column(String(100))
    is_active = Column(Boolean, default=True)
    last_fetched = Column(DateTime)
    last_error = Column(Text)
    error_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    articles = relationship("Article", back_populates="feed")


class Article(Base):
    """
    Articles from RSS feeds
    Optimized for context engineering - stores raw content and minimal metadata
    """

    __tablename__ = "articles"

    id = Column(Integer, primary_key=True)
    feed_id = Column(Integer, ForeignKey("rss_feeds.id"))
    guid = Column(String(500), nullable=False)
    url = Column(String(500))
    title = Column(String(500))
    description = Column(Text)
    content = Column(Text)
    published_date = Column(DateTime)
    author = Column(String(200))
    categories = Column(JSON)  # List of categories/tags from feed

    # Normalized content for context
    normalized_content = Column(Text)  # Clean text without HTML
    word_count = Column(Integer)
    language = Column(String(10))

    # Context engineering fields
    entities = Column(JSON)  # Extracted entities (people, orgs, locations)
    embedding_summary = Column(Text)  # AI-generated 2-3 sentence summary
    relevance_score = Column(Float)  # Simple score: recency + user profile match
    last_included_in_synthesis = Column(DateTime)  # Track usage in context

    # Priority and deduplication fields
    priority_score = Column(Float)  # Used for article filtering/sorting
    priority_metadata = Column(JSON)  # Stores duplicate tracking info
    trend_metadata = Column(JSON)  # Trend-related metadata

    # Content filtering (user preference based)
    filtered = Column(Boolean, default=False)
    filter_reason = Column(String(200))

    # Timestamps
    fetched_at = Column(DateTime, default=utcnow)
    created_at = Column(DateTime, default=utcnow)

    feed = relationship("RSSFeed", back_populates="articles")

    __table_args__ = (
        UniqueConstraint("feed_id", "guid", name="_feed_guid_uc"),
        Index("idx_published_date", "published_date"),
        Index("idx_fetched_at", "fetched_at"),
        Index("idx_relevance_score", "relevance_score"),  # For context selection
        Index("idx_filtered", "filtered"),  # Quick filtering queries
        # Composite indexes for critical query paths
        # Both composite indexes were added for briefing-era query paths that
        # task 012 deleted (curator.py and content_engine.py). They are kept:
        # "recent unfiltered articles" is the shape every tier reads, and
        # dropping an index is a separate, measurable decision.
        Index("idx_articles_filtered_fetched", "filtered", "fetched_at"),
        Index("idx_articles_filtered_published", "filtered", "published_date"),
    )
