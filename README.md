# InsightWeaver

**A tool for building warranted, inspectable understanding from RSS feeds.**

---

## The Problem

The dominant narratives in daily news coverage preclude alternatives without the reader knowing it. This is not a conspiracy -- it is a structural feature of how information is produced and distributed. Every article frames its subject: it foregrounds certain facts, backgrounds others, and takes certain premises for granted. When your information sources all use the same frame, you are not exposed to the alternatives. You cannot evaluate what you cannot see.

The traditional response to this problem -- aggregating more sources -- does not solve it. More articles using the same frame is not more perspective. It is more volume.

Information overload is a real problem, but it is a symptom. The deeper problem is that the reader has no way to see the editorial structure of their information diet: which frames are present, which are absent, and what assumptions are embedded in the coverage they consume.

---

## Principles

### 1. Insight over information

The output should help you understand what story is being told and what it assumes -- not just what was reported. A list of headlines is not a briefing. A briefing that tells you what happened without surfacing the frame through which "what happened" was constructed has done half the job.

### 2. Warranted trust over projected confidence

Transparency about sourcing, epistemic status, and uncertainty is the mechanism. Every claim carries a label: reported fact, single-source claim, consensus view, or speculation. When the label is ambiguous, the system defaults to the weaker one. False confidence is a violation even when the underlying claim is accurate. A synthesis that honestly maps what it does not know is more useful than one that papers over holes.

### 3. Frame visibility over false balance

Balance does not mean equal treatment of all positions. It means making the frames present in the corpus visible, naming their assumptions, and explicitly flagging what is absent. Bothsidesism is itself a framing choice -- one that treats the number of perspectives presented as a proxy for fairness while obscuring the structural question of which perspectives were available in the first place. InsightWeaver surfaces frames as structural features of coverage: what a frame emphasizes, what it de-emphasizes, and what it takes for granted. It does not evaluate which frame is "correct."

### 4. Epistemic autonomy as the goal

The system equips the user to reason. It does not hand them conclusions. Synthesis is not the same as manipulation. When information is insufficient to draw a conclusion, the system says what is missing and stops. It does not fill gaps with plausible-sounding inferences. The user decides what the information means.

### 5. Honest self-awareness about the tool's own narrative

InsightWeaver makes editorial choices: which feeds to include, how to cluster topics, which frame candidates to surface for validation. Those choices shape the output. They are surfaced to the user, not hidden behind a veneer of objectivity. RSS feed selection is explicitly the user's responsibility. Frame validation requires human review. The system's own assumptions are part of what it reports on.

---

## What InsightWeaver Does

InsightWeaver is a CLI tool that runs on your computer. It fetches RSS feeds you configure, synthesizes them into daily briefings using Claude (Anthropic's AI), and makes the narrative structure of the coverage visible.

The output is organized around **situations**, not headlines. A situation is a mini-narrative with examined characters: who are the actors, what are their interests, what are they doing, who benefits, who is harmed, who decides. The actors and interests emerge from sourced evidence, not from the tool's editorial preference. When the evidence is ambiguous about who benefits, the tool says so rather than picking a side or retreating into "there are many perspectives."

**Epistemic labeling.** Every claim carries a status: reported fact, single-source claim, consensus view, or speculation. Uncertainty is expressed as a structural feature of the information -- what is missing and why it matters -- not hidden behind hedging language.

**Frame analysis.** For each situation, the system identifies the dominant frame in today's coverage, names its assumptions, and flags which frames are absent. It also identifies the causal structure that determines outcomes regardless of how the coverage frames it -- the forces, constraints, and dependencies that matter whether or not the articles mention them.

**An emergent frame glossary** built from your actual corpus over time. When a topic cluster has no known frames, the system discovers candidates. You validate them interactively: accept, reject, or edit. Nothing enters the glossary without your review.

**Gap detection as a feed curation signal.** When a frame is consistently absent from your feeds, the system logs the gap and recommends a type of source that would carry the missing perspective. It does not attempt to fill the gap itself. It does not search the web. Source control stays with the user.

**Transparency about the tool's own choices.** Every briefing tells you which feeds contributed, what was filtered, how articles were clustered into situations, and which frames are known versus newly discovered. The system's editorial decisions are part of what it reports on.

---

## How It Works

InsightWeaver uses context engineering: it curates optimal context for Claude and bakes analytical guardrails into the prompt rather than checking outputs after the fact. The pipeline uses a two-pass architecture so that frame analysis is independent of narrative construction.

1. **Collection**: RSS feeds are fetched in parallel from sources you configure
2. **Deduplication**: Duplicate and near-duplicate articles are removed
3. **Context curation**: Articles are selected based on your profile (location, profession, interests)
4. **Pass 1 -- Clustering and frame discovery**: Articles are grouped into situations. For each situation, the system checks for known frames or discovers new ones. This pass is auditable: you can inspect which articles landed in which cluster.
5. **Pass 2 -- Situation synthesis**: Claude analyzes each situation with known frames injected, producing examined narratives with actors, interests, power dynamics, causal structure, frame analysis, and information gaps. ANALYSIS_RULES.md is injected into every prompt, enforcing epistemic labeling and structural honesty.
6. **Delivery**: Reports are saved locally and optionally emailed

RSS is the only input source.

---

## Who This Is For

People who want to understand the structure of the news they consume, not just its content. People who want to know who benefits, who is harmed, and what the coverage makes hard to see. People who are willing to curate their own sources and validate the system's frame discoveries. People who prefer tools that are transparent about their own editorial choices.

---

## Getting Started

```bash
git clone https://github.com/YOUR_USERNAME/InsightWeaver.git
cd InsightWeaver
python -m venv venv && source venv/bin/activate
pip install -e .
cp .env.example .env  # Add your ANTHROPIC_API_KEY
insightweaver brief   # Generate your first briefing
```

See [GETTING_STARTED.md](GETTING_STARTED.md) for detailed setup instructions.

---

## Requirements

- Python 3.10+
- Anthropic API key
- Internet connection
- ~100MB disk space

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

See [LICENSE](LICENSE) for details.
