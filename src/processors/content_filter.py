"""
Content Filter for InsightWeaver

Filters articles based on user preferences (sports, clickbait, etc.)
Uses hybrid approach: keyword matching + NLP heuristics
"""

import re


class ContentFilter:
    """Filter articles based on user profile content preferences"""

    # Sports keywords - only highly specific terms with no dual-use
    SPORTS_KEYWORDS = {
        # League names (highly specific)
        "nfl",
        "nba",
        "mlb",
        "nhl",
        "mls",
        "ncaa",
        "fifa",
        "uefa",
        "premier league",
        # Sport names
        "football",
        "basketball",
        "baseball",
        "hockey",
        "soccer",
        "tennis",
        "golf",
        "nascar",
        "formula 1",
        # Championship events
        "super bowl",
        "world series",
        "stanley cup",
        "playoffs",
        "olympics",
        # Position-specific terms
        "touchdown",
        "quarterback",
        "pitcher",
        "batter",
        "goalie",
        "striker",
        "innings",
        # Combat sports
        "ufc",
        "boxing match",
        "wrestling match",
        "mma fight",
    }

    # Clickbait indicators - only unambiguous phrases
    CLICKBAIT_KEYWORDS = {
        "you won't believe",
        "mind-blowing",
        "jaw-dropping",
        "goes viral",
        "breaks the internet",
        "what happens next",
        "this one trick",
        "doctors hate",
        "experts hate",
        "literally exploded",
        "won the internet",
        "everyone is talking about",
    }

    # Celebrity/entertainment keywords - remove dual-use terms
    ENTERTAINMENT_KEYWORDS = {
        "celebrity",
        "movie star",
        "red carpet",
        "oscars",
        "grammys",
        "emmys",
        "kardashian",
        "hollywood",
        "fashion week",
        "tiktok trend",
        "instagram model",
        "influencer drama",
        "celebrity gossip",
        "box office",
    }

    def __init__(self, user_profile=None):
        """
        Initialize content filter

        Args:
            user_profile: UserProfile instance with excluded topics
        """
        self.user_profile = user_profile
        self.excluded_topics = []

        if user_profile:
            self.excluded_topics = [topic.lower() for topic in user_profile.get_excluded_topics()]

    def should_filter(
        self, title: str, description: str = "", _content: str = ""
    ) -> tuple[bool, str | None]:
        """
        Determine if article should be filtered based on content

        Args:
            title: Article title
            description: Article description/summary
            content: Full article content (optional)

        Returns:
            Tuple of (should_filter: bool, reason: str)
        """
        # Combine text for analysis
        text = f"{title} {description}".lower()

        # Check user-specified excluded topics first
        for topic in self.excluded_topics:
            if topic in text:
                return True, f"excluded_topic:{topic}"

        # Check for sports content
        if self._is_sports_content(text):
            return True, "sports"

        # Check for clickbait
        if self._is_clickbait(title):
            return True, "clickbait"

        # Check for entertainment/celebrity content
        if self._is_entertainment_content(text):
            return True, "entertainment"

        return False, None

    def _is_sports_content(self, text: str) -> bool:
        """
        Detect sports content using keyword matching

        Args:
            text: Lowercased text to analyze

        Returns:
            True if sports content detected
        """
        # Count sports keyword matches
        matches = sum(1 for keyword in self.SPORTS_KEYWORDS if keyword in text)

        # Threshold: 2+ sports keywords = likely sports content
        return matches >= 2

    def _is_clickbait(self, title: str) -> bool:
        """
        Detect clickbait using keywords + heuristics

        Args:
            title: Article title

        Returns:
            True if clickbait detected
        """
        title_lower = title.lower()

        # Check for clickbait keywords
        for keyword in self.CLICKBAIT_KEYWORDS:
            if keyword in title_lower:
                return True

        # Heuristic: Excessive punctuation
        if title.count("!") >= 2 or title.count("?") >= 2:
            return True

        # Heuristic: ALL CAPS words (excluding acronyms)
        words = title.split()
        all_caps_words = [w for w in words if w.isupper() and len(w) > 3]
        if len(all_caps_words) >= 2:
            return True

        # Heuristic: Numbers in clickbait patterns
        clickbait_number_patterns = [
            r"\d+ (reasons|ways|things|tips|tricks)",
            r"number \d+",
            r"#\d+ will",
        ]
        return any(re.search(pattern, title_lower) for pattern in clickbait_number_patterns)

    def _is_entertainment_content(self, text: str) -> bool:
        """
        Detect entertainment/celebrity content

        Args:
            text: Lowercased text to analyze

        Returns:
            True if entertainment content detected
        """
        matches = sum(1 for keyword in self.ENTERTAINMENT_KEYWORDS if keyword in text)

        # Threshold: 1+ entertainment keywords = likely entertainment content
        return matches >= 1

    def filter_articles(self, articles: list) -> tuple[list, list]:
        """
        Filter a list of articles, marking filtered ones

        Args:
            articles: List of Article objects (SQLAlchemy models)

        Returns:
            Tuple of (kept_articles, filtered_articles)
        """
        kept = []
        filtered = []

        for article in articles:
            title = article.title or ""
            description = article.description or ""
            content = article.normalized_content or ""

            should_filter, reason = self.should_filter(title, description, content)

            if should_filter:
                article.filtered = True
                article.filter_reason = reason
                filtered.append(article)
            else:
                kept.append(article)

        return kept, filtered

    def get_filter_stats(self, articles: list) -> dict:
        """
        Get statistics about filtered articles

        Args:
            articles: List of Article objects

        Returns:
            Dict with filtering statistics
        """
        total = len(articles)
        filtered_count = sum(1 for a in articles if a.filtered)

        # Count by reason
        reasons = {}
        for article in articles:
            if article.filtered and article.filter_reason:
                reason = article.filter_reason
                reasons[reason] = reasons.get(reason, 0) + 1

        return {
            "total_articles": total,
            "filtered_count": filtered_count,
            "kept_count": total - filtered_count,
            "filter_rate": filtered_count / total if total > 0 else 0,
            "reasons": reasons,
        }
