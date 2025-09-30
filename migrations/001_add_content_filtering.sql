-- Migration: Add content filtering columns to articles table
-- Date: 2025-09-30
-- Description: Adds filtered flag and filter_reason to support Phase 5A content filtering

-- Add filtered column (default FALSE for existing articles)
ALTER TABLE articles ADD COLUMN filtered BOOLEAN DEFAULT FALSE;

-- Add filter_reason column
ALTER TABLE articles ADD COLUMN filter_reason VARCHAR(200);

-- Create index for efficient filtering queries
CREATE INDEX IF NOT EXISTS idx_articles_filtered ON articles(filtered);

-- Update statistics
-- SELECT COUNT(*) as total_articles,
--        SUM(CASE WHEN filtered THEN 1 ELSE 0 END) as filtered_articles
-- FROM articles;