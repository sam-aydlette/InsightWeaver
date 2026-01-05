"""
Unit tests for TrustPipeline
Tests query enhancement, time sensitivity detection, fetch-first mechanism, and parallel analysis
"""
import json
import pytest
from src.trust.trust_pipeline import TrustPipeline


class TestInitialization:
    """Test TrustPipeline initialization"""

    def test_init_default(self, mocker):
        """Test initialization with default settings"""
        mock_client = mocker.patch("src.trust.trust_pipeline.ClaudeClient")

        pipeline = TrustPipeline()

        assert pipeline.client is not None
        assert pipeline.fact_verifier is not None
        assert pipeline.bias_analyzer is not None
        assert pipeline.intimacy_detector is not None
        assert pipeline.source_matcher is not None

    def test_init_with_api_key(self, mocker):
        """Test initialization with custom API key"""
        mock_client = mocker.patch("src.trust.trust_pipeline.ClaudeClient")

        pipeline = TrustPipeline(api_key="test-api-key")

        mock_client.assert_called_once_with(api_key="test-api-key")


class TestQueryEnhancement:
    """Test query enhancement with trust constraints"""

    @pytest.mark.asyncio
    async def test_query_with_trust_constraints_simple(self, trust_pipeline, mock_claude_client):
        """Test simple query without time-sensitive content"""
        mock_claude_client.analyze.side_effect = [
            # First call: time sensitivity analysis
            json.dumps({"is_time_sensitive": False, "facts_needed": [], "source_type": "none", "reasoning": "Not time-sensitive"}),
            # Second call: actual query
            "Python is a programming language created by Guido van Rossum."
        ]

        result = await trust_pipeline.query_with_trust_constraints("What is Python?")

        assert isinstance(result, str)
        assert len(result) > 0
        assert "Python" in result
        assert mock_claude_client.analyze.call_count == 2

    @pytest.mark.asyncio
    async def test_query_with_trust_constraints_custom_temperature(self, trust_pipeline, mock_claude_client):
        """Test query with custom temperature"""
        mock_claude_client.analyze.side_effect = [
            json.dumps({"is_time_sensitive": False, "facts_needed": [], "source_type": "none", "reasoning": "Not time-sensitive"}),
            "Test response"
        ]

        result = await trust_pipeline.query_with_trust_constraints("Test query", temperature=0.5)

        # Check that temperature was passed
        call_args = mock_claude_client.analyze.call_args_list[1]
        assert call_args[1]["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_query_with_enhanced_context(self, trust_pipeline, mock_claude_client, mocker):
        """Test query enhancement with fetched current facts"""
        # Mock web_fetch in trust_pipeline module
        mock_web_fetch = mocker.patch(
            'src.trust.trust_pipeline.web_fetch',
            new_callable=mocker.AsyncMock,
            return_value="Joe Biden is the current President of the United States."
        )

        # Mock the source_matcher.find_source method directly
        mock_find_source = mocker.AsyncMock(return_value={
            "name": "Test Government Source",
            "url": "https://test.gov",
            "query_prompt": "Find current president"
        })
        trust_pipeline.source_matcher.find_source = mock_find_source

        mock_claude_client.analyze.side_effect = [
            # Time sensitivity analysis
            json.dumps({
                "is_time_sensitive": True,
                "facts_needed": ["current president"],
                "source_type": "government_leadership",
                "reasoning": "Asking about current president"
            }),
            # Actual query response
            "The current president is Joe Biden."
        ]

        result = await trust_pipeline.query_with_trust_constraints("Who is the president?")

        assert "Biden" in result
        # Should have fetched from web
        mock_web_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_error_handling(self, trust_pipeline, mock_claude_client):
        """Test error handling when Claude API fails"""
        mock_claude_client.analyze.side_effect = Exception("API Error")

        with pytest.raises(Exception):
            await trust_pipeline.query_with_trust_constraints("Test query")


class TestTimeSensitivity:
    """Test time sensitivity analysis"""

    @pytest.mark.asyncio
    async def test_analyze_time_sensitive_query(self, trust_pipeline, mock_claude_client):
        """Test detection of time-sensitive query"""
        mock_claude_client.analyze.return_value = json.dumps({
            "is_time_sensitive": True,
            "facts_needed": ["current unemployment rate"],
            "source_type": "economic_data",
            "reasoning": "Query asks for current economic metric"
        })

        result = await trust_pipeline._analyze_query_for_time_sensitivity("What is the unemployment rate?")

        assert result is not None
        assert result["is_time_sensitive"] is True
        assert "unemployment rate" in str(result["facts_needed"])

    @pytest.mark.asyncio
    async def test_analyze_not_time_sensitive(self, trust_pipeline, mock_claude_client):
        """Test non-time-sensitive query"""
        mock_claude_client.analyze.return_value = json.dumps({
            "is_time_sensitive": False,
            "facts_needed": [],
            "source_type": "none",
            "reasoning": "Historical fact that won't change"
        })

        result = await trust_pipeline._analyze_query_for_time_sensitivity("Who was the first president?")

        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_time_sensitivity_json_error(self, trust_pipeline, mock_claude_client):
        """Test handling of JSON parse errors in time sensitivity analysis"""
        mock_claude_client.analyze.return_value = "Invalid JSON {{"

        result = await trust_pipeline._analyze_query_for_time_sensitivity("Test query")

        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_time_sensitivity_api_error(self, trust_pipeline, mock_claude_client):
        """Test handling of API errors in time sensitivity analysis"""
        mock_claude_client.analyze.side_effect = Exception("API Error")

        result = await trust_pipeline._analyze_query_for_time_sensitivity("Test query")

        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_time_sensitivity_with_markdown(self, trust_pipeline, mock_claude_client):
        """Test JSON extraction from markdown wrapper"""
        json_content = {
            "is_time_sensitive": True,
            "facts_needed": ["current CEO"],
            "source_type": "corporate_leadership",
            "reasoning": "Test"
        }
        mock_claude_client.analyze.return_value = f"```json\n{json.dumps(json_content)}\n```"

        result = await trust_pipeline._analyze_query_for_time_sensitivity("Who is the CEO of Apple?")

        assert result is not None
        assert result["is_time_sensitive"] is True


class TestFetchFirstMechanism:
    """Test fetch-first mechanism for time-sensitive queries"""

    @pytest.mark.asyncio
    async def test_fetch_current_facts_time_sensitive(self, trust_pipeline, mock_claude_client, mocker):
        """Test fetching current facts for time-sensitive query"""
        # Mock web_fetch in trust_pipeline module
        mock_web_fetch = mocker.patch(
            'src.trust.trust_pipeline.web_fetch',
            new_callable=mocker.AsyncMock,
            return_value="Narendra Modi is the current Prime Minister of India."
        )

        # Mock source_matcher.find_source
        mock_find_source = mocker.AsyncMock(return_value={
            "name": "Test Government Source",
            "url": "https://test.gov.in",
            "query_prompt": "Find current Prime Minister of India"
        })
        trust_pipeline.source_matcher.find_source = mock_find_source

        mock_claude_client.analyze.return_value = json.dumps({
            "is_time_sensitive": True,
            "facts_needed": ["current prime minister of India"],
            "source_type": "government_leadership",
            "reasoning": "Current leadership query"
        })

        result = await trust_pipeline._fetch_current_facts_if_needed("Who is the Prime Minister of India?")

        assert result is not None
        assert "Narendra Modi" in result
        assert mock_web_fetch.called

    @pytest.mark.asyncio
    async def test_fetch_current_facts_not_time_sensitive(self, trust_pipeline, mock_claude_client):
        """Test no fetching for non-time-sensitive query"""
        mock_claude_client.analyze.return_value = json.dumps({
            "is_time_sensitive": False,
            "facts_needed": [],
            "source_type": "none",
            "reasoning": "Not time-sensitive"
        })

        result = await trust_pipeline._fetch_current_facts_if_needed("What is Python?")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_current_facts_no_source_found(self, trust_pipeline, mock_claude_client):
        """Test handling when no authoritative source is found"""
        mock_claude_client.analyze.side_effect = [
            # Time sensitivity analysis
            json.dumps({
                "is_time_sensitive": True,
                "facts_needed": ["unknown fact"],
                "source_type": "other",
                "reasoning": "Time-sensitive"
            }),
            # Source matching - no match
            json.dumps({
                "best_match_id": None,
                "confidence": 0.0,
                "reasoning": "No appropriate source"
            })
        ]

        result = await trust_pipeline._fetch_current_facts_if_needed("Obscure time-sensitive query")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_current_facts_web_fetch_error(self, trust_pipeline, mock_claude_client, mock_web_fetch):
        """Test handling of web fetch errors"""
        mock_claude_client.analyze.side_effect = [
            json.dumps({
                "is_time_sensitive": True,
                "facts_needed": ["current data"],
                "source_type": "economic_data",
                "reasoning": "Economic query"
            }),
            json.dumps({
                "best_match_id": 0,
                "confidence": 0.9,
                "reasoning": "Source found"
            })
        ]

        mock_web_fetch.side_effect = Exception("Fetch failed")

        result = await trust_pipeline._fetch_current_facts_if_needed("Test query")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_with_specific_facts_needed(self, trust_pipeline, mock_claude_client, mocker):
        """Test fetching with specific facts listed"""
        # Mock web_fetch in trust_pipeline module
        mock_web_fetch = mocker.patch(
            'src.trust.trust_pipeline.web_fetch',
            new_callable=mocker.AsyncMock,
            return_value="Tim Cook is CEO since 2011"
        )

        # Mock source_matcher.find_source
        mock_find_source = mocker.AsyncMock(return_value={
            "name": "Test Corporate Source",
            "url": "https://test.apple.com",
            "query_prompt": "Find CEO information"
        })
        trust_pipeline.source_matcher.find_source = mock_find_source

        mock_claude_client.analyze.return_value = json.dumps({
            "is_time_sensitive": True,
            "facts_needed": ["CEO name", "appointment date"],
            "source_type": "corporate_leadership",
            "reasoning": "Corporate leadership query"
        })

        result = await trust_pipeline._fetch_current_facts_if_needed("Who is the CEO of Apple?")

        assert result is not None
        # Should include the specific facts in the prompt
        call_args = mock_web_fetch.call_args
        prompt_used = call_args[1]["prompt"]
        assert "CEO name" in prompt_used or "appointment date" in prompt_used


class TestResponseAnalysis:
    """Test parallel response analysis"""

    @pytest.mark.asyncio
    async def test_analyze_response_all_checks(self, trust_pipeline, mock_claude_client):
        """Test full analysis with all checks enabled"""
        # Mock responses for each analysis type
        mock_claude_client.analyze.side_effect = [
            # Fact verification - claim extraction
            json.dumps({"claims": [{"text": "Fact 1", "type": "FACT", "confidence": 0.9, "reasoning": "Test"}]}),
            # Fact verification - claim verification
            json.dumps({"verdict": "VERIFIED", "confidence": 0.95, "reasoning": "Confirmed", "caveats": [], "contradictions": []}),
            # Bias analysis
            json.dumps({"framing": [], "assumptions": [], "omissions": [], "loaded_language": []}),
            # Intimacy detection
            json.dumps({"issues": [], "overall_tone": "PROFESSIONAL", "summary": "No issues"})
        ]

        response = "Test response with factual claims"
        result = await trust_pipeline.analyze_response(response)

        assert result["analyzed"] is True
        assert "facts" in result
        assert "bias" in result
        assert "intimacy" in result

    @pytest.mark.asyncio
    async def test_analyze_response_facts_only(self, trust_pipeline, mock_claude_client):
        """Test analysis with only fact checking"""
        mock_claude_client.analyze.side_effect = [
            json.dumps({"claims": []}),
        ]

        response = "Test response"
        result = await trust_pipeline.analyze_response(
            response,
            verify_facts=True,
            check_bias=False,
            check_intimacy=False
        )

        assert "facts" in result
        assert "bias" not in result
        assert "intimacy" not in result

    @pytest.mark.asyncio
    async def test_analyze_response_skip_temporal(self, trust_pipeline, mock_claude_client):
        """Test skipping temporal validation when fetch-first was used"""
        mock_claude_client.analyze.side_effect = [
            json.dumps({"claims": [{"text": "Current fact", "type": "FACT", "confidence": 0.9, "reasoning": "Test"}]}),
            json.dumps({"verdict": "VERIFIED", "confidence": 0.95, "reasoning": "Confirmed", "caveats": [], "contradictions": []}),
            json.dumps({"framing": [], "assumptions": [], "omissions": [], "loaded_language": []}),
            json.dumps({"issues": [], "overall_tone": "PROFESSIONAL", "summary": "No issues"})
        ]

        response = "Test response"
        result = await trust_pipeline.analyze_response(response, skip_temporal_validation=True)

        assert result["analyzed"] is True
        # Temporal validation should be skipped in fact verifier

    @pytest.mark.asyncio
    async def test_analyze_response_partial_failure(self, trust_pipeline, mocker):
        """Test graceful handling when one analysis task fails"""
        # Mock the individual analyzers
        fact_verifier_mock = mocker.AsyncMock()
        fact_verifier_mock.verify.return_value = [
            mocker.MagicMock(
                to_dict=lambda: {"claim": {"text": "Test"}, "verdict": "VERIFIED"},
                verdict="VERIFIED"
            )
        ]
        trust_pipeline.fact_verifier = fact_verifier_mock

        bias_analyzer_mock = mocker.AsyncMock()
        bias_analyzer_mock.analyze.side_effect = Exception("Bias analysis failed")
        trust_pipeline.bias_analyzer = bias_analyzer_mock

        intimacy_detector_mock = mocker.AsyncMock()
        intimacy_mock_result = mocker.MagicMock()
        intimacy_mock_result.to_dict.return_value = {
            "issues": [],
            "overall_tone": "PROFESSIONAL",
            "summary": "No issues"
        }
        intimacy_detector_mock.detect.return_value = intimacy_mock_result
        trust_pipeline.intimacy_detector = intimacy_detector_mock

        response = "Test response"
        result = await trust_pipeline.analyze_response(response)

        # Facts and intimacy should succeed
        assert "facts" in result
        assert "intimacy" in result
        # Bias should have error marker
        assert "bias" in result
        assert result["bias"]["analyzed"] is False
        assert "error" in result["bias"]

    @pytest.mark.asyncio
    async def test_analyze_response_counts_verdicts(self, trust_pipeline, mocker):
        """Test correct counting of fact verification verdicts"""
        # Mock fact verifier with mixed verdicts
        verifications = [
            mocker.MagicMock(
                to_dict=lambda: {"claim": {"text": "Fact 1"}, "verdict": "VERIFIED"},
                verdict="VERIFIED"
            ),
            mocker.MagicMock(
                to_dict=lambda: {"claim": {"text": "Fact 2"}, "verdict": "VERIFIED"},
                verdict="VERIFIED"
            ),
            mocker.MagicMock(
                to_dict=lambda: {"claim": {"text": "Fact 3"}, "verdict": "UNVERIFIABLE"},
                verdict="UNVERIFIABLE"
            ),
            mocker.MagicMock(
                to_dict=lambda: {"claim": {"text": "Fact 4"}, "verdict": "CONTRADICTED"},
                verdict="CONTRADICTED"
            )
        ]

        fact_verifier_mock = mocker.AsyncMock()
        fact_verifier_mock.verify.return_value = verifications
        trust_pipeline.fact_verifier = fact_verifier_mock

        response = "Test response"
        result = await trust_pipeline.analyze_response(
            response,
            verify_facts=True,
            check_bias=False,
            check_intimacy=False
        )

        assert result["facts"]["total_claims"] == 4
        assert result["facts"]["verified_count"] == 2
        assert result["facts"]["uncertain_count"] == 1
        assert result["facts"]["contradicted_count"] == 1


class TestFullPipeline:
    """Test full pipeline integration"""

    @pytest.mark.asyncio
    async def test_full_pipeline_non_time_sensitive(self, trust_pipeline, mock_claude_client):
        """Test complete flow for non-time-sensitive query"""
        mock_claude_client.analyze.side_effect = [
            # Time sensitivity check
            json.dumps({"is_time_sensitive": False, "facts_needed": [], "source_type": "none", "reasoning": "Conceptual"}),
            # Query response
            "Python is a high-level programming language.",
            # Fact extraction
            json.dumps({"claims": [{"text": "Python is high-level", "type": "FACT", "confidence": 0.9, "reasoning": "Clear fact"}]}),
            # Fact verification
            json.dumps({"verdict": "VERIFIED", "confidence": 0.95, "reasoning": "Confirmed", "caveats": [], "contradictions": []}),
            # Bias analysis
            json.dumps({"framing": [], "assumptions": [], "omissions": [], "loaded_language": []}),
            # Intimacy detection
            json.dumps({"issues": [], "overall_tone": "PROFESSIONAL", "summary": "Professional"})
        ]

        # Get response
        response = await trust_pipeline.query_with_trust_constraints("What is Python?")

        # Analyze response
        analysis = await trust_pipeline.analyze_response(response)

        assert "Python" in response
        assert analysis["analyzed"] is True
        assert "facts" in analysis
        assert "bias" in analysis
        assert "intimacy" in analysis

    @pytest.mark.asyncio
    async def test_full_pipeline_time_sensitive(self, trust_pipeline, mock_claude_client, mocker):
        """Test complete flow for time-sensitive query with fetch-first"""
        # Mock web_fetch in trust_pipeline module
        mock_web_fetch = mocker.patch(
            'src.trust.trust_pipeline.web_fetch',
            new_callable=mocker.AsyncMock,
            return_value="Joe Biden is President"
        )

        # Mock source_matcher.find_source
        mock_find_source = mocker.AsyncMock(return_value={
            "name": "Test Government Source",
            "url": "https://test.gov",
            "query_prompt": "Find current president"
        })
        trust_pipeline.source_matcher.find_source = mock_find_source

        mock_claude_client.analyze.side_effect = [
            # Time sensitivity check
            json.dumps({
                "is_time_sensitive": True,
                "facts_needed": ["current president"],
                "source_type": "government_leadership",
                "reasoning": "Current position"
            }),
            # Query response (with fetched facts)
            "Joe Biden is the current President of the United States.",
            # Fact extraction
            json.dumps({"claims": [{"text": "Biden is president", "type": "FACT", "confidence": 0.95, "reasoning": "Current fact"}]}),
            # Fact verification (skip temporal since fetch-first)
            json.dumps({"verdict": "VERIFIED", "confidence": 0.95, "reasoning": "Confirmed from source", "caveats": [], "contradictions": []}),
            # Bias analysis
            json.dumps({"framing": [], "assumptions": [], "omissions": [], "loaded_language": []}),
            # Intimacy detection
            json.dumps({"issues": [], "overall_tone": "PROFESSIONAL", "summary": "Professional"})
        ]

        # Get response
        response = await trust_pipeline.query_with_trust_constraints("Who is the president?")

        # Analyze response (skip temporal since we did fetch-first)
        analysis = await trust_pipeline.analyze_response(response, skip_temporal_validation=True)

        assert "Biden" in response
        assert mock_web_fetch.called
        assert "facts" in analysis
        assert analysis["analyzed"] is True

    @pytest.mark.asyncio
    async def test_pipeline_empty_response(self, trust_pipeline, mock_claude_client):
        """Test handling of empty response"""
        mock_claude_client.analyze.side_effect = [
            json.dumps({"claims": []}),
            json.dumps({"framing": [], "assumptions": [], "omissions": [], "loaded_language": []}),
            json.dumps({"issues": [], "overall_tone": "PROFESSIONAL", "summary": "No content"})
        ]

        response = ""
        analysis = await trust_pipeline.analyze_response(response)

        assert analysis["analyzed"] is True
        assert analysis["facts"]["total_claims"] == 0

    @pytest.mark.asyncio
    async def test_pipeline_no_checks_enabled(self, trust_pipeline):
        """Test analysis when all checks are disabled"""
        response = "Test response"
        analysis = await trust_pipeline.analyze_response(
            response,
            verify_facts=False,
            check_bias=False,
            check_intimacy=False
        )

        assert analysis["analyzed"] is True
        assert "facts" not in analysis
        assert "bias" not in analysis
        assert "intimacy" not in analysis
        assert analysis["response_length"] == len(response)
