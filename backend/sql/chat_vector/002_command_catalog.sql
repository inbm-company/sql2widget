-- Commands are the retrieval keys; plans are the associated execution context.
-- Connection IDs refer to the service DB and cannot have cross-database FKs.
CREATE TABLE IF NOT EXISTS command_catalog (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    connection_id TEXT NOT NULL,
    command TEXT NOT NULL,
    command_key TEXT NOT NULL,
    database_info JSONB NOT NULL,
    schema_hash TEXT NOT NULL,
    plan JSONB NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding vector(__EMBEDDING_DIM__) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, connection_id, schema_hash, embedding_model, command_key)
);

CREATE INDEX IF NOT EXISTS idx_command_catalog_scope
    ON command_catalog (tenant_id, connection_id, schema_hash, embedding_model);

-- Exact cosine search within the scoped catalog keeps small per-DB catalogs
-- deterministic (no approximate-index filtering can hide eligible commands).
