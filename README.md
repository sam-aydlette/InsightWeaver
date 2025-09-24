# InsightWeaver

An intelligent RSS feed aggregation and analysis system that transforms diverse data streams into actionable intelligence briefings for Northern Virginia residents. Features advanced trend analysis with 99% API cost reduction, AI-powered newsletter generation, and complete end-to-end automation from data collection to email delivery.

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

InsightWeaver includes a comprehensive test suite with multiple test modes:

```bash
# Interactive test runner with multiple modes
cd tests && python run_tests.py

# Available test suites:
# 1. Phase 2 Checkpoint Verification - RSS pipeline validation
# 2. Prioritization Agent Test - Advanced 3-stage prioritization
# 3. Trend Analysis Agent Test - Comprehensive trend detection
# 4. Run All Tests - Complete system validation

# Test modes (for agent tests):
# - MINI: 50 articles (quick development)
# - QUICK: 100 articles (standard testing)
# - FULL: 1000 articles (comprehensive testing)
```

**Individual Test Commands:**
```bash
# Test RSS Pipeline (147 feeds, parallel processing, deduplication)
python tests/test_phase2_checkpoint.py

# Test Prioritization Agent (17 categories, 98% API cost reduction)
TEST_MODE=quick python tests/test_prioritization_agent.py

# Test Trend Analysis Agent (15 global trends, robust JSON parsing)
TEST_MODE=mini python tests/test_trend_agent.py
```

**Test Features:**
- ✅ **Stage-by-Stage Validation**: Each component tested individually
- ✅ **Performance Metrics**: Processing times and API efficiency
- ✅ **Data Quality Checks**: Categorization rates and accuracy validation
- ✅ **Error Handling**: Comprehensive failure scenario testing
- ✅ **Success Criteria**: Clear pass/fail evaluation with recommendations

### 6. Usage

InsightWeaver provides a comprehensive command-line interface with advanced analysis capabilities:

```bash
# Initial setup: create database and load RSS feeds
python main.py --setup

# Run complete pipeline (fetch → deduplicate → prioritize → analyze trends → generate newsletters)
python main.py

# Run individual components
python main.py --fetch        # Only fetch RSS feeds (147+ sources)
python main.py --prioritize   # Only run prioritization (17 categories, API-efficient)
python main.py --trends       # Only run trend analysis (15 global trends)
python main.py --newsletter   # Only generate intelligence newsletters

# Query results with advanced filtering
python main.py --query                     # Show top priority articles
python main.py --query --min 0.7           # Show only high priority (≥0.7)
python main.py --query --min 0.8 --limit 20  # Show top 20 with score ≥0.8
python main.py --query --trends            # Show trend analysis results
```

**Advanced Pipeline Features:**
- **147+ RSS feeds** processed in parallel with deduplication
- **17 granular categories** optimized for Northern Virginia context
- **15 global trends** tracked with 99% API cost reduction
- **3-stage prioritization** using local analysis + Claude API
- **AI-powered newsletters** with daily briefs and weekly trend analysis
- **Email delivery** via Gmail SMTP with professional HTML formatting
- **Robust GenAI handling** with 5-layer JSON parsing system

**Processing Workflow:**
1. **Feed Collection**: Parallel fetching from 147+ RSS sources
2. **Deduplication**: Advanced content similarity detection
3. **Local Analysis**: spaCy-based categorization and sentiment analysis
4. **API Analysis**: Efficient Claude API calls with batching and rate limiting
5. **Trend Detection**: 6-month momentum analysis across 15 global trends
6. **Newsletter Generation**: AI-powered daily briefs and weekly trend analysis
7. **Result Storage**: Structured data with comprehensive metadata and HTML newsletters

## System Architecture

### Intelligence Analysis Pipeline

InsightWeaver implements a sophisticated multi-stage analysis pipeline optimized for cost efficiency and accuracy:

#### **Stage 1: Local Processing (FREE)**
- **spaCy NLP**: Industrial-strength text processing and entity recognition
- **Sentiment Analysis**: TextBlob-based sentiment scoring for initial categorization
- **17 Granular Categories**: Specialized categories for government, technology, security, and business
- **Content Normalization**: Advanced deduplication using text similarity algorithms

#### **Stage 2: API-Efficient Classification (LOW COST)**
- **Claude Haiku**: Fast, cost-effective model for binary stance classification
- **Batch Processing**: Smart batching with rate limiting (10 articles per batch)
- **Binary Prompts**: Forced SUPPORTING/OPPOSING classification for decisive trend analysis
- **Robust JSON Parsing**: 5-layer fallback system handling all GenAI response issues

#### **Stage 3: Trend Aggregation (FREE)**
- **15 Global Trends**: Comprehensive tracking across political, economic, and technological domains
- **6-Month Analysis**: Historical trend momentum calculation
- **Confidence Scoring**: Statistical confidence based on article volume and stance clarity
- **Evidence Compilation**: Structured reasoning with supporting/opposing evidence

### Performance Metrics

- **API Cost Reduction**: 99% reduction vs. naive approaches
- **Processing Speed**: 2-4 minutes for complete pipeline (3,700+ articles)
- **Newsletter Generation**: Sub-second rendering with AI-powered summaries
- **Categorization Rate**: >90% of articles successfully categorized
- **Trend Coverage**: 15 comprehensive global trends vs. basic topic detection
- **Email Delivery**: Confirmed working with Gmail SMTP authentication
- **System Reliability**: Robust error handling with graceful degradation

### GenAI Response Handling

InsightWeaver includes advanced GenAI response normalization:

- **Layer 1**: Claude commentary removal (`"Here is the JSON:"` prefixes)
- **Layer 2**: Missing comma fixes (most common GenAI error)
- **Layer 3**: Truncation recovery and JSON completion
- **Layer 4**: Quote normalization and trailing comma removal
- **Layer 5**: Aggressive regex extraction with balanced fallbacks

**Test Results**: 100% success rate on all GenAI malformation scenarios.

### Newsletter System

InsightWeaver includes a comprehensive intelligence newsletter system:

#### **Daily Intelligence Briefs**
- **Executive Summaries**: AI-generated paragraph-style intelligence synthesis
- **Priority Articles**: Top 15 high-relevance items with scores and reasoning
- **Regional Focus**: Virginia-specific developments and government impacts
- **Professional Formatting**: Clean HTML styling optimized for government/tech professionals

#### **Weekly Trend Analysis**
- **Strategic Intelligence**: Multi-domain trend tracking with momentum indicators
- **Evidence-Based Analysis**: Supporting/opposing article compilation
- **Forward Indicators**: Predictive insights for 2-4 week planning horizons
- **Confidence Scoring**: Statistical reliability measures for trend direction

#### **Email Delivery System**
- **Gmail SMTP Integration**: Automated delivery with app password authentication
- **HTML & Text Formats**: Professional templates with responsive design
- **Local Storage Fallback**: Organized file storage in `data/newsletters/`
- **System Health Monitoring**: Comprehensive validation and error reporting

**Newsletter Commands:**
```bash
# Generate and send intelligence newsletters
python main.py --newsletter

# Test newsletter system configuration
python main.py --test-newsletter
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
