"""
Base Terminal Formatter
Common formatting utilities for terminal output
"""

import textwrap
from typing import Any


class BaseTerminalFormatter:
    """Base class with common terminal formatting utilities"""

    def __init__(self, max_width: int = 80):
        self.max_width = max_width

    def format_header(self, title: str, char: str = "=") -> str:
        """
        Format a section header with decorative characters

        Args:
            title: Header title text
            char: Character to use for decoration (default: '=')

        Returns:
            Formatted header string with decoration lines
        """
        return f"{char * self.max_width}\n{title}\n{char * self.max_width}"

    def format_subheader(self, title: str, char: str = "-") -> str:
        """
        Format a subsection header

        Args:
            title: Subheader title text
            char: Character to use for decoration (default: '-')

        Returns:
            Formatted subheader string
        """
        return f"{char * self.max_width}\n{title}\n{char * self.max_width}"

    def wrap_text(
        self,
        text: str,
        indent: int = 0,
        subsequent_indent: int | None = None,
    ) -> str:
        """
        Wrap text to fit within max_width

        Args:
            text: Text to wrap
            indent: Number of spaces for initial indent
            subsequent_indent: Indent for subsequent lines (defaults to indent)

        Returns:
            Wrapped text string
        """
        initial = " " * indent
        subsequent = " " * (subsequent_indent if subsequent_indent is not None else indent)
        return textwrap.fill(
            text,
            width=self.max_width,
            initial_indent=initial,
            subsequent_indent=subsequent,
        )

    def format_list(
        self,
        items: list[str],
        bullet: str = "-",
        indent: int = 2,
    ) -> str:
        """
        Format a list of items with bullets

        Args:
            items: List of string items
            bullet: Bullet character (default: '-')
            indent: Indentation level

        Returns:
            Formatted list string
        """
        lines = []
        prefix = " " * indent
        bullet_prefix = f"{prefix}{bullet} "
        wrap_indent = " " * (indent + len(bullet) + 1)

        for item in items:
            wrapped = textwrap.fill(
                item,
                width=self.max_width,
                initial_indent=bullet_prefix,
                subsequent_indent=wrap_indent,
            )
            lines.append(wrapped)

        return "\n".join(lines)

    def format_numbered_list(
        self,
        items: list[str],
        indent: int = 0,
        start: int = 1,
    ) -> str:
        """
        Format a numbered list of items

        Args:
            items: List of string items
            indent: Indentation level
            start: Starting number

        Returns:
            Formatted numbered list string
        """
        lines = []
        prefix = " " * indent

        for i, item in enumerate(items, start):
            number_prefix = f"{prefix}{i}. "
            wrap_indent = " " * (indent + len(str(i)) + 2)
            wrapped = textwrap.fill(
                item,
                width=self.max_width,
                initial_indent=number_prefix,
                subsequent_indent=wrap_indent,
            )
            lines.append(wrapped)

        return "\n".join(lines)

    def format_key_value(
        self,
        key: str,
        value: Any,
        separator: str = ": ",
        indent: int = 0,
    ) -> str:
        """
        Format a key-value pair

        Args:
            key: The key/label
            value: The value (will be converted to string)
            separator: Separator between key and value
            indent: Indentation level

        Returns:
            Formatted key-value string
        """
        prefix = " " * indent
        key_prefix = f"{prefix}{key}{separator}"
        wrap_indent = " " * len(key_prefix)

        return textwrap.fill(
            str(value),
            width=self.max_width,
            initial_indent=key_prefix,
            subsequent_indent=wrap_indent,
        )

    def format_section(
        self,
        title: str,
        content: str | list[str],
        header_char: str = "-",
    ) -> str:
        """
        Format a complete section with header and content

        Args:
            title: Section title
            content: Section content (string or list of lines)
            header_char: Character for header decoration

        Returns:
            Formatted section string
        """
        lines = [
            self.format_subheader(title, header_char),
            "",
        ]

        if isinstance(content, list):
            lines.extend(content)
        else:
            lines.append(content)

        lines.append("")
        return "\n".join(lines)
