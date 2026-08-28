"""
Forecast Command - A derived view over the predictions ledger and question
graph. No separate forecast engine; what you see here is exactly what the
synthesis has already committed to as falsifiable observables, organized
by whether each one has resolved.
"""

from datetime import datetime, timedelta

import click

from ..context.beat_scope import prediction_scope_filter, question_scope_filter
from ..database.connection import get_db
from ..database.models import (
    PREDICTION_STATUS_CONTRADICTED,
    PREDICTION_STATUS_OPEN,
    PREDICTION_STATUS_TRIGGERED,
    QUESTION_STATUS_OPEN,
    Prediction,
    Question,
)
from ..utils import utcnow
from ..utils.cadence import InvalidCadence, describe_next_review, is_due
from .colors import accent, header, muted, success, warning
from .scope import beat_option, resolve_beat_scope, scope_label
from .stake import due_predictions_header, render_due_prediction


@click.command(name="forecast")
@click.option(
    "--days",
    "-d",
    type=int,
    default=60,
    help="Window for the resolved track record (default: 60 days).",
)
@click.option(
    "--due",
    "due_only",
    is_flag=True,
    default=False,
    help=(
        "Show only what is due right now: your claims past their resolution "
        "date, and questions whose own review interval has elapsed. Surfacing "
        "a question stamps it as reviewed."
    ),
)
@beat_option
def forecast_command(days, due_only, beat_name):
    """
    Show open observables and the recently-resolved record.

    Scoped: this is a derived view over the predictions ledger, so it inherits
    the ledger's scoping. Without --beat it shows your own observables only.
    """
    if due_only:
        _render_due(beat_name)
        return

    cutoff = utcnow() - timedelta(days=days)

    with get_db() as session:
        beat_id = resolve_beat_scope(session, beat_name)
        scope = prediction_scope_filter(session, beat_id)
        open_preds = (
            session.query(Prediction)
            .filter(Prediction.status == PREDICTION_STATUS_OPEN, scope)
            .order_by(Prediction.made_at.asc())
            .all()
        )
        resolved = (
            session.query(Prediction)
            .filter(
                Prediction.status.in_(
                    [PREDICTION_STATUS_TRIGGERED, PREDICTION_STATUS_CONTRADICTED]
                ),
                Prediction.resolved_at >= cutoff,
                scope,
            )
            .order_by(Prediction.resolved_at.desc())
            .all()
        )

        click.echo(header(f"FORECAST ({scope_label(beat_name)})"))
        click.echo(
            muted(
                "A derived view over the predictions ledger -- not a separate engine. "
                "What you see here is exactly what past syntheses committed to as "
                "falsifiable observables."
            )
        )
        click.echo("=" * 80)
        click.echo()

        click.echo(header("KNOWN UNKNOWNS"))
        click.echo(muted("Open observables -- explicit triggers, not yet resolved."))
        click.echo()
        if not open_preds:
            click.echo(muted("  No open observables."))
        else:
            for p in open_preds:
                _render_open_prediction(p)
        click.echo()

        click.echo(header(f"KNOWN KNOWNS (last {days} days)"))
        click.echo(muted("Observables later coverage triggered or contradicted."))
        click.echo()
        if not resolved:
            click.echo(muted("  No resolutions in this window."))
        else:
            triggered = [p for p in resolved if p.status == PREDICTION_STATUS_TRIGGERED]
            contradicted = [p for p in resolved if p.status == PREDICTION_STATUS_CONTRADICTED]
            for p in triggered:
                _render_resolved_prediction(p, success("triggered"))
            for p in contradicted:
                _render_resolved_prediction(p, warning("contradicted"))

        click.echo()
        click.echo(
            muted(
                "Note: the 'unknown unknowns' bucket has been removed by design. "
                "The tool does not fabricate observables it cannot ground in evidence."
            )
        )


def _render_due(beat_name: str | None) -> None:
    """
    Answer "what is due right now", at each question's own speed.

    Two things can be due, and they are deliberately different clocks:

    * a **prediction** whose ``due_by`` has passed -- a specific claim that can
      now be graded, and
    * a **question** whose own review interval has elapsed since it was last
      reviewed -- worth re-examining, whether or not anything moved.

    Surfacing a question stamps ``last_reviewed_at``. That is the point: a
    quiet question that reappears every day trains the operator to skim, and
    skimming is how a standing agenda stops being one. Nothing runs on a
    schedule -- ``--due`` is a question you ask.
    """
    now = utcnow()
    with get_db() as session:
        beat_id = resolve_beat_scope(session, beat_name)

        awaiting = (
            session.query(Prediction)
            .filter(
                Prediction.status == PREDICTION_STATUS_OPEN,
                Prediction.due_by.is_not(None),
                Prediction.due_by <= now,
                prediction_scope_filter(session, beat_id),
            )
            .order_by(Prediction.due_by.asc())
            .all()
        )

        open_questions = (
            session.query(Question)
            .filter(
                Question.status == QUESTION_STATUS_OPEN,
                question_scope_filter(session, beat_id),
            )
            .order_by(Question.first_asked_at.asc())
            .all()
        )
        # Each question is tested against its *own* interval, not a global
        # rhythm: two questions on different cadences come due independently.
        due_questions = [q for q in open_questions if _question_is_due(q, now)]
        uncadenced = sum(1 for q in open_questions if not q.cadence)

        click.echo(header(f"DUE NOW ({scope_label(beat_name)})"))
        click.echo(muted(f"As of {now.date().isoformat()}. Nothing here runs on its own."))
        click.echo("=" * 80)
        click.echo()

        due_predictions_header(len(awaiting))
        if not awaiting:
            click.echo(muted("  Nothing of yours has come due."))
            click.echo()
        else:
            for p in awaiting:
                render_due_prediction(p, now)

        click.echo(header(f"QUESTIONS DUE FOR REVIEW ({len(due_questions)})"))
        click.echo(muted("Each question against its own cadence, not a shared rhythm."))
        click.echo()
        if not due_questions:
            click.echo(muted("  No question's review interval has elapsed."))
            click.echo()
        else:
            for q in due_questions:
                _render_due_question(session, q, now, beat_id)

        # The stamp happens whether or not anything moved.
        for q in due_questions:
            q.last_reviewed_at = now
        session.commit()

        if due_questions:
            ids = ", ".join(f"Q{q.id}" for q in due_questions)
            click.echo(success(f"Stamped as reviewed: {ids}."))
            click.echo(
                muted("Reviewed means looked at, not resolved. They return at their next interval.")
            )
            click.echo()

        if uncadenced:
            click.echo(
                muted(
                    f"{uncadenced} open question(s) carry no cadence and never surface "
                    "here. A cadence is your read on how fast a subject moves, so only "
                    "questions you declared with 'questions add' have one."
                )
            )


def _question_is_due(q: Question, now: datetime) -> bool:
    """Whether one question's own interval has elapsed. A bad stored cadence is not due."""
    try:
        return is_due(q.cadence, q.last_reviewed_at, q.first_asked_at, now)
    except InvalidCadence:
        return False


def _render_due_question(session, q: Question, now: datetime, beat_id: int | None) -> None:
    """A due question plus whatever open claims are already staked on it."""
    try:
        phrase = describe_next_review(q.cadence, q.last_reviewed_at, q.first_asked_at, now)
    except InvalidCadence as exc:
        phrase = f"unreadable cadence ({exc.raw})"
    last = q.last_reviewed_at.date().isoformat() if q.last_reviewed_at else "never"
    click.echo(
        f"  {accent(f'Q{q.id}')} {muted(f'cadence {q.cadence} | {phrase} | last reviewed {last}')}"
    )
    click.echo(f"      {q.text}")

    open_claims = (
        session.query(Prediction)
        .filter(
            Prediction.question_id == q.id,
            Prediction.status == PREDICTION_STATUS_OPEN,
            prediction_scope_filter(session, beat_id),
        )
        .order_by(Prediction.made_at.asc())
        .all()
    )
    if not open_claims:
        click.echo(
            muted(f'      No open claim. Stake one: predict {q.id} "..." --by DATE --confidence N')
        )
    for p in open_claims:
        due = p.due_by.date().isoformat() if p.due_by else "no date"
        conf = f"{p.confidence:.0%}" if p.confidence is not None else "no confidence"
        click.echo(muted(f"      P{p.id} [{p.author}] {conf}, due {due}: {p.observable_text}"))
    click.echo()


def _question_tag(question: Question | None) -> str:
    if question is None:
        return ""
    return f"[Q{question.id}] "


def _render_open_prediction(p: Prediction) -> None:
    tag = _question_tag(p.question)
    click.echo(f"  {accent(f'P{p.id}')} {muted(tag)}{p.observable_text}")
    click.echo(f"      Trigger: {muted(p.trigger_condition)}")
    if p.question:
        click.echo(f"      Bears on: {muted(p.question.text)}")
    click.echo()


def _render_resolved_prediction(p: Prediction, status_label: str) -> None:
    tag = _question_tag(p.question)
    click.echo(f"  {accent(f'P{p.id}')} [{status_label}] {muted(tag)}{p.observable_text}")
    if p.resolution_note:
        click.echo(f"      {p.resolution_note}")
    click.echo()
