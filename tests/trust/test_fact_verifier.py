"""
Unit tests for FactVerifier
Tests claim extraction, verification, and temporal validation
"""
import json
import pytest
from src.trust.fact_verifier import Claim, FactVerification, FactVerifier


class TestClaimExtraction:
    """Test claim extraction from responses"""

    @pytest.mark.asyncio
    async def test_extract_claims_mixed_types(self, fact_verifier, mock_claude_client, json_claim_extraction_response):
        """Test extraction of different claim types"""
        mock_claude_client.analyze.return_value = json_claim_extraction_response

        response = "Python was created by Guido van Rossum. Python is the best programming language. Python might become more popular."
        claims = await fact_verifier._extract_claims(response)

        assert len(claims) == 3
        assert claims[0].claim_type == "FACT"
        assert claims[1].claim_type == "OPINION"
        assert claims[2].claim_type == "SPECULATION"
        assert claims[0].confidence == 0.95

    @pytest.mark.asyncio
    async def test_extract_claims_empty_response(self, fact_verifier, mock_claude_client):
        """Test handling of empty response"""
        mock_claude_client.analyze.return_value = json.dumps({"claims": []})

        claims = await fact_verifier._extract_claims("")
        assert claims == []

    @pytest.mark.asyncio
    async def test_extract_claims_no_claims(self, fact_verifier, mock_claude_client):
        """Test response with no factual claims"""
        mock_claude_client.analyze.return_value = json.dumps({"claims": []})

        response = "Hello, how are you?"
        claims = await fact_verifier._extract_claims(response)
        assert claims == []

    @pytest.mark.asyncio
    async def test_extract_claims_json_parse_error(self, fact_verifier, mock_claude_client):
        """Test handling of malformed JSON from Claude"""
        mock_claude_client.analyze.return_value = "This is not valid JSON {{"

        response = "Test claim"
        claims = await fact_verifier._extract_claims(response)
        assert claims == []

    @pytest.mark.asyncio
    async def test_extract_claims_with_markdown_wrapper(self, fact_verifier, mock_claude_client):
        """Test stripping of markdown code blocks"""
        json_data = json.dumps({
            "claims": [
                {"text": "Test claim", "type": "FACT", "confidence": 0.9, "reasoning": "Test"}
            ]
        })
        mock_claude_client.analyze.return_value = f"```json\n{json_data}\n```"

        response = "Test claim"
        claims = await fact_verifier._extract_claims(response)

        assert len(claims) == 1
        assert claims[0].text == "Test claim"

    @pytest.mark.asyncio
    async def test_extract_claims_confidence_levels(self, fact_verifier, mock_claude_client):
        """Test that confidence levels are properly extracted"""
        mock_claude_client.analyze.return_value = json.dumps({
            "claims": [
                {"text": "High confidence", "type": "FACT", "confidence": 0.95, "reasoning": "Very sure"},
                {"text": "Low confidence", "type": "INFERENCE", "confidence": 0.5, "reasoning": "Uncertain"}
            ]
        })

        response = "High confidence. Low confidence."
        claims = await fact_verifier._extract_claims(response)

        assert claims[0].confidence == 0.95
        assert claims[1].confidence == 0.5


class TestClaimVerification:
    """Test individual claim verification"""

    @pytest.mark.asyncio
    async def test_verify_fact_claim(self, fact_verifier, mock_claude_client, json_fact_verification_response):
        """Test verification of FACT type claim"""
        mock_claude_client.analyze.return_value = json_fact_verification_response

        claim = Claim("Python was created in 1991", "FACT", 0.9, "Historical fact")
        verification = await fact_verifier._verify_claim(claim, skip_temporal_validation=True)

        assert verification.verdict == "VERIFIED"
        assert verification.confidence == 0.92
        assert "well-supported" in verification.reasoning

    @pytest.mark.asyncio
    async def test_verify_inference_claim(self, fact_verifier, mock_claude_client):
        """Test verification of INFERENCE type claim"""
        mock_claude_client.analyze.return_value = json.dumps({
            "verdict": "VERIFIED",
            "confidence": 0.8,
            "reasoning": "Logical inference supported by evidence",
            "caveats": [],
            "contradictions": []
        })

        claim = Claim("This suggests growth", "INFERENCE", 0.7, "Logical conclusion")
        verification = await fact_verifier._verify_claim(claim, skip_temporal_validation=True)

        assert verification.verdict == "VERIFIED"
        assert verification.claim.claim_type == "INFERENCE"

    @pytest.mark.asyncio
    async def test_verify_speculation_claim(self, fact_verifier, mock_claude_client):
        """Test that SPECULATION returns UNVERIFIABLE immediately"""
        claim = Claim("It might rain tomorrow", "SPECULATION", 0.5, "Future prediction")
        verification = await fact_verifier._verify_claim(claim)

        assert verification.verdict == "UNVERIFIABLE"
        assert verification.confidence == 1.0
        assert "speculation" in verification.reasoning.lower()
        # Should not call Claude API for speculation
        mock_claude_client.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_verify_opinion_claim(self, fact_verifier, mock_claude_client):
        """Test that OPINION returns UNVERIFIABLE immediately"""
        claim = Claim("Python is the best language", "OPINION", 0.6, "Subjective judgment")
        verification = await fact_verifier._verify_claim(claim)

        assert verification.verdict == "UNVERIFIABLE"
        assert verification.confidence == 1.0
        assert "opinion" in verification.reasoning.lower()
        # Should not call Claude API for opinion
        mock_claude_client.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_verify_claim_contradicted(self, fact_verifier, mock_claude_client):
        """Test detection of contradicted claims"""
        mock_claude_client.analyze.return_value = json.dumps({
            "verdict": "CONTRADICTED",
            "confidence": 0.9,
            "reasoning": "This contradicts known facts",
            "caveats": [],
            "contradictions": ["The actual value is different"]
        })

        claim = Claim("Wrong fact", "FACT", 0.8, "Incorrect claim")
        verification = await fact_verifier._verify_claim(claim, skip_temporal_validation=True)

        assert verification.verdict == "CONTRADICTED"
        assert len(verification.contradictions) == 1

    @pytest.mark.asyncio
    async def test_verify_claim_unverifiable(self, fact_verifier, mock_claude_client):
        """Test handling of unverifiable facts"""
        mock_claude_client.analyze.return_value = json.dumps({
            "verdict": "UNVERIFIABLE",
            "confidence": 0.0,
            "reasoning": "Cannot verify with available sources",
            "caveats": [],
            "contradictions": []
        })

        claim = Claim("Unknown fact", "FACT", 0.7, "Cannot verify")
        verification = await fact_verifier._verify_claim(claim, skip_temporal_validation=True)

        assert verification.verdict == "UNVERIFIABLE"
        assert verification.confidence == 0.0

    @pytest.mark.asyncio
    async def test_verify_claim_with_caveats(self, fact_verifier, mock_claude_client):
        """Test extraction of caveats from verification"""
        mock_claude_client.analyze.return_value = json.dumps({
            "verdict": "VERIFIED",
            "confidence": 0.85,
            "reasoning": "Generally correct but with nuances",
            "caveats": ["Caveat 1", "Caveat 2"],
            "contradictions": []
        })

        claim = Claim("Nuanced fact", "FACT", 0.8, "Needs context")
        verification = await fact_verifier._verify_claim(claim, skip_temporal_validation=True)

        assert len(verification.caveats) == 2
        assert "Caveat 1" in verification.caveats

    @pytest.mark.asyncio
    async def test_verify_claim_json_error(self, fact_verifier, mock_claude_client):
        """Test handling of JSON parsing errors"""
        mock_claude_client.analyze.return_value = "Invalid JSON {{"

        claim = Claim("Test claim", "FACT", 0.8, "Test")
        verification = await fact_verifier._verify_claim(claim, skip_temporal_validation=True)

        assert verification.verdict == "ERROR"
        assert verification.confidence == 0.0


class TestTemporalValidation:
    """Test temporal validation of time-sensitive claims"""

    @pytest.mark.asyncio
    async def test_temporal_check_time_sensitive_verified(self, fact_verifier, mock_claude_client, mock_web_fetch, mocker):
        """Test verification that claim is still current"""
        # Initial verification
        initial_verification = FactVerification(
            claim=Claim("The president is Joe Biden", "FACT", 0.9, "Current leadership"),
            verdict="VERIFIED",
            confidence=0.95,
            reasoning="Verified against knowledge base",
            caveats=[],
            contradictions=[]
        )

        # Mock source matcher to return a source
        mock_find_source = mocker.AsyncMock(return_value={
            'name': 'White House',
            'url': 'https://whitehouse.gov',
            'query_prompt': 'Who is president?'
        })
        fact_verifier.source_matcher.find_source = mock_find_source

        # Mock web_fetch
        mock_web_fetch.return_value = "President: Joe Biden"

        # Mock Claude verification
        mock_claude_client.analyze.return_value = json.dumps({
            "still_current": True,
            "confidence": 0.95,
            "reasoning": "Claim matches current information",
            "source_quote": "President: Joe Biden"
        })

        result = await fact_verifier._check_temporal_validity(
            initial_verification.claim,
            initial_verification
        )

        assert result is not None
        assert result['still_current'] is True
        assert 'checked_date' in result

    @pytest.mark.asyncio
    async def test_temporal_check_time_sensitive_outdated(self, fact_verifier, mock_claude_client, mock_web_fetch, mocker):
        """Test detection of outdated facts"""
        initial_verification = FactVerification(
            claim=Claim("The CEO is Jane Doe", "FACT", 0.9, "Corporate leadership"),
            verdict="VERIFIED",
            confidence=0.9,
            reasoning="Verified",
            caveats=[],
            contradictions=[]
        )

        mock_find_source = mocker.AsyncMock(return_value={
            'name': 'Company Site',
            'url': 'https://company.com',
            'query_prompt': 'Who is CEO?'
        })
        fact_verifier.source_matcher.find_source = mock_find_source

        mock_web_fetch.return_value = "CEO: John Brown (as of 2024)"

        mock_claude_client.analyze.return_value = json.dumps({
            "still_current": False,
            "confidence": 0.9,
            "reasoning": "CEO changed in 2024",
            "update_info": "Current CEO is John Brown",
            "source_quote": "CEO: John Brown"
        })

        result = await fact_verifier._check_temporal_validity(
            initial_verification.claim,
            initial_verification
        )

        assert result is not None
        assert result['still_current'] is False
        assert 'update_info' in result

    @pytest.mark.asyncio
    async def test_temporal_check_not_time_sensitive(self, fact_verifier):
        """Test that non-time-sensitive claims skip temporal check"""
        verification = FactVerification(
            claim=Claim("The Earth is round", "FACT", 0.95, "Scientific fact"),
            verdict="VERIFIED",
            confidence=0.99,
            reasoning="Well-established",
            caveats=[],
            contradictions=[]
        )

        result = await fact_verifier._check_temporal_validity(
            verification.claim,
            verification
        )

        # Should return None for non-time-sensitive claims
        assert result is None

    @pytest.mark.asyncio
    async def test_temporal_check_no_source_available(self, fact_verifier, mocker):
        """Test handling when no authoritative source is available"""
        verification = FactVerification(
            claim=Claim("The current director is John Smith", "FACT", 0.8, "Leadership"),
            verdict="VERIFIED",
            confidence=0.85,
            reasoning="Verified",
            caveats=[],
            contradictions=[]
        )

        # Mock source matcher to return None
        mock_find_source = mocker.AsyncMock(return_value=None)
        fact_verifier.source_matcher.find_source = mock_find_source
        fact_verifier.source_matcher.get_fallback_config = lambda: {'reason': 'No source available'}

        result = await fact_verifier._check_temporal_validity(
            verification.claim,
            verification
        )

        assert result is not None
        assert result['still_current'] is None
        assert 'No source available' in result['reasoning'] or 'No authoritative source' in result['reasoning']

    @pytest.mark.asyncio
    async def test_temporal_check_web_fetch_error(self, fact_verifier, mock_web_fetch, mocker):
        """Test handling of network errors during web fetch"""
        verification = FactVerification(
            claim=Claim("The president is current", "FACT", 0.9, "Leadership"),
            verdict="VERIFIED",
            confidence=0.9,
            reasoning="Verified",
            caveats=[],
            contradictions=[]
        )

        mock_find_source = mocker.AsyncMock(return_value={
            'name': 'Test Source',
            'url': 'https://test.com',
            'query_prompt': 'Test'
        })
        fact_verifier.source_matcher.find_source = mock_find_source

        # Mock web_fetch to raise exception
        mock_web_fetch.side_effect = Exception("Network error")

        result = await fact_verifier._check_temporal_validity(
            verification.claim,
            verification
        )

        assert result is not None
        assert result['still_current'] is None
        assert 'failed' in result['reasoning'].lower() or 'error' in result['reasoning'].lower()

    @pytest.mark.asyncio
    async def test_temporal_check_skip_when_requested(self, fact_verifier, mock_claude_client):
        """Test that skip_temporal_validation flag is respected"""
        mock_claude_client.analyze.return_value = json.dumps({
            "verdict": "VERIFIED",
            "confidence": 0.9,
            "reasoning": "Verified",
            "caveats": [],
            "contradictions": []
        })

        claim = Claim("The president is current", "FACT", 0.9, "Time-sensitive")
        verification = await fact_verifier._verify_claim(claim, skip_temporal_validation=True)

        # Temporal check should not be present
        assert verification.temporal_check is None

    def test_is_time_sensitive_keywords(self):
        """Test keyword detection for time-sensitive claims"""
        from src.trust.fact_verifier import FactVerifier

        # Create instance with None client (we don't need it for this test)
        verifier = FactVerifier(None)

        # Should detect time-sensitive keywords
        assert verifier._is_time_sensitive(
            Claim("The current president is...", "FACT", 0.9, "Test")
        )
        assert verifier._is_time_sensitive(
            Claim("Who is the CEO now?", "FACT", 0.9, "Test")
        )
        assert verifier._is_time_sensitive(
            Claim("The director in 2025 is...", "FACT", 0.9, "Test")
        )

        # Should not detect as time-sensitive (no time-sensitive keywords)
        assert not verifier._is_time_sensitive(
            Claim("Python was created by Guido van Rossum", "FACT", 0.9, "Test")
        )
        assert not verifier._is_time_sensitive(
            Claim("The Earth orbits the Sun", "FACT", 0.9, "Test")
        )


class TestMainPipeline:
    """Test the main verify() pipeline"""

    @pytest.mark.asyncio
    async def test_verify_complete_pipeline(self, fact_verifier, mock_claude_client):
        """Test end-to-end verification pipeline"""
        # Mock claim extraction
        mock_claude_client.analyze.side_effect = [
            # Extraction response
            json.dumps({
                "claims": [
                    {"text": "Fact 1", "type": "FACT", "confidence": 0.9, "reasoning": "Test"},
                    {"text": "Opinion 1", "type": "OPINION", "confidence": 0.5, "reasoning": "Test"}
                ]
            }),
            # Verification response for Fact 1
            json.dumps({
                "verdict": "VERIFIED",
                "confidence": 0.95,
                "reasoning": "Confirmed",
                "caveats": [],
                "contradictions": []
            })
        ]

        response = "Fact 1. Opinion 1."
        verifications = await fact_verifier.verify(response, skip_temporal_validation=True)

        assert len(verifications) == 2
        assert verifications[0].verdict == "VERIFIED"
        assert verifications[1].verdict == "UNVERIFIABLE"  # Opinion

    @pytest.mark.asyncio
    async def test_verify_parallel_execution(self, fact_verifier, mock_claude_client, mocker):
        """Test that claims are verified in parallel"""
        verification_response = json.dumps({
            "verdict": "VERIFIED",
            "confidence": 0.9,
            "reasoning": "Test",
            "caveats": [],
            "contradictions": []
        })

        mock_claude_client.analyze.side_effect = [
            # Extraction
            json.dumps({
                "claims": [
                    {"text": "Fact 1", "type": "FACT", "confidence": 0.9, "reasoning": "Test"},
                    {"text": "Fact 2", "type": "FACT", "confidence": 0.9, "reasoning": "Test"},
                    {"text": "Fact 3", "type": "FACT", "confidence": 0.9, "reasoning": "Test"}
                ]
            }),
            # Verifications (3 facts)
            verification_response,
            verification_response,
            verification_response
        ]

        response = "Fact 1. Fact 2. Fact 3."
        verifications = await fact_verifier.verify(response, skip_temporal_validation=True)

        assert len(verifications) == 3
        # All should be verified
        assert all(v.verdict == "VERIFIED" for v in verifications)

    @pytest.mark.asyncio
    async def test_verify_with_temporal_skip(self, fact_verifier, mock_claude_client):
        """Test verification with temporal validation skipped"""
        mock_claude_client.analyze.side_effect = [
            json.dumps({
                "claims": [
                    {"text": "Current fact", "type": "FACT", "confidence": 0.9, "reasoning": "Test"}
                ]
            }),
            json.dumps({
                "verdict": "VERIFIED",
                "confidence": 0.9,
                "reasoning": "Test",
                "caveats": [],
                "contradictions": []
            })
        ]

        response = "Current fact"
        verifications = await fact_verifier.verify(response, skip_temporal_validation=True)

        # Should not have temporal_check
        assert verifications[0].temporal_check is None

    @pytest.mark.asyncio
    async def test_verify_mixed_verdicts(self, fact_verifier, mock_claude_client):
        """Test handling of multiple verdict types"""
        mock_claude_client.analyze.side_effect = [
            json.dumps({
                "claims": [
                    {"text": "Good fact", "type": "FACT", "confidence": 0.9, "reasoning": "Test"},
                    {"text": "Bad fact", "type": "FACT", "confidence": 0.8, "reasoning": "Test"},
                    {"text": "Opinion", "type": "OPINION", "confidence": 0.5, "reasoning": "Test"}
                ]
            }),
            json.dumps({"verdict": "VERIFIED", "confidence": 0.95, "reasoning": "Good", "caveats": [], "contradictions": []}),
            json.dumps({"verdict": "CONTRADICTED", "confidence": 0.9, "reasoning": "Bad", "caveats": [], "contradictions": ["Wrong"]})
        ]

        response = "Good fact. Bad fact. Opinion."
        verifications = await fact_verifier.verify(response, skip_temporal_validation=True)

        assert len(verifications) == 3
        assert verifications[0].verdict == "VERIFIED"
        assert verifications[1].verdict == "CONTRADICTED"
        assert verifications[2].verdict == "UNVERIFIABLE"

    @pytest.mark.asyncio
    async def test_verify_empty_claims(self, fact_verifier, mock_claude_client):
        """Test handling when no claims are extracted"""
        mock_claude_client.analyze.return_value = json.dumps({"claims": []})

        response = "No claims here"
        verifications = await fact_verifier.verify(response)

        assert len(verifications) == 0

    @pytest.mark.asyncio
    async def test_verify_partial_failures(self, fact_verifier, mock_claude_client):
        """Test that some verifications can fail without blocking others"""
        mock_claude_client.analyze.side_effect = [
            json.dumps({
                "claims": [
                    {"text": "Fact 1", "type": "FACT", "confidence": 0.9, "reasoning": "Test"},
                    {"text": "Fact 2", "type": "FACT", "confidence": 0.9, "reasoning": "Test"}
                ]
            }),
            json.dumps({"verdict": "VERIFIED", "confidence": 0.9, "reasoning": "Good", "caveats": [], "contradictions": []}),
            Exception("API Error")  # Second verification fails
        ]

        response = "Fact 1. Fact 2."
        verifications = await fact_verifier.verify(response, skip_temporal_validation=True)

        assert len(verifications) == 2
        assert verifications[0].verdict == "VERIFIED"
        assert verifications[1].verdict == "ERROR"

    @pytest.mark.asyncio
    async def test_verify_all_failures(self, fact_verifier, mock_claude_client):
        """Test handling when all verifications fail"""
        mock_claude_client.analyze.side_effect = [
            json.dumps({
                "claims": [
                    {"text": "Fact 1", "type": "FACT", "confidence": 0.9, "reasoning": "Test"}
                ]
            }),
            Exception("Total failure")
        ]

        response = "Fact 1"
        verifications = await fact_verifier.verify(response, skip_temporal_validation=True)

        assert len(verifications) == 1
        assert verifications[0].verdict == "ERROR"


class TestHelperMethods:
    """Test helper methods"""

    def test_clean_json_response(self, fact_verifier):
        """Test JSON cleaning from markdown wrappers"""
        json_data = '{"test": "value"}'

        # With markdown wrapper
        wrapped = f"```json\n{json_data}\n```"
        assert fact_verifier._clean_json_response(wrapped) == json_data

        # With plain markdown wrapper
        wrapped2 = f"```\n{json_data}\n```"
        assert fact_verifier._clean_json_response(wrapped2) == json_data

        # Without wrapper
        assert fact_verifier._clean_json_response(json_data) == json_data

    def test_clean_json_with_text_before_after(self, fact_verifier):
        """Test JSON extraction from markdown with surrounding text"""
        json_data = '{"test": "value"}'
        # The method strips markdown wrappers from beginning/end, not from middle
        with_text = f"```json\n{json_data}\n```"

        cleaned = fact_verifier._clean_json_response(with_text)
        assert cleaned == json_data
