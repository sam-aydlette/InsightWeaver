"""
Optimized Database Models for Context Engineering
Simplified schema focusing on context curation and synthesis outputs
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, Integer, String, Text, DateTime,
    Float, JSON, Boolean, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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

    # Legacy fields (kept for backward compatibility)
    priority_score = Column(Float)  # Legacy priority scoring
    priority_metadata = Column(JSON)  # Legacy priority metadata
    trend_metadata = Column(JSON)  # Legacy trend metadata

    # Content filtering (user preference based)
    filtered = Column(Boolean, default=False)
    filter_reason = Column(String(200))

    # Timestamps
    fetched_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    feed = relationship("RSSFeed", back_populates="articles")

    __table_args__ = (
        UniqueConstraint('feed_id', 'guid', name='_feed_guid_uc'),
        Index('idx_published_date', 'published_date'),
        Index('idx_fetched_at', 'fetched_at'),
        Index('idx_relevance_score', 'relevance_score'),  # For context selection
        Index('idx_filtered', 'filtered'),  # Quick filtering queries
    )


class AnalysisRun(Base):
    """
    Execution tracking for synthesis runs
    Simplified for context engineering approach
    """
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True)
    run_type = Column(String(50))  # 'narrative_synthesis'
    status = Column(String(50))  # 'started', 'completed', 'failed'
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    articles_processed = Column(Integer)
    context_token_count = Column(Integer)  # Approximate tokens sent to Claude
    claude_model = Column(String(100))  # Track which model was used
    error_message = Column(Text)

    __table_args__ = (
        Index('idx_run_started_at', 'started_at'),
    )


class NarrativeSynthesis(Base):
    """
    Primary output: Claude-generated narrative intelligence briefs
    Contains all analysis (trends, predictions, insights) in structured JSON
    """
    __tablename__ = "narrative_syntheses"

    id = Column(Integer, primary_key=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id"))
    context_snapshot_id = Column(Integer, ForeignKey("context_snapshots.id"))

    # User context
    user_profile_version = Column(String(50))

    # Synthesis output
    synthesis_data = Column(JSON)  # Full structured output from Claude
    executive_summary = Column(Text)  # Extracted for quick access

    # Metadata
    articles_analyzed = Column(Integer)
    temporal_scope = Column(String(100))  # "immediate,near,medium,long"
    generated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_narrative_generated_at', 'generated_at'),
        Index('idx_narrative_profile_version', 'user_profile_version'),
    )


class ContextSnapshot(Base):
    """
    Stores exact context sent to Claude for each synthesis
    Enables reproducibility and debugging
    """
    __tablename__ = "context_snapshots"

    id = Column(Integer, primary_key=True)
    synthesis_id = Column(Integer)  # Will reference narrative_syntheses after creation

    # Context composition
    article_ids = Column(JSON)  # List of article IDs included
    context_size_tokens = Column(Integer)  # Approximate token count
    user_profile_hash = Column(String(64))  # Hash of user profile used

    # Context metadata
    historical_summaries = Column(Text)  # Memory context included
    instructions = Column(Text)  # Instructions sent to Claude

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_context_created_at', 'created_at'),
    )


# Migration compatibility - keep these for backward compatibility during migration
# Remove after migration is complete
class TrendAnalysis(Base):
    """DEPRECATED: Trends now in NarrativeSynthesis.synthesis_data"""
    __tablename__ = "trend_analyses"

    id = Column(Integer, primary_key=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id"))
    trend_name = Column(String(200))
    trend_type = Column(String(50))
    confidence = Column(Float)
    timeframe_start = Column(DateTime)
    timeframe_end = Column(DateTime)
    data_points = Column(JSON)
    related_articles = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class Prediction(Base):
    """DEPRECATED: Predictions now in NarrativeSynthesis.synthesis_data"""
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id"))
    prediction_text = Column(Text)
    confidence = Column(Float)
    category = Column(String(100))
    timeframe = Column(String(50))
    supporting_evidence = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
