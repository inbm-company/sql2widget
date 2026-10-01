-- Uploaded documents are kept so a source can be re-ingested without the original files.
CREATE TABLE IF NOT EXISTS graph_source_files (
    source_id TEXT NOT NULL REFERENCES graph_sources(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    content TEXT NOT NULL,
    PRIMARY KEY (source_id, path)
);
