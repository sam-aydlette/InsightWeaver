"""
Unit tests for IntimacyDetector
Tests tone analysis and anthropomorphization detection
"""

import json

import pytest

from src.trust.intimacy_detector import IntimacyAnalysis, IntimacyIssue


class TestMainDetection:
    """Test main intimacy detection functionality"""

    @pytest.mark.asyncio
    async def test_detect_professional_tone(self, intimacy_detector, mock_claude_client):
        """Test detection of professional tone with no issues"""
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "issues": [],
                "overall_tone": "PROFESSIONAL",
                "summary": "Response maintains professional tone throughout",
            }
        )

        response = "I can assist you with your query. Here is the information you requested."
        analysis = await intimacy_detector.detect(response)

        assert isinstance(analysis, IntimacyAnalysis)
        assert len(analysis.issues) == 0
        assert analysis.overall_tone == "PROFESSIONAL"
        assert analysis.to_dict()["total_issues"] == 0

    @pytest.mark.asyncio
    async def test_detect_emotion_claims(self, intimacy_detector, mock_claude_client):
        """Test detection of emotion claims like 'I'm excited'"""
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "issues": [
                    {
                        "category": "EMOTION",
                        "text": "I'm excited to help you",
                        "explanation": "AI cannot experience emotions like excitement",
                        "severity": "HIGH",
                        "professional_alternative": "I'm ready to assist you",
                    }
                ],
                "overall_tone": "FAMILIAR",
                "summary": "Contains emotion claims",
            }
        )

        response = "I'm excited to help you with this!"
        analysis = await intimacy_detector.detect(response)

        assert len(analysis.issues) == 1
        assert analysis.issues[0].category == "EMOTION"
        assert analysis.issues[0].severity == "HIGH"
        assert "excited" in analysis.issues[0].text.lower()

    @pytest.mark.asyncio
    async def test_detect_false_empathy(self, intimacy_detector, mock_claude_client):
        """Test detection of false empathy claims"""
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "issues": [
                    {
                        "category": "FALSE_EMPATHY",
                        "text": "I understand how you feel",
                        "explanation": "AI cannot genuinely understand human emotions",
                        "severity": "MEDIUM",
                        "professional_alternative": "I recognize this may be challenging",
                    }
                ],
                "overall_tone": "FAMILIAR",
                "summary": "Contains false empathy",
            }
        )

        response = "I understand how you feel about this issue"
        analysis = await intimacy_detector.detect(response)

        assert len(analysis.issues) == 1
        assert analysis.issues[0].category == "FALSE_EMPATHY"
        assert "understand" in analysis.issues[0].text.lower()

    @pytest.mark.asyncio
    async def test_detect_anthropomorphization(self, intimacy_detector, mock_claude_client):
        """Test detection of human-like claims"""
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "issues": [
                    {
                        "category": "ANTHROPOMORPHIZATION",
                        "text": "I learned from my experiences",
                        "explanation": "AI doesn't learn from experiences in a human sense",
                        "severity": "MEDIUM",
                        "professional_alternative": "My training data includes information about",
                    }
                ],
                "overall_tone": "FAMILIAR",
                "summary": "Contains anthropomorphization",
            }
        )

        response = "I learned from my experiences with similar questions"
        analysis = await intimacy_detector.detect(response)

        assert len(analysis.issues) == 1
        assert analysis.issues[0].category == "ANTHROPOMORPHIZATION"

    @pytest.mark.asyncio
    async def test_detect_familiarity_issues(self, intimacy_detector, mock_claude_client):
        """Test detection of inappropriate familiarity"""
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "issues": [
                    {
                        "category": "FAMILIARITY",
                        "text": "We're in this together",
                        "explanation": "Creates false sense of partnership",
                        "severity": "LOW",
                        "professional_alternative": "I'm here to assist you",
                    }
                ],
                "overall_tone": "FAMILIAR",
                "summary": "Overly familiar tone",
            }
        )

        response = "We're in this together! Let's solve it!"
        analysis = await intimacy_detector.detect(response)

        assert len(analysis.issues) == 1
        assert analysis.issues[0].category == "FAMILIARITY"
        assert analysis.issues[0].severity == "LOW"

    @pytest.mark.asyncio
    async def test_detect_mixed_issues(
        self, intimacy_detector, mock_claude_client, json_intimacy_detection_response
    ):
        """Test detection of multiple issue types"""
        mock_claude_client.analyze.return_value = json_intimacy_detection_response

        response = "I'm excited to help. I understand how you feel."
        analysis = await intimacy_detector.detect(response)

        assert len(analysis.issues) >= 1
        assert analysis.overall_tone == "FAMILIAR"

    @pytest.mark.asyncio
    async def test_detect_severity_levels(self, intimacy_detector, mock_claude_client):
        """Test that severity levels are properly detected"""
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "issues": [
                    {
                        "category": "EMOTION",
                        "text": "I'm thrilled",
                        "explanation": "High severity emotion",
                        "severity": "HIGH",
                        "professional_alternative": "I'm ready",
                    },
                    {
                        "category": "ANTHROPOMORPHIZATION",
                        "text": "I think",
                        "explanation": "Medium severity",
                        "severity": "MEDIUM",
                        "professional_alternative": "Based on analysis",
                    },
                    {
                        "category": "FAMILIARITY",
                        "text": "Let's do this",
                        "explanation": "Low severity",
                        "severity": "LOW",
                        "professional_alternative": "I can assist",
                    },
                ],
                "overall_tone": "INAPPROPRIATE",
                "summary": "Multiple severity levels",
            }
        )

        response = "I'm thrilled! I think we should do this."
        analysis = await intimacy_detector.detect(response)

        severity_dict = analysis.to_dict()
        assert severity_dict["high_severity_count"] == 1
        assert severity_dict["medium_severity_count"] == 1
        assert severity_dict["low_severity_count"] == 1

    @pytest.mark.asyncio
    async def test_detect_json_parse_error(self, intimacy_detector, mock_claude_client):
        """Test handling of malformed JSON"""
        mock_claude_client.analyze.return_value = "Invalid JSON {{"

        response = "Test response"
        analysis = await intimacy_detector.detect(response)

        # Should return empty analysis on error
        assert isinstance(analysis, IntimacyAnalysis)
        assert len(analysis.issues) == 0

    @pytest.mark.asyncio
    async def test_detect_api_error(self, intimacy_detector, mock_claude_client):
        """Test handling of Claude API errors"""
        mock_claude_client.analyze.side_effect = Exception("API Error")

        response = "Test response"
        analysis = await intimacy_detector.detect(response)

        # Should return empty analysis on error
        assert isinstance(analysis, IntimacyAnalysis)
        assert analysis.to_dict()["total_issues"] == 0

    @pytest.mark.asyncio
    async def test_detect_empty_response(self, intimacy_detector, mock_claude_client):
        """Test handling of empty input"""
        mock_claude_client.analyze.return_value = json.dumps(
            {"issues": [], "overall_tone": "PROFESSIONAL", "summary": "No issues"}
        )

        response = ""
        analysis = await intimacy_detector.detect(response)

        assert isinstance(analysis, IntimacyAnalysis)
        assert analysis.to_dict()["total_issues"] == 0


class TestDataStructureConversions:
    """Test data structure serialization"""

    def test_intimacy_issue_to_dict(self):
        """Test IntimacyIssue serialization"""
        issue = IntimacyIssue(
            category="EMOTION",
            text="I'm happy to help",
            explanation="AI cannot feel happiness",
            severity="HIGH",
            professional_alternative="I'm available to assist",
        )

        result = issue.to_dict()
        assert result["category"] == "EMOTION"
        assert result["text"] == "I'm happy to help"
        assert result["explanation"] == "AI cannot feel happiness"
        assert result["severity"] == "HIGH"
        assert result["professional_alternative"] == "I'm available to assist"

    def test_intimacy_analysis_to_dict(self):
        """Test IntimacyAnalysis serialization"""
        analysis = IntimacyAnalysis(
            issues=[
                IntimacyIssue("EMOTION", "text1", "exp1", "HIGH", "alt1"),
                IntimacyIssue("FAMILIARITY", "text2", "exp2", "LOW", "alt2"),
            ],
            overall_tone="FAMILIAR",
            summary="Test summary",
        )

        result = analysis.to_dict()
        assert len(result["issues"]) == 2
        assert result["overall_tone"] == "FAMILIAR"
        assert result["summary"] == "Test summary"
        assert result["total_issues"] == 2
        assert result["high_severity_count"] == 1
        assert result["low_severity_count"] == 1

    def test_intimacy_analysis_severity_counts(self):
        """Test severity counting in IntimacyAnalysis"""
        # Empty analysis
        empty = IntimacyAnalysis([], "PROFESSIONAL", "No issues")
        result = empty.to_dict()
        assert result["high_severity_count"] == 0
        assert result["medium_severity_count"] == 0
        assert result["low_severity_count"] == 0

        # Mixed severities
        mixed = IntimacyAnalysis(
            issues=[
                IntimacyIssue("EMOTION", "t1", "e1", "HIGH", "a1"),
                IntimacyIssue("EMOTION", "t2", "e2", "HIGH", "a2"),
                IntimacyIssue("ANTHROPOMORPHIZATION", "t3", "e3", "MEDIUM", "a3"),
                IntimacyIssue("FAMILIARITY", "t4", "e4", "LOW", "a4"),
            ],
            overall_tone="INAPPROPRIATE",
            summary="Multiple issues",
        )
        result = mixed.to_dict()
        assert result["high_severity_count"] == 2
        assert result["medium_severity_count"] == 1
        assert result["low_severity_count"] == 1
        assert result["total_issues"] == 4


class TestToneAssessment:
    """Test overall tone assessment"""

    def test_overall_tone_professional(self):
        """Test PROFESSIONAL tone classification"""
        analysis = IntimacyAnalysis(
            issues=[], overall_tone="PROFESSIONAL", summary="No issues detected"
        )

        assert analysis.overall_tone == "PROFESSIONAL"
        assert analysis.to_dict()["total_issues"] == 0

    def test_overall_tone_familiar(self):
        """Test FAMILIAR tone classification"""
        analysis = IntimacyAnalysis(
            issues=[IntimacyIssue("FAMILIARITY", "text", "exp", "LOW", "alt")],
            overall_tone="FAMILIAR",
            summary="Some familiarity",
        )

        assert analysis.overall_tone == "FAMILIAR"
        assert analysis.to_dict()["total_issues"] == 1

    def test_overall_tone_inappropriate(self):
        """Test INAPPROPRIATE tone classification"""
        analysis = IntimacyAnalysis(
            issues=[IntimacyIssue("EMOTION", "text", "exp", "HIGH", "alt")],
            overall_tone="INAPPROPRIATE",
            summary="Emotion claims present",
        )

        assert analysis.overall_tone == "INAPPROPRIATE"
        assert analysis.to_dict()["high_severity_count"] == 1
