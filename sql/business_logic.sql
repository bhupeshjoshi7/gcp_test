-- =============================================================================
-- Business Logic & Transformation Queries
-- =============================================================================

-- Step 1: Upsert staging records into production table
INSERT INTO argon_data (
    id,
    name,
    category,
    amount,
    event_timestamp,
    updated_at
)
SELECT 
    TRIM(raw_id),
    TRIM(raw_name),
    COALESCE(UPPER(TRIM(raw_category)), 'GENERAL'),
    COALESCE(raw_amount, 0),
    COALESCE(raw_timestamp, CURRENT_TIMESTAMP),
    CURRENT_TIMESTAMP
FROM staging_argon_data
WHERE raw_id IS NOT NULL AND raw_id != ''
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    amount = EXCLUDED.amount,
    event_timestamp = EXCLUDED.event_timestamp,
    updated_at = CURRENT_TIMESTAMP;

-- Step 2: Example aggregation / analytics table refresh
CREATE TABLE IF NOT EXISTS daily_category_summary (
    summary_date    DATE,
    category        VARCHAR(100),
    total_records   INT,
    total_amount    NUMERIC(15, 2),
    refreshed_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (summary_date, category)
);

INSERT INTO daily_category_summary (summary_date, category, total_records, total_amount, refreshed_at)
SELECT 
    CURRENT_DATE,
    category,
    COUNT(*),
    SUM(amount),
    CURRENT_TIMESTAMP
FROM argon_data
GROUP BY category
ON CONFLICT (summary_date, category) DO UPDATE SET
    total_records = EXCLUDED.total_records,
    total_amount = EXCLUDED.total_amount,
    refreshed_at = CURRENT_TIMESTAMP;
