# InsightWeaver System Description

## Overview
InsightWeaver is an intelligent RSS feed aggregation and analysis system that transforms diverse data streams into actionable intelligence briefings for Northern Virginia residents. The system combines multi-perspective news analysis with advanced natural language processing to deliver personalized, location-aware intelligence reports.

## Mission Statement
Transform RSS feed data streams into coherent, actionable narratives that inform decision-making across two integrated perspectives: Northern Virginia citizen (combining family life and civic engagement with multi-level geographic context) and professional cybersecurity advisory work in the U.S. public sector.

## System Architecture
Backend: Python with FastAPI
Database: PostgreSQL with SQLAlchemy ORM
Task Queue: Celery + Redis
Dashboard: React with recharts/D3.js
Email: Gmail App 

## Key Features
The core elements are:
1. Pulling from 100+ RSS feeds daily
2. Normalizing and storing those articles in a database
3. An agent performing prioritization based on Claude API prompt and the articles from the last 48 hours and storing that metadata in the database
4. An agent performing trend analysis based on Claude API prompt and the articles from the last 6 months and storing that metadata in the database
5. An agent performing predictions for what will happen in the next 2-4 weeks based on the information gleaned from the prioritization and trend analysis
6. Reporting on the results of steps 1-5. This reporting should be a real-time dashboard and a point-in-time email report.

### Multi-Perspective Analysis
- **Geographic Layering**: Local → State → National → Global
- **Temporal Analysis**: Real-time → Short-term → Long-term
- **Domain Coverage**: Government, Security, Economic, Social
- **Perspective Integration**: Western and Non-Western viewpoints

### Natural Language Processing
- **spaCy Integration**: Industrial-strength NLP
- **Entity Recognition**: People, Organizations, Locations, Events
- **Trend Extraction**: Statistical and linguistic pattern detection
- **Sentiment Analysis**: Positive/negative trend identification
- **Relationship Mapping**: Entity co-occurrence patterns

### Resilience & Reliability

#### Multi-Layer Resilience
1. **Feed Level**: Individual feed failures don't stop collection
2. **Agent Level**: Agents can run in degraded mode
3. **Orchestration Level**: System continues with partial results
4. **Output Level**: Generates best-effort reports with available data

#### Error Recovery Patterns
- **Retry Logic**: Transient failures trigger retries
- **Circuit Breakers**: Prevent cascade failures
- **Fallback Values**: Use defaults when data unavailable
- **Error Aggregation**: Collect and report all errors at end

### Location Intelligence
- **Multi-level Hierarchy**: Precinct → County → State → National
- **Proximity Analysis**: Distance-based relevance scoring
- **Administrative Context**: Understanding of government boundaries
- **User Perspective**: Tailored to Northern Virginia residents

### Monitoring & Observability
- **Comprehensive Logging**: All components use structured logging
- **Health Metrics**: Real-time agent and system health
- **Execution History**: Tracks all analysis runs
- **Performance Metrics**: Monitors processing times
- **Data Quality Metrics**: Tracks source reliability

## Configuration

### Environment Variables
- `DATABASE_PATH`: SQLite database location
- `SMTP_SERVER`: Email server for report delivery
- `SMTP_PORT`: Email server port
- `EMAIL_USERNAME`: SMTP authentication username
- `EMAIL_PASSWORD`: SMTP authentication password
- `RECIPIENT_EMAIL`: Report recipient address
- `ANTHROPIC_API_KEY`: API key for Claude integration

### Settings Management
- Centralized configuration in TODO
- Environment variable loading via python-dotenv
- RSS feed configuration with 170+ sources
- Customizable analysis parameters

## Operational Modes

### Standard Operation
- Scheduled daily execution via cron
- Full pipeline execution
- Email delivery of reports
- Comprehensive logging

### Dry-Run Mode
- Full analysis without email delivery
- Report saved to local file
- Useful for testing and development
- Preserves production database

### Debug Mode
- Verbose logging output
- Performance profiling enabled
- Detailed error traces
- Component-level debugging

## Performance Characteristics

### Resource Requirements
- **CPU**: Moderate (spaCy NLP processing)
- **Memory**: ~2GB for full analysis
- **Disk**: ~500MB for database and models
- **Network**: Bandwidth for 170+ RSS feeds

### Processing Times
- **Feed Collection**: 2-5 minutes (parallel fetching)
- **Entity Extraction**: 1-2 minutes (depending on volume)
- **Agent Analysis**: 1-3 minutes (parallel execution)
- **Report Generation**: <30 seconds
- **Total Pipeline**: 5-10 minutes typical

### Scalability
- Horizontal scaling via multiple instances
- Database connection pooling ready
- Async/await architecture for concurrency
- Cache-friendly design patterns

## Security Considerations

### Data Protection
- No storage of credentials in code
- Environment variables for sensitive data
- HTTPS-only feed fetching
- Secure SMTP for email delivery

### Input Validation
- RSS feed content sanitization
- HTML tag stripping
- SQL injection prevention
- Entity extraction boundaries

### Access Control
- File system permissions for database
- SMTP authentication required
- No public API endpoints
- Local execution only

## Maintenance & Extension

### Adding New RSS Feeds
1. Edit
2. Add feed to appropriate category
3. Test feed parsing compatibility
4. No code changes required

### Adding New Analysis Agents
TODO: Add content here

### Customizing Reports
1. Modify templates
2. Update CSS styles for formatting
3. Add new sections as needed
4. Maintain responsive design

## System Limitations

### Known Constraints
- English language content only
- RSS/Atom feed formats required
- 10-minute processing time for large volumes
- Email size limits for reports
- Single-region focus (Northern Virginia)

### Planned Improvements

## Version History

### Current Version (September 2025)
- 170+ RSS feed sources

### Previous Versions
- v1.0: Basic RSS aggregation


*This document is maintained alongside code changes and represents the current system state.*