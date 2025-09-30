"""
Narrative Synthesis Agent

Multi-hop narrative synthesis with temporal layering that transforms
prioritized articles and trends into personalized, actionable intelligence.
"""

import logging
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.agents.claude_client import ClaudeClient
from src.database.models import Article, NarrativeSynthesis
from src.database.connection import get_db
from src.utils.profile_loader import get_user_profile

logger = logging.getLogger(__name__)


class NarrativeSynthesisAgent(BaseAgent):
    """
    Agent that synthesizes high-priority articles and trends into personalized narratives

    Features:
    - Temporal layering (immediate/near/medium/long-term)
    - Cross-domain connection finding
    - Personal implication generation
    - Actionable recommendations
    """

    def __init__(self):
        super().__init__("NarrativeSynthesisAgent", "1.0")
        self.sonnet_client = ClaudeClient(model="claude-sonnet-4-20250514")  # High-quality synthesis

        # Load user profile
        try:
            self.user_profile = get_user_profile()
            self.logger.info(f"Loaded user profile for narrative synthesis: {self.user_profile}")
        except FileNotFoundError as e:
            self.logger.error(f"User profile required for narrative synthesis: {e}")
            raise

    def _create_temporal_classification_prompt(self) -> str:
        """Create prompt for temporal classification of articles"""

        user_context = self.user_profile.format_for_agent_context()

        return f"""You are analyzing articles to classify them by temporal urgency and time horizon.

{user_context}

For each article, determine the appropriate time horizon based on when action/awareness is needed:

TIME HORIZONS:
- IMMEDIATE (0-48h): Breaking news, immediate decisions, urgent action required
- NEAR_TERM (1-2 weeks): Developing situations, upcoming deadlines, short-term planning
- MEDIUM_TERM (1-3 months): Trends affecting planning, strategic considerations
- LONG_TERM (6+ months): Structural shifts, long-range positioning, fundamental changes

Consider the user's active decisions and priorities when classifying urgency.

Return JSON:
{{
  "temporal_classification": [
    {{
      "article_id": 123,
      "time_horizon": "IMMEDIATE",
      "reasoning": "Brief explanation of timeline",
      "urgency_score": 0.9
    }}
  ]
}}"""

    def _create_synthesis_prompt(self, temporal_data: Dict[str, List[Dict]], trend_data: Optional[Dict] = None) -> str:
        """Create comprehensive synthesis prompt"""

        user_context = self.user_profile.format_for_agent_context()
        prof_domains = ', '.join(self.user_profile.get_professional_domains()[:3])
        priority_topics = ', '.join(self.user_profile.get_personal_priorities().get('priority_topics', [])[:5])
        active_decisions = ', '.join(self.user_profile.get_personal_priorities().get('active_decisions', [])[:3])

        return f"""You are a senior intelligence analyst creating a personalized intelligence brief.

{user_context}

KEY FOCUS AREAS:
- Professional: {prof_domains}
- Priority Topics: {priority_topics}
- Active Decisions: {active_decisions}

You have articles classified into time horizons and trend analysis data. Your task is to synthesize this into a coherent, actionable narrative.

SYNTHESIS REQUIREMENTS:

1. TEMPORAL NARRATIVES: For each time horizon, write a narrative paragraph that:
   - Connects related articles into a coherent story
   - Explains WHY this matters to the user specifically
   - Identifies cause-effect relationships
   - Provides context and implications

2. CROSS-DOMAIN INSIGHTS: Identify connections ACROSS time horizons and topics:
   - How does an immediate event relate to long-term trends?
   - What patterns emerge across different domains?
   - Are there contradictions or confirming signals?

3. PERSONAL IMPLICATIONS: For each major theme, explain:
   - How this affects the user's professional work
   - Impact on active decisions (homebuying, career, etc.)
   - What the user should monitor or consider

4. PRIORITY ACTIONS: Specific, actionable recommendations organized by urgency

5. EXECUTIVE SUMMARY: 2-3 paragraphs synthesizing the most important insights

Return this EXACT JSON structure:
{{
  "temporal_layers": {{
    "immediate": {{
      "narrative": "Paragraph connecting immediate articles into story with personal relevance",
      "article_ids": [123, 456],
      "key_implications": ["implication 1", "implication 2"],
      "recommended_actions": ["action 1", "action 2"]
    }},
    "near_term": {{ ... same structure ... }},
    "medium_term": {{ ... same structure ... }},
    "long_term": {{ ... same structure ... }}
  }},
  "cross_domain_insights": [
    {{
      "theme": "Concise theme title",
      "connected_items": ["article_123", "article_456", "trend_xyz"],
      "narrative": "Paragraph explaining the connection and why it matters",
      "personal_impact": "How this specifically affects the user",
      "confidence": 0.8
    }}
  ],
  "executive_summary": "2-3 paragraph synthesis of the most important insights tailored to user context",
  "priority_actions": [
    {{
      "action": "Specific actionable recommendation",
      "urgency": "immediate|near|medium|long",
      "reasoning": "Why this action matters",
      "related_items": ["article_123", "trend_xyz"]
    }}
  ],
  "synthesis_metadata": {{
    "dominant_themes": ["theme1", "theme2", "theme3"],
    "overall_sentiment": "positive|negative|mixed|neutral",
    "certainty_level": 0.75
  }}
}}

Be decisive, insightful, and focus on actionable intelligence. Write narratives in clear, engaging prose."""

    def _format_synthesis_context(self, temporal_data: Dict[str, List[Dict]], trend_data: Optional[Dict] = None) -> str:
        """Format temporal data and trends into user prompt"""
        import json

        # Format temporal data
        context_text = "TEMPORAL ARTICLE DATA:\n\n"

        for horizon, articles in temporal_data.items():
            if articles:
                context_text += f"\n{horizon.upper().replace('_', ' ')} ({len(articles)} articles):\n"
                for i, article in enumerate(articles, 1):
                    context_text += f"\nArticle {article['id']}:\n"
                    context_text += f"  Title: {article['title']}\n"
                    context_text += f"  Summary: {article['content'][:400]}...\n"

        # Add trend data if available
        if trend_data:
            context_text += "\n\nTREND ANALYSIS DATA:\n\n"
            context_text += json.dumps(trend_data, indent=2)

        # Add user profile summary
        context_text += "\n\nUSER PROFILE:\n"
        context_text += f"Location: {self.user_profile.get_primary_location()}\n"
        context_text += f"Professional Domains: {', '.join(self.user_profile.get_professional_domains())}\n"
        context_text += f"Active Decisions: {', '.join(self.user_profile.get_personal_priorities().get('active_decisions', []))}\n"

        return context_text

    def _intelligent_sample(self, articles: List[Article], target_count: int) -> List[Article]:
        """
        Intelligently sample articles for synthesis to ensure diversity and quality

        Strategy:
        - Take top 30 by priority score (highest confidence)
        - Cluster remaining by topic keywords
        - Sample 2-3 from each cluster (up to 20 total) for diversity

        Args:
            articles: List of articles sorted by priority score (descending)
            target_count: Target number of articles (typically 50)

        Returns:
            Sampled list of articles
        """
        from collections import defaultdict
        import re

        # Step 1: Take top articles by score
        top_count = int(target_count * 0.6)  # 60% = top 30 for target of 50
        selected = articles[:top_count]
        remaining = articles[top_count:]

        self.logger.info(f"Selected top {len(selected)} articles by priority score")

        if not remaining:
            return selected

        # Step 2: Cluster remaining articles by topic keywords
        # Extract key terms from titles for clustering
        topic_clusters = defaultdict(list)

        for article in remaining:
            title = (article.title or "").lower()

            # Define topic keywords (can be expanded)
            topic_keywords = {
                'ai': ['ai', 'artificial intelligence', 'machine learning', 'neural', 'llm', 'gpt'],
                'cyber': ['cyber', 'security', 'hack', 'breach', 'vulnerability', 'ransomware'],
                'policy': ['policy', 'regulation', 'law', 'congress', 'senate', 'bill', 'legislation'],
                'economy': ['economy', 'market', 'inflation', 'federal reserve', 'gdp', 'trade'],
                'tech': ['technology', 'startup', 'innovation', 'patent', 'research'],
                'health': ['health', 'medical', 'vaccine', 'disease', 'hospital', 'cdc'],
                'climate': ['climate', 'energy', 'renewable', 'carbon', 'emissions', 'environment'],
                'military': ['military', 'defense', 'pentagon', 'army', 'navy', 'air force'],
                'space': ['space', 'nasa', 'satellite', 'rocket', 'mars', 'orbital'],
                'local': ['virginia', 'arlington', 'fairfax', 'dc', 'washington']
            }

            # Assign to first matching cluster
            assigned = False
            for topic, keywords in topic_keywords.items():
                if any(keyword in title for keyword in keywords):
                    topic_clusters[topic].append(article)
                    assigned = True
                    break

            # Default cluster for uncategorized
            if not assigned:
                topic_clusters['general'].append(article)

        # Step 3: Sample from each cluster
        diversity_count = target_count - len(selected)
        samples_per_cluster = max(2, diversity_count // len(topic_clusters))

        for topic, cluster_articles in sorted(topic_clusters.items()):
            # Take top-scored articles from this cluster
            cluster_sample = cluster_articles[:samples_per_cluster]
            selected.extend(cluster_sample)

            if len(selected) >= target_count:
                break

        # Trim to exact target if over
        selected = selected[:target_count]

        # Log cluster distribution
        cluster_summary = {topic: len(articles) for topic, articles in topic_clusters.items()}
        self.logger.info(f"Topic clusters found: {cluster_summary}")
        self.logger.info(f"Final sample: {len(selected)} articles with diversity across {len(topic_clusters)} topics")

        return selected

    async def synthesize_narrative(
        self,
        articles: List[Article],
        trend_data: Optional[Dict] = None,
        hours: int = 48
    ) -> Dict[str, Any]:
        """
        Main synthesis method: temporal classification → narrative synthesis

        Args:
            articles: High-priority articles to synthesize
            trend_data: Optional trend analysis results
            hours: Time window for articles

        Returns:
            Complete synthesis results
        """

        if not articles:
            return {
                "synthesis_data": None,
                "executive_summary": "No high-priority articles to synthesize",
                "articles_analyzed": 0
            }

        self.logger.info(f"Synthesizing narrative from {len(articles)} high-priority articles")

        # Prepare article data for analysis
        articles_data = []
        with get_db() as db:
            for article in articles:
                article = db.merge(article)
                articles_data.append({
                    "id": article.id,
                    "title": article.title or "No title",
                    "content": (article.normalized_content or article.description or "")[:3000],
                    "published_date": article.published_date.isoformat() if article.published_date else "Unknown",
                    "source": article.feed.name if article.feed else "Unknown",
                    "priority_score": article.priority_score,
                    "priority_metadata": article.priority_metadata or {},
                    "url": article.url
                })

        # STAGE 1: Temporal Classification
        self.logger.info("Stage 1: Temporal classification of articles...")

        temporal_prompt = self._create_temporal_classification_prompt()

        # Process in reasonable batch sizes to avoid timeouts and rate limits
        TEMPORAL_BATCH_SIZE = 20  # Process 20 articles at a time

        temporal_result = await self.sonnet_client.analyze_batch(
            system_prompt=temporal_prompt,
            articles_data=articles_data,
            batch_size=TEMPORAL_BATCH_SIZE
        )

        temporal_classification = temporal_result[0].get('temporal_classification', []) if temporal_result else []

        # Organize articles by time horizon
        temporal_data = {
            'immediate': [],
            'near_term': [],
            'medium_term': [],
            'long_term': []
        }

        for classification in temporal_classification:
            horizon = classification.get('time_horizon', 'medium_term').lower()
            article_id = classification.get('article_id')

            # Find full article data
            article_full = next((a for a in articles_data if a['id'] == article_id), None)
            if article_full:
                article_full['temporal_reasoning'] = classification.get('reasoning', '')
                article_full['urgency_score'] = classification.get('urgency_score', 0.5)
                temporal_data[horizon].append(article_full)

        self.logger.info(f"Temporal classification: "
                        f"immediate={len(temporal_data['immediate'])}, "
                        f"near={len(temporal_data['near_term'])}, "
                        f"medium={len(temporal_data['medium_term'])}, "
                        f"long={len(temporal_data['long_term'])}")

        # STAGE 2: Comprehensive Narrative Synthesis
        self.logger.info("Stage 2: Generating narrative synthesis...")

        synthesis_prompt = self._create_synthesis_prompt(temporal_data, trend_data)

        # Create user prompt with all context
        user_prompt = self._format_synthesis_context(temporal_data, trend_data)

        # Send to Sonnet for synthesis (use longer timeout for complex synthesis)
        response = await self.sonnet_client.send_message(
            system_prompt=synthesis_prompt,
            user_prompt=user_prompt,
            timeout=120.0  # 2 minutes for narrative synthesis
        )

        if not response:
            raise Exception("Narrative synthesis failed - no response from Sonnet")

        self.logger.debug(f"Raw response type: {type(response)}, length: {len(response) if response else 0}")
        self.logger.debug(f"Response preview: {response[:1000] if response else 'EMPTY'}")

        # Parse JSON response - extract from markdown code blocks if present
        import json
        import re

        response_text = response.strip()

        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)

        try:
            synthesis_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse synthesis response: {e}")
            self.logger.error(f"Response was: {response[:1000]}")
            raise Exception(f"Failed to parse synthesis JSON: {e}")

        # Extract executive summary
        executive_summary = synthesis_data.get('executive_summary', 'No summary generated')

        # Determine temporal scope
        temporal_scope = ','.join([k for k, v in temporal_data.items() if v])

        # Add metadata
        synthesis_data['metadata'] = {
            'synthesis_id': str(uuid.uuid4()),
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'articles_analyzed': len(articles),
            'trends_analyzed': len(trend_data) if trend_data else 0,
            'agent_version': self.agent_version
        }

        self.logger.info(f"Narrative synthesis complete: {len(articles)} articles, "
                        f"{len(synthesis_data.get('cross_domain_insights', []))} cross-domain insights")

        return {
            "synthesis_data": synthesis_data,
            "executive_summary": executive_summary,
            "articles_analyzed": len(articles),
            "trends_analyzed": len(trend_data) if trend_data else 0,
            "temporal_scope": temporal_scope
        }

    async def analyze_articles(self, articles: List[Article]) -> Dict[str, Any]:
        """
        Implementation of base agent abstract method

        Args:
            articles: Articles to analyze (expects high-priority only)

        Returns:
            Synthesis results
        """
        return await self.synthesize_narrative(articles)

    def save_synthesis(self, synthesis_results: Dict[str, Any], analysis_run_id: Optional[int] = None) -> int:
        """
        Save narrative synthesis to database

        Args:
            synthesis_results: Results from synthesize_narrative()
            analysis_run_id: Optional analysis run ID to link to

        Returns:
            Synthesis ID
        """
        with get_db() as db:
            profile_version = self.user_profile.profile.get('profile_metadata', {}).get('version', '1.0')

            synthesis = NarrativeSynthesis(
                analysis_run_id=analysis_run_id,
                user_profile_version=profile_version,
                synthesis_data=synthesis_results['synthesis_data'],
                executive_summary=synthesis_results['executive_summary'],
                articles_analyzed=synthesis_results['articles_analyzed'],
                trends_analyzed=synthesis_results.get('trends_analyzed', 0),
                temporal_scope=synthesis_results.get('temporal_scope', ''),
                generated_at=datetime.now(timezone.utc)
            )

            db.add(synthesis)
            db.commit()

            self.logger.info(f"Saved narrative synthesis with ID {synthesis.id}")
            return synthesis.id

    async def run_synthesis(self, hours: int = 48, min_priority_score: float = 0.7) -> Dict[str, Any]:
        """
        Complete synthesis workflow: fetch high-priority articles → synthesize → save

        Args:
            hours: Time window for articles
            min_priority_score: Minimum priority score threshold

        Returns:
            Complete synthesis results with database ID
        """
        run_id = None
        try:
            # Start analysis run
            run_id = self.start_analysis_run(
                run_type=self.agent_name.lower(),
                metadata={"hours": hours, "min_priority_score": min_priority_score}
            )

            # Get high-priority articles using intelligent sampling
            # Option A+D: Dynamic threshold + intelligent sampling for diversity
            MAX_ARTICLES_FOR_SYNTHESIS = 50
            EXCELLENCE_THRESHOLD = 0.85  # Only truly high-priority articles
            MAX_EXCELLENT_ARTICLES = 100  # Upper bound even for excellent articles

            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

            with get_db() as db:
                # Get articles with dynamic threshold (excellence threshold)
                excellent_articles = db.query(Article).filter(
                    Article.fetched_at >= cutoff_time,
                    Article.priority_score >= EXCELLENCE_THRESHOLD,
                    Article.filtered == False
                ).order_by(Article.priority_score.desc()).limit(MAX_EXCELLENT_ARTICLES).all()

                self.logger.info(f"Found {len(excellent_articles)} articles with score >= {EXCELLENCE_THRESHOLD}")

                # Intelligent sampling if we have more than MAX_ARTICLES_FOR_SYNTHESIS
                if len(excellent_articles) <= MAX_ARTICLES_FOR_SYNTHESIS:
                    articles = excellent_articles
                    self.logger.info(f"Using all {len(articles)} excellent articles (under limit)")
                else:
                    articles = self._intelligent_sample(excellent_articles, MAX_ARTICLES_FOR_SYNTHESIS)
                    self.logger.info(f"Sampled {len(articles)} from {len(excellent_articles)} excellent articles (diversity sampling)")

            self.logger.info(f"Final selection: {len(articles)} articles for synthesis")

            if not articles:
                self.complete_analysis_run(run_id, 0)
                return {
                    "articles_analyzed": 0,
                    "synthesis_data": None,
                    "message": "No high-priority articles found"
                }

            # Run synthesis
            synthesis_results = await self.synthesize_narrative(articles)

            # Save to database
            synthesis_id = self.save_synthesis(synthesis_results, run_id)
            synthesis_results['synthesis_id'] = synthesis_id

            # Complete the run
            self.complete_analysis_run(run_id, len(articles))

            return {
                "analysis_run_id": run_id,
                "synthesis_id": synthesis_id,
                **synthesis_results
            }

        except Exception as e:
            self.logger.error(f"Synthesis failed: {e}")
            if run_id:
                self.complete_analysis_run(run_id, 0, str(e))
            raise