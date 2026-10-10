-- =============================================================================
-- Database Schema for Argon Data Pipeline
-- Target Database: PostgreSQL (Google Cloud SQL)
-- =============================================================================

-- 1. STAGING TABLE: Temporary landing area for raw CSV ingest
-- Truncated before each daily batch load
CREATE TABLE IF NOT EXISTS staging_argon_data (
    raw_id          VARCHAR(255),
    raw_name        VARCHAR(255),
    raw_category    VARCHAR(100),
    raw_amount      NUMERIC(15, 2),
    raw_timestamp   TIMESTAMP,
    loaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. PRODUCTION / ANALYTICS TABLE: Persistent, curated data
CREATE TABLE IF NOT EXISTS argon_data (
    id              VARCHAR(255) PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    category        VARCHAR(100),
    amount          NUMERIC(15, 2) DEFAULT 0.00,
    event_timestamp TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_argon_category ON argon_data(category);
CREATE INDEX IF NOT EXISTS idx_argon_timestamp ON argon_data(event_timestamp);
