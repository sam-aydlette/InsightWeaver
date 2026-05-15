"""
Optimized Database Models for Context Engineering
Simplified schema focusing on context curation and synthesis outputs
"""

from datetime import datetime

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

    # Priority and deduplication fields
    priority_score = Column(Float)  # Used for article filtering/sorting
    priority_metadata = Column(JSON)  # Stores duplicate tracking info
    trend_metadata = Column(JSON)  # Trend-related metadata

    # Content filtering (user preference based)
    filtered = Column(Boolean, default=False)
    filter_reason = Column(String(200))

    # Timestamps
    fetched_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    feed = relationship("RSSFeed", back_populates="articles")

    __table_args__ = (
        UniqueConstraint("feed_id", "guid", name="_feed_guid_uc"),
        Index("idx_published_date", "published_date"),
        Index("idx_fetched_at", "fetched_at"),
        Index("idx_relevance_score", "relevance_score"),  # For context selection
        Index("idx_filtered", "filtered"),  # Quick filtering queries
        # Composite indexes for critical query paths
        Index(
            "idx_articles_filtered_fetched", "filtered", "fetched_at"
        ),  # curator.py synthesis queries
        Index(
            "idx_articles_filtered_published", "filtered", "published_date"
        ),  # content_engine.py queries
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

    __table_args__ = (Index("idx_run_started_at", "started_at"),)


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
        Index("idx_narrative_generated_at", "generated_at"),
        Index("idx_narrative_profile_version", "user_profile_version"),
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

    __table_args__ = (Index("idx_context_created_at", "created_at"),)


class ForecastRun(Base):
    """
    Execution tracking for long-term forecast runs
    Each run can generate multiple horizon forecasts
    """

    __tablename__ = "forecast_runs"

    id = Column(Integer, primary_key=True)
    run_type = Column(String(50))  # 'multi_horizon', 'single_horizon'
    horizons_requested = Column(JSON)  # ['6mo', '1yr', '3yr', '5yr']
    scenario_count = Column(Integer, default=3)

    # Execution tracking
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(50))  # 'running', 'completed', 'failed'

    # Results
    forecasts_generated = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_forecast_run_started", "started_at"),
        Index("idx_forecast_run_status", "status"),
    )


class LongTermForecast(Base):
    """
    Long-term forecasts (6mo - 5yr horizons)
    Separate from NarrativeSynthesis for distinct analysis types
    """

    __tablename__ = "long_term_forecasts"

    id = Column(Integer, primary_key=True)
    forecast_run_id = Column(Integer, ForeignKey("forecast_runs.id"))

    # Horizon metadata
    time_horizon = Column(String(50), nullable=False)  # '6mo', '1yr', '3yr', '5yr'
    horizon_months = Column(Integer)  # 6, 12, 36, 60
    base_date = Column(DateTime, default=datetime.utcnow)
    target_date = Column(DateTime, nullable=False)

    # Forecast data (structured JSON with all 5 analysis types)
    forecast_data = Column(JSON, nullable=False)
    # Structure: {
    #   "trend_extrapolations": [...],
    #   "scenarios": [optimistic/baseline/pessimistic],
    #   "historical_patterns": [...],
    #   "causal_chains": [...],
    #   "event_risks": {known_knowns, known_unknowns, unknown_unknowns}
    # }

    # Source tracking
    data_sources_used = Column(JSON)  # List of source names
    articles_analyzed = Column(Integer)
    historical_months_analyzed = Column(Integer)

    # Confidence metrics (DEPRECATED - not grounded in empirical methodology)
    # overall_confidence = Column(Float)  # REMOVED: No validated confidence methodology
    # confidence_by_type = Column(JSON)  # REMOVED: No validated confidence methodology

    # Token usage tracking
    context_tokens = Column(Integer)
    generation_tokens = Column(Integer)

    generated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_forecast_horizon", "time_horizon"),
        Index("idx_forecast_target_date", "target_date"),
        Index("idx_forecast_generated_at", "generated_at"),
    )


class ForecastScenario(Base):
    """
    Individual scenario branches for a forecast
    Optimistic/baseline/pessimistic or custom scenarios
    """

    __tablename__ = "forecast_scenarios"

    id = Column(Integer, primary_key=True)
    forecast_id = Column(Integer, ForeignKey("long_term_forecasts.id"))

    # Scenario metadata
    scenario_type = Column(String(50))  # 'optimistic', 'baseline', 'pessimistic', 'custom'
    scenario_name = Column(String(200))
    scenario_description = Column(Text)

    # Scenario details
    predictions = Column(JSON)
    key_assumptions = Column(JSON)
    trigger_events = Column(JSON)  # Early signals this scenario is unfolding
    scenario_probability = Column(Float)  # 0.0-1.0 (should sum to 1.0 across scenarios)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_scenario_forecast", "forecast_id"),
        Index("idx_scenario_type", "scenario_type"),
    )


class CausalChain(Base):
    """
    Cause-effect relationships mapped over time
    Tracks how initial causes lead to final outcomes
    """

    __tablename__ = "causal_chains"

    id = Column(Integer, primary_key=True)
    forecast_id = Column(Integer, ForeignKey("long_term_forecasts.id"))

    # Chain structure
    chain_name = Column(String(200))
    initial_cause = Column(Text)
    intermediate_effects = Column(JSON)  # Ordered list of effects
    final_outcome = Column(Text)

    # Temporal metadata
    time_to_unfold_months = Column(Integer)
    confidence = Column(Float)  # 0.0-1.0

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_causal_forecast", "forecast_id"),
        Index("idx_causal_confidence", "confidence"),
    )


class ProvenanceRecord(Base):
    """
    Provenance chain for a synthesis claim
    Shows the reasoning path from sources to conclusions
    """

    __tablename__ = "provenance_records"

    id = Column(Integer, primary_key=True)
    synthesis_id = Column(Integer, ForeignKey("narrative_syntheses.id"), nullable=False)

    # Claim being traced
    claim_text = Column(Text, nullable=False)
    claim_location = Column(String(100))

    # Source attribution
    contributing_sources = Column(JSON, nullable=False)
    confidence_breakdown = Column(JSON)
    alternative_interpretations = Column(JSON, default=list)
    reasoning_chain = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_provenance_synthesis", "synthesis_id"),
        Index("idx_provenance_created", "created_at"),
    )


# ============================================================================
# Narrative Frame Glossary
# Emergent frame discovery from corpus behavior
# ============================================================================


class TopicCluster(Base):
    """
    A cluster of articles about a related topic.
    Frames are discovered and tracked per cluster.
    """

    __tablename__ = "topic_clusters"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    keywords = Column(JSON, nullable=False)  # List of keywords identifying this cluster
    created_at = Column(DateTime, default=datetime.utcnow)

    frames = relationship("NarrativeFrame", back_populates="topic_cluster")
    gaps = relationship("FrameGap", back_populates="topic_cluster")

    __table_args__ = (Index("idx_topic_cluster_name", "name"),)


class NarrativeFrame(Base):
    """
    A distinct way of understanding a topic: what it emphasizes,
    what it de-emphasizes, and what assumption it takes for granted.
    Discovered emergently from the article corpus, validated by the user.
    """

    __tablename__ = "narrative_frames"

    id = Column(Integer, primary_key=True)
    topic_cluster_id = Column(Integer, ForeignKey("topic_clusters.id"), nullable=False)
    label = Column(String(200), nullable=False)
    description = Column(Text)
    assumptions = Column(Text)  # What this frame takes for granted
    first_seen = Column(DateTime, default=datetime.utcnow)
    validated = Column(Boolean, default=False)  # User has reviewed and accepted

    topic_cluster = relationship("TopicCluster", back_populates="frames")
    article_frames = relationship("ArticleFrame", back_populates="frame")

    __table_args__ = (
        Index("idx_narrative_frame_cluster", "topic_cluster_id"),
        Index("idx_narrative_frame_validated", "validated"),
    )


class ArticleFrame(Base):
    """
    Maps an article to a narrative frame with a confidence score.
    Populated during synthesis when known frames exist for a topic.
    """

    __tablename__ = "article_frames"

    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    frame_id = Column(Integer, ForeignKey("narrative_frames.id"), nullable=False)
    confidence = Column(Float, nullable=False)  # 0.0-1.0
    run_date = Column(DateTime, default=datetime.utcnow)

    frame = relationship("NarrativeFrame", back_populates="article_frames")

    __table_args__ = (
        Index("idx_article_frame_article", "article_id"),
        Index("idx_article_frame_frame", "frame_id"),
        Index("idx_article_frame_run_date", "run_date"),
    )


class FrameGap(Base):
    """
    A recurring absence of a known frame from daily coverage.
    Gaps are a feed curation signal: if a frame is consistently absent,
    the user may want to add a source that carries that perspective.
    """

    __tablename__ = "frame_gaps"

    id = Column(Integer, primary_key=True)
    topic_cluster_id = Column(Integer, ForeignKey("topic_clusters.id"), nullable=False)
    frame_label = Column(String(200), nullable=False)  # May reference a NarrativeFrame or be novel
    first_detected = Column(DateTime, default=datetime.utcnow)
    occurrences = Column(Integer, default=1)
    feed_suggestion = Column(Text)  # Suggested feed type to fill this gap

    topic_cluster = relationship("TopicCluster", back_populates="gaps")

    __table_args__ = (
        Index("idx_frame_gap_cluster", "topic_cluster_id"),
        Index("idx_frame_gap_occurrences", "occurrences"),
    )


# ============================================================================
# Question Graph
# Persistent, addressable questions that accumulate across runs.
# A Question is the unit that joins situations, predictions, and decisions
# across time. unresolved_question fields from synthesis output bind here.
# ============================================================================


QUESTION_STATUS_OPEN = "open"
QUESTION_STATUS_RESOLVED = "resolved"
QUESTION_STATUS_SUPERSEDED = "superseded"


class Question(Base):
    """
    A question the coverage is implicitly tracking across runs.

    Identity rule: when a synthesis emits an unresolved_question, the matcher
    either binds it to an existing open Question or creates a new one. Resolved
    questions are never auto-reopened; a fresh appearance gets a new Question
    with previous_question_id pointing at the resolved record.
    """

    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    text = Column(Text, nullable=False)
    normalized_text = Column(Text, nullable=False)

    first_asked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(20), nullable=False, default=QUESTION_STATUS_OPEN)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)

    # When a previously resolved question reappears, the new Question record
    # points back at its predecessor instead of reopening it.
    previous_question_id = Column(Integer, ForeignKey("questions.id"), nullable=True)

    # Primary vs. secondary unresolved_question within its originating situation.
    # Secondary questions are tracked but rendered quieter in the brief.
    is_primary = Column(Boolean, default=True, nullable=False)

    situation_links = relationship("QuestionSituation", back_populates="question")

    __table_args__ = (
        Index("idx_question_status", "status"),
        Index("idx_question_normalized", "normalized_text"),
        Index("idx_question_first_asked", "first_asked_at"),
    )


class QuestionSituation(Base):
    """
    Join row: a Question appeared in a specific situation within a synthesis.

    A Question accumulates QuestionSituation rows over time; the count is the
    question's "run number" when surfaced in the brief.
    """

    __tablename__ = "question_situations"

    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    synthesis_id = Column(Integer, ForeignKey("narrative_syntheses.id"), nullable=False)
    situation_index = Column(Integer, nullable=False)
    observed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    question = relationship("Question", back_populates="situation_links")

    __table_args__ = (
        Index("idx_qs_question", "question_id"),
        Index("idx_qs_synthesis", "synthesis_id"),
        UniqueConstraint(
            "question_id", "synthesis_id", "situation_index", name="_question_situation_uc"
        ),
    )


# ============================================================================
# Predictions Ledger
# Falsifiable observables the synthesis committed to, keyed to Questions.
# A pre-synthesis check pass grades open predictions against fresh coverage,
# which makes the tool's own forward-looking statements auditable over time.
# ============================================================================


PREDICTION_STATUS_OPEN = "open"
PREDICTION_STATUS_TRIGGERED = "triggered"
PREDICTION_STATUS_CONTRADICTED = "contradicted"
PREDICTION_STATUS_EXPIRED = "expired"

# Open predictions older than this are expired by the check pass; coverage
# that far out is unlikely to still bear on the original observable.
PREDICTION_EXPIRY_DAYS = 90


class Prediction(Base):
    """
    A falsifiable observable the synthesis flagged as worth watching.

    Each what_to_watch entry from a situation becomes a Prediction keyed to
    that situation's primary Question. The check pass that runs before each
    synthesis grades open predictions: triggered (the observable appeared),
    contradicted (coverage explicitly went the other way), or expired (aged
    out without resolution).
    """

    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    observable_text = Column(Text, nullable=False)
    trigger_condition = Column(Text, nullable=False)

    made_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    made_in_synthesis_id = Column(Integer, ForeignKey("narrative_syntheses.id"), nullable=False)

    status = Column(String(20), nullable=False, default=PREDICTION_STATUS_OPEN)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)

    question = relationship("Question")

    __table_args__ = (
        Index("idx_prediction_status", "status"),
        Index("idx_prediction_question", "question_id"),
        Index("idx_prediction_made_at", "made_at"),
    )


# ============================================================================
# Decision Journal
# Standing decisions the user is carrying. Each run routes situation evidence
# into the factors the user cares about, turning daily coverage into an
# accumulating record per decision rather than a one-off briefing.
# ============================================================================


DECISION_STATUS_OPEN = "open"
DECISION_STATUS_DECIDED = "decided"
DECISION_STATUS_DEFERRED = "deferred"

# How a piece of evidence moved a factor.
EVIDENCE_DIRECTION_SUPPORTS = "supports"
EVIDENCE_DIRECTION_COMPLICATES = "complicates"
EVIDENCE_DIRECTION_NEUTRAL = "neutral"


class Decision(Base):
    """A standing decision the user is carrying, seeded from the profile."""

    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True)
    name = Column(String(300), nullable=False)
    decision_type = Column(String(50))  # career / housing / education / financial / civic / other
    status = Column(String(20), nullable=False, default=DECISION_STATUS_OPEN)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    decided_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    factors = relationship("DecisionFactor", back_populates="decision")
    evidence = relationship("DecisionEvidence", back_populates="decision")

    __table_args__ = (Index("idx_decision_status", "status"),)


class DecisionFactor(Base):
    """
    A variable the user is tracking for a decision. ``what_would_update_me``
    is the user's stated rule for what evidence would change their read --
    it is what makes routing tractable, since the router matches situations
    against these clauses.
    """

    __tablename__ = "decision_factors"

    id = Column(Integer, primary_key=True)
    decision_id = Column(Integer, ForeignKey("decisions.id"), nullable=False)
    name = Column(String(300), nullable=False)
    what_would_update_me = Column(Text, nullable=True)
    current_state_note = Column(Text, nullable=True)

    decision = relationship("Decision", back_populates="factors")
    evidence = relationship("DecisionEvidence", back_populates="factor")

    __table_args__ = (Index("idx_decision_factor_decision", "decision_id"),)


class DecisionEvidence(Base):
    """
    One run's routing result: a situation contained evidence bearing on a
    decision factor. This is the only place situation-to-decision routing is
    recorded, so the chain from coverage to decision stays inspectable.
    """

    __tablename__ = "decision_evidence"

    id = Column(Integer, primary_key=True)
    decision_id = Column(Integer, ForeignKey("decisions.id"), nullable=False)
    factor_id = Column(Integer, ForeignKey("decision_factors.id"), nullable=False)
    synthesis_id = Column(Integer, ForeignKey("narrative_syntheses.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=True)

    situation_excerpt = Column(Text, nullable=False)
    direction = Column(String(20), nullable=False, default=EVIDENCE_DIRECTION_NEUTRAL)
    epistemic_status = Column(String(30))  # reported_fact/single_source/consensus/speculation
    observed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    decision = relationship("Decision", back_populates="evidence")
    factor = relationship("DecisionFactor", back_populates="evidence")

    __table_args__ = (
        Index("idx_decision_evidence_decision", "decision_id"),
        Index("idx_decision_evidence_factor", "factor_id"),
        Index("idx_decision_evidence_synthesis", "synthesis_id"),
    )
