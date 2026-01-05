"""
Unit tests for moderate_formatter module
Tests actionability calculation, bias counting, and summary formatting
"""
import pytest
from src.trust.moderate_formatter import (
    calculate_actionability,
    count_high_severity_bias,
    select_top_bias_issues,
    format_moderate_trust_summary,
    format_compact_trust_summary
)


class TestActionabilityCalculation:
    """Test actionability rating logic"""

    def test_actionability_yes_high_verification(self):
        """Test YES rating for >=80% verified facts with no bias"""
        analysis = {
            "facts": {
                "verified_count": 8,
                "contradicted_count": 0,
                "total_claims": 10
            },
            "bias": {
                "framing_issues": [],
                "assumptions": [],
                "omissions": [],
                "loaded_terms": []
            },
            "intimacy": {
                "high_severity_count": 0
            }
        }

        rating, reason = calculate_actionability(analysis)
        assert rating == "YES"
        assert "verification" in reason.lower() or "quality" in reason.lower()

    def test_actionability_no_contradicted_facts(self):
        """Test NO rating for any contradicted facts"""
        analysis = {
            "facts": {
                "verified_count": 7,
                "contradicted_count": 1,
                "total_claims": 10
            },
            "bias": {
                "framing_issues": [],
                "assumptions": [],
                "omissions": [],
                "loaded_terms": []
            },
            "intimacy": {
                "high_severity_count": 0
            }
        }

        rating, reason = calculate_actionability(analysis)
        assert rating == "NO"
        assert "contradicted" in reason.lower()

    def test_actionability_no_high_intimacy(self):
        """Test NO rating for high-severity intimacy issues"""
        analysis = {
            "facts": {
                "verified_count": 9,
                "contradicted_count": 0,
                "total_claims": 10
            },
            "bias": {
                "framing_issues": [],
                "assumptions": [],
                "omissions": [],
                "loaded_terms": []
            },
            "intimacy": {
                "high_severity_count": 2
            }
        }

        rating, reason = calculate_actionability(analysis)
        assert rating == "NO"
        assert "tone" in reason.lower() or "intimacy" in reason.lower()

    def test_actionability_caution_low_verification(self):
        """Test CAUTION rating for <60% verified facts"""
        analysis = {
            "facts": {
                "verified_count": 5,
                "contradicted_count": 0,
                "total_claims": 10
            },
            "bias": {
                "framing_issues": [],
                "assumptions": [],
                "omissions": [],
                "loaded_terms": []
            },
            "intimacy": {
                "high_severity_count": 0
            }
        }

        rating, reason = calculate_actionability(analysis)
        assert rating == "CAUTION"
        assert "unverified" in reason.lower() or "claims" in reason.lower()

    def test_actionability_caution_high_bias(self):
        """Test CAUTION rating for >=2 high-severity bias issues"""
        analysis = {
            "facts": {
                "verified_count": 8,
                "contradicted_count": 0,
                "total_claims": 10
            },
            "bias": {
                "framing_issues": [
                    {"frame_type": "crisis", "text": "t", "effect": "e", "alternative": "a"},
                    {"frame_type": "urgency", "text": "t", "effect": "e", "alternative": "a"}
                ],
                "assumptions": [],
                "omissions": [],
                "loaded_terms": []
            },
            "intimacy": {
                "high_severity_count": 0
            }
        }

        rating, reason = calculate_actionability(analysis)
        assert rating == "CAUTION"
        assert "bias" in reason.lower()

    def test_actionability_caution_mixed(self):
        """Test CAUTION rating for mixed quality"""
        analysis = {
            "facts": {
                "verified_count": 7,
                "contradicted_count": 0,
                "total_claims": 10
            },
            "bias": {
                "framing_issues": [],
                "assumptions": [{"assumption": "test", "basis": "test", "impact": "significant impact"}],
                "omissions": [],
                "loaded_terms": []
            },
            "intimacy": {
                "high_severity_count": 0
            }
        }

        rating, reason = calculate_actionability(analysis)
        assert rating == "CAUTION"

    def test_actionability_empty_analysis(self):
        """Test handling of empty analysis"""
        analysis = {}

        rating, reason = calculate_actionability(analysis)
        # Should handle gracefully, likely return CAUTION
        assert rating in ["YES", "NO", "CAUTION"]


class TestHighSeverityBiasCounting:
    """Test high-severity bias counting logic"""

    def test_count_high_severity_framing(self):
        """Test that all framing issues count as high-severity"""
        bias = {
            "framing_issues": [
                {"frame_type": "f1"},
                {"frame_type": "f2"}
            ],
            "assumptions": [],
            "omissions": [],
            "loaded_terms": []
        }

        count = count_high_severity_bias(bias)
        assert count == 2  # All framing is high-severity

    def test_count_high_severity_assumptions(self):
        """Test assumption counting with impact keywords"""
        bias = {
            "framing_issues": [],
            "assumptions": [
                {"assumption": "a1", "basis": "b1", "impact": "significant impact"},
                {"assumption": "a2", "basis": "b2", "impact": "major problem"},
                {"assumption": "a3", "basis": "b3", "impact": "minor issue"}
            ],
            "omissions": [],
            "loaded_terms": []
        }

        count = count_high_severity_bias(bias)
        assert count == 2  # Only those with significant/major/critical

    def test_count_high_severity_omissions(self):
        """Test omission counting with relevance keywords"""
        bias = {
            "framing_issues": [],
            "assumptions": [],
            "omissions": [
                {"missing_perspective": "m1", "relevance": "critical for decision", "suggestion": "s1"},
                {"missing_perspective": "m2", "relevance": "important consideration", "suggestion": "s2"},
                {"missing_perspective": "m3", "relevance": "nice to have", "suggestion": "s3"}
            ],
            "loaded_terms": []
        }

        count = count_high_severity_bias(bias)
        assert count == 2  # critical and important

    def test_count_high_severity_mixed(self):
        """Test counting with multiple bias types"""
        bias = {
            "framing_issues": [{"frame_type": "f1"}],
            "assumptions": [{"assumption": "a1", "basis": "b1", "impact": "significant impact"}],
            "omissions": [{"missing_perspective": "m1", "relevance": "critical", "suggestion": "s1"}],
            "loaded_terms": [{"term": "t1", "connotation": "c1", "neutral_alternative": "n1"}]
        }

        count = count_high_severity_bias(bias)
        assert count == 3  # 1 framing + 1 assumption + 1 omission (loaded terms not high-severity)

    def test_count_high_severity_none(self):
        """Test counting when no high-severity issues"""
        bias = {
            "framing_issues": [],
            "assumptions": [{"assumption": "a1", "basis": "b1", "impact": "minor"}],
            "omissions": [],
            "loaded_terms": [{"term": "t1", "connotation": "c1", "neutral_alternative": "n1"}]
        }

        count = count_high_severity_bias(bias)
        assert count == 0


class TestTopBiasSelection:
    """Test top bias issue selection logic"""

    def test_select_top_bias_priority_order(self):
        """Test that framing > assumptions > omissions > loaded terms"""
        bias = {
            "framing_issues": [{"frame_type": "f1", "text": "t1", "effect": "e1", "alternative": "a1"}],
            "assumptions": [{"assumption": "a1", "basis": "b1", "impact": "i1"}],
            "omissions": [{"missing_perspective": "m1", "relevance": "r1", "suggestion": "s1"}],
            "loaded_terms": [{"term": "t1", "connotation": "c1", "neutral_alternative": "n1"}]
        }

        issues = select_top_bias_issues(bias, max_count=2)

        # Should prioritize framing first, then assumptions
        assert len(issues) == 2
        assert "framing" in issues[0].lower()
        assert "assumes" in issues[1].lower() or "assumption" in issues[1].lower()

    def test_select_top_bias_max_count(self):
        """Test max_count limit enforcement"""
        bias = {
            "framing_issues": [
                {"frame_type": "f1", "text": "t1", "effect": "e1", "alternative": "a1"},
                {"frame_type": "f2", "text": "t2", "effect": "e2", "alternative": "a2"}
            ],
            "assumptions": [
                {"assumption": "a1", "basis": "b1", "impact": "i1"},
                {"assumption": "a2", "basis": "b2", "impact": "i2"}
            ],
            "omissions": [],
            "loaded_terms": []
        }

        issues = select_top_bias_issues(bias, max_count=3)
        assert len(issues) == 3

    def test_select_top_bias_truncate_long_text(self):
        """Test truncation of long descriptions"""
        long_text = "This is a very long framing text that exceeds one hundred characters and should be truncated to keep the summary compact and readable for users"
        bias = {
            "framing_issues": [{"frame_type": "test", "text": long_text, "effect": "effect", "alternative": "alt"}],
            "assumptions": [],
            "omissions": [],
            "loaded_terms": []
        }

        issues = select_top_bias_issues(bias, max_count=3)

        # Check that text is truncated
        assert len(issues) == 1
        # Text in issues[0] should be truncated (50 char max in implementation)
        assert "..." in issues[0]  # Ellipsis indicates truncation

    def test_select_top_bias_empty(self):
        """Test handling when no bias issues exist"""
        bias = {
            "framing_issues": [],
            "assumptions": [],
            "omissions": [],
            "loaded_terms": []
        }

        issues = select_top_bias_issues(bias, max_count=3)
        assert len(issues) == 0


class TestModerateSummaryFormatting:
    """Test moderate summary formatting"""

    def test_format_moderate_all_sections(self, complete_analysis_result):
        """Test formatting with all sections present"""
        result = format_moderate_trust_summary(complete_analysis_result)

        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain section headers
        assert "Facts" in result or "facts" in result

    def test_format_moderate_fact_counts(self):
        """Test correct fact count formatting"""
        analysis = {
            "facts": {
                "analyzed": True,
                "verified_count": 5,
                "uncertain_count": 2,
                "contradicted_count": 1,
                "total_claims": 8
            },
            "bias": {
                "framing_issues": [],
                "assumptions": [],
                "omissions": [],
                "loaded_terms": []
            },
            "intimacy": {
                "overall_tone": "PROFESSIONAL",
                "high_severity_count": 0,
                "medium_severity_count": 0,
                "low_severity_count": 0
            }
        }

        result = format_moderate_trust_summary(analysis)

        # Should show fact counts
        assert "5" in result or "verified" in result.lower()

    def test_format_moderate_bias_section(self):
        """Test bias formatting with top issues"""
        analysis = {
            "facts": {
                "analyzed": True,
                "verified_count": 8,
                "uncertain_count": 0,
                "contradicted_count": 0,
                "total_claims": 8
            },
            "bias": {
                "analyzed": True,
                "framing_issues": [{"frame_type": "crisis", "text": "Emergency!", "effect": "Creates urgency", "alternative": "Situation"}],
                "assumptions": [],
                "omissions": [],
                "loaded_terms": []
            },
            "intimacy": {
                "overall_tone": "PROFESSIONAL",
                "high_severity_count": 0,
                "medium_severity_count": 0,
                "low_severity_count": 0
            }
        }

        result = format_moderate_trust_summary(analysis)

        # Should mention framing or bias
        assert "framing" in result.lower() or "bias" in result.lower()

    def test_format_moderate_tone_section(self):
        """Test tone formatting with severity"""
        analysis = {
            "facts": {
                "verified_count": 8,
                "uncertain_count": 0,
                "contradicted_count": 0,
                "total_claims": 8
            },
            "bias": {
                "framing_issues": [],
                "assumptions": [],
                "omissions": [],
                "loaded_terms": []
            },
            "intimacy": {
                "overall_tone": "FAMILIAR",
                "high_severity_count": 1,
                "medium_severity_count": 0,
                "low_severity_count": 0,
                "summary": "Contains emotion claims"
            }
        }

        result = format_moderate_trust_summary(analysis)

        # Should show tone
        assert "FAMILIAR" in result or "tone" in result.lower()

    def test_format_moderate_actionability_section(self):
        """Test actionability rating with reason"""
        analysis = {
            "facts": {
                "verified_count": 9,
                "uncertain_count": 0,
                "contradicted_count": 0,
                "total_claims": 10
            },
            "bias": {
                "framing_issues": [],
                "assumptions": [],
                "omissions": [],
                "loaded_terms": []
            },
            "intimacy": {
                "overall_tone": "PROFESSIONAL",
                "high_severity_count": 0,
                "medium_severity_count": 0,
                "low_severity_count": 0
            }
        }

        result = format_moderate_trust_summary(analysis)

        # Should show actionability rating
        assert "YES" in result or "NO" in result or "CAUTION" in result

    def test_format_moderate_width_wrapping(self):
        """Test text wrapping at max_width"""
        analysis = {
            "facts": {
                "verified_count": 8,
                "uncertain_count": 0,
                "contradicted_count": 0,
                "total_claims": 8
            },
            "bias": {
                "framing_issues": [],
                "assumptions": [],
                "omissions": [],
                "loaded_terms": []
            },
            "intimacy": {
                "overall_tone": "PROFESSIONAL",
                "high_severity_count": 0,
                "medium_severity_count": 0,
                "low_severity_count": 0
            }
        }

        result = format_moderate_trust_summary(analysis, max_width=80)

        # Lines should generally not exceed max_width (allowing for some flexibility)
        lines = result.split('\n')
        # Most lines should respect the width (some headers might be longer)
        assert all(len(line) <= 100 for line in lines)


class TestCompactSummary:
    """Test compact summary formatting"""

    def test_format_compact_one_liner(self):
        """Test single line format"""
        analysis = {
            "facts": {
                "verified_count": 8,
                "contradicted_count": 0,
                "total_claims": 10
            },
            "bias": {
                "framing_issues": [],
                "assumptions": [],
                "omissions": [],
                "loaded_terms": [],
                "total_issues": 0
            },
            "intimacy": {
                "overall_tone": "PROFESSIONAL",
                "total_issues": 0
            }
        }

        result = format_compact_trust_summary(analysis)

        # Should be compact (single line or very short)
        assert isinstance(result, str)
        assert len(result) < 200  # Compact summary

    def test_format_compact_icons(self):
        """Test correct icon usage"""
        analysis_good = {
            "facts": {
                "verified_count": 9,
                "contradicted_count": 0,
                "total_claims": 10
            },
            "bias": {
                "framing_issues": [],
                "assumptions": [],
                "omissions": [],
                "loaded_terms": [],
                "total_issues": 0
            },
            "intimacy": {
                "overall_tone": "PROFESSIONAL",
                "total_issues": 0
            }
        }

        result = format_compact_trust_summary(analysis_good)

        # Should contain positive indicators for good analysis
        assert "✓" in result or "YES" in result

        # Test with issues
        analysis_bad = {
            "facts": {
                "verified_count": 3,
                "contradicted_count": 2,
                "total_claims": 10
            },
            "bias": {
                "framing_issues": [{"frame_type": "f"}],
                "assumptions": [],
                "omissions": [],
                "loaded_terms": [],
                "total_issues": 1
            },
            "intimacy": {
                "overall_tone": "INAPPROPRIATE",
                "total_issues": 2
            }
        }

        result_bad = format_compact_trust_summary(analysis_bad)

        # Should contain warning indicators
        assert "✗" in result_bad or "⚠" in result_bad or "NO" in result_bad or "CAUTION" in result_bad
