"""
Unit tests for BiasAnalyzer
Tests framing, assumptions, omissions, and loaded language detection
"""

import json

import pytest

from src.trust.bias_analyzer import (
    Assumption,
    BiasAnalysis,
    FramingIssue,
    LoadedTerm,
    Omission,
)


class TestMainAnalysis:
    """Test main bias analysis functionality"""

    @pytest.mark.asyncio
    async def test_analyze_no_bias(self, bias_analyzer, mock_claude_client):
        """Test clean response with no bias issues"""
        mock_claude_client.analyze.return_value = json.dumps(
            {"framing": [], "assumptions": [], "omissions": [], "loaded_language": []}
        )

        response = "Python is a programming language. It was created in 1991."
        analysis = await bias_analyzer.analyze(response)

        assert isinstance(analysis, BiasAnalysis)
        assert len(analysis.framing_issues) == 0
        assert len(analysis.assumptions) == 0
        assert len(analysis.omissions) == 0
        assert len(analysis.loaded_terms) == 0
        assert analysis.to_dict()["total_issues"] == 0

    @pytest.mark.asyncio
    async def test_analyze_framing_issues(self, bias_analyzer, mock_claude_client):
        """Test detection of framing bias"""
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "framing": [
                    {
                        "frame_type": "crisis-urgency",
                        "text": "The situation demands immediate action",
                        "effect": "Creates artificial urgency without justification",
                        "alternative": "The situation requires careful consideration",
                    }
                ],
                "assumptions": [],
                "omissions": [],
                "loaded_language": [],
            }
        )

        response = "The situation demands immediate action"
        analysis = await bias_analyzer.analyze(response)

        assert len(analysis.framing_issues) == 1
        assert analysis.framing_issues[0].frame_type == "crisis-urgency"
        assert "immediate action" in analysis.framing_issues[0].text

    @pytest.mark.asyncio
    async def test_analyze_assumptions(self, bias_analyzer, mock_claude_client):
        """Test detection of hidden assumptions"""
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "framing": [],
                "assumptions": [
                    {
                        "assumption": "All users prioritize speed over accessibility",
                        "basis": "Focus on performance without mentioning accessibility",
                        "impact": "Excludes users with disabilities from consideration",
                    }
                ],
                "omissions": [],
                "loaded_language": [],
            }
        )

        response = "We optimized for maximum speed"
        analysis = await bias_analyzer.analyze(response)

        assert len(analysis.assumptions) == 1
        assert "accessibility" in analysis.assumptions[0].assumption.lower()
        assert analysis.to_dict()["total_issues"] == 1

    @pytest.mark.asyncio
    async def test_analyze_omissions(self, bias_analyzer, mock_claude_client):
        """Test detection of missing perspectives"""
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "framing": [],
                "assumptions": [],
                "omissions": [
                    {
                        "missing_perspective": "Environmental impact of the solution",
                        "relevance": "Critical for sustainability assessment",
                        "suggestion": "Include carbon footprint analysis",
                    }
                ],
                "loaded_language": [],
            }
        )

        response = "This is the best technical solution"
        analysis = await bias_analyzer.analyze(response)

        assert len(analysis.omissions) == 1
        assert "environmental" in analysis.omissions[0].missing_perspective.lower()

    @pytest.mark.asyncio
    async def test_analyze_loaded_terms(self, bias_analyzer, mock_claude_client):
        """Test detection of loaded language"""
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "framing": [],
                "assumptions": [],
                "omissions": [],
                "loaded_language": [
                    {
                        "term": "radical changes",
                        "connotation": "Extreme, potentially dangerous",
                        "neutral_alternative": "significant changes",
                    }
                ],
            }
        )

        response = "We propose radical changes to the system"
        analysis = await bias_analyzer.analyze(response)

        assert len(analysis.loaded_terms) == 1
        assert "radical" in analysis.loaded_terms[0].term.lower()
        assert "significant" in analysis.loaded_terms[0].neutral_alternative.lower()

    @pytest.mark.asyncio
    async def test_analyze_all_categories(
        self, bias_analyzer, mock_claude_client, json_bias_analysis_response
    ):
        """Test response with all bias types present"""
        mock_claude_client.analyze.return_value = json_bias_analysis_response

        response = "The crisis demands action. We optimized for speed. This is radical."
        analysis = await bias_analyzer.analyze(response)

        assert len(analysis.framing_issues) == 1
        assert len(analysis.assumptions) == 1
        assert len(analysis.omissions) == 1
        assert len(analysis.loaded_terms) == 1
        assert analysis.to_dict()["total_issues"] == 4

    @pytest.mark.asyncio
    async def test_analyze_json_parse_error(self, bias_analyzer, mock_claude_client):
        """Test handling of malformed JSON"""
        mock_claude_client.analyze.return_value = "Invalid JSON {{"

        response = "Test response"
        analysis = await bias_analyzer.analyze(response)

        # Should return empty analysis on error
        assert isinstance(analysis, BiasAnalysis)
        assert len(analysis.framing_issues) == 0
        assert len(analysis.assumptions) == 0

    @pytest.mark.asyncio
    async def test_analyze_api_error(self, bias_analyzer, mock_claude_client):
        """Test handling of Claude API errors"""
        mock_claude_client.analyze.side_effect = Exception("API Error")

        response = "Test response"
        analysis = await bias_analyzer.analyze(response)

        # Should return empty analysis on error
        assert isinstance(analysis, BiasAnalysis)
        assert analysis.to_dict()["total_issues"] == 0

    @pytest.mark.asyncio
    async def test_analyze_empty_response(self, bias_analyzer, mock_claude_client):
        """Test handling of empty input"""
        mock_claude_client.analyze.return_value = json.dumps(
            {"framing": [], "assumptions": [], "omissions": [], "loaded_language": []}
        )

        response = ""
        analysis = await bias_analyzer.analyze(response)

        assert isinstance(analysis, BiasAnalysis)
        assert analysis.to_dict()["total_issues"] == 0

    @pytest.mark.asyncio
    async def test_analyze_with_text_wrapped_json(self, bias_analyzer, mock_claude_client):
        """Test JSON extraction from explanatory text"""
        json_content = {
            "framing": [
                {"frame_type": "test", "text": "test", "effect": "test", "alternative": "test"}
            ],
            "assumptions": [],
            "omissions": [],
            "loaded_language": [],
        }
        wrapped = f"Here's the analysis:\n```json\n{json.dumps(json_content)}\n```\nEnd"

        mock_claude_client.analyze.return_value = wrapped

        response = "Test response"
        analysis = await bias_analyzer.analyze(response)

        assert len(analysis.framing_issues) == 1


class TestDataStructureConversions:
    """Test data structure serialization"""

    def test_framing_issue_to_dict(self):
        """Test FramingIssue serialization"""
        issue = FramingIssue(
            frame_type="crisis",
            text="Emergency situation",
            effect="Creates urgency",
            alternative="Situation requiring attention",
        )

        result = issue.to_dict()
        assert result["frame_type"] == "crisis"
        assert result["text"] == "Emergency situation"
        assert result["effect"] == "Creates urgency"
        assert result["alternative"] == "Situation requiring attention"

    def test_assumption_to_dict(self):
        """Test Assumption serialization"""
        assumption = Assumption(
            assumption="Everyone wants speed",
            basis="Performance focus",
            impact="Ignores accessibility",
        )

        result = assumption.to_dict()
        assert result["assumption"] == "Everyone wants speed"
        assert result["basis"] == "Performance focus"
        assert result["impact"] == "Ignores accessibility"

    def test_omission_to_dict(self):
        """Test Omission serialization"""
        omission = Omission(
            missing_perspective="Environmental impact",
            relevance="Critical for sustainability",
            suggestion="Include carbon analysis",
        )

        result = omission.to_dict()
        assert result["missing_perspective"] == "Environmental impact"
        assert result["relevance"] == "Critical for sustainability"
        assert result["suggestion"] == "Include carbon analysis"

    def test_loaded_term_to_dict(self):
        """Test LoadedTerm serialization"""
        term = LoadedTerm(term="radical", connotation="Extreme", neutral_alternative="significant")

        result = term.to_dict()
        assert result["term"] == "radical"
        assert result["connotation"] == "Extreme"
        assert result["neutral_alternative"] == "significant"

    def test_bias_analysis_to_dict(self):
        """Test complete BiasAnalysis serialization"""
        analysis = BiasAnalysis(
            framing_issues=[FramingIssue("crisis", "text", "effect", "alt")],
            assumptions=[Assumption("assumption", "basis", "impact")],
            omissions=[Omission("missing", "relevance", "suggestion")],
            loaded_terms=[LoadedTerm("term", "connotation", "alternative")],
        )

        result = analysis.to_dict()
        assert len(result["framing_issues"]) == 1
        assert len(result["assumptions"]) == 1
        assert len(result["omissions"]) == 1
        assert len(result["loaded_terms"]) == 1
        assert result["total_issues"] == 4

    def test_bias_analysis_total_issues(self):
        """Test total issues count calculation"""
        # Empty analysis
        empty = BiasAnalysis([], [], [], [])
        assert empty.to_dict()["total_issues"] == 0

        # Multiple issues
        multiple = BiasAnalysis(
            framing_issues=[FramingIssue("f1", "t", "e", "a"), FramingIssue("f2", "t", "e", "a")],
            assumptions=[Assumption("a1", "b", "i")],
            omissions=[],
            loaded_terms=[LoadedTerm("t1", "c", "n"), LoadedTerm("t2", "c", "n")],
        )
        assert multiple.to_dict()["total_issues"] == 5


class TestHelperMethods:
    """Test helper methods"""

    def test_clean_json_response(self, bias_analyzer):
        """Test JSON cleaning from markdown wrappers"""
        json_data = '{"test": "value"}'

        # With markdown wrapper
        wrapped = f"```json\n{json_data}\n```"
        assert bias_analyzer._clean_json_response(wrapped) == json_data

        # Without wrapper
        assert bias_analyzer._clean_json_response(json_data) == json_data

    def test_clean_json_complex_text(self, bias_analyzer):
        """Test JSON extraction from complex surrounding text"""
        json_data = '{"framing": [], "assumptions": []}'

        # Text before and after
        complex_text = f"Analysis results:\n{json_data}\nEnd of analysis"

        # The method extracts between first { and last }
        cleaned = bias_analyzer._clean_json_response(complex_text)

        # Should extract the JSON portion
        import json as json_lib

        parsed = json_lib.loads(cleaned)
        assert "framing" in parsed
        assert "assumptions" in parsed
