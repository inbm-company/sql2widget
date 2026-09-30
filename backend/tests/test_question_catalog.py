"""Real pgvector verification. All catalog writes are rolled back."""

from contextlib import contextmanager
from uuid import uuid4

import pytest

from app import config
from app.repositories import question_catalog as repo


@pytest.fixture
def catalog(monkeypatch):
    original_get_conn = repo.get_conn
    with original_get_conn() as conn:
        @contextmanager
        def same_transaction():
            yield conn

        monkeypatch.setattr(repo, "get_conn", same_transaction)
        try:
            yield f"test_{uuid4().hex}"
        finally:
            conn.rollback()


def test_pgvector_question_ranking_scope_threshold_and_idempotency(catalog):
    tenant = catalog
    vector = [1.0] + [0.0] * (config.CHAT_EMBEDDING_DIM - 1)
    different = [0.0, 1.0] + [0.0] * (config.CHAT_EMBEDDING_DIM - 2)
    entry = {"question": "주문 수를 알려줘", "plan": {"widgets": []},
             "embedding_model": "test-model", "embedding": vector}

    def save(tenant_id=tenant, connection_id="db-a", schema_hash="schema-a", **changes):
        return repo.upsert_questions(tenant_id=tenant_id, connection_id=connection_id,
            schema_hash=schema_hash, database_info={"name": "test-db"}, entries=[{**entry, **changes}])[0]

    first = save()
    repeated = save(question="  주문   수를 알려줘  ")
    assert repeated["id"] == first["id"]
    save(tenant_id=f"{tenant}-other")
    save(connection_id="db-b")
    save(schema_hash="old-schema")
    save(embedding_model="other-model")
    save(question="관련 없는 질문", embedding=different)

    hits = repo.search_questions(tenant_id=tenant, connection_id="db-a", schema_hash="schema-a",
        embedding_model="test-model", embedding=vector, min_similarity=0.75)
    assert [hit["id"] for hit in hits] == [first["id"]]
    assert hits[0]["similarity"] == pytest.approx(1.0)
    assert hits[0]["database_info"]["name"] == "test-db"

    hits = repo.search_questions(tenant_id=tenant, connection_id="db-a", schema_hash="schema-a",
        embedding_model="test-model", embedding=vector, min_similarity=0, limit=1)
    assert len(hits) == 1
    assert hits[0]["id"] == first["id"]
