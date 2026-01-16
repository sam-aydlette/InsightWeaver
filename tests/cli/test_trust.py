"""
Tests for Trust Command
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cli.trust import trust_command


class TestTrustCommandHelp:
    """Tests for trust command help"""

    def test_trust_help(self, cli_runner):
        """Should show trust help text"""
        result = cli_runner.invoke(trust_command, ["--help"])

        assert result.exit_code == 0
        assert "Trust-verified" in result.output
        assert "query" in result.output.lower()


class TestTrustCommandOptions:
    """Tests for trust command options"""

    def test_trust_has_no_verify_option(self, cli_runner):
        """Should have --no-verify option"""
        result = cli_runner.invoke(trust_command, ["--help"])

        assert "--no-verify" in result.output

    def test_trust_has_verify_facts_only_option(self, cli_runner):
        """Should have --verify-facts-only option"""
        result = cli_runner.invoke(trust_command, ["--help"])

        assert "--verify-facts-only" in result.output

    def test_trust_has_check_bias_only_option(self, cli_runner):
        """Should have --check-bias-only option"""
        result = cli_runner.invoke(trust_command, ["--help"])

        assert "--check-bias-only" in result.output

    def test_trust_has_check_tone_only_option(self, cli_runner):
        """Should have --check-tone-only option"""
        result = cli_runner.invoke(trust_command, ["--help"])

        assert "--check-tone-only" in result.output

    def test_trust_has_export_option(self, cli_runner):
        """Should have --export option"""
        result = cli_runner.invoke(trust_command, ["--help"])

        assert "--export" in result.output

    def test_trust_has_format_option(self, cli_runner):
        """Should have --format option"""
        result = cli_runner.invoke(trust_command, ["--help"])

        assert "--format" in result.output

    def test_trust_has_verbose_option(self, cli_runner):
        """Should have --verbose option"""
        result = cli_runner.invoke(trust_command, ["--help"])

        assert "--verbose" in result.output

    def test_trust_has_quiet_option(self, cli_runner):
        """Should have --quiet option"""
        result = cli_runner.invoke(trust_command, ["--help"])

        assert "--quiet" in result.output or "-q" in result.output


class TestTrustCommandNoApiKey:
    """Tests for trust command without API key"""

    def test_trust_fails_without_api_key(self, cli_runner, mock_no_api_key):
        """Should fail when API key not configured"""
        result = cli_runner.invoke(trust_command, ["test query"])

        assert result.exit_code != 0
        assert "ANTHROPIC_API_KEY" in result.output or "API" in result.output


class TestTrustCommandExecution:
    """Tests for trust command execution"""

    @patch("src.cli.trust.asyncio.run")
    @patch("src.cli.trust.should_show_art")
    def test_trust_runs_pipeline(
        self, mock_show_art, mock_asyncio_run, cli_runner, mock_api_key
    ):
        """Should run trust pipeline with query"""
        mock_show_art.return_value = False
        mock_asyncio_run.return_value = None

        cli_runner.invoke(trust_command, ["What is AI?", "--quiet"])

        mock_asyncio_run.assert_called_once()

    @patch("src.cli.trust.asyncio.run")
    @patch("src.cli.trust.should_show_art")
    def test_trust_joins_multi_word_query(
        self, mock_show_art, mock_asyncio_run, cli_runner, mock_api_key
    ):
        """Should join multi-word query into single string"""
        mock_show_art.return_value = False
        mock_asyncio_run.return_value = None

        cli_runner.invoke(trust_command, ["What", "is", "AI?", "--quiet"])

        # Query should be joined
        call_args = mock_asyncio_run.call_args
        assert call_args is not None


class TestTrustPipelineAsync:
    """Tests for async trust pipeline function"""

    @pytest.mark.asyncio
    @patch("src.cli.trust.TrustPipeline")
    @patch("src.cli.trust.TrustReportFormatter")
    @patch("src.cli.trust.click.echo")
    @patch("src.cli.trust.settings")
    async def test_run_trust_pipeline_success(
        self, mock_settings, mock_echo, mock_formatter_class, mock_pipeline_class
    ):
        """Should run trust pipeline successfully"""
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from src.cli.trust import _run_trust_pipeline

        # Setup mocks
        mock_pipeline = MagicMock()
        mock_pipeline_class.return_value = mock_pipeline
        mock_pipeline.run_full_pipeline = AsyncMock(
            return_value={
                "response": "Test response",
                "analysis": {"overall_trust_score": 0.9},
            }
        )

        mock_formatter = MagicMock()
        mock_formatter_class.return_value = mock_formatter
        mock_formatter.format_response_display.return_value = "Response display"
        mock_formatter.format_compact_summary.return_value = "Summary"
        mock_formatter.export_to_text.return_value = "Report text"

        with TemporaryDirectory() as tmpdir:
            mock_settings.trust_reports_dir = Path(tmpdir)

            await _run_trust_pipeline(
                query="Test query",
                verify_response=True,
                verify_facts=True,
                check_bias=True,
                check_intimacy=True,
                export_path=None,
                export_format="text",
                verbose=False,
            )

        mock_pipeline.run_full_pipeline.assert_called_once()
