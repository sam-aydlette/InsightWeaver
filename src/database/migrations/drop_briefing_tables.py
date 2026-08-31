"""
Migration: drop the tables belonging to the deleted briefing product.

Backlog task 012 deleted the briefing product -- synthesis, rendering, topic
clusters, narrative frames, questions, predictions, decisions and beats. Their
models are gone from ``src/database/models.py``; this drops the tables so that
the schema and the code agree, rather than leaving nineteen unreferenced tables
that read as current to the next person who opens the database.

**This destroys real data.** Measured on the operator's database 2026-08-31:
46 questions, 42 question_situations, 33 predictions, 42 narrative_frames,
39 frame_gaps, 337 provenance_records, 20 article_frames, 14 topic_clusters,
17 beat_entities, 17 entity_mentions, plus the syntheses and runs. That is the
whole record of the product being removed, and none of it is reconstructible
from the articles that remain.

Two guards, because a migration that is one keystroke from unrecoverable should
not be one keystroke from *accidentally* unrecoverable:

1. It refuses to run without ``--confirm``. There is no prompt to hold Enter
   through and no environment variable that quietly enables it in CI.
2. It writes every target table -- schema and rows -- to a timestamped SQL dump
   before dropping anything, and refuses to drop if the dump cannot be written.

**What "reversible" means here.** ``downgrade()`` recreates the dropped tables
from their captured DDL, so the *schema* round-trips. It does not restore rows,
because a dropped row is gone; the dump from step 2 is the only path back to the
data, and restoring it is a deliberate act (``--restore``), not an automatic
one. Saying a destructive migration is "reversible" without that distinction is
the kind of claim this file exists not to make.

``articles`` and ``rss_feeds`` are never touched. ``articles`` holds 55,249 rows
and its fate is backlog task 014's decision, not this migration's -- it is
listed in :data:`PROTECTED_TABLES` and the drop asserts against it.

Added 2026-08-31 for backlog task 012.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.database.connection import engine

__all__ = [
    "BRIEFING_TABLES",
    "PROTECTED_TABLES",
    "capture",
    "downgrade",
    "dump_path",
    "upgrade",
]

# Every table that belonged to a concept task 012 deleted, in dependency order
# (children before parents) so the drops do not trip a foreign key.
BRIEFING_TABLES: tuple[str, ...] = (
    # Frames hang off topic clusters and articles.
    "article_frames",
    "frame_gaps",
    "narrative_frames",
    "topic_clusters",
    # Beat entity observations hang off beats and beat runs.
    "entity_mentions",
    "beat_entities",
    "beat_standing_questions",
    "beat_runs",
    "beats",
    # Decisions.
    "decision_evidence",
    "decision_factors",
    "decisions",
    # The question graph and everything keyed off it.
    "predictions",
    "question_situations",
    "questions",
    # Synthesis outputs and their provenance.
    "provenance_records",
    "narrative_syntheses",
    "context_snapshots",
    "analysis_runs",
)

# Tables this migration must never touch, asserted at runtime rather than left
# to the correctness of the list above. `articles` is task 014's decision.
PROTECTED_TABLES: frozenset[str] = frozenset({"articles", "rss_feeds"})

_CONFIRM_HELP = (
    "This migration permanently drops the briefing tables and the rows in them.\n"
    "Re-run with --confirm once you have read what it will drop:\n\n"
    "    python -m src.database.migrations.drop_briefing_tables --confirm\n"
)


def _guard() -> None:
    """Fail loudly if the drop list and the protected list ever overlap."""
    collision = PROTECTED_TABLES & set(BRIEFING_TABLES)
    if collision:
        raise AssertionError(
            f"refusing to run: protected table(s) {sorted(collision)} appear in the drop list"
        )


def _existing(conn, tables: tuple[str, ...]) -> list[str]:
    """Which of ``tables`` this database actually has, in drop order."""
    present = {
        row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    }
    return [t for t in tables if t in present]


def dump_path(db_url: str, when: datetime | None = None) -> Path:
    """
    Where the pre-drop dump goes: beside the database, stamped with the time.

    Beside the database rather than in the repo, because the dump contains the
    operator's data and the repo is a place things get committed from.
    """
    stamp = (when or datetime.now()).strftime("%Y%m%d-%H%M%S")
    if db_url.startswith("sqlite:///"):
        db_file = Path(db_url.removeprefix("sqlite:///"))
        return db_file.parent / f"{db_file.name}.briefing-tables-{stamp}.sql"
    return Path.cwd() / f"briefing-tables-{stamp}.sql"


def capture(target: Engine, out: Path) -> tuple[Path, dict[str, int]]:
    """
    Write the schema and every row of the briefing tables to ``out``.

    Returns the path written and a ``{table: row_count}`` map. Raises if the
    file cannot be written -- a drop whose backup silently failed is the exact
    accident this function exists to prevent.
    """
    counts: dict[str, int] = {}
    lines: list[str] = [
        "-- Pre-drop capture of the briefing tables (backlog task 012).",
        f"-- Written {datetime.now().isoformat(timespec='seconds')} from {target.url}.",
        "-- Restore with: python -m src.database.migrations.drop_briefing_tables"
        " --restore <this file>",
        "",
    ]
    with target.connect() as conn:
        for table in _existing(conn, BRIEFING_TABLES):
            ddl = conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:n"),
                {"n": table},
            ).scalar()
            lines.append(f"-- {table}")
            if ddl:
                lines.append(f"{ddl};")
            for idx_sql in conn.execute(
                text(
                    "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=:n"
                    " AND sql IS NOT NULL"
                ),
                {"n": table},
            ):
                lines.append(f"{idx_sql[0]};")

            rows = conn.execute(text(f'SELECT * FROM "{table}"'))  # noqa: S608 - fixed list
            cols = list(rows.keys())
            count = 0
            for row in rows:
                values = ", ".join(_sql_literal(v) for v in row)
                collist = ", ".join(f'"{c}"' for c in cols)
                lines.append(f'INSERT INTO "{table}" ({collist}) VALUES ({values});')
                count += 1
            counts[table] = count
            lines.append("")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out, counts


def _sql_literal(value: object) -> str:
    """One Python value as a SQLite literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int | float):
        return repr(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def _statements(body: str) -> list[str]:
    """
    Split a capture file into executable statements.

    Comment lines are stripped *before* splitting, not after. Doing it the other
    way round silently drops the first statement of every table: each ``CREATE
    TABLE`` is preceded by a ``-- <table>`` marker, so the chunk it lands in
    starts with a comment and a naive "does this chunk start with CREATE" filter
    discards it. That produced a downgrade which recreated nothing and a restore
    which then failed on the first INSERT.
    """
    stripped = "\n".join(line for line in body.splitlines() if not line.lstrip().startswith("--"))
    return [s.strip() for s in stripped.split(";\n") if s.strip()]


def upgrade(target: Engine | None = None, *, confirmed: bool = False) -> dict[str, int]:
    """
    Drop every briefing table, after capturing it.

    ``confirmed`` must be True. The flag is a parameter rather than a prompt so
    that the refusal is testable and so that no interactive path exists to
    fat-finger through.
    """
    _guard()
    if not confirmed:
        raise SystemExit(_CONFIRM_HELP)

    target = target or engine
    out, counts = capture(target, dump_path(str(target.url)))
    total = sum(counts.values())
    print(f"Captured {total} row(s) across {len(counts)} table(s) to {out}")

    with target.begin() as conn:
        present = _existing(conn, BRIEFING_TABLES)
        for table in present:
            if table in PROTECTED_TABLES:  # pragma: no cover - _guard covers this
                raise AssertionError(f"refusing to drop protected table {table}")
            conn.execute(text(f'DROP TABLE IF EXISTS "{table}"'))
            print(f"  dropped {table} ({counts.get(table, 0)} row(s))")

    print(f"\nDropped {len(present)} briefing table(s). Data is recoverable only from {out}.")
    return counts


def downgrade(target: Engine | None = None, dump: Path | None = None) -> list[str]:
    """
    Recreate the dropped tables from a capture file, schema only.

    Rows are **not** restored -- use ``--restore`` for that. This exists so the
    schema change round-trips; it cannot undo the data loss and does not claim
    to.
    """
    target = target or engine
    if dump is None:
        raise SystemExit(
            "downgrade needs the capture file written by upgrade:\n"
            "    python -m src.database.migrations.drop_briefing_tables --down <dump.sql>\n"
        )
    statements = [
        s
        for s in _statements(dump.read_text(encoding="utf-8"))
        if s.upper().startswith(("CREATE TABLE", "CREATE INDEX", "CREATE UNIQUE"))
    ]
    recreated: list[str] = []
    with target.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
            recreated.append(stmt.split()[2].strip('"'))
    print(f"Recreated {len(recreated)} object(s), empty. Rows were not restored.")
    return recreated


def restore(target: Engine | None = None, dump: Path | None = None) -> int:
    """Replay a capture file in full, schema and rows. Deliberate and explicit."""
    target = target or engine
    if dump is None:
        raise SystemExit("--restore needs a capture file")
    applied = 0
    with target.begin() as conn:
        for stmt in _statements(dump.read_text(encoding="utf-8")):
            conn.execute(text(stmt))
            applied += 1
    print(f"Replayed {applied} statement(s) from {dump}.")
    return applied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="drop_briefing_tables",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="actually drop the tables (required; there is no prompt)",
    )
    parser.add_argument("--down", type=Path, metavar="DUMP", help="recreate schema from DUMP")
    parser.add_argument(
        "--restore", type=Path, metavar="DUMP", help="replay DUMP in full, schema and rows"
    )
    args = parser.parse_args(argv)

    if args.restore:
        restore(dump=args.restore)
        return 0
    if args.down:
        downgrade(dump=args.down)
        return 0
    upgrade(confirmed=args.confirm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
