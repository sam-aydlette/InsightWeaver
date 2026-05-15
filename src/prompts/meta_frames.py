"""
Prompt for cross-cluster reconciliation.

META_FRAME_RECONCILIATION_PROMPT looks across all of today's situations and
flags meta-fractures: a single underlying frame conflict appearing across
multiple, topically distinct situations.
"""

META_FRAME_RECONCILIATION_PROMPT = """You are looking at frame analyses from several distinct situations in today's coverage. Each situation has its own narrative layers and its own fractures. Sometimes the same underlying fracture surfaces in more than one situation -- in different topical guises but with the same structural disagreement.

Your job is to find those cases, and only those.

## What counts

A meta-fracture is a single underlying disagreement that appears across two or more situations. Examples:

- A "scarcity vs. abundance of labor" fracture might surface in immigration coverage AND in industrial-policy coverage AND in housing coverage.
- A "national interest vs. global cooperation" fracture might surface in trade coverage AND in climate coverage.

Two situations sharing topical overlap does not make a meta-fracture. The fracture itself -- the structural point of disagreement -- must be the same.

Most days will have few meta-fractures or none. An empty result is a valid and expected answer.

## Today's situations

{situations_block}

## Output

Return valid JSON. Include only real meta-fractures; an empty list is fine.

```json
{{
  "meta_fractures": [
    {{
      "name": "Short label for the underlying fracture (under 8 words).",
      "description": "One sentence stating the structural disagreement.",
      "situation_indices": [0, 2, 5],
      "shared_point": "The specific point of disagreement that recurs across these situations."
    }}
  ]
}}
```

Return ONLY the JSON, no markdown fencing or commentary."""
