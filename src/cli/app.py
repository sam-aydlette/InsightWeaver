"""
InsightWeaver CLI application.

Backlog task 012 deleted the briefing product, and with it every command that
generated, rendered, or reasoned over a brief: brief, frames, diet, questions,
predictions, forecast, decisions, beat, stake and scope. What is left is the
source layer, which the rewrite keeps.

The command table is deliberately short. It is not a placeholder for the new
pipeline -- building that is a separate task -- and nothing here should grow a
command back by habit.
"""

import contextlib
import shlex
import time

import click

from .colors import accent, header, muted
from .output import set_debug_mode
from .replay import replay_command
from .route import route_command
from .sources import sources_command
from .watch import watch_command

# Maps command prefix to its Click command object.
#
# Order used to matter here: "predictions" had to precede "predict", since the
# shorter name is a prefix of the longer one (2026-08-27, backlog task 011).
# Both commands are gone, but the startswith() dispatch below is unchanged, so
# the ordering constraint still applies to whatever is added next.
COMMAND_DISPATCH = {
    "sources": sources_command,
    "watch": watch_command,
    "replay": replay_command,
    "route": route_command,
}


def print_command_refresher():
    """Print a short refresher of available commands."""
    click.echo(
        f"\n{header('Commands:')} {accent('sources')} | {accent('watch')} | "
        f"{accent('route')} | {accent('replay')} | help | exit\n"
    )


def print_help():
    """Print full help text for interactive mode."""
    click.echo(header("Available commands:"))
    click.echo(f"  {accent('sources')}             - Inspect configured feeds and what they hold")
    click.echo(
        f"  {accent('watch')}               - Pre-registered watches and the decisions they serve"
    )
    click.echo(
        f"  {accent('route')}               - Match Observations to Watches, deterministically"
    )
    click.echo(
        f"  {accent('replay')}              - Rebuild Evidence from Observations and diff it"
    )
    click.echo(f"  {accent('help')}                - Show this help message")
    click.echo(f"  {accent('exit')}                - Exit InsightWeaver")
    click.echo()
    click.echo(header("Sources command:"))
    click.echo(f"  {accent('sources list')}             - All feeds with stored-article counts")
    click.echo(f"  {accent('sources show')} <name>      - Detailed view for one feed")
    click.echo()
    click.echo(header("Watch command:"))
    click.echo(
        f"  {accent('watch list')}               - Each watch, belief, decision, days to expiry"
    )
    click.echo(
        f"  {accent('watch sync')}               - Load the hand-authored Position and watch files"
    )
    click.echo(
        muted("  Watches are only ever created from those files -- there is no 'watch add'.")
    )
    click.echo()
    click.echo(header("Route command:"))
    click.echo(f"  {accent('route --dry-run')}         - Per watch, how many of the last N route")
    click.echo(muted("  Reports the unrouted count and its clusters -- the coverage-gap signal."))
    click.echo(muted("  No model is involved anywhere in this tier."))
    click.echo()
    click.echo(header("Replay command:"))
    click.echo(f"  {accent('replay --prompt-version X')}  - Rebuild Evidence for prompt version X")
    click.echo(
        muted("  Prints the diff against stored Evidence and writes nothing. --commit persists.")
    )
    click.echo()
    click.echo(muted("Tip: Add --debug to any command to see detailed logs"))
    click.echo()


def _dispatch_command(command: str) -> bool:
    """
    Dispatch a user command to the appropriate Click command.

    Returns True if a command was matched, False otherwise.

    Argument splitting is quote-aware (shlex) as of 2026-08-27: an option that
    takes prose needs its value delivered as one argument, and a plain
    whitespace split would hand Click several instead.
    """
    for prefix, click_cmd in COMMAND_DISPATCH.items():
        if command.startswith(prefix):
            try:
                args = shlex.split(command)[1:]
            except ValueError as exc:
                from .colors import error as err_style

                click.echo(err_style(f"Could not read that command: {exc}"))
                print_command_refresher()
                return True
            with contextlib.suppress(SystemExit):
                try:
                    click_cmd.main(args, standalone_mode=False)
                except click.ClickException as exc:
                    # standalone_mode=False re-raises instead of printing, so
                    # the rejection has to be shown here to reach the operator.
                    exc.show()
            print_command_refresher()
            return True
    return False


ASCII_ART = r"""
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║    ██╗███╗   ██╗███████╗██╗ ██████╗ ██╗  ██╗████████╗    ║
    ║    ██║████╗  ██║██╔════╝██║██╔════╝ ██║  ██║╚══██╔══╝    ║
    ║    ██║██╔██╗ ██║███████╗██║██║  ███╗███████║   ██║       ║
    ║    ██║██║╚██╗██║╚════██║██║██║   ██║██╔══██║   ██║       ║
    ║    ██║██║ ╚████║███████║██║╚██████╔╝██║  ██║   ██║       ║
    ║    ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝       ║
    ║                                                          ║
    ║    ██╗    ██╗███████╗ █████╗ ██╗   ██╗███████╗██████╗    ║
    ║    ██║    ██║██╔════╝██╔══██╗██║   ██║██╔════╝██╔══██╗   ║
    ║    ██║ █╗ ██║█████╗  ███████║██║   ██║█████╗  ██████╔╝   ║
    ║    ██║███╗██║██╔══╝  ██╔══██║╚██╗ ██╔╝██╔══╝  ██╔══██╗   ║
    ║    ╚███╔███╔╝███████╗██║  ██║ ╚████╔╝ ███████╗██║  ██║   ║
    ║     ╚══╝╚══╝ ╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝   ║
    ║                                                          ║
    ║       ~  Transform Data Into Trustworthy Insight  ~      ║
    ║                                                          ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
"""


def interactive_mode():
    """Run InsightWeaver in interactive mode."""
    click.echo(accent(ASCII_ART))
    click.echo()
    click.echo(header("Welcome to InsightWeaver") + " - Transform Data Into Trustworthy Insight.")
    click.echo()

    # Pause to let user see the ASCII art and slogan
    time.sleep(2.5)

    print_help()

    while True:
        try:
            command = click.prompt("insightweaver", type=str, prompt_suffix=" > ")
            command = command.strip()

            if command in ("exit", "quit", "q"):
                click.echo("Thank you for using InsightWeaver!")
                break
            elif command in ("help", "?"):
                click.echo()
                print_help()
            elif command == "":
                continue
            elif not _dispatch_command(command):
                from .colors import error as err_style
                from .colors import warning as warn_style

                click.echo(err_style(f"Unknown command: {command}"))
                click.echo(warn_style("Type 'help' for available commands or 'exit' to quit."))
        except (KeyboardInterrupt, EOFError):
            click.echo(accent("\nThank you for using InsightWeaver!"))
            break
        except Exception as e:
            from .colors import error as err_style

            click.echo(err_style(f"Error: {str(e)}"))


@click.group(invoke_without_command=True)
@click.pass_context
@click.option("--debug", is_flag=True, help="Enable debug mode (show logs and detailed output)")
@click.version_option(version="1.0.0", prog_name="InsightWeaver")
def cli(ctx, debug):
    """
    InsightWeaver - monitoring against pre-registered watches.

    The briefing product was removed in backlog task 012. What remains is
    ingestion, the source layer, and the Position/Watch units added by task 013.
    """
    set_debug_mode(debug)
    ctx.ensure_object(dict)
    ctx.obj["DEBUG"] = debug

    if ctx.invoked_subcommand is None:
        interactive_mode()


# Register commands
for name, cmd in COMMAND_DISPATCH.items():
    cli.add_command(cmd, name=name)


if __name__ == "__main__":
    cli()
