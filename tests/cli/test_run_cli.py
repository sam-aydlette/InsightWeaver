"""
Tests for the `run` CLI command (backlog task 031).

``run`` chains ingest, route, adjudicate and brief and stops at the first
step that raises a ``click.ClickException``. These tests never execute the
real steps -- ``src.cli.run.STEPS`` is patched with fake commands whose
callbacks record their own invocation, so the tests exercise only the
orchestration logic in ``run_command`` itself.

Added 2026-09-22, backlog task 031.
"""

from unittest.mock import patch

import click
import pytest

from src.cli.app import cli
from src.cli.run import STEPS, run_command


def _fake_step(name, calls, raises=None, warn=None):
    """Build a click.Command whose callback records the call and optionally raises."""

    @click.command(name=name)
    def _cmd():
        calls.append(name)
        if warn is not None:
            click.echo(warn)
        if raises is not None:
            raise raises

    return name, _cmd


class TestRunOrdersAndEchoesSteps:
    def test_steps_run_in_order(self, cli_runner):
        calls = []
        steps = (
            _fake_step("ingest", calls),
            _fake_step("route", calls),
            _fake_step("adjudicate", calls),
            _fake_step("brief", calls),
        )

        with patch("src.cli.run.STEPS", steps):
            result = cli_runner.invoke(run_command, [])

        assert result.exit_code == 0
        assert calls == ["ingest", "route", "adjudicate", "brief"]

    def test_each_step_name_is_echoed_with_arrow_prefix(self, cli_runner):
        calls = []
        steps = (
            _fake_step("ingest", calls),
            _fake_step("route", calls),
        )

        with patch("src.cli.run.STEPS", steps):
            result = cli_runner.invoke(run_command, [])

        assert "==> ingest" in result.output
        assert "==> route" in result.output


class TestRunStopsAtFirstFailure:
    def test_click_exception_in_second_step_stops_the_run(self, cli_runner):
        calls = []
        steps = (
            _fake_step("ingest", calls),
            _fake_step("route", calls, raises=click.ClickException("boom")),
            _fake_step("adjudicate", calls),
            _fake_step("brief", calls),
        )

        with patch("src.cli.run.STEPS", steps):
            result = cli_runner.invoke(run_command, [])

        assert result.exit_code != 0
        assert calls == ["ingest", "route"]
        assert "route" not in calls[2:]
        assert "adjudicate" not in calls
        assert "brief" not in calls

    def test_failure_message_is_prefixed_with_the_step_name(self, cli_runner):
        calls = []
        steps = (
            _fake_step("ingest", calls),
            _fake_step("route", calls, raises=click.ClickException("boom")),
        )

        with patch("src.cli.run.STEPS", steps):
            result = cli_runner.invoke(run_command, [])

        assert "route: boom" in result.output


class TestRunToleratesWarnings:
    def test_a_step_that_warns_but_returns_normally_does_not_stop_the_run(self, cli_runner):
        calls = []
        steps = (
            _fake_step("ingest", calls, warn="warning: one source unreachable"),
            _fake_step("route", calls),
        )

        with patch("src.cli.run.STEPS", steps):
            result = cli_runner.invoke(run_command, [])

        assert result.exit_code == 0
        assert calls == ["ingest", "route"]
        assert "warning: one source unreachable" in result.output


class TestRealStepsTable:
    def test_step_names_are_exactly_ingest_route_adjudicate_brief_in_order(self):
        assert tuple(name for name, _ in STEPS) == ("ingest", "route", "adjudicate", "brief")

    @pytest.mark.parametrize("name", ["ingest", "route", "adjudicate", "brief"])
    def test_each_step_command_is_the_one_registered_on_the_cli_group(self, name):
        steps_by_name = dict(STEPS)
        assert steps_by_name[name] is cli.commands[name]


class TestRealCliHelp:
    def test_run_help_exits_zero_through_the_real_cli_group(self, cli_runner):
        result = cli_runner.invoke(cli, ["run", "--help"])
        assert result.exit_code == 0

    def test_brief_help_exits_zero_through_the_real_cli_group(self, cli_runner):
        result = cli_runner.invoke(cli, ["brief", "--help"])
        assert result.exit_code == 0

    def test_run_and_brief_are_registered_on_the_cli_group(self):
        assert "run" in cli.commands
        assert "brief" in cli.commands
