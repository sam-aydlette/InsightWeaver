"""
Migration: Add Decision Journal Tables
Adds Decision, DecisionFactor, and DecisionEvidence. After creating the
tables, seeds them from personal_priorities.active_decisions in the user
profile if the decisions table is empty -- the profile is the seed, the
database is the source of truth from then on.
"""

import logging

from src.database.connection import engine, get_db
from src.database.models import Decision, DecisionEvidence, DecisionFactor

logger = logging.getLogger(__name__)


def _seed_from_profile():
    """Seed decisions from the user profile if the table is empty."""
    try:
        from src.utils.profile_loader import get_user_profile

        profile = get_user_profile()
        active = profile.get_active_decisions()
    except FileNotFoundError:
        print("  no user profile found; skipping decision seeding")
        return
    except Exception as e:
        print(f"  could not read profile decisions; skipping seeding ({e})")
        return

    if not active:
        print("  profile has no active_decisions; nothing to seed")
        return

    with get_db() as session:
        if session.query(Decision).count() > 0:
            print("  decisions table already populated; skipping seeding")
            return

        for entry in active:
            decision = Decision(
                name=entry.get("name", "Unnamed decision"),
                decision_type=entry.get("decision_type", "other"),
            )
            session.add(decision)
            session.flush()
            for factor_name in entry.get("key_factors", []):
                session.add(DecisionFactor(decision_id=decision.id, name=factor_name))
        session.commit()
        print(f"  seeded {len(active)} decisions from profile")


def upgrade():
    """Create decision journal tables and seed from the profile."""
    print("Creating decision journal tables...")
    Decision.__table__.create(engine, checkfirst=True)
    print("  decisions table created")
    DecisionFactor.__table__.create(engine, checkfirst=True)
    print("  decision_factors table created")
    DecisionEvidence.__table__.create(engine, checkfirst=True)
    print("  decision_evidence table created")

    _seed_from_profile()
    print("\nDecision journal migration completed.")


def downgrade():
    """Drop decision journal tables."""
    print("Dropping decision journal tables...")
    DecisionEvidence.__table__.drop(engine, checkfirst=True)
    print("  decision_evidence table dropped")
    DecisionFactor.__table__.drop(engine, checkfirst=True)
    print("  decision_factors table dropped")
    Decision.__table__.drop(engine, checkfirst=True)
    print("  decisions table dropped")
    print("\nDecision journal downgrade completed.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "down":
        downgrade()
    else:
        upgrade()
