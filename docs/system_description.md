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
3. A sophisticated prioritization agent using local sentiment analysis and Claude API to identify the most important articles for Northern Virginia government/tech professionals
4. An efficient trend analysis agent using a 3-stage workflow (local categorization → Haiku stance detection → 6-month aggregation) to track 15 global trends with minimal API costs
5. An agent performing predictions for what will happen in the next 2-4 weeks based on the information gleaned from the prioritization and trend analysis
6. Reporting on the results of steps 1-5. This reporting should be a real-time dashboard and a point-in-time email report.

### Multi-Perspective Analysis
- **Geographic Layering**: Local → State → National → Global
- **Temporal Analysis**: Real-time → Short-term → Long-term
- **Domain Coverage**: Government, Security, Economic, Social
- **Perspective Integration**: Western and Non-Western viewpoints

### Intelligent Prioritization System

The InsightWeaver prioritization agent uses a sophisticated three-stage analysis to identify the most relevant articles for Northern Virginia government/technology professionals:

#### Stage 1: Local Sentiment Analysis (Free)
- **Granular Categorization**: Articles automatically sorted into 17 specialized categories
- **Keyword Matching**: Advanced pattern matching for government, technology, and regional terms
- **Local Priority Scoring**: Articles scored based on Northern Virginia relevance
- **Cost Optimization**: 100% local processing eliminates API costs for initial filtering

#### Stage 2: Category Competition (Low Cost)
- **Haiku Analysis**: Fast, cost-effective Claude Haiku model ranks top 3 articles per category
- **Competitive Selection**: Only the highest-quality articles from each category advance
- **Batch Processing**: Efficient API usage with smart batching and rate limiting
- **Quality Filtering**: Ensures only substantive articles reach expensive analysis

#### Stage 3: Final Selection (Minimal Cost)
- **Sonnet Analysis**: Premium Claude Sonnet model selects ultimate priority article
- **Cross-Category Comparison**: Final winner chosen from category champions
- **Expert Analysis**: Detailed reasoning and impact assessment for top selection
- **Cost Control**: Single expensive API call for final decision

#### Granular Categories (17 total)
**Government & Policy (4 categories)**
- `federal_policy`: Congress, White House, federal decisions
- `state_local_policy`: Virginia, Maryland, DC local politics
- `defense_security`: Pentagon, defense contractors, military news
- `regulatory`: FCC, FDA, EPA regulatory changes

**Technology & Innovation (4 categories)**
- `ai_ml`: AI, machine learning, ChatGPT, Claude developments
- `cybersecurity`: Hacks, breaches, CISA, security threats
- `gov_tech`: Government modernization, FedRAMP, GSA initiatives
- `tech_infrastructure`: Cloud, AWS, data centers, networks

**Crisis & Threats (4 categories)**
- `security_threat`: Foreign interference, APTs, terrorism
- `economic_disruption`: Recession, market crashes, inflation
- `system_failure`: Outages, technical failures, downtime
- `natural_disaster`: Hurricanes, emergencies, FEMA responses

**Business & Economy (4 categories)**
- `nova_economy`: Northern Virginia specific business news
- `federal_contracting`: Government contracts, procurement, RFPs
- `investment_funding`: VC funding, acquisitions, IPOs
- `market_changes`: Industry trends, disruption, competition

**General Information (1 category)**
- `background_info`: General news and background information

#### Performance Metrics
- **API Cost Reduction**: ~98% reduction compared to naive approach
- **Processing Speed**: 18 seconds for 3,700+ articles
- **Coverage**: 93% of articles successfully categorized
- **Precision**: 17 granular categories vs. 5 generic categories
- **Relevance**: Optimized for Northern Virginia government/tech context

### Efficient Trend Analysis System

The InsightWeaver trend analysis agent uses a highly efficient three-stage workflow to track 15 global trends with minimal Claude API costs:

#### Stage 1: Local Trend Categorization (Free)
- **spaCy-Based Classification**: Articles automatically categorized into 15 global trend groups using comprehensive keyword dictionaries
- **Zero API Cost**: 100% local processing for initial trend identification
- **Comprehensive Coverage**: Tracks major world trends across politics, technology, economics, and society
- **Filtering Logic**: Only trends with sufficient article coverage (3+ articles) proceed to expensive analysis

#### Stage 2: Haiku Pro/Against Classification (Low Cost)
- **Stance Detection**: Fast Claude Haiku model determines if each article supports or opposes the trend direction
- **Targeted Analysis**: Only relevant articles analyzed per trend, reducing API calls
- **Batch Processing**: Efficient batching with rate limiting for cost control
- **Confidence Scoring**: Each stance classification includes confidence and reasoning

#### Stage 3: 6-Month Trend Direction Calculation (Free)
- **Aggregated Analysis**: Combines pro/against counts to determine overall trend momentum
- **Direction Scoring**: Calculates GAINING/LOSING/NEUTRAL based on article stance ratios
- **Strength Assessment**: Determines weak/moderate/strong based on article volume and clarity
- **Evidence Compilation**: Samples supporting and opposing evidence for trend justification

#### Global Trends Tracked (15 total)
**Political & Governance**
- `privatization_vs_regulation`: Market solutions vs. state intervention
- `geopolitical_fragmentation_vs_cooperation`: Regional blocs vs. multilateral institutions
- `security_vs_privacy`: Surveillance expansion vs. privacy rights
- `social_cohesion_vs_polarization`: Unity vs. political division

**Economic & Financial**
- `economic_growth_vs_stagnation`: GDP growth vs. recession risk
- `debt_expansion_vs_fiscal_restraint`: Spending vs. austerity
- `formal_vs_informal_economy`: Traditional employment vs. gig work
- `climate_action_vs_economic_priorities`: Environmental protection vs. economic growth

**Technology & Society**
- `digital_centralization_vs_decentralization`: Tech monopolies vs. distributed systems
- `automation_vs_human_labor`: AI/robotics vs. human employment
- `scientific_openness_vs_strategic_competition`: Research collaboration vs. tech rivalry

**Demographic & Social**
- `demographic_transition`: Aging populations vs. youth bulges
- `urbanization_vs_distributed_living`: Megacities vs. remote work dispersion
- `cultural_homogenization_vs_localization`: Global culture vs. local identity

**Infrastructure & Environment**
- `energy_transition`: Renewables vs. fossil fuels

#### Performance Metrics
- **API Cost Reduction**: ~99% reduction compared to naive approach
- **Processing Speed**: 30-60 seconds for trend analysis of all articles
- **Trend Coverage**: 15 comprehensive global trends vs. basic topic detection
- **Efficiency**: Only trends with 3+ relevant articles analyzed with expensive API calls
- **Accuracy**: Stance classification with confidence scoring and evidence compilation

### Natural Language Processing
- **spaCy Integration**: Industrial-strength NLP for text processing
- **TextBlob Sentiment**: Lightweight sentiment analysis for categorization
- **Entity Recognition**: People, Organizations, Locations, Events
- **Trend Extraction**: Statistical and linguistic pattern detection
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
- **Feed Collection**: 1-2 minutes (147 feeds, parallel fetching)
- **Deduplication**: 10-30 seconds (staged processing optimization)
- **Sentiment Analysis**: 2-5 seconds (local spaCy/TextBlob processing)
- **Prioritization Agent**: 15-25 seconds (three-stage Claude API analysis)
- **Report Generation**: <30 seconds
- **Total Pipeline**: 2-4 minutes typical

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
1. Extend `BaseAgent` class in `src/agents/base_agent.py`
2. Implement `analyze_articles()` method
3. Add agent to pipeline orchestrator
4. Update prompts and metadata schemas as needed

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
- **147+ RSS feed sources** across government, technology, and news categories
- **Three-stage prioritization agent** with local sentiment analysis and Claude API integration
- **17 granular categories** optimized for Northern Virginia government/tech professionals
- **Staged deduplication processing** for enhanced performance
- **~98% API cost reduction** through intelligent local pre-filtering
- **2-4 minute total pipeline** processing 3,700+ articles efficiently

### Previous Versions
- v2.0: Added Claude API prioritization with basic 5-category system
- v1.0: Basic RSS aggregation and storage


*This document is maintained alongside code changes and represents the current system state.*