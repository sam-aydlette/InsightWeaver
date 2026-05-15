"""
Diet Command - Surface the editorial structure of your information diet.

Derived entirely from the article_frames mapping: which frames each feed
carries, which frames are absent, and which frames only one feed supplies.
"""

import click
from sqlalchemy import func

from ..database.connection import get_db
from ..database.models import (
    Article,
    ArticleFrame,
    FrameGap,
    NarrativeFrame,
    RSSFeed,
    TopicCluster,
)
from .colors import accent, header, muted, warning


@click.group(name="diet")
def diet_command():
    """Inspect the editorial structure of your feed set."""
    pass


@diet_command.command(name="feeds")
def feeds_fingerprint():
    """Per-feed frame fingerprint: which frames each feed carries."""
    with get_db() as session:
        rows = (
            session.query(
                RSSFeed.name,
                NarrativeFrame.label,
                func.count(ArticleFrame.id),
            )
            .join(Article, ArticleFrame.article_id == Article.id)
            .join(RSSFeed, Article.feed_id == RSSFeed.id)
            .join(NarrativeFrame, ArticleFrame.frame_id == NarrativeFrame.id)
            .group_by(RSSFeed.name, NarrativeFrame.label)
            .order_by(RSSFeed.name, func.count(ArticleFrame.id).desc())
            .all()
        )

        if not rows:
            click.echo(muted("No frame classifications yet. Run a brief first."))
            return

        by_feed: dict[str, list[tuple[str, int]]] = {}
        for feed_name, frame_label, count in rows:
            by_feed.setdefault(feed_name, []).append((frame_label, count))

        click.echo(header("FEED FRAME FINGERPRINTS"))
        click.echo("=" * 80)
        for feed_name, frames in by_feed.items():
            click.echo(accent(feed_name))
            for frame_label, count in frames:
                click.echo(f"  {frame_label} {muted(f'({count})')}")
            click.echo()


@diet_command.command(name="gaps")
def diet_gaps():
    """Recurring frame absences -- a feed curation signal."""
    with get_db() as session:
        rows = (
            session.query(FrameGap, TopicCluster.name)
            .join(TopicCluster, FrameGap.topic_cluster_id == TopicCluster.id)
            .order_by(FrameGap.occurrences.desc())
            .all()
        )

        if not rows:
            click.echo(muted("No frame gaps recorded yet."))
            return

        click.echo(header("RECURRING FRAME GAPS"))
        click.echo(muted("Frames consistently absent from your feeds."))
        click.echo("=" * 80)
        for gap, cluster_name in rows:
            click.echo(
                f"{warning(gap.frame_label)} {muted(f'({gap.occurrences}x, in {cluster_name})')}"
            )
            if gap.feed_suggestion:
                click.echo(f"  Suggested source: {muted(gap.feed_suggestion)}")
            click.echo()


@diet_command.command(name="overlap")
def diet_overlap():
    """Which frames only one feed carries, and which are widely carried."""
    with get_db() as session:
        rows = (
            session.query(
                NarrativeFrame.label,
                func.count(func.distinct(RSSFeed.id)),
            )
            .join(ArticleFrame, ArticleFrame.frame_id == NarrativeFrame.id)
            .join(Article, ArticleFrame.article_id == Article.id)
            .join(RSSFeed, Article.feed_id == RSSFeed.id)
            .group_by(NarrativeFrame.label)
            .order_by(func.count(func.distinct(RSSFeed.id)).asc())
            .all()
        )

        if not rows:
            click.echo(muted("No frame classifications yet. Run a brief first."))
            return

        unique = [(label, n) for label, n in rows if n == 1]
        shared = [(label, n) for label, n in rows if n > 1]

        click.echo(header("FRAME OVERLAP"))
        click.echo("=" * 80)

        click.echo(accent("Carried by only one feed (single point of exposure):"))
        if unique:
            for label, _ in unique:
                click.echo(f"  {label}")
        else:
            click.echo(muted("  none"))
        click.echo()

        click.echo(accent("Carried by multiple feeds:"))
        if shared:
            for label, n in shared:
                click.echo(f"  {label} {muted(f'({n} feeds)')}")
        else:
            click.echo(muted("  none"))
