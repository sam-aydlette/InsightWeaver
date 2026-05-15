"""
InsightWeaver CLI Application
Click-based multi-command interface
"""

import contextlib
import time

import click

from .brief import brief_group
from .colors import accent, header, muted
from .decisions import decisions_command
from .diet import diet_command
from .forecast import forecast_command
from .frames import frames_command
from .output import set_debug_mode
from .predictions import predictions_command
from .questions import questions_command
from .sources import sources_command

# Maps command prefix to its Click command object.
# Order matters: longer prefixes checked first via startswith().
COMMAND_DISPATCH = {
    "brief": brief_group,
    "forecast": forecast_command,
    "frames": frames_command,
    "questions": questions_command,
    "predictions": predictions_command,
    "decisions": decisions_command,
    "diet": diet_command,
    "sources": sources_command,
}


def print_command_refresher():
    """Print a short refresher of available commands."""
    refresher = (
        f"\n{header('Commands:')} {accent('brief')} | {accent('forecast')} | "
        f"{accent('frames')} | {accent('questions')} | {accent('predictions')} | "
        f"{accent('decisions')} | {accent('diet')} | {accent('sources')} | "
        f"help | exit\n"
    )
    click.echo(refresher)


def print_help():
    """Print full help text for interactive mode."""
    click.echo(header("Available commands:"))
    click.echo(f"  {accent('brief')}               - Generate intelligence brief and report")
    click.echo(f"  {accent('forecast')}            - Generate long-term trend forecasts")
    click.echo(f"  {accent('frames')}              - Manage narrative frame glossary")
    click.echo(f"  {accent('questions')}           - Inspect the persistent question graph")
    click.echo(f"  {accent('predictions')}         - Inspect the predictions ledger")
    click.echo(f"  {accent('decisions')}           - Manage the decision journal")
    click.echo(f"  {accent('diet')}                - Inspect your information diet's structure")
    click.echo(f"  {accent('sources')}             - Per-source structural calibration")
    click.echo(f"  {accent('help')}                - Show this help message")
    click.echo(f"  {accent('exit')}                - Exit InsightWeaver")
    click.echo()
    click.echo(header("Brief command options:"))
    click.echo(f"  {accent('--hours N')}           - Look back N hours (default: 24)")
    click.echo(f"  {accent('--save PATH')}         - Save brief as markdown to PATH")
    click.echo(f"  {accent('--quiet')}             - Compact output (titles only)")
    click.echo(muted("  Topic filters:   --cybersecurity (-cs), --ai (-ai)"))
    click.echo(
        muted("  Scope filters:   --local (-l), --state (-s), --national (-n), --global (-g)")
    )
    click.echo()
    click.echo(header("Forecast command options:"))
    click.echo(f"  {accent('--horizon')} [6mo|1yr|3yr|5yr]  - Specific time horizon (default: all)")
    click.echo(
        f"  {accent('--scenarios N')}       - Number of detailed scenarios (0 = skip, 3 = standard)"
    )
    click.echo(
        f"  {accent('--full')}              - Show full detailed analysis (default: executive)"
    )
    click.echo(muted("  Same topic/scope filters as brief"))
    click.echo()
    click.echo(header("Frames command:"))
    click.echo(f"  {accent('frames list')}          - List all topic clusters and frames")
    click.echo(f"  {accent('frames show')} <topic>  - Show frames for a topic")
    click.echo(f"  {accent('frames edit')} <id>     - Edit a frame in $EDITOR")
    click.echo(f"  {accent('frames gaps')}          - Show recurring perspective gaps")
    click.echo()
    click.echo(header("Questions command:"))
    click.echo(f"  {accent('questions list')}         - List open (or resolved) questions")
    click.echo(f"  {accent('questions show')} <id>    - Show a question's full history")
    click.echo(f"  {accent('questions resolve')} <id> --note '...'  - Resolve a question")
    click.echo()
    click.echo(header("Predictions command:"))
    click.echo(f"  {accent('predictions open')}         - Predictions still waiting on coverage")
    click.echo(f"  {accent('predictions triggered')}    - Predictions later coverage confirmed")
    click.echo(f"  {accent('predictions contradicted')} - Predictions later coverage went against")
    click.echo(f"  {accent('predictions track-record')} - Rolling calibration record")
    click.echo()
    click.echo(header("Decisions command:"))
    click.echo(f"  {accent('decisions list')}            - List standing decisions")
    click.echo(f"  {accent('decisions show')} <id>       - Show factors and routed evidence")
    click.echo(f"  {accent('decisions add')} --name '...' --type ...  - Add a decision")
    click.echo(f"  {accent('decisions factor add')} <id> --name '...'  - Add a factor")
    click.echo(f"  {accent('decisions resolve')} <id> --note '...'  - Mark a decision decided")
    click.echo()
    click.echo(header("Diet command:"))
    click.echo(f"  {accent('diet feeds')}             - Per-feed frame fingerprint")
    click.echo(f"  {accent('diet gaps')}              - Recurring frame absences")
    click.echo(f"  {accent('diet overlap')}           - Which frames only one feed carries")
    click.echo()
    click.echo(header("Sources command:"))
    click.echo(f"  {accent('sources list')}             - All feeds with calibration signals")
    click.echo(f"  {accent('sources show')} <name>      - Detailed view for one feed")
    click.echo()
    click.echo(header("Examples:"))
    click.echo(muted("  brief                  (24-hour brief, all topics)"))
    click.echo(muted("  brief -cs -n           (national cybersecurity news)"))
    click.echo(muted("  brief --hours 48 -l    (48-hour local news brief)"))
    click.echo(muted("  brief --save brief.md  (save brief as markdown)"))
    click.echo(muted("  forecast               (multi-horizon forecasts, executive mode)"))
    click.echo(muted("  forecast --horizon 1yr --full  (1-year detailed forecast)"))
    click.echo(muted("  frames list            (view narrative frame glossary)"))
    click.echo(muted("  frames gaps            (view perspective gaps in your feeds)"))
    click.echo()
    click.echo(muted("Tip: Add --debug to any command to see detailed logs"))
    click.echo()


def _dispatch_command(command: str) -> bool:
    """
    Dispatch a user command to the appropriate Click command.

    Returns True if a command was matched, False otherwise.
    """
    for prefix, click_cmd in COMMAND_DISPATCH.items():
        if command.startswith(prefix):
            with contextlib.suppress(SystemExit):
                click_cmd.main(command.split()[1:], standalone_mode=False)
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
    InsightWeaver - Intelligent RSS Feed Analysis System

    Transform RSS feed data streams into coherent, actionable narratives
    through location-specific, integrated perspectives.
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
