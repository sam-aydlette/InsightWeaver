"""
Tests for Context Curator
"""

from unittest.mock import MagicMock, patch

from src.context.curator import ContextCurator


class TestContextCuratorInit:
    """Tests for ContextCurator initialization"""

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_init_with_default_profile(self, mock_perspective, mock_get_profile):
        """Should load default user profile"""
        mock_get_profile.return_value = MagicMock()
        mock_perspective.return_value = MagicMock(name="test", tone="professional")

        curator = ContextCurator()

        mock_get_profile.assert_called_once()
        assert curator.user_profile is not None

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_init_with_custom_profile(self, mock_perspective, mock_get_profile):
        """Should accept custom user profile"""
        custom_profile = MagicMock()
        mock_perspective.return_value = MagicMock(name="test", tone="professional")

        curator = ContextCurator(user_profile=custom_profile)

        assert curator.user_profile == custom_profile

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_init_handles_missing_profile(self, mock_perspective, mock_get_profile):
        """Should handle missing profile file"""
        mock_get_profile.side_effect = FileNotFoundError()
        mock_perspective.return_value = MagicMock(name="test", tone="professional")

        curator = ContextCurator()

        assert curator.user_profile is None

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_init_with_topic_filters(self, mock_perspective, mock_get_profile):
        """Should accept topic filters"""
        mock_get_profile.return_value = MagicMock()
        mock_perspective.return_value = MagicMock(name="test", tone="professional")

        filters = {"topics": ["cybersecurity"], "scopes": ["local"]}
        curator = ContextCurator(topic_filters=filters)

        assert curator.topic_filters == filters
        assert curator.topic_matcher is not None


class TestTokenBudget:
    """Tests for token budget constants"""

    def test_token_budget_defined(self):
        """Should have token budget defined"""
        assert hasattr(ContextCurator, "TOKEN_BUDGET")
        assert "system_prompt" in ContextCurator.TOKEN_BUDGET
        assert "articles" in ContextCurator.TOKEN_BUDGET
        assert "historical" in ContextCurator.TOKEN_BUDGET
        assert "response" in ContextCurator.TOKEN_BUDGET

    def test_token_budget_reasonable_values(self):
        """Token budget values should be reasonable"""
        assert ContextCurator.TOKEN_BUDGET["system_prompt"] > 0
        assert ContextCurator.TOKEN_BUDGET["articles"] > 0


class TestEstimateTokens:
    """Tests for token estimation"""

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_estimate_tokens_basic(self, mock_perspective, mock_get_profile):
        """Should estimate tokens from context"""
        mock_get_profile.return_value = MagicMock()
        mock_perspective.return_value = MagicMock(name="test", tone="professional")
        curator = ContextCurator()

        context = {
            "user_profile": {"location": "Fairfax"},
            "articles": [{"title": "Test", "content": "Content"}],
            "memory": "Historical context",
            "instructions": "Do analysis",
        }

        result = curator._estimate_tokens(context)

        assert "system" in result
        assert "articles" in result
        assert "historical" in result
        assert "total" in result
        assert result["total"] > 0

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_estimate_tokens_empty_context(self, mock_perspective, mock_get_profile):
        """Should handle empty context"""
        mock_get_profile.return_value = MagicMock()
        mock_perspective.return_value = MagicMock(name="test", tone="professional")
        curator = ContextCurator()

        result = curator._estimate_tokens({})

        assert result["total"] == 0


class TestFormatUserProfile:
    """Tests for user profile formatting"""

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_format_user_profile_basic(
        self, mock_perspective, mock_get_profile, sample_user_profile
    ):
        """Should format user profile correctly"""
        mock_get_profile.return_value = sample_user_profile
        mock_perspective.return_value = MagicMock(name="test", tone="professional")

        curator = ContextCurator(user_profile=sample_user_profile)

        result = curator._format_user_profile()

        assert "location" in result
        assert "professional_domains" in result
        assert "civic_interests" in result

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_format_user_profile_no_profile(self, mock_perspective, mock_get_profile):
        """Should return defaults when no profile"""
        mock_get_profile.side_effect = FileNotFoundError()
        mock_perspective.return_value = MagicMock(name="test", tone="professional")

        curator = ContextCurator()

        result = curator._format_user_profile()

        assert result["location"] == "Unknown"
        assert result["professional_domains"] == []

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_format_user_profile_handles_string_location(
        self, mock_perspective, mock_get_profile
    ):
        """Should handle string location format"""
        profile = MagicMock()
        profile.get_primary_location.return_value = "Fairfax, VA"
        profile.get_professional_domains.return_value = []
        profile.get_civic_interests.return_value = []

        mock_get_profile.return_value = profile
        mock_perspective.return_value = MagicMock(name="test", tone="professional")

        curator = ContextCurator(user_profile=profile)

        result = curator._format_user_profile()

        assert result["location"] == "Fairfax, VA"


class TestFormatArticles:
    """Tests for article formatting"""

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_format_articles_basic(
        self, mock_perspective, mock_get_profile, sample_article_for_context
    ):
        """Should format articles correctly"""
        mock_get_profile.return_value = MagicMock()
        mock_perspective.return_value = MagicMock(name="test", tone="professional")

        curator = ContextCurator()

        feed = MagicMock()
        feed.name = "Test Feed"
        article = sample_article_for_context(
            id=1,
            title="Test Article",
            normalized_content="Content here",
            url="https://example.com/1",
            feed=feed,
        )

        result = curator._format_articles([article])

        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["title"] == "Test Article"
        assert result[0]["source"] == "Test Feed"
        assert result[0]["content"] == "Content here"

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_format_articles_uses_embedding_summary(
        self, mock_perspective, mock_get_profile, sample_article_for_context
    ):
        """Should prefer embedding summary over normalized content"""
        mock_get_profile.return_value = MagicMock()
        mock_perspective.return_value = MagicMock(name="test", tone="professional")

        curator = ContextCurator()

        feed = MagicMock()
        feed.name = "Test Feed"
        article = sample_article_for_context(
            id=1,
            title="Test",
            normalized_content="Normalized content",
            embedding_summary="Better embedding summary",
            feed=feed,
        )

        result = curator._format_articles([article])

        assert result[0]["content"] == "Better embedding summary"

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_format_articles_handles_no_feed(
        self, mock_perspective, mock_get_profile, sample_article_for_context
    ):
        """Should handle articles without feed"""
        mock_get_profile.return_value = MagicMock()
        mock_perspective.return_value = MagicMock(name="test", tone="professional")

        curator = ContextCurator()

        article = sample_article_for_context(id=1, title="Test", feed=None)

        result = curator._format_articles([article])

        assert result[0]["source"] == "Unknown"


class TestEnforceTokenBudget:
    """Tests for token budget enforcement"""

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_enforce_budget_under_limit(self, mock_perspective, mock_get_profile):
        """Should not modify context when under budget"""
        mock_get_profile.return_value = MagicMock()
        mock_perspective.return_value = MagicMock(name="test", tone="professional")

        curator = ContextCurator()

        context = {
            "user_profile": {},
            "articles": [{"title": "Test"}],
            "memory": "Short memory",
            "instructions": "Short",
        }

        result = curator._enforce_token_budget(context)

        assert "_token_metadata" in result
        assert len(result["articles"]) == 1

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_enforce_budget_reduces_articles(self, mock_perspective, mock_get_profile):
        """Should reduce articles when over budget"""
        mock_get_profile.return_value = MagicMock()
        mock_perspective.return_value = MagicMock(name="test", tone="professional")

        curator = ContextCurator()

        # Create context with many long articles to exceed budget
        large_articles = [{"title": f"Article {i}", "content": "X" * 5000} for i in range(100)]
        context = {
            "user_profile": {},
            "articles": large_articles,
            "memory": "X" * 50000,
            "instructions": "Long instructions " * 1000,
        }

        result = curator._enforce_token_budget(context)

        # Should reduce articles to fit budget
        assert len(result["articles"]) < 100


class TestGetSynthesisInstructions:
    """Tests for synthesis instructions generation"""

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_get_synthesis_instructions_includes_perspective(
        self, mock_perspective, mock_get_profile, sample_user_profile
    ):
        """Should include perspective name and framework"""
        mock_get_profile.return_value = sample_user_profile
        perspective = MagicMock()
        perspective.name = "Daily Intelligence Brief"
        perspective.tone = "professional"
        perspective.framework = "Framework for {city}, {state}"
        mock_perspective.return_value = perspective

        curator = ContextCurator(user_profile=sample_user_profile)

        result = curator._get_synthesis_instructions()

        assert "Daily Intelligence Brief" in result
        assert "Fairfax" in result

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_get_synthesis_instructions_no_profile(
        self, mock_perspective, mock_get_profile
    ):
        """Should use generic placeholders without profile"""
        mock_get_profile.side_effect = FileNotFoundError()
        perspective = MagicMock()
        perspective.name = "Test"
        perspective.tone = "professional"
        perspective.framework = "Framework for {city}"
        mock_perspective.return_value = perspective

        curator = ContextCurator()

        result = curator._get_synthesis_instructions()

        assert "your city" in result


class TestGetSummaryInstructions:
    """Tests for summary instructions generation"""

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_get_summary_instructions_daily(
        self, mock_perspective, mock_get_profile, sample_user_profile
    ):
        """Should include daily period for daily brief"""
        mock_get_profile.return_value = sample_user_profile
        perspective = MagicMock()
        perspective.name = "Test"
        perspective.tone = "professional"
        mock_perspective.return_value = perspective

        curator = ContextCurator(user_profile=sample_user_profile)

        result = curator._get_summary_instructions("daily")

        assert "today" in result.lower()

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_get_summary_instructions_weekly(
        self, mock_perspective, mock_get_profile, sample_user_profile
    ):
        """Should include weekly period for weekly brief"""
        mock_get_profile.return_value = sample_user_profile
        perspective = MagicMock()
        perspective.name = "Test"
        perspective.tone = "professional"
        mock_perspective.return_value = perspective

        curator = ContextCurator(user_profile=sample_user_profile)

        result = curator._get_summary_instructions("weekly")

        assert "week" in result.lower()


class TestCurateForSummary:
    """Tests for summary curation"""

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_curate_for_summary_basic(
        self, mock_perspective, mock_get_profile, sample_user_profile, sample_article_for_context
    ):
        """Should curate context for summary generation"""
        mock_get_profile.return_value = sample_user_profile
        perspective = MagicMock()
        perspective.name = "Test"
        perspective.tone = "professional"
        mock_perspective.return_value = perspective

        curator = ContextCurator(user_profile=sample_user_profile)

        feed = MagicMock()
        feed.name = "Test Feed"
        articles = [sample_article_for_context(id=i, feed=feed) for i in range(5)]

        result = curator.curate_for_summary(articles, brief_type="daily")

        assert "user_profile" in result
        assert "articles" in result
        assert "instructions" in result

    @patch("src.context.curator.get_user_profile")
    @patch("src.context.curator.get_perspective")
    def test_curate_for_summary_limits_articles(
        self, mock_perspective, mock_get_profile, sample_user_profile, sample_article_for_context
    ):
        """Should limit to top 20 articles"""
        mock_get_profile.return_value = sample_user_profile
        perspective = MagicMock()
        perspective.name = "Test"
        perspective.tone = "professional"
        mock_perspective.return_value = perspective

        curator = ContextCurator(user_profile=sample_user_profile)

        feed = MagicMock()
        feed.name = "Test Feed"
        articles = [sample_article_for_context(id=i, feed=feed) for i in range(50)]

        result = curator.curate_for_summary(articles)

        assert len(result["articles"]) == 20
