-- Initialize pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create helper function for setting current tenant in session
CREATE OR REPLACE FUNCTION set_tenant_id(tenant_uuid TEXT)
RETURNS void AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', tenant_uuid, false);
END;
$$ LANGUAGE plpgsql;
