"""
Trust Report Formatting
Format trust analysis results for terminal display and export
"""
from typing import Dict, Any, Optional

from .moderate_formatter import format_moderate_trust_summary


class TrustReportFormatter:
    """
    Formats trust verification results for display

    Stage 2A: Basic response display only
    Stage 2B-2E: Will add comprehensive trust analysis formatting
    """

    @staticmethod
    def format_response_display(response: str, max_length: Optional[int] = None) -> str:
        """
        Format Claude response for terminal display

        Args:
            response: The response text
            max_length: Optional maximum length (None = show all)

        Returns:
            Formatted response string
        """
        lines = []
        lines.append("\n" + "=" * 70)
        lines.append("CLAUDE RESPONSE")
        lines.append("=" * 70)

        if max_length and len(response) > max_length:
            lines.append(response[:max_length])
            lines.append(f"\n... (truncated, {len(response)} chars total)")
        else:
            lines.append(response)

        lines.append("=" * 70)
        return "\n".join(lines)

    @staticmethod
    def format_trust_analysis(analysis: Dict[str, Any]) -> str:
        """
        Format trust analysis results

        Stage 2B: Fact verification implemented
        Stage 2C-2E: Will add bias and intimacy analysis

        Args:
            analysis: Analysis results dictionary

        Returns:
            Formatted analysis string
        """
        if not analysis.get("analyzed", False):
            return f"\n{analysis.get('message', 'Analysis not available')}\n"

        lines = []
        lines.append("\n" + "=" * 70)
        lines.append("TRUST ANALYSIS")
        lines.append("=" * 70)

        # Fact Verification Results
        if "facts" in analysis and analysis["facts"]:
            facts = analysis["facts"]
            lines.append("\n## FACT VERIFICATION\n")

            for i, verification in enumerate(facts.get("verifications", []), 1):
                claim = verification.get("claim", {})
                verdict = verification.get("verdict", "UNKNOWN")
                confidence = verification.get("confidence", 0.0)
                reasoning = verification.get("reasoning", "")

                # Verdict icon
                icon = {
                    "VERIFIED": "✓",
                    "CONTRADICTED": "✗",
                    "UNVERIFIABLE": "?",
                    "OUTDATED": "⏰",
                    "ERROR": "⚠"
                }.get(verdict, "?")

                lines.append(f"{i}. [{icon}] {claim.get('text', '')}")
                lines.append(f"   Type: {claim.get('type', 'UNKNOWN')}")
                lines.append(f"   Verdict: {verdict} (confidence: {confidence:.2f})")
                lines.append(f"   Reasoning: {reasoning}")

                # Show temporal verification if present
                temporal_check = verification.get("temporal_check")
                if temporal_check:
                    still_current = temporal_check.get("still_current")
                    checked_date = temporal_check.get("checked_date", "unknown")

                    if still_current is False:
                        lines.append(f"   ⏰ TEMPORAL CHECK: Outdated as of {checked_date}")
                        update_info = temporal_check.get("update_info", "")
                        if update_info:
                            lines.append(f"      Update: {update_info}")
                    elif still_current is True:
                        lines.append(f"   ✓ TEMPORAL CHECK: Still current as of {checked_date}")
                    else:
                        lines.append(f"   ⚠ TEMPORAL CHECK: Could not verify current status")

                # Show caveats if present
                caveats = verification.get("caveats", [])
                if caveats:
                    lines.append(f"   Caveats: {'; '.join(caveats)}")

                # Show contradictions if present
                contradictions = verification.get("contradictions", [])
                if contradictions:
                    lines.append(f"   ⚠ Contradictions: {'; '.join(contradictions)}")

                lines.append("")

        # Bias Analysis
        if "bias" in analysis:
            bias = analysis["bias"]
            if not bias.get("analyzed", False):
                lines.append(f"\n## BIAS ANALYSIS\n")
                lines.append(f"{bias.get('message', 'Not analyzed')}\n")
            else:
                lines.append("\n## BIAS ANALYSIS\n")

                # Framing issues
                framing_issues = bias.get("framing_issues", [])
                if framing_issues:
                    lines.append("### Framing\n")
                    for i, issue in enumerate(framing_issues, 1):
                        lines.append(f"{i}. Frame: {issue.get('frame_type', 'Unknown')}")
                        lines.append(f"   Text: \"{issue.get('text', '')}\"")
                        lines.append(f"   Effect: {issue.get('effect', '')}")
                        lines.append(f"   Alternative: {issue.get('alternative', '')}")
                        lines.append("")

                # Assumptions
                assumptions = bias.get("assumptions", [])
                if assumptions:
                    lines.append("### Hidden Assumptions\n")
                    for i, assumption in enumerate(assumptions, 1):
                        lines.append(f"{i}. {assumption.get('assumption', '')}")
                        lines.append(f"   Basis: \"{assumption.get('basis', '')}\"")
                        lines.append(f"   Impact: {assumption.get('impact', '')}")
                        lines.append("")

                # Omissions
                omissions = bias.get("omissions", [])
                if omissions:
                    lines.append("### Missing Perspectives\n")
                    for i, omission in enumerate(omissions, 1):
                        lines.append(f"{i}. {omission.get('missing_perspective', '')}")
                        lines.append(f"   Relevance: {omission.get('relevance', '')}")
                        lines.append(f"   Suggestion: {omission.get('suggestion', '')}")
                        lines.append("")

                # Loaded language
                loaded_terms = bias.get("loaded_terms", [])
                if loaded_terms:
                    lines.append("### Loaded Language\n")
                    for i, term in enumerate(loaded_terms, 1):
                        lines.append(f"{i}. \"{term.get('term', '')}\"")
                        lines.append(f"   Connotation: {term.get('connotation', '')}")
                        lines.append(f"   Neutral alternative: \"{term.get('neutral_alternative', '')}\"")
                        lines.append("")

                # Summary if no issues
                total_issues = bias.get("total_issues", 0)
                if total_issues == 0:
                    lines.append("✓ No significant bias issues detected\n")

        # Intimacy Detection
        if "intimacy" in analysis:
            intimacy = analysis["intimacy"]
            if not intimacy.get("analyzed", False):
                lines.append(f"\n## INTIMACY DETECTION\n")
                lines.append(f"{intimacy.get('message', 'Not analyzed')}\n")
            else:
                lines.append("\n## INTIMACY DETECTION\n")

                # Overall tone
                tone = intimacy.get("overall_tone", "PROFESSIONAL")
                tone_icon = {
                    "PROFESSIONAL": "✓",
                    "FAMILIAR": "⚠",
                    "INAPPROPRIATE": "✗"
                }.get(tone, "?")

                lines.append(f"Overall Tone: [{tone_icon}] {tone}\n")

                # Summary
                summary = intimacy.get("summary", "")
                if summary:
                    lines.append(f"Summary: {summary}\n")

                # Issues
                issues = intimacy.get("issues", [])
                if issues:
                    lines.append("### Detected Issues\n")
                    for i, issue in enumerate(issues, 1):
                        category = issue.get("category", "UNKNOWN")
                        text = issue.get("text", "")
                        severity = issue.get("severity", "LOW")
                        explanation = issue.get("explanation", "")
                        alternative = issue.get("professional_alternative", "")

                        # Severity icon
                        severity_icon = {
                            "HIGH": "⚠⚠⚠",
                            "MEDIUM": "⚠⚠",
                            "LOW": "⚠"
                        }.get(severity, "⚠")

                        lines.append(f"{i}. [{severity_icon}] {category}")
                        lines.append(f"   Text: \"{text}\"")
                        lines.append(f"   Explanation: {explanation}")
                        lines.append(f"   Professional alternative: \"{alternative}\"")
                        lines.append("")
                else:
                    lines.append("✓ No intimacy issues detected\n")

        lines.append("=" * 70)
        return "\n".join(lines)

    @staticmethod
    def format_compact_summary(analysis: Dict[str, Any]) -> str:
        """
        Format compact one-line trust summary

        Stage 2B: Fact verification implemented
        Stage 2C-2E: Will add bias and intimacy

        Args:
            analysis: Analysis results dictionary

        Returns:
            One-line summary string
        """
        if not analysis.get("analyzed", False):
            return "Trust analysis not yet run"

        parts = []

        # Fact verification summary
        if "facts" in analysis and analysis["facts"]:
            facts = analysis["facts"]
            verified = facts.get("verified_count", 0)
            uncertain = facts.get("uncertain_count", 0)
            contradicted = facts.get("contradicted_count", 0)

            # Count outdated facts separately
            outdated = 0
            for verification in facts.get("verifications", []):
                if verification.get("verdict") == "OUTDATED":
                    outdated += 1
                    verified = max(0, verified - 1)  # Don't double-count

            fact_parts = []
            if verified > 0:
                fact_parts.append(f"✓ {verified}")
            if outdated > 0:
                fact_parts.append(f"⏰ {outdated}")
            if uncertain > 0:
                fact_parts.append(f"? {uncertain}")
            if contradicted > 0:
                fact_parts.append(f"✗ {contradicted}")

            if fact_parts:
                parts.append(f"Facts: {' | '.join(fact_parts)}")
            else:
                parts.append("Facts: none found")

        # Bias analysis summary
        if "bias" in analysis:
            bias = analysis["bias"]
            if bias.get("analyzed", False):
                total_issues = bias.get("total_issues", 0)
                if total_issues > 0:
                    issue_parts = []
                    framing_count = len(bias.get("framing_issues", []))
                    assumption_count = len(bias.get("assumptions", []))
                    omission_count = len(bias.get("omissions", []))
                    loaded_count = len(bias.get("loaded_terms", []))

                    if framing_count > 0:
                        issue_parts.append(f"{framing_count}F")
                    if assumption_count > 0:
                        issue_parts.append(f"{assumption_count}A")
                    if omission_count > 0:
                        issue_parts.append(f"{omission_count}O")
                    if loaded_count > 0:
                        issue_parts.append(f"{loaded_count}L")

                    parts.append(f"Bias: ⚠ {' '.join(issue_parts)}")
                else:
                    parts.append("Bias: ✓")
            else:
                parts.append("Bias: pending")

        # Intimacy
        if "intimacy" in analysis:
            intimacy = analysis["intimacy"]
            if intimacy.get("analyzed", False):
                total_issues = intimacy.get("total_issues", 0)
                overall_tone = intimacy.get("overall_tone", "PROFESSIONAL")

                if total_issues > 0:
                    high_count = intimacy.get("high_severity_count", 0)
                    medium_count = intimacy.get("medium_severity_count", 0)
                    low_count = intimacy.get("low_severity_count", 0)

                    issue_parts = []
                    if high_count > 0:
                        issue_parts.append(f"{high_count}H")
                    if medium_count > 0:
                        issue_parts.append(f"{medium_count}M")
                    if low_count > 0:
                        issue_parts.append(f"{low_count}L")

                    parts.append(f"Tone: ⚠ {' '.join(issue_parts)} ({overall_tone})")
                else:
                    parts.append(f"Tone: ✓ ({overall_tone})")
            else:
                parts.append("Tone: pending")

        if parts:
            return " | ".join(parts)
        else:
            return "No analysis results"

    @staticmethod
    def format_moderate_summary(analysis: Dict[str, Any]) -> str:
        """
        Format moderate-detail trust summary

        Intermediate format between compact and verbose showing:
        - Fact verification counts
        - Top 2-3 bias/framing issues
        - Tone rating with explanation
        - Actionability check (YES/NO/CAUTION)

        Args:
            analysis: Analysis results dictionary

        Returns:
            Formatted moderate-detail summary string
        """
        if not analysis.get("analyzed", False):
            return "\nTrust Verification: UNAVAILABLE (Analysis not run)\n"

        return "\n" + format_moderate_trust_summary(analysis) + "\n"

    @staticmethod
    def export_to_json(result: Dict[str, Any]) -> str:
        """
        Export full results to JSON format

        Args:
            result: Complete pipeline results

        Returns:
            JSON string
        """
        import json
        return json.dumps(result, indent=2, ensure_ascii=False)

    @staticmethod
    def export_to_text(result: Dict[str, Any]) -> str:
        """
        Export full results to detailed text format

        Args:
            result: Complete pipeline results

        Returns:
            Formatted text report
        """
        lines = []
        lines.append("=" * 70)
        lines.append("INSIGHTWEAVER TRUST REPORT")
        lines.append("=" * 70)

        lines.append("\n## ORIGINAL QUERY")
        lines.append(result.get("original_query", "N/A"))

        lines.append("\n## CLAUDE RESPONSE")
        lines.append(result.get("response", "N/A"))

        if "analysis" in result:
            lines.append("\n## TRUST ANALYSIS")
            lines.append(TrustReportFormatter.format_trust_analysis(result["analysis"]))

        lines.append("\n" + "=" * 70)
        lines.append("End of Report")
        lines.append("=" * 70)

        return "\n".join(lines)
