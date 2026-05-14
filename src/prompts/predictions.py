"""
Prompt for the prediction tracker.

PREDICTION_CHECK_PROMPT grades open predictions against fresh coverage:
did the observable appear, did coverage explicitly contradict it, or is it
still open?
"""

PREDICTION_CHECK_PROMPT = """You are checking a ledger of open predictions against today's news coverage. Each prediction is a falsifiable observable that a past analysis flagged as worth watching. Your job is to decide, for each one, whether today's coverage resolves it.

## Verdicts

For each prediction, return exactly one verdict:

- **triggered**: today's coverage reports that the observable happened, or that the trigger condition was met. There must be specific evidence in the coverage -- not an inference.
- **contradicted**: today's coverage reports something that explicitly rules out the observable or the trigger condition. Again, specific evidence, not an inference.
- **open**: today's coverage does not bear on this prediction either way. This is the default. Most predictions on most days are "open".

Be conservative. "open" is the safe answer. Only return "triggered" or "contradicted" when the coverage directly addresses the observable. A prediction about a Fed rate decision is not triggered by an article that merely discusses inflation.

## Open predictions

{predictions_block}

## Today's coverage

{coverage_block}

## Output

Return valid JSON, one entry per prediction:

```json
{{
  "verdicts": [
    {{
      "prediction_id": 12,
      "verdict": "triggered",
      "note": "Short evidence-grounded reason, under 25 words. Name the coverage that resolves it."
    }},
    {{
      "prediction_id": 13,
      "verdict": "open",
      "note": "No coverage bears on this."
    }}
  ]
}}
```

Return ONLY the JSON, no markdown fencing or commentary."""
