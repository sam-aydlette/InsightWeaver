"""
Prompt for the decision router.

DECISION_ROUTING_PROMPT matches today's situations against the user's open
decision factors: which factors does each situation bear on, and which way
did the evidence move them?
"""

DECISION_ROUTING_PROMPT = """You are routing today's news analysis into a user's standing decisions. The user is carrying a set of decisions, each with factors they are tracking. Your job is to find where today's situations contain evidence that bears on those factors.

## How to route

For each situation, ask: does it contain evidence that bears on any of the tracked factors? Most situations bear on no factors -- that is fine and expected. Only route a situation to a factor when there is a real, specific connection.

When you do route:

- **direction** -- how the evidence moves the factor:
  - `supports`: the evidence makes the factor look more favorable for the decision, or confirms the user's tracked read.
  - `complicates`: the evidence makes the factor look less favorable, or cuts against the user's tracked read.
  - `neutral`: the evidence is relevant but does not clearly push either way.
- **epistemic_status** -- the strength of the evidence, copied from how the situation labels it: `reported_fact`, `single_source`, `consensus`, or `speculation`. When the situation is ambiguous, choose the weaker label.
- **excerpt** -- one sentence, drawn from the situation, stating what the evidence actually is. Concrete, not a paraphrase of the factor.

Be conservative. A vague topical overlap is not evidence. If a situation discusses housing and a factor mentions housing, that is not automatically a route -- the situation must contain something that actually bears on that specific factor.

## Open decision factors

{factors_block}

## Today's situations

{situations_block}

## Output

Return valid JSON. Include only real routes; an empty list is a valid answer.

```json
{{
  "evidence": [
    {{
      "situation_index": 0,
      "factor_id": 5,
      "direction": "complicates",
      "epistemic_status": "single_source",
      "excerpt": "One concrete sentence stating the evidence."
    }}
  ]
}}
```

Return ONLY the JSON, no markdown fencing or commentary."""
