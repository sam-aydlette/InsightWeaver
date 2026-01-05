"""
Anomaly Detection for Article Coverage
Detects unusual patterns in article topics/sources compared to baseline
"""

import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from ..database.models import Article

logger = logging.getLogger(__name__)


class CoverageAnomalyDetector:
    """Detects unusual patterns in article coverage"""

    def __init__(self, baseline_days: int = 30):
        """
        Initialize anomaly detector

        Args:
            baseline_days: Days to look back for baseline calculation
        """
        self.baseline_days = baseline_days

    def detect_anomalies(
        self,
        session: Session,
        current_articles: list[Article],
        current_hours: int = 48
    ) -> dict[str, Any]:
        """
        Detect coverage anomalies by comparing current period to baseline

        Args:
            session: Database session
            current_articles: Articles from current period
            current_hours: Hours covered by current articles

        Returns:
            Anomaly report dictionary
        """
        # Get baseline from previous period
        baseline_end = datetime.utcnow() - timedelta(hours=current_hours)
        baseline_start = baseline_end - timedelta(days=self.baseline_days)

        baseline_articles = session.query(Article).filter(
            Article.fetched_at >= baseline_start,
            Article.fetched_at < baseline_end,
            Article.filtered == False
        ).all()

        if not baseline_articles:
            return {
                "has_baseline": False,
                "message": "Insufficient historical data for anomaly detection"
            }

        # Analyze current vs baseline
        current_stats = self._analyze_articles(current_articles)
        baseline_stats = self._analyze_articles(baseline_articles)

        # Normalize to same time period
        baseline_period_count = len(baseline_articles) / (self.baseline_days * 24) * current_hours
        current_count = len(current_articles)

        # Detect anomalies
        anomalies = []

        # Volume anomaly
        if current_count > baseline_period_count * 1.5:
            anomalies.append({
                "type": "volume_spike",
                "severity": "medium",
                "description": f"Article volume {int((current_count/baseline_period_count - 1) * 100)}% above baseline",
                "current": current_count,
                "baseline": int(baseline_period_count)
            })
        elif current_count < baseline_period_count * 0.5:
            anomalies.append({
                "type": "volume_drop",
                "severity": "low",
                "description": f"Article volume {int((1 - current_count/baseline_period_count) * 100)}% below baseline",
                "current": current_count,
                "baseline": int(baseline_period_count)
            })

        # Topic anomalies (keywords in titles)
        topic_anomalies = self._detect_topic_anomalies(
            current_stats['top_keywords'],
            baseline_stats['top_keywords']
        )
        anomalies.extend(topic_anomalies)

        # Source anomalies
        source_anomalies = self._detect_source_anomalies(
            current_stats['source_distribution'],
            baseline_stats['source_distribution'],
            current_hours,
            self.baseline_days
        )
        anomalies.extend(source_anomalies)

        return {
            "has_baseline": True,
            "baseline_period": f"{self.baseline_days} days",
            "current_period": f"{current_hours} hours",
            "current_article_count": current_count,
            "baseline_article_count": int(baseline_period_count),
            "anomalies": anomalies,
            "summary": self._generate_summary(anomalies)
        }

    def _analyze_articles(self, articles: list[Article]) -> dict[str, Any]:
        """Analyze articles for patterns"""
        # Extract keywords from titles (simple approach)
        all_words = []
        for article in articles:
            if article.title:
                # Simple keyword extraction: words longer than 4 chars, lowercase
                words = [w.lower() for w in article.title.split() if len(w) > 4 and w.isalnum()]
                all_words.extend(words)

        keyword_counts = Counter(all_words)

        # Source distribution
        sources = [a.feed.name if a.feed else "Unknown" for a in articles]
        source_counts = Counter(sources)

        return {
            "top_keywords": keyword_counts.most_common(20),
            "source_distribution": dict(source_counts)
        }

    def _detect_topic_anomalies(
        self,
        current_keywords: list[tuple],
        baseline_keywords: list[tuple]
    ) -> list[dict[str, Any]]:
        """Detect unusual topic coverage"""
        anomalies = []

        # Convert to dicts for easier lookup
        current_dict = dict(current_keywords)
        baseline_dict = dict(baseline_keywords)

        # Find emerging topics (in current but not in baseline top 20)
        baseline_words = set(w for w, _ in baseline_keywords)
        for word, count in current_keywords[:10]:  # Check top 10 current
            if word not in baseline_words and count >= 3:
                anomalies.append({
                    "type": "emerging_topic",
                    "severity": "medium",
                    "description": f"Unusual coverage of '{word}' ({count} mentions)",
                    "keyword": word,
                    "mentions": count
                })

        # Find missing topics (in baseline top 10 but absent from current)
        current_words = set(w for w, _ in current_keywords)
        for word, baseline_count in baseline_keywords[:10]:
            if word not in current_words:
                anomalies.append({
                    "type": "missing_topic",
                    "severity": "low",
                    "description": f"'{word}' absent (usually ~{baseline_count} mentions)",
                    "keyword": word,
                    "baseline_mentions": baseline_count
                })

        return anomalies[:3]  # Limit to top 3 topic anomalies

    def _detect_source_anomalies(
        self,
        current_sources: dict[str, int],
        baseline_sources: dict[str, int],
        current_hours: int,
        baseline_days: int
    ) -> list[dict[str, Any]]:
        """Detect unusual source patterns"""
        anomalies = []

        # Normalize baseline to same time period
        normalization_factor = (baseline_days * 24) / current_hours

        # Check for sources with unusual volume
        for source, current_count in current_sources.items():
            baseline_count = baseline_sources.get(source, 0) / normalization_factor

            if baseline_count > 0:
                ratio = current_count / baseline_count
                if ratio > 2.0:  # Source producing 2x normal volume
                    anomalies.append({
                        "type": "source_spike",
                        "severity": "low",
                        "description": f"{source}: {int((ratio - 1) * 100)}% above normal volume",
                        "source": source,
                        "current": current_count,
                        "baseline": int(baseline_count)
                    })
            elif current_count >= 5:  # New source with significant volume
                anomalies.append({
                    "type": "new_source_active",
                    "severity": "low",
                    "description": f"{source}: New or previously inactive source ({current_count} articles)",
                    "source": source,
                    "current": current_count
                })

        return anomalies[:2]  # Limit to top 2 source anomalies

    def _generate_summary(self, anomalies: list[dict[str, Any]]) -> str:
        """Generate human-readable summary of anomalies"""
        if not anomalies:
            return "Coverage patterns normal compared to baseline"

        high_severity = [a for a in anomalies if a.get('severity') == 'high']
        medium_severity = [a for a in anomalies if a.get('severity') == 'medium']

        if high_severity:
            return f"Significant anomalies detected: {high_severity[0]['description']}"
        elif medium_severity:
            return f"Notable pattern changes: {len(medium_severity)} anomalies detected"
        else:
            return f"Minor deviations from baseline: {len(anomalies)} small anomalies"

    def format_for_context(self, anomaly_report: dict[str, Any]) -> str:
        """Format anomaly report for inclusion in Claude context"""
        if not anomaly_report.get('has_baseline'):
            return ""

        parts = ["<coverage_analysis>"]
        parts.append("## Coverage Pattern Analysis")
        parts.append(f"Comparing current {anomaly_report['current_period']} to {anomaly_report['baseline_period']} baseline:\n")

        parts.append(f"**Article Volume:** {anomaly_report['current_article_count']} articles "
                    f"(baseline: {anomaly_report['baseline_article_count']})\n")

        if anomaly_report['anomalies']:
            parts.append("**Detected Anomalies:**")
            for anomaly in anomaly_report['anomalies']:
                parts.append(f"• {anomaly['description']}")
        else:
            parts.append("**Pattern:** Coverage patterns consistent with baseline")

        parts.append("\n**Analysis Guidance:** Pay attention to topics with unusual coverage patterns. "
                    "Emerging topics may signal important developments. Missing topics may indicate "
                    "gaps in current period or shifts in news cycle.")

        parts.append("</coverage_analysis>")

        return "\n".join(parts)
