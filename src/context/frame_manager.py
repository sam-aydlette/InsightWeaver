"""
Frame Manager
Handles frame discovery, matching, and persistence for the narrative frame glossary.
Called by the synthesizer between Pass 1 (clustering) and Pass 2 (situation synthesis).
"""

import logging
from typing import Any

from ..database.connection import get_db
from ..database.models import FrameGap, NarrativeFrame, TopicCluster
from ..prompts.frames import FRAME_AWARE_SYNTHESIS_PROMPT, FRAME_DISCOVERY_PROMPT
from .claude_client import ClaudeClient

logger = logging.getLogger(__name__)


class FrameManager:
    """Manages the narrative frame glossary lifecycle."""

    def __init__(self, client: ClaudeClient):
        self.client = client

    def find_matching_cluster(self, cluster: dict) -> TopicCluster | None:
        """
        Find an existing TopicCluster that matches this cluster by keyword overlap.

        Returns the matching TopicCluster or None.
        """
        keywords = {kw.lower() for kw in cluster.get("keywords", [])}
        title_words = set(cluster.get("title", "").lower().split())
        match_terms = keywords | title_words

        if not match_terms:
            return None

        try:
            with get_db() as session:
                existing_clusters = session.query(TopicCluster).all()

                best_match = None
                best_overlap = 0

                for tc in existing_clusters:
                    tc_keywords = {kw.lower() for kw in (tc.keywords or [])}
                    tc_name_words = set(tc.name.lower().split())
                    tc_terms = tc_keywords | tc_name_words

                    overlap = len(match_terms & tc_terms)
                    if overlap > best_overlap and overlap >= 2:
                        best_overlap = overlap
                        best_match = tc

                if best_match:
                    # Detach from session before returning
                    session.expunge(best_match)

                return best_match

        except Exception as e:
            logger.error(f"Error finding matching cluster: {e}")
            return None

    def get_validated_frames(self, topic_cluster_id: int) -> list[NarrativeFrame]:
        """Get validated frames for a topic cluster."""
        try:
            with get_db() as session:
                frames = (
                    session.query(NarrativeFrame)
                    .filter_by(topic_cluster_id=topic_cluster_id, validated=True)
                    .all()
                )
                session.expunge_all()
                return frames
        except Exception as e:
            logger.error(f"Error getting validated frames: {e}")
            return []

    def build_frame_aware_prompt(self, topic_name: str, frames: list[NarrativeFrame]) -> str:
        """
        Build FRAME_AWARE_SYNTHESIS_PROMPT for injection into situation synthesis.

        Returns the formatted prompt string to append to the synthesis task.
        """
        frames_yaml = ""
        for frame in frames:
            frames_yaml += f"- **{frame.label}**\n"
            if frame.description:
                frames_yaml += f"  Description: {frame.description}\n"
            if frame.assumptions:
                frames_yaml += f"  Assumes: {frame.assumptions}\n"
            frames_yaml += "\n"

        return FRAME_AWARE_SYNTHESIS_PROMPT.format(
            topic_name=topic_name,
            frames_yaml=frames_yaml,
        )

    async def discover_frames(
        self, cluster_articles: list[dict], cluster: dict
    ) -> dict[str, Any] | None:
        """
        Run frame discovery on a cluster with no known frames.

        Returns the parsed frame discovery result or None on failure.
        """
        # Build article text for the prompt
        article_texts = []
        for i, article in enumerate(cluster_articles, 1):
            title = article.get("title", "Untitled")
            content = article.get("content", article.get("description", ""))
            # Truncate content to keep context manageable
            snippet = content[:500] if content else ""
            article_texts.append(f"[{i}] {title}\n{snippet}")

        articles_text = "\n\n".join(article_texts)
        prompt = FRAME_DISCOVERY_PROMPT.format(articles=articles_text)

        try:
            response = await self.client.analyze(
                system_prompt="You are a media frame analyst. Identify narrative frames in news coverage.",
                user_message=prompt,
                temperature=0.0,
            )

            # Parse JSON response
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            import json

            return json.loads(response.strip())

        except Exception as e:
            logger.error(f"Frame discovery failed for '{cluster.get('title', '')}': {e}")
            return None

    def store_discovered_frames(self, cluster: dict, discovery_result: dict) -> int | None:
        """
        Store frame discovery results in the database.

        Creates a TopicCluster and unvalidated NarrativeFrame records.
        Also creates FrameGap records for absent frames.

        Returns the TopicCluster ID or None on failure.
        """
        try:
            with get_db() as session:
                # Create topic cluster
                tc = TopicCluster(
                    name=cluster.get("title", "Unknown"),
                    keywords=cluster.get("keywords", []),
                )
                session.add(tc)
                session.flush()

                # Store present frames as unvalidated candidates
                for frame_data in discovery_result.get("frames_present", []):
                    frame = NarrativeFrame(
                        topic_cluster_id=tc.id,
                        label=frame_data.get("label", "Unknown"),
                        description=frame_data.get("emphasizes", ""),
                        assumptions=frame_data.get("assumed_premise", ""),
                        validated=False,
                    )
                    session.add(frame)

                # Store absent frames as gaps
                for absent in discovery_result.get("frames_absent", []):
                    # Find matching feed recommendation
                    feed_suggestion = ""
                    for rec in discovery_result.get("gap_recommendations", []):
                        if rec.get("absent_frame_label") == absent.get("label"):
                            feed_suggestion = rec.get("feed_type", "")
                            break

                    gap = FrameGap(
                        topic_cluster_id=tc.id,
                        frame_label=absent.get("label", "Unknown"),
                        occurrences=1,
                        feed_suggestion=feed_suggestion,
                    )
                    session.add(gap)

                session.commit()
                logger.info(
                    f"Stored frame discovery for '{tc.name}': "
                    f"{len(discovery_result.get('frames_present', []))} frames, "
                    f"{len(discovery_result.get('frames_absent', []))} gaps"
                )
                return tc.id

        except Exception as e:
            logger.error(f"Failed to store frame discovery: {e}")
            return None

    def update_frame_gaps(self, topic_cluster_id: int, absent_frame_labels: list[str]):
        """
        Increment gap occurrences for known frames that are absent today.

        Called when FRAME_AWARE_SYNTHESIS_PROMPT identifies absent known frames.
        """
        if not absent_frame_labels:
            return

        try:
            with get_db() as session:
                for label in absent_frame_labels:
                    existing_gap = (
                        session.query(FrameGap)
                        .filter_by(
                            topic_cluster_id=topic_cluster_id,
                            frame_label=label,
                        )
                        .first()
                    )

                    if existing_gap:
                        existing_gap.occurrences += 1
                    else:
                        gap = FrameGap(
                            topic_cluster_id=topic_cluster_id,
                            frame_label=label,
                            occurrences=1,
                        )
                        session.add(gap)

                session.commit()

        except Exception as e:
            logger.error(f"Failed to update frame gaps: {e}")
