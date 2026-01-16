"""
InsightWeaver CLI Application
Click-based multi-command interface
"""

import os
import time
import webbrowser

import click

from .brief import brief_group
from .colors import accent, header, muted
from .forecast import forecast_command
from .output import set_debug_mode
from .trust import trust_command


def print_command_refresher():
    """Print a short refresher of available commands."""
    refresher = (
        f'\n{header("Commands:")} {accent("brief")} | {accent("trust")} "query" | '
        f"{accent('forecast')} | help | exit\n"
    )
    click.echo(refresher)


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

    click.echo(header("Available commands:"))
    click.echo(f"  {accent('brief')}               - Generate intelligence brief and report")
    click.echo(f"  {accent('trust')} [query]       - Get trust-verified AI responses")
    click.echo(f"  {accent('forecast')}            - Generate long-term trend forecasts")
    click.echo(f"  {accent('help')}                - Show this help message")
    click.echo(f"  {accent('exit')}                - Exit InsightWeaver")
    click.echo()
    click.echo(header("Brief command options:"))
    click.echo(f"  {accent('--hours N')}           - Look back N hours (default: 24)")
    click.echo(f"  {accent('--email')}             - Send report via email (in addition to saving)")
    click.echo(f"  {accent('--no-verify')}         - Skip trust verification of AI output")
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
    click.echo(f"  {accent('--no-verify')}         - Skip trust verification of AI output")
    click.echo(muted("  Same topic/scope filters as brief"))
    click.echo()
    click.echo(header("Trust command:"))
    click.echo(f'  {accent("trust")} "your question"  - Get AI response with fact-checking, bias')
    click.echo("                           analysis, and tone verification")
    click.echo()
    click.echo(header("Examples:"))
    click.echo(muted("  brief                  (24-hour brief, all topics)"))
    click.echo(muted("  brief -cs -n           (national cybersecurity news)"))
    click.echo(muted("  brief --hours 48 -l    (48-hour local news brief)"))
    click.echo(muted("  brief --no-verify      (skip trust verification)"))
    click.echo(muted("  forecast               (multi-horizon forecasts, executive mode)"))
    click.echo(muted("  forecast --horizon 1yr --full  (1-year detailed forecast)"))
    click.echo(muted("  forecast -cs --scenarios 3     (cybersecurity trends with scenarios)"))
    click.echo(muted('  trust "Who is the president?"  (verified factual response)'))
    click.echo()
    click.echo(muted("Tip: Add --debug to any command to see detailed logs"))
    click.echo()

    while True:
        try:
            command = click.prompt("insightweaver", type=str, prompt_suffix=" > ")
            command = command.strip()

            if command in ["exit", "quit", "q"]:
                click.echo("Thank you for using InsightWeaver!")
                break
            elif command in ["help", "?"]:
                click.echo()
                click.echo(header("Available commands:"))
                click.echo(
                    f"  {accent('brief')}               - Generate intelligence brief and report"
                )
                click.echo(f"  {accent('trust')} [query]       - Get trust-verified AI responses")
                click.echo(
                    f"  {accent('forecast')}            - Generate long-term trend forecasts"
                )
                click.echo(f"  {accent('help')}                - Show this help message")
                click.echo(f"  {accent('exit')}                - Exit InsightWeaver")
                click.echo()
                click.echo(header("Brief command options:"))
                click.echo(f"  {accent('--hours N')}           - Look back N hours (default: 24)")
                click.echo(
                    f"  {accent('--email')}             - Send report via email (in addition to saving)"
                )
                click.echo(
                    f"  {accent('--no-verify')}         - Skip trust verification of AI output"
                )
                click.echo(muted("  Topic filters:   --cybersecurity (-cs), --ai (-ai)"))
                click.echo(
                    muted(
                        "  Scope filters:   --local (-l), --state (-s), --national (-n), --global (-g)"
                    )
                )
                click.echo()
                click.echo(header("Forecast command options:"))
                click.echo(
                    f"  {accent('--horizon')} [6mo|1yr|3yr|5yr]  - Specific time horizon (default: all)"
                )
                click.echo(
                    f"  {accent('--scenarios N')}       - Number of detailed scenarios (0 = skip, 3 = standard)"
                )
                click.echo(
                    f"  {accent('--full')}              - Show full detailed analysis (default: executive)"
                )
                click.echo(
                    f"  {accent('--no-verify')}         - Skip trust verification of AI output"
                )
                click.echo(muted("  Same topic/scope filters as brief"))
                click.echo()
                click.echo(header("Trust command:"))
                click.echo(
                    f'  {accent("trust")} "your question"  - Get AI response with fact-checking, bias'
                )
                click.echo("                           analysis, and tone verification")
                click.echo()
                click.echo(header("Examples:"))
                click.echo(muted("  brief                  (24-hour brief, all topics)"))
                click.echo(muted("  brief -cs -n           (national cybersecurity news)"))
                click.echo(muted("  brief --hours 48 -l    (48-hour local news brief)"))
                click.echo(muted("  brief --no-verify      (skip trust verification)"))
                click.echo(
                    muted("  forecast               (multi-horizon forecasts, executive mode)")
                )
                click.echo(muted("  forecast --horizon 1yr --full  (1-year detailed forecast)"))
                click.echo(
                    muted("  forecast -cs --scenarios 3     (cybersecurity trends with scenarios)")
                )
                click.echo(muted('  trust "Who is the president?"  (verified factual response)'))
                click.echo()
                click.echo(muted("Tip: Add --debug to any command to see detailed logs"))
                click.echo()
            elif command.startswith("brief"):
                # Parse command and invoke brief group
                try:  # noqa: SIM105
                    brief_group.main(command.split()[1:], standalone_mode=False)
                except SystemExit:
                    pass
                print_command_refresher()
            elif command.startswith("trust"):
                # Parse command and invoke trust command
                try:  # noqa: SIM105
                    trust_command.main(command.split()[1:], standalone_mode=False)
                except SystemExit:
                    pass
                print_command_refresher()
            elif command.startswith("forecast"):
                # Parse command and invoke forecast command
                try:  # noqa: SIM105
                    forecast_command.main(command.split()[1:], standalone_mode=False)
                except SystemExit:
                    pass
                print_command_refresher()
            elif command == "":
                continue
            else:
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
cli.add_command(brief_group, name="brief")
cli.add_command(trust_command, name="trust")
cli.add_command(forecast_command, name="forecast")


@cli.command()
@click.option("--port", default=5000, help="Port to run the server on")
def setup(port):
    """Launch the web-based setup wizard."""
    click.echo(header("InsightWeaver Setup"))
    click.echo()
    click.echo("Starting setup wizard...")
    click.echo()

    # Check if profile already exists
    config_dir = os.path.expanduser("~/.insightweaver")
    profile_path = os.path.join(config_dir, "user_profile.json")

    if os.path.exists(profile_path):
        click.echo(muted("A profile already exists. The wizard will let you review it."))
        click.echo()

    # Start web server with setup route
    from src.web.server import create_app

    app = create_app()
    url = f"http://localhost:{port}/setup"

    click.echo(f"Opening {accent(url)} in your browser...")
    click.echo(muted("Press Ctrl+C to stop the server."))
    click.echo()

    # Open browser after a short delay
    import threading

    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    # Run the server
    app.run(host="127.0.0.1", port=port, debug=False)


@cli.command()
@click.option("--port", default=5000, help="Port to run the server on")
@click.option("--no-browser", is_flag=True, help="Don't open browser automatically")
def start(port, no_browser):
    """Start the InsightWeaver web interface."""
    click.echo(header("InsightWeaver Web Interface"))
    click.echo()

    # Check if setup is complete
    config_dir = os.path.expanduser("~/.insightweaver")
    profile_path = os.path.join(config_dir, "user_profile.json")

    if not os.path.exists(profile_path):
        click.echo("No profile found. Running setup wizard first...")
        click.echo()
        from src.web.server import create_app

        app = create_app()
        url = f"http://localhost:{port}/setup"
    else:
        from src.web.server import create_app

        app = create_app()
        url = f"http://localhost:{port}"

    click.echo(f"Server running at {accent(url)}")
    click.echo(muted("Press Ctrl+C to stop the server."))
    click.echo()

    # Open browser after a short delay
    if not no_browser:
        import threading

        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    # Run the server
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    cli()
