"""User command -> DB-scoped similar commands -> answer-generation context."""

import hashlib
import math

from app import config, llm
from app.contracts import CommandIn
from app.query import execute_readonly, validate_readonly_select
from app.repositories import command_catalog, connections

SQL_COMPONENTS = config.ALLOWED_COMPONENTS - {"MarkdownBlock", "SourceList", "FilterBar"}


class CommandCatalogError(RuntimeError):
    pass


def schema_hash(schema_text: str) -> str:
    # Exact schema scope also prevents a role from seeing commands prepared for
    # a larger permission set. Changed schemas must be registered again.
    return hashlib.sha256(schema_text.encode()).hexdigest()


def connection_context(tenant_id: str, connection_id: str, role: str) -> dict:
    row = connections.get_connection(connection_id, tenant_id)
    if not row:
        raise LookupError("Database connection not found")
    allowed = connections.allowed_tables_for_role(tenant_id, connection_id, role)
    if not allowed:
        raise ValueError("선택한 역할에 허용된 테이블이 없습니다. 테이블 권한을 먼저 저장하세요.")
    schema_text = connections.schema_context_for_connection(row, allowed)
    return {
        "row": row,
        "allowed_tables": allowed,
        "schema_text": schema_text,
        "database_info": {
            "connection_id": connection_id,
            "name": row["name"],
            "database_name": row["database_name"],
            "tables": sorted(allowed),
            "schema": schema_text,
        },
    }


def _embedding(command: str, settings: dict, result: dict | None = None) -> dict:
    result = result if result is not None else llm.embed_text(
        command,
        runtime_provider=settings.get("provider"),
        runtime_api_key=settings.get("api_key"),
    )
    values = result.get("embedding")
    if (not values or len(values) != config.CHAT_EMBEDDING_DIM
            or not result.get("model")
            or not all(isinstance(v, (float, int)) and math.isfinite(v) for v in values)
            or not any(values)):
        raise CommandCatalogError("명령 임베딩을 만들 수 없습니다. AI 연결 설정과 임베딩 응답을 확인하세요.")
    return {
        "embedding": values,
        "embedding_model": f"{result['provider']}:{result['model']}:{len(values)}",
    }


def search_commands(command: str, *, tenant_id: str, connection_id: str,
                    schema_text: str, allowed_tables: set[str], llm_settings: dict,
                    limit: int = 5, min_similarity: float = 0.75,
                    user_role: str | None = None, embedding_result: dict | None = None) -> dict:
    try:
        # The legacy chat resolver can fall back to demo permissions. Never
        # use that fallback to grant access to the new shared command catalog.
        if user_role is not None:
            configured = connections.allowed_tables_for_role(tenant_id, connection_id, user_role)
            if not configured or configured != allowed_tables:
                return {"status": "no_permissions", "matches": []}
        embedded = _embedding(command, llm_settings, embedding_result)
        matches = command_catalog.search_commands(
            tenant_id=tenant_id, connection_id=connection_id,
            schema_hash=schema_hash(schema_text), **embedded,
            limit=limit, min_similarity=min_similarity,
        )
        # Stored references are revalidated before reaching the model/client.
        valid = []
        for match in matches:
            try:
                item = CommandIn(command=match["command"], plan=match["plan"])
                _validate_plan(item, allowed_tables)
            except ValueError:
                continue
            valid.append(match)
        return {"status": "matched" if valid else "no_match", "matches": valid}
    except Exception:  # Retrieval is optional; the real LLM still must succeed.
        return {
            "status": "unavailable", "matches": [],
            "error": "명령 유사도 검색에 실패했습니다. AI 임베딩 설정과 유사도 DB를 확인하세요.",
        }


def _validate_plan(item: CommandIn, allowed_tables: set[str]) -> None:
    if not item.command.strip():
        raise ValueError("명령이 비어 있습니다.")
    for widget in item.plan.widgets:
        if widget.component not in SQL_COMPONENTS:
            raise ValueError("명령에 사용할 수 없는 위젯입니다.")
        try:
            validate_readonly_select(widget.sql, allowed_tables=allowed_tables)
        except Exception as exc:
            raise ValueError("허용된 테이블의 읽기 전용 SQL만 등록할 수 있습니다.") from exc


def register_commands(items: list[CommandIn], *, tenant_id: str, connection_id: str,
                      context: dict, llm_settings: dict) -> list[dict]:
    entries = []
    for item in items:
        _validate_plan(item, context["allowed_tables"])
        for widget in item.plan.widgets:
            try:
                execute_readonly(
                    connections.connection_url(context["row"]), widget.sql,
                    allowed_tables=context["allowed_tables"], row_limit=1,
                    timeout_seconds=5,
                )
            except Exception as exc:
                raise ValueError("명령의 SQL 실행 검증에 실패했습니다. 등록된 명령은 변경되지 않았습니다.") from exc
        embedded = _embedding(item.command, llm_settings)
        entries.append({"command": item.command.strip(), "plan": item.plan.model_dump(), **embedded})
    try:
        return command_catalog.upsert_commands(
            tenant_id=tenant_id, connection_id=connection_id,
            schema_hash=schema_hash(context["schema_text"]),
            database_info=context["database_info"], entries=entries,
        )
    except Exception as exc:
        raise CommandCatalogError("유사도 DB 저장에 실패했습니다. DB 연결과 마이그레이션을 확인하세요.") from exc


def seed_commands(*, tenant_id: str, user_id: str, connection_id: str,
                  context: dict, llm_settings: dict, count: int = 3) -> list[dict]:
    result = llm.plan_with_llm(
        "이 DB에서 사용자가 요청할 명령과 각 명령의 SQL·위젯 실행 정보를 준비하세요.",
        schema_text=context["schema_text"], tenant_id=tenant_id, user_id=user_id,
        conversation_id=None, catalog_seed_count=count,
        runtime_provider=llm_settings.get("provider"),
        runtime_api_key=llm_settings.get("api_key"),
        runtime_model=llm_settings.get("model"),
    )
    try:
        candidates = result["plan"]["commands"]
        if not isinstance(candidates, list) or not 1 <= len(candidates) <= count:
            raise ValueError("Invalid command count")
        items = [CommandIn.model_validate(item) for item in candidates]
    except (TypeError, KeyError, ValueError) as exc:
        raise CommandCatalogError("AI가 유효한 초기 명령을 만들지 못했습니다. AI 연결 설정을 확인하고 다시 시도하세요.") from exc
    return register_commands(
        items, tenant_id=tenant_id, connection_id=connection_id,
        context=context, llm_settings=llm_settings,
    )
