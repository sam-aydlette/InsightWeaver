"""
Frames Command - Narrative Frame Glossary Management
Browse, validate, and edit the emergent frame glossary.
"""

import os
import subprocess
import tempfile

import click

from ..database.connection import get_db
from ..database.models import ArticleFrame, FrameGap, NarrativeFrame, TopicCluster
from .colors import accent, error, header, muted, success, warning


@click.group(name="frames")
def frames_command():
    """Manage the narrative frame glossary."""
    pass


@frames_command.command(name="list")
@click.option("--unvalidated", "-u", is_flag=True, help="Show only unvalidated frames")
def list_frames(unvalidated):
    """List all topic clusters and their frames."""
    with get_db() as session:
        clusters = session.query(TopicCluster).order_by(TopicCluster.name).all()

        if not clusters:
            click.echo(muted("No topic clusters found. Run a brief to discover frames."))
            return

        click.echo(header("NARRATIVE FRAME GLOSSARY"))
        click.echo("=" * 70)

        for cluster in clusters:
            frames = (
                session.query(NarrativeFrame)
                .filter_by(topic_cluster_id=cluster.id)
                .order_by(NarrativeFrame.label)
                .all()
            )

            if unvalidated:
                frames = [f for f in frames if not f.validated]
                if not frames:
                    continue

            validated_count = sum(1 for f in frames if f.validated)
            total = len(frames)

            click.echo()
            click.echo(f"{accent(cluster.name)}  {muted(f'[{validated_count}/{total} validated]')}")

            if not frames:
                click.echo(muted("  (no frames discovered yet)"))
                continue

            for frame in frames:
                status = success("[v]") if frame.validated else warning("[?]")
                click.echo(f"  {status} #{frame.id} {frame.label}")

        click.echo()
        click.echo(muted("Use 'frames show <topic>' for details or 'frames edit <id>' to modify."))


@frames_command.command(name="show")
@click.argument("topic")
def show_topic(topic):
    """Show frames for a topic cluster.

    TOPIC can be a cluster name (partial match) or numeric ID.
    """
    with get_db() as session:
        cluster = _find_cluster(session, topic)
        if not cluster:
            click.echo(error(f"No topic cluster matching '{topic}'"))
            return

        frames = (
            session.query(NarrativeFrame)
            .filter_by(topic_cluster_id=cluster.id)
            .order_by(NarrativeFrame.first_seen)
            .all()
        )

        click.echo(header(f"TOPIC: {cluster.name}"))
        click.echo("=" * 70)
        click.echo(f"Keywords: {', '.join(cluster.keywords or [])}")
        click.echo(f"Created: {cluster.created_at.strftime('%Y-%m-%d')}")
        click.echo()

        if not frames:
            click.echo(muted("No frames discovered for this topic yet."))
            return

        for frame in frames:
            status = success("VALIDATED") if frame.validated else warning("UNVALIDATED")
            click.echo(f"{accent(f'#{frame.id}')} {frame.label}  [{status}]")
            click.echo(f"  {frame.description or '(no description)'}")
            if frame.assumptions:
                click.echo(f"  Assumes: {muted(frame.assumptions)}")
            click.echo(f"  First seen: {frame.first_seen.strftime('%Y-%m-%d')}")

            # Show article count using this frame
            article_count = session.query(ArticleFrame).filter_by(frame_id=frame.id).count()
            if article_count:
                click.echo(f"  Articles tagged: {article_count}")
            click.echo()

        # Show gaps for this cluster
        gaps = (
            session.query(FrameGap)
            .filter_by(topic_cluster_id=cluster.id)
            .order_by(FrameGap.occurrences.desc())
            .all()
        )

        if gaps:
            click.echo(header("FRAME GAPS"))
            click.echo("-" * 70)
            for gap in gaps:
                click.echo(
                    f"  {warning('GAP')} {gap.frame_label}  "
                    f"({gap.occurrences} occurrence{'s' if gap.occurrences != 1 else ''})"
                )
                if gap.feed_suggestion:
                    click.echo(f"    Feed suggestion: {muted(gap.feed_suggestion)}")
            click.echo()


@frames_command.command(name="edit")
@click.argument("frame_id", type=int)
def edit_frame(frame_id):
    """Edit a narrative frame in $EDITOR.

    Opens the frame's label, description, and assumptions in your editor.
    Same pattern as git commit.
    """
    with get_db() as session:
        frame = session.query(NarrativeFrame).filter_by(id=frame_id).first()
        if not frame:
            click.echo(error(f"No frame with ID {frame_id}"))
            return

        cluster = session.query(TopicCluster).filter_by(id=frame.topic_cluster_id).first()
        topic_name = cluster.name if cluster else "unknown"

        # Build editable content
        content = (
            f"# Editing frame #{frame.id} for topic: {topic_name}\n"
            f"# Lines starting with # are comments and will be ignored.\n"
            f"# Save and close your editor to apply changes.\n"
            f"# Leave the file empty to cancel.\n"
            f"\n"
            f"label: {frame.label}\n"
            f"description: {frame.description or ''}\n"
            f"assumptions: {frame.assumptions or ''}\n"
        )

        editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vi"))

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", prefix="insightweaver-frame-", delete=False
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            result = subprocess.run([editor, tmp_path])
            if result.returncode != 0:
                click.echo(error("Editor exited with an error. No changes applied."))
                return

            with open(tmp_path) as f:
                edited = f.read()

            # Parse edited content
            parsed = _parse_frame_edit(edited)
            if not parsed:
                click.echo(muted("Empty or unchanged. No changes applied."))
                return

            # Apply changes
            frame.label = parsed.get("label", frame.label)
            frame.description = parsed.get("description", frame.description)
            frame.assumptions = parsed.get("assumptions", frame.assumptions)
            session.commit()

            click.echo(success(f"Frame #{frame_id} updated."))
            click.echo(f"  Label: {frame.label}")
            click.echo(f"  Description: {frame.description}")
            click.echo(f"  Assumptions: {frame.assumptions}")

        finally:
            os.unlink(tmp_path)


@frames_command.command(name="gaps")
@click.option("--min-occurrences", "-m", type=int, default=1, help="Minimum gap occurrences")
def show_gaps(min_occurrences):
    """Show recurring frame gaps across all topics.

    Gaps are perspectives consistently absent from your feeds.
    High-occurrence gaps suggest you should add a feed source.
    """
    with get_db() as session:
        gaps = (
            session.query(FrameGap, TopicCluster)
            .join(TopicCluster, FrameGap.topic_cluster_id == TopicCluster.id)
            .filter(FrameGap.occurrences >= min_occurrences)
            .order_by(FrameGap.occurrences.desc())
            .all()
        )

        if not gaps:
            click.echo(muted("No frame gaps detected yet. Run briefs to discover gaps."))
            return

        click.echo(header("FRAME GAPS -- FEED CURATION SIGNALS"))
        click.echo("=" * 70)
        click.echo()

        for gap, cluster in gaps:
            click.echo(
                f"  {warning(f'[{gap.occurrences}x]')} "
                f"{gap.frame_label}  "
                f"{muted(f'({cluster.name})')}"
            )
            if gap.feed_suggestion:
                click.echo(f"    Suggested feed type: {accent(gap.feed_suggestion)}")
            click.echo(f"    First detected: {gap.first_detected.strftime('%Y-%m-%d')}")
            click.echo()

        click.echo(
            muted(
                "These gaps represent perspectives absent from your current feeds.\n"
                "Consider adding RSS sources for the suggested feed types."
            )
        )


def _find_cluster(session, identifier: str) -> TopicCluster | None:
    """Find a topic cluster by ID or partial name match."""
    # Try numeric ID first
    try:
        cluster_id = int(identifier)
        return session.query(TopicCluster).filter_by(id=cluster_id).first()
    except ValueError:
        pass

    # Try exact name match
    cluster = session.query(TopicCluster).filter(TopicCluster.name.ilike(identifier)).first()
    if cluster:
        return cluster

    # Try partial match
    return session.query(TopicCluster).filter(TopicCluster.name.ilike(f"%{identifier}%")).first()


def _parse_frame_edit(content: str) -> dict | None:
    """Parse the edited frame file content.

    Returns dict with label/description/assumptions, or None if empty.
    """
    lines = [
        line for line in content.strip().splitlines() if not line.startswith("#") and line.strip()
    ]

    if not lines:
        return None

    result = {}
    for line in lines:
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()
            if key in ("label", "description", "assumptions") and value:
                result[key] = value

    return result if result else None


def run_frame_validation_loop():
    """
    Interactive frame validation loop.

    Called at the end of a brief run when unvalidated frames exist.
    Shows each candidate frame and prompts: y/n/edit/skip.
    'edit' opens $EDITOR with the frame pre-populated (same pattern as git commit).
    'skip' exits the loop, leaving remaining frames for next time.

    Returns the number of frames validated.
    """
    try:
        return _run_frame_validation_loop_inner()
    except Exception:
        # Frame tables may not exist yet -- don't crash the brief
        return 0


def _run_frame_validation_loop_inner():
    with get_db() as session:
        unvalidated = (
            session.query(NarrativeFrame, TopicCluster)
            .join(TopicCluster, NarrativeFrame.topic_cluster_id == TopicCluster.id)
            .filter(NarrativeFrame.validated.is_(False))
            .order_by(NarrativeFrame.first_seen.desc())
            .all()
        )

        if not unvalidated:
            return 0

        click.echo()
        click.echo(header("FRAME VALIDATION"))
        click.echo("=" * 70)
        click.echo(
            f"{len(unvalidated)} unvalidated frame{'s' if len(unvalidated) != 1 else ''} "
            f"discovered. Review each one:"
        )
        click.echo(muted("  y = accept  |  n = reject  |  edit = open in $EDITOR  |  skip = stop"))
        click.echo()

        validated_count = 0

        for frame, cluster in unvalidated:
            click.echo(f"{accent(f'#{frame.id}')} {frame.label}")
            click.echo(f"  Topic: {cluster.name}")
            click.echo(f"  Description: {frame.description or '(none)'}")
            click.echo(f"  Assumes: {muted(frame.assumptions or '(none)')}")

            # Show article count
            article_count = session.query(ArticleFrame).filter_by(frame_id=frame.id).count()
            if article_count:
                click.echo(f"  Articles tagged: {article_count}")

            click.echo()

            while True:
                choice = click.prompt(
                    "  Action", type=click.Choice(["y", "n", "edit", "skip"]), show_choices=True
                )

                if choice == "y":
                    frame.validated = True
                    session.commit()
                    click.echo(success("  Accepted."))
                    validated_count += 1
                    break
                elif choice == "n":
                    session.delete(frame)
                    session.commit()
                    click.echo(muted("  Rejected and removed."))
                    break
                elif choice == "edit":
                    _edit_frame_inline(session, frame, cluster.name)
                    # After edit, mark as validated
                    frame.validated = True
                    session.commit()
                    click.echo(success("  Edited and accepted."))
                    validated_count += 1
                    break
                elif choice == "skip":
                    click.echo(muted("  Skipping remaining frames."))
                    return validated_count

            click.echo()

        if validated_count:
            click.echo(success(f"Validated {validated_count} frame(s)."))

        return validated_count


def _edit_frame_inline(_session, frame: NarrativeFrame, topic_name: str):
    """Open a frame in $EDITOR for editing."""
    content = (
        f"# Editing frame #{frame.id} for topic: {topic_name}\n"
        f"# Lines starting with # are comments and will be ignored.\n"
        f"\n"
        f"label: {frame.label}\n"
        f"description: {frame.description or ''}\n"
        f"assumptions: {frame.assumptions or ''}\n"
    )

    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vi"))

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", prefix="insightweaver-frame-", delete=False
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        subprocess.run([editor, tmp_path])

        with open(tmp_path) as f:
            edited = f.read()

        parsed = _parse_frame_edit(edited)
        if parsed:
            frame.label = parsed.get("label", frame.label)
            frame.description = parsed.get("description", frame.description)
            frame.assumptions = parsed.get("assumptions", frame.assumptions)
    finally:
        os.unlink(tmp_path)
