-- Entity schema agreed with the user in chat before entities are extracted from a source's documents.
ALTER TABLE graph_sources ADD COLUMN IF NOT EXISTS schema_draft JSONB;
ALTER TABLE graph_sources ADD COLUMN IF NOT EXISTS schema_status TEXT NOT NULL DEFAULT 'none';
ALTER TABLE graph_sources DROP CONSTRAINT IF EXISTS graph_sources_schema_status_check;
ALTER TABLE graph_sources ADD CONSTRAINT graph_sources_schema_status_check
    CHECK (schema_status IN ('none', 'proposed', 'approved'));
