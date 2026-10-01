-- State of the background job that extracts entities from a source using its approved schema.
ALTER TABLE graph_sources ADD COLUMN IF NOT EXISTS extract_status TEXT NOT NULL DEFAULT 'idle';
ALTER TABLE graph_sources ADD COLUMN IF NOT EXISTS extract_progress JSONB;
ALTER TABLE graph_sources ADD COLUMN IF NOT EXISTS extract_error TEXT;
ALTER TABLE graph_sources ADD COLUMN IF NOT EXISTS entity_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE graph_sources ADD COLUMN IF NOT EXISTS relation_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE graph_sources ADD COLUMN IF NOT EXISTS last_extracted_at TIMESTAMPTZ;
ALTER TABLE graph_sources DROP CONSTRAINT IF EXISTS graph_sources_extract_status_check;
ALTER TABLE graph_sources ADD CONSTRAINT graph_sources_extract_status_check
    CHECK (extract_status IN ('idle', 'running', 'completed', 'failed'));
