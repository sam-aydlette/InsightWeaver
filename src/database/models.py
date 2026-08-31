"""
Database models.

Three tables: the feeds we read, the articles we stored from them, and the
watches the operator has pre-registered.

Everything else was deleted by backlog task 012 along with the briefing product
that owned it -- syntheses, context snapshots, provenance, topic clusters,
narrative frames, questions, predictions, decisions and beats. The tables are
dropped by ``src.database.migrations.drop_briefing_tables``; the models are
removed here so that ``create_tables()`` cannot quietly recreate a concept the
rewrite removed.

``watches`` is the first table of the rewrite, added 2026-08-31 by backlog task
013. Its CHECK constraints are not decoration -- see the class docstring.

``observations`` and ``evidence`` are the second and third, added 2026-08-31 by
backlog task 014. ``route_candidates`` is the fourth, added 2026-08-31 by
backlog task 015: it holds Tier 1's output, which is candidacy rather than
evidence.

**The rule for ``articles`` versus ``observations``, decided by task 014 and
written here because this is the file both of them live in.** They coexist, with
one direction of authority and one writer:

* ``articles`` is the *legacy ingestion table*. It holds the 55,249 rows written
  before the rewrite and it stays the row shape the pre-rewrite code reads. It
  is not deleted and not migrated.
* ``observations`` is *authoritative for everything the rewrite builds*. A tier
  added from task 014 onwards reads ``observations`` and never ``articles``.
* Exactly one code path writes an observation:
  ``src.sources.observation.store_observation``, called from
  ``src.sources.store.store_items``, which is the store path every adapter in
  ``src/sources/`` already goes through. Each new article gets an observation in
  the same transaction, and ``observations.article_id`` links the two.
* The 55,249 pre-existing rows have no observation, and neither does anything
  the legacy ``src/rss/fetcher.py`` path writes directly. That is a known,
  bounded gap, not an ambiguity: the content hash is a pure function of columns
  those rows already carry, so a backfill is mechanical and is deliberately left
  to its own task rather than run inside this one.

The one thing that was not acceptable was two corpora with no stated rule. The
rule is: **new tiers read observations; articles is the pre-rewrite archive.**
"""

from sqlalchemy import (
    DDL,
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from ..utils import utcnow

Base = declarative_base()


class ObservationIsImmutable(RuntimeError):
    """
    Raised when anything tries to change a stored observation.

    Not a warning and not a silently-ignored write. An observation is
    content-addressed, so its hash is a claim that the payload beside it is the
    payload that produced the hash. A single successful UPDATE turns every
    replay run afterwards into a comparison against a corpus that no longer
    matches its own identities, and nothing would say so.
    """


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


class Watch(Base):
    """
    One pre-registered claim, the decision it serves, and what would move it.

    Rows arrive from exactly one place: ``src.position.watches.sync_watches``,
    reading the operator's hand-authored file. Nothing else writes here.
    Invariant 6 -- the system never authors its own watches -- is a property of
    the code paths that exist, so no path exists.

    **The constraints are the enforcement, not a formality.** Invariant 2 says
    every Watch must name a decision; the loader rejects a blank ``so_what``,
    and ``ck_watches_so_what_present`` rejects it again at the storage layer, so
    a row written by hand through ``sqlite3`` fails the same way a bad YAML file
    does. The repository's own history is the argument: 25 unfalsifiable
    predictions accumulated in the deleted ledger because a missing field was
    tolerated by every layer that could have refused it.

    ``triggers`` is JSON, and structured JSON specifically -- a list of clauses
    over terms, entities and source allowlists. Tier 1 compiles it into a
    deterministic predicate. The column it replaces, ``predictions.
    trigger_condition``, was free text; 33 rows were written against it and none
    were ever graded, because nothing downstream could evaluate a sentence.
    """

    __tablename__ = "watches"

    # The operator's own id from the file, not a surrogate. It is the name they
    # will type and the name an alert will carry, and a watch that is renamed in
    # the file is a different watch.
    id = Column(String(100), primary_key=True)

    claim = Column(Text, nullable=False)
    belief = Column(Float, nullable=False)

    # so_what, split: the key is what makes invariant 2 machine-checkable, the
    # prose is what makes it readable. `decision_key` references a decision in
    # the Position file, which is not a table -- Position lives in a private
    # repo under git, so this is deliberately not a foreign key.
    decision_key = Column(String(100), nullable=False)
    so_what = Column(Text, nullable=False)

    triggers = Column(JSON, nullable=False)
    expires = Column(Date, nullable=False)
    staleness_alert_days = Column(Integer, nullable=False)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        CheckConstraint("length(trim(so_what)) > 0", name="ck_watches_so_what_present"),
        CheckConstraint("length(trim(decision_key)) > 0", name="ck_watches_decision_present"),
        CheckConstraint("belief >= 0.0 AND belief <= 1.0", name="ck_watches_belief_range"),
        CheckConstraint("staleness_alert_days >= 1", name="ck_watches_staleness_min"),
        Index("idx_watches_decision_key", "decision_key"),
        Index("idx_watches_expires", "expires"),
    )


class Observation(Base):
    """
    One thing a source published, keyed by a hash of what it said.

    **The hash is the identity.** There is no surrogate primary key, because a
    surrogate key would let the same document be stored twice under two ids and
    the duplicate would be invisible. ``content_hash`` is computed by
    ``src.sources.observation.observation_hash`` from the fields in
    ``OBSERVATION_FIELDS`` and nothing else -- specifically not from
    ``observed_at``, not from the source's last-fetch time, and not from
    anything else that changes between two fetches of an unchanged document.
    That exclusion is the whole invariant, so it is tested directly
    (tests/sources/test_observation.py::TestHashIsContentOnly) rather than
    inferred from the field list.

    ``observed_at`` is a column precisely *because* it is not in the hash: when
    we first saw this content is worth keeping and is not part of what the
    content is. It is the one per-fetch value on the row and it lives outside
    the payload.

    ``payload`` is the normalized adapter output, verbatim, exactly the values
    that were hashed. It is never rewritten -- see
    :class:`ObservationIsImmutable` and the BEFORE UPDATE trigger below.

    ``minhash`` is the near-duplicate signature of the item's text, written once
    at insert. It is stored rather than recomputed so that a grouping computed
    now and a grouping computed after a replay are the same grouping. See
    ``src/sources/minhash.py``.

    Added 2026-08-31 for backlog task 014.
    """

    __tablename__ = "observations"

    content_hash = Column(String(80), primary_key=True)

    # Which source published it. The same text from two sources is two
    # observations, on purpose: "who said this" is part of what was observed,
    # and grouping the pair back together is what the MinHash signature is for.
    source_id = Column(Integer, ForeignKey("rss_feeds.id"), nullable=False)

    # The legacy row this observation was written alongside. Nullable because a
    # backfill from the pre-rewrite corpus would set it and a future
    # observations-only source may not have one. See the module docstring's rule.
    article_id = Column(Integer, ForeignKey("articles.id"))

    payload = Column(JSON, nullable=False)
    minhash = Column(JSON, nullable=False)

    # A projection of payload["published_date"], written by the same call that
    # writes the payload, so that "observations in this window" is an indexed
    # query rather than a JSON scan. Immutability is what keeps it honest: it
    # cannot drift from the payload because neither can change.
    published_date = Column(DateTime)

    observed_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("content_hash LIKE 'sha256:%'", name="ck_observations_hash_prefix"),
        Index("idx_observations_source", "source_id"),
        Index("idx_observations_published", "published_date"),
        Index("idx_observations_article", "article_id"),
    )


# Immutability, enforced twice on purpose.
#
# 1. The ORM guard below stops a mutation made through a Session, which is how
#    application code would do it, and raises a named Python exception.
# 2. The trigger stops an UPDATE issued any other way -- a raw
#    `session.execute(text("UPDATE ..."))`, the sqlite3 shell, a future
#    migration written in a hurry. A guarantee that only holds for code that
#    goes through the ORM is a convention, not a guarantee.
#
# The trigger is attached to the table's after_create, so it exists both when
# `Base.metadata.create_all()` builds a test database and when
# `src.database.migrations.add_observations_and_evidence` creates the real one.
# There is no second copy of the DDL to forget to update.
_OBSERVATIONS_IMMUTABLE_TRIGGER = DDL(
    "CREATE TRIGGER observations_are_immutable "
    "BEFORE UPDATE ON observations "
    "BEGIN "
    "SELECT RAISE(ABORT, "
    "'observations are immutable: the content hash is the identity, so changing "
    "a stored row would leave its hash describing content that is no longer there. "
    "Insert a new observation instead.'); "
    "END"
)

event.listen(
    Observation.__table__,
    "after_create",
    _OBSERVATIONS_IMMUTABLE_TRIGGER.execute_if(dialect="sqlite"),
)


@event.listens_for(Observation, "before_update", propagate=True)
def _refuse_observation_update(_mapper, _connection, target):
    """Refuse an ORM flush that would UPDATE an observation."""
    raise ObservationIsImmutable(
        f"refusing to update observation {target.content_hash}: observations are "
        f"immutable once written. If the content changed, it is a different "
        f"observation with a different hash."
    )


class Evidence(Base):
    """
    One adjudicated link from an observation to a watch, under a named prompt.

    **``prompt_version`` is on every row, and that is the point of the table.**
    Adjudication is the only stochastic tier in the system; the only way to tell
    an improvement from a regression is to hold the observations fixed, run a
    different prompt version over them, and diff. That requires knowing which
    version produced which row, per row -- a version recorded once per run, in a
    log, or in a config file is a version that cannot answer "and where did this
    row come from" six weeks later.

    The uniqueness constraint ``(observation_hash, watch_id, prompt_version)`` is
    what makes replay idempotent: one verdict per observation per watch per
    prompt version, so re-running a version either inserts nothing or reveals
    that the version is not deterministic.

    ``direction`` is two-valued. There is no 'neutral': an observation that
    neither supports nor contradicts a watch produces no row, because a table of
    non-evidence is a table nobody can read.

    Evidence is *derived*. It is the one thing here that may be deleted and
    rebuilt, and ``insightweaver replay --commit`` does exactly that, scoped to a
    single prompt version.

    Added 2026-08-31 for backlog task 014.
    """

    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True)

    observation_hash = Column(String(80), ForeignKey("observations.content_hash"), nullable=False)
    watch_id = Column(String(100), ForeignKey("watches.id"), nullable=False)

    direction = Column(String(20), nullable=False)
    magnitude = Column(Float, nullable=False)

    prompt_version = Column(String(100), nullable=False)
    rationale = Column(Text)

    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint(
            "observation_hash",
            "watch_id",
            "prompt_version",
            name="_evidence_observation_watch_version_uc",
        ),
        CheckConstraint("direction IN ('supports', 'contradicts')", name="ck_evidence_direction"),
        CheckConstraint(
            "magnitude >= 0.0 AND magnitude <= 1.0", name="ck_evidence_magnitude_range"
        ),
        CheckConstraint(
            "length(trim(prompt_version)) > 0", name="ck_evidence_prompt_version_present"
        ),
        Index("idx_evidence_prompt_version", "prompt_version"),
        Index("idx_evidence_watch", "watch_id"),
    )


class RouteCandidate(Base):
    """
    One observation that a Watch's compiled triggers selected as *candidate* evidence.

    Tier 1's output, and nothing more than that. A row here says "this
    observation matched this watch's triggers", which is a claim about regexes
    and a source allowlist -- not a claim that the observation is evidence, and
    not a direction. Adjudication produces :class:`Evidence`; this table is what
    adjudication is allowed to read. Keeping them separate is what makes the
    cost claim checkable: the number of rows in this table is the number of
    observations the one stochastic tier will ever see.

    **The unique constraint is the idempotency.** Routing the same observation
    twice produces one link, because ``(observation_hash, watch_id)`` is unique
    and :func:`src.routing.router.persist` skips what is already there. Tier 1
    is deterministic, so re-running it over an unchanged corpus is a no-op --
    and if it ever is not, the constraint says so with an IntegrityError rather
    than doubling a watch's candidate count.

    ``clause_index`` records *which* trigger clause fired. It is the difference
    between "this watch is routing 400 observations" and "clause 2 of this watch
    is routing 400 observations", which is the difference between knowing a
    trigger is too loose and knowing which line of the file to edit. It is
    excluded from the unique key on purpose: an observation matching two clauses
    of the same watch is still one candidate, and the first clause in file order
    is the one recorded.

    There is no ``routed_by`` or model column, because there is no model. The
    test that proves it is
    tests/routing/test_no_model.py::TestRoutingNeedsNoAnthropicClient.

    Added 2026-08-31 for backlog task 015.
    """

    __tablename__ = "route_candidates"

    id = Column(Integer, primary_key=True)

    observation_hash = Column(String(80), ForeignKey("observations.content_hash"), nullable=False)
    watch_id = Column(String(100), ForeignKey("watches.id"), nullable=False)

    clause_index = Column(Integer, nullable=False)

    routed_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("observation_hash", "watch_id", name="_route_observation_watch_uc"),
        CheckConstraint("clause_index >= 0", name="ck_route_clause_index"),
        Index("idx_route_watch", "watch_id"),
        Index("idx_route_observation", "observation_hash"),
    )
