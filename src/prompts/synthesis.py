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
SITUATION_SYNTHESIS_PROMPT = """You are analyzing a set of articles about a single situation. The reader should finish your analysis understanding five things:

1. What is actually happening (not just what is being reported)
2. Who is doing what to whom, and why
3. What the coverage makes easy to see and what it makes hard to see
4. Where the story could go, and what would have to be true for each path
5. What they would need to know to make a good decision about this

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
  "narrative": "2-4 paragraph examined narrative. Identify the operative narrative layers -- the distinct stories being told about what is happening. Map where they conflict: what does one narrative assert that another denies or ignores? Name actors and their interests. State who benefits, who is harmed, who decides. When actors operate under conflicting narratives, name the discrepancy. Every factual claim carries an epistemic label and citation. End with the unresolved question that determines where this goes.",
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
    "narrative_layers": "The distinct narratives operative in the coverage -- not just one dominant frame but the layers that coexist and their relationship to each other",
    "fractures": "Where these narratives conflict -- the specific point of disagreement, not just the fact that disagreement exists",
    "bridges": "What connects conflicting narratives, if anything. If no bridge exists, say so.",
    "structural_absences": "What is hard to see -- perspectives that are absent not because of missing data but because the information environment makes them difficult to articulate. Name the structural reason."
  }},
  "where_this_goes": {{
    "branching_paths": "The conditional futures: if X then Y, if A then B. Which narrative layer predicts which outcome.",
    "unresolved_question": "The single question whose answer determines which path the situation takes. This is often the most valuable part of the analysis.",
    "what_to_watch": "The specific observable event or data point that would signal which path is unfolding"
  }},
  "information_gaps": [
    {{
      "what_is_missing": "Specific information or perspective not present",
      "why_it_matters": "How this gap affects the reader's ability to understand the situation or make a decision",
      "why_missing": "Is this a data gap, a coverage gap, or a structural absence?",
      "feed_recommendation": "Type of source that would fill this gap (source category, not URL)"
    }}
  ],
  "article_citations": [1, 3, 7]
}}
```

## Requirements

- Every factual claim must carry an epistemic status label: reported fact, single-source claim, consensus view, or speculation.
- Identify multiple narrative layers, not just one dominant frame. Map their conflicts and any bridges between them.
- When the evidence is ambiguous, say so. Do not pick a side or retreat into "there are many perspectives."
- The where_this_goes section maps conditional futures, not predictions. "If X, then Y" -- not "Y will happen."
- Do not recommend actions. Map implications so the reader can reason for themselves.
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
