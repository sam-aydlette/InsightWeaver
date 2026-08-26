"""
Standing questions: the agenda a beat declares, rather than the one its
coverage happens to raise.

Emergent Questions are discovered -- the graph notices what coverage leaves
unresolved. A **standing question** is the other direction: the human writes it
into ``config/beats/<name>.json`` and the beat carries it whether or not this
week's coverage touches it. That inversion is the whole point, so the
load-bearing behaviour here is the *quiet* case: a standing question with no
coverage this run is reported as unmoved, never filtered out as an empty
section. "No movement on CMMC Phase 2 this week" is a finding.

Two things follow from that:

* **Seeding is idempotent and beat-bound.** A declared question becomes a real
  ``Question`` row on the beat's first run, joined to the beat through
  ``beat_standing_questions``. Re-running seeds nothing new. The join is what
  keeps a never-yet-moved question inside the beat's scope instead of leaking
  into the person brief's ledger -- see ``beat_scope.question_scope_filter``.
* **The agenda is computed at store time, not at render time.** It lands in
  ``synthesis_data["metadata"]["standing_agenda"]``, so ``--from-run`` replays
  the same agenda the live run reported, and no renderer needs database access.

Added 2026-08-26 for backlog task 007.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from ..database.models import (
    PREDICTION_STATUS_OPEN,
    QUESTION_STATUS_OPEN,
    BeatStandingQuestion,
    Prediction,
    Question,
    QuestionSituation,
)
from ..utils import utcnow
from .beat_scope import beat_synthesis_ids, scoped_appearance_count
from .question_matcher import normalize_question

logger = logging.getLogger(__name__)


def seed_standing_questions(
    session: Session, beat_id: int, declared: tuple[str, ...] | list[str]
) -> list[Question]:
    """
    Make sure every question this beat declares exists in the graph.

    Returns the ``Question`` rows for the declared agenda, in declaration
    order. The caller commits.

    Idempotent by normalized text within the beat. An existing open Question in
    this beat's scope with the same normalized text is *adopted* rather than
    duplicated: when a beat has been raising a question emergently and the
    human then declares it, that is the same question and its accumulated
    history should survive the declaration.

    Nothing is ever retired here. Removing a question from the config stops it
    being declared; it does not close the Question, because closing a question
    is a judgement and this function makes none.
    """
    if not declared:
        return []

    existing_rows = {
        row.normalized_text: row
        for row in session.query(BeatStandingQuestion).filter(
            BeatStandingQuestion.beat_id == beat_id
        )
    }

    seeded: list[Question] = []
    now = utcnow()
    for text in declared:
        normalized = normalize_question(text)
        if not normalized:
            # The config loader rejects blank declarations, so this can only be
            # punctuation-only text. Skipping it silently would drop an agenda
            # item, so say so.
            logger.warning(f"Standing question {text!r} normalizes to nothing; not seeded")
            continue

        link = existing_rows.get(normalized)
        if link is not None:
            question = session.query(Question).filter(Question.id == link.question_id).first()
            if question is not None:
                seeded.append(question)
                continue
            # The declaration outlived its Question row. Re-seed rather than
            # carry a dangling agenda item.
            session.delete(link)
            session.flush()

        question = _adopt_or_create(session, beat_id, text, normalized, now)
        session.add(
            BeatStandingQuestion(
                beat_id=beat_id,
                question_id=question.id,
                declared_text=text,
                normalized_text=normalized,
                declared_at=now,
            )
        )
        session.flush()
        seeded.append(question)
        logger.info(f"Seeded standing question Q{question.id} for beat {beat_id}: {text!r}")

    return seeded


def _adopt_or_create(
    session: Session, beat_id: int, text: str, normalized: str, now: Any
) -> Question:
    """Reuse this beat's open Question with the same normalized text, or make one."""
    already_this_beat = (
        session.query(Question)
        .join(QuestionSituation, QuestionSituation.question_id == Question.id)
        .filter(
            Question.normalized_text == normalized,
            Question.status == QUESTION_STATUS_OPEN,
            QuestionSituation.synthesis_id.in_(beat_synthesis_ids(beat_id)),
        )
        .first()
    )
    if already_this_beat is not None:
        logger.info(
            f"Standing question {text!r} adopts existing Q{already_this_beat.id} "
            f"already raised by beat {beat_id}"
        )
        return already_this_beat

    question = Question(
        text=text,
        normalized_text=normalized,
        first_asked_at=now,
        status=QUESTION_STATUS_OPEN,
        is_primary=True,
    )
    session.add(question)
    session.flush()
    return question


def build_standing_agenda(
    session: Session,
    beat_id: int,
    situations: list[dict[str, Any]],
    movement: dict[int, list[int]],
) -> list[dict[str, Any]]:
    """
    Report this run's movement against every declared standing question.

    ``movement`` maps a Question id to the zero-based indices of the situations
    that bound to it in this run. A standing question absent from that mapping
    did not move, and it still gets an entry -- with ``moved`` false and the
    date it last moved, or ``None`` if it never has. Filtering those out is the
    one thing this function must never do.

    Returns entries in declaration order. Renderers consume this verbatim; it
    contains no styling and no judgement about whether a question is well-posed.
    """
    links = (
        session.query(BeatStandingQuestion)
        .filter(BeatStandingQuestion.beat_id == beat_id)
        .order_by(BeatStandingQuestion.declared_at.asc(), BeatStandingQuestion.id.asc())
        .all()
    )

    agenda: list[dict[str, Any]] = []
    for link in links:
        question = session.query(Question).filter(Question.id == link.question_id).first()
        if question is None:
            continue

        moved_indices = sorted(movement.get(int(question.id), []))
        entry: dict[str, Any] = {
            "question_id": int(question.id),
            "text": question.text,
            "status": question.status,
            "declared_at": _date(link.declared_at),
            "moved": bool(moved_indices),
            "moved_in": [
                {
                    "situation_index": index + 1,
                    "title": _situation_title(situations, index),
                }
                for index in moved_indices
            ],
            # Counted within this beat's scope, and inclusive of this run: the
            # number the reader sees is "how many runs of this beat have moved
            # it", not "how many times anything anywhere raised it".
            "appearance_count": scoped_appearance_count(session, question.id, beat_id)
            + len(moved_indices),
            "last_moved_at": _last_moved_at(session, beat_id, int(question.id)),
            "watching": _open_observables(session, int(question.id)),
        }
        if link.declared_text and link.declared_text != question.text:
            entry["declared_text"] = link.declared_text
        agenda.append(entry)

    return agenda


def _situation_title(situations: list[dict[str, Any]], index: int) -> str:
    if 0 <= index < len(situations):
        title = situations[index].get("title")
        if isinstance(title, str):
            return title
    return ""


def _last_moved_at(session: Session, beat_id: int, question_id: int) -> str | None:
    """The date this question last appeared in one of *this beat's* syntheses."""
    row = (
        session.query(QuestionSituation.observed_at)
        .filter(
            QuestionSituation.question_id == question_id,
            QuestionSituation.synthesis_id.in_(beat_synthesis_ids(beat_id)),
        )
        .order_by(QuestionSituation.observed_at.desc())
        .first()
    )
    return _date(row[0]) if row and row[0] else None


def _open_observables(session: Session, question_id: int) -> list[str]:
    """
    Open predictions keyed to this question -- what would have to be observed
    to change the picture. Read-only: the ledger is graded elsewhere, and
    nothing here creates, resolves or expires a Prediction.
    """
    rows = (
        session.query(Prediction)
        .filter(
            Prediction.question_id == question_id,
            Prediction.status == PREDICTION_STATUS_OPEN,
        )
        .order_by(Prediction.made_at.desc())
        .all()
    )
    items: list[str] = []
    for row in rows:
        observable = (row.observable_text or "").strip()
        trigger = (row.trigger_condition or "").strip()
        if observable and trigger:
            items.append(f"{observable} -- {trigger}")
        elif observable:
            items.append(observable)
    return items


def _date(value: Any) -> str | None:
    """A datetime as ``YYYY-MM-DD``, or None."""
    return value.date().isoformat() if value is not None else None
