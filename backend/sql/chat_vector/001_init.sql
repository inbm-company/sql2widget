CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- message_id는 메인 DB(agent4any)의 messages.id를 가리킨다.
-- 별도 데이터베이스이므로 FK 제약은 걸 수 없고, 애플리케이션이 정합성을 책임진다.
CREATE TABLE IF NOT EXISTS message_embeddings (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    message_id TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    embedding vector(__EMBEDDING_DIM__) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_message_embeddings_conversation
    ON message_embeddings (conversation_id, created_at);

CREATE INDEX IF NOT EXISTS idx_message_embeddings_tenant
    ON message_embeddings (tenant_id);

-- 코사인 유사도 기준 근사 최근접 이웃 검색용 HNSW 인덱스
CREATE INDEX IF NOT EXISTS idx_message_embeddings_hnsw
    ON message_embeddings USING hnsw (embedding vector_cosine_ops);
