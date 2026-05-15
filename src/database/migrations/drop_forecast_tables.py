"""
Migration: Drop forecast subsystem tables.

The standalone forecast subsystem -- a separate Claude pipeline producing
Rumsfeld-bucketed scenarios -- has been replaced by a derived view over the
existing predictions ledger and question graph. Its persistence tables are
no longer populated by any code path.

One-directional: no downgrade. The forecast subsystem itself has been
deleted; recreating the tables would not bring back the producers.
"""

from sqlalchemy import text

from src.database.connection import engine

FORECAST_TABLES = [
    "causal_chains",
    "forecast_scenarios",
    "long_term_forecasts",
    "forecast_runs",
]


def upgrade():
    """Drop forecast tables in FK-safe order."""
    print("Dropping forecast subsystem tables...")
    with engine.begin() as conn:
        for table in FORECAST_TABLES:
            conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
            print(f"  dropped {table} (if it existed)")
    print("Forecast subsystem table drop completed.")


if __name__ == "__main__":
    upgrade()
