"""
InsightWeaver CLI application.

Backlog task 012 deleted the briefing product, and with it every command that
generated, rendered, or reasoned over a brief: brief, frames, diet, questions,
predictions, forecast, decisions, beat, stake and scope. What is left is the
source layer, which the rewrite keeps.

The REPL (an ASCII-art banner, a 2.5-second sleep, and a prefix dispatcher over
a raw input loop) was removed on 2026-09-22 (backlog task 027): a scripted,
idempotent command has no use for a banner, a sleep or a prefix dispatcher.
Invoking ``insightweaver`` with no subcommand now prints the group's help and
exits.

The command table grows one task at a time as the decision monitor lands
(``docs/PLAN.md`` section 4): ``ingest`` and ``route`` on 2026-09-22 (backlog
task 028). Nothing here should grow a command back by habit.
"""

import click

from .auth import auth
from .ingest import ingest_command
from .output import set_debug_mode
from .replay import replay_command
from .route import route_command
from .sources import sources_command
from .watch import watch_command


@click.group(invoke_without_command=True)
@click.pass_context
@click.option("--debug", is_flag=True, help="Enable debug mode (show logs and detailed output)")
@click.version_option(version="1.0.0", prog_name="InsightWeaver")
def cli(ctx, debug):
    """
    InsightWeaver - monitoring against pre-registered watches.

    Ingest sources and route observations to pre-registered watches. The
    briefing product was removed in backlog task 012; adjudication and the
    brief are the next tasks in docs/PLAN.md.
    """
    set_debug_mode(debug)
    ctx.ensure_object(dict)
    ctx.obj["DEBUG"] = debug

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)


# Register commands, in the order a morning runs them.
cli.add_command(auth, name="auth")
cli.add_command(sources_command, name="sources")
cli.add_command(ingest_command, name="ingest")
cli.add_command(watch_command, name="watch")
cli.add_command(route_command, name="route")
cli.add_command(replay_command, name="replay")


if __name__ == "__main__":
    cli()
