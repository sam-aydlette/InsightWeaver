"""
Run command - the morning, in order: ingest, route, adjudicate, brief.

Each step is the same command the operator could run by hand, invoked in
process with its defaults, and the run stops at the first that fails with a
non-zero exit. A step that succeeds while reporting a problem -- an
unreachable source, a failed adjudication -- does not stop the run, because
the brief is where those are read. Nothing here is a scheduler; it is one
command that saves typing four.

Added 2026-09-22 for backlog task 031.
"""

from __future__ import annotations

import click

from .adjudicate import adjudicate_command
from .brief import brief_command
from .ingest import ingest_command
from .route import route_command

STEPS = (
    ("ingest", ingest_command),
    ("route", route_command),
    ("adjudicate", adjudicate_command),
    ("brief", brief_command),
)


@click.command(name="run")
@click.pass_context
def run_command(ctx: click.Context) -> None:
    """Ingest, route, adjudicate and render the brief, stopping at the first failure."""
    for name, command in STEPS:
        click.echo(f"==> {name}")
        try:
            ctx.invoke(command)
        except click.ClickException as exc:
            raise click.ClickException(f"{name}: {exc.format_message()}")
        click.echo()
