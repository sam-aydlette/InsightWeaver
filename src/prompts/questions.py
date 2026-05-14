"""
Prompts for the question matcher.

QUESTION_MATCHING_PROMPT decides whether a freshly-proposed unresolved_question
from today's synthesis is the same underlying question as one of the currently
open Questions in the persistent graph.
"""

QUESTION_MATCHING_PROMPT = """You are matching freshly-proposed questions against a list of open questions that the system is already tracking. Your job is to decide, for each proposed question, whether it is the same underlying question as one of the open ones, or whether it is a genuinely new question.

## What counts as "the same question"

Two questions are the same when they ask about the same underlying outcome, even if the phrasing differs and even if the proposed question is more specific or more general. Examples:

- "Will the Fed cut rates in June?" and "Does the Fed pivot at the June meeting?" — same.
- "Will the bill pass?" and "Does the Senate vote it through?" — different. The second is one specific path to the first; the first encompasses the second plus other paths.
- "Will inflation come down?" and "Will the May CPI print show inflation easing?" — different. The second is a specific observation that bears on the first.

When in doubt, prefer "new" over "match". A false match collapses two distinct epistemic threads; a false new just creates a duplicate that can be merged later.

## Constraints

- Never match across substantively different domains (a question about labor markets is not the same as one about housing markets, even if both touch employment).
- A proposed question that asks about a specific event (a vote, a print, a hearing) is not the same as an open question about the broader outcome that event would inform.
- The open list is sorted with most-recent first. Older open questions are likelier to be stale or already resolved-in-effect; be slightly more cautious about matching them.

## Input

### Proposed questions
{proposed_block}

### Open questions
{open_block}

## Output

Return valid JSON with this exact structure, one entry per proposed question, in the same order:

```json
{{
  "matches": [
    {{
      "proposed_index": 0,
      "matched_id": 47,
      "reasoning": "Short reason (under 20 words)."
    }},
    {{
      "proposed_index": 1,
      "matched_id": null,
      "reasoning": "Short reason (under 20 words)."
    }}
  ]
}}
```

`matched_id` is the integer id of the matched open question, or `null` if none matches. Return ONLY the JSON, no markdown fencing or commentary."""
