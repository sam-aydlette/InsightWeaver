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

    def test_only_list_and_sync_are_registered(self):
        assert set(watch_command.commands) == {"list", "sync"}

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
