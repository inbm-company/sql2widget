"""DB-wide expected questions and role-safe similarity retrieval."""

import hashlib
import math
import re
from collections import Counter

from app import config, llm
from app.contracts import QuestionIn
from app.query import QueryError, execute_readonly, validate_readonly_select
from app.repositories import connections, question_catalog

SQL_COMPONENTS = config.ALLOWED_COMPONENTS - {"MarkdownBlock", "SourceList", "FilterBar"}
TABLES_PER_BATCH = 4


class QuestionCatalogError(RuntimeError):
    pass


def schema_hash(schema_text: str) -> str:
    return hashlib.sha256(schema_text.encode()).hexdigest()


def connection_context(tenant_id: str, connection_id: str) -> dict:
    """Read the selected DB's schema without choosing a user role."""
    row = connections.get_connection(connection_id, tenant_id)
    if not row:
        raise LookupError("Database connection not found")
    table_names = connections.catalog_tables_for_connection(row)
    if not table_names:
        raise ValueError("질문을 만들 수 있는 테이블이 없습니다.")
    metadata = connections.schema_metadata(row, table_names)
    tables = [table for table in metadata["tables"]
              if table["name"] in table_names]
    if not tables:
        raise ValueError("DB 스키마에서 조회 가능한 테이블을 찾지 못했습니다.")
    metadata = {**metadata, "tables": tables}
    return {
        "row": row,
        "table_names": table_names,
        "metadata": metadata,
        "schema_text": connections.format_schema_context(metadata),
        "database_info": {
            "connection_id": connection_id,
            "name": row["name"],
            "database_name": row["database_name"],
            "tables": sorted(table_names),
        },
    }


def _embedding(question: str, settings: dict, result: dict | None = None) -> dict:
    result = result if result is not None else llm.embed_text(
        question, runtime_provider=settings.get("provider"),
        runtime_api_key=settings.get("api_key"),
    )
    return _check_embedding(result.get("embedding"), result)


def _check_embedding(values: list[float] | None, result: dict) -> dict:
    if (not values or len(values) != config.CHAT_EMBEDDING_DIM
            or not result.get("model")
            or not all(isinstance(v, (float, int)) and math.isfinite(v) for v in values)
            or not any(values)):
        raise QuestionCatalogError("질문 임베딩을 만들 수 없습니다. AI 연결 설정과 임베딩 응답을 확인하세요.")
    return {
        "embedding": values,
        "embedding_model": f"{result['provider']}:{result['model']}:{len(values)}",
    }


def _validate_question(item: QuestionIn, allowed_tables: set[str]) -> None:
    if not item.question.strip():
        raise ValueError("질문이 비어 있습니다.")
    for widget in item.plan.widgets:
        if widget.component not in SQL_COMPONENTS:
            raise ValueError("질문에 사용할 수 없는 위젯입니다.")
        try:
            validate_readonly_select(widget.sql, allowed_tables=allowed_tables)
        except QueryError as exc:
            raise ValueError("허용된 테이블의 읽기 전용 SQL만 등록할 수 있습니다.") from exc
        # The legacy validator does not recognize quoted identifiers. Check
        # both quoted and unquoted FROM/JOIN references before sharing a plan.
        refs = re.findall(
            r'\b(?:FROM|JOIN)\s+((?:"[^"]+"|[a-zA-Z_]\w*)'
            r'(?:\s*\.\s*(?:"[^"]+"|[a-zA-Z_]\w*))*)',
            widget.sql, flags=re.IGNORECASE,
        )
        if not refs:
            raise ValueError("테이블을 조회하는 SQL만 등록할 수 있습니다.")
        permitted = {name.lower() for name in allowed_tables}
        for ref in refs:
            table_name = ref.split(".")[-1].strip().strip('"').replace('""', '"')
            if table_name.lower() not in permitted:
                raise ValueError("허용되지 않은 테이블의 SQL은 사용할 수 없습니다.")


def _prepared_entries(items: list[QuestionIn], *, context: dict,
                      settings: dict, verify_sql: bool) -> list[dict]:
    url = connections.connection_url(context["row"]) if verify_sql else None
    for item in items:
        _validate_question(item, context["table_names"])
        if verify_sql:
            for widget in item.plan.widgets:
                try:
                    execute_readonly(url, widget.sql, allowed_tables=context["table_names"],
                                     row_limit=1, timeout_seconds=5)
                except Exception as exc:
                    raise ValueError("질문의 SQL 실행 검증에 실패했습니다. 이 묶음은 저장되지 않았습니다.") from exc
    result = llm.embed_texts(
        [item.question for item in items],
        runtime_provider=settings.get("provider"),
        runtime_api_key=settings.get("api_key"),
    )
    vectors = result.get("embeddings")
    if vectors is None or len(vectors) != len(items):
        raise QuestionCatalogError("질문 임베딩에 실패했습니다. AI 연결 설정을 확인하세요.")
    return [
        {"question": item.question.strip(), "plan": item.plan.model_dump(),
         **_check_embedding(values, result)}
        for item, values in zip(items, vectors)
    ]


def register_questions(items: list[QuestionIn], *, tenant_id: str,
                       connection_id: str, context: dict, llm_settings: dict,
                       verified: bool = False) -> list[dict]:
    if not items:
        return []
    entries = _prepared_entries(items, context=context, settings=llm_settings,
                                verify_sql=not verified)
    try:
        return question_catalog.upsert_questions(
            tenant_id=tenant_id, connection_id=connection_id,
            schema_hash=schema_hash(context["schema_text"]),
            database_info=context["database_info"], entries=entries,
        )
    except Exception as exc:
        raise QuestionCatalogError("유사도 DB 저장에 실패했습니다. DB 연결과 마이그레이션을 확인하세요.") from exc


def _quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _uncovered_tables(tables: list[dict], questions: list[QuestionIn],
                      name_counts: Counter) -> list[str]:
    uncovered = []
    for table in tables:
        qualified = f"{_quoted(table['schema'])}.{_quoted(table['name'])}"
        unquoted = f"{table['schema']}.{table['name']}"
        bare = re.compile(
            rf'\b(?:FROM|JOIN)\s+"?{re.escape(table["name"])}"?(?=\s|$)',
            flags=re.IGNORECASE,
        )
        if not any(
            qualified in widget.sql or unquoted in widget.sql
            or (name_counts[table["name"]] == 1 and bare.search(widget.sql))
            for item in questions for widget in item.plan.widgets
        ):
            uncovered.append(f"{table['schema']}.{table['name']}")
    return uncovered


def _generate_candidates(*, message: str, schema_text: str, tenant_id: str,
                         user_id: str, llm_settings: dict) -> list[dict]:
    result = llm.plan_with_llm(
        message, schema_text=schema_text, tenant_id=tenant_id, user_id=user_id,
        conversation_id=None, catalog_seed=True,
        runtime_provider=llm_settings.get("provider"),
        runtime_api_key=llm_settings.get("api_key"),
        runtime_model=llm_settings.get("model"),
    )
    try:
        candidates = result["plan"]["questions"]
        if not isinstance(candidates, list):
            raise ValueError("Invalid questions")
    except (TypeError, KeyError, ValueError) as exc:
        raise QuestionCatalogError(
            "AI가 예상 질문을 만들지 못했습니다. AI 연결 설정을 확인하고 다시 시도하세요."
        ) from exc
    return candidates


def seed_question_batch(*, tenant_id: str, user_id: str, connection_id: str,
                        context: dict, llm_settings: dict, offset: int = 0) -> dict:
    tables = context["metadata"]["tables"]
    if offset >= len(tables):
        return {"questions": [], "saved_count": 0, "skipped_count": 0,
                "uncovered_tables": [], "processed_tables": 0,
                "total_tables": len(tables), "next_offset": None}
    selected = tables[offset:offset + TABLES_PER_BATCH]
    names = {table["name"] for table in selected}
    chunk_metadata = {
        "tables": selected,
        "foreign_keys": [fk for fk in context["metadata"]["foreign_keys"]
                         if fk["table_name"] in names and fk["foreign_table_name"] in names],
    }
    schema_text = connections.format_schema_context(chunk_metadata)
    name_counts = Counter(table["name"] for table in tables)
    skipped = 0
    unique = {}
    url = connections.connection_url(context["row"])
    message = "각 테이블에서 예상되는 다양한 사용자 질문과 SQL·위젯을 만들어 주세요."
    for attempt in range(3):
        if attempt == 1 and unique:
            existing = "; ".join(item.question for item in unique.values())
            message = (
                "이미 생성한 질문과 의미가 겹치지 않는 예상 질문을 더 만들어 주세요. "
                "다른 집계·순위·분포·추이·필터·테이블 관계를 살펴보세요. "
                f"이미 생성한 질문: {existing}"
            )
        elif attempt > 0:
            uncovered = _uncovered_tables(selected, list(unique.values()), name_counts)
            if not uncovered:
                break
            message = (
                "다음 테이블은 유효한 예상 질문이 아직 없습니다: "
                + ", ".join(uncovered)
                + ". 해당 테이블을 사용하는 자연스러운 사용자 질문과 실행 가능한 SQL·위젯을 "
                  "스키마에 맞게 다양하게 만들어 주세요."
            )
        try:
            candidates = _generate_candidates(
                message=message, schema_text=schema_text, tenant_id=tenant_id,
                user_id=user_id, llm_settings=llm_settings,
            )
        except QuestionCatalogError:
            if attempt == 0 or not unique:
                raise
            break
        for candidate in candidates:
            try:
                item = QuestionIn.model_validate(candidate)
                _validate_question(item, names)
                for widget in item.plan.widgets:
                    execute_readonly(url, widget.sql,
                                     allowed_tables=names, row_limit=1, timeout_seconds=5)
            except Exception:  # One bad AI suggestion should not discard valid questions.
                skipped += 1
                continue
            unique[item.question.casefold()] = item
        if attempt == 1 and not _uncovered_tables(selected, list(unique.values()), name_counts):
            break
    uncovered = _uncovered_tables(selected, list(unique.values()), name_counts)
    saved = []
    if unique:
        saved = register_questions(
            list(unique.values()), tenant_id=tenant_id, connection_id=connection_id,
            context=context, llm_settings=llm_settings, verified=True,
        )
    next_offset = offset + len(selected)
    return {
        "questions": saved, "saved_count": len(saved), "skipped_count": skipped,
        "uncovered_tables": uncovered,
        "processed_tables": len(selected), "total_tables": len(tables),
        "next_offset": next_offset if next_offset < len(tables) else None,
    }


def search_questions(question: str, *, tenant_id: str, connection_id: str,
                     allowed_tables: set[str], llm_settings: dict,
                     user_role: str | None = None, embedding_result: dict | None = None,
                     limit: int = 5, min_similarity: float = 0.75) -> dict:
    try:
        if user_role is not None:
            configured = connections.allowed_tables_for_role(tenant_id, connection_id, user_role)
            if not configured or configured != allowed_tables:
                return {"status": "no_permissions", "matches": []}
        if not allowed_tables:
            return {"status": "no_permissions", "matches": []}
        context = connection_context(tenant_id, connection_id)
        embedded = _embedding(question, llm_settings, embedding_result)
        valid = []
        offset = 0
        while len(valid) < limit:
            matches = question_catalog.search_questions(
                tenant_id=tenant_id, connection_id=connection_id,
                schema_hash=schema_hash(context["schema_text"]), **embedded,
                limit=50, offset=offset, min_similarity=min_similarity,
            )
            for match in matches:
                try:
                    item = QuestionIn(question=match["question"], plan=match["plan"])
                    _validate_question(item, allowed_tables)
                except ValueError:
                    continue
                valid.append(match)
                if len(valid) == limit:
                    break
            if len(matches) < 50:
                break
            offset += len(matches)
        return {"status": "matched" if valid else "no_match", "matches": valid}
    except Exception:  # Retrieval is optional; the live model still must succeed.
        return {"status": "unavailable", "matches": [],
                "error": "예상 질문 검색에 실패했습니다. AI 임베딩 설정과 유사도 DB를 확인하세요."}
