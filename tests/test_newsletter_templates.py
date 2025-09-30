"""
Unit tests for personalized narrative newsletter templates
"""

import unittest
from datetime import datetime
from src.newsletter.templates import PersonalizedNarrativeTemplate


class TestPersonalizedNarrativeTemplate(unittest.TestCase):
    """Test personalized narrative template rendering"""

    def setUp(self):
        """Create mock synthesis data"""
        self.mock_data = {
            "date": datetime(2025, 9, 30),
            "synthesis_data": {
                "metadata": {
                    "synthesis_id": "test-123-456",
                    "generated_at": "2025-09-30T10:00:00",
                    "articles_analyzed": 15
                },
                "executive_summary": "Today's key developments focus on AI regulation and cybersecurity.\n\nFederal agencies are implementing new frameworks.",
                "temporal_layers": {
                    "immediate": {
                        "narrative": "Breaking developments in federal AI policy require your immediate attention.",
                        "key_implications": [
                            "New compliance requirements for contractors",
                            "Budget implications for FY2026"
                        ],
                        "recommended_actions": ["Review policy document", "Contact compliance team"]
                    },
                    "near_term": {
                        "narrative": "Upcoming cybersecurity audits will affect your projects.",
                        "key_implications": ["Audit preparation needed"],
                        "recommended_actions": []
                    }
                },
                "cross_domain_insights": [
                    {
                        "theme": "AI Policy + Federal Contracting",
                        "narrative": "New AI regulations directly impact federal IT contracts.",
                        "personal_impact": "Your current projects may need compliance updates.",
                        "confidence": 0.85
                    }
                ],
                "priority_actions": [
                    {
                        "action": "Review new AI compliance framework",
                        "urgency": "immediate",
                        "reasoning": "Affects current contracts"
                    },
                    {
                        "action": "Schedule security audit prep meeting",
                        "urgency": "near",
                        "reasoning": "Audits begin in 2 weeks"
                    }
                ]
            },
            "user_context": {
                "location": {"city": "Arlington", "state": "Virginia"},
                "professional_domains": ["software engineering", "cybersecurity"]
            }
        }

    def test_generate_html_includes_key_sections(self):
        """Test that HTML generation includes all key sections"""
        html = PersonalizedNarrativeTemplate.generate_html(self.mock_data)

        # Check for key sections
        self.assertIn("Your Intelligence Brief", html)
        self.assertIn("What You Need to Know", html)
        self.assertIn("Immediate Focus", html)
        self.assertIn("What You Should Do", html)

    def test_html_includes_user_context(self):
        """Test that user location is included"""
        html = PersonalizedNarrativeTemplate.generate_html(self.mock_data)

        self.assertIn("Arlington", html)
        self.assertIn("Virginia", html)

    def test_html_renders_temporal_layers(self):
        """Test that temporal layers are rendered"""
        html = PersonalizedNarrativeTemplate.generate_html(self.mock_data)

        self.assertIn("Immediate Focus", html)
        self.assertIn("0-48 hours", html)
        self.assertIn("Breaking developments in federal AI policy", html)
        self.assertIn("Why This Matters to You", html)

    def test_html_renders_cross_domain_insights(self):
        """Test that cross-domain insights are rendered"""
        html = PersonalizedNarrativeTemplate.generate_html(self.mock_data)

        self.assertIn("AI Policy + Federal Contracting", html)
        self.assertIn("New AI regulations directly impact", html)
        self.assertIn("For you:", html)

    def test_html_renders_priority_actions(self):
        """Test that priority actions are rendered"""
        html = PersonalizedNarrativeTemplate.generate_html(self.mock_data)

        self.assertIn("Review new AI compliance framework", html)
        self.assertIn("immediate", html)
        self.assertIn("Affects current contracts", html)

    def test_generate_text_format(self):
        """Test plain text generation"""
        text = PersonalizedNarrativeTemplate.generate_text(self.mock_data)

        # Check structure
        self.assertIn("YOUR INTELLIGENCE BRIEF", text)
        self.assertIn("WHAT YOU NEED TO KNOW", text)
        self.assertIn("⚠️ IMMEDIATE FOCUS", text)
        self.assertIn("✓ WHAT YOU SHOULD DO", text)

    def test_text_includes_executive_summary(self):
        """Test that text includes executive summary"""
        text = PersonalizedNarrativeTemplate.generate_text(self.mock_data)

        self.assertIn("Today's key developments", text)
        self.assertIn("AI regulation", text)

    def test_empty_synthesis_graceful_handling(self):
        """Test handling of empty synthesis data"""
        empty_data = {
            "date": datetime.now(),
            "synthesis_data": {},
            "user_context": {"location": {}}
        }

        html = PersonalizedNarrativeTemplate.generate_html(empty_data)
        self.assertIn("Your Intelligence Brief", html)
        self.assertIn("No narrative synthesis available", html)

    def test_missing_temporal_layers_handled(self):
        """Test that missing temporal layers don't break rendering"""
        data = self.mock_data.copy()
        data["synthesis_data"]["temporal_layers"] = {}

        html = PersonalizedNarrativeTemplate.generate_html(data)
        self.assertIn("Your Intelligence Brief", html)


if __name__ == '__main__':
    unittest.main()