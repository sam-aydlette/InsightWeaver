"""
Personalized Narrative Newsletter Templates for InsightWeaver
Story-driven, temporal-layered intelligence briefings
"""

from datetime import datetime
from typing import Dict, List, Any, Optional


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
    def generate_html(data: Dict[str, Any]) -> str:
        """
        Generate HTML version of personalized narrative brief

        Args:
            data: Must contain 'synthesis_data' from NarrativeSynthesisAgent
        """
        synthesis = data.get('synthesis_data', {})
        metadata = synthesis.get('metadata', {})
        temporal_layers = synthesis.get('temporal_layers', {})
        cross_domain = synthesis.get('cross_domain_insights', [])
        priority_actions = synthesis.get('priority_actions', [])
        executive_summary = synthesis.get('executive_summary', 'No narrative synthesis available.')

        # Get user context for personalization
        user_context = data.get('user_context', {})
        location = user_context.get('location', {})
        location_str = f"{location.get('city', 'Your')}, {location.get('state', 'Area')}"

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Your Intelligence Brief - {PersonalizedNarrativeTemplate.format_date(data.get('date', datetime.now()))}</title>
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
        .executive-summary {{
            background: #ebf8ff;
            border-left: 4px solid #3182ce;
            padding: 24px;
            margin-bottom: 36px;
            border-radius: 4px;
        }}
        .executive-summary h2 {{
            margin: 0 0 12px 0;
            color: #2c5282;
            font-size: 20px;
        }}
        .executive-summary p {{
            font-size: 16px;
            line-height: 1.8;
            margin: 12px 0;
            color: #2d3748;
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
            <h1>Your Intelligence Brief</h1>
            <div class="meta">
                {PersonalizedNarrativeTemplate.format_date(data.get('date', datetime.now()))} |
                Personalized for {location_str} |
                {metadata.get('articles_analyzed', 0)} sources analyzed
            </div>
        </div>

        <div class="executive-summary">
            <h2>What You Need to Know</h2>
            {PersonalizedNarrativeTemplate._render_executive_summary(executive_summary)}
        </div>

        {PersonalizedNarrativeTemplate._render_temporal_layers(temporal_layers)}

        {PersonalizedNarrativeTemplate._render_cross_domain_insights(cross_domain)}

        {PersonalizedNarrativeTemplate._render_priority_actions(priority_actions)}

        <div class="footer">
            Generated by <a href="#">InsightWeaver</a> |
            Synthesis ID: {metadata.get('synthesis_id', 'N/A')[:8]}... |
            {metadata.get('generated_at', 'Unknown time')}
        </div>
    </div>
</body>
</html>
        """
        return html.strip()

    @staticmethod
    def _render_executive_summary(summary: str) -> str:
        """Render executive summary with paragraph breaks"""
        paragraphs = summary.split('\n\n')
        return '\n'.join([f'<p>{p.strip()}</p>' for p in paragraphs if p.strip()])

    @staticmethod
    def _render_temporal_layers(temporal_layers: Dict[str, Any]) -> str:
        """Render temporal sections with narratives"""
        if not temporal_layers:
            return ""

        sections_html = []

        # Order and labels for temporal horizons
        horizons = [
            ('immediate', 'Immediate Focus', '0-48 hours'),
            ('near_term', 'Near-Term Watch', '1-2 weeks'),
            ('medium_term', 'Medium-Term Planning', '1-3 months'),
            ('long_term', 'Long-Term Positioning', '6+ months')
        ]

        for horizon_key, horizon_label, timeline in horizons:
            layer = temporal_layers.get(horizon_key, {})
            if not layer or not layer.get('narrative'):
                continue

            narrative = layer.get('narrative', '')
            implications = layer.get('key_implications', [])
            actions = layer.get('recommended_actions', [])

            section_html = f"""
        <div class="temporal-section {horizon_key}">
            <h3>{horizon_label}<span class="timeline">{timeline}</span></h3>
            <div class="narrative">{narrative}</div>
            """

            if implications:
                section_html += """
            <div class="implications">
                <h4>Why This Matters to You</h4>
                <ul>
                """
                for impl in implications:
                    section_html += f"<li>{impl}</li>\n"
                section_html += """
                </ul>
            </div>
                """

            section_html += "</div>\n"
            sections_html.append(section_html)

        return '\n'.join(sections_html)

    @staticmethod
    def _render_cross_domain_insights(insights: List[Dict[str, Any]]) -> str:
        """Render cross-domain connections"""
        if not insights:
            return ""

        html = '<div class="section">\n'

        for insight in insights[:3]:  # Limit to top 3 insights
            theme = insight.get('theme', 'Connection')
            narrative = insight.get('narrative', '')
            personal_impact = insight.get('personal_impact', '')

            html += f"""
        <div class="cross-domain">
            <h4>🔗 {theme}</h4>
            <div class="narrative">{narrative}</div>
            {f'<div class="personal-impact">For you: {personal_impact}</div>' if personal_impact else ''}
        </div>
            """

        html += '</div>\n'
        return html

    @staticmethod
    def _render_priority_actions(actions: List[Dict[str, Any]]) -> str:
        """Render priority actions section"""
        if not actions:
            return ""

        html = """
        <div class="actions-section">
            <h3>What You Should Do</h3>
        """

        for action in actions:
            action_text = action.get('action', '')
            urgency = action.get('urgency', 'medium')
            reasoning = action.get('reasoning', '')

            html += f"""
            <div class="action-item {urgency}">
                <div><span class="urgency">{urgency}</span><span class="action-text">{action_text}</span></div>
                {f'<div class="reasoning">{reasoning}</div>' if reasoning else ''}
            </div>
            """

        html += """
        </div>
        """
        return html

    @staticmethod
    def generate_text(data: Dict[str, Any]) -> str:
        """Generate plain text version of personalized narrative brief"""
        synthesis = data.get('synthesis_data', {})
        temporal_layers = synthesis.get('temporal_layers', {})
        cross_domain = synthesis.get('cross_domain_insights', [])
        priority_actions = synthesis.get('priority_actions', [])
        executive_summary = synthesis.get('executive_summary', 'No narrative synthesis available.')

        user_context = data.get('user_context', {})
        location = user_context.get('location', {})
        location_str = f"{location.get('city', 'Your')}, {location.get('state', 'Area')}"

        text = f"""
═══════════════════════════════════════════════════════════════
YOUR INTELLIGENCE BRIEF
{PersonalizedNarrativeTemplate.format_date(data.get('date', datetime.now()))}
Personalized for {location_str}
═══════════════════════════════════════════════════════════════

WHAT YOU NEED TO KNOW
─────────────────────────────────────────────────────────────

{executive_summary}

"""

        # Temporal sections
        horizons = [
            ('immediate', 'IMMEDIATE FOCUS (0-48 hours)', '⚠️'),
            ('near_term', 'NEAR-TERM WATCH (1-2 weeks)', '📅'),
            ('medium_term', 'MEDIUM-TERM PLANNING (1-3 months)', '📊'),
            ('long_term', 'LONG-TERM POSITIONING (6+ months)', '🔮')
        ]

        for horizon_key, horizon_label, emoji in horizons:
            layer = temporal_layers.get(horizon_key, {})
            if not layer or not layer.get('narrative'):
                continue

            text += f"""\n{emoji} {horizon_label}
─────────────────────────────────────────────────────────────

{layer.get('narrative', '')}

"""
            implications = layer.get('key_implications', [])
            if implications:
                text += "Why this matters to you:\n"
                for impl in implications:
                    text += f"  • {impl}\n"
                text += "\n"

        # Cross-domain insights
        if cross_domain:
            text += """\n🔗 CONNECTIONS YOU SHOULD SEE
─────────────────────────────────────────────────────────────

"""
            for insight in cross_domain[:3]:
                text += f"{insight.get('theme', 'Connection')}:\n{insight.get('narrative', '')}\n"
                if insight.get('personal_impact'):
                    text += f"For you: {insight.get('personal_impact')}\n"
                text += "\n"

        # Priority actions
        if priority_actions:
            text += """\n✓ WHAT YOU SHOULD DO
─────────────────────────────────────────────────────────────

"""
            for action in priority_actions:
                urgency = action.get('urgency', 'medium').upper()
                text += f"[{urgency}] {action.get('action', '')}\n"
                if action.get('reasoning'):
                    text += f"    → {action.get('reasoning')}\n"
                text += "\n"

        text += """
═══════════════════════════════════════════════════════════════
Generated by InsightWeaver
═══════════════════════════════════════════════════════════════
"""
        return text.strip()


# Keep legacy template for backward compatibility during transition
DailyBriefTemplate = PersonalizedNarrativeTemplate
WeeklyTrendTemplate = PersonalizedNarrativeTemplate