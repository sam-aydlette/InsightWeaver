"""
Tests for CLI App
"""

from unittest.mock import patch

import pytest

from src.cli.app import cli, interactive_mode, print_command_refresher


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
        with (
            patch("src.cli.app.set_debug_mode") as mock_debug,
            patch("src.cli.app.interactive_mode"),
        ):
            cli_runner.invoke(cli, ["--debug"])
            mock_debug.assert_called_with(True)


class TestPrintCommandRefresher:
    """Tests for command refresher helper"""

    def test_print_command_refresher(self, cli_runner, capsys):
        """Should print command refresher"""
        print_command_refresher()
        captured = capsys.readouterr()

        assert "Commands:" in captured.out
        assert "sources" in captured.out


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
        ["brief", "frames", "diet", "questions", "predictions", "forecast", "decisions", "beat"],
    )
    def test_deleted_commands_are_not_registered(self, cli_runner, gone):
        """
        The briefing commands are gone from --help and from dispatch.

        Pinned rather than assumed: the editable install resolves a missing
        ``src.*`` module against the developer's other checkout, so a dangling
        command import can appear to work locally. This asserts on the
        registered command table instead.
        """
        assert gone not in cli.commands

        result = cli_runner.invoke(cli, [gone, "--help"])
        assert result.exit_code != 0


class TestAsciiArt:
    """Tests for ASCII art constant"""

    def test_ascii_art_defined(self):
        """Should have ASCII art defined"""
        from src.cli.app import ASCII_ART

        # ASCII art uses Unicode block characters, not ASCII letters
        assert len(ASCII_ART) > 100  # Has substantial content
        assert "Transform Data" in ASCII_ART or "Insight" in ASCII_ART


class TestInteractiveMode:
    """Tests for interactive mode"""

    @patch("src.cli.app.click.prompt")
    @patch("src.cli.app.click.echo")
    @patch("src.cli.app.time.sleep")
    def test_interactive_mode_exits_on_exit_command(self, mock_sleep, mock_echo, mock_prompt):
        """Should exit on 'exit' command"""
        mock_prompt.return_value = "exit"

        interactive_mode()

        # Should have called prompt at least once
        mock_prompt.assert_called()

    @patch("src.cli.app.click.prompt")
    @patch("src.cli.app.click.echo")
    @patch("src.cli.app.time.sleep")
    def test_interactive_mode_exits_on_quit_command(self, mock_sleep, mock_echo, mock_prompt):
        """Should exit on 'quit' command"""
        mock_prompt.return_value = "quit"

        interactive_mode()

        mock_prompt.assert_called()

    @patch("src.cli.app.click.prompt")
    @patch("src.cli.app.click.echo")
    @patch("src.cli.app.time.sleep")
    def test_interactive_mode_shows_help(self, mock_sleep, mock_echo, mock_prompt):
        """Should show help on 'help' command"""
        mock_prompt.side_effect = ["help", "exit"]

        interactive_mode()

        # Check that help was shown (echo called multiple times)
        assert mock_echo.call_count > 2

    @patch("src.cli.app.click.prompt")
    @patch("src.cli.app.click.echo")
    @patch("src.cli.app.time.sleep")
    def test_interactive_mode_handles_keyboard_interrupt(self, mock_sleep, mock_echo, mock_prompt):
        """Should handle KeyboardInterrupt gracefully"""
        mock_prompt.side_effect = KeyboardInterrupt()

        interactive_mode()

        # Should have printed exit message
        assert any("InsightWeaver" in str(call) for call in mock_echo.call_args_list)

    @patch("src.cli.app.click.prompt")
    @patch("src.cli.app.click.echo")
    @patch("src.cli.app.time.sleep")
    def test_interactive_mode_handles_unknown_command(self, mock_sleep, mock_echo, mock_prompt):
        """Should handle unknown commands"""
        mock_prompt.side_effect = ["unknown_cmd", "exit"]

        interactive_mode()

        # Should show error message
        assert any("Unknown" in str(call) for call in mock_echo.call_args_list)
