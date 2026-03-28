"""
Migration: Add Narrative Frame Tables
Adds TopicCluster, NarrativeFrame, ArticleFrame, and FrameGap tables
for emergent frame discovery and tracking.
"""

from src.database.connection import engine
from src.database.models import ArticleFrame, FrameGap, NarrativeFrame, TopicCluster


def upgrade():
    """Create narrative frame tables."""
    print("Creating narrative frame tables...")

    TopicCluster.__table__.create(engine, checkfirst=True)
    print("  topic_clusters table created")

    NarrativeFrame.__table__.create(engine, checkfirst=True)
    print("  narrative_frames table created")

    ArticleFrame.__table__.create(engine, checkfirst=True)
    print("  article_frames table created")

    FrameGap.__table__.create(engine, checkfirst=True)
    print("  frame_gaps table created")

    print("\nNarrative frame tables migration completed.")


def downgrade():
    """Drop narrative frame tables."""
    print("Dropping narrative frame tables...")

    FrameGap.__table__.drop(engine, checkfirst=True)
    print("  frame_gaps table dropped")

    ArticleFrame.__table__.drop(engine, checkfirst=True)
    print("  article_frames table dropped")

    NarrativeFrame.__table__.drop(engine, checkfirst=True)
    print("  narrative_frames table dropped")

    TopicCluster.__table__.drop(engine, checkfirst=True)
    print("  topic_clusters table dropped")

    print("\nNarrative frame tables downgrade completed.")


if __name__ == "__main__":
    upgrade()
