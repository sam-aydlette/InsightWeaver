# Database Migrations for Context Engineering

## Overview
These migrations optimize the InsightWeaver database for the context engineering approach, removing agent-specific fields and adding context curation capabilities.

## Migration Strategy

### Phase 1: Add New Fields (SAFE - Run Now)
**File:** `001_optimize_for_context_engineering.py`

**What it does:**
- Adds new fields to `articles` table for context engineering
- Creates `context_snapshots` table for reproducibility
- Updates `narrative_syntheses` and `analysis_runs` tables
- **Does NOT remove any existing data**

**Run with:**
```bash
python migrations/001_optimize_for_context_engineering.py
```

### Phase 2: Cleanup Deprecated Fields (Run After Validation)
**File:** `002_cleanup_deprecated_fields.py`

**What it does:**
- Removes deprecated tables: `trend_analyses`, `predictions`
- Removes deprecated fields from `articles`
- **This is destructive - only run after validating Phase 1 works**

## Testing

```bash
# Backup database
cp data/insightweaver.db data/insightweaver.db.backup

# Run Phase 1
python migrations/001_optimize_for_context_engineering.py

# Test system
python main.py
```

See file for full documentation.
