"""
Moderate Detail Trust Formatter
Formats trust analysis results with moderate detail (between compact and verbose)
"""

import textwrap
from typing import Dict, Any, List, Tuple


def calculate_actionability(analysis: Dict[str, Any]) -> Tuple[str, str]:
    """
    Calculate actionability rating based on trust analysis

    Args:
        analysis: Trust analysis dictionary from TrustPipeline.analyze_response()

    Returns:
        Tuple of (rating, reason) where rating is YES/NO/CAUTION
    """
    # Extract fact metrics
    facts = analysis.get("facts", {})
    verified_count = facts.get("verified_count", 0)
    contradicted_count = facts.get("contradicted_count", 0)
    total_claims = facts.get("total_claims", 1)  # Avoid division by zero

    # Calculate fact score
    fact_score = verified_count / total_claims if total_claims > 0 else 0

    # Count high-severity bias issues
    bias = analysis.get("bias", {})
    high_severity_bias = count_high_severity_bias(bias)

    # Count high-severity intimacy issues
    intimacy = analysis.get("intimacy", {})
    high_severity_intimacy = intimacy.get("high_severity_count", 0)

    # Decision logic (most restrictive first)
    if contradicted_count > 0:
        return ("NO", "Contains contradicted facts")

    if high_severity_intimacy > 0:
        return ("NO", "Inappropriate tone detected")

    if fact_score < 0.6:
        return ("CAUTION", "Significant unverified claims")

    if high_severity_bias >= 2:
        return ("CAUTION", "Significant framing bias")

    if fact_score >= 0.8 and high_severity_bias == 0:
        return ("YES", "Strong fact verification, minimal bias")

    # Default to caution for mixed quality
    return ("CAUTION", "Mixed verification quality")


def count_high_severity_bias(bias: Dict[str, Any]) -> int:
    """
    Count high-severity bias issues

    High severity is determined by:
    - Framing issues (always high severity)
    - Assumptions with strong impact
    - Omissions of critical perspectives
    - Loaded terms with strong connotations

    Args:
        bias: Bias analysis dictionary

    Returns:
        Count of high-severity issues
    """
    count = 0

    # All framing issues are high severity
    framing_issues = bias.get("framing_issues", [])
    count += len(framing_issues)

    # Assumptions with certain keywords are high severity
    assumptions = bias.get("assumptions", [])
    for assumption in assumptions:
        impact = assumption.get("impact", "").lower()
        if any(keyword in impact for keyword in ["significant", "major", "critical", "strong"]):
            count += 1

    # Omissions of critical perspectives
    omissions = bias.get("omissions", [])
    for omission in omissions:
        relevance = omission.get("relevance", "").lower()
        if any(keyword in relevance for keyword in ["critical", "essential", "important", "key"]):
            count += 1

    return count


def select_top_bias_issues(bias: Dict[str, Any], max_count: int = 3) -> List[str]:
    """
    Select top bias issues by priority

    Priority order:
    1. Framing issues (highest impact)
    2. Assumptions (moderate impact)
    3. Omissions (moderate impact)
    4. Loaded terms (lower impact)

    Args:
        bias: Bias analysis dictionary
        max_count: Maximum number of issues to return

    Returns:
        List of formatted bias issue strings
    """
    selected_issues = []

    # Priority 1: Framing issues
    framing_issues = bias.get("framing_issues", [])
    for issue in framing_issues[:max_count]:
        frame_type = issue.get("frame_type", "Framing")
        text = issue.get("text", "")
        effect = issue.get("effect", "")

        # Format: "Frame type: text (effect)"
        formatted = f"{frame_type.capitalize()} framing"
        if text:
            formatted += f": \"{text[:50]}...\""  if len(text) > 50 else f": \"{text}\""
        if effect:
            formatted += f" ({effect[:80]})" if len(effect) > 80 else f" ({effect})"

        selected_issues.append(formatted)

        if len(selected_issues) >= max_count:
            return selected_issues

    # Priority 2: Assumptions
    assumptions = bias.get("assumptions", [])
    for assumption in assumptions:
        if len(selected_issues) >= max_count:
            break

        assumption_text = assumption.get("assumption", "")
        basis = assumption.get("basis", "")

        # Format: "Assumes X (basis: Y)"
        formatted = f"Assumes {assumption_text[:60]}"
        if basis:
            formatted += f" (basis: {basis[:60]})"

        selected_issues.append(formatted)

    # Priority 3: Omissions
    omissions = bias.get("omissions", [])
    for omission in omissions:
        if len(selected_issues) >= max_count:
            break

        missing = omission.get("missing_perspective", "")
        relevance = omission.get("relevance", "")

        # Format: "Omits X (relevance: Y)"
        formatted = f"Omits {missing[:60]}"
        if relevance:
            formatted += f" ({relevance[:60]})"

        selected_issues.append(formatted)

    # Priority 4: Loaded terms (only if still under max_count)
    loaded_terms = bias.get("loaded_terms", [])
    for term in loaded_terms:
        if len(selected_issues) >= max_count:
            break

        term_text = term.get("term", "")
        connotation = term.get("connotation", "")
        neutral = term.get("neutral_alternative", "")

        # Format: "Loaded term: X (connotation, neutral: Y)"
        formatted = f"Loaded term: \"{term_text}\""
        if connotation:
            formatted += f" ({connotation}"
            if neutral:
                formatted += f", neutral: \"{neutral}\""
            formatted += ")"

        selected_issues.append(formatted)

    return selected_issues[:max_count]


def format_moderate_trust_summary(analysis: Dict[str, Any], max_width: int = 80) -> str:
    """
    Format trust analysis as moderate-detail summary

    Includes:
    1. Fact verification counts
    2. Top 2-3 bias/framing issues
    3. Tone rating with explanation
    4. Actionability check (YES/NO/CAUTION)

    Args:
        analysis: Trust analysis dictionary from TrustPipeline.analyze_response()
        max_width: Maximum line width for formatting

    Returns:
        Formatted moderate-detail trust summary string
    """
    lines = []

    # Section header
    lines.append("Trust Verification:")

    # 1. Fact Verification Summary
    facts = analysis.get("facts", {})
    if facts.get("analyzed"):
        verified = facts.get("verified_count", 0)
        unverifiable = facts.get("uncertain_count", 0)
        contradicted = facts.get("contradicted_count", 0)

        fact_line = f"  Facts: {verified} verified, {unverifiable} unverifiable, {contradicted} contradicted"
        lines.append(fact_line)
        lines.append("")  # Blank line for spacing

    # 2. Top Bias/Framing Issues
    bias = analysis.get("bias", {})
    if bias.get("analyzed"):
        top_issues = select_top_bias_issues(bias, max_count=3)

        if top_issues:
            lines.append("  Top Bias/Framing Issues:")
            for issue in top_issues:
                # Wrap long issue text
                wrapped = textwrap.fill(
                    f"  • {issue}",
                    width=max_width,
                    subsequent_indent="    "
                )
                lines.append(wrapped)
        else:
            lines.append("  Bias/Framing: None detected")

        lines.append("")  # Blank line for spacing

    # 3. Tone Rating
    intimacy = analysis.get("intimacy", {})
    if intimacy.get("analyzed"):
        overall_tone = intimacy.get("overall_tone", "UNKNOWN")
        high_severity = intimacy.get("high_severity_count", 0)
        medium_severity = intimacy.get("medium_severity_count", 0)

        if high_severity > 0:
            tone_line = f"  Tone: {overall_tone} - {high_severity} high-severity intimacy issue(s) detected"
        elif medium_severity > 0:
            tone_line = f"  Tone: {overall_tone} - {medium_severity} medium-severity intimacy issue(s) detected"
        else:
            tone_line = f"  Tone: {overall_tone} - No intimacy issues detected"

        lines.append(tone_line)
        lines.append("")  # Blank line for spacing

    # 4. Actionability Check
    rating, reason = calculate_actionability(analysis)
    actionability_line = f"  Actionability: {rating} - {reason}"
    lines.append(actionability_line)

    return "\n".join(lines)


def format_compact_trust_summary(analysis: Dict[str, Any]) -> str:
    """
    Format trust analysis as ultra-compact one-liner

    For cases where even moderate detail is too much.
    Returns single line like: "Trust: ✓ Facts | ⚠ Bias | ✓ Tone | Actionable: YES"

    Args:
        analysis: Trust analysis dictionary

    Returns:
        Single-line trust summary
    """
    # Fact status
    facts = analysis.get("facts", {})
    contradicted = facts.get("contradicted_count", 0)
    verified = facts.get("verified_count", 0)
    total = facts.get("total_claims", 0)

    if contradicted > 0:
        fact_status = "✗ Facts"
    elif verified >= total * 0.8:
        fact_status = "✓ Facts"
    else:
        fact_status = "⚠ Facts"

    # Bias status
    bias = analysis.get("bias", {})
    high_bias = count_high_severity_bias(bias)

    if high_bias >= 2:
        bias_status = "✗ Bias"
    elif high_bias == 1:
        bias_status = "⚠ Bias"
    else:
        bias_status = "✓ Bias"

    # Tone status
    intimacy = analysis.get("intimacy", {})
    high_intimacy = intimacy.get("high_severity_count", 0)

    if high_intimacy > 0:
        tone_status = "✗ Tone"
    else:
        tone_status = "✓ Tone"

    # Actionability
    rating, _ = calculate_actionability(analysis)

    return f"Trust: {fact_status} | {bias_status} | {tone_status} | Actionable: {rating}"
