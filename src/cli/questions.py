"""
Questions Command - Inspect and manage the persistent Question graph.
"""

from datetime import datetime

import click

from ..database.connection import get_db
from ..database.models import (
    QUESTION_STATUS_OPEN,
    QUESTION_STATUS_RESOLVED,
    NarrativeSynthesis,
    Question,
    QuestionSituation,
)
from .colors import accent, header, muted, success, warning


@click.group(name="questions")
def questions_command():
    """Inspect and manage the persistent question graph."""
    pass


@questions_command.command(name="list")
@click.option("--status", "-s", type=click.Choice(["open", "resolved", "all"]), default="open")
@click.option("--limit", "-n", type=int, default=50)
def list_questions(status, limit):
    """List questions, oldest open first by default."""
    with get_db() as session:
        query = session.query(Question)
        if status != "all":
            query = query.filter(Question.status == status)

        if status == QUESTION_STATUS_OPEN:
            query = query.order_by(Question.first_asked_at.asc())
        else:
            query = query.order_by(Question.first_asked_at.desc())

        rows = query.limit(limit).all()

        if not rows:
            click.echo(muted(f"No {status} questions."))
            return

        click.echo(header(f"QUESTIONS ({status}, {len(rows)} shown)"))
        click.echo("=" * 80)
        now = datetime.utcnow()
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
    """Show a question's full history across runs."""
    with get_db() as session:
        q = session.query(Question).filter_by(id=question_id).first()
        if not q:
            click.echo(warning(f"Question Q{question_id} not found."))
            return

        click.echo(header(f"QUESTION Q{q.id}"))
        click.echo("=" * 80)
        click.echo(q.text)
        click.echo()
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
    """Mark a question resolved with a note."""
    with get_db() as session:
        q = session.query(Question).filter_by(id=question_id).first()
        if not q:
            click.echo(warning(f"Question Q{question_id} not found."))
            return
        if q.status != QUESTION_STATUS_OPEN:
            click.echo(warning(f"Q{q.id} is already {q.status}; not modifying."))
            return

        q.status = QUESTION_STATUS_RESOLVED
        q.resolved_at = datetime.utcnow()
        q.resolution_note = note
        session.commit()

        click.echo(success(f"Q{q.id} resolved."))


def _situation_title(synth: NarrativeSynthesis, situation_index: int) -> str:
    """Pull the title of a specific situation out of a stored synthesis blob."""
    data = synth.synthesis_data or {}
    situations = data.get("situations", []) if isinstance(data, dict) else []
    if 0 <= situation_index < len(situations):
        return situations[situation_index].get("title", "")
    return ""
