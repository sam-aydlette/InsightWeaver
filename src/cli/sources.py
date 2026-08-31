"""
Sources command - what is configured, and what it has actually stored.

**This command was reduced, not designed, on 2026-08-31 (backlog task 012).**
It used to report two derived calibration signals per feed -- ``frame
uniqueness`` and ``gap filling`` -- both computed from the ``article_frames``
mapping and recorded frame gaps. Task 012 deleted narrative frames, so both
signals lost their inputs. They are removed rather than reimplemented against
some other proxy: the original module refused to report claim survival because
computing it "would require structured claim extraction we have not built", and
inventing a replacement metric here would break the same rule in the same file.

What is left is the part that does not depend on the deleted product: the feed
inventory and the corpus each feed has actually contributed. That is a real
answer to "which of my sources are pulling their weight" and it is measured, not
derived. Whatever the new pipeline wants to calibrate on, it can add here once
it exists.
"""

import click
from sqlalchemy import func

from ..database.connection import get_db
from ..database.models import Article, RSSFeed
from .colors import accent, header, muted


def _feed_stats(session) -> dict[int, dict]:
    """Returns ``{feed_id: {name, category, is_active, articles, latest, ...}}``."""
    feeds = session.query(RSSFeed).all()
    if not feeds:
        return {}

    counts = dict(
        session.query(Article.feed_id, func.count(Article.id)).group_by(Article.feed_id).all()
    )
    latest = dict(
        session.query(Article.feed_id, func.max(Article.published_date))
        .group_by(Article.feed_id)
        .all()
    )

    return {
        feed.id: {
            "name": feed.name,
            "category": feed.category,
            "is_active": feed.is_active,
            "articles": counts.get(feed.id, 0),
            "latest": latest.get(feed.id),
            "last_fetched": feed.last_fetched,
            "error_count": feed.error_count or 0,
            "last_error": feed.last_error,
        }
        for feed in feeds
    }


@click.group(name="sources")
def sources_command():
    """Configured feeds and the corpus they have contributed."""
    pass


@sources_command.command(name="list")
def list_sources():
    """Show all feeds with stored-article counts."""
    with get_db() as session:
        stats = _feed_stats(session)
        if not stats:
            click.echo(muted("No feeds configured."))
            return

        click.echo(header("SOURCES"))
        click.echo(
            muted(
                "Stored articles per feed. A feed with zero has been configured "
                "but has contributed nothing to the corpus."
            )
        )
        click.echo("=" * 80)

        # Most productive first, so the silent feeds collect at the bottom where
        # they read as the finding they are.
        for _fid, row in sorted(stats.items(), key=lambda kv: -kv[1]["articles"]):
            label = row["name"] if row["is_active"] else f"{row['name']} (inactive)"
            click.echo(accent(label))
            if row["articles"] == 0:
                click.echo(muted("  no stored articles"))
            else:
                newest = row["latest"].date().isoformat() if row["latest"] else "undated"
                click.echo(f"  {row['articles']} article(s)  {muted(f'newest {newest}')}")
            if row["error_count"]:
                click.echo(muted(f"  {row['error_count']} fetch error(s)"))
            click.echo()


@sources_command.command(name="show")
@click.argument("name")
def show_source(name):
    """Show detail for a feed by exact or partial name."""
    with get_db() as session:
        feed = session.query(RSSFeed).filter(RSSFeed.name.ilike(f"%{name}%")).first()
        if not feed:
            click.echo(muted(f"No feed matching '{name}'."))
            return

        row = _feed_stats(session).get(feed.id)
        if row is None:
            click.echo(muted(f"No detail available for {feed.name}."))
            return

        click.echo(header(f"SOURCE: {feed.name}"))
        click.echo("=" * 80)
        click.echo(f"  url:             {feed.url}")
        click.echo(f"  category:        {row['category'] or 'none'}")
        click.echo(f"  active:          {'yes' if row['is_active'] else 'no'}")
        click.echo(f"  stored articles: {row['articles']}")
        newest = row["latest"].date().isoformat() if row["latest"] else "none"
        click.echo(f"  newest article:  {newest}")
        fetched = row["last_fetched"].isoformat(sep=" ") if row["last_fetched"] else "never"
        click.echo(f"  last fetched:    {fetched}")
        if row["error_count"]:
            click.echo(f"  fetch errors:    {row['error_count']}")
            if row["last_error"]:
                click.echo(muted(f"  last error: {row['last_error']}"))
        click.echo()
