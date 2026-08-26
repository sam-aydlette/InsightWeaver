"""
Optimized Database Models for Context Engineering
Simplified schema focusing on context curation and synthesis outputs
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
    started_at = Column(DateTime, default=utcnow)
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
    generated_at = Column(DateTime, default=utcnow)

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

    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (Index("idx_context_created_at", "created_at"),)


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

    created_at = Column(DateTime, default=utcnow)

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
    created_at = Column(DateTime, default=utcnow)

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
    first_seen = Column(DateTime, default=utcnow)
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
    run_date = Column(DateTime, default=utcnow)

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
    first_detected = Column(DateTime, default=utcnow)
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

    first_asked_at = Column(DateTime, default=utcnow, nullable=False)
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
    observed_at = Column(DateTime, default=utcnow, nullable=False)

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

    made_at = Column(DateTime, default=utcnow, nullable=False)
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
    created_at = Column(DateTime, default=utcnow, nullable=False)
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
    observed_at = Column(DateTime, default=utcnow, nullable=False)

    decision = relationship("Decision", back_populates="evidence")
    factor = relationship("DecisionFactor", back_populates="evidence")

    __table_args__ = (
        Index("idx_decision_evidence_decision", "decision_id"),
        Index("idx_decision_evidence_factor", "factor_id"),
        Index("idx_decision_evidence_synthesis", "synthesis_id"),
    )


# ============================================================================
# Beats
# A beat is a subject with its own sources, as opposed to the person-shaped
# user profile. These two tables are purely additive (added 2026-08-26 for
# backlog task 004): no existing table gained a beat_id column, because a
# run's beat membership is recorded here and the graph's beat scope is derived
# from it. See docs/CONCEPTS.md, "Beats", for the reasoning.
# ============================================================================


BEAT_RUN_STATUS_STARTED = "started"
BEAT_RUN_STATUS_COMPLETED = "completed"
BEAT_RUN_STATUS_FAILED = "failed"


class Beat(Base):
    """
    A subject the user runs briefs for, mirroring config/beats/<name>.json.

    The config file is authoritative for sources; this row exists so runs can
    be attributed to a beat and so the beat's identity survives a config edit.
    """

    __tablename__ = "beats"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, unique=True)
    description = Column(Text)
    config_path = Column(String(500))
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    runs = relationship("BeatRun", back_populates="beat")

    __table_args__ = (Index("idx_beat_name", "name"),)


class BeatRun(Base):
    """
    One brief run attributed to a beat.

    This is the join that scopes the graph: a Question or Prediction belongs to
    a beat when the synthesis it appeared in has a BeatRun row for that beat,
    and belongs to the default (person) scope when its syntheses have none.
    """

    __tablename__ = "beat_runs"

    id = Column(Integer, primary_key=True)
    beat_id = Column(Integer, ForeignKey("beats.id"), nullable=False)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id"), nullable=True)
    synthesis_id = Column(Integer, ForeignKey("narrative_syntheses.id"), nullable=True)

    status = Column(String(20), nullable=False, default=BEAT_RUN_STATUS_COMPLETED)
    started_at = Column(DateTime, default=utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    articles_analyzed = Column(Integer)
    feeds_resolved = Column(Integer)  # How many feeds the beat selected at run time

    beat = relationship("Beat", back_populates="runs")

    __table_args__ = (
        Index("idx_beat_run_beat", "beat_id"),
        Index("idx_beat_run_synthesis", "synthesis_id"),
        Index("idx_beat_run_started_at", "started_at"),
    )


class BeatStandingQuestion(Base):
    """
    A Question a beat *declared* it is watching, rather than one coverage raised.

    Added 2026-08-26 for backlog task 007. This is a beat table, in the same
    sense beat_runs is: the graph tables still carry no beat_id column, and a
    beat's scope is still derived from a join rather than stamped on a row.
    The join is needed because a declared question can exist before -- and
    without ever -- appearing in a synthesis, so beat_runs alone cannot place
    it. Without this row such a question would fall into the default scope and
    collide with the person brief's ledger, which is exactly what the
    derivation rule exists to prevent.

    ``declared_text`` is the config file's wording, kept verbatim so an edit to
    the beat file is visible as a difference rather than silently adopted;
    ``questions.text`` is what the graph shows.
    """

    __tablename__ = "beat_standing_questions"

    id = Column(Integer, primary_key=True)
    beat_id = Column(Integer, ForeignKey("beats.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)

    declared_text = Column(Text, nullable=False)
    normalized_text = Column(Text, nullable=False)
    declared_at = Column(DateTime, default=utcnow, nullable=False)

    question = relationship("Question")

    __table_args__ = (
        Index("idx_bsq_beat", "beat_id"),
        Index("idx_bsq_question", "question_id"),
        UniqueConstraint("beat_id", "normalized_text", name="_beat_standing_question_uc"),
    )


# ============================================================================
# Institutional activity
# What a beat's declared institutions did this run, against what they usually
# do. Added 2026-08-26 for backlog task 006.
#
# The hard boundary, restated in the schema itself: `kind` admits `org`,
# `program` and `document_type` and nothing else. There is no person kind and
# no persons table, so there is no row a per-individual activity ledger could
# be assembled from. A named individual may appear inside a rendered situation
# where the source document names a signatory -- that is an attribute of a
# document and expires with it -- but never as a row here, because a row here
# accumulates across runs into a file on someone. See
# backlog/006-institutional-activity.md and docs/CONCEPTS.md.
# ============================================================================


ENTITY_KIND_ORG = "org"
ENTITY_KIND_PROGRAM = "program"
ENTITY_KIND_DOCUMENT_TYPE = "document_type"

# The closed set. Enforced at the loader (src/config/beats.py rejects a
# `coverage.people` key) and again on the write path in
# src/context/institutional_activity.py, which refuses an unknown kind rather
# than storing it.
ENTITY_KINDS = (ENTITY_KIND_ORG, ENTITY_KIND_PROGRAM, ENTITY_KIND_DOCUMENT_TYPE)


class BeatEntity(Base):
    """
    One institution a beat tracks, mirroring an entry in its `coverage` block.

    The config file stays authoritative for which entities exist and what their
    aliases are; this row exists so mentions have something stable to key off
    across runs and so an entity keeps its history after a config edit.
    """

    __tablename__ = "beat_entities"

    id = Column(Integer, primary_key=True)
    beat_id = Column(Integer, ForeignKey("beats.id"), nullable=False)

    # One of ENTITY_KINDS. Never a person.
    kind = Column(String(20), nullable=False)
    name = Column(String(200), nullable=False)  # canonical form, as configured
    aliases = Column(JSON, default=list)  # other surface forms of the same institution

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    beat = relationship("Beat")
    mentions = relationship("EntityMention", back_populates="entity")

    __table_args__ = (
        Index("idx_beat_entity_beat", "beat_id"),
        UniqueConstraint("beat_id", "kind", "name", name="_beat_entity_uc"),
    )


class EntityMention(Base):
    """
    How many of one run's items mentioned one entity.

    One row per entity per recorded run, **including the zeroes**: a run in
    which an office said nothing is an observation about that office, and
    without the zero row the trailing average would be an average over only
    the days something happened, which always reads as "normal".

    ``item_count`` counts *items*, not occurrences -- an article that names
    CISA nine times is one item. Counting repetitions would let a verbose
    outlet impersonate institutional activity.
    """

    __tablename__ = "entity_mentions"

    id = Column(Integer, primary_key=True)
    entity_id = Column(Integer, ForeignKey("beat_entities.id"), nullable=False)
    beat_run_id = Column(Integer, ForeignKey("beat_runs.id"), nullable=True)
    synthesis_id = Column(Integer, ForeignKey("narrative_syntheses.id"), nullable=True)

    item_count = Column(Integer, nullable=False, default=0)
    items_scanned = Column(Integer)  # denominator: how many items this run looked at
    observed_at = Column(DateTime, default=utcnow, nullable=False)

    entity = relationship("BeatEntity", back_populates="mentions")

    __table_args__ = (
        Index("idx_entity_mention_entity", "entity_id"),
        Index("idx_entity_mention_run", "beat_run_id"),
        Index("idx_entity_mention_observed", "observed_at"),
        UniqueConstraint("entity_id", "beat_run_id", name="_entity_mention_run_uc"),
    )
