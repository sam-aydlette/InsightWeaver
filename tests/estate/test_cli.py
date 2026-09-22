"""
The ``estate`` command, Phase 0: ``auth`` only.
"""

import pytest
from click.testing import CliRunner

from src.config.settings import settings
from src.estate import credentials
from src.estate.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestAuth:
    def test_set_stores_under_the_known_username(self, runner, memory_keyring):
        result = runner.invoke(cli, ["auth", "set", "anthropic", "--value", "sk-test"])

        assert result.exit_code == 0, result.output
        assert memory_keyring.store[(settings.keyring_service, credentials.ANTHROPIC)] == "sk-test"
        assert "sk-test" not in result.output

    def test_set_prompts_with_hidden_input_when_no_value_given(self, runner, memory_keyring):
        result = runner.invoke(cli, ["auth", "set", "anthropic"], input="sk-prompted\n")

        assert result.exit_code == 0, result.output
        assert memory_keyring.store[(settings.keyring_service, credentials.ANTHROPIC)] == (
            "sk-prompted"
        )
        assert "sk-prompted" not in result.output

    def test_set_refuses_a_blank_value(self, runner, memory_keyring):
        result = runner.invoke(cli, ["auth", "set", "anthropic", "--value", "   "])

        assert result.exit_code != 0
        assert "blank" in result.output
        assert not memory_keyring.store

    def test_set_rejects_an_unknown_name(self, runner, memory_keyring):
        result = runner.invoke(cli, ["auth", "set", "plaid", "--value", "x"])

        assert result.exit_code != 0
        assert not memory_keyring.store

    def test_status_never_prints_a_value(self, runner, memory_keyring):
        credentials.write(credentials.ANTHROPIC, "sk-secret")

        result = runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 0, result.output
        assert "anthropic" in result.output and "set" in result.output
        assert "sk-secret" not in result.output

    def test_status_reports_not_set(self, runner, memory_keyring):
        result = runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 0, result.output
        assert "not set" in result.output

    def test_clear_removes_and_a_second_clear_fails(self, runner, memory_keyring):
        credentials.write(credentials.ANTHROPIC, "sk-test")

        first = runner.invoke(cli, ["auth", "clear", "anthropic"])
        second = runner.invoke(cli, ["auth", "clear", "anthropic"])

        assert first.exit_code == 0, first.output
        assert not memory_keyring.store
        assert second.exit_code != 0


class TestShape:
    def test_phase_0_registers_only_auth(self):
        """Later phases add commands one task at a time; nothing is pre-registered."""
        assert set(cli.commands) == {"auth"}

    def test_the_command_has_no_interactive_mode(self, runner):
        """Invoking with no subcommand prints help and exits, rather than looping."""
        result = runner.invoke(cli, [])

        assert "auth" in result.output
        assert result.exit_code in (0, 2)
