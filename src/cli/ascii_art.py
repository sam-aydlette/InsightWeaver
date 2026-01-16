"""
ASCII art for CLI commands
Hacker aesthetic visual identifiers for each command
"""

import sys

from .colors import accent, header


def _is_tty() -> bool:
    """Check if running in an interactive terminal"""
    return sys.stdout.isatty()


def render_brief_art(status: str = "Analyzing the signal...") -> str:
    """
    Render ASCII art for the brief command - Intelligence Analyst figure

    Args:
        status: Status message to display next to the art

    Returns:
        Formatted ASCII art string with colors
    """
    title = "INTELLIGENCE BRIEF"
    underline = "=" * len(title)

    # Build art line by line to avoid escaping issues
    lines = [
        "",
        "        " + accent("___"),
        "       " + accent("/   \\"),
        "      " + accent("| O O |"),
        "       " + accent("\\ - /") + "     " + header(title),
        "      " + accent("/|   |\\") + "    " + header(underline),
        "     " + accent("/ |   | \\") + "   " + status,
        "    " + accent("/  |___|  \\"),
        "",
    ]
    return "\n".join(lines)


def render_forecast_art(status: str = "Gazing into the future...") -> str:
    """
    Render ASCII art for the forecast command - Crystal Ball

    Args:
        status: Status message to display next to the art

    Returns:
        Formatted ASCII art string with colors
    """
    title = "FORECAST"
    underline = "=" * len(title)

    lines = [
        "",
        "         " + accent(".-."),
        "        " + accent("(   )"),
        "       " + accent("/`   `\\") + "    " + header(title),
        "      " + accent("|  ___  |") + "   " + header(underline),
        "      " + accent("| (   ) |") + "   " + status,
        "       " + accent("\\`---'/"),
        "        " + accent("`---'"),
        "",
    ]
    return "\n".join(lines)


def render_trust_art(status: str = "Verifying response...") -> str:
    """
    Render ASCII art for the trust command - Shield

    Args:
        status: Status message to display next to the art

    Returns:
        Formatted ASCII art string with colors
    """
    title = "TRUST VERIFICATION"
    underline = "=" * len(title)

    lines = [
        "",
        "       " + accent("/\\"),
        "      " + accent("/  \\"),
        "     " + accent("/ == \\") + "     " + header(title),
        "    " + accent("/======\\") + "    " + header(underline),
        "    " + accent("\\======/") + "    " + status,
        "     " + accent("\\    /"),
        "      " + accent("\\  /"),
        "       " + accent("\\/"),
        "",
    ]
    return "\n".join(lines)


def should_show_art(quiet: bool = False) -> bool:
    """
    Determine if ASCII art should be displayed

    Args:
        quiet: User-specified quiet mode flag

    Returns:
        True if art should be shown, False otherwise
    """
    if quiet:
        return False
    return _is_tty()
