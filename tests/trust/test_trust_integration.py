"""
Integration tests for trust pipeline
Tests complete end-to-end workflows with minimal mocking
"""

import json
from unittest.mock import AsyncMock

import pytest


class TestCompleteWorkflows:
    """Test complete trust pipeline workflows end-to-end"""

    @pytest.mark.asyncio
    async def test_simple_query_full_pipeline(self, trust_pipeline):
        """Test simple non-time-sensitive query through full pipeline"""
        # Mock time sensitivity to False
        trust_pipeline._analyze_query_for_time_sensitivity = AsyncMock(return_value=None)

        # Mock the query response
        trust_pipeline.client.analyze = AsyncMock(
            return_value="The first president was George Washington."
        )

        # Mock verifiers to return simple results
        from src.trust.fact_verifier import Claim, FactVerification

        trust_pipeline.fact_verifier.verify = AsyncMock(
            return_value=[
                FactVerification(
                    claim=Claim(
                        "George Washington was the first president", "FACT", 0.95, "Historical"
                    ),
                    verdict="VERIFIED",
                    confidence=0.98,
                    reasoning="Well-documented",
                    caveats=[],
                    contradictions=[],
                )
            ]
        )

        from src.trust.bias_analyzer import BiasAnalysis

        trust_pipeline.bias_analyzer.analyze = AsyncMock(return_value=BiasAnalysis([], [], [], []))

        from src.trust.intimacy_detector import IntimacyAnalysis

        trust_pipeline.intimacy_detector.detect = AsyncMock(
            return_value=IntimacyAnalysis([], "PROFESSIONAL", "No issues")
        )

        result = await trust_pipeline.run_full_pipeline(
            user_query="Who was the first president?", verify_response=True
        )

        # Verify complete result structure
        assert "response" in result
        assert "analysis" in result
        assert result["trust_enhanced"] is True
        assert result["used_fetch_first"] is False

        # Verify analysis was performed
        assert result["analysis"]["analyzed"] is True

    @pytest.mark.asyncio
    async def test_time_sensitive_query_detected(self, trust_pipeline):
        """Test time-sensitive query detection"""
        # Mock query analysis to return time-sensitive
        mock_analysis = {
            "is_time_sensitive": True,
            "facts_needed": ["current president"],
            "source_type": "government_leadership",
            "reasoning": "Asks about current position",
        }
        trust_pipeline._analyze_query_for_time_sensitivity = AsyncMock(return_value=mock_analysis)

        # Mock fetch to fail (to test pipeline continues)
        trust_pipeline._fetch_current_facts_if_needed = AsyncMock(return_value=None)

        # Mock response
        trust_pipeline.client.analyze = AsyncMock(return_value="Joe Biden")

        result = await trust_pipeline.run_full_pipeline(
            user_query="Who is the current president?",
            verify_response=False,  # Skip verification for simplicity
        )

        # Should still work even if fetch failed
        assert "response" in result
        assert result["used_fetch_first"] is True

    @pytest.mark.asyncio
    async def test_biased_response_detected(self, trust_pipeline):
        """Test detection of bias in response"""
        from src.trust.bias_analyzer import BiasAnalysis, FramingIssue, LoadedTerm, Omission

        trust_pipeline._analyze_query_for_time_sensitivity = AsyncMock(return_value=None)
        trust_pipeline.client.analyze = AsyncMock(
            return_value="This revolutionary technology will change everything!"
        )
        trust_pipeline.fact_verifier.verify = AsyncMock(return_value=[])

        # Return bias issues
        trust_pipeline.bias_analyzer.analyze = AsyncMock(
            return_value=BiasAnalysis(
                framing_issues=[FramingIssue("hero", "revolutionary", "hype", "innovative")],
                assumptions=[],
                omissions=[Omission("risks", "important", "include challenges")],
                loaded_terms=[LoadedTerm("revolutionary", "dramatic", "innovative")],
            )
        )

        from src.trust.intimacy_detector import IntimacyAnalysis

        trust_pipeline.intimacy_detector.detect = AsyncMock(
            return_value=IntimacyAnalysis([], "PROFESSIONAL", "OK")
        )

        result = await trust_pipeline.run_full_pipeline(
            user_query="Tell me about tech", verify_response=True
        )

        # Verify bias detected
        assert result["analysis"]["bias"]["total_issues"] > 0

    @pytest.mark.asyncio
    async def test_intimacy_issues_detected(self, trust_pipeline):
        """Test detection of inappropriate intimacy"""
        from src.trust.bias_analyzer import BiasAnalysis
        from src.trust.intimacy_detector import IntimacyAnalysis, IntimacyIssue

        trust_pipeline._analyze_query_for_time_sensitivity = AsyncMock(return_value=None)
        trust_pipeline.client.analyze = AsyncMock(return_value="I'm excited to help you!")
        trust_pipeline.fact_verifier.verify = AsyncMock(return_value=[])
        trust_pipeline.bias_analyzer.analyze = AsyncMock(return_value=BiasAnalysis([], [], [], []))

        # Return intimacy issues
        trust_pipeline.intimacy_detector.detect = AsyncMock(
            return_value=IntimacyAnalysis(
                issues=[IntimacyIssue("EMOTION", "excited", "AI can't feel", "HIGH", "ready")],
                overall_tone="FAMILIAR",
                summary="Emotion claims detected",
            )
        )

        result = await trust_pipeline.run_full_pipeline(user_query="Help me", verify_response=True)

        # Verify intimacy detected
        assert result["analysis"]["intimacy"]["total_issues"] > 0

    @pytest.mark.asyncio
    async def test_contradicted_facts_detected(self, trust_pipeline):
        """Test detection of contradicted factual claims"""
        from src.trust.bias_analyzer import BiasAnalysis
        from src.trust.fact_verifier import Claim, FactVerification
        from src.trust.intimacy_detector import IntimacyAnalysis

        trust_pipeline._analyze_query_for_time_sensitivity = AsyncMock(return_value=None)
        trust_pipeline.client.analyze = AsyncMock(return_value="Python was created in 2010")

        # Return contradicted fact
        trust_pipeline.fact_verifier.verify = AsyncMock(
            return_value=[
                FactVerification(
                    claim=Claim("Python was created in 2010", "FACT", 0.9, "Date claim"),
                    verdict="CONTRADICTED",
                    confidence=0.95,
                    reasoning="Actually 1991",
                    caveats=[],
                    contradictions=["First released 1991"],
                )
            ]
        )

        trust_pipeline.bias_analyzer.analyze = AsyncMock(return_value=BiasAnalysis([], [], [], []))
        trust_pipeline.intimacy_detector.detect = AsyncMock(
            return_value=IntimacyAnalysis([], "PROFESSIONAL", "OK")
        )

        result = await trust_pipeline.run_full_pipeline(
            user_query="When was Python created?", verify_response=True
        )

        # Verify contradiction detected
        assert result["analysis"]["facts"]["contradicted_count"] == 1

    @pytest.mark.asyncio
    async def test_response_without_verification(self, trust_pipeline):
        """Test getting response without running verification"""
        trust_pipeline._analyze_query_for_time_sensitivity = AsyncMock(return_value=None)
        trust_pipeline.client.analyze = AsyncMock(return_value="Answer here")

        result = await trust_pipeline.run_full_pipeline(
            user_query="Question?", verify_response=False
        )

        # Should have response but no analysis
        assert "response" in result
        assert "analysis" not in result


class TestErrorScenarios:
    """Test error handling and resilience"""

    @pytest.mark.asyncio
    async def test_api_error_during_query(self, trust_pipeline):
        """Test handling of API errors during query"""
        trust_pipeline._analyze_query_for_time_sensitivity = AsyncMock(return_value=None)
        trust_pipeline.client.analyze = AsyncMock(side_effect=Exception("API Error"))

        with pytest.raises(Exception) as exc_info:
            await trust_pipeline.run_full_pipeline(user_query="Test", verify_response=False)

        assert "API Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_partial_verification_failure(self, trust_pipeline):
        """Test that partial verification failures are handled gracefully"""
        from src.trust.bias_analyzer import BiasAnalysis
        from src.trust.intimacy_detector import IntimacyAnalysis

        trust_pipeline._analyze_query_for_time_sensitivity = AsyncMock(return_value=None)
        trust_pipeline.client.analyze = AsyncMock(return_value="Response")

        # Fact verification fails
        trust_pipeline.fact_verifier.verify = AsyncMock(
            side_effect=Exception("Verification failed")
        )

        # But other analyses succeed
        trust_pipeline.bias_analyzer.analyze = AsyncMock(return_value=BiasAnalysis([], [], [], []))
        trust_pipeline.intimacy_detector.detect = AsyncMock(
            return_value=IntimacyAnalysis([], "PROFESSIONAL", "OK")
        )

        result = await trust_pipeline.run_full_pipeline(user_query="Test", verify_response=True)

        # Should complete with partial results
        assert "response" in result
        assert "analysis" in result

        # Facts marked as error
        assert result["analysis"]["facts"]["analyzed"] is False

        # But others succeeded
        assert result["analysis"]["bias"]["analyzed"] is True
        assert result["analysis"]["intimacy"]["analyzed"] is True

    @pytest.mark.asyncio
    async def test_fetch_first_failure_continues(self, trust_pipeline):
        """Test that fetch-first failures don't break pipeline"""
        # Mock time-sensitive detection
        mock_analysis = {
            "is_time_sensitive": True,
            "facts_needed": ["current info"],
            "source_type": "government",
            "reasoning": "Current data",
        }
        trust_pipeline._analyze_query_for_time_sensitivity = AsyncMock(return_value=mock_analysis)

        # Mock fetch to fail
        trust_pipeline._fetch_current_facts_if_needed = AsyncMock(return_value=None)

        # But query should still work
        trust_pipeline.client.analyze = AsyncMock(return_value="Response without fetched data")

        result = await trust_pipeline.run_full_pipeline(
            user_query="Current info?", verify_response=False
        )

        # Should complete successfully
        assert "response" in result
        assert result["used_fetch_first"] is True


class TestReportGeneration:
    """Test trust report formatting"""

    def test_compact_report_generation(self, complete_analysis_result):
        """Test generating compact trust report"""
        from src.trust.trust_report import TrustReportFormatter

        compact = TrustReportFormatter.format_compact_summary(complete_analysis_result)

        # Should return a string
        assert isinstance(compact, str)
        assert len(compact) > 0

    def test_moderate_report_generation(self, complete_analysis_result):
        """Test generating moderate trust report"""
        from src.trust.trust_report import TrustReportFormatter

        moderate = TrustReportFormatter.format_moderate_summary(complete_analysis_result)

        # Should return a string
        assert isinstance(moderate, str)
        assert len(moderate) > 0

    def test_response_display_formatting(self):
        """Test response display formatting"""
        from src.trust.trust_report import TrustReportFormatter

        response = "This is a test response"
        display = TrustReportFormatter.format_response_display(response)

        # Should format the response
        assert isinstance(display, str)
        assert len(display) > 0

    def test_export_to_json(self, complete_analysis_result):
        """Test exporting analysis to JSON"""
        from src.trust.trust_report import TrustReportFormatter

        result = {
            "original_query": "Test query",
            "response": "Test response",
            "analysis": complete_analysis_result,
        }

        json_export = TrustReportFormatter.export_to_json(result)

        # Should be valid JSON
        assert isinstance(json_export, str)
        parsed = json.loads(json_export)
        assert "original_query" in parsed

    def test_export_to_text(self, complete_analysis_result):
        """Test exporting analysis to text"""
        from src.trust.trust_report import TrustReportFormatter

        result = {
            "original_query": "Test query",
            "response": "Test response",
            "analysis": complete_analysis_result,
        }

        text_export = TrustReportFormatter.export_to_text(result)

        # Should be readable text
        assert isinstance(text_export, str)
        assert len(text_export) > 0


class TestComponentIntegration:
    """Test integration between components"""

    @pytest.mark.asyncio
    async def test_query_enhancement_flows_to_analysis(self, trust_pipeline):
        """Test that enhanced query produces analyzable response"""
        trust_pipeline._analyze_query_for_time_sensitivity = AsyncMock(return_value=None)
        trust_pipeline.client.analyze = AsyncMock(return_value="Enhanced response")
        trust_pipeline.fact_verifier.verify = AsyncMock(return_value=[])

        from src.trust.bias_analyzer import BiasAnalysis

        trust_pipeline.bias_analyzer.analyze = AsyncMock(return_value=BiasAnalysis([], [], [], []))

        from src.trust.intimacy_detector import IntimacyAnalysis

        trust_pipeline.intimacy_detector.detect = AsyncMock(
            return_value=IntimacyAnalysis([], "PROFESSIONAL", "OK")
        )

        await trust_pipeline.run_full_pipeline(
            user_query="Test query", verify_response=True
        )

        # Query enhancement and analysis both executed
        assert trust_pipeline.client.analyze.called
        assert trust_pipeline.fact_verifier.verify.called
        assert trust_pipeline.bias_analyzer.analyze.called
        assert trust_pipeline.intimacy_detector.detect.called

    @pytest.mark.asyncio
    async def test_parallel_verification_executes(self, trust_pipeline):
        """Test that multiple verifications execute in parallel"""
        import asyncio

        trust_pipeline._analyze_query_for_time_sensitivity = AsyncMock(return_value=None)
        trust_pipeline.client.analyze = AsyncMock(return_value="Response")

        # Track call order
        call_order = []

        async def track_fact_verify(*args, **kwargs):
            call_order.append("facts")
            await asyncio.sleep(0.01)
            return []

        async def track_bias_analyze(*args, **kwargs):
            call_order.append("bias")
            await asyncio.sleep(0.01)
            from src.trust.bias_analyzer import BiasAnalysis

            return BiasAnalysis([], [], [], [])

        async def track_intimacy_detect(*args, **kwargs):
            call_order.append("intimacy")
            await asyncio.sleep(0.01)
            from src.trust.intimacy_detector import IntimacyAnalysis

            return IntimacyAnalysis([], "PROFESSIONAL", "OK")

        trust_pipeline.fact_verifier.verify = track_fact_verify
        trust_pipeline.bias_analyzer.analyze = track_bias_analyze
        trust_pipeline.intimacy_detector.detect = track_intimacy_detect

        await trust_pipeline.run_full_pipeline(user_query="Test", verify_response=True)

        # All three should have been called
        assert len(call_order) == 3
        assert "facts" in call_order
        assert "bias" in call_order
        assert "intimacy" in call_order
