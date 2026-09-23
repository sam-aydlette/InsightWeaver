"""
Part of the model split of 2026-09-22 (backlog task 030); see ``__init__``.
"""

from sqlalchemy import (
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
)

from ...utils import utcnow
from .base import Base


class Route(Base):
    """
    One observation routed to one watch by a deterministic trigger clause.

    Tier 1's whole job is to keep the model from seeing the bulk of the corpus:
    every row here is a candidate pair the adjudicator may be asked about, and
    every observation with no row here is one it never sees. ``clause_index``
    records which of the watch's trigger clauses fired first, so a route can be
    explained by reading the watch file rather than by re-running the matcher.

    Unique per ``(observation, watch)`` so that routing is idempotent: the same
    observation routed twice is one link. Derived from ``observations`` and
    ``watches.triggers`` alone, with no model call, so the table can be dropped
    and rebuilt (``route --rebuild``) whenever a trigger changes.

    Added 2026-09-22 for backlog task 028.
    """

    __tablename__ = "routes"

    id = Column(Integer, primary_key=True)
    observation_hash = Column(String(80), ForeignKey("observations.content_hash"), nullable=False)
    watch_id = Column(String(100), ForeignKey("watches.id"), nullable=False)
    clause_index = Column(Integer, nullable=False)
    routed_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("observation_hash", "watch_id", name="_route_observation_watch_uc"),
        CheckConstraint("clause_index >= 0", name="ck_routes_clause_index"),
        Index("idx_routes_watch", "watch_id"),
        Index("idx_routes_observation", "observation_hash"),
    )


class Adjudication(Base):
    """
    One model call about one routed pair, whatever it answered.

    ``outcome`` is ``evidence`` (a verdict was written to ``evidence``),
    ``none`` (the model judged the item not to bear on the claim) or ``failed``
    (a refusal, an API error, or a response that failed validation; the text
    is in ``error``). A failed pair is left here and never retried: a retry
    that produced a different answer to the same input would break the replay
    determinism that is the only way to review a prompt change.

    Unique per ``(observation, watch, prompt_version)``, which is what makes
    ``insightweaver adjudicate`` idempotent: run twice, the second run asks
    nothing. ``audit_id`` finds the exact request in the local audit log;
    ``input_tokens`` and ``output_tokens`` are what the API reported, so the
    cost of a run is a sum over this table and not a guess. ``confidence``,
    ``satisfies_clause`` and ``rationale`` keep the rest of a validated
    verdict, for 'none' verdicts too, since ``evidence`` holds only evidence.

    Added 2026-09-22 for backlog task 029.
    """

    __tablename__ = "adjudications"

    id = Column(Integer, primary_key=True)
    observation_hash = Column(String(80), ForeignKey("observations.content_hash"), nullable=False)
    watch_id = Column(String(100), ForeignKey("watches.id"), nullable=False)
    prompt_version = Column(String(100), nullable=False)
    outcome = Column(String(20), nullable=False)
    error = Column(Text)
    audit_id = Column(String(40))
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    # The parts of a validated verdict that `evidence` does not hold: the
    # model's confidence in its reading, the clause it named, and the
    # rationale for a 'none' verdict as well as for evidence. Null on failure.
    confidence = Column(Float)
    satisfies_clause = Column(Integer)
    rationale = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "observation_hash",
            "watch_id",
            "prompt_version",
            name="_adjudication_pair_version_uc",
        ),
        CheckConstraint(
            "outcome IN ('evidence', 'none', 'failed')", name="ck_adjudications_outcome"
        ),
        CheckConstraint(
            "length(trim(prompt_version)) > 0", name="ck_adjudications_prompt_version_present"
        ),
        Index("idx_adjudications_version", "prompt_version"),
        Index("idx_adjudications_watch", "watch_id"),
    )


class BriefRun(Base):
    """
    One row per brief rendered, so the next brief knows where the last left off.

    ``brief`` defaults its window to the ``as_of`` of the most recent row
    delivered before the start of the day it is rendered on, which is what
    makes a second run the same morning reproduce the first instead of
    reporting "nothing since ten minutes ago". ``rendered_sha`` is the hash of
    the bytes printed, kept so a reader can check that a saved brief is the one
    this row records. ``--dry-run`` renders without writing here.

    Added 2026-09-22 for backlog task 031.
    """

    __tablename__ = "briefs"

    id = Column(Integer, primary_key=True)
    as_of = Column(DateTime, nullable=False)
    since = Column(DateTime, nullable=False)
    moved = Column(Integer, nullable=False)
    quiet = Column(Integer, nullable=False)
    rendered_sha = Column(String(80), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (Index("idx_briefs_as_of", "as_of"),)
