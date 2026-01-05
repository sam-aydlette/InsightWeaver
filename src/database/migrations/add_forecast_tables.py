"""
Migration: Add Forecast Tables
Adds ForecastRun, LongTermForecast, ForecastScenario, and CausalChain tables
for long-term trend forecasting feature
"""
from src.database.connection import engine
from src.database.models import CausalChain, ForecastRun, ForecastScenario, LongTermForecast


def upgrade():
    """Create forecast tables"""
    print("Creating forecast tables...")

    ForecastRun.__table__.create(engine, checkfirst=True)
    print("✓ forecast_runs table created")

    LongTermForecast.__table__.create(engine, checkfirst=True)
    print("✓ long_term_forecasts table created")

    ForecastScenario.__table__.create(engine, checkfirst=True)
    print("✓ forecast_scenarios table created")

    CausalChain.__table__.create(engine, checkfirst=True)
    print("✓ causal_chains table created")

    print("\nForecast tables migration completed successfully!")


def downgrade():
    """Drop forecast tables"""
    print("Dropping forecast tables...")

    CausalChain.__table__.drop(engine, checkfirst=True)
    print("✓ causal_chains table dropped")

    ForecastScenario.__table__.drop(engine, checkfirst=True)
    print("✓ forecast_scenarios table dropped")

    LongTermForecast.__table__.drop(engine, checkfirst=True)
    print("✓ long_term_forecasts table dropped")

    ForecastRun.__table__.drop(engine, checkfirst=True)
    print("✓ forecast_runs table dropped")

    print("\nForecast tables migration rollback completed!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "down":
        downgrade()
    else:
        upgrade()
