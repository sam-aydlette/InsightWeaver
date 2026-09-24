"""
Part of the model split of 2026-09-22 (backlog task 030); see ``__init__``.
"""

from sqlalchemy import (
    DDL,
    JSON,
    CheckConstraint,
    Column,
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

from ...utils import utcnow
from .base import Base, ObservationIsImmutable


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
