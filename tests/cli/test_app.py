"""
Tests for CLI App
"""

from unittest.mock import MagicMock, patch

from src.cli.app import cli, interactive_mode, print_command_refresher


class TestCliGroup:
    """Tests for main CLI group"""

    def test_cli_help(self, cli_runner):
        """Should show help text"""
        result = cli_runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "InsightWeaver" in result.output
        assert "RSS Feed Analysis" in result.output

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
        assert "brief" in captured.out
        assert "trust" in captured.out
        assert "forecast" in captured.out


class TestSubcommandRegistration:
    """Tests for subcommand registration"""

    def test_brief_command_registered(self, cli_runner):
        """Should have brief command registered"""
        result = cli_runner.invoke(cli, ["brief", "--help"])

        assert result.exit_code == 0
        assert "hours" in result.output.lower()

    def test_trust_command_registered(self, cli_runner):
        """Should have trust command registered"""
        result = cli_runner.invoke(cli, ["trust", "--help"])

        assert result.exit_code == 0
        assert "query" in result.output.lower() or "verified" in result.output.lower()

    def test_forecast_command_registered(self, cli_runner):
        """Should have forecast command registered"""
        result = cli_runner.invoke(cli, ["forecast", "--help"])

        assert result.exit_code == 0
        assert "forecast" in result.output.lower()

    def test_setup_command_registered(self, cli_runner):
        """Should have setup command registered"""
        result = cli_runner.invoke(cli, ["setup", "--help"])

        assert result.exit_code == 0
        assert "port" in result.output.lower()

    def test_start_command_registered(self, cli_runner):
        """Should have start command registered"""
        result = cli_runner.invoke(cli, ["start", "--help"])

        assert result.exit_code == 0
        assert "port" in result.output.lower()


class TestSetupCommand:
    """Tests for setup command"""

    def test_setup_help(self, cli_runner):
        """Should show setup help"""
        result = cli_runner.invoke(cli, ["setup", "--help"])

        assert result.exit_code == 0
        assert "wizard" in result.output.lower()

    @patch("src.web.server.create_app")
    @patch("src.cli.app.webbrowser")
    @patch("os.path.exists")
    def test_setup_command_starts_server(
        self, mock_exists, mock_webbrowser, mock_create_app, cli_runner
    ):
        """Should start web server for setup"""
        mock_exists.return_value = False
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app
        import contextlib

        mock_app.run.side_effect = KeyboardInterrupt()  # Stop immediately

        with contextlib.suppress(KeyboardInterrupt):
            cli_runner.invoke(cli, ["setup", "--port", "5001"])

        mock_create_app.assert_called_once()


class TestStartCommand:
    """Tests for start command"""

    def test_start_help(self, cli_runner):
        """Should show start help"""
        result = cli_runner.invoke(cli, ["start", "--help"])

        assert result.exit_code == 0
        assert "web interface" in result.output.lower()

    def test_start_no_browser_option(self, cli_runner):
        """Should accept no-browser option"""
        result = cli_runner.invoke(cli, ["start", "--help"])

        assert "--no-browser" in result.output


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
    def test_interactive_mode_exits_on_exit_command(
        self, mock_sleep, mock_echo, mock_prompt
    ):
        """Should exit on 'exit' command"""
        mock_prompt.return_value = "exit"

        interactive_mode()

        # Should have called prompt at least once
        mock_prompt.assert_called()

    @patch("src.cli.app.click.prompt")
    @patch("src.cli.app.click.echo")
    @patch("src.cli.app.time.sleep")
    def test_interactive_mode_exits_on_quit_command(
        self, mock_sleep, mock_echo, mock_prompt
    ):
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
    def test_interactive_mode_handles_keyboard_interrupt(
        self, mock_sleep, mock_echo, mock_prompt
    ):
        """Should handle KeyboardInterrupt gracefully"""
        mock_prompt.side_effect = KeyboardInterrupt()

        interactive_mode()

        # Should have printed exit message
        assert any("InsightWeaver" in str(call) for call in mock_echo.call_args_list)

    @patch("src.cli.app.click.prompt")
    @patch("src.cli.app.click.echo")
    @patch("src.cli.app.time.sleep")
    def test_interactive_mode_handles_unknown_command(
        self, mock_sleep, mock_echo, mock_prompt
    ):
        """Should handle unknown commands"""
        mock_prompt.side_effect = ["unknown_cmd", "exit"]

        interactive_mode()

        # Should show error message
        assert any("Unknown" in str(call) for call in mock_echo.call_args_list)
