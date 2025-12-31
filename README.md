# InsightWeaver

**Transform RSS feed data streams into coherent, actionable narratives through context-engineered intelligence synthesis.**

## Mission

InsightWeaver processes diverse RSS feeds and generates personalized narrative intelligence briefs using Claude's analytical capabilities. The system focuses on **context engineering** rather than custom analysis engines, following best practices for building effective AI agents.

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd InsightWeaver

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install InsightWeaver
pip install -e .

# Set up environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Initial Setup

```bash
# Initialize database and load RSS feeds
insightweaver brief setup

# Verify installation
insightweaver brief health
```

### First Run

```bash
# Run full pipeline (fetch feeds, analyze, generate report)
insightweaver brief

# Or run specific components
insightweaver brief fetch          # Only fetch RSS feeds
insightweaver brief report          # Generate intelligence report
```

## CLI Commands

InsightWeaver provides a multi-command CLI interface:

### Main Commands

```bash
insightweaver --help               # Show all available commands
insightweaver --version            # Show version information
```

### Brief Command (Intelligence Reports)

```bash
# Full pipeline (default)
insightweaver brief                              # Fetch, analyze, generate report
insightweaver brief --hours 48                   # Last 48 hours
insightweaver brief --email                      # Send via email
insightweaver brief --no-verify                  # Skip trust verification

# Topic filters
insightweaver brief --cybersecurity (-cs)        # Cybersecurity only
insightweaver brief --ai (-ai)                   # AI/ML only

# Scope filters
insightweaver brief --local (-l)                 # Local news only
insightweaver brief --state (-s)                 # State news only
insightweaver brief --national (-n)              # National news only
insightweaver brief --global (-g)                # Global news only

# Combined filters
insightweaver brief -cs -n                       # National cybersecurity
insightweaver brief --hours 48 -l                # 48-hour local news
insightweaver brief -cs -g --email               # Global cybersecurity via email

# Setup and initialization
insightweaver brief setup                        # Initialize database and load feeds

# Data collection
insightweaver brief fetch                        # Fetch RSS feeds only
insightweaver brief collect                      # Run API data collectors
insightweaver brief collect --force              # Force all collectors
insightweaver brief collect --name usajobs       # Run specific collector

# Analysis and reporting
insightweaver brief report                       # Last 24 hours (default)
insightweaver brief report --hours 48            # Last 48 hours
insightweaver brief report --hours 168           # Last week
insightweaver brief report --start-date 2025-01-01 --end-date 2025-01-07

# System management
insightweaver brief health                       # System health status
insightweaver brief metrics                      # Performance metrics (7d)
insightweaver brief metrics --days 30            # 30-day metrics

# Data management
insightweaver brief cleanup                      # Clean old data
insightweaver brief cleanup --dry-run            # Preview cleanup
insightweaver brief retention-status             # Show retention status
insightweaver brief collector-status             # Show collector status

# Utilities
insightweaver brief query                        # Query priority articles
insightweaver brief query --min 0.7 --limit 20   # Custom filters
insightweaver brief test-newsletter              # Test email system
```

### Forecast Command (Long-term Trend Forecasting)

```bash
# Generate multi-horizon forecasts (default: executive mode)
insightweaver forecast                           # All horizons (6mo, 1yr, 3yr, 5yr)
insightweaver forecast --full                    # Full detailed analysis

# Specific time horizons
insightweaver forecast --horizon 6mo             # 6-month forecast only
insightweaver forecast --horizon 1yr             # 1-year forecast only
insightweaver forecast --horizon 3yr             # 3-year forecast only
insightweaver forecast --horizon 5yr             # 5-year forecast only

# Scenario generation
insightweaver forecast --scenarios 3             # Generate 3 detailed scenarios
insightweaver forecast --horizon 1yr --scenarios 5    # 1-year with 5 scenarios

# Topic filters (same as brief)
insightweaver forecast -cs                       # Cybersecurity trends
insightweaver forecast -ai                       # AI/ML trends
insightweaver forecast -cs --full --scenarios 3  # Detailed cybersecurity forecast

# Scope filters
insightweaver forecast -l                        # Local trends
insightweaver forecast -n                        # National trends
insightweaver forecast -g                        # Global trends

# Trust verification
insightweaver forecast --no-verify               # Skip trust verification

# Combined examples
insightweaver forecast --horizon 1yr -cs --full --scenarios 3
    # 1-year detailed cybersecurity forecast with 3 scenarios
insightweaver forecast -ai -g --scenarios 5
    # Global AI trends with 5 scenarios (executive mode)
```

### Trust Command (Verified AI Responses)

```bash
# Get trust-verified AI responses with fact-checking and bias analysis
insightweaver trust "Who is the current president of the United States?"
insightweaver trust "What is the unemployment rate?"
insightweaver trust "Who is the CEO of Apple?"

# The trust command provides:
# - Fact verification against authoritative sources (56 sources)
# - Bias and framing analysis
# - Tone and intimacy detection
# - Temporal validation for time-sensitive facts
```

## Trust Verification

InsightWeaver includes built-in trust verification for all AI-generated outputs. By default, brief and forecast commands automatically verify their outputs for trustworthiness.

### What Gets Verified

**Fact Verification**: Claims are extracted and verified against 56 authoritative sources:
- Government websites (US, global leaders, economic indicators)
- International organizations (UN, NATO, WHO, IMF, World Bank)
- Corporate leadership pages (Apple, Microsoft, Amazon, Google)
- Academic institutions (Harvard, etc.)
- Wikipedia (fallback for comprehensive country coverage)

**Bias Analysis**: Identifies framing issues, assumptions, omissions, and loaded language

**Tone Detection**: Ensures professional, appropriate communication without inappropriate intimacy

**Temporal Validation**: Time-sensitive facts are verified against current authoritative sources using intelligent Claude-based source selection and dynamic URL construction

### Verification Output

Each verification shows:
- **Fact Summary**: Counts of verified/unverifiable/contradicted claims
- **Top Bias Issues**: 2-3 most significant framing/assumptions/omissions
- **Tone Rating**: Overall tone assessment (PROFESSIONAL, CASUAL, etc.)
- **Actionability**: YES/NO/CAUTION with reasoning

### Performance Impact

Trust verification adds approximately 30-60 seconds per verification (3 API calls: fact extraction, bias analysis, tone detection).

### Opt-Out

Use `--no-verify` flag to skip trust verification:
```bash
insightweaver brief --no-verify
insightweaver forecast --no-verify
```

## Configuration

### Required: API Keys

Edit `.env` file:

```bash
# Required: Claude API access
ANTHROPIC_API_KEY=your_anthropic_key_here

# Required: Email settings (for reports)
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
FROM_EMAIL=your_email@gmail.com
RECIPIENT_EMAIL=your_email@gmail.com
```

### User Profile

Edit `config/user_profile.json` to customize:
- Geographic location and interests
- Professional domains
- Civic interests
- Content preferences (what to exclude/include)

See `docs/configuration_guide.md` for detailed guidance.

### RSS Feeds

RSS feeds are organized in `config/feeds/` by domain:
- `technology/` - Tech news feeds
- `cybersecurity/` - Security feeds
- `local/` - Local news feeds
- `civic/` - Government and civic feeds

Add/remove feeds by editing the JSON files.

### API Data Collectors

Configure external data sources in `config/api_sources.json`:
- Government calendars
- Vulnerability databases
- Job postings
- Events

See `docs/collectors.md` for setup instructions.

## Architecture: Context Engineering

Instead of building pattern detectors and inference engines, InsightWeaver curates optimal context windows for Claude to analyze natively.

**Core Principle:** Leverage the LLM's power, engineer the human context and trustworthiness.

**Performance:** <10 minutes end-to-end, ~50k-65k tokens per synthesis

### How It Works

1. **Feed Collection**: Parallel RSS fetching with rate limiting
2. **Deduplication**: Remove duplicate articles
3. **Content Filtering**: Filter based on user preferences
4. **Context Curation**: Build optimal context window for Claude
5. **Synthesis**: Claude generates narrative intelligence brief
6. **Report Generation**: HTML email with actionable insights

### Context Components

- **User Profile**: Location, profession, interests
- **Decision Context**: Active decisions and timelines
- **Recent Articles**: Filtered and prioritized content
- **Semantic Memory**: Persistent facts across sessions
- **Domain Knowledge**: Pre-loaded context modules

## Scheduling

Set up automated daily reports:

```bash
# See deployment/SCHEDULING_SETUP.md for detailed instructions

# Option 1: systemd (Linux)
# Copy service files and enable timer

# Option 2: cron
# Add to crontab: 0 8 * * * insightweaver brief

# Option 3: Manual
insightweaver brief  # Run whenever you want
```

## Documentation

### User Guides
- `docs/configuration_guide.md` - How to configure user profile and decisions
- `docs/collectors.md` - Setting up API data collectors
- `deployment/SCHEDULING_SETUP.md` - Automated daily reports

### Technical Documentation
- `PHASE_1_COMPLETE.md` - Latest implementation (token budget, perspectives, examples)
- `PERFORMANCE_AND_MAINTENANCE.md` - Operations, metrics, maintenance guide
- `REFACTORING_SUMMARY.md` - Architecture evolution from agents to context engineering
- `DATABASE_OPTIMIZATION.md` - Schema design for context engineering
- `PROJECT_ALIGNMENT.md` - Architecture alignment analysis
- `MIGRATION_GUIDE.md` - Database migration instructions

### Design Principles

1. **Simple Over Complex**: Avoid over-engineering
2. **Focus Over Features**: Do one thing exceptionally well

## Examples

### Daily Intelligence Brief

```bash
# Morning routine: check what's important
insightweaver brief
```

**Output:**
- Executive summary (bottom line)
- Trends by geographic scope (local → global)
- Priority events with impact levels
- Predictions and scenarios (2-4 week horizon)
- Civic engagement opportunities
- Trust verification (facts, bias, tone, actionability)

### Custom Reports

```bash
# Weekly review (last 7 days)
insightweaver brief report --hours 168

# Month-end review (specific dates)
insightweaver brief report --start-date 2025-01-01 --end-date 2025-01-31

# National cybersecurity news
insightweaver brief -cs -n

# Skip trust verification for faster output
insightweaver brief --no-verify
```

### Long-term Forecasting

```bash
# Generate multi-horizon forecasts (executive briefing)
insightweaver forecast

# 1-year detailed forecast with scenarios
insightweaver forecast --horizon 1yr --full --scenarios 3

# Cybersecurity trends forecast
insightweaver forecast -cs --scenarios 5
```

**Output:**
- Trend analysis for each horizon (6mo, 1yr, 3yr, 5yr)
- Detailed scenarios (if requested)
- Executive briefing or full detailed analysis
- Trust verification for predictions and reasoning

### Trust-Verified Queries

```bash
# Get verified factual information
insightweaver trust "Who is the current president of the United States?"

# Economic data with verification
insightweaver trust "What is the current unemployment rate?"

# Corporate leadership verification
insightweaver trust "Who is the CEO of Microsoft?"
```

**Output:**
- AI response with current, verified information
- Fact verification status (verified/contradicted/unverifiable)
- Bias analysis
- Tone rating
- Compact trust summary

### System Monitoring

```bash
# Check system health
insightweaver brief health

# View performance metrics
insightweaver brief metrics --days 30

# Clean up old data
insightweaver brief cleanup --dry-run  # Preview first
insightweaver brief cleanup             # Execute
```

## Troubleshooting

### No articles being fetched
```bash
# Check feed health
insightweaver brief health

# Try manual fetch
insightweaver brief fetch
```

### Email not sending
```bash
# Test email configuration
insightweaver brief test-newsletter

# Check .env settings:
# EMAIL_USERNAME, EMAIL_PASSWORD, FROM_EMAIL, RECIPIENT_EMAIL
```

### Database issues
```bash
# Reinitialize database (WARNING: destroys existing data)
insightweaver brief setup
```

### API errors
```bash
# Verify API key in .env
echo $ANTHROPIC_API_KEY

# Check quota/credits at console.anthropic.com
```

## Development

### Running from source (without install)
```bash
python main.py brief --help
python main.py brief health
```

### Testing
```bash
pytest                              # Run all tests
pytest tests/test_collectors.py    # Specific test file
```

### Logs

Logs are written to:
- `data/logs/scheduled_report_YYYYMMDD.log` - Scheduled runs
- Console output - Manual runs

## Requirements

- **Python**: 3.8 or higher
- **Claude API**: Anthropic API key (paid tier recommended for daily use)
- **Email**: Gmail or SMTP-compatible email account
- **Disk**: ~100MB for database and logs
- **Internet**: Required for RSS fetching and Claude API

## Built With

- **Python 3.13+**
- **Claude Sonnet 4** - AI analysis
- **SQLite** - Local database
- **Click** - CLI framework
- **Feedparser** - RSS parsing
- **HTTPX** - Async HTTP client
- **BeautifulSoup4** - HTML parsing

---

**For more information, see the documentation in the `docs/` directory.**
