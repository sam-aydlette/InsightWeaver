# InsightWeaver

An intelligent RSS feed aggregation and analysis system that transforms diverse data streams into actionable intelligence briefings for Northern Virginia residents.

## Local Development Setup

### Prerequisites
- Python 3.9+
- Redis (for task queue, optional for Phase 1)

### 1. Environment Setup

Create virtual environment and install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Download spaCy language model
python -m spacy download en_core_web_sm
```

### 2. Database Setup

SQLite is used by default (no installation required). The database file will be created automatically in `./data/insightweaver.db`.

### 3. Environment Configuration

Copy `.env.example` to `.env` and configure:
```bash
cp .env.example .env
```

Required environment variables (minimal for Phase 1):
```env
# Database (SQLite - optional, uses default path)
# DATABASE_URL=sqlite:///./data/insightweaver.db

# API Keys (required for analysis phases)
ANTHROPIC_API_KEY=your_anthropic_api_key

# Email (optional for Phase 1)
# SMTP_SERVER=smtp.gmail.com
# SMTP_PORT=587
# EMAIL_USERNAME=your_email@gmail.com
# EMAIL_PASSWORD=your_app_password
# FROM_EMAIL=your_email@gmail.com
# RECIPIENT_EMAIL=recipient@example.com

# Application
DEBUG=true
LOG_LEVEL=INFO
```

### 4. Initialize Database

Create database tables:
```bash
python -c "from src.database.connection import create_tables; create_tables()"
```

### 5. Test the System

Run comprehensive tests:
```bash
# Test Phase 2: RSS Pipeline (112 feeds, parallel processing, deduplication)
python tests/test_phase2_checkpoint.py

# Test Phase 3: Prioritization Agent (requires ANTHROPIC_API_KEY for full functionality)
python tests/test_prioritization_agent.py

# Interactive test runner
python tests/run_tests.py
```

### 6. Run Components

```bash
# Load RSS feeds into database
python -c "from src.feed_manager import setup_feeds; setup_feeds()"

# Fetch all RSS feeds (parallel with rate limiting)
python -c "
import asyncio
from src.rss.parallel_fetcher import fetch_all_active_feeds
asyncio.run(fetch_all_active_feeds())
"

# Run article prioritization (requires ANTHROPIC_API_KEY)
python src/cli/prioritize.py

# Query prioritized articles
sqlite3 data/insightweaver.db 'SELECT title, priority_score FROM articles WHERE priority_score IS NOT NULL ORDER BY priority_score DESC LIMIT 10;'
```

## GitHub Actions Setup

1. In your GitHub repository settings, add these secrets:
   - `SMTP_SERVER` (smtp.gmail.com)
   - `SMTP_PORT` (587)
   - `EMAIL_USERNAME` (your Gmail address)
   - `EMAIL_PASSWORD` (your Gmail App Password)
   - `FROM_EMAIL` (your Gmail address)
   - `RECIPIENT_EMAIL` (where to send briefings)
   - `ANTHROPIC_API_KEY` (authenticating to a Claude API account)

2. The workflow runs daily at 8 AM UTC automatically


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. Free to use with attribution.
