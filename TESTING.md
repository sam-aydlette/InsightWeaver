# InsightWeaver Testing Guide

## Testing Structure

InsightWeaver has two types of tests:

1. **Functional/Integration Tests** (`test_suite.py`) - End-to-end tests with real API calls
2. **Unit Tests** (`tests/`) - Component-level tests without API calls (FREE)

## Quick Start

```bash
# Most common: Quick functional test with minimal cost
python test_suite.py --quick

# Validate existing data (FREE - no API calls)
python test_suite.py --validate

# Run unit tests (FREE - no API calls)
python -m pytest tests/ -v

# Test specific component only
python test_suite.py --trends --articles 10 --trend-count 1
```

## Test Options

### Full Test Suite
```bash
python test_suite.py --all
```
**Cost:** ~$2-5 (100 articles × 5 trends + synthesis)
**Time:** ~10 minutes
**Use:** Complete validation before deployment

### Quick Test (Recommended)
```bash
python test_suite.py --quick
```
**Cost:** ~$0.10 (10 articles × 1 trend + small synthesis)
**Time:** ~2 minutes
**Use:** After code changes, regular testing

### Validate Only (FREE)
```bash
python test_suite.py --validate
```
**Cost:** $0 (database queries only)
**Time:** <5 seconds
**Use:** Check existing data integrity

### Individual Components

#### Trend Analysis
```bash
# Minimal test
python test_suite.py --trends --articles 10 --trend-count 1

# More comprehensive
python test_suite.py --trends --articles 50 --trend-count 3
```
**Tests:**
- Issue 1: No random SUPPORTING/OPPOSING assignments
- Issue 2: NEUTRAL stance is accepted
- Issue 3: Stance distribution shows real counts

#### Narrative Synthesis
```bash
# Minimal test
python test_suite.py --synthesis --articles 10

# Standard test
python test_suite.py --synthesis --articles 20
```
**Tests:**
- Synthesis generates all required fields
- Executive summary is populated
- Temporal layers are created
- Cross-domain insights exist

#### Newsletter Generation
```bash
python test_suite.py --newsletter
```
**Cost:** FREE (uses existing synthesis)
**Tests:**
- Issue 4: Newsletter fails fast with clear errors if data is incomplete
- HTML generation works
- All required sections present

### Combined Tests
```bash
# Test trends + newsletter (skip expensive synthesis)
python test_suite.py --trends --newsletter --articles 10

# Test everything except trends
python test_suite.py --validate --synthesis --newsletter --articles 20
```

## Test Results

### Success Output
```
══════════════════════════════════════════════════════════════════════
                            TEST SUMMARY
══════════════════════════════════════════════════════════════════════

Total tests: 4
Passed: 4
Warnings: 0

Passed tests:
  ✓ validate_database
  ✓ trend_analysis
  ✓ narrative_synthesis
  ✓ newsletter_generation
```

### Failure Output
Shows exactly what failed and why:
```
✗ Synthesis missing fields: ['temporal_layers']
ℹ Available fields: ['metadata', 'executive_summary']
ℹ Synthesis ID: 42, Generated: 2025-09-30 12:34:56
```

## Cost Estimates

| Test Type | Articles | Trends | API Calls | Est. Cost |
|-----------|----------|--------|-----------|-----------|
| Validate | 0 | 0 | 0 | $0.00 |
| Quick | 10 | 1 | ~12 | $0.10 |
| Trends Only (small) | 10 | 1 | ~2 | $0.02 |
| Trends Only (medium) | 50 | 3 | ~16 | $0.15 |
| Synthesis (small) | 10 | 0 | ~3 | $0.05 |
| Synthesis (medium) | 20 | 0 | ~5 | $0.10 |
| Newsletter | 0 | 0 | 0 | $0.00 |
| Full Test | 100 | 5 | ~60 | $2-5 |

## Recommended Testing Workflow

### After Code Changes
```bash
# 1. Run unit tests (FREE)
python -m pytest tests/ -v

# 2. Validate existing data (FREE)
python test_suite.py --validate

# 3. Quick functional test (~$0.10)
python test_suite.py --quick

# 4. If passing, commit changes
```

### Before Deployment
```bash
# 1. Unit tests
python -m pytest tests/ -v

# 2. Full functional validation
python test_suite.py --all
```

## Unit Tests

The `tests/` directory contains unit tests for individual components:

- **test_content_filter.py** - ContentFilter (sports/clickbait detection)
- **test_database_models.py** - Database schema and models
- **test_profile_loader.py** - UserProfile loading and validation
- **test_newsletter_templates.py** - Newsletter template rendering

Run all unit tests:
```bash
python -m pytest tests/ -v
```

Run specific test file:
```bash
python -m pytest tests/test_content_filter.py -v
```

### Investigating Specific Issues

**Issue: Random stance assignments**
```bash
python test_suite.py --trends --articles 20 --trend-count 2
# Look for: "No random assignments detected"
```

**Issue: Newsletter failing**
```bash
python test_suite.py --validate --newsletter
# Shows exact missing fields
```

**Issue: Synthesis incomplete**
```bash
python test_suite.py --synthesis --articles 15
# Shows which fields are missing
```

## Exit Codes

- `0` - All tests passed
- `1` - One or more tests failed

Use in CI/CD:
```bash
python test_suite.py --quick || exit 1
```

## Interpreting Results

### Stance Distribution = 0
**Cause:** Articles being excluded (missing from API response)
**Fix:** Check API timeout, rate limits, or prompt issues

### Synthesis Missing Fields
**Cause:** Narrative synthesis agent failing to populate data
**Fix:** Check `synthesis_data` structure in agent code

### Newsletter Fails with "NULL synthesis_data"
**Cause:** Synthesis agent crashed before saving
**Fix:** Check synthesis agent error logs

### Random Assignments Detected
**Cause:** Fallback code still present
**Fix:** Remove all `random.choice()` calls in trend_agent.py and claude_client.py