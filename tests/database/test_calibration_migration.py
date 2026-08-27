"""
Tests for the add_calibration_loop migration (backlog task 011).

The migration rebuilds `predictions` to relax a NOT NULL constraint, which
SQLite cannot do in place. A rebuild that lost or misattributed a row would
corrupt the ledger this feature exists to make trustworthy, so it is exercised
against the real pre-011 DDL rather than against the current model.
"""

import pytest
from sqlalchemy import create_engine, inspect, text

from src.database.migrations import add_calibration_loop

# The exact shape `predictions` and `questions` had before this migration,
# copied from a live database on 2026-08-27.
_PRE_011_SCHEMA = [
    """
    CREATE TABLE questions (
        id INTEGER NOT NULL,
        text TEXT NOT NULL,
        normalized_text TEXT NOT NULL,
        first_asked_at DATETIME NOT NULL,
        status VARCHAR(20) NOT NULL,
        resolved_at DATETIME,
        resolution_note TEXT,
        previous_question_id INTEGER,
        is_primary BOOLEAN NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(previous_question_id) REFERENCES questions (id)
    )
    """,
    "CREATE INDEX idx_question_status ON questions (status)",
    """
    CREATE TABLE predictions (
        id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        observable_text TEXT NOT NULL,
        trigger_condition TEXT NOT NULL,
        made_at DATETIME NOT NULL,
        made_in_synthesis_id INTEGER NOT NULL,
        status VARCHAR(20) NOT NULL,
        resolved_at DATETIME,
        resolution_note TEXT,
        PRIMARY KEY (id),
        FOREIGN KEY(question_id) REFERENCES questions (id)
    )
    """,
    "CREATE INDEX idx_prediction_status ON predictions (status)",
    "CREATE INDEX idx_prediction_question ON predictions (question_id)",
    "CREATE INDEX idx_prediction_made_at ON predictions (made_at)",
]


@pytest.fixture
def legacy_engine(tmp_path, monkeypatch):
    """A database at the pre-011 shape, with the migration pointed at it."""
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        for statement in _PRE_011_SCHEMA:
            conn.execute(text(statement))
        conn.execute(
            text(
                "INSERT INTO questions (id, text, normalized_text, first_asked_at, "
                "status, is_primary) VALUES (1, 'Will it slip?', 'will it slip', "
                "'2026-01-01 00:00:00', 'open', 1)"
            )
        )
        for i in range(1, 4):
            conn.execute(
                text(
                    "INSERT INTO predictions (id, question_id, observable_text, "
                    "trigger_condition, made_at, made_in_synthesis_id, status) VALUES "
                    f"({i}, 1, 'observable {i}', 'trigger {i}', '2026-02-0{i} 00:00:00', 7, 'open')"
                )
            )
    monkeypatch.setattr(add_calibration_loop, "engine", engine)
    return engine


def _columns(engine, table):
    with engine.connect() as conn:
        return {col["name"] for col in inspect(conn).get_columns(table)}


class TestUpgrade:
    def test_adds_cadence_columns_to_questions(self, legacy_engine):
        add_calibration_loop.upgrade()

        assert {"cadence", "last_reviewed_at"} <= _columns(legacy_engine, "questions")

    def test_adds_the_authorship_columns_to_predictions(self, legacy_engine):
        add_calibration_loop.upgrade()

        assert {"author", "due_by", "confidence", "outcome"} <= _columns(
            legacy_engine, "predictions"
        )

    def test_carries_every_existing_row_and_backfills_author_to_model(self, legacy_engine):
        add_calibration_loop.upgrade()

        with legacy_engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, observable_text, author FROM predictions ORDER BY id")
            ).all()
        assert [r[0] for r in rows] == [1, 2, 3]
        assert [r[1] for r in rows] == ["observable 1", "observable 2", "observable 3"]
        assert {r[2] for r in rows} == {"model"}

    def test_made_in_synthesis_id_becomes_nullable(self, legacy_engine):
        """The whole reason for the rebuild: an operator claim has no synthesis."""
        add_calibration_loop.upgrade()

        with legacy_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO predictions (question_id, observable_text, "
                    "trigger_condition, made_at, status, author) VALUES "
                    "(1, 'Yes -- slips', 'Operator judgement.', "
                    "'2026-08-27 00:00:00', 'open', 'operator')"
                )
            )
            stored = conn.execute(
                text("SELECT made_in_synthesis_id FROM predictions WHERE author = 'operator'")
            ).scalar_one()
        assert stored is None

    def test_is_idempotent(self, legacy_engine):
        add_calibration_loop.upgrade()
        add_calibration_loop.upgrade()

        with legacy_engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM predictions")).scalar_one() == 3

    def test_leaves_no_scratch_table_behind(self, legacy_engine):
        add_calibration_loop.upgrade()

        with legacy_engine.connect() as conn:
            names = set(inspect(conn).get_table_names())
        assert "predictions_pre_011" not in names


class TestDowngrade:
    def test_restores_the_pre_011_shape(self, legacy_engine):
        add_calibration_loop.upgrade()
        add_calibration_loop.downgrade()

        assert {"author", "due_by", "confidence", "outcome"}.isdisjoint(
            _columns(legacy_engine, "predictions")
        )
        assert {"cadence", "last_reviewed_at"}.isdisjoint(_columns(legacy_engine, "questions"))
        with legacy_engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM predictions")).scalar_one() == 3

    def test_refuses_rather_than_misattributing_an_operator_claim(self, legacy_engine):
        add_calibration_loop.upgrade()
        with legacy_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO predictions (question_id, observable_text, "
                    "trigger_condition, made_at, status, author) VALUES "
                    "(1, 'Yes -- slips', 'Operator judgement.', "
                    "'2026-08-27 00:00:00', 'open', 'operator')"
                )
            )

        with pytest.raises(RuntimeError, match="operator prediction"):
            add_calibration_loop.downgrade()

        # Refusing must leave the ledger untouched, not half-reverted.
        assert "author" in _columns(legacy_engine, "predictions")
        with legacy_engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM predictions")).scalar_one() == 4
