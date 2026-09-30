-- Preserve existing sources as unassigned until their creator chooses a project.
ALTER TABLE graph_sources ADD COLUMN IF NOT EXISTS project_id TEXT
    REFERENCES projects(id) ON DELETE SET NULL;
ALTER TABLE graph_sources DROP CONSTRAINT IF EXISTS graph_sources_tenant_id_path_key;
CREATE UNIQUE INDEX IF NOT EXISTS graph_sources_project_path_key
    ON graph_sources (tenant_id, project_id, path);
