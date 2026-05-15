"""
Sources Command - Calibration by structural behavior, not by static dial.

Two derived signals per feed, computed on demand from the article_frames
mapping and recorded frame gaps:

- frame_uniqueness: fraction of this feed's frame-tagged articles whose
  frame is carried by no other feed (a high score means this source is
  a single point of exposure for those frames).
- gap_filling: fraction of recorded frame-gap labels that this feed's
  articles have been tagged with (a high score means this source carries
  perspectives the rest of the corpus has been missing).

Claim survival -- the third signal from the original plan -- is deliberately
omitted. Computing it would require structured claim extraction we have not
built. We do not fabricate metrics; revisit if claim extraction lands.
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
)
from .colors import accent, header, muted


def _compute_calibration(session) -> dict[int, dict]:
    """Returns ``{feed_id: {name, uniqueness, gap_filling, tagged_articles}}``."""
    feeds = session.query(RSSFeed).all()
    if not feeds:
        return {}

    # frame_id -> distinct feed count
    frame_feed_counts = dict(
        session.query(
            NarrativeFrame.id,
            func.count(func.distinct(RSSFeed.id)),
        )
        .join(ArticleFrame, ArticleFrame.frame_id == NarrativeFrame.id)
        .join(Article, ArticleFrame.article_id == Article.id)
        .join(RSSFeed, Article.feed_id == RSSFeed.id)
        .group_by(NarrativeFrame.id)
        .all()
    )
    unique_frame_ids = {fid for fid, n in frame_feed_counts.items() if n == 1}

    # Distinct gap frame_labels (case-normalized) we have on record.
    gap_labels = {
        row[0].strip().lower()
        for row in session.query(FrameGap.frame_label).distinct().all()
        if row[0]
    }

    result: dict[int, dict] = {}
    for feed in feeds:
        # All frame-tagged articles in this feed.
        tagged_q = (
            session.query(ArticleFrame, NarrativeFrame.label, NarrativeFrame.id)
            .join(NarrativeFrame, ArticleFrame.frame_id == NarrativeFrame.id)
            .join(Article, ArticleFrame.article_id == Article.id)
            .filter(Article.feed_id == feed.id)
            .all()
        )
        tagged = len(tagged_q)
        unique_tags = sum(1 for _af, _label, fid in tagged_q if fid in unique_frame_ids)
        uniqueness = (unique_tags / tagged) if tagged else 0.0

        # Distinct frame labels this feed carries (case-normalized).
        feed_labels = {label.strip().lower() for _af, label, _fid in tagged_q if label}
        gap_filling = len(gap_labels & feed_labels) / len(gap_labels) if gap_labels else 0.0

        result[feed.id] = {
            "name": feed.name,
            "uniqueness": uniqueness,
            "gap_filling": gap_filling,
            "tagged_articles": tagged,
        }
    return result


@click.group(name="sources")
def sources_command():
    """Calibration of each feed by structural behavior."""
    pass


@sources_command.command(name="list")
def list_sources():
    """Show all feeds with derived calibration signals."""
    with get_db() as session:
        cal = _compute_calibration(session)
        if not cal:
            click.echo(muted("No feeds configured."))
            return

        click.echo(header("SOURCE CALIBRATION"))
        click.echo(
            muted(
                "Frame uniqueness: how much of what this source carries no other "
                "feed does.\nGap filling: share of recorded frame gaps this source covers."
            )
        )
        click.echo("=" * 80)

        # Sort by uniqueness descending so the standout sources surface first.
        for _fid, row in sorted(cal.items(), key=lambda kv: -kv[1]["uniqueness"]):
            tagged = row["tagged_articles"]
            click.echo(accent(row["name"]))
            if tagged == 0:
                click.echo(muted("  no frame-tagged articles yet"))
            else:
                click.echo(
                    f"  uniqueness:  {row['uniqueness']:.0%}  "
                    f"gap-filling: {row['gap_filling']:.0%}  "
                    f"{muted(f'({tagged} tagged article(s))')}"
                )
            click.echo()


@sources_command.command(name="show")
@click.argument("name")
def show_source(name):
    """Show detailed calibration for a feed by exact or partial name."""
    with get_db() as session:
        feed = session.query(RSSFeed).filter(RSSFeed.name.ilike(f"%{name}%")).first()
        if not feed:
            click.echo(muted(f"No feed matching '{name}'."))
            return

        cal = _compute_calibration(session).get(feed.id)
        if cal is None:
            click.echo(muted(f"No calibration available for {feed.name}."))
            return

        click.echo(header(f"SOURCE: {feed.name}"))
        click.echo("=" * 80)
        click.echo(f"  uniqueness:    {cal['uniqueness']:.0%}")
        click.echo(f"  gap-filling:   {cal['gap_filling']:.0%}")
        click.echo(f"  tagged articles: {cal['tagged_articles']}")
        click.echo()

        rows = (
            session.query(NarrativeFrame.label, func.count(ArticleFrame.id))
            .select_from(ArticleFrame)
            .join(NarrativeFrame, ArticleFrame.frame_id == NarrativeFrame.id)
            .join(Article, ArticleFrame.article_id == Article.id)
            .filter(Article.feed_id == feed.id)
            .group_by(NarrativeFrame.label)
            .order_by(func.count(ArticleFrame.id).desc())
            .all()
        )
        if rows:
            click.echo(header("Frames carried"))
            for label, count in rows:
                click.echo(f"  {label} {muted(f'({count} article(s))')}")
