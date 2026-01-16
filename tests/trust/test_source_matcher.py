"""
Unit tests for AuthoritativeSourceMatcher
Tests source loading, intelligent matching, dynamic URL construction, and keyword fallback
"""

import json

import pytest

from src.trust.source_matcher import AuthoritativeSourceMatcher


class TestSourceLoading:
    """Test source loading from YAML config"""

    def test_load_sources_success(self, mocker, mock_yaml_sources):
        """Test successful loading of sources from YAML"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test Source")
        mocker.patch("builtins.open", mock_open)
        mocker.patch("yaml.safe_load", return_value=mock_yaml_sources)

        matcher = AuthoritativeSourceMatcher(config_path="/fake/path.yaml")

        assert len(matcher.sources) > 0
        assert matcher.sources[0]["name"] == "Wikipedia - Current Leaders"
        assert matcher.fallback_config["enabled"] is True

    def test_load_sources_file_not_found(self, mocker, caplog):
        """Test handling when config file doesn't exist"""
        mocker.patch("builtins.open", side_effect=FileNotFoundError)

        matcher = AuthoritativeSourceMatcher(config_path="/nonexistent/path.yaml")

        assert len(matcher.sources) == 0
        assert matcher.fallback_config["enabled"] is False
        assert "not found" in caplog.text.lower()

    def test_load_sources_parse_error(self, mocker, caplog):
        """Test handling of YAML parse errors"""
        mock_open = mocker.mock_open(read_data="invalid: yaml: content:")
        mocker.patch("builtins.open", mock_open)
        mocker.patch("yaml.safe_load", side_effect=Exception("Parse error"))

        matcher = AuthoritativeSourceMatcher(config_path="/fake/path.yaml")

        assert len(matcher.sources) == 0
        assert matcher.fallback_config["enabled"] is False
        assert "failed" in caplog.text.lower()

    def test_load_sources_empty_config(self, mocker):
        """Test handling of empty/minimal config"""
        mock_open = mocker.mock_open(read_data="")
        mocker.patch("builtins.open", mock_open)
        mocker.patch("yaml.safe_load", return_value={})

        matcher = AuthoritativeSourceMatcher(config_path="/fake/path.yaml")

        assert len(matcher.sources) == 0
        assert matcher.fallback_config == {}


class TestIntelligentMatching:
    """Test Claude-based intelligent source matching"""

    @pytest.mark.asyncio
    async def test_find_source_successful_match(
        self, mocker, mock_claude_client, mock_yaml_sources
    ):
        """Test successful source matching via Claude"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test")
        mocker.patch("builtins.open", mock_open)
        mocker.patch("yaml.safe_load", return_value=mock_yaml_sources)

        # Mock Claude response
        mock_claude_client.analyze.return_value = json.dumps(
            {"best_match_id": 0, "confidence": 0.95, "reasoning": "This is a current leaders query"}
        )

        matcher = AuthoritativeSourceMatcher(
            config_path="/fake/path.yaml", claude_client=mock_claude_client
        )
        claim = "Who is the Prime Minister of India?"
        result = await matcher.find_source(claim)

        assert result is not None
        assert result["name"] == "Wikipedia - Current Leaders"
        assert result["url"] is not None
        assert "query_prompt" in result
        mock_claude_client.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_source_no_match(self, mocker, mock_claude_client, mock_yaml_sources):
        """Test when Claude finds no appropriate source"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test")
        mocker.patch("builtins.open", mock_open)
        mocker.patch("yaml.safe_load", return_value=mock_yaml_sources)

        # Mock Claude response with no match
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "best_match_id": None,
                "confidence": 0.0,
                "reasoning": "No appropriate authoritative source available for this type of claim",
            }
        )

        matcher = AuthoritativeSourceMatcher(
            config_path="/fake/path.yaml", claude_client=mock_claude_client
        )
        claim = "I think cats are better than dogs"
        result = await matcher.find_source(claim)

        assert result is None

    @pytest.mark.asyncio
    async def test_find_source_no_claude_client(self, mocker, mock_yaml_sources):
        """Test behavior when no Claude client is available"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test")
        mocker.patch("builtins.open", mock_open)
        mocker.patch("yaml.safe_load", return_value=mock_yaml_sources)

        matcher = AuthoritativeSourceMatcher(config_path="/fake/path.yaml", claude_client=None)
        claim = "Who is the Prime Minister of India?"
        result = await matcher.find_source(claim)

        assert result is None

    @pytest.mark.asyncio
    async def test_find_source_no_sources_loaded(self, mocker, mock_claude_client):
        """Test behavior when no sources are loaded"""
        mocker.patch("builtins.open", side_effect=FileNotFoundError)

        matcher = AuthoritativeSourceMatcher(
            config_path="/fake/path.yaml", claude_client=mock_claude_client
        )
        claim = "Who is the Prime Minister of India?"
        result = await matcher.find_source(claim)

        assert result is None
        mock_claude_client.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_find_source_invalid_match_id(
        self, mocker, mock_claude_client, mock_yaml_sources
    ):
        """Test handling of invalid match ID from Claude"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test")
        mocker.patch("builtins.open", mock_open)
        mocker.patch("yaml.safe_load", return_value=mock_yaml_sources)

        # Mock Claude response with invalid ID
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "best_match_id": 999,  # Out of range
                "confidence": 0.8,
                "reasoning": "Test",
            }
        )

        matcher = AuthoritativeSourceMatcher(
            config_path="/fake/path.yaml", claude_client=mock_claude_client
        )
        claim = "Test claim"
        result = await matcher.find_source(claim)

        assert result is None

    @pytest.mark.asyncio
    async def test_find_source_json_parse_error(
        self, mocker, mock_claude_client, mock_yaml_sources
    ):
        """Test handling of malformed JSON response from Claude"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test")
        mocker.patch("builtins.open", mock_open)
        mocker.patch("yaml.safe_load", return_value=mock_yaml_sources)

        # Mock Claude response with invalid JSON
        mock_claude_client.analyze.return_value = "Invalid JSON {{"

        matcher = AuthoritativeSourceMatcher(
            config_path="/fake/path.yaml", claude_client=mock_claude_client
        )
        claim = "Test claim"
        result = await matcher.find_source(claim)

        assert result is None

    @pytest.mark.asyncio
    async def test_find_source_api_error(self, mocker, mock_claude_client, mock_yaml_sources):
        """Test handling of Claude API errors"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test")
        mocker.patch("builtins.open", mock_open)
        mocker.patch("yaml.safe_load", return_value=mock_yaml_sources)

        # Mock Claude API error
        mock_claude_client.analyze.side_effect = Exception("API Error")

        matcher = AuthoritativeSourceMatcher(
            config_path="/fake/path.yaml", claude_client=mock_claude_client
        )
        claim = "Test claim"
        result = await matcher.find_source(claim)

        assert result is None

    @pytest.mark.asyncio
    async def test_find_source_with_markdown_wrapper(
        self, mocker, mock_claude_client, mock_yaml_sources
    ):
        """Test JSON extraction from markdown code blocks"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test")
        mocker.patch("builtins.open", mock_open)
        mocker.patch("yaml.safe_load", return_value=mock_yaml_sources)

        # Mock Claude response with markdown wrapper
        json_content = {"best_match_id": 0, "confidence": 0.9, "reasoning": "Test"}
        mock_claude_client.analyze.return_value = f"```json\n{json.dumps(json_content)}\n```"

        matcher = AuthoritativeSourceMatcher(
            config_path="/fake/path.yaml", claude_client=mock_claude_client
        )
        claim = "Who is the Prime Minister of India?"
        result = await matcher.find_source(claim)

        assert result is not None
        assert result["name"] == "Wikipedia - Current Leaders"

    @pytest.mark.asyncio
    async def test_find_source_geographic_specificity(
        self, mocker, mock_claude_client, mock_yaml_sources
    ):
        """Test that Claude correctly handles geographic specificity"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test")
        mocker.patch("builtins.open", mock_open)
        mocker.patch("yaml.safe_load", return_value=mock_yaml_sources)

        # Mock Claude selecting geographically appropriate source
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "best_match_id": 0,
                "confidence": 0.95,
                "reasoning": "India-specific query requires Wikipedia current leaders source",
            }
        )

        matcher = AuthoritativeSourceMatcher(
            config_path="/fake/path.yaml", claude_client=mock_claude_client
        )
        claim = "Who is the Prime Minister of India in 2025?"
        result = await matcher.find_source(claim)

        assert result is not None
        # Verify the system prompt mentioned geographic specificity
        call_args = mock_claude_client.analyze.call_args
        assert "Geographic specificity" in call_args[1]["user_message"]


class TestDynamicURLConstruction:
    """Test dynamic URL construction with country extraction"""

    @pytest.mark.asyncio
    async def test_construct_dynamic_url_success(
        self, mocker, mock_claude_client, mock_yaml_sources
    ):
        """Test successful dynamic URL construction"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test")
        mocker.patch("builtins.open", mock_open)

        # Add source with url_template and requires_country_extraction
        sources_with_template = {
            "sources": [
                {
                    "name": "CIA World Factbook - Country Specific",
                    "url_template": "https://www.cia.gov/the-world-factbook/countries/{country}/",
                    "requires_country_extraction": True,
                    "query_prompt": "Find current leader information for {country}",
                    "keywords": ["president", "prime minister", "leader"],
                }
            ],
            "fallback": {"enabled": True},
        }
        mocker.patch("yaml.safe_load", return_value=sources_with_template)

        # Mock Claude responses
        mock_claude_client.analyze.side_effect = [
            # First call: source matching
            json.dumps(
                {
                    "best_match_id": 0,
                    "confidence": 0.95,
                    "reasoning": "CIA factbook is appropriate for country leaders",
                }
            ),
            # Second call: country extraction
            json.dumps({"country": "India", "slug_hyphen": "india", "slug_underscore": "India"}),
        ]

        matcher = AuthoritativeSourceMatcher(
            config_path="/fake/path.yaml", claude_client=mock_claude_client
        )
        claim = "Who is the Prime Minister of India?"
        result = await matcher.find_source(claim)

        assert result is not None
        assert "india" in result["url"]
        assert result["url"] == "https://www.cia.gov/the-world-factbook/countries/india/"
        assert mock_claude_client.analyze.call_count == 2

    @pytest.mark.asyncio
    async def test_construct_dynamic_url_wikipedia_format(self, mocker, mock_claude_client):
        """Test Wikipedia uses underscore format for country slugs"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test")
        mocker.patch("builtins.open", mock_open)

        # Wikipedia source with url_template
        sources_with_wikipedia = {
            "sources": [
                {
                    "name": "Wikipedia - Country Politics",
                    "url_template": "https://en.wikipedia.org/wiki/Politics_of_{country}",
                    "requires_country_extraction": True,
                    "query_prompt": "Find political information",
                    "keywords": ["politics", "government"],
                }
            ],
            "fallback": {"enabled": True},
        }
        mocker.patch("yaml.safe_load", return_value=sources_with_wikipedia)

        # Mock Claude responses
        mock_claude_client.analyze.side_effect = [
            json.dumps(
                {"best_match_id": 0, "confidence": 0.9, "reasoning": "Wikipedia appropriate"}
            ),
            json.dumps(
                {
                    "country": "South Korea",
                    "slug_hyphen": "south-korea",
                    "slug_underscore": "South_Korea",
                }
            ),
        ]

        matcher = AuthoritativeSourceMatcher(
            config_path="/fake/path.yaml", claude_client=mock_claude_client
        )
        claim = "Politics of South Korea"
        result = await matcher.find_source(claim)

        assert result is not None
        # Should use underscore format for Wikipedia
        assert "South_Korea" in result["url"]
        assert "south-korea" not in result["url"]

    @pytest.mark.asyncio
    async def test_construct_dynamic_url_extraction_failure(self, mocker, mock_claude_client):
        """Test handling of country extraction failure"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test")
        mocker.patch("builtins.open", mock_open)

        sources_with_template = {
            "sources": [
                {
                    "name": "Test Source",
                    "url_template": "https://example.com/{country}/",
                    "requires_country_extraction": True,
                    "keywords": ["test"],
                }
            ],
            "fallback": {"enabled": True},
        }
        mocker.patch("yaml.safe_load", return_value=sources_with_template)

        # Mock Claude responses - extraction returns invalid JSON
        mock_claude_client.analyze.side_effect = [
            json.dumps({"best_match_id": 0, "confidence": 0.9, "reasoning": "Test"}),
            "Invalid JSON",
        ]

        matcher = AuthoritativeSourceMatcher(
            config_path="/fake/path.yaml", claude_client=mock_claude_client
        )
        claim = "Test claim"
        result = await matcher.find_source(claim)

        assert result is None

    @pytest.mark.asyncio
    async def test_construct_dynamic_url_no_template(self, mocker, mock_claude_client):
        """Test handling when source lacks url_template"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test")
        mocker.patch("builtins.open", mock_open)

        sources_without_template = {
            "sources": [
                {
                    "name": "Test Source",
                    "requires_country_extraction": True,
                    # Missing both url_template and url - should fail
                    "keywords": ["test"],
                    "query_prompt": "Test query",
                }
            ],
            "fallback": {"enabled": True},
        }
        mocker.patch("yaml.safe_load", return_value=sources_without_template)

        mock_claude_client.analyze.return_value = json.dumps(
            {"best_match_id": 0, "confidence": 0.9, "reasoning": "Test"}
        )

        matcher = AuthoritativeSourceMatcher(
            config_path="/fake/path.yaml", claude_client=mock_claude_client
        )
        claim = "Test claim"
        result = await matcher.find_source(claim)

        # Should return dict with url=None when both url_template and url are missing
        assert result is not None
        assert result["url"] is None
        assert result["name"] == "Test Source"

    @pytest.mark.asyncio
    async def test_construct_dynamic_url_no_claude_client(self, mocker):
        """Test dynamic URL construction requires Claude client"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test")
        mocker.patch("builtins.open", mock_open)

        sources_with_template = {
            "sources": [
                {
                    "name": "Test Source",
                    "url_template": "https://example.com/{country}/",
                    "requires_country_extraction": True,
                    "keywords": ["test"],
                }
            ],
            "fallback": {"enabled": True},
        }
        mocker.patch("yaml.safe_load", return_value=sources_with_template)

        matcher = AuthoritativeSourceMatcher(config_path="/fake/path.yaml", claude_client=None)
        claim = "Test claim"
        result = await matcher.find_source(claim)

        # Without Claude client, can't do intelligent matching at all
        assert result is None


class TestKeywordMatchingFallback:
    """Test synchronous keyword-based matching"""

    def test_find_source_sync_single_keyword(self, mocker, mock_yaml_sources):
        """Test matching with single keyword"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test")
        mocker.patch("builtins.open", mock_open)
        mocker.patch("yaml.safe_load", return_value=mock_yaml_sources)

        matcher = AuthoritativeSourceMatcher(config_path="/fake/path.yaml")
        claim = "Who is the current prime minister?"
        result = matcher.find_source_sync(claim)

        assert result is not None
        assert result["name"] == "Wikipedia - Current Leaders"

    def test_find_source_sync_multiple_keywords(self, mocker):
        """Test matching with multiple matching keywords"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test")
        mocker.patch("builtins.open", mock_open)

        sources_with_keywords = {
            "sources": [
                {
                    "name": "Source A",
                    "url": "https://example-a.com",
                    "query_prompt": "Query A",
                    "keywords": ["economy", "gdp"],
                },
                {
                    "name": "Source B",
                    "url": "https://example-b.com",
                    "query_prompt": "Query B",
                    "keywords": ["economy", "gdp", "inflation"],
                },
            ],
            "fallback": {"enabled": True},
        }
        mocker.patch("yaml.safe_load", return_value=sources_with_keywords)

        matcher = AuthoritativeSourceMatcher(config_path="/fake/path.yaml")
        claim = "What is the GDP and inflation rate?"
        result = matcher.find_source_sync(claim)

        # Should match Source B because it has all keywords matching
        assert result is not None
        assert result["name"] == "Source B"

    def test_find_source_sync_all_keywords_match_bonus(self, mocker):
        """Test bonus scoring when all keywords match"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test")
        mocker.patch("builtins.open", mock_open)

        sources = {
            "sources": [
                {
                    "name": "Partial Match",
                    "url": "https://partial.com",
                    "query_prompt": "Query",
                    "keywords": ["president", "election", "vote", "campaign"],
                },
                {
                    "name": "Full Match",
                    "url": "https://full.com",
                    "query_prompt": "Query",
                    "keywords": ["president", "election"],
                },
            ],
            "fallback": {"enabled": True},
        }
        mocker.patch("yaml.safe_load", return_value=sources)

        matcher = AuthoritativeSourceMatcher(config_path="/fake/path.yaml")
        claim = "Who won the presidential election?"
        result = matcher.find_source_sync(claim)

        # Should prefer "Full Match" because all its keywords match (gets bonus)
        assert result is not None
        assert result["name"] == "Full Match"

    def test_find_source_sync_no_match(self, mocker, mock_yaml_sources):
        """Test when no keywords match"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test")
        mocker.patch("builtins.open", mock_open)
        mocker.patch("yaml.safe_load", return_value=mock_yaml_sources)

        matcher = AuthoritativeSourceMatcher(config_path="/fake/path.yaml")
        claim = "What is the best pizza topping?"
        result = matcher.find_source_sync(claim)

        assert result is None


class TestFallbackConfiguration:
    """Test fallback configuration retrieval"""

    def test_get_fallback_config(self, mocker, mock_yaml_sources):
        """Test retrieving fallback configuration"""
        mock_open = mocker.mock_open(read_data="sources:\n  - name: Test")
        mocker.patch("builtins.open", mock_open)
        mocker.patch("yaml.safe_load", return_value=mock_yaml_sources)

        matcher = AuthoritativeSourceMatcher(config_path="/fake/path.yaml")
        fallback = matcher.get_fallback_config()

        assert fallback is not None
        assert fallback["enabled"] is True
        assert "search_engine" in fallback
