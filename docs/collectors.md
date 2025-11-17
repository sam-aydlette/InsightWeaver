# Data Collectors

InsightWeaver includes specialized data collectors for gathering structured data from APIs beyond RSS feeds. These collectors provide additional context for decision-making by tracking government meetings, vulnerabilities, job postings, and events.

## Available Collectors

### 1. Fairfax Calendar Collector
**Status**: ✅ Enabled (No API key required)

Tracks upcoming Fairfax County Board of Supervisors and FCPS School Board meetings.

- **Source**: Generated from typical meeting schedules
- **Refresh**: Every 24 hours
- **Data Type**: Government meetings
- **Setup**: No configuration needed

### 2. VulnCheck KEV Collector
**Status**: ⚠️ Disabled (Requires free API token)

Collects Known Exploited Vulnerabilities (KEV) from VulnCheck's comprehensive database.

- **Source**: VulnCheck Community API
- **Coverage**: ~3,700 CVEs (175% more than CISA KEV)
- **Refresh**: Every 24 hours
- **Data Type**: Cybersecurity vulnerabilities with exploit intelligence

**Setup**:
1. Create free account at https://vulncheck.com/
2. Generate API token at https://console.vulncheck.com
3. Set environment variable:
   ```bash
   export VULNCHECK_API_TOKEN="your-token-here"
   ```
4. Enable in `config/api_sources.json`:
   ```json
   "vulncheck_kev": {
     "enabled": true,
     ...
   }
   ```

### 3. Event Monitor (Bandsintown)
**Status**: ⚠️ Disabled (Requires API authentication)

Tracks concert and live music events for specified artists.

- **Source**: Bandsintown API
- **Refresh**: Every 12 hours
- **Data Type**: Concert events in DC/NoVA area

**Setup**:
1. Register for API access at https://www.bandsintown.com/api_requests/new
2. Update collector code with authentication
3. Configure artists in `config/api_sources.json`

### 4. USAJobs Collector
**Status**: ⚠️ Disabled (Requires API key)

Monitors federal job postings matching specified keywords and locations.

- **Source**: USAJobs API
- **Refresh**: Every 24 hours
- **Data Type**: Federal job postings

**Setup**:
1. Request API key at https://developer.usajobs.gov/APIRequest/Index
2. Set environment variables:
   ```bash
   export USAJOBS_API_KEY="your-key-here"
   export USAJOBS_EMAIL="your-email@example.com"
   ```
3. Configure keywords and locations in `config/api_sources.json`
4. Enable the collector:
   ```json
   "usajobs": {
     "enabled": true,
     ...
   }
   ```

## Usage

### Run All Collectors
```bash
# Run collectors that are due for refresh
python main.py --collect

# Force all enabled collectors to run
python main.py --collect --force
```

### Run Specific Collector
```bash
python main.py --collect --name vulncheck_kev
python main.py --collect --name fairfax_calendar
```

### Check Collector Status
```bash
python main.py --collector-status
```

### Full Pipeline (includes collectors)
```bash
# Collectors run automatically in full pipeline
python main.py
```

## Configuration

Edit `config/api_sources.json` to:
- Enable/disable collectors
- Adjust refresh frequencies
- Configure collector-specific settings
- Add custom keywords, artists, or search terms

Example:
```json
{
  "collectors": {
    "vulncheck_kev": {
      "enabled": true,
      "class": "VulnCheckKEVCollector",
      "refresh_hours": 24,
      "description": "Known Exploited Vulnerabilities"
    }
  }
}
```

## Data Storage

All collected data is stored in the database:
- **api_data_sources**: Collector configuration and status
- **api_data_points**: Individual data items collected

Query collected data:
```python
from src.database.models import APIDataPoint
from src.database.connection import get_db

with get_db() as db:
    # Get recent vulnerabilities
    vulns = db.query(APIDataPoint).filter(
        APIDataPoint.data_type == 'vulnerability_kev'
    ).order_by(APIDataPoint.event_date.desc()).limit(10).all()
```

## Adding New Collectors

To add a new collector:

1. Create collector class in `src/collectors/`:
   ```python
   from .base_collector import BaseCollector

   class MyCollector(BaseCollector):
       def fetch_data(self):
           # Implement data fetching
           pass

       def parse_item(self, raw_item):
           # Implement parsing
           pass
   ```

2. Register in `src/collectors/manager.py`:
   ```python
   elif class_name == 'MyCollector':
       return MyCollector()
   ```

3. Add to `config/api_sources.json`:
   ```json
   "my_collector": {
     "enabled": true,
     "class": "MyCollector",
     "refresh_hours": 24
   }
   ```

## Relevance Scoring

Collectors automatically score items based on:
- Recency (newer = higher score)
- User decision context (matches = higher score)
- Data-specific factors (e.g., exploits available, ransomware campaigns)

Scores range from 0.0 to 1.0 and determine priority in Claude's context window.

## Token Allocation

Collectors respect token budget allocations defined in config:
```json
"token_allocation": {
  "calendar_events": 5000,
  "vulnerabilities": 10000,
  "job_postings": 7000,
  "total_api_data": 25000
}
```

This ensures balanced representation in narrative synthesis.
