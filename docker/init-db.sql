-- ============================================================================
-- FinBot Database Initialization Script
-- PostgreSQL 15+ initialization for FinBot trading platform
-- ============================================================================

-- Set timezone
SET timezone = 'UTC';

-- ============================================================================
-- Install Extensions
-- ============================================================================

-- Full-text search and similarity
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Additional useful extensions
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ============================================================================
-- Create Schema
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS finbot;

-- (Suppression des commandes globales de configuration conformément aux bonnes pratiques)
-- ============================================================================
-- Ensure Proper Permissions
-- ============================================================================

-- Grant schema usage
GRANT USAGE ON SCHEMA finbot TO finbot;

-- Grant default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA finbot 
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO finbot;

ALTER DEFAULT PRIVILEGES IN SCHEMA finbot 
    GRANT USAGE, SELECT ON SEQUENCES TO finbot;

ALTER DEFAULT PRIVILEGES IN SCHEMA finbot 
    GRANT EXECUTE ON FUNCTIONS TO finbot;

-- ============================================================================
-- Create Audit Log Table (Optional)
-- ============================================================================

CREATE TABLE IF NOT EXISTS finbot.audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name VARCHAR(255) NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    old_data JSONB,
    new_data JSONB,
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    changed_by VARCHAR(255),
    ip_address INET,
    user_agent TEXT
);

-- Index for efficient querying
CREATE INDEX IF NOT EXISTS idx_audit_log_table_time 
    ON finbot.audit_log(table_name, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_changed_at 
    ON finbot.audit_log(changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_operation 
    ON finbot.audit_log(operation, changed_at DESC);

-- ============================================================================
-- Create System Settings Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS finbot.system_settings (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert default settings
INSERT INTO finbot.system_settings (key, value, description) VALUES
    ('db_version', '"1.0.0"', 'Database schema version'),
    ('initialized_at', to_jsonb(CURRENT_TIMESTAMP), 'Database initialization timestamp'),
    ('maintenance_mode', 'false', 'System maintenance mode flag')
ON CONFLICT (key) DO NOTHING;

-- ============================================================================
-- Create Performance Monitoring View
-- ============================================================================

CREATE OR REPLACE VIEW finbot.database_stats AS
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS data_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS index_size,
    n_tup_ins AS inserts,
    n_tup_upd AS updates,
    n_tup_del AS deletes,
    n_live_tup AS live_rows,
    n_dead_tup AS dead_rows,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
WHERE schemaname = 'finbot'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- ============================================================================
-- Create Helper Functions
-- ============================================================================

-- Function to update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION finbot.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to log table changes
CREATE OR REPLACE FUNCTION finbot.log_table_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO finbot.audit_log (table_name, operation, new_data, changed_by)
        VALUES (TG_TABLE_NAME, 'INSERT', row_to_json(NEW), current_user);
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO finbot.audit_log (table_name, operation, old_data, new_data, changed_by)
        VALUES (TG_TABLE_NAME, 'UPDATE', row_to_json(OLD), row_to_json(NEW), current_user);
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO finbot.audit_log (table_name, operation, old_data, changed_by)
        VALUES (TG_TABLE_NAME, 'DELETE', row_to_json(OLD), current_user);
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Maintenance Tasks
-- ============================================================================

-- Vacuum and analyze all tables
VACUUM ANALYZE;

-- ============================================================================
-- Success Message
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '==========================================================';
    RAISE NOTICE 'FinBot Database Initialized Successfully';
    RAISE NOTICE 'Schema: finbot';
    RAISE NOTICE 'Extensions: pg_trgm, uuid-ossp, btree_gin, btree_gist';
    RAISE NOTICE 'Audit logging: ENABLED';
    RAISE NOTICE 'Performance monitoring: ENABLED';
    RAISE NOTICE '==========================================================';
END $$;
