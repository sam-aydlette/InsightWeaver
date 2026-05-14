"""
Decisions Command - Manage the decision journal and inspect routed evidence.
"""

from datetime import datetime

import click

from ..database.connection import get_db
from ..database.models import (
    DECISION_STATUS_DECIDED,
    DECISION_STATUS_OPEN,
    Decision,
    DecisionEvidence,
    DecisionFactor,
)
from .colors import accent, header, muted, success, warning

DECISION_TYPES = ["career", "housing", "education", "financial", "civic", "other"]


@click.group(name="decisions")
def decisions_command():
    """Manage standing decisions and the evidence routed into them."""
    pass


@decisions_command.command(name="list")
@click.option(
    "--status", "-s", type=click.Choice(["open", "decided", "deferred", "all"]), default="open"
)
def list_decisions(status):
    """List decisions with factor and evidence counts."""
    with get_db() as session:
        query = session.query(Decision)
        if status != "all":
            query = query.filter(Decision.status == status)
        rows = query.order_by(Decision.created_at.asc()).all()

        if not rows:
            click.echo(muted(f"No {status} decisions. Add one with 'decisions add'."))
            return

        click.echo(header(f"DECISIONS ({status}, {len(rows)} shown)"))
        click.echo("=" * 80)
        for d in rows:
            factor_count = session.query(DecisionFactor).filter_by(decision_id=d.id).count()
            evidence_count = session.query(DecisionEvidence).filter_by(decision_id=d.id).count()
            tag = success("open") if d.status == DECISION_STATUS_OPEN else muted(d.status)
            click.echo(f"{accent(f'D{d.id}')}  [{tag}]  {muted(d.decision_type or 'other')}")
            click.echo(f"  {d.name}")
            click.echo(muted(f"  {factor_count} factor(s) | {evidence_count} evidence record(s)"))
            click.echo()


@decisions_command.command(name="show")
@click.argument("decision_id", type=int)
def show_decision(decision_id):
    """Show a decision, its factors, and routed evidence per factor."""
    with get_db() as session:
        d = session.query(Decision).filter_by(id=decision_id).first()
        if not d:
            click.echo(warning(f"Decision D{decision_id} not found."))
            return

        click.echo(header(f"DECISION D{d.id}"))
        click.echo("=" * 80)
        click.echo(d.name)
        click.echo()
        click.echo(muted(f"Type: {d.decision_type or 'other'} | Status: {d.status}"))
        click.echo(muted(f"Created: {d.created_at.date().isoformat()}"))
        if d.decided_at:
            click.echo(muted(f"Decided: {d.decided_at.date().isoformat()}"))
        if d.notes:
            click.echo(muted(f"Notes: {d.notes}"))
        click.echo()

        factors = session.query(DecisionFactor).filter_by(decision_id=d.id).all()
        if not factors:
            click.echo(muted("No factors yet. Add one with 'decisions factor add'."))
            return

        for f in factors:
            click.echo(header(f"Factor F{f.id}: {f.name}"))
            if f.what_would_update_me:
                click.echo(muted(f"  Would update me: {f.what_would_update_me}"))
            evidence = (
                session.query(DecisionEvidence)
                .filter_by(factor_id=f.id)
                .order_by(DecisionEvidence.observed_at.asc())
                .all()
            )
            if not evidence:
                click.echo(muted("  No evidence routed yet."))
            for ev in evidence:
                status_tag = f" [{ev.epistemic_status}]" if ev.epistemic_status else ""
                click.echo(
                    f"  {accent(ev.direction)} {ev.observed_at.date().isoformat()}"
                    f"{muted(status_tag)}"
                )
                click.echo(f"    {ev.situation_excerpt}")
            click.echo()


@decisions_command.command(name="add")
@click.option("--name", required=True, help="What the decision is.")
@click.option(
    "--type",
    "decision_type",
    type=click.Choice(DECISION_TYPES),
    default="other",
    help="Decision category.",
)
def add_decision(name, decision_type):
    """Add a new standing decision."""
    with get_db() as session:
        decision = Decision(name=name, decision_type=decision_type)
        session.add(decision)
        session.commit()
        click.echo(success(f"Added decision D{decision.id}: {name}"))


@decisions_command.command(name="resolve")
@click.argument("decision_id", type=int)
@click.option("--note", required=True, help="What you decided and why.")
def resolve_decision(decision_id, note):
    """Mark a decision decided with a note."""
    with get_db() as session:
        d = session.query(Decision).filter_by(id=decision_id).first()
        if not d:
            click.echo(warning(f"Decision D{decision_id} not found."))
            return
        if d.status != DECISION_STATUS_OPEN:
            click.echo(warning(f"D{d.id} is already {d.status}; not modifying."))
            return
        d.status = DECISION_STATUS_DECIDED
        d.decided_at = datetime.utcnow()
        d.notes = note
        session.commit()
        click.echo(success(f"D{d.id} marked decided."))


@decisions_command.group(name="factor")
def factor_group():
    """Manage the factors tracked for a decision."""
    pass


@factor_group.command(name="add")
@click.argument("decision_id", type=int)
@click.option("--name", required=True, help="What the factor is.")
@click.option(
    "--update-when",
    "what_would_update_me",
    default=None,
    help="Your rule for what evidence would change your read.",
)
def add_factor(decision_id, name, what_would_update_me):
    """Add a factor to a decision."""
    with get_db() as session:
        d = session.query(Decision).filter_by(id=decision_id).first()
        if not d:
            click.echo(warning(f"Decision D{decision_id} not found."))
            return
        factor = DecisionFactor(
            decision_id=d.id, name=name, what_would_update_me=what_would_update_me
        )
        session.add(factor)
        session.commit()
        click.echo(success(f"Added factor F{factor.id} to D{d.id}: {name}"))
