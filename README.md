# InsightWeaver

**Transform RSS feed data streams into coherent, actionable narratives through context-engineered intelligence synthesis.**

## Mission

InsightWeaver processes diverse RSS feeds and generates personalized narrative intelligence briefs using Claude's analytical capabilities. The system focuses on **context engineering** rather than custom analysis engines, following Anthropic's guidance for building effective AI agents.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Add ANTHROPIC_API_KEY to .env

# Initialize database
python main.py --setup

# Run full pipeline
python main.py
```

## Architecture: Context Engineering

Instead of building pattern detectors and inference engines, InsightWeaver curates optimal context windows for Claude to analyze natively.

**Core Principle:** Trust Claude's capabilities, engineer the context.

**Performance:** <10 minutes end-to-end, ~50k-65k tokens per synthesis

See `PERFORMANCE_AND_MAINTENANCE.md` for detailed benchmarks and operations guide.

## Documentation

- `PHASE_1_COMPLETE.md` - Latest implementation (token budget, perspectives, examples)
- `PERFORMANCE_AND_MAINTENANCE.md` - Operations, metrics, maintenance guide
- `REFACTORING_SUMMARY.md` - Architecture evolution from agents to context engineering
- `DATABASE_OPTIMIZATION.md` - Schema design for context engineering
- `PROJECT_ALIGNMENT.md` - Architecture alignment analysis
- `MIGRATION_GUIDE.md` - Database migration instructions

## Philosophy

> "The best code is no code. The best analysis engine is Claude with perfect context."

We trust Claude for analysis. We focus on context curation.

---

**Built with:** Python 3.13+, Claude Sonnet 4, SQLite
