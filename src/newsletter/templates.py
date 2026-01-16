"""
Personalized Narrative Newsletter Templates for InsightWeaver
Story-driven, temporal-layered intelligence briefings
"""

import re
from datetime import datetime
from typing import Any


class NewsletterTemplate:
    """Base newsletter template class"""

    @staticmethod
    def format_date(date_obj: datetime) -> str:
        """Format date for newsletter headers"""
        return date_obj.strftime("%B %d, %Y")

    @staticmethod
    def format_time_range(start_date: datetime, end_date: datetime) -> str:
        """Format time range for analysis periods"""
        if start_date.date() == end_date.date():
            return start_date.strftime("%B %d, %Y")
        return f"{start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}"


class PersonalizedNarrativeTemplate(NewsletterTemplate):
    """Personalized narrative-driven intelligence brief template"""

    @staticmethod
    def _convert_citations_to_links(text: str, citation_map: dict[str, Any]) -> str:
        """
        Convert citation markers like ^[1,3] to clickable HTML links.

        Args:
            text: Text containing citation markers
            citation_map: Map of citation numbers to article details

        Returns:
            Text with citations converted to HTML anchor links
        """
        if not text or not citation_map:
            return text

        def replace_citation(match: re.Match) -> str:
            # Extract citation numbers from match (e.g., "1,3" from "^[1,3]")
            citation_nums = match.group(1).split(",")
            links = []
            for num in citation_nums:
                num = num.strip()
                if num in citation_map:
                    # Link to the sources section at the bottom of the page
                    links.append(f'<a href="#citation-{num}" class="citation-link">[{num}]</a>')
                else:
                    links.append(f"[{num}]")
            return '<sup class="citations">' + "".join(links) + "</sup>"

        # Match ^[N] or ^[N,M,O] patterns
        pattern = r"\^\[([0-9,\s]+)\]"
        return re.sub(pattern, replace_citation, text)

    @staticmethod
    def _render_sources_section(citation_map: dict[str, Any]) -> str:
        """
        Render the Sources/References section at the bottom of the report.

        Args:
            citation_map: Map of citation numbers to article details

        Returns:
            HTML for the sources section
        """
        if not citation_map:
            return ""

        html = """
        <div class="section sources-section">
            <h2>Sources</h2>
            <ol class="sources-list">
        """

        # Sort citations by number
        sorted_nums = sorted(citation_map.keys(), key=lambda x: int(x))

        for num in sorted_nums:
            citation = citation_map[num]
            title = citation.get("title", "Unknown Title")
            source = citation.get("source", "Unknown Source")
            url = citation.get("url", "")

            if url:
                html += f"""
                <li id="citation-{num}" class="source-item">
                    <a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>
                    <span class="source-name">- {source}</span>
                </li>
                """
            else:
                html += f"""
                <li id="citation-{num}" class="source-item">
                    {title}
                    <span class="source-name">- {source}</span>
                </li>
                """

        html += """
            </ol>
        </div>
        """
        return html

    @staticmethod
    def generate_html(data: dict[str, Any]) -> str:
        """
        Generate HTML version of intelligence brief

        Args:
            data: Must contain 'synthesis_data' from NarrativeSynthesizer
        """
        synthesis = data.get("synthesis_data", {})
        metadata = synthesis.get("metadata", {})
        bottom_line_raw = synthesis.get("bottom_line", {})
        # Handle bottom_line being either a string or dict
        if isinstance(bottom_line_raw, str):
            bottom_line = {"summary": bottom_line_raw, "immediate_actions": []}
        else:
            bottom_line = bottom_line_raw if bottom_line_raw else {}
        trends = synthesis.get("trends_and_patterns", {})
        events = synthesis.get("priority_events", [])
        predictions = synthesis.get("predictions_scenarios", {})

        # Extract citation_map for source linking
        citation_map = metadata.get("citation_map", {})

        # Get user context for personalization
        user_context = data.get("user_context", {})
        location = user_context.get("location", {})
        # Handle location being either a string or dict
        if isinstance(location, str):
            location_str = location if location else "Your Area"
        else:
            location_str = f"{location.get('city', 'Your Area')}, {location.get('state', 'State')}"
        niche_field = (
            user_context.get("professional_domains", ["Technology"])[0]
            if user_context.get("professional_domains")
            else "Professional Domain"
        )

        # Determine report title and date range based on report type
        report_type = data.get("report_type", "daily")
        duration_hours = data.get("duration_hours", 24)

        if report_type == "daily":
            title = "Daily Intelligence Brief"
        elif report_type == "weekly":
            title = "Weekly Intelligence Analysis"
        elif report_type == "update":
            title = "Intelligence Update"
        else:
            # Custom duration
            if duration_hours < 24:
                title = f"Intelligence Report ({int(duration_hours)}h)"
            else:
                days = int(duration_hours / 24)
                title = f"Intelligence Report ({days}d)"

        # Format date range
        if "start_date" in data and "end_date" in data:
            date_range = (
                f"{data['start_date'].strftime('%b %d')} - {data['end_date'].strftime('%b %d, %Y')}"
            )
        else:
            date_range = data.get("date", datetime.now()).strftime("%B %d, %Y")

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title} - {date_range}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.7;
            color: #1a202c;
            max-width: 700px;
            margin: 0 auto;
            padding: 20px;
            background: #f7fafc;
        }}
        .container {{ background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header {{
            border-bottom: 3px solid #3182ce;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0 0 8px 0;
            font-size: 32px;
            color: #2d3748;
            font-weight: 700;
        }}
        .header .meta {{
            color: #718096;
            font-size: 14px;
        }}
        .bottom-line {{
            background: #fef5e7;
            border: 2px solid #f39c12;
            padding: 24px;
            margin-bottom: 36px;
            border-radius: 6px;
        }}
        .bottom-line h2 {{
            margin: 0 0 16px 0;
            color: #d68910;
            font-size: 22px;
            font-weight: 700;
        }}
        .bottom-line .summary {{
            font-size: 17px;
            line-height: 1.8;
            margin: 12px 0;
            color: #2d3748;
            font-weight: 500;
        }}
        .bottom-line .actions {{
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid #f39c12;
        }}
        .bottom-line .actions h3 {{
            margin: 0 0 8px 0;
            font-size: 15px;
            color: #d68910;
            text-transform: uppercase;
            font-weight: 600;
        }}
        .bottom-line .actions ul {{
            margin: 0;
            padding-left: 20px;
        }}
        .bottom-line .actions li {{
            margin: 6px 0;
            color: #2d3748;
            font-weight: 500;
        }}
        .temporal-section {{
            margin-bottom: 36px;
            border-left: 3px solid #e2e8f0;
            padding-left: 20px;
        }}
        .temporal-section.immediate {{ border-left-color: #fc8181; }}
        .temporal-section.near {{ border-left-color: #f6ad55; }}
        .temporal-section.medium {{ border-left-color: #68d391; }}
        .temporal-section.long {{ border-left-color: #63b3ed; }}
        .temporal-section h3 {{
            margin: 0 0 12px 0;
            color: #2d3748;
            font-size: 22px;
            font-weight: 600;
        }}
        .temporal-section .timeline {{
            display: inline-block;
            background: #edf2f7;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 12px;
            color: #4a5568;
            margin-left: 8px;
            font-weight: 500;
        }}
        .narrative {{
            font-size: 16px;
            line-height: 1.8;
            margin: 16px 0;
            color: #2d3748;
        }}
        .implications {{
            background: #f7fafc;
            padding: 16px;
            border-radius: 4px;
            margin: 16px 0;
        }}
        .implications h4 {{
            margin: 0 0 8px 0;
            color: #4a5568;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 600;
        }}
        .implications ul {{
            margin: 0;
            padding-left: 20px;
        }}
        .implications li {{
            margin: 6px 0;
            color: #2d3748;
        }}
        .articles-list {{
            margin: 20px 0;
        }}
        .article-card {{
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 16px;
            margin: 12px 0;
            transition: box-shadow 0.2s;
        }}
        .article-card:hover {{
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .article-title {{
            font-size: 16px;
            font-weight: 600;
            color: #2d3748;
            margin: 0 0 8px 0;
        }}
        .article-title a {{
            color: #2d3748;
            text-decoration: none;
        }}
        .article-title a:hover {{
            color: #3182ce;
        }}
        .article-meta {{
            font-size: 13px;
            color: #718096;
            margin-bottom: 8px;
        }}
        .article-excerpt {{
            font-size: 14px;
            color: #4a5568;
            line-height: 1.6;
        }}
        .read-more {{
            display: inline-block;
            margin-top: 8px;
            font-size: 13px;
            color: #3182ce;
            text-decoration: none;
            font-weight: 500;
        }}
        .read-more:hover {{
            text-decoration: underline;
        }}
        .cross-domain {{
            background: #fffaf0;
            border: 1px solid #fbd38d;
            border-radius: 6px;
            padding: 20px;
            margin: 24px 0;
        }}
        .cross-domain h4 {{
            margin: 0 0 12px 0;
            color: #744210;
            font-size: 18px;
        }}
        .cross-domain .narrative {{
            font-size: 15px;
            color: #2d3748;
        }}
        .cross-domain .personal-impact {{
            background: white;
            padding: 12px;
            border-radius: 4px;
            margin-top: 12px;
            font-style: italic;
            color: #744210;
        }}
        .actions-section {{
            background: #f0fff4;
            border: 2px solid #9ae6b4;
            border-radius: 6px;
            padding: 24px;
            margin: 36px 0;
        }}
        .actions-section h3 {{
            margin: 0 0 16px 0;
            color: #22543d;
            font-size: 22px;
        }}
        .action-item {{
            background: white;
            padding: 16px;
            margin: 12px 0;
            border-radius: 4px;
            border-left: 4px solid #48bb78;
        }}
        .action-item.immediate {{ border-left-color: #fc8181; }}
        .action-item.near {{ border-left-color: #f6ad55; }}
        .action-item.medium {{ border-left-color: #68d391; }}
        .action-item.long {{ border-left-color: #63b3ed; }}
        .action-item .urgency {{
            display: inline-block;
            background: #48bb78;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            text-transform: uppercase;
            font-weight: 600;
            margin-right: 8px;
        }}
        .action-item .action-text {{
            font-weight: 600;
            color: #2d3748;
            font-size: 15px;
        }}
        .action-item .reasoning {{
            color: #4a5568;
            font-size: 14px;
            margin-top: 6px;
        }}
        .section {{
            margin-bottom: 48px;
        }}
        .section h2 {{
            margin: 0 0 24px 0;
            color: #2d3748;
            font-size: 24px;
            font-weight: 700;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 12px;
        }}
        .trend-scope {{
            margin-bottom: 24px;
        }}
        .trend-scope h3 {{
            margin: 0 0 12px 0;
            color: #4a5568;
            font-size: 18px;
            font-weight: 600;
        }}
        .trend-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .trend-item {{
            padding: 12px;
            margin: 8px 0;
            background: #f7fafc;
            border-left: 3px solid #3182ce;
            border-radius: 4px;
        }}
        .trend-text {{
            font-weight: 600;
            color: #2d3748;
            font-size: 15px;
        }}
        .confidence {{
            display: inline-block;
            background: #e6fffa;
            color: #234e52;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 12px;
            margin-left: 12px;
            font-weight: 600;
        }}
        .trend-desc {{
            margin-top: 6px;
            color: #4a5568;
            font-size: 14px;
        }}
        .events-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 16px;
        }}
        .events-table th {{
            background: #2d3748;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            font-size: 13px;
        }}
        .events-table td {{
            padding: 12px;
            border-bottom: 1px solid #e2e8f0;
            font-size: 14px;
        }}
        .event-row.impact-critical {{
            background: #fff5f5;
        }}
        .event-row.impact-high {{
            background: #fffaf0;
        }}
        .event-row.impact-medium {{
            background: #f0fff4;
        }}
        .event-row.impact-low {{
            background: #f7fafc;
        }}
        .impact-badge {{
            font-weight: 700;
            font-size: 12px;
        }}
        .impact-critical .impact-badge {{
            color: #c53030;
        }}
        .impact-high .impact-badge {{
            color: #dd6b20;
        }}
        .impact-medium .impact-badge {{
            color: #38a169;
        }}
        .impact-low .impact-badge {{
            color: #718096;
        }}
        .civic-section {{
            background: #ebf8ff;
            border: 2px solid #4299e1;
            border-radius: 8px;
            padding: 24px;
            margin: 36px 0;
        }}
        .civic-section h2 {{
            margin: 0 0 16px 0;
            color: #2c5282;
            font-size: 24px;
            font-weight: 700;
        }}
        .civic-event {{
            background: white;
            border-left: 4px solid #4299e1;
            padding: 16px;
            margin: 12px 0;
            border-radius: 4px;
        }}
        .civic-event-title {{
            font-weight: 600;
            color: #2d3748;
            font-size: 16px;
            margin-bottom: 8px;
        }}
        .civic-event-date {{
            color: #2c5282;
            font-weight: 600;
            font-size: 14px;
            margin-bottom: 8px;
        }}
        .civic-event-details {{
            color: #4a5568;
            font-size: 14px;
            line-height: 1.6;
        }}
        .civic-action {{
            background: #f0fff4;
            padding: 12px;
            margin-top: 8px;
            border-radius: 4px;
            border-left: 3px solid #38a169;
        }}
        .civic-action-label {{
            font-weight: 600;
            color: #22543d;
            font-size: 13px;
            text-transform: uppercase;
            margin-bottom: 4px;
        }}
        .civic-action-text {{
            color: #2d3748;
            font-size: 14px;
        }}
        .prediction-category {{
            margin-bottom: 24px;
        }}
        .prediction-category h3 {{
            margin: 0 0 12px 0;
            color: #4a5568;
            font-size: 18px;
            font-weight: 600;
        }}
        .prediction-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .prediction-item {{
            padding: 16px;
            margin: 12px 0;
            background: #f7fafc;
            border-radius: 6px;
            border-left: 4px solid #cbd5e0;
        }}
        .prediction-item.confidence-high {{
            border-left-color: #38a169;
            background: #f0fff4;
        }}
        .prediction-item.confidence-medium {{
            border-left-color: #ed8936;
            background: #fffaf0;
        }}
        .prediction-item.confidence-low {{
            border-left-color: #cbd5e0;
            background: #f7fafc;
        }}
        .prediction-text {{
            font-weight: 600;
            color: #2d3748;
            font-size: 15px;
            margin-bottom: 8px;
        }}
        .prediction-meta {{
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            margin-top: 8px;
        }}
        .prediction-meta span {{
            display: inline-block;
            background: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }}
        .confidence {{
            color: #2d3748;
        }}
        .timeframe {{
            color: #718096;
        }}
        .rationale {{
            margin-top: 8px;
            color: #4a5568;
            font-size: 13px;
            font-style: italic;
        }}
        .citations {{
            font-size: 10px;
            vertical-align: super;
            line-height: 0;
        }}
        .citation-link {{
            color: #3182ce;
            text-decoration: none;
            font-weight: 600;
            padding: 0 1px;
        }}
        .citation-link:hover {{
            text-decoration: underline;
            color: #2c5282;
        }}
        .sources-section {{
            background: #f7fafc;
            border-radius: 6px;
            padding: 24px;
            margin-top: 36px;
        }}
        .sources-section h2 {{
            margin: 0 0 16px 0;
            color: #2d3748;
            font-size: 20px;
            font-weight: 700;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 8px;
        }}
        .sources-list {{
            margin: 0;
            padding-left: 24px;
        }}
        .source-item {{
            margin: 8px 0;
            font-size: 13px;
            line-height: 1.5;
            color: #2d3748;
        }}
        .source-item a {{
            color: #3182ce;
            text-decoration: none;
        }}
        .source-item a:hover {{
            text-decoration: underline;
        }}
        .source-name {{
            color: #718096;
            font-style: italic;
        }}
        .footer {{
            text-align: center;
            color: #a0aec0;
            font-size: 12px;
            margin-top: 48px;
            padding-top: 24px;
            border-top: 1px solid #e2e8f0;
        }}
        .footer a {{ color: #3182ce; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <div class="meta">
                {date_range} |
                Personalized for {location_str} |
                {data.get("articles_analyzed", metadata.get("articles_analyzed", 0))} sources analyzed
            </div>
        </div>

        {PersonalizedNarrativeTemplate._render_bottom_line(bottom_line, citation_map)}

        {PersonalizedNarrativeTemplate._render_civic_engagement(events, citation_map)}

        {PersonalizedNarrativeTemplate._render_trends_and_patterns(trends, niche_field, citation_map)}

        {PersonalizedNarrativeTemplate._render_priority_events(events, citation_map)}

        {PersonalizedNarrativeTemplate._render_predictions(predictions, niche_field, citation_map)}

        {PersonalizedNarrativeTemplate._render_sources_section(citation_map)}

        <div class="footer">
            Generated by <a href="#">InsightWeaver</a> |
            Synthesis ID: {metadata.get("synthesis_id", "N/A")[:8]}... |
            {metadata.get("generated_at", "Unknown time")}
        </div>
    </div>
</body>
</html>
        """
        return html.strip()

    @staticmethod
    def _render_bottom_line(bottom_line: dict[str, Any], citation_map: dict[str, Any]) -> str:
        """Render bottom line section"""
        if not bottom_line:
            return ""

        summary = bottom_line.get("summary", "No summary available")
        actions = bottom_line.get("immediate_actions", [])

        # Convert citations to links
        convert = PersonalizedNarrativeTemplate._convert_citations_to_links
        summary = convert(summary, citation_map)

        html = f"""
        <div class="bottom-line">
            <h2>BOTTOM LINE</h2>
            <div class="summary">{summary}</div>
        """

        if actions:
            html += """
            <div class="actions">
                <h3>Immediate Actions</h3>
                <ul>
            """
            for action in actions:
                action = convert(action, citation_map)
                html += f"<li>{action}</li>\n"
            html += """
                </ul>
            </div>
            """

        html += "</div>\n"
        return html

    @staticmethod
    def _render_trends_and_patterns(
        trends: dict[str, list[dict[str, Any]]], niche_field: str, citation_map: dict[str, Any]
    ) -> str:
        """Render trends organized by geographic scope"""
        if not trends:
            return ""

        convert = PersonalizedNarrativeTemplate._convert_citations_to_links

        html = """
        <div class="section">
            <h2>TRENDS & PATTERNS</h2>
        """

        # Geographic scopes with labels
        scopes = [
            ("local", "Local"),
            ("state_regional", "State/Regional"),
            ("national", "National"),
            ("global", "Global"),
            ("niche_field", f"{niche_field}"),
        ]

        for scope_key, scope_label in scopes:
            scope_trends = trends.get(scope_key, [])
            if not scope_trends:
                continue

            html += f"""
            <div class="trend-scope">
                <h3>{scope_label}</h3>
                <ul class="trend-list">
            """

            for trend in scope_trends:
                subject = convert(trend.get("subject", ""), citation_map)
                direction = trend.get("direction", "stable")
                quantifier = convert(trend.get("quantifier", ""), citation_map)
                description = convert(trend.get("description", ""), citation_map)

                # Format trend
                trend_text = f"{subject} {direction}"
                if quantifier:
                    trend_text += f" ({quantifier})"

                html += f"""
                <li class="trend-item">
                    <span class="trend-text">{trend_text}</span>
                    {f'<div class="trend-desc">{description}</div>' if description else ""}
                </li>
                """

            html += """
                </ul>
            </div>
            """

        html += "</div>\n"
        return html

    @staticmethod
    def _render_priority_events(events: list[dict[str, Any]], citation_map: dict[str, Any]) -> str:
        """Render priority events table"""
        if not events:
            return ""

        convert = PersonalizedNarrativeTemplate._convert_citations_to_links

        html = """
        <div class="section">
            <h2>PRIORITY EVENTS (Next 2-4 Weeks)</h2>
            <table class="events-table">
                <thead>
                    <tr>
                        <th>Impact</th>
                        <th>Event</th>
                        <th>When</th>
                        <th>Why It Matters</th>
                        <th>Recommended Action</th>
                    </tr>
                </thead>
                <tbody>
        """

        for event in events:
            # Handle both dict and string formats (Claude sometimes returns strings)
            if isinstance(event, dict):
                impact = event.get("impact_level", "MEDIUM")
                event_name = convert(event.get("event", ""), citation_map)
                when = convert(event.get("when", ""), citation_map)
                why_matters = convert(event.get("why_matters", ""), citation_map)
                action = convert(event.get("recommended_action", ""), citation_map)
            else:
                impact = "MEDIUM"
                event_name = convert(str(event), citation_map)
                when = ""
                why_matters = ""
                action = ""

            html += f"""
                <tr class="event-row impact-{impact.lower()}">
                    <td class="impact-badge">{impact}</td>
                    <td>{event_name}</td>
                    <td>{when}</td>
                    <td>{why_matters}</td>
                    <td>{action}</td>
                </tr>
            """

        html += """
                </tbody>
            </table>
        </div>
        """
        return html

    @staticmethod
    def _render_predictions(
        predictions: dict[str, list[dict[str, Any]]], niche_field: str, citation_map: dict[str, Any]
    ) -> str:
        """Render predictions with confidence indicators"""
        if not predictions:
            return ""

        convert = PersonalizedNarrativeTemplate._convert_citations_to_links

        html = """
        <div class="section">
            <h2>PREDICTIONS & SCENARIOS (2-4 Week Horizon)</h2>
        """

        categories = [
            ("local_governance", "Local Governance/Services"),
            ("education", "Education/Schools"),
            ("niche_field", f"{niche_field}"),
            ("economic_conditions", "Economic Conditions"),
            ("infrastructure", "Infrastructure/Transportation"),
        ]

        for cat_key, cat_label in categories:
            cat_predictions = predictions.get(cat_key, [])
            if not cat_predictions:
                continue

            html += f"""
            <div class="prediction-category">
                <h3>{cat_label}</h3>
                <ul class="prediction-list">
            """

            for pred in cat_predictions:
                prediction_text = convert(pred.get("prediction", ""), citation_map)
                # Map confidence to high/medium/low for CSS styling
                conf = pred.get("confidence", 0.5)
                confidence_level = "high" if conf >= 0.7 else ("medium" if conf >= 0.4 else "low")
                timeframe = pred.get("timeframe", "2-4 weeks")
                rationale = convert(pred.get("rationale", ""), citation_map)

                html += f"""
                <li class="prediction-item confidence-{confidence_level}">
                    <div class="prediction-text">{prediction_text}</div>
                    <div class="prediction-meta">
                        <span class="confidence">{int(conf * 100)}% confidence</span>
                        <span class="timeframe">{timeframe}</span>
                    </div>
                    {f'<div class="rationale">{rationale}</div>' if rationale else ""}
                </li>
                """

            html += """
                </ul>
            </div>
            """

        html += "</div>\n"
        return html

    @staticmethod
    def _render_civic_engagement(events: list[dict[str, Any]], citation_map: dict[str, Any]) -> str:
        """Render civic engagement section with government meetings, public hearings, and civic deadlines"""
        if not events:
            return ""

        convert = PersonalizedNarrativeTemplate._convert_citations_to_links

        # Filter for civic events (keywords: meeting, hearing, board, school board, election, zoning, council)
        civic_keywords = [
            "meeting",
            "hearing",
            "board",
            "school board",
            "election",
            "zoning",
            "council",
            "public comment",
            "supervisor",
            "ordinance",
            "ballot",
            "vote",
            "planning commission",
        ]

        civic_events = []
        for event in events:
            # Handle both dict and string formats (Claude sometimes returns strings)
            if isinstance(event, dict):
                event_text = f"{event.get('event', '')} {event.get('why_matters', '')} {event.get('recommended_action', '')}".lower()
            else:
                event_text = str(event).lower()
            if any(keyword in event_text for keyword in civic_keywords):
                civic_events.append(event)

        if not civic_events:
            return ""

        html = """
        <div class="civic-section">
            <h2>CIVIC ENGAGEMENT OPPORTUNITIES</h2>
            <p style="margin: 0 0 16px 0; color: #4a5568; font-size: 15px;">
                Upcoming meetings, public hearings, and civic participation opportunities in your area.
            </p>
        """

        for event in civic_events:
            # Handle both dict and string formats (Claude sometimes returns strings)
            if isinstance(event, dict):
                event_name = convert(event.get("event", ""), citation_map)
                when = convert(event.get("when", ""), citation_map)
                why_matters = convert(event.get("why_matters", ""), citation_map)
                action = convert(event.get("recommended_action", ""), citation_map)
            else:
                event_name = convert(str(event), citation_map)
                when = ""
                why_matters = ""
                action = ""

            html += f"""
            <div class="civic-event">
                <div class="civic-event-title">{event_name}</div>
                <div class="civic-event-date">{when}</div>
                <div class="civic-event-details">{why_matters}</div>
        """

            if action:
                html += f"""
                <div class="civic-action">
                    <div class="civic-action-label">How to Participate</div>
                    <div class="civic-action-text">{action}</div>
                </div>
        """

            html += """
            </div>
        """

        html += """
        </div>
        """
        return html


# Template aliases for backward compatibility
DailyBriefTemplate = PersonalizedNarrativeTemplate
