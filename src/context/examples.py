"""
Few-Shot Examples for Claude Analysis
Demonstrates desired output format and quality
"""

from typing import List, Dict, Any


# Example synthesis output showing desired structure and style
# Generic example that demonstrates format without location-specific assumptions
SYNTHESIS_EXAMPLE = {
    "input_summary": "Articles about federal AI policy, local infrastructure projects, and cybersecurity threats",
    "output": {
        "bottom_line": {
            "summary": "Federal AI policy developments are accelerating with immediate implications for regional defense and technology sectors. The NIST AI Safety Institute location announcement creates employment opportunities and heightened scrutiny for area contractors, while local infrastructure modernization intersects with federal smart city initiatives. Near-term focus should be on procurement rule changes affecting local firms and engagement with emerging AI governance standards.",
            "immediate_actions": [
                "Review NIST AI Safety Institute RFP when published (expected Thursday)",
                "Monitor County Board technology committee meetings regarding AI vendor standards"
            ]
        },

        "trends_and_patterns": {
            "local": [
                {
                    "subject": "Local technology contractor engagement with federal AI initiatives",
                    "direction": "increasing",
                    "quantifier": "RFP response activity expected to triple in Q1 2025",
                    "description": "Area contractors preparing for AI Safety Institute implementation contracts with increased proposal activity",
                    "confidence": 0.85
                },
                {
                    "subject": "Regional infrastructure cybersecurity incidents",
                    "direction": "stable",
                    "quantifier": "Consistent baseline with recent public institution breach",
                    "description": "Security vulnerabilities in regional infrastructure triggering federal monitoring for broader resilience planning",
                    "confidence": 0.78
                }
            ],
            "state_regional": [
                {
                    "subject": "State-level AI procurement guidelines",
                    "direction": "emerging",
                    "quantifier": "Framework development accelerating across Virginia agencies",
                    "description": "State procurement offices beginning to align with federal AI governance standards",
                    "confidence": 0.72
                }
            ],
            "national": [
                {
                    "subject": "Federal AI procurement spending",
                    "direction": "increasing",
                    "quantifier": "15% year-over-year growth projected",
                    "description": "Defense and civilian agencies expanding AI acquisition budgets following NIST institute establishment",
                    "confidence": 0.90
                }
            ],
            "global": [
                {
                    "subject": "International AI governance convergence",
                    "direction": "increasing",
                    "quantifier": "G7 nations aligning on algorithmic accountability frameworks",
                    "description": "Global regulatory coordination creating standardized requirements for government AI systems",
                    "confidence": 0.68
                }
            ],
            "niche_field": [
                {
                    "subject": "Cybersecurity career specialization",
                    "direction": "emerging",
                    "quantifier": "Governance roles growing faster than technical roles",
                    "description": "Field bifurcating between technical implementation and compliance positions with regional advantages for governance specialization",
                    "confidence": 0.82
                }
            ]
        },

        "priority_events": [
            {
                "event": "NIST AI Safety Institute RFP publication",
                "when": "Expected Thursday (within 48 hours)",
                "impact_level": "HIGH",
                "why_matters": "Early engagement critical for local firms to capture implementation contracts; subcontracting opportunities favor firms understanding requirements early",
                "recommended_action": "Prepare response materials and assess company positioning for prime or subcontracting opportunities",
                "confidence": 0.92
            },
            {
                "event": "County Board technology vendor standards discussion",
                "when": "Next two weeks",
                "impact_level": "MEDIUM",
                "why_matters": "Local procurement rules will mirror federal approaches, creating early warning for how AI governance affects county services (schools, permits, infrastructure)",
                "recommended_action": "Monitor meeting agendas and attend public sessions to understand implementation timeline",
                "confidence": 0.75
            },
            {
                "event": "Federal AI procurement guidelines finalization",
                "when": "Next 2-4 weeks",
                "impact_level": "HIGH",
                "why_matters": "Guidelines will reshape how regional defense contractors bid on technology projects; compliance complexity may consolidate market toward larger firms",
                "recommended_action": "Evaluate compliance partnerships if operating as smaller contractor",
                "confidence": 0.88
            }
        ],

        "predictions_scenarios": {
            "local_governance": [
                {
                    "prediction": "County will adopt AI vendor accountability requirements similar to federal standards within 3-6 months",                    "confidence": 0.80,
                    "timeframe": "2-4 weeks for initial policy discussion",
                    "rationale": "Local governments typically follow federal technology procurement patterns with 3-6 month lag; County Board already showing interest based on meeting agendas"
                }
            ],
            "education": [
                {
                    "prediction": "School enrollment and resource allocation systems will incorporate algorithmic accountability reviews",                    "confidence": 0.65,
                    "timeframe": "2-4 weeks for pilot program announcements",
                    "rationale": "Federal frameworks cascading to state education agencies; pilot programs likely in districts serving federal workforce"
                }
            ],
            "niche_field": [
                {
                    "prediction": "Cybersecurity job market will require AI governance certifications for government contractor roles",                    "confidence": 0.85,
                    "timeframe": "2-4 weeks for requirement announcements in new solicitations",
                    "rationale": "Defense contractor clearances facing enhanced AI-related scrutiny; professional development in AI governance becoming competitive requirement"
                }
            ],
            "economic_conditions": [
                {
                    "prediction": "Small defense contractors will seek compliance partnerships or face market consolidation pressure",                    "confidence": 0.78,
                    "timeframe": "2-4 weeks for partnership announcements",
                    "rationale": "Compliance complexity with intersecting AI and cybersecurity requirements creating barriers to entry for smaller firms"
                }
            ],
            "infrastructure": [
                {
                    "prediction": "Regional infrastructure projects will incorporate AI oversight requirements in procurement specifications",                    "confidence": 0.70,
                    "timeframe": "2-4 weeks for updated RFP language",
                    "rationale": "Recent cybersecurity incidents triggering enhanced monitoring; smart city initiatives requiring governance frameworks"
                }
            ]
        },

        "metadata": {
            "articles_analyzed": 15,
            "synthesis_id": "example_001",
            "generated_at": "2025-10-06T12:00:00Z"
        }
    }
}


def get_few_shot_examples() -> List[Dict[str, Any]]:
    """
    Get few-shot examples for synthesis prompts

    Returns:
        List of input/output example pairs
    """
    return [SYNTHESIS_EXAMPLE]


def format_examples_for_prompt(examples: List[Dict[str, Any]]) -> str:
    """
    Format examples for inclusion in system prompt

    Args:
        examples: List of example dictionaries

    Returns:
        Formatted example text
    """
    formatted = "## Example Output Format\n\n"
    formatted += "Here is an example of the desired output structure and analytical depth:\n\n"

    for i, example in enumerate(examples, 1):
        formatted += f"### Example {i}\n"
        formatted += f"**Input Context:** {example['input_summary']}\n\n"
        formatted += "**Output Structure:**\n"
        formatted += "```json\n"

        import json
        formatted += json.dumps(example['output'], indent=2)
        formatted += "\n```\n\n"

        formatted += "**Key Quality Indicators:**\n"
        formatted += "- Bottom line provides clear executive summary with actionable next steps\n"
        formatted += "- Trends organized geographically (local → state → national → global → niche field)\n"
        formatted += "- Trends formatted as observable patterns with direction and quantifiers\n"
        formatted += "- Events prioritized by impact level with clear timeframes and recommended actions\n"
        formatted += "- Predictions include confidence scores, and rationale\n"
        formatted += "- Analytical tone balances professional rigor with personal relevance\n\n"

    return formatted
