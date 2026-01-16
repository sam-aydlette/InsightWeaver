# InsightWeaver

**Transform information overload into actionable intelligence.**

---

## The Problem

We live in an era of unprecedented information abundance. Hundreds of news sources publish thousands of articles daily. Social media amplifies every story. The result is not better-informed citizens, but overwhelmed ones.

The traditional response has been aggregation: collect everything, present it all, let users sort through it. But aggregation without synthesis just moves the problem. You still have to read dozens of headlines, assess relevance, identify patterns, and decide what matters to you.

Meanwhile, consequential local news often goes unnoticed. A zoning decision that affects your neighborhood. A vulnerability in software your company uses. A policy change that impacts your industry. These stories exist, but they're buried under the noise.

---

## The Solution

InsightWeaver is a personal intelligence analyst that runs on your computer. It monitors news sources, identifies what's relevant to your specific situation, and synthesizes it into actionable briefings.

Instead of presenting you with a feed to scroll, InsightWeaver gives you:

- **A daily briefing** that tells you what happened and why it matters to you
- **Forecasts** that identify trends and predict what's coming
- **Verified answers** to questions you ask, with fact-checking and bias analysis

The key difference is **synthesis over aggregation**. InsightWeaver doesn't just collect information; it processes it through the lens of your location, profession, and interests to extract what's actually relevant.

---

## Why This Matters

### Information Asymmetry

Institutions have intelligence analysts. Governments have briefing officers. Corporations have research departments. These entities receive synthesized, relevant information tailored to their needs.

Individuals get a firehose.

InsightWeaver democratizes intelligence synthesis. The same capability that helps institutions make informed decisions becomes available to anyone.

### Local Relevance

National news dominates attention, but local news often has more direct impact on daily life. A city council vote, a regional economic trend, a state policy change, these affect you more than most national headlines.

InsightWeaver prioritizes geographic relevance. It connects global trends to local implications and surfaces local stories that national outlets ignore.

### Trust and Verification

AI can generate plausible-sounding text that's factually wrong. InsightWeaver addresses this with built-in trust verification:

- Claims are checked against authoritative sources
- Framing is analyzed for bias
- Tone is evaluated for appropriateness
- Outputs that fail verification are regenerated or flagged

You get AI's analytical power with safeguards against its weaknesses.

### Privacy by Design

Your reading habits, questions, and interests are valuable data. Most news platforms monetize this information.

InsightWeaver runs entirely on your computer. Your data never leaves your machine except for API calls to generate analysis. There's no account, no tracking, no advertising. You own your information.

---

## How It Works

InsightWeaver uses a **context engineering** approach rather than custom machine learning models. Instead of training specialized algorithms, it curates optimal context for Claude (Anthropic's AI) to analyze natively.

1. **Collection**: RSS feeds from hundreds of sources are fetched in parallel
2. **Deduplication**: Duplicate and near-duplicate articles are removed
3. **Context Curation**: Relevant articles are selected based on your profile
4. **Synthesis**: Claude analyzes the curated content and generates insights
5. **Verification**: Outputs are checked for factual accuracy and bias
6. **Delivery**: Reports are saved locally and optionally emailed

The entire pipeline runs in under 10 minutes and costs approximately $0.10-0.50 per briefing in API usage.

---

## Who This Is For

InsightWeaver is designed for people who:

- Want to stay informed without spending hours reading news
- Care about local issues that national media ignores
- Need to track specific topics relevant to their profession
- Value verified information over viral content
- Prefer privacy-respecting tools that run locally

It's particularly valuable for:

- **Professionals** tracking industry developments
- **Citizens** following local government and civic issues
- **Security practitioners** monitoring vulnerability disclosures
- **Anyone** who wants a personalized alternative to algorithmic feeds

---

## Getting Started

**New to InsightWeaver?** See the **[Getting Started Guide](GETTING_STARTED.md)** for step-by-step installation and usage instructions.

**Technical users** can jump straight to installation:

```bash
git clone https://github.com/YOUR_USERNAME/InsightWeaver.git
cd InsightWeaver
python -m venv venv && source venv/bin/activate
pip install -e .
cp .env.example .env  # Add your ANTHROPIC_API_KEY
insightweaver setup   # Run the setup wizard
insightweaver start   # Launch the web interface
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](GETTING_STARTED.md) | Installation and first-time setup |
| [Configuration Guide](docs/configuration_guide.md) | Customizing your profile and preferences |
| [CLI Reference](docs/cli_reference.md) | Command-line interface documentation |
| [Scheduling Setup](deployment/SCHEDULING_SETUP.md) | Automating daily briefings |
| [Architecture](docs/architecture.md) | Technical design and context engineering approach |

---

## Requirements

- Python 3.10+
- Anthropic API key
- Internet connection
- ~100MB disk space

---

## Contributing

InsightWeaver is open source. Contributions are welcome.

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

See [LICENSE](LICENSE) for details.

---

## Acknowledgments

InsightWeaver is built on the insight that AI's strength lies in analysis and synthesis, not information retrieval. By combining high-quality RSS sources with Claude's analytical capabilities and rigorous trust verification, we can transform the overwhelming flow of information into something genuinely useful.

The goal is not just aggregation, but understanding. Not just information, but intelligence.
