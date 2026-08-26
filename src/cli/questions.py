"""
Questions Command - Inspect and manage the persistent Question graph.
"""

import click

from ..context.beat_scope import owning_beat_names, question_scope_filter
from ..database.connection import get_db
from ..database.models import (
    QUESTION_STATUS_OPEN,
    QUESTION_STATUS_RESOLVED,
    NarrativeSynthesis,
    Question,
    QuestionSituation,
)
from ..utils import utcnow
from .colors import accent, header, muted, success, warning
from .scope import beat_option, resolve_beat_scope, scope_label


@click.group(name="questions")
def questions_command():
    """Inspect and manage the persistent question graph."""
    pass


@questions_command.command(name="list")
@click.option("--status", "-s", type=click.Choice(["open", "resolved", "all"]), default="open")
@click.option("--limit", "-n", type=int, default=50)
@beat_option
def list_questions(status, limit, beat_name):
    """
    List questions, oldest open first by default.

    Scoped: without --beat this is your own ledger and never shows a beat's
    questions. Pass --beat NAME to read that subject's ledger instead.
    """
    with get_db() as session:
        beat_id = resolve_beat_scope(session, beat_name)
        query = session.query(Question).filter(question_scope_filter(session, beat_id))
        if status != "all":
            query = query.filter(Question.status == status)

        if status == QUESTION_STATUS_OPEN:
            query = query.order_by(Question.first_asked_at.asc())
        else:
            query = query.order_by(Question.first_asked_at.desc())

        rows = query.limit(limit).all()

        if not rows:
            click.echo(muted(f"No {status} questions in {scope_label(beat_name)}."))
            return

        click.echo(header(f"QUESTIONS ({status}, {len(rows)} shown, {scope_label(beat_name)})"))
        click.echo("=" * 80)
        now = utcnow()
        for q in rows:
            age_days = (now - q.first_asked_at).days
            tag = success("open") if q.status == QUESTION_STATUS_OPEN else muted(q.status)
            click.echo(
                f"{accent(f'Q{q.id}')}  [{tag}]  "
                f"{muted(f'asked {q.first_asked_at.date().isoformat()} ({age_days}d ago)')}"
            )
            click.echo(f"  {q.text}")
            if q.previous_question_id:
                click.echo(muted(f"  (follows Q{q.previous_question_id})"))
            click.echo()


@questions_command.command(name="show")
@click.argument("question_id", type=int)
def show_question(question_id):
    """
    Show a question's full history across runs.

    Not scoped: you named a specific question, so it is looked up wherever it
    lives. The ledger it belongs to is disclosed rather than assumed.
    """
    with get_db() as session:
        q = session.query(Question).filter_by(id=question_id).first()
        if not q:
            click.echo(warning(f"Question Q{question_id} not found."))
            return

        click.echo(header(f"QUESTION Q{q.id}"))
        click.echo("=" * 80)
        click.echo(q.text)
        click.echo()
        owners = owning_beat_names(session, q.id)
        click.echo(muted(f"Ledger: {', '.join(owners) if owners else 'yours (no beat)'}"))
        click.echo(muted(f"First asked: {q.first_asked_at.isoformat()}"))
        click.echo(muted(f"Status: {q.status}"))
        if q.resolved_at:
            click.echo(muted(f"Resolved: {q.resolved_at.isoformat()}"))
        if q.resolution_note:
            click.echo(muted(f"Note: {q.resolution_note}"))
        if q.previous_question_id:
            click.echo(muted(f"Previous question: Q{q.previous_question_id}"))
        click.echo()

        links = (
            session.query(QuestionSituation, NarrativeSynthesis)
            .join(NarrativeSynthesis, QuestionSituation.synthesis_id == NarrativeSynthesis.id)
            .filter(QuestionSituation.question_id == q.id)
            .order_by(QuestionSituation.observed_at.asc())
            .all()
        )

        if not links:
            click.echo(muted("No appearances recorded."))
            return

        click.echo(header(f"Appearances ({len(links)})"))
        click.echo("-" * 80)
        for i, (link, synth) in enumerate(links, 1):
            situation_title = _situation_title(synth, link.situation_index)
            click.echo(
                f"  {accent(f'#{i}')} {link.observed_at.date().isoformat()}  "
                f"synthesis {synth.id}  situation {link.situation_index}"
            )
            if situation_title:
                click.echo(f"      {muted(situation_title)}")


@questions_command.command(name="resolve")
@click.argument("question_id", type=int)
@click.option("--note", required=True, help="Resolution note explaining what closed this question.")
def resolve_question(question_id, note):
    """
    Mark a question resolved with a note.

    Not scoped, for the same reason as `show`: resolving is an explicit act on
    a named row. Which ledger it belonged to is reported back, so resolving a
    beat's question from your own context is visible rather than silent.
    """
    with get_db() as session:
        q = session.query(Question).filter_by(id=question_id).first()
        if not q:
            click.echo(warning(f"Question Q{question_id} not found."))
            return
        if q.status != QUESTION_STATUS_OPEN:
            click.echo(warning(f"Q{q.id} is already {q.status}; not modifying."))
            return

        owners = owning_beat_names(session, q.id)
        q.status = QUESTION_STATUS_RESOLVED
        q.resolved_at = utcnow()
        q.resolution_note = note
        session.commit()

        where = f" in beat {', '.join(owners)}" if owners else ""
        click.echo(success(f"Q{q.id} resolved{where}."))


def _situation_title(synth: NarrativeSynthesis, situation_index: int) -> str:
    """Pull the title of a specific situation out of a stored synthesis blob."""
    data = synth.synthesis_data or {}
    situations = data.get("situations", []) if isinstance(data, dict) else []
    if 0 <= situation_index < len(situations):
        return situations[situation_index].get("title", "")
    return ""
