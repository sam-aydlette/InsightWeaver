"""
Tests for the ``brief`` CLI command (backlog task 031).

Every render passes ``--as-of`` explicitly so nothing here reads the wall
clock. The Position is always patched at ``src.cli.brief.load_position`` so
these tests do not depend on whether a real Position file exists on the
machine running them.

Added 2026-09-22 for backlog task 031.
"""

from __future__ import annotations

import hashlib
import re
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from src.cli.brief import brief_command
from src.database.models import BriefRun
from src.position.position import Position, PositionError


def _stamp(when: datetime) -> str:
    return when.strftime("%Y-%m-%d %H:%M")


def _patch_db(session):
    @contextmanager
    def _ctx():
        try:
            yield session
            session.flush()
        except Exception:
            session.rollback()
            raise

    return patch("src.cli.brief.get_db", _ctx)


def _position(reviewed: date | None = date(2026, 9, 1)) -> Position:
    return Position(path=Path("position.yaml"), version=1, decisions=(), reviewed=reviewed)


def _patch_position(value=None, error: Exception | None = None):
    def _load(**_kwargs):
        if error is not None:
            raise error
        return value if value is not None else _position()

    return patch("src.cli.brief.load_position", _load)


@pytest.fixture
def run(cli_runner, test_session):
    """Invoke brief_command against the test session with a valid Position."""

    def _run(args, position_patch=None):
        with _patch_db(test_session), position_patch or _patch_position():
            return cli_runner.invoke(brief_command, args)

    return _run


class TestDefaultWindow:
    def test_no_briefs_rows_defaults_to_seven_days_back(self, run):
        as_of = "2026-09-22T06:00:00"
        result = run(["--as-of", as_of, "--dry-run"])
        assert result.exit_code == 0, result.output
        expected_since = datetime(2026, 9, 22, 6, 0) - timedelta(days=7)
        assert f"window: since {_stamp(expected_since)}" in result.output

    def test_a_row_before_todays_start_sets_the_window(self, run, test_session):
        # 2026-09-21 23:00 is before the start of 2026-09-22, so it qualifies.
        prior = datetime(2026, 9, 21, 23, 0)
        test_session.add(
            BriefRun(
                as_of=prior, since=prior - timedelta(days=7), moved=0, quiet=0, rendered_sha="x"
            )
        )
        test_session.flush()

        result = run(["--as-of", "2026-09-22T06:00:00", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert f"window: since {_stamp(prior)}" in result.output

    def test_a_row_later_the_same_day_is_ignored_by_the_next_run(self, run, test_session):
        # A qualifying row from yesterday sets the window both times.
        prior = datetime(2026, 9, 21, 20, 0)
        test_session.add(
            BriefRun(
                as_of=prior, since=prior - timedelta(days=7), moved=0, quiet=0, rendered_sha="x"
            )
        )
        test_session.flush()

        as_of = "2026-09-22T06:00:00"
        first = run(["--as-of", as_of])
        second = run(["--as-of", as_of])
        assert first.exit_code == 0, first.output
        assert second.exit_code == 0, second.output
        assert first.output == second.output, (
            "a second run the same morning must reproduce the first, "
            "not fold in the row the first run just wrote"
        )

    def test_the_newest_qualifying_row_wins(self, run, test_session):
        older = datetime(2026, 9, 19, 8, 0)
        newer = datetime(2026, 9, 20, 8, 0)
        test_session.add_all(
            [
                BriefRun(as_of=older, since=older, moved=0, quiet=0, rendered_sha="a"),
                BriefRun(as_of=newer, since=newer, moved=0, quiet=0, rendered_sha="b"),
            ]
        )
        test_session.flush()

        result = run(["--as-of", "2026-09-22T06:00:00", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert f"window: since {_stamp(newer)}" in result.output
        assert f"window: since {_stamp(older)}" not in result.output


class TestSinceOverride:
    def test_since_2w_overrides_the_default(self, run):
        as_of = "2026-09-22T06:00:00"
        result = run(["--as-of", as_of, "--since", "2w", "--dry-run"])
        assert result.exit_code == 0, result.output
        expected_since = datetime(2026, 9, 22, 6, 0) - timedelta(days=14)
        assert f"window: since {_stamp(expected_since)}" in result.output


class TestBriefsRow:
    def test_a_row_is_written_per_render_with_counts_and_sha(self, run, test_session):
        as_of = "2026-09-22T06:00:00"
        result = run(["--as-of", as_of])
        assert result.exit_code == 0, result.output

        rows = test_session.query(BriefRun).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.moved == len([])  # no watches exist in this corpus
        assert row.quiet == 0
        assert row.rendered_sha == hashlib.sha256(result.output.encode("utf-8")).hexdigest()

    def test_dry_run_writes_no_row(self, run, test_session):
        as_of = "2026-09-22T06:00:00"
        result = run(["--as-of", as_of, "--dry-run"])
        assert result.exit_code == 0, result.output
        assert test_session.query(BriefRun).count() == 0


class TestFormatAndOutput:
    def test_format_md_prints_markdown_headings(self, run):
        as_of = "2026-09-22T06:00:00"
        result = run(["--as-of", as_of, "--format", "md", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "## MOVED" in result.output
        assert "## QUIET" in result.output
        assert not re.search(r"^MOVED$", result.output, re.MULTILINE)

    def test_output_path_writes_the_file_and_prints_wrote(self, run, tmp_path):
        as_of = "2026-09-22T06:00:00"
        out_path = tmp_path / "brief.txt"

        plain = run(["--as-of", as_of, "--dry-run"])
        assert plain.exit_code == 0, plain.output

        written = run(["--as-of", as_of, "--dry-run", "--output", str(out_path)])
        assert written.exit_code == 0, written.output
        assert "wrote" in written.output
        assert str(out_path) in written.output
        assert out_path.read_text(encoding="utf-8") == plain.output


class TestAsOfParsing:
    def test_a_non_iso_as_of_exits_non_zero_with_a_message(self, run):
        result = run(["--as-of", "not-a-date", "--dry-run"])
        assert result.exit_code != 0
        assert "not-a-date" in result.output
        assert "ISO 8601" in result.output

    def test_an_aware_as_of_is_converted_to_naive_utc(self, run):
        # 2026-09-22T08:00:00+02:00 is 2026-09-22T06:00:00 UTC.
        result = run(["--as-of", "2026-09-22T08:00:00+02:00", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert f"Brief as of {_stamp(datetime(2026, 9, 22, 6, 0))}".upper() in result.output


class TestPositionNotRead:
    def test_a_position_that_cannot_be_read_still_renders_and_exits_zero(self, run):
        result = run(
            ["--as-of", "2026-09-22T06:00:00", "--dry-run"],
            position_patch=_patch_position(error=FileNotFoundError("no position at /nowhere")),
        )
        assert result.exit_code == 0, result.output
        assert "POSITION NOT READ" in result.output
        assert "no position at /nowhere" in result.output

    def test_a_position_error_also_renders_with_the_message(self, run):
        bad_path = Path("/nowhere/position.yaml")
        error = PositionError(bad_path, ["'decisions' is required"])
        result = run(
            ["--as-of", "2026-09-22T06:00:00", "--dry-run"],
            position_patch=_patch_position(error=error),
        )
        assert result.exit_code == 0, result.output
        assert "POSITION NOT READ" in result.output
        # Every problem the loader found, not just the first line of the message.
        assert "'decisions' is required" in result.output
        assert "REVIEW OVERDUE" in result.output
        assert "decisions: POSITION NOT READ (see the header)" in result.output


class TestOutputFailure:
    def test_an_unwritable_output_path_records_no_brief(self, run, test_session, tmp_path):
        """A row for a brief nobody received would move the next default window past it."""
        missing_dir = tmp_path / "no-such-dir" / "brief.txt"
        result = run(["--as-of", "2026-09-22T06:00:00", "--output", str(missing_dir)])
        assert result.exit_code != 0
        assert "could not write" in result.output
        assert test_session.query(BriefRun).count() == 0


class TestInvalidSince:
    def test_an_invalid_since_exits_non_zero_and_writes_no_row(self, run, test_session):
        result = run(["--as-of", "2026-09-22T06:00:00", "--since", "not-a-cadence"])
        assert result.exit_code != 0
        assert test_session.query(BriefRun).count() == 0


class TestNoModelCallInTheRenderPath:
    def test_no_module_imports_the_model_client_or_the_adjudicator(self):
        """
        The render path (backlog task 031) makes no model call; OUT OF SCOPE in
        the task file. Scanning source text rather than sys.modules, because an
        indirect import elsewhere in the process could otherwise make this test
        pass by accident.
        """
        root = Path(__file__).resolve().parents[2] / "src"
        files = [*sorted((root / "brief").glob("*.py")), root / "cli" / "brief.py"]
        assert files, "expected src/brief/*.py and src/cli/brief.py to exist"
        for path in files:
            text = path.read_text(encoding="utf-8")
            assert "src.llm" not in text, f"{path} imports src.llm"
            assert "src.evidence.claude_adjudicator" not in text, (
                f"{path} imports src.evidence.claude_adjudicator"
            )
