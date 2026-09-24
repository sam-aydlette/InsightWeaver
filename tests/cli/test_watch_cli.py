"""
Tests for the `watch` CLI command (backlog task 013).

:class:`TestNoWriteSeamExists` is the invariant-6 test. It asserts on the
registered command table and on each command's parameters rather than on
anybody's intention, because the way the system starts authoring its own
watches is not a decision -- it is a convenient flag added by someone who has
not read the invariant.
"""

from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest.mock import patch

import click
import pytest

from src.cli.watch import _expiry_phrase, watch_command
from src.database.models import Watch as WatchRow
from src.database.models import WatchBelief

EXAMPLE_POSITION = Path(__file__).resolve().parents[2] / "config" / "position.example.yaml"
EXAMPLE_WATCHES = Path(__file__).resolve().parents[2] / "config" / "watches.example.yaml"


def _patch_db(session):
    @contextmanager
    def _ctx():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    return patch("src.cli.watch.get_db", _ctx)


@pytest.fixture
def stored_watch(test_session):
    test_session.add(
        WatchRow(
            id="conmon-scope-expands",
            claim="Continuous monitoring scope expands.",
            belief=0.35,
            decision_key="fedramp-authorization-renewal",
            so_what="It moves renewal past the point where lapsing is cheaper.",
            triggers=[{"terms": ["ConMon"], "entities": ["FedRAMP PMO"]}],
            expires=date(2027, 3, 31),
            staleness_alert_days=30,
        )
    )
    test_session.commit()
    return test_session


class TestWatchList:
    def test_empty_table_says_so(self, cli_runner, test_session):
        with _patch_db(test_session):
            result = cli_runner.invoke(watch_command, ["list"])

        assert result.exit_code == 0
        assert "No watches stored" in result.output

    def test_shows_belief_decision_and_days_to_expiry(self, cli_runner, stored_watch, monkeypatch):
        monkeypatch.setenv("POSITION_PATH", str(EXAMPLE_POSITION))
        with (
            _patch_db(stored_watch),
            patch("src.cli.watch.load_position") as loader,
        ):
            from src.position import load_position as real_loader

            loader.side_effect = lambda: real_loader(EXAMPLE_POSITION)
            result = cli_runner.invoke(watch_command, ["list"])

        assert result.exit_code == 0
        assert "conmon-scope-expands" in result.output
        assert "0.35" in result.output
        assert "fedramp-authorization-renewal" in result.output
        assert "Renew the platform's FedRAMP" in result.output
        assert "to expiry" in result.output

    def test_degrades_to_keys_when_position_is_absent(self, cli_runner, stored_watch, tmp_path):
        """
        Position lives in a private repo and may not be on this machine.

        The listing then shows decision keys and says why, rather than failing:
        the keys are stored on the row and are the load-bearing half.
        """
        with (
            _patch_db(stored_watch),
            patch("src.cli.watch.load_position", side_effect=FileNotFoundError("no position")),
        ):
            result = cli_runner.invoke(watch_command, ["list"])

        assert result.exit_code == 0
        assert "fedramp-authorization-renewal" in result.output
        assert "Position unreadable" in result.output


class TestWatchSync:
    def test_sync_loads_the_checked_in_files(self, cli_runner, test_session, monkeypatch):
        monkeypatch.setenv("POSITION_PATH", str(EXAMPLE_POSITION))
        monkeypatch.setenv("WATCHES_PATH", str(EXAMPLE_WATCHES))

        from src.position import load_position as real_position
        from src.position import load_watches as real_watches

        today = date(2026, 9, 1)
        with (
            _patch_db(test_session),
            patch(
                "src.cli.watch.load_position",
                side_effect=lambda **kw: real_position(EXAMPLE_POSITION, today=today),
            ),
            patch(
                "src.cli.watch.load_watches",
                side_effect=lambda **kw: real_watches(
                    EXAMPLE_WATCHES, position=kw["position"], today=today
                ),
            ),
        ):
            result = cli_runner.invoke(watch_command, ["sync"])

        assert result.exit_code == 0, result.output
        assert test_session.query(WatchRow).count() == 3
        assert "added" in result.output

    def test_sync_reports_a_bad_file_and_stores_nothing(self, cli_runner, test_session):
        from src.position import WatchError

        with (
            _patch_db(test_session),
            patch("src.cli.watch.load_position"),
            patch(
                "src.cli.watch.load_watches",
                side_effect=WatchError(Path("watches.yaml"), ["watch 'x': 'so_what' is required"]),
            ),
        ):
            result = cli_runner.invoke(watch_command, ["sync"])

        assert result.exit_code != 0
        assert "so_what" in result.output
        assert test_session.query(WatchRow).count() == 0


class TestNoWriteSeamExists:
    """Invariant 6: the system never authors its own watches."""

    def test_only_the_four_operator_commands_are_registered(self):
        """list and sync (task 013); believe and resolve (task 030). No constructor."""
        assert set(watch_command.commands) == {"list", "sync", "believe", "resolve"}

    @pytest.mark.parametrize("command", ["believe", "resolve"])
    def test_the_operator_commands_take_no_argument_describing_a_watch(self, command):
        names = {p.name for p in watch_command.commands[command].params}
        assert names.isdisjoint({"claim", "triggers", "so_what", "decision", "expires"})

    @pytest.mark.parametrize("forbidden", ["add", "create", "new", "propose", "accept", "edit"])
    def test_no_write_command_exists(self, forbidden):
        assert forbidden not in watch_command.commands

    def test_sync_takes_no_arguments_describing_a_watch(self):
        """
        ``watch sync`` mirrors a file. The moment it takes ``--claim`` it is a
        constructor, and a constructor can be called by a model.
        """
        params = watch_command.commands["sync"].params
        assert [p.name for p in params if not isinstance(p, click.Option)] == []
        assert params == []

    def test_list_is_read_only_in_its_signature(self):
        assert watch_command.commands["list"].params == []


class TestExpiryPhrase:
    def test_future(self):
        assert "12d to expiry" in _expiry_phrase(date(2026, 9, 13), date(2026, 9, 1))

    def test_today(self):
        assert "expires today" in _expiry_phrase(date(2026, 9, 1), date(2026, 9, 1))

    def test_past(self):
        assert "expired 5d ago" in _expiry_phrase(date(2026, 8, 27), date(2026, 9, 1))


class TestBelieve:
    def test_records_a_principal_belief_with_its_note(self, cli_runner, stored_watch):
        with _patch_db(stored_watch):
            result = cli_runner.invoke(
                watch_command, ["believe", "conmon-scope-expands", "0.6", "--note", "memo landed"]
            )

        assert result.exit_code == 0, result.output
        assert "belief 0.60 recorded" in result.output
        row = stored_watch.query(WatchBelief).one()
        assert (row.belief, row.source, row.note) == (0.6, "principal", "memo landed")

    def test_refuses_without_a_note_and_out_of_range(self, cli_runner, stored_watch):
        with _patch_db(stored_watch):
            no_note = cli_runner.invoke(watch_command, ["believe", "conmon-scope-expands", "0.6"])
            too_big = cli_runner.invoke(
                watch_command, ["believe", "conmon-scope-expands", "1.6", "--note", "n"]
            )

        assert no_note.exit_code != 0
        assert too_big.exit_code != 0
        assert stored_watch.query(WatchBelief).count() == 0

    def test_refuses_an_unknown_watch(self, cli_runner, stored_watch):
        with _patch_db(stored_watch):
            result = cli_runner.invoke(watch_command, ["believe", "nope", "0.5", "--note", "n"])

        assert result.exit_code != 0
        assert "no watch 'nope'" in result.output

    def test_list_shows_the_current_belief_its_source_and_the_registration(
        self, cli_runner, stored_watch, tmp_path
    ):
        with _patch_db(stored_watch):
            cli_runner.invoke(
                watch_command, ["believe", "conmon-scope-expands", "0.6", "--note", "memo"]
            )
            result = cli_runner.invoke(watch_command, ["list"])

        assert result.exit_code == 0, result.output
        assert "belief:   0.60" in result.output
        assert "(principal, " in result.output
        assert "registered 0.35" in result.output


class TestResolve:
    def test_grades_once_and_refuses_a_second_time(self, cli_runner, stored_watch):
        with _patch_db(stored_watch):
            first = cli_runner.invoke(
                watch_command,
                ["resolve", "conmon-scope-expands", "--outcome", "no", "--note", "deviation"],
            )
            second = cli_runner.invoke(
                watch_command,
                ["resolve", "conmon-scope-expands", "--outcome", "yes", "--note", "changed"],
            )
            listing = cli_runner.invoke(watch_command, ["list"])

        assert first.exit_code == 0, first.output
        assert "resolved no" in first.output
        assert second.exit_code != 0
        row = stored_watch.get(WatchRow, "conmon-scope-expands")
        assert (row.outcome, row.resolution_note) == ("no", "deviation")
        assert "[resolved no" in listing.output

    def test_list_marks_a_retired_watch(self, cli_runner, stored_watch):
        from datetime import datetime

        stored_watch.get(WatchRow, "conmon-scope-expands").retired_at = datetime(2026, 8, 30)
        stored_watch.commit()

        with _patch_db(stored_watch):
            result = cli_runner.invoke(watch_command, ["list"])

        assert result.exit_code == 0, result.output
        assert "[retired 2026-08-30]" in result.output

    def test_refuses_an_outcome_outside_yes_no(self, cli_runner, stored_watch):
        with _patch_db(stored_watch):
            result = cli_runner.invoke(
                watch_command,
                ["resolve", "conmon-scope-expands", "--outcome", "maybe", "--note", "n"],
            )

        assert result.exit_code != 0
