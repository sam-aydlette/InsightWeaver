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

from sqlalchemy import and_, func, inspect, or_, select, true
from sqlalchemy.orm import Session

from ..config.beats import BeatConfig
from ..database.models import (
    Beat,
    BeatRun,
    BeatStandingQuestion,
    Prediction,
    Question,
    QuestionSituation,
)
from ..utils import utcnow

logger = logging.getLogger(__name__)


class BeatTablesMissing(RuntimeError):
    """Raised when a beat run is attempted on a database that predates beats."""


class BeatNotRecorded(LookupError):
    """Raised when a name does not match any beat that has ever run."""

    def __init__(self, name: str, known: list[str]) -> None:
        self.name = name
        self.known = known
        available = ", ".join(known) if known else "none yet"
        super().__init__(f"No beat named '{name}' has recorded a run. Beats with runs: {available}")


# Which migration creates each beat table, for the "you have not migrated"
# message. beat_standing_questions arrived later than the other two (2026-08-26,
# backlog task 007), so a database can legitimately have one and not the other.
_BEAT_TABLE_MIGRATIONS = {
    Beat.__tablename__: "add_beats",
    BeatRun.__tablename__: "add_beats",
    BeatStandingQuestion.__tablename__: "add_standing_questions",
}


def require_beat_tables(bind) -> None:
    """
    Fail if this database has no beats at all.

    On the write side: without ``beats``/``beat_runs`` a run would have nowhere
    to be attributed, and an unattributed beat run is indistinguishable from
    the default brief -- so it must not start. Without
    ``beat_standing_questions`` a declared agenda would have nowhere to be
    recorded, and a standing question that cannot be recorded must not be
    silently skipped -- that is the failure this feature exists to prevent. On
    the read side: there is no beat ledger to show, and an empty listing would
    read as "this beat has nothing", which is a wrong answer rather than a
    missing one.
    """
    inspector = inspect(bind)
    missing = [name for name in _BEAT_TABLE_MIGRATIONS if not inspector.has_table(name)]
    if missing:
        migrations = sorted({_BEAT_TABLE_MIGRATIONS[name] for name in missing})
        commands = " and ".join(
            f"'python -m src.database.migrations.{module}'" for module in migrations
        )
        raise BeatTablesMissing(
            f"This database has no {' or '.join(missing)} table, so it cannot record "
            f"beats yet. Run {commands} (or 'insightweaver brief setup') once, then retry."
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


def beat_synthesis_ids(beat_id: int):
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


def _standing_questions_recorded(session: Session) -> bool:
    """
    Whether this database can hold declared standing questions.

    Same reasoning as :func:`_beat_runs_recorded`: a database that predates
    backlog task 007 has no ``beat_standing_questions`` table, and "the table
    does not exist" and "the table is empty" are the same statement -- no beat
    has declared anything.
    """
    return inspect(session.get_bind()).has_table(BeatStandingQuestion.__tablename__)


def question_scope_filter(session: Session, beat_id: int | None):
    """
    A criterion restricting a ``Question`` query to one scope.

    A question is in a beat's scope when it appeared in one of that beat's
    syntheses **or** when that beat declared it as a standing question. The
    second clause is what keeps a declared question that no coverage has yet
    touched inside the beat rather than in the default scope: it has no
    situation links to derive a beat from, so without it the person brief's
    matcher could bind to a compliance beat's agenda item.

    ``beat_id=None`` yields the default scope: questions that have never
    appeared in any beat's synthesis and that no beat has declared. A question
    with no links at all (one created earlier in this same transaction) is in
    the default scope, which is harmless because such a question is not a match
    candidate anyway.
    """
    runs_possible = _beat_runs_recorded(session)
    standing_possible = _standing_questions_recorded(session)

    if beat_id is None and not runs_possible and not standing_possible:
        return true()

    if beat_id is None:
        excluded = []
        if runs_possible:
            excluded.append(
                Question.id.not_in(
                    select(QuestionSituation.question_id).where(
                        QuestionSituation.synthesis_id.in_(_any_beat_synthesis_ids())
                    )
                )
            )
        if standing_possible:
            excluded.append(Question.id.not_in(select(BeatStandingQuestion.question_id)))
        return and_(*excluded)

    included = [
        Question.id.in_(
            select(QuestionSituation.question_id).where(
                QuestionSituation.synthesis_id.in_(beat_synthesis_ids(beat_id))
            )
        )
    ]
    if standing_possible:
        included.append(
            Question.id.in_(
                select(BeatStandingQuestion.question_id).where(
                    BeatStandingQuestion.beat_id == beat_id
                )
            )
        )
    return or_(*included)


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
        stmt = stmt.where(QuestionSituation.synthesis_id.in_(beat_synthesis_ids(beat_id)))

    return int(session.execute(stmt).scalar() or 0)


def beat_id_by_name(session: Session, name: str) -> int:
    """
    Resolve a beat name to its id for the read side.

    Deliberately keyed off the ``beats`` table rather than ``config/beats/``:
    a ledger you have already accumulated stays readable after its config file
    is edited or deleted. Reading is about what ran, not about what is
    currently configured to run.
    """
    require_beat_tables(session.get_bind())
    row = session.query(Beat).filter(Beat.name == name).first()
    if row is None:
        known = [entry[0] for entry in session.query(Beat.name).order_by(Beat.name).all()]
        raise BeatNotRecorded(name, known)
    return int(row.id)


def declared_standing_question_ids(session: Session, beat_id: int | None) -> set[int]:
    """
    The Question ids one beat has declared as standing questions.

    ``beat_id=None`` returns an empty set: the default brief is a person, not a
    subject, and only a beat can declare an agenda.
    """
    if beat_id is None or not _standing_questions_recorded(session):
        return set()

    rows = (
        session.query(BeatStandingQuestion.question_id)
        .filter(BeatStandingQuestion.beat_id == beat_id)
        .all()
    )
    return {int(entry[0]) for entry in rows}


def owning_beat_names(session: Session, question_id: int | None) -> list[str]:
    """
    Which beats, if any, a question has appeared under or been declared by.

    Used by the id-addressed commands to disclose the scope a row belongs to.
    An empty list means the question belongs to the default scope. A declared
    standing question that has never moved still names its beat here, because
    it belongs to that ledger from the moment it is declared.
    """
    if question_id is None:
        return []

    names: set[str] = set()

    if _beat_runs_recorded(session):
        appeared = (
            session.query(Beat.name)
            .join(BeatRun, BeatRun.beat_id == Beat.id)
            .join(QuestionSituation, QuestionSituation.synthesis_id == BeatRun.synthesis_id)
            .filter(QuestionSituation.question_id == question_id)
            .distinct()
            .all()
        )
        names.update(entry[0] for entry in appeared)

    if _standing_questions_recorded(session):
        declared = (
            session.query(Beat.name)
            .join(BeatStandingQuestion, BeatStandingQuestion.beat_id == Beat.id)
            .filter(BeatStandingQuestion.question_id == question_id)
            .distinct()
            .all()
        )
        names.update(entry[0] for entry in declared)

    return sorted(names)
