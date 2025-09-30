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
    categories = Column(JSON)  # List of categories/tags

    # Normalized fields
    normalized_content = Column(Text)  # Clean text without HTML
    word_count = Column(Integer)
    language = Column(String(10))

    # Metadata
    fetched_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Content filtering
    filtered = Column(Boolean, default=False)  # True if filtered out by content preferences
    filter_reason = Column(String(200))  # Why it was filtered (e.g., "sports", "clickbait")

    # Analysis results (to be populated by agents)
    priority_score = Column(Float)
    priority_metadata = Column(JSON)
    trend_metadata = Column(JSON)
    entities = Column(JSON)  # Extracted entities

    feed = relationship("RSSFeed", back_populates="articles")

    __table_args__ = (
        UniqueConstraint('feed_id', 'guid', name='_feed_guid_uc'),
        Index('idx_published_date', 'published_date'),
        Index('idx_fetched_at', 'fetched_at'),
    )

class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True)
    run_type = Column(String(50))  # 'prioritization', 'trend', 'prediction'
    status = Column(String(50))  # 'started', 'completed', 'failed'
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    articles_processed = Column(Integer)
    error_message = Column(Text)
    analysis_metadata = Column(JSON)  # Store analysis-specific data

class TrendAnalysis(Base):
    __tablename__ = "trend_analyses"

    id = Column(Integer, primary_key=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id"))
    trend_name = Column(String(200))
    trend_type = Column(String(50))  # 'topic', 'entity', 'sentiment'
    confidence = Column(Float)
    timeframe_start = Column(DateTime)
    timeframe_end = Column(DateTime)
    data_points = Column(JSON)  # Trend data over time
    related_articles = Column(JSON)  # List of article IDs
    created_at = Column(DateTime, default=datetime.utcnow)

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id"))
    prediction_text = Column(Text)
    confidence = Column(Float)
    category = Column(String(100))
    timeframe = Column(String(50))  # e.g., "2-4 weeks"
    supporting_evidence = Column(JSON)  # References to trends and articles
    created_at = Column(DateTime, default=datetime.utcnow)

class NarrativeSynthesis(Base):
    __tablename__ = "narrative_syntheses"

    id = Column(Integer, primary_key=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id"))
    user_profile_version = Column(String(50))  # Track which profile version was used
    synthesis_data = Column(JSON)  # Full structured narrative output
    executive_summary = Column(Text)  # Extracted for quick display
    articles_analyzed = Column(Integer)
    trends_analyzed = Column(Integer)
    temporal_scope = Column(String(100))  # "immediate,near,medium,long"
    generated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_narrative_generated_at', 'generated_at'),
    )