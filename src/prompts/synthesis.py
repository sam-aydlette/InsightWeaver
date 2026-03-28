"""
Clustering and situation synthesis prompts.

Pass 1: CLUSTERING_PROMPT groups articles into topic clusters.
Pass 2: SITUATION_SYNTHESIS_PROMPT produces examined narratives for each cluster.
THIN_COVERAGE_PROMPT produces one-line summaries for clusters with insufficient coverage.
"""

# Pass 1: Group articles into topic clusters.
# Input: article titles + first paragraphs.
# Output: clusters with article IDs and one-sentence descriptions.
# No significance judgment -- just topical grouping.
CLUSTERING_PROMPT = """You are grouping news articles into topic clusters. A cluster is a set of articles about related topics where understanding one informs understanding the others. Articles do not need to be about the exact same event -- they belong together if they are part of the same broader story, involve the same actors, or affect the same systems.

## Instructions

Read the article summaries below. Group them into **5-15 clusters**. Each article belongs to exactly one cluster. Prefer fewer, larger clusters over many single-article clusters. Two articles about different aspects of the same policy area, the same institution, or the same conflict belong in the same cluster.

Only create a single-article cluster when an article is genuinely unrelated to everything else.

Do not judge significance. Do not rank or prioritize. Just group by relatedness.

## Output Format

Return valid JSON with this exact structure:

```json
{{
  "clusters": [
    {{
      "title": "One-sentence description of the situation",
      "article_ids": [1, 3, 7],
      "keywords": ["keyword1", "keyword2", "keyword3"]
    }}
  ]
}}
```

## Articles

{articles}"""


# Pass 2: Situation synthesis for clusters with 3+ articles.
# Produces examined narratives: actors, interests, power dynamics,
# coverage frame, causal structure, information gaps.
# Epistemic labels on every claim. No confidence scores.
SITUATION_SYNTHESIS_PROMPT = """You are analyzing a set of articles about a single situation. Your task is to produce an examined narrative: who are the actors, what are their interests, who benefits, who is harmed, how the coverage frames the story, what causal structure determines the outcome, and what information is missing.

{analysis_rules}

## Citation Discipline

For every factual claim, include inline citations using this format: "claim^[1,3]" referencing article numbers from the list below. Only cite articles that directly support the claim. Do not cite your own analytical conclusions.

## Article Reference List
{article_ref_list}

## Output Format

Return valid JSON with this exact structure:

```json
{{
  "title": "One-sentence description of the situation",
  "narrative": "2-4 paragraph examined narrative of the situation. Name actors and their interests. State who benefits, who is harmed, who decides. Every factual claim carries an epistemic label and citation. Uncertainty is expressed as what is missing, not as hedging.",
  "actors": [
    {{
      "name": "Named person or organization",
      "role": "What they are doing in this situation",
      "interests": "What they stand to gain or lose",
      "epistemic_status": "reported_fact | single_source | consensus | speculation"
    }}
  ],
  "power_dynamics": {{
    "who_benefits": "Named, with explanation^[citations]",
    "who_is_harmed": "Named, with explanation^[citations]",
    "who_decides": "Named, with explanation^[citations]"
  }},
  "coverage_frame": {{
    "dominant_frame": "What the coverage emphasizes and what it takes for granted",
    "assumed_premise": "What the reader must already believe for this framing to feel natural",
    "de_emphasized": "What the coverage pushes to background or omits"
  }},
  "causal_structure": {{
    "forces": "What determines the outcome regardless of how the coverage frames it^[citations]",
    "constraints": "What limits possible outcomes^[citations]",
    "dependencies": "What this situation depends on that may not be visible in today's coverage"
  }},
  "information_gaps": [
    {{
      "what_is_missing": "Specific information or perspective not present in today's coverage",
      "why_it_matters": "How this gap affects the reliability or completeness of the analysis",
      "feed_recommendation": "Type of source that would fill this gap (source category, not URL)"
    }}
  ],
  "article_citations": [1, 3, 7]
}}
```

## Requirements

- Every factual claim must carry an epistemic status label: reported fact (multiple independent sources), single-source claim (name the source), consensus view (state whose consensus), or speculation (say so plainly).
- When the evidence is ambiguous about who benefits or who is harmed, say so. Do not pick a side or retreat into "there are many perspectives."
- The causal structure section should identify forces and constraints that matter whether or not the articles mention them. If you can infer a dependency from the evidence, state it with its epistemic basis. If you cannot, flag it as a gap.
- Do not recommend actions. Map implications: "if X is true, then Y follows" -- not "you should do Z."
- Do not use emotional language or urgency framing unless directly quoting a source.

Return ONLY valid JSON, no markdown formatting or additional text."""


# Thin coverage summary for clusters with 1-2 articles.
# Minimal output: title, source, one-line description.
THIN_COVERAGE_PROMPT = """Summarize each of these article clusters in one sentence. These clusters have insufficient coverage for full analysis (1-2 articles each).

For each cluster, return:
- title: one-sentence description of the topic
- article_count: number of articles
- sources: list of source names
- note: one sentence on why this might matter despite thin coverage, or "Insufficient coverage for assessment"

## Clusters

{clusters}

## Output Format

Return valid JSON:

```json
{{
  "thin_coverage": [
    {{
      "title": "Topic description",
      "article_count": 1,
      "sources": ["Source Name"],
      "note": "One sentence."
    }}
  ]
}}
```

Return ONLY valid JSON."""
