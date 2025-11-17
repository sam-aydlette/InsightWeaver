# Enhanced Data Collection System

## Overview

InsightWeaver now implements a multi-tier data collection strategy that goes beyond RSS feeds to gather fresh, time-sensitive intelligence from APIs, structured data sources, and monitored web pages.

## Architecture

### Five-Tier Data Collection Strategy

#### Tier 1: Time-Sensitive Intelligence (Highest Priority)
**Focus:** Data Claude CANNOT know (post-cutoff + real-time)

**Implemented:**
- **Fairfax County Calendar** - Board meetings, FCPS meetings, planning commission
- **Concert/Event Monitoring** - Bandsintown API for live music events
- **Job Market Monitoring** - USAJobs API for federal positions

**Status:** ✅ Phase 1 Complete

#### Tier 2: Monitored Page Changes (High Priority)
**Focus:** Track specific pages for YOUR decisions

**Planned:**
- Website change detection system
- Monitor policy pages, job boards, event announcements
- Diff detection and alert generation

**Status:** 🔄 Phase 2 Pending

#### Tier 3: Enhanced RSS Filtering (Medium Priority)
**Focus:** Filter RSS to keep only POST-cutoff relevance

**Planned:**
- Recency scoring (<7 days = high priority)
- Novelty detection (Claude Haiku check)
- Decision relevance scoring
- Source quality tiers

**Status:** 🔄 Phase 3 Pending

#### Tier 4: Structured Data Sources (Medium Priority)
**Focus:** APIs that provide context, not articles

**Planned:**
- Economic data: BLS unemployment, Fed rates
- Housing data: Census ACS for NoVA
- School data: Virginia DOE performance
- Transportation: WMATA, VDOT APIs

**Status:** 🔄 Phase 4 Pending

#### Tier 5: Supplemental Context (Low Priority)
**Focus:** Background context for analysis (static, refreshed rarely)

**Planned:**
- Baseline datasets (housing prices, salary trends, enrollment)
- Stored as JSON, refreshed monthly

**Status:** 🔄 Phase 5 Pending

## Database Schema

### New Tables

#### `api_data_sources`
Configuration for API-based data sources

```sql
CREATE TABLE api_data_sources (
    id INTEGER PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    source_type VARCHAR(50) NOT NULL,  -- 'calendar', 'job_market', 'events', etc.
    endpoint_url VARCHAR(500),
    api_key_required BOOLEAN DEFAULT FALSE,
    refresh_frequency_hours INTEGER DEFAULT 24,
    is_active BOOLEAN DEFAULT TRUE,
    last_fetched DATETIME,
    last_error TEXT,
    error_count INTEGER DEFAULT 0,
    metadata JSON,
    created_at DATETIME,
    updated_at DATETIME
);
```

#### `api_data_points`
Individual data points collected from APIs

```sql
CREATE TABLE api_data_points (
    id INTEGER PRIMARY KEY,
    source_id INTEGER REFERENCES api_data_sources(id),
    data_type VARCHAR(50) NOT NULL,  -- 'event', 'job_posting', 'metric'
    external_id VARCHAR(200),
    title VARCHAR(500),
    description TEXT,
    data_payload JSON,
    event_date DATETIME,
    published_date DATETIME,
    expires_date DATETIME,
    relevance_score FLOAT,
    decision_ids JSON,  -- Which decision_context items this relates to
    last_included_in_synthesis DATETIME,
    included_count INTEGER DEFAULT 0,
    fetched_at DATETIME,
    created_at DATETIME,
    UNIQUE(source_id, external_id)
);
```

#### `monitored_pages`
Configuration for website change monitoring

```sql
CREATE TABLE monitored_pages (
    id INTEGER PRIMARY KEY,
    url VARCHAR(500) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    page_type VARCHAR(50),  -- 'policy', 'job_board', 'event_page'
    selector VARCHAR(200),  -- CSS selector for content to monitor
    check_frequency_hours INTEGER DEFAULT 24,
    decision_ids JSON,
    is_active BOOLEAN DEFAULT TRUE,
    last_checked DATETIME,
    last_changed DATETIME,
    last_content_hash VARCHAR(64),
    last_error TEXT,
    error_count INTEGER DEFAULT 0,
    metadata JSON,
    created_at DATETIME,
    updated_at DATETIME
);
```

#### `page_changes`
Detected changes from monitored pages

```sql
CREATE TABLE page_changes (
    id INTEGER PRIMARY KEY,
    monitored_page_id INTEGER REFERENCES monitored_pages(id),
    change_type VARCHAR(50),  -- 'content_added', 'content_removed', 'content_modified'
    old_content TEXT,
    new_content TEXT,
    diff_summary TEXT,
    content_hash VARCHAR(64),
    relevance_score FLOAT,
    decision_ids JSON,
    last_included_in_synthesis DATETIME,
    included_count INTEGER DEFAULT 0,
    detected_at DATETIME,
    created_at DATETIME
);
```

## Collectors

### Base Collector

`src/collectors/base_collector.py`

Abstract base class for all collectors with:
- HTTP client management
- Source tracking (get_or_create_source)
- Abstract methods: `fetch_data()`, `parse_item()`
- Relevance scoring against decision context
- Error handling and retry logic

### Implemented Collectors

#### 1. FairfaxCalendarCollector
**File:** `src/collectors/fairfax_calendar.py`

**Sources:**
- Fairfax County Board of Supervisors meetings
- FCPS School Board meetings
- Planning Commission meetings

**Features:**
- Web scraping with BeautifulSoup
- Fallback generation based on typical schedules (2nd/4th Tuesday, etc.)
- Generates 3 months of upcoming meetings

**Relevance:** Connects to `education_monitoring` decision

#### 2. EventMonitorCollector
**File:** `src/collectors/event_monitor.py`

**Sources:**
- Bandsintown API (free, no auth required)
- Alternative: Songkick API (requires API key)

**Features:**
- Tracks configured artists (Kurt Vile, Death Cab for Cutie, Corrosion of Conformity)
- Filters for DC/NoVA area (Virginia, DC, Maryland)
- Includes venue, lineup, ticket links

**Relevance:** Connects to `concerts_2025_2026` decision

#### 3. JobMarketCollector
**File:** `src/collectors/job_market.py`

**Sources:**
- USAJobs API (federal positions)
- Placeholder for ClearedJobs.net scraper

**Features:**
- Keyword-based job search (cybersecurity, software engineer, etc.)
- Location filtering (Virginia, Washington DC, Maryland)
- Extracts salary range, qualifications, application deadline
- Deduplication by job ID

**Relevance:** Connects to `career_2025_q4` decision

**Requirements:**
- `USAJOBS_API_KEY` environment variable (get from https://developer.usajobs.gov/)
- `USAJOBS_EMAIL` environment variable

### Collector Manager

**File:** `src/collectors/manager.py`

Orchestrates all collectors:
- Loads configuration from `config/api_sources.json`
- Initializes collectors with decision context
- Schedules collections based on refresh frequency
- Tracks status and errors
- Provides collection summaries

**Methods:**
- `initialize_collectors(decision_context)` - Setup all enabled collectors
- `collect_all(decision_context, force)` - Run all due collectors
- `run_specific_collector(name, decision_context)` - Run one collector
- `get_collection_status()` - Get status of all sources

## Configuration

### API Sources Configuration

**File:** `config/api_sources.json`

```json
{
  "collectors": {
    "fairfax_calendar": {
      "enabled": true,
      "class": "FairfaxCalendarCollector",
      "refresh_hours": 24
    },
    "event_monitor": {
      "enabled": true,
      "class": "EventMonitorCollector",
      "refresh_hours": 12,
      "config": {
        "artists": [
          "Kurt Vile",
          "Death Cab for Cutie",
          "Corrosion of Conformity"
        ]
      }
    },
    "usajobs": {
      "enabled": true,
      "class": "JobMarketCollector",
      "refresh_hours": 24,
      "config": {
        "keywords": [
          "cybersecurity",
          "information security",
          "compliance automation"
        ],
        "location_codes": ["Virginia", "Washington DC", "Maryland"]
      },
      "requires_env": ["USAJOBS_API_KEY", "USAJOBS_EMAIL"]
    }
  }
}
```

## Testing

### Test Script

**File:** `test_collectors.py`

Run with:
```bash
python test_collectors.py
```

Tests:
- Loads decision context
- Initializes all collectors
- Runs collection with `force=True`
- Displays summary and individual results
- Shows collection status

## Usage

### Manual Collection

```python
from src.collectors.manager import CollectorManager
from src.context.module_loader import ContextModuleLoader

# Load decision context
module_loader = ContextModuleLoader()
modules = module_loader.load_all_modules()
decision_context = modules.get('core', [{}])[0]

# Run collectors
manager = CollectorManager()
summary = manager.collect_all(decision_context=decision_context, force=True)

print(f"Collected {summary['total_items_collected']} new items")
```

### Integration with Pipeline

The collector manager can be integrated into the main pipeline to run before narrative synthesis:

```python
# In main.py or pipeline orchestrator
from src.collectors.manager import CollectorManager

# Step 1: Collect API data
manager = CollectorManager()
manager.collect_all(decision_context=decision_context)

# Step 2: Fetch RSS feeds (existing)
...

# Step 3: Run narrative synthesis (existing)
...
```

## Relevance Scoring

All collectors score items against the user's `active_decisions` from `decision_context.json`:

1. Extract `relevant_signals` from each decision
2. Count keyword matches in item title + description
3. Score: `matches * 0.3` (capped at 1.0)
4. Track which `decision_ids` matched
5. Items with score > 0.5 are considered high relevance

**Example:**
- Decision: `career_2025_q4` with signal "cybersecurity job market trends"
- Job posting: "Senior Cybersecurity Engineer - DoD"
- Match: "cybersecurity" → relevance_score = 0.3, decision_ids = ["career_2025_q4"]

## Token Allocation

**Target for API Data in Claude Context:**
- Calendar events: 5,000 tokens (~10 events)
- Concert events: 3,000 tokens (~5 events)
- Job postings: 7,000 tokens (~7 detailed job descriptions)
- **Total API data: 15,000 tokens**

Combined with RSS (35k) and other context, total usage: 120-150k / 200k (60-75%)

## Next Steps

### Phase 2: Website Change Monitoring
- Implement `PageMonitor` class with `httpx` + `BeautifulSoup`
- Hash content with `hashlib.sha256`
- Generate diffs with `difflib`
- Store changes in `page_changes` table

### Phase 3: Enhanced RSS Scoring
- Create `RelevanceScorer` in `src/processors/`
- Add recency scoring (<7 days = 1.0, >30 days = 0.1)
- Implement novelty detection with Claude Haiku API
- Prioritize articles in token budget

### Phase 4: Structured Data APIs
- Economic: BLS API, Fed API
- Housing: Census ACS API
- School: Virginia DOE API
- Transportation: WMATA API

### Phase 5: Optimization
- Measure token usage per source type
- A/B test relevance scoring formulas
- Tune refresh frequencies
- Add caching for expensive API calls

## Dependencies

Add to `requirements.txt`:
```
httpx>=0.24.0        # HTTP client for API calls
beautifulsoup4>=4.12.0  # HTML parsing for web scraping
```

## Environment Variables

Required for full functionality:
```bash
# USAJobs API (get from https://developer.usajobs.gov/)
export USAJOBS_API_KEY="your_api_key_here"
export USAJOBS_EMAIL="your_email@example.com"

# Optional: Songkick API (alternative to Bandsintown)
export SONGKICK_API_KEY="your_songkick_key"
```

## Migration

To add the new tables to the database:

```python
from src.database.connection import engine
from src.database.models import Base

# Create new tables
Base.metadata.create_all(engine)
```

Or use Alembic for proper migrations (recommended for production).
