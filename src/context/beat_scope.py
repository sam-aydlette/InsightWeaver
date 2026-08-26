"""
Beat scoping for the commitment graph.

The graph tables (``questions``, ``question_situations``, ``predictions``)
carry no ``beat_id`` column. A row's beat is *derived* instead: a synthesis
belongs to a beat when ``beat_runs`` says so, a Question belongs to a beat when
it appeared in one of that beat's syntheses, and a Prediction inherits the beat
of the Question it keys off. Two scopes therefore exist:

* a **beat scope** -- rows reachable from that beat's runs, and
* the **default scope** -- rows that no beat run ever touched, which is the
  person-profile brief the tool has always produced.

With no ``beat_runs`` rows at all -- the state of every existing database
before this feature is used -- the default scope is the whole graph and every
helper here is an identity filter, which is what keeps ``insightweaver brief``
byte-identical to its previous behaviour.

See docs/CONCEPTS.md, "Beats", for why derivation was chosen over a column.
Added 2026-08-26 for backlog task 004.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, inspect, select, true
from sqlalchemy.orm import Session

from ..config.beats import BeatConfig
from ..database.models import Beat, BeatRun, Prediction, Question, QuestionSituation
from ..utils import utcnow

logger = logging.getLogger(__name__)


class BeatTablesMissing(RuntimeError):
    """Raised when a beat run is attempted on a database that predates beats."""


def require_beat_tables(bind) -> None:
    """
    Fail before a beat run starts if this database cannot record it.

    Without ``beats``/``beat_runs`` the run would have nowhere to be
    attributed, and an unattributed beat run is indistinguishable from the
    default brief -- so it must not start at all.
    """
    inspector = inspect(bind)
    missing = [
        name
        for name in (Beat.__tablename__, BeatRun.__tablename__)
        if not inspector.has_table(name)
    ]
    if missing:
        raise BeatTablesMissing(
            f"This database has no {' or '.join(missing)} table, so a beat run could "
            f"not be recorded. Run 'python -m src.database.migrations.add_beats' "
            f"(or 'insightweaver brief setup') once, then retry."
        )


def ensure_beat(session: Session, config: BeatConfig) -> int:
    """
    Get or create the ``beats`` row for a loaded beat config, returning its id.

    The config file stays authoritative for sources; this row exists so runs
    can be attributed and so the beat keeps a stable id across config edits.
    """
    row = session.query(Beat).filter(Beat.name == config.name).first()
    if row is None:
        row = Beat(
            name=config.name,
            description=config.description,
            config_path=config.config_path,
        )
        session.add(row)
        session.flush()
        logger.info(f"Registered new beat '{config.name}' as beat_id {row.id}")
    else:
        row.description = config.description
        row.config_path = config.config_path
        row.updated_at = utcnow()
    return int(row.id)


def _beat_synthesis_ids(beat_id: int):
    """Select of every synthesis id attributed to one beat."""
    return select(BeatRun.synthesis_id).where(
        BeatRun.beat_id == beat_id,
        BeatRun.synthesis_id.is_not(None),
    )


def _any_beat_synthesis_ids():
    """Select of every synthesis id attributed to any beat."""
    return select(BeatRun.synthesis_id).where(BeatRun.synthesis_id.is_not(None))


def _beat_runs_recorded(session: Session) -> bool:
    """
    Whether this database can have attributed any run to a beat.

    A database predating this feature has no ``beat_runs`` table. That is not a
    fallback case to paper over -- "the table does not exist" and "the table is
    empty" are the same statement: no run has ever been attributed to a beat.
    Both mean the default scope is the whole graph. Checking lets the default
    brief keep working on an unmigrated database instead of failing on a table
    it has no reason to care about.

    A beat *run* never takes this path: registering the beat writes to ``beats``
    first, so a missing table surfaces there, loudly, before any scoped query.
    """
    return inspect(session.get_bind()).has_table(BeatRun.__tablename__)


def question_scope_filter(session: Session, beat_id: int | None):
    """
    A criterion restricting a ``Question`` query to one scope.

    ``beat_id=None`` yields the default scope: questions that have never
    appeared in any beat's synthesis. A question with no situation links at all
    (one created earlier in this same transaction) is in the default scope,
    which is harmless because such a question is not a match candidate anyway.
    """
    if beat_id is None and not _beat_runs_recorded(session):
        return true()

    linked_to_beat = select(QuestionSituation.question_id).where(
        QuestionSituation.synthesis_id.in_(_any_beat_synthesis_ids())
    )
    if beat_id is None:
        return Question.id.not_in(linked_to_beat)

    linked_to_this_beat = select(QuestionSituation.question_id).where(
        QuestionSituation.synthesis_id.in_(_beat_synthesis_ids(beat_id))
    )
    return Question.id.in_(linked_to_this_beat)


def prediction_scope_filter(session: Session, beat_id: int | None):
    """
    A criterion restricting a ``Prediction`` query to one scope.

    Predictions key off Questions, so scoping the questions scopes the ledger:
    a beat run grades only its own open observables and never expires or
    resolves another scope's.
    """
    if beat_id is None and not _beat_runs_recorded(session):
        return true()

    in_scope_questions = select(Question.id).where(question_scope_filter(session, beat_id))
    return Prediction.question_id.in_(in_scope_questions)


def scoped_appearance_count(session: Session, question_id: int | None, beat_id: int | None) -> int:
    """
    How many times a question has already appeared *within one scope*.

    This is what makes ``Q47 (run 4, asked 2026-03-12)`` mean "the fourth time
    this beat raised it" rather than "the fourth time anything raised it".
    """
    if question_id is None:
        return 0

    stmt = (
        select(func.count())
        .select_from(QuestionSituation)
        .where(QuestionSituation.question_id == question_id)
    )
    if beat_id is None:
        if _beat_runs_recorded(session):
            stmt = stmt.where(QuestionSituation.synthesis_id.not_in(_any_beat_synthesis_ids()))
    else:
        stmt = stmt.where(QuestionSituation.synthesis_id.in_(_beat_synthesis_ids(beat_id)))

    return int(session.execute(stmt).scalar() or 0)
