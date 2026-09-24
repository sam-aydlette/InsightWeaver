"""
Tests for CLI App
"""

from unittest.mock import patch

import pytest

from src.cli.app import cli


class TestCliGroup:
    """Tests for main CLI group"""

    def test_cli_help(self, cli_runner):
        """Should show help text"""
        result = cli_runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "InsightWeaver" in result.output
        assert "monitoring against pre-registered watches" in result.output

    def test_cli_version(self, cli_runner):
        """Should show version"""
        result = cli_runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "1.0.0" in result.output

    def test_cli_debug_flag(self, cli_runner):
        """Should accept debug flag"""
        with patch("src.cli.app.set_debug_mode") as mock_debug:
            result = cli_runner.invoke(cli, ["--debug"])
            mock_debug.assert_called_with(True)

        assert result.exit_code == 0
        assert "InsightWeaver" in result.output

    def test_cli_with_no_arguments_prints_help_and_exits(self, cli_runner):
        """No subcommand prints the group help and exits 0, rather than entering a REPL."""
        result = cli_runner.invoke(cli, [])

        assert result.exit_code == 0
        assert "sources" in result.output


class TestSubcommandRegistration:
    """Tests for subcommand registration"""

    def test_sources_command_registered(self, cli_runner):
        """Should have sources command registered"""
        result = cli_runner.invoke(cli, ["sources", "--help"])

        assert result.exit_code == 0
        assert "list" in result.output.lower()

    def test_watch_command_registered(self, cli_runner):
        """Should have watch command registered (backlog task 013)"""
        result = cli_runner.invoke(cli, ["watch", "--help"])

        assert result.exit_code == 0
        assert "list" in result.output.lower()
        assert "sync" in result.output.lower()

    def test_watch_has_no_add_subcommand(self, cli_runner):
        """
        Invariant 6: the system never authors its own watches.

        Asserted here as well as in tests/cli/test_watch_cli.py because this is
        the file someone reads when adding a command.
        """
        assert "add" not in cli.commands["watch"].commands

    @pytest.mark.parametrize(
        "gone",
        ["frames", "diet", "questions", "predictions", "forecast", "decisions", "beat"],
    )
    def test_deleted_commands_are_not_registered(self, cli_runner, gone):
        """
        The briefing commands are gone from --help and from dispatch. ``brief``
        left this list on 2026-09-22 (backlog task 031) when it came back as a
        derived view over the monitor's tables, with no model call in it.

        Pinned rather than assumed: the editable install resolves a missing
        ``src.*`` module against the developer's other checkout, so a dangling
        command import can appear to work locally. This asserts on the
        registered command table instead.
        """
        assert gone not in cli.commands

        result = cli_runner.invoke(cli, [gone, "--help"])
        assert result.exit_code != 0
