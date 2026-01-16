"""
Unit tests for TrustReportFormatter
Tests formatting methods including recent enhancement to format_compact_summary()
"""

from src.trust.trust_report import TrustReportFormatter


class TestResponseDisplay:
    """Test response display formatting"""

    def test_format_response_display_full(self):
        """Test display of complete response without truncation"""
        response = "This is a test response about Python programming."
        result = TrustReportFormatter.format_response_display(response)

        assert "CLAUDE RESPONSE" in result
        assert response in result
        assert "=" * 70 in result

    def test_format_response_display_truncated(self):
        """Test truncation of long responses"""
        response = "A" * 1000
        result = TrustReportFormatter.format_response_display(response, max_length=100)

        assert response[:100] in result
        assert "truncated" in result
        assert "1000 chars total" in result

    def test_format_response_display_empty(self):
        """Test handling of empty response"""
        response = ""
        result = TrustReportFormatter.format_response_display(response)

        assert "CLAUDE RESPONSE" in result
        assert "=" * 70 in result


class TestTrustAnalysisFormatting:
    """Test comprehensive trust analysis formatting"""

    def test_format_trust_analysis_complete(self, complete_analysis_result):
        """Test formatting with all analysis types present"""
        result = TrustReportFormatter.format_trust_analysis(complete_analysis_result)

        assert "TRUST ANALYSIS" in result
        assert "FACT VERIFICATION" in result
        assert "BIAS ANALYSIS" in result
        assert "INTIMACY DETECTION" in result

    def test_format_trust_analysis_facts_only(self, sample_fact_analysis):
        """Test formatting with only fact verification"""
        analysis = {"analyzed": True, "facts": sample_fact_analysis}
        result = TrustReportFormatter.format_trust_analysis(analysis)

        assert "FACT VERIFICATION" in result
        assert "Python was created in 1991" in result
        assert "VERIFIED" in result

    def test_format_trust_analysis_with_temporal_check(self, sample_fact_analysis):
        """Test display of temporal verification results"""
        analysis = {"analyzed": True, "facts": sample_fact_analysis}
        result = TrustReportFormatter.format_trust_analysis(analysis)

        # Should show outdated fact with temporal check
        assert "OUTDATED" in result or "TEMPORAL CHECK" in result

    def test_format_trust_analysis_with_caveats(self):
        """Test display of caveats properly"""
        analysis = {
            "analyzed": True,
            "facts": {
                "verifications": [
                    {
                        "claim": {"text": "Test claim", "type": "FACT"},
                        "verdict": "VERIFIED",
                        "confidence": 0.9,
                        "reasoning": "Verified",
                        "caveats": ["Caveat 1", "Caveat 2"],
                        "contradictions": [],
                    }
                ]
            },
        }
        result = TrustReportFormatter.format_trust_analysis(analysis)

        assert "Caveat 1" in result
        assert "Caveat 2" in result

    def test_format_trust_analysis_with_contradictions(self):
        """Test display of contradictions properly"""
        analysis = {
            "analyzed": True,
            "facts": {
                "verifications": [
                    {
                        "claim": {"text": "Wrong fact", "type": "FACT"},
                        "verdict": "CONTRADICTED",
                        "confidence": 0.9,
                        "reasoning": "Contradicted",
                        "caveats": [],
                        "contradictions": ["Contradiction 1", "Contradiction 2"],
                    }
                ]
            },
        }
        result = TrustReportFormatter.format_trust_analysis(analysis)

        assert "Contradiction 1" in result
        assert "Contradiction 2" in result

    def test_format_trust_analysis_no_analysis(self):
        """Test handling of no analysis run"""
        analysis = {"analyzed": False, "message": "Analysis not available"}
        result = TrustReportFormatter.format_trust_analysis(analysis)

        assert "Analysis not available" in result

    def test_format_trust_analysis_bias_only(self, sample_bias_analysis):
        """Test formatting with only bias analysis"""
        analysis = {"analyzed": True, "bias": sample_bias_analysis}
        analysis["bias"]["analyzed"] = True
        result = TrustReportFormatter.format_trust_analysis(analysis)

        assert "BIAS ANALYSIS" in result

    def test_format_trust_analysis_intimacy_only(self, sample_intimacy_analysis):
        """Test formatting with only intimacy detection"""
        analysis = {"analyzed": True, "intimacy": sample_intimacy_analysis}
        analysis["intimacy"]["analyzed"] = True
        result = TrustReportFormatter.format_trust_analysis(analysis)

        assert "INTIMACY DETECTION" in result


class TestCompactSummary:
    """Test compact summary formatting - includes recent enhancement tests"""

    def test_format_compact_summary_all_verified(self):
        """Test summary when all facts are verified (no detail section needed)"""
        analysis = {
            "analyzed": True,
            "facts": {
                "verifications": [
                    {
                        "verdict": "VERIFIED",
                        "claim": {"text": "Fact 1"},
                        "confidence": 0.9,
                        "reasoning": "Verified",
                    },
                    {
                        "verdict": "VERIFIED",
                        "claim": {"text": "Fact 2"},
                        "confidence": 0.95,
                        "reasoning": "Verified",
                    },
                ],
                "verified_count": 2,
                "uncertain_count": 0,
                "contradicted_count": 0,
            },
        }
        result = TrustReportFormatter.format_compact_summary(analysis)

        assert "Facts: ✓ 2" in result
        assert "Unverifiable Facts:" not in result

    def test_format_compact_summary_with_unverifiable(self):
        """ENHANCEMENT TEST: Show unverifiable facts with brief explanations"""
        analysis = {
            "analyzed": True,
            "facts": {
                "verifications": [
                    {
                        "verdict": "VERIFIED",
                        "claim": {"text": "Verified fact"},
                        "confidence": 0.9,
                        "reasoning": "Confirmed",
                    },
                    {
                        "verdict": "UNVERIFIABLE",
                        "claim": {"text": "Cannot verify this claim"},
                        "confidence": 0.0,
                        "reasoning": "No authoritative source available for verification beyond model knowledge cutoff",
                    },
                    {
                        "verdict": "UNVERIFIABLE",
                        "claim": {"text": "Another unverifiable claim"},
                        "confidence": 0.0,
                        "reasoning": "Claim is speculation and cannot be factually verified",
                    },
                ],
                "verified_count": 1,
                "uncertain_count": 2,
                "contradicted_count": 0,
            },
        }
        result = TrustReportFormatter.format_compact_summary(analysis)

        # Check main summary line
        assert "Facts: ✓ 1 | ? 2" in result

        # Check unverifiable section exists
        assert "Unverifiable Facts:" in result

        # Check both claims are listed
        assert "Cannot verify this claim" in result
        assert "Another unverifiable claim" in result

        # Check reasons are included
        assert "Reason:" in result
        assert "No authoritative source available" in result
        assert "Claim is speculation" in result

    def test_format_compact_summary_with_contradicted(self):
        """ENHANCEMENT TEST: Show contradicted facts with contradictions"""
        analysis = {
            "analyzed": True,
            "facts": {
                "verifications": [
                    {
                        "verdict": "CONTRADICTED",
                        "claim": {"text": "Wrong fact about president"},
                        "confidence": 0.9,
                        "reasoning": "This contradicts current factual information. The president is not John Smith",
                    },
                    {
                        "verdict": "VERIFIED",
                        "claim": {"text": "Correct fact"},
                        "confidence": 0.95,
                        "reasoning": "Verified",
                    },
                ],
                "verified_count": 1,
                "uncertain_count": 0,
                "contradicted_count": 1,
            },
        }
        result = TrustReportFormatter.format_compact_summary(analysis)

        # Check main summary
        assert "Facts: ✓ 1 | ✗ 1" in result

        # Check contradicted section exists
        assert "Contradicted Facts:" in result

        # Check claim and contradiction are shown
        assert "Wrong fact about president" in result
        assert "Contradiction:" in result
        assert "This contradicts current factual information" in result

    def test_format_compact_summary_with_outdated(self):
        """ENHANCEMENT TEST: Show outdated facts with updates"""
        analysis = {
            "analyzed": True,
            "facts": {
                "verifications": [
                    {
                        "verdict": "OUTDATED",
                        "claim": {"text": "Old CEO information"},
                        "confidence": 0.85,
                        "reasoning": "This claim was true in 2023 but is now outdated. Current CEO is John Brown",
                    },
                    {
                        "verdict": "VERIFIED",
                        "claim": {"text": "Current fact"},
                        "confidence": 0.9,
                        "reasoning": "Verified",
                    },
                ],
                "verified_count": 1,
                "uncertain_count": 0,
                "contradicted_count": 0,
            },
        }
        result = TrustReportFormatter.format_compact_summary(analysis)

        # Check main summary (outdated counted separately, not as verified)
        assert "⏰ 1" in result  # Outdated icon

        # Check outdated section exists
        assert "Outdated Facts:" in result

        # Check claim and update are shown
        assert "Old CEO information" in result
        assert "Update:" in result
        assert "This claim was true in 2023 but is now outdated" in result

    def test_format_compact_summary_mixed_issues(self):
        """ENHANCEMENT TEST: Multiple issue types together"""
        analysis = {
            "analyzed": True,
            "facts": {
                "verifications": [
                    {
                        "verdict": "VERIFIED",
                        "claim": {"text": "Good fact"},
                        "confidence": 0.95,
                        "reasoning": "Verified",
                    },
                    {
                        "verdict": "UNVERIFIABLE",
                        "claim": {"text": "Unknown fact"},
                        "confidence": 0.0,
                        "reasoning": "Cannot verify",
                    },
                    {
                        "verdict": "CONTRADICTED",
                        "claim": {"text": "Wrong fact"},
                        "confidence": 0.9,
                        "reasoning": "Contradicted by evidence",
                    },
                    {
                        "verdict": "OUTDATED",
                        "claim": {"text": "Old fact"},
                        "confidence": 0.8,
                        "reasoning": "Outdated information",
                    },
                ],
                "verified_count": 1,
                "uncertain_count": 1,
                "contradicted_count": 1,
            },
        }
        result = TrustReportFormatter.format_compact_summary(analysis)

        # Check all sections appear
        assert "Unverifiable Facts:" in result
        assert "Contradicted Facts:" in result
        assert "Outdated Facts:" in result

        # Check all claims listed
        assert "Unknown fact" in result
        assert "Wrong fact" in result
        assert "Old fact" in result

    def test_format_compact_summary_long_claims_truncation(self):
        """ENHANCEMENT TEST: Truncate claims >80 chars to 77..."""
        long_claim = "This is a very long claim that exceeds eighty characters and should be truncated to seventy-seven characters plus ellipsis"
        analysis = {
            "analyzed": True,
            "facts": {
                "verifications": [
                    {
                        "verdict": "UNVERIFIABLE",
                        "claim": {"text": long_claim},
                        "confidence": 0.0,
                        "reasoning": "Cannot verify",
                    }
                ],
                "verified_count": 0,
                "uncertain_count": 1,
                "contradicted_count": 0,
            },
        }
        result = TrustReportFormatter.format_compact_summary(analysis)

        # Should be truncated to 77 chars + "..."
        assert long_claim[:77] + "..." in result
        assert long_claim not in result  # Full claim should not appear

    def test_format_compact_summary_long_reasoning_truncation(self):
        """ENHANCEMENT TEST: Truncate reasoning >100 chars to first sentence or 97..."""
        long_reasoning = "This is a very long reasoning that exceeds one hundred characters and has multiple sentences. Second sentence here. Third sentence here that should not appear in the truncated version."
        analysis = {
            "analyzed": True,
            "facts": {
                "verifications": [
                    {
                        "verdict": "UNVERIFIABLE",
                        "claim": {"text": "Test claim"},
                        "confidence": 0.0,
                        "reasoning": long_reasoning,
                    }
                ],
                "verified_count": 0,
                "uncertain_count": 1,
                "contradicted_count": 0,
            },
        }
        result = TrustReportFormatter.format_compact_summary(analysis)

        # Should show first sentence only
        first_sentence = long_reasoning.split(".")[0]
        assert first_sentence in result
        assert "Second sentence" not in result
        assert "Third sentence" not in result

    def test_format_compact_summary_no_facts(self):
        """Test handling when no facts are found"""
        analysis = {
            "analyzed": True,
            "facts": {
                "verifications": [],
                "verified_count": 0,
                "uncertain_count": 0,
                "contradicted_count": 0,
            },
        }
        result = TrustReportFormatter.format_compact_summary(analysis)

        assert "Facts: none found" in result or "Facts:" in result

    def test_format_compact_summary_with_bias(self):
        """Test compact summary includes bias counts"""
        analysis = {
            "analyzed": True,
            "bias": {
                "framing_issues": [{"frame_type": "test"}],
                "assumptions": [{"assumption": "test"}],
                "omissions": [],
                "loaded_terms": [],
                "total_issues": 2,  # Add total_issues count
                "analyzed": True,
            },
        }
        result = TrustReportFormatter.format_compact_summary(analysis)

        assert "Bias:" in result
        # Should show counts: 1F (framing), 1A (assumptions)
        assert "1F" in result or "1A" in result or "⚠" in result

    def test_format_compact_summary_with_intimacy(self):
        """Test compact summary includes intimacy counts"""
        analysis = {
            "analyzed": True,
            "intimacy": {
                "total_issues": 2,
                "high_severity_count": 1,
                "medium_severity_count": 1,
                "low_severity_count": 0,
                "overall_tone": "FAMILIAR",
                "analyzed": True,
            },
        }
        result = TrustReportFormatter.format_compact_summary(analysis)

        assert "Tone:" in result
        assert "FAMILIAR" in result
        # Should show severity counts
        assert "1H" in result or "1M" in result

    def test_format_compact_summary_not_analyzed(self):
        """Test handling when analysis not run"""
        analysis = {"analyzed": False}
        result = TrustReportFormatter.format_compact_summary(analysis)

        assert "not" in result.lower() or "unavailable" in result.lower()


class TestModerateSummary:
    """Test moderate summary formatting"""

    def test_format_moderate_summary_complete(self, complete_analysis_result):
        """Test moderate summary with complete analysis"""
        result = TrustReportFormatter.format_moderate_summary(complete_analysis_result)

        # Should delegate to moderate_formatter
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_moderate_summary_not_analyzed(self):
        """Test moderate summary when analysis not run"""
        analysis = {"analyzed": False}
        result = TrustReportFormatter.format_moderate_summary(analysis)

        assert "UNAVAILABLE" in result or "not" in result.lower()


class TestExportFunctions:
    """Test export to JSON and text"""

    def test_export_to_json(self):
        """Test JSON export of complete results"""
        result = {
            "original_query": "Test query",
            "response": "Test response",
            "analysis": {"analyzed": True},
        }
        json_output = TrustReportFormatter.export_to_json(result)

        import json

        parsed = json.loads(json_output)
        assert parsed["original_query"] == "Test query"
        assert parsed["response"] == "Test response"
        assert parsed["analysis"]["analyzed"] is True

    def test_export_to_text(self):
        """Test text export of complete results"""
        result = {
            "original_query": "Test query",
            "response": "Test response",
            "analysis": {"analyzed": True, "facts": {"verifications": []}},
        }
        text_output = TrustReportFormatter.export_to_text(result)

        assert "INSIGHTWEAVER TRUST REPORT" in text_output
        assert "Test query" in text_output
        assert "Test response" in text_output

    def test_export_to_text_complete(self, complete_analysis_result):
        """Test full text report export"""
        result = {
            "original_query": "What is quantum computing?",
            "response": "Quantum computing is a computing paradigm...",
            "analysis": complete_analysis_result,
        }
        text_output = TrustReportFormatter.export_to_text(result)

        assert "What is quantum computing?" in text_output
        assert "Quantum computing" in text_output
        assert "End of Report" in text_output
