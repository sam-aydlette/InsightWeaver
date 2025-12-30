"""
InsightWeaver CLI Application
Click-based multi-command interface
"""
import click
import sys
from .brief import brief_group
from .trust import trust_command


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
    ║       ~  Transform Data into Trustworthy Insight  ~      ║
    ║                                                          ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
"""


def interactive_mode():
    """Run InsightWeaver in interactive mode."""
    click.echo(ASCII_ART)
    click.echo()
    click.echo("Welcome to InsightWeaver - Your intelligent RSS analysis companion.")
    click.echo()
    click.echo("Available commands:")
    click.echo("  brief    - Generate and manage daily briefs")
    click.echo("  trust    - Build and analyze your trusted source network")
    click.echo("  help     - Show this help message")
    click.echo("  exit     - Exit InsightWeaver")
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
                click.echo("  brief    - Generate and manage daily briefs")
                click.echo("  trust    - Build and analyze your trusted source network")
                click.echo("  help     - Show this help message")
                click.echo("  exit     - Exit InsightWeaver")
                click.echo()
            elif command.startswith('brief'):
                args = command.split()[1:] if len(command.split()) > 1 else []
                ctx = click.Context(cli)
                ctx.invoke(brief_group, args)
            elif command.startswith('trust'):
                args = command.split()[1:] if len(command.split()) > 1 else []
                ctx = click.Context(cli)
                ctx.invoke(trust_command, args)
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
@click.version_option(version="1.0.0", prog_name="InsightWeaver")
def cli(ctx):
    """
    InsightWeaver - Intelligent RSS Feed Analysis System

    Transform RSS feed data streams into coherent, actionable narratives
    through location-specific, integrated perspectives.
    """
    if ctx.invoked_subcommand is None:
        interactive_mode()


# Register commands
cli.add_command(brief_group, name="brief")
cli.add_command(trust_command, name="trust")


if __name__ == "__main__":
    cli()
