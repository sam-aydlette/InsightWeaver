"""
Perspective System
Generic, modular frameworks for intelligence analysis that adapt to user configuration
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class Perspective:
    """
    A perspective defines how intelligence should be analyzed and presented.
    Framework uses placeholders for user-specific data injection at runtime.
    """
    id: str
    name: str
    description: str
    framework: str  # Analysis instructions with {placeholder} format
    tone: str  # Communication style


# Daily Intelligence Brief - Generic framework for civic-minded professionals
# Adapts to any location, profession, and interests via user_profile.json
DAILY_INTELLIGENCE_BRIEF = Perspective(
    id="daily_intelligence_brief",
    name="Daily Intelligence Brief",
    description="Comprehensive daily analysis for civic-minded professionals",
    framework="""
**Geographic Scope Analysis:**
Analyze developments across these layers, identifying specific, measurable trends:

1. **Local** ({city}, {region}):
   - Daily life impacts: schools, transportation, housing, local economy
   - Community services and infrastructure
   - Local governance and policy changes

2. **State/Regional** ({state}):
   - State policy and regulatory changes
   - Regional economic shifts and development
   - Regional infrastructure and resource allocation

3. **National** ({country}):
   - Federal policy affecting voting decisions
   - National economy and political developments
   - National security and governance

4. **Global**:
   - International events with direct local/regional impact
   - Geopolitical developments affecting economy or security
   - Global trends relevant to professional domain

5. **Niche Field** ({professional_domains}):
   - Industry-specific developments and innovations
   - Professional domain trends and career implications
   - Actionable intelligence for field advancement
   - Focus on truly innovative breakthroughs, not routine news

**Analysis Requirements:**

**Trends:** Extract measurable, specific trends
- Format: "[Subject] [direction] [quantifier]"
- Example: "Federal cybersecurity budget increasing 12% for FY2026"
- Include confidence level (0.0-1.0) for each trend

**Priority Events:** Identify upcoming events (next 2-4 weeks)
- Rank impact: CRITICAL / HIGH / MEDIUM / LOW
- CRITICAL: Immediate action needed, major decision point
- HIGH: Significant impact on family, work, community
- MEDIUM: Notable but manageable
- LOW: Awareness only
- Specify: what it is, when, why it matters, recommended action

**Predictions:** Project likely developments (2-4 week horizon)
- Categories: Local governance, Education, Niche field, Economic conditions, Infrastructure
- Include: prediction, confidence (0.0-1.0 probability), timeframe, rationale
- Base on identified trends and patterns

**Bottom Line:**
- Lead with 2-3 sentence executive summary
- Flag immediate action items if any
- Most important takeaway for decision-making

**Tone & Style:**
- Clear, direct, analytical but accessible language
- Flag anything requiring immediate attention
- Note confidence levels when uncertain
- Identify connections between local/national/global events
- Keep niche section focused on actionable intelligence
""",
    tone="analytical_professional"
)

# Executive Summary - Quick briefing format
EXECUTIVE_SUMMARY = Perspective(
    id="executive_summary",
    name="Executive Summary",
    description="Concise high-level overview for busy professionals",
    framework="""
**Purpose**: Provide 3-5 minute read capturing essential developments.

**Focus Areas**:
- {professional_domains}: Industry and career-relevant developments
- {civic_focus}: Policy areas of interest
- {region}/{state}: Regional context and implications

**Output Structure**:
- Executive summary (2-3 sentences)
- Key developments (3-5 bullet points)
- Action items (1-3 immediate considerations)

**Tone**: {tone} - direct, actionable, assumes domain expertise
""",
    tone="analytical_concise"
)

# Weekly Digest - Longer form analysis
WEEKLY_DIGEST = Perspective(
    id="weekly_digest",
    name="Weekly Digest",
    description="Comprehensive weekly analysis with trend identification",
    framework="""
**Scope**: 7-day analysis window for {city}, {state}, and broader context.

**Analysis Dimensions**:
1. Professional ({professional_domains}): Industry trends and career implications
2. Civic ({civic_focus}): Policy developments and governance
3. Economic: Market trends, regional economy, household impact
4. Community: Local developments affecting daily life

**Trend Analysis**:
- Identify patterns across the week
- Project 2-4 week implications
- Highlight cross-domain connections
- Recommend strategic positioning

**Geographic Scope**: {city} → {state} → {country} → Global
""",
    tone="analytical_comprehensive"
)


# Perspective registry
PERSPECTIVES: Dict[str, Perspective] = {
    "daily_intelligence_brief": DAILY_INTELLIGENCE_BRIEF,
    "executive_summary": EXECUTIVE_SUMMARY,
    "weekly_digest": WEEKLY_DIGEST,
}


def get_perspective(perspective_id: str) -> Perspective:
    """
    Get perspective by ID

    Args:
        perspective_id: Perspective identifier (no default - must be explicit)

    Returns:
        Perspective configuration

    Raises:
        KeyError: If perspective not found
    """
    if perspective_id not in PERSPECTIVES:
        raise KeyError(f"Perspective '{perspective_id}' not found. Available: {list(PERSPECTIVES.keys())}")

    return PERSPECTIVES[perspective_id]


def list_perspectives() -> List[str]:
    """List available perspective IDs"""
    return list(PERSPECTIVES.keys())


def get_default_perspective() -> str:
    """Get default perspective ID for daily briefings"""
    return "daily_intelligence_brief"
