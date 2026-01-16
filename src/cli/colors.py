"""
Terminal color palette - hacker aesthetic
Centralized color definitions for consistent CLI styling
"""

import click

# Color constants
ACCENT = "bright_green"
HEADER = "cyan"
SUCCESS = "green"
WARNING = "yellow"
ERROR = "red"
MUTED = "bright_black"
EMPHASIS = "bright_white"


def header(text: str) -> str:
    """Style section header (cyan, bold)"""
    return click.style(text, fg=HEADER, bold=True)


def accent(text: str) -> str:
    """Style primary accent text (bright green)"""
    return click.style(text, fg=ACCENT)


def success(text: str) -> str:
    """Style success message (green)"""
    return click.style(text, fg=SUCCESS)


def warning(text: str) -> str:
    """Style warning message (yellow)"""
    return click.style(text, fg=WARNING)


def error(text: str) -> str:
    """Style error message (red)"""
    return click.style(text, fg=ERROR)


def muted(text: str) -> str:
    """Style secondary/muted text (gray)"""
    return click.style(text, fg=MUTED)


def emphasis(text: str) -> str:
    """Style emphasized text (bright white, bold)"""
    return click.style(text, fg=EMPHASIS, bold=True)


def colorize_priority(priority: str) -> str:
    """Colorize priority level tags"""
    priority_upper = priority.upper()
    if priority_upper in ("CRITICAL", "HIGH"):
        return click.style(f"[{priority_upper}]", fg=ERROR, bold=True)
    elif priority_upper == "MEDIUM":
        return click.style(f"[{priority_upper}]", fg=WARNING)
    else:
        return click.style(f"[{priority_upper}]", fg=MUTED)


def colorize_confidence(score: float) -> str:
    """Colorize confidence score based on value"""
    if score >= 0.8:
        return click.style(f"{score:.0%}", fg=SUCCESS)
    elif score >= 0.5:
        return click.style(f"{score:.0%}", fg=WARNING)
    else:
        return click.style(f"{score:.0%}", fg=ERROR)
