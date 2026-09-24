"""
The ``auth`` subcommand of ``insightweaver``.

Moved from ``tests/estate/test_cli.py`` on 2026-09-22 (backlog task 027) when
the ``estate`` script folded into ``insightweaver`` as one command.
"""

from src.cli.app import cli
from src.config import credentials
from src.config.settings import settings


class TestAuth:
    def test_set_stores_under_the_known_username(self, cli_runner, memory_keyring):
        result = cli_runner.invoke(cli, ["auth", "set", "anthropic", "--value", "sk-test"])

        assert result.exit_code == 0, result.output
        assert memory_keyring.store[(settings.keyring_service, credentials.ANTHROPIC)] == "sk-test"
        assert "sk-test" not in result.output

    def test_set_prompts_with_hidden_input_when_no_value_given(self, cli_runner, memory_keyring):
        result = cli_runner.invoke(cli, ["auth", "set", "anthropic"], input="sk-prompted\n")

        assert result.exit_code == 0, result.output
        assert memory_keyring.store[(settings.keyring_service, credentials.ANTHROPIC)] == (
            "sk-prompted"
        )
        assert "sk-prompted" not in result.output

    def test_set_refuses_a_blank_value(self, cli_runner, memory_keyring):
        result = cli_runner.invoke(cli, ["auth", "set", "anthropic", "--value", "   "])

        assert result.exit_code != 0
        assert "blank" in result.output
        assert not memory_keyring.store

    def test_set_rejects_an_unknown_name(self, cli_runner, memory_keyring):
        result = cli_runner.invoke(cli, ["auth", "set", "plaid", "--value", "x"])

        assert result.exit_code != 0
        assert not memory_keyring.store

    def test_status_never_prints_a_value(self, cli_runner, memory_keyring):
        credentials.write(credentials.ANTHROPIC, "sk-secret")

        result = cli_runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 0, result.output
        assert "anthropic" in result.output and "set" in result.output
        assert "sk-secret" not in result.output

    def test_status_reports_not_set(self, cli_runner, memory_keyring):
        result = cli_runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 0, result.output
        assert "not set" in result.output

    def test_clear_removes_and_a_second_clear_fails(self, cli_runner, memory_keyring):
        credentials.write(credentials.ANTHROPIC, "sk-test")

        first = cli_runner.invoke(cli, ["auth", "clear", "anthropic"])
        second = cli_runner.invoke(cli, ["auth", "clear", "anthropic"])

        assert first.exit_code == 0, first.output
        assert not memory_keyring.store
        assert second.exit_code != 0
