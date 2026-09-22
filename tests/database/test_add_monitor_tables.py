"""
Tests for the migration that adds the decision monitor's tables (backlog task 028).

Mirrors tests/database/test_add_watches_table.py: the table is built from the
model, so the tests are weighted towards what would be silently lost if it were
ever replaced with hand-written DDL -- the UNIQUE and CHECK constraints -- and
towards the way down, which loses rows and refuses without ``--confirm``.

Every fixture builds its own SQLite file. Nothing here opens the real database.
"""

import pytest
from sqlalchemy import create_engine, inspect, text

from src.database.migrations import add_monitor_tables as mig
from src.database.models import Route


@pytest.fixture
def blank_engine(tmp_path):
    return create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")


class TestUpgrade:
    def test_creates_routes_and_returns_its_name(self, blank_engine):
        assert mig.upgrade(blank_engine) == ["routes"]
        assert inspect(blank_engine).has_table("routes")

    def test_is_idempotent(self, blank_engine):
        mig.upgrade(blank_engine)
        assert mig.upgrade(blank_engine) == []

    def test_columns_match_the_route_model(self, blank_engine):
        mig.upgrade(blank_engine)
        created = {c["name"] for c in inspect(blank_engine).get_columns("routes")}
        assert created == set(Route.__table__.columns.keys())

    def test_the_unique_and_check_constraints_are_in_the_created_ddl(self, blank_engine):
        """
        Read from sqlite_master rather than from the model: the question is what
        the migration actually created, not what it intended to.
        """
        mig.upgrade(blank_engine)
        with blank_engine.connect() as conn:
            ddl = conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='table' AND name='routes'")
            ).scalar()

        assert "_route_observation_watch_uc" in ddl
        assert "UNIQUE (observation_hash, watch_id)" in ddl
        assert "ck_routes_clause_index" in ddl
        assert "CHECK (clause_index >= 0)" in ddl

    def test_touches_nothing_else(self, blank_engine):
        """Additive means additive: it creates one table and no others."""
        mig.upgrade(blank_engine)
        assert inspect(blank_engine).get_table_names() == ["routes"]


class TestDowngrade:
    def test_refuses_without_confirm(self, blank_engine):
        mig.upgrade(blank_engine)
        with pytest.raises(SystemExit) as exc:
            mig.downgrade(blank_engine)
        assert "--confirm" in str(exc.value)
        assert inspect(blank_engine).has_table("routes")

    def test_drops_with_confirm(self, blank_engine):
        mig.upgrade(blank_engine)
        assert mig.downgrade(blank_engine, confirmed=True) == ["routes"]
        assert not inspect(blank_engine).has_table("routes")

    def test_drop_on_a_missing_table_is_a_no_op(self, blank_engine):
        assert mig.downgrade(blank_engine, confirmed=True) == []


class TestMainEntryPoint:
    def test_down_without_confirm_exits_non_zero(self, blank_engine, monkeypatch):
        """
        Drives ``main`` rather than ``downgrade`` directly, to prove the CLI
        wiring refuses too, not just the function it calls.

        The module-level ``engine`` is patched to the throwaway file so this
        exercises ``main``'s argument parsing without ever touching whatever
        DATABASE_URL names.
        """
        monkeypatch.setattr(mig, "engine", blank_engine)
        mig.upgrade(blank_engine)

        with pytest.raises(SystemExit) as exc:
            mig.main(["--down"])

        assert exc.value.code
        assert inspect(blank_engine).has_table("routes")
