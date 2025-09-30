-- Migration: Add narrative_syntheses table
-- Date: 2025-09-30
-- Description: Adds table for storing multi-hop narrative synthesis with temporal layering

CREATE TABLE IF NOT EXISTS narrative_syntheses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_run_id INTEGER,
    user_profile_version VARCHAR(50),
    synthesis_data JSON,
    executive_summary TEXT,
    articles_analyzed INTEGER,
    trends_analyzed INTEGER,
    temporal_scope VARCHAR(100),
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (analysis_run_id) REFERENCES analysis_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_narrative_generated_at ON narrative_syntheses(generated_at);