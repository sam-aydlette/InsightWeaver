"""
Migration: Add the operator calibration loop (2026-08-27, backlog task 011)

Two tables change, both preserving every existing row:

``questions``  gains ``cadence`` and ``last_reviewed_at``. Purely additive --
two nullable columns via ALTER TABLE. Every pre-existing question keeps a null
cadence, which is correct: it was surfaced by the model from coverage, not put
on a review schedule by the operator, so ``forecast --due`` never raises it.

``predictions`` gains ``author``, ``due_by``, ``confidence`` and ``outcome``,
and relaxes ``made_in_synthesis_id`` to nullable so a claim the operator stakes
from the CLI -- which has no synthesis behind it -- can be stored at all.
SQLite cannot drop a NOT NULL constraint in place, so this half is the standard
SQLite table rebuild: rename, recreate from the model, copy every row, drop the
old table. Every existing prediction backfills to ``author='model'``, which is
what all of them were.

Reversible. ``downgrade`` restores both tables to their pre-011 shape, and
refuses rather than destroying data if any operator prediction exists: an
operator-staked claim has no representation in the old schema, so silently
dropping or relabelling one would be a lie about who said it.
"""

from sqlalchemy import inspect, text

from src.database.connection import engine
from src.database.models import Prediction, Question

# The pre-011 shape of `predictions`, needed verbatim by downgrade(). Kept as a
# literal rather than derived from the model, because the model has moved on.
_PREDICTIONS_PRE_011_DDL = """
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
	FOREIGN KEY(question_id) REFERENCES questions (id),
	FOREIGN KEY(made_in_synthesis_id) REFERENCES narrative_syntheses (id)
)
"""

_PREDICTIONS_PRE_011_COLUMNS = [
    "id",
    "question_id",
    "observable_text",
    "trigger_condition",
    "made_at",
    "made_in_synthesis_id",
    "status",
    "resolved_at",
    "resolution_note",
]

_PREDICTIONS_PRE_011_INDEXES = [
    "CREATE INDEX idx_prediction_status ON predictions (status)",
    "CREATE INDEX idx_prediction_question ON predictions (question_id)",
    "CREATE INDEX idx_prediction_made_at ON predictions (made_at)",
]

# Every index on `predictions`, old and new. Dropped before a rebuild so the
# names are free: SQLite keeps indexes attached to a table across a RENAME,
# under their original names, which would collide on recreate.
_ALL_PREDICTION_INDEXES = [
    "idx_prediction_status",
    "idx_prediction_question",
    "idx_prediction_made_at",
    "idx_prediction_author",
    "idx_prediction_due_by",
]

_QUESTION_COLUMNS = {
    "cadence": "VARCHAR(20)",
    "last_reviewed_at": "DATETIME",
}


def _column_names(conn, table: str) -> set[str]:
    return {col["name"] for col in inspect(conn).get_columns(table)}


def _has_table(conn, table: str) -> bool:
    return inspect(conn).has_table(table)


def _require_sqlite(conn) -> None:
    """
    The rebuild half is SQLite-specific.

    Failing loudly beats emitting DDL that silently does the wrong thing on
    another engine. InsightWeaver has only ever run on SQLite.
    """
    if conn.dialect.name != "sqlite":
        raise RuntimeError(
            f"This migration rebuilds the predictions table using SQLite semantics; "
            f"the configured database is '{conn.dialect.name}'. Port it before running."
        )


def upgrade():
    """Add the cadence and authorship columns, preserving every row."""
    with engine.begin() as conn:
        _require_sqlite(conn)

        print("Adding review cadence to questions...")
        if not _has_table(conn, "questions"):
            Question.__table__.create(conn, checkfirst=True)
            print("  questions table created")
        else:
            existing = _column_names(conn, "questions")
            for name, sql_type in _QUESTION_COLUMNS.items():
                if name in existing:
                    print(f"  questions.{name} already present, skipping")
                    continue
                conn.execute(text(f"ALTER TABLE questions ADD COLUMN {name} {sql_type}"))
                print(f"  questions.{name} added")

        print("\nAdding authorship, due date and outcome to predictions...")
        if not _has_table(conn, "predictions"):
            Prediction.__table__.create(conn, checkfirst=True)
            print("  predictions table created")
        elif "author" in _column_names(conn, "predictions"):
            print("  predictions already carries author, skipping rebuild")
        else:
            _rebuild_predictions_forward(conn)

    print("\nCalibration loop migration completed.")


def _rebuild_predictions_forward(conn) -> None:
    """
    SQLite table rebuild: relax made_in_synthesis_id and add the new columns.

    Row count is asserted on both sides. A rebuild that quietly lost rows would
    corrupt the one ledger this task exists to make trustworthy.
    """
    before = conn.execute(text("SELECT COUNT(*) FROM predictions")).scalar_one()
    print(f"  rebuilding predictions ({before} row(s) to carry over)")

    for index_name in _ALL_PREDICTION_INDEXES:
        conn.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
    conn.execute(text("ALTER TABLE predictions RENAME TO predictions_pre_011"))

    Prediction.__table__.create(conn, checkfirst=False)

    carried = ", ".join(_PREDICTIONS_PRE_011_COLUMNS)
    conn.execute(
        text(
            f"INSERT INTO predictions ({carried}, author) "
            f"SELECT {carried}, 'model' FROM predictions_pre_011"
        )
    )

    after = conn.execute(text("SELECT COUNT(*) FROM predictions")).scalar_one()
    if after != before:
        raise RuntimeError(
            f"Rebuild carried {after} of {before} predictions. Rolling back; "
            "the database is unchanged."
        )

    conn.execute(text("DROP TABLE predictions_pre_011"))
    print(f"  {after} prediction(s) backfilled to author='model'")


def downgrade():
    """Restore the pre-011 shape of both tables."""
    with engine.begin() as conn:
        _require_sqlite(conn)

        print("Reverting predictions...")
        if not _has_table(conn, "predictions"):
            print("  no predictions table, nothing to revert")
        elif "author" not in _column_names(conn, "predictions"):
            print("  predictions already at the pre-011 shape, skipping")
        else:
            _rebuild_predictions_back(conn)

        print("\nReverting questions...")
        if not _has_table(conn, "questions"):
            print("  no questions table, nothing to revert")
        else:
            existing = _column_names(conn, "questions")
            for name in _QUESTION_COLUMNS:
                if name not in existing:
                    print(f"  questions.{name} already absent, skipping")
                    continue
                conn.execute(text(f"ALTER TABLE questions DROP COLUMN {name}"))
                print(f"  questions.{name} dropped")

    print("\nCalibration loop downgrade completed.")


def _rebuild_predictions_back(conn) -> None:
    """
    Rebuild predictions to the pre-011 shape, or refuse.

    An operator prediction has no synthesis and no author column to live in
    once this runs, so it cannot survive the revert. Refusing is the honest
    answer; quietly relabelling it 'model' would put words in the operator's
    mouth, and dropping it would delete the record silently.
    """
    stakes = conn.execute(
        text("SELECT COUNT(*) FROM predictions WHERE author = 'operator'")
    ).scalar_one()
    if stakes:
        raise RuntimeError(
            f"{stakes} operator prediction(s) are in the ledger. The pre-011 schema "
            "has nowhere to record who staked a claim or when it resolves, so this "
            "downgrade would silently misattribute them. Export or delete them "
            "first if you really mean to revert. Nothing was changed."
        )

    orphans = conn.execute(
        text("SELECT COUNT(*) FROM predictions WHERE made_in_synthesis_id IS NULL")
    ).scalar_one()
    if orphans:
        raise RuntimeError(
            f"{orphans} prediction(s) have no synthesis, which the pre-011 schema "
            "requires. Nothing was changed."
        )

    before = conn.execute(text("SELECT COUNT(*) FROM predictions")).scalar_one()
    print(f"  rebuilding predictions ({before} row(s) to carry over)")

    for index_name in _ALL_PREDICTION_INDEXES:
        conn.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
    conn.execute(text("ALTER TABLE predictions RENAME TO predictions_post_011"))

    conn.execute(text(_PREDICTIONS_PRE_011_DDL))
    for statement in _PREDICTIONS_PRE_011_INDEXES:
        conn.execute(text(statement))

    carried = ", ".join(_PREDICTIONS_PRE_011_COLUMNS)
    conn.execute(
        text(f"INSERT INTO predictions ({carried}) SELECT {carried} FROM predictions_post_011")
    )

    after = conn.execute(text("SELECT COUNT(*) FROM predictions")).scalar_one()
    if after != before:
        raise RuntimeError(
            f"Revert carried {after} of {before} predictions. Rolling back; "
            "the database is unchanged."
        )

    conn.execute(text("DROP TABLE predictions_post_011"))
    print(f"  {after} prediction(s) restored")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "down":
        downgrade()
    else:
        upgrade()
