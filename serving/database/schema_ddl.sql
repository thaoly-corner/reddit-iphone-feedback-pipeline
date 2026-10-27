-- ============================================================================
-- 1. KIMBALL STAR SCHEMA (DENORMALIZED 1-HOP DIMENSIONS FOR FAST SERVING)
-- ============================================================================

CREATE TABLE IF NOT EXISTS dim_date (
    date_key INT PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    day_name VARCHAR(15) NOT NULL,
    day_of_week INT NOT NULL,
    day_of_month INT NOT NULL,
    week_of_year INT NOT NULL,
    month INT NOT NULL,
    quarter INT NOT NULL,
    year INT NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_iphone_model (
    model_id SERIAL PRIMARY KEY,
    model_name VARCHAR(60) NOT NULL UNIQUE,
    series VARCHAR(30) NOT NULL,
    form_factor VARCHAR(25) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_os_version (
    os_id SERIAL PRIMARY KEY,
    version_name VARCHAR(40) NOT NULL UNIQUE,
    major_release VARCHAR(20) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_issue_category (
    issue_id SERIAL PRIMARY KEY,
    feature_name VARCHAR(60) NOT NULL,
    issue_name VARCHAR(100) NOT NULL,
    severity_tier VARCHAR(20) DEFAULT 'MEDIUM',
    CONSTRAINT uq_feature_issue UNIQUE (feature_name, issue_name)
);

CREATE TABLE IF NOT EXISTS fact_feedback_summary (
    summary_id BIGSERIAL PRIMARY KEY,
    date_key INT NOT NULL REFERENCES dim_date(date_key) ON DELETE RESTRICT,
    model_id INT NOT NULL REFERENCES dim_iphone_model(model_id) ON DELETE RESTRICT,
    os_id INT NOT NULL REFERENCES dim_os_version(os_id) ON DELETE RESTRICT,
    issue_id INT NOT NULL REFERENCES dim_issue_category(issue_id) ON DELETE RESTRICT,
    total_posts INT DEFAULT 0 CHECK (total_posts >= 0),
    total_comments INT DEFAULT 0 CHECK (total_comments >= 0),
    positive_count INT DEFAULT 0 CHECK (positive_count >= 0),
    neutral_count INT DEFAULT 0 CHECK (neutral_count >= 0),
    negative_count INT DEFAULT 0 CHECK (negative_count >= 0),
    avg_sentiment_score NUMERIC(6, 4),
    avg_engagement_score NUMERIC(10, 2),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_fact_grain UNIQUE (date_key, model_id, os_id, issue_id)
);

-- ============================================================================
-- 2. GALAXY SCHEMA / FACT CONSTELLATION (MULTIPLE FACTS SHARING CONFORMED DIMS)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fact_emerging_issues (
    alert_id BIGSERIAL PRIMARY KEY,
    date_key INT NOT NULL REFERENCES dim_date(date_key) ON DELETE RESTRICT,
    model_id INT NOT NULL REFERENCES dim_iphone_model(model_id) ON DELETE RESTRICT,
    issue_id INT NOT NULL REFERENCES dim_issue_category(issue_id) ON DELETE RESTRICT,
    current_3d_avg NUMERIC(10, 2) NOT NULL,
    baseline_14d_avg NUMERIC(10, 2) NOT NULL,
    growth_rate_pct NUMERIC(8, 2) NOT NULL,
    z_score NUMERIC(6, 2) NOT NULL,
    is_anomaly BOOLEAN NOT NULL,
    CONSTRAINT uq_emerging_grain UNIQUE (date_key, model_id, issue_id)
);

CREATE TABLE IF NOT EXISTS fact_high_impact_complaints (
    post_id VARCHAR(50) PRIMARY KEY,
    date_key INT NOT NULL REFERENCES dim_date(date_key) ON DELETE RESTRICT,
    model_id INT NOT NULL REFERENCES dim_iphone_model(model_id) ON DELETE RESTRICT,
    os_id INT NOT NULL REFERENCES dim_os_version(os_id) ON DELETE RESTRICT,
    issue_id INT NOT NULL REFERENCES dim_issue_category(issue_id) ON DELETE RESTRICT,
    title TEXT NOT NULL,
    permalink TEXT NOT NULL,
    reddit_score INT NOT NULL,
    num_comments INT NOT NULL,
    engagement_score INT NOT NULL,
    sentiment_score NUMERIC(6, 4) NOT NULL
);

-- ============================================================================
-- 3. SNOWFLAKE SCHEMA (3NF NORMALIZED HIERARCHICAL DIMENSIONS FOR COMPARISON)
-- ============================================================================

CREATE TABLE IF NOT EXISTS snow_dim_model_series (
    series_id SERIAL PRIMARY KEY,
    series_name VARCHAR(30) NOT NULL UNIQUE,
    release_generation INT
);

CREATE TABLE IF NOT EXISTS snow_dim_iphone_model (
    model_id SERIAL PRIMARY KEY,
    model_name VARCHAR(60) NOT NULL UNIQUE,
    series_id INT NOT NULL REFERENCES snow_dim_model_series(series_id),
    form_factor VARCHAR(25) NOT NULL
);

CREATE TABLE IF NOT EXISTS snow_dim_feature_group (
    feature_id SERIAL PRIMARY KEY,
    feature_name VARCHAR(60) NOT NULL UNIQUE,
    hardware_or_software VARCHAR(20) NOT NULL
);

CREATE TABLE IF NOT EXISTS snow_dim_issue_category (
    issue_id SERIAL PRIMARY KEY,
    feature_id INT NOT NULL REFERENCES snow_dim_feature_group(feature_id),
    issue_name VARCHAR(100) NOT NULL,
    severity_tier VARCHAR(20) DEFAULT 'MEDIUM',
    CONSTRAINT uq_snow_feature_issue UNIQUE (feature_id, issue_name)
);

CREATE TABLE IF NOT EXISTS snow_fact_feedback_summary (
    summary_id BIGSERIAL PRIMARY KEY,
    date_key INT NOT NULL REFERENCES dim_date(date_key),
    model_id INT NOT NULL REFERENCES snow_dim_iphone_model(model_id),
    os_id INT NOT NULL REFERENCES dim_os_version(os_id),
    issue_id INT NOT NULL REFERENCES snow_dim_issue_category(issue_id),
    total_posts INT DEFAULT 0,
    total_comments INT DEFAULT 0,
    negative_count INT DEFAULT 0,
    avg_sentiment_score NUMERIC(6, 4),
    avg_engagement_score NUMERIC(10, 2),
    CONSTRAINT uq_snow_fact_grain UNIQUE (date_key, model_id, os_id, issue_id)
);

-- ============================================================================
-- Compatibility table already populated by the existing OBT loader.
CREATE TABLE IF NOT EXISTS obt_feedback_wide (
    date_key INT NOT NULL,
    full_date DATE NOT NULL,
    model_name TEXT NOT NULL,
    series_name TEXT NOT NULL,
    os_version TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    issue_name TEXT NOT NULL,
    total_posts INT,
    total_comments INT,
    negative_count INT,
    avg_sentiment_score DOUBLE PRECISION,
    avg_engagement_score DOUBLE PRECISION,
    UNIQUE (date_key, model_name, os_version, feature_name, issue_name)
);

-- 4. INDEXING STRATEGY (COMPOSITE & PARTIAL B-TREE INDEXES)
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_ffs_date_model ON fact_feedback_summary(date_key, model_id);
CREATE INDEX IF NOT EXISTS idx_ffs_issue ON fact_feedback_summary(issue_id);
CREATE INDEX IF NOT EXISTS idx_fei_anomaly ON fact_emerging_issues(date_key, growth_rate_pct DESC) WHERE is_anomaly = TRUE;
CREATE INDEX IF NOT EXISTS idx_fhic_engagement ON fact_high_impact_complaints(engagement_score DESC);
CREATE INDEX IF NOT EXISTS idx_snow_ffs_date_model ON snow_fact_feedback_summary(date_key, model_id);
