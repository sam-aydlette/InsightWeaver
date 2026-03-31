"""
Frame discovery and frame-aware synthesis prompts.

These prompts are used by the synthesis pipeline when interacting with topic clusters
and the narrative_frames glossary.
"""

# Used when a topic cluster has no known frames yet.
# The model identifies candidate frames from the article corpus.
FRAME_DISCOVERY_PROMPT = """You are analyzing a cluster of articles about a single topic. No narrative frames have been catalogued for this topic yet. Your task is to identify the distinct narrative layers present in (and absent from) this coverage, and map how they relate to each other.

A "frame" is a coherent way of understanding a story: what it emphasizes, what it de-emphasizes, and what assumption it takes for granted. Frames are not opinions -- they are structural features of how information is organized. There is never just one frame; multiple narrative layers coexist and may conflict.

## Instructions

Read the articles below and identify 2-4 distinct frames. For each frame:

1. **Label**: A short, neutral name (e.g., "national security frame", "consumer welfare frame", "labor market frame").
2. **Emphasizes**: What this frame foregrounds -- the facts, actors, or dynamics it treats as central.
3. **De-emphasizes**: What this frame pushes to the background or omits entirely.
4. **Assumed premise**: The unstated belief a reader must hold for this frame to feel natural.

After identifying individual frames, analyze their relationships:

5. **Fractures**: Where do the identified frames conflict? What does one frame assert that another denies or ignores? Name the specific point of disagreement.
6. **Bridges**: Is there any claim or evidence that connects conflicting frames? If no bridge exists, say so.

Then consider what frames are plausibly absent. Absent frames may be missing because of data gaps, coverage gaps, or structural absences -- the information environment makes that perspective difficult to articulate. Name the reason.

For absent frames, recommend a type of feed source that would carry that perspective. This must be a source category (e.g., "trade union publications", "municipal finance reporting", "patient advocacy press"), not a search query or URL.

## Output Format

Return valid JSON with this exact structure:

```json
{{
  "topic_summary": "One sentence describing the topic cluster.",
  "frames_present": [
    {{
      "label": "frame name",
      "emphasizes": "what this frame foregrounds",
      "de_emphasizes": "what this frame backgrounds",
      "assumed_premise": "the unstated assumption"
    }}
  ],
  "narrative_conflicts": [
    {{
      "frames_in_tension": ["frame label 1", "frame label 2"],
      "fracture_point": "the specific disagreement between these frames",
      "bridge": "what connects them, or 'none identified'"
    }}
  ],
  "frames_absent": [
    {{
      "label": "frame name",
      "emphasizes": "what this frame would foreground",
      "de_emphasizes": "what this frame would background",
      "assumed_premise": "the unstated assumption",
      "why_absent": "data gap, coverage gap, or structural absence -- and why"
    }}
  ],
  "gap_recommendations": [
    {{
      "absent_frame_label": "which absent frame this addresses",
      "feed_type": "category of source that would carry this perspective",
      "rationale": "why this source type would fill the gap"
    }}
  ]
}}
```

## Articles

{articles}"""


# Injected into the synthesis prompt when known frames exist for a topic.
# Asks the model to tag coverage against known frames and flag absences.
FRAME_AWARE_SYNTHESIS_PROMPT = """## Known Narrative Frames for "{topic_name}"

The following frames have been previously identified and validated for this topic. Use them to structure your analysis.

{frames_yaml}

### Instructions

For this topic in your synthesis:

1. **Tag each article's framing** against the known frames above. An article may use more than one frame.
2. **Report frame distribution**: Which frames are represented in today's coverage and roughly how many articles use each.
3. **Flag absent frames**: Which of the known frames have zero coverage today. List them explicitly. Do not speculate about what the absent perspective would say -- the absence itself is the signal.
4. **Note novel frames**: If an article uses a frame not listed above, describe it using the same structure (label, emphasizes, de-emphasizes, assumed premise). This is a candidate for the frame glossary.

Include the frame analysis in your output under a "frame_analysis" key for this topic."""
