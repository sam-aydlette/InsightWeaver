"""
Tests for Newsletter Templates
"""

from datetime import datetime

from src.newsletter.templates import (
    DailyBriefTemplate,
    NewsletterTemplate,
    PersonalizedNarrativeTemplate,
)


class TestNewsletterTemplateBase:
    """Tests for base NewsletterTemplate class"""

    def test_format_date(self):
        """Should format date correctly"""
        date = datetime(2024, 1, 15, 10, 30, 0)

        result = NewsletterTemplate.format_date(date)

        assert result == "January 15, 2024"

    def test_format_time_range_same_day(self):
        """Should format same-day range"""
        start = datetime(2024, 1, 15, 8, 0, 0)
        end = datetime(2024, 1, 15, 18, 0, 0)

        result = NewsletterTemplate.format_time_range(start, end)

        assert result == "January 15, 2024"

    def test_format_time_range_different_days(self):
        """Should format multi-day range"""
        start = datetime(2024, 1, 10, 8, 0, 0)
        end = datetime(2024, 1, 15, 18, 0, 0)

        result = NewsletterTemplate.format_time_range(start, end)

        assert "January 10" in result
        assert "January 15, 2024" in result


class TestConvertCitationsToLinks:
    """Tests for citation conversion"""

    def test_convert_single_citation(self):
        """Should convert single citation to link"""
        text = "Test text^[1] with citation"
        citation_map = {"1": {"title": "Test", "source": "Source", "url": "https://example.com"}}

        result = PersonalizedNarrativeTemplate._convert_citations_to_links(text, citation_map)

        assert '<a href="#citation-1"' in result
        assert "[1]" in result
        assert "^[1]" not in result

    def test_convert_multiple_citations(self):
        """Should convert multiple citations"""
        text = "Test^[1,2,3] with multiple"
        citation_map = {
            "1": {"title": "Test 1", "source": "Source", "url": "https://example.com/1"},
            "2": {"title": "Test 2", "source": "Source", "url": "https://example.com/2"},
            "3": {"title": "Test 3", "source": "Source", "url": "https://example.com/3"},
        }

        result = PersonalizedNarrativeTemplate._convert_citations_to_links(text, citation_map)

        assert "#citation-1" in result
        assert "#citation-2" in result
        assert "#citation-3" in result

    def test_preserve_unknown_citations(self):
        """Should preserve citations not in map"""
        text = "Test^[99] unknown citation"
        citation_map = {"1": {"title": "Test", "source": "Source", "url": "https://example.com"}}

        result = PersonalizedNarrativeTemplate._convert_citations_to_links(text, citation_map)

        assert "[99]" in result

    def test_handle_empty_text(self):
        """Should handle empty text"""
        result = PersonalizedNarrativeTemplate._convert_citations_to_links("", {"1": {}})

        assert result == ""

    def test_handle_empty_citation_map(self):
        """Should handle empty citation map"""
        text = "Test text^[1]"

        result = PersonalizedNarrativeTemplate._convert_citations_to_links(text, {})

        assert result == text


class TestRenderSourcesSection:
    """Tests for sources section rendering"""

    def test_render_sources_section(self):
        """Should render sources section with links"""
        citation_map = {
            "1": {
                "title": "Test Article 1",
                "source": "Test Source",
                "url": "https://example.com/1",
            },
            "2": {
                "title": "Test Article 2",
                "source": "Other Source",
                "url": "https://example.com/2",
            },
        }

        result = PersonalizedNarrativeTemplate._render_sources_section(citation_map)

        assert "Sources" in result
        assert "Test Article 1" in result
        assert "Test Article 2" in result
        assert 'id="citation-1"' in result
        assert 'id="citation-2"' in result

    def test_render_sources_sorted(self):
        """Should sort sources by citation number"""
        citation_map = {
            "3": {"title": "Third", "source": "Source", "url": ""},
            "1": {"title": "First", "source": "Source", "url": ""},
            "2": {"title": "Second", "source": "Source", "url": ""},
        }

        result = PersonalizedNarrativeTemplate._render_sources_section(citation_map)

        # Check order by finding positions
        first_pos = result.find("First")
        second_pos = result.find("Second")
        third_pos = result.find("Third")

        assert first_pos < second_pos < third_pos

    def test_render_empty_sources(self):
        """Should return empty string for no sources"""
        result = PersonalizedNarrativeTemplate._render_sources_section({})

        assert result == ""

    def test_render_source_without_url(self):
        """Should handle sources without URL"""
        citation_map = {"1": {"title": "Test", "source": "Source", "url": ""}}

        result = PersonalizedNarrativeTemplate._render_sources_section(citation_map)

        assert "Test" in result
        assert "Source" in result


class TestGenerateHtml:
    """Tests for HTML generation"""

    def test_generate_html_daily_report(self, sample_content_data):
        """Should generate HTML for daily report"""
        html = PersonalizedNarrativeTemplate.generate_html(sample_content_data)

        assert "<!DOCTYPE html>" in html
        assert "Daily Intelligence Brief" in html
        assert "Fairfax" in html

    def test_generate_html_weekly_report(self, sample_weekly_content_data):
        """Should generate HTML for weekly report"""
        html = PersonalizedNarrativeTemplate.generate_html(sample_weekly_content_data)

        assert "<!DOCTYPE html>" in html
        assert "Weekly Intelligence Analysis" in html

    def test_generate_html_custom_duration(self):
        """Should generate title for custom duration"""
        data = {
            "start_date": datetime.now(),
            "end_date": datetime.now(),
            "duration_hours": 12,
            "report_type": "custom",
            "synthesis_data": {"metadata": {}},
            "user_context": {"location": "Test"},
        }

        html = PersonalizedNarrativeTemplate.generate_html(data)

        assert "Intelligence Report" in html

    def test_generate_html_includes_bottom_line(self, sample_content_data):
        """Should include bottom line section"""
        html = PersonalizedNarrativeTemplate.generate_html(sample_content_data)

        assert "BOTTOM LINE" in html
        assert "Test summary" in html

    def test_generate_html_includes_sources(self, sample_content_data):
        """Should include sources section"""
        html = PersonalizedNarrativeTemplate.generate_html(sample_content_data)

        assert "Sources" in html
        assert "Test Article 1" in html

    def test_generate_html_string_bottom_line(self):
        """Should handle bottom_line as string"""
        data = {
            "start_date": datetime.now(),
            "end_date": datetime.now(),
            "duration_hours": 24,
            "report_type": "daily",
            "synthesis_data": {
                "bottom_line": "Simple string summary",
                "metadata": {},
            },
            "user_context": {"location": "Test"},
        }

        html = PersonalizedNarrativeTemplate.generate_html(data)

        assert "Simple string summary" in html

    def test_generate_html_string_location(self):
        """Should handle string location format"""
        data = {
            "start_date": datetime.now(),
            "end_date": datetime.now(),
            "duration_hours": 24,
            "report_type": "daily",
            "synthesis_data": {"metadata": {}},
            "user_context": {"location": "Fairfax, VA"},
        }

        html = PersonalizedNarrativeTemplate.generate_html(data)

        assert "Fairfax, VA" in html


class TestRenderBottomLine:
    """Tests for bottom line rendering"""

    def test_render_bottom_line(self):
        """Should render bottom line section"""
        bottom_line = {
            "summary": "Test summary^[1]",
            "immediate_actions": ["Action 1^[1]", "Action 2^[2]"],
        }
        citation_map = {"1": {"title": "Test"}, "2": {"title": "Test 2"}}

        html = PersonalizedNarrativeTemplate._render_bottom_line(bottom_line, citation_map)

        assert "BOTTOM LINE" in html
        assert "Test summary" in html
        assert "Action 1" in html
        assert "Action 2" in html

    def test_render_empty_bottom_line(self):
        """Should handle empty bottom line"""
        html = PersonalizedNarrativeTemplate._render_bottom_line({}, {})

        assert html == ""

    def test_render_bottom_line_no_actions(self):
        """Should handle bottom line without actions"""
        bottom_line = {"summary": "Test summary"}

        html = PersonalizedNarrativeTemplate._render_bottom_line(bottom_line, {})

        assert "Test summary" in html
        assert "Immediate Actions" not in html


class TestRenderTrendsAndPatterns:
    """Tests for trends rendering"""

    def test_render_trends(self):
        """Should render trends section"""
        trends = {
            "local": [
                {
                    "subject": "Local trend",
                    "direction": "increasing",
                    "quantifier": "10%",
                    "description": "Description",
                }
            ],
            "national": [],
        }

        html = PersonalizedNarrativeTemplate._render_trends_and_patterns(trends, "Tech", {})

        assert "TRENDS" in html
        assert "Local" in html
        assert "Local trend" in html
        assert "increasing" in html

    def test_render_empty_trends(self):
        """Should handle empty trends"""
        html = PersonalizedNarrativeTemplate._render_trends_and_patterns({}, "Tech", {})

        assert html == ""


class TestRenderPriorityEvents:
    """Tests for priority events rendering"""

    def test_render_priority_events(self):
        """Should render events table"""
        events = [
            {
                "event": "Test event",
                "when": "Next week",
                "impact_level": "HIGH",
                "why_matters": "Important",
                "recommended_action": "Take action",
            }
        ]

        html = PersonalizedNarrativeTemplate._render_priority_events(events, {})

        assert "PRIORITY EVENTS" in html
        assert "Test event" in html
        assert "HIGH" in html

    def test_render_string_event(self):
        """Should handle string events (malformed Claude response)"""
        events = ["Simple string event"]

        html = PersonalizedNarrativeTemplate._render_priority_events(events, {})

        assert "Simple string event" in html
        assert "MEDIUM" in html  # Default impact level

    def test_render_empty_events(self):
        """Should handle empty events"""
        html = PersonalizedNarrativeTemplate._render_priority_events([], {})

        assert html == ""


class TestRenderPredictions:
    """Tests for predictions rendering"""

    def test_render_predictions(self):
        """Should render predictions section"""
        predictions = {
            "local_governance": [
                {
                    "prediction": "Budget will increase",
                    "confidence": 0.8,
                    "timeframe": "2-4 weeks",
                    "rationale": "Based on trends",
                }
            ],
        }

        html = PersonalizedNarrativeTemplate._render_predictions(predictions, "Tech", {})

        assert "PREDICTIONS" in html
        assert "Budget will increase" in html
        assert "80%" in html

    def test_render_predictions_confidence_levels(self):
        """Should apply correct confidence styling"""
        predictions = {
            "local_governance": [
                {"prediction": "High conf", "confidence": 0.8, "timeframe": "1 week"},
                {"prediction": "Med conf", "confidence": 0.5, "timeframe": "2 weeks"},
                {"prediction": "Low conf", "confidence": 0.3, "timeframe": "3 weeks"},
            ],
        }

        html = PersonalizedNarrativeTemplate._render_predictions(predictions, "Tech", {})

        assert "confidence-high" in html
        assert "confidence-medium" in html
        assert "confidence-low" in html

    def test_render_empty_predictions(self):
        """Should handle empty predictions"""
        html = PersonalizedNarrativeTemplate._render_predictions({}, "Tech", {})

        assert html == ""


class TestRenderCivicEngagement:
    """Tests for civic engagement rendering"""

    def test_render_civic_events(self):
        """Should render civic events section"""
        events = [
            {
                "event": "City council meeting",
                "when": "Next Tuesday",
                "impact_level": "HIGH",
                "why_matters": "Budget decisions",
                "recommended_action": "Attend meeting",
            }
        ]

        html = PersonalizedNarrativeTemplate._render_civic_engagement(events, {})

        assert "CIVIC ENGAGEMENT" in html
        assert "City council meeting" in html
        assert "Attend meeting" in html

    def test_filter_non_civic_events(self):
        """Should filter out non-civic events"""
        events = [
            {"event": "Tech conference", "when": "Next week", "impact_level": "LOW"},
        ]

        html = PersonalizedNarrativeTemplate._render_civic_engagement(events, {})

        assert html == ""

    def test_render_civic_string_event(self):
        """Should handle string civic events"""
        events = ["School board meeting announcement"]

        html = PersonalizedNarrativeTemplate._render_civic_engagement(events, {})

        assert "School board meeting" in html


class TestDailyBriefTemplateAlias:
    """Tests for DailyBriefTemplate alias"""

    def test_alias_points_to_personalized_template(self):
        """Should be alias for PersonalizedNarrativeTemplate"""
        assert DailyBriefTemplate is PersonalizedNarrativeTemplate
