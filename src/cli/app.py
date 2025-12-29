"""
InsightWeaver CLI Application
Click-based multi-command interface
"""
import click
from .brief import brief_group
# trust command will be added in Stage 2
# from .trust import trust_command


@click.group()
@click.version_option(version="1.0.0", prog_name="InsightWeaver")
def cli():
    """
    InsightWeaver - Intelligent RSS Feed Analysis System

    Transform RSS feed data streams into coherent, actionable narratives
    through location-specific, integrated perspectives.
    """
    pass


# Register commands
cli.add_command(brief_group, name="brief")
# Stage 2: cli.add_command(trust_command, name="trust")


if __name__ == "__main__":
    cli()
