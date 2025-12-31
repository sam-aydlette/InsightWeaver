"""
Simple script to create forecast tables directly
Bypasses settings import issue
"""
import os
from sqlalchemy import create_engine
from pathlib import Path

# Get database path
project_root = Path(__file__).parent
db_path = project_root / "data" / "insightweaver.db"
db_url = f"sqlite:///{db_path}"

# Create engine
engine = create_engine(db_url)

# Import models
from src.database.models import Base, ForecastRun, LongTermForecast, ForecastScenario, CausalChain

# Create tables
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
