"""
InsightWeaver CLI Application
Click-based multi-command interface
"""
import click
from .brief import brief_group
from .trust import trust_command
from .forecast import forecast_command
from .output import set_debug_mode


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
    click.echo(ASCII_ART)
    click.echo()
    click.echo("Welcome to InsightWeaver - Transform Data Into Trustworthy Insight.")
    click.echo()
    click.echo("Available commands:")
    click.echo("  brief               - Generate intelligence brief and report")
    click.echo("  trust [query]       - Get trust-verified AI responses")
    click.echo("  forecast            - Generate long-term trend forecasts")
    click.echo("  help                - Show this help message")
    click.echo("  exit                - Exit InsightWeaver")
    click.echo()
    click.echo("Brief command options:")
    click.echo("  --hours N           - Look back N hours (default: 24)")
    click.echo("  --email             - Send report via email (in addition to saving)")
    click.echo("  --no-verify         - Skip trust verification of AI output")
    click.echo("  Topic filters:   --cybersecurity (-cs), --ai (-ai)")
    click.echo("  Scope filters:   --local (-l), --state (-s), --national (-n), --global (-g)")
    click.echo()
    click.echo("Forecast command options:")
    click.echo("  --horizon [6mo|1yr|3yr|5yr]  - Specific time horizon (default: all)")
    click.echo("  --scenarios N       - Number of detailed scenarios (0 = skip, 3 = standard)")
    click.echo("  --full              - Show full detailed analysis (default: executive)")
    click.echo("  --no-verify         - Skip trust verification of AI output")
    click.echo("  Same topic/scope filters as brief")
    click.echo()
    click.echo("Trust command:")
    click.echo("  trust \"your question\"  - Get AI response with fact-checking, bias")
    click.echo("                           analysis, and tone verification")
    click.echo()
    click.echo("Examples:")
    click.echo("  brief                  (24-hour brief, all topics)")
    click.echo("  brief -cs -n           (national cybersecurity news)")
    click.echo("  brief --hours 48 -l    (48-hour local news brief)")
    click.echo("  brief --no-verify      (skip trust verification)")
    click.echo("  forecast               (multi-horizon forecasts, executive mode)")
    click.echo("  forecast --horizon 1yr --full  (1-year detailed forecast)")
    click.echo("  forecast -cs --scenarios 3     (cybersecurity trends with scenarios)")
    click.echo("  trust \"Who is the president?\"  (verified factual response)")
    click.echo()
    click.echo("Tip: Add --debug to any command to see detailed logs")
    click.echo()

    while True:
        try:
            command = click.prompt("insightweaver", type=str, prompt_suffix=" > ")
            command = command.strip()

            if command in ['exit', 'quit', 'q']:
                click.echo("Thank you for using InsightWeaver!")
                break
            elif command in ['help', '?']:
                click.echo("\nAvailable commands:")
                click.echo("  brief               - Generate intelligence brief and report")
                click.echo("  trust [query]       - Get trust-verified AI responses")
                click.echo("  forecast            - Generate long-term trend forecasts")
                click.echo("  help                - Show this help message")
                click.echo("  exit                - Exit InsightWeaver")
                click.echo()
                click.echo("Brief command options:")
                click.echo("  --hours N           - Look back N hours (default: 24)")
                click.echo("  --email             - Send report via email (in addition to saving)")
                click.echo("  --no-verify         - Skip trust verification of AI output")
                click.echo("  Topic filters:   --cybersecurity (-cs), --ai (-ai)")
                click.echo("  Scope filters:   --local (-l), --state (-s), --national (-n), --global (-g)")
                click.echo()
                click.echo("Forecast command options:")
                click.echo("  --horizon [6mo|1yr|3yr|5yr]  - Specific time horizon (default: all)")
                click.echo("  --scenarios N       - Number of detailed scenarios (0 = skip, 3 = standard)")
                click.echo("  --full              - Show full detailed analysis (default: executive)")
                click.echo("  --no-verify         - Skip trust verification of AI output")
                click.echo("  Same topic/scope filters as brief")
                click.echo()
                click.echo("Trust command:")
                click.echo("  trust \"your question\"  - Get AI response with fact-checking, bias")
                click.echo("                           analysis, and tone verification")
                click.echo()
                click.echo("Examples:")
                click.echo("  brief                  (24-hour brief, all topics)")
                click.echo("  brief -cs -n           (national cybersecurity news)")
                click.echo("  brief --hours 48 -l    (48-hour local news brief)")
                click.echo("  brief --no-verify      (skip trust verification)")
                click.echo("  forecast               (multi-horizon forecasts, executive mode)")
                click.echo("  forecast --horizon 1yr --full  (1-year detailed forecast)")
                click.echo("  forecast -cs --scenarios 3     (cybersecurity trends with scenarios)")
                click.echo("  trust \"Who is the president?\"  (verified factual response)")
                click.echo()
                click.echo("Tip: Add --debug to any command to see detailed logs")
                click.echo()
            elif command.startswith('brief'):
                # Parse command and invoke brief group
                try:
                    brief_group.main(command.split()[1:], standalone_mode=False)
                except SystemExit:
                    pass
            elif command.startswith('trust'):
                # Parse command and invoke trust command
                try:
                    trust_command.main(command.split()[1:], standalone_mode=False)
                except SystemExit:
                    pass
            elif command.startswith('forecast'):
                # Parse command and invoke forecast command
                try:
                    forecast_command.main(command.split()[1:], standalone_mode=False)
                except SystemExit:
                    pass
            elif command == '':
                continue
            else:
                click.echo(f"Unknown command: {command}")
                click.echo("Type 'help' for available commands or 'exit' to quit.")
        except (KeyboardInterrupt, EOFError):
            click.echo("\nThank you for using InsightWeaver!")
            break
        except Exception as e:
            click.echo(f"Error: {str(e)}")


@click.group(invoke_without_command=True)
@click.pass_context
@click.option('--debug', is_flag=True, help='Enable debug mode (show logs and detailed output)')
@click.version_option(version="1.0.0", prog_name="InsightWeaver")
def cli(ctx, debug):
    """
    InsightWeaver - Intelligent RSS Feed Analysis System

    Transform RSS feed data streams into coherent, actionable narratives
    through location-specific, integrated perspectives.
    """
    set_debug_mode(debug)
    ctx.ensure_object(dict)
    ctx.obj['DEBUG'] = debug

    if ctx.invoked_subcommand is None:
        interactive_mode()


# Register commands
cli.add_command(brief_group, name="brief")
cli.add_command(trust_command, name="trust")
cli.add_command(forecast_command, name="forecast")


if __name__ == "__main__":
    cli()
