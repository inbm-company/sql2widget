import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row

from app import config, command_similarity
from app.agent_service import AgentRunError, run_agent
from app.auth import (
    create_access_token,
    get_current_user,
    issue_refresh_token,
    rotate_refresh_token,
    verify_password,
)
from app.contracts import (
    ChatRequest,
    CommandRegisterRequest,
    CommandSearchRequest,
    CommandSeedRequest,
    CreateConversationRequest,
    CreateProjectRequest,
    UpdateProjectRequest,
    UpdateConversationRequest,
    DatabaseConnectionIn,
    LoginRequest,
    RefreshRequest,
    StagePutRequest,
    StageWidgetIn,
    StageWidgetPatch,
    TablePermissionPut,
)
from app.db import fetch_one
from app.llm import effective_provider, embed_text
from app.query import execute_readonly
from app.repositories import connections as conn_repo
from app.repositories import conversations as conv_repo
from app.repositories import message_embeddings as embed_repo
from app.repositories import projects as project_repo
from app.repositories import stages as stage_repo

app = FastAPI(title="agent4any", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "provider": config.LLM_PROVIDER,
        "effective_provider": effective_provider(),
    }


def require_admin(user: dict):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")


@app.post("/api/auth/login")
def login(body: LoginRequest):
    user = fetch_one(
        "SELECT id, email, role, tenant_id, password_hash FROM users WHERE email = %s",
        (body.email.lower().strip(),),
    )
    if not user or not verify_password(user["password_hash"], body.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access = create_access_token(user["id"], user["tenant_id"], user["role"])
    refresh = issue_refresh_token(user["id"])
    return {
        "access_token": access,
        "refresh_token": refresh,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"],
            "tenant_id": user["tenant_id"],
        },
    }


@app.post("/api/auth/refresh")
def refresh(body: RefreshRequest):
    user, access, new_refresh = rotate_refresh_token(body.refresh_token)
    return {"access_token": access, "refresh_token": new_refresh, "user": user}


@app.get("/api/auth/me")
def me(user=Depends(get_current_user)):
    return user


@app.get("/api/projects")
def list_projects(user=Depends(get_current_user)):
    return project_repo.list_projects(user["tenant_id"], user["id"])


@app.post("/api/projects")
def create_project(body: CreateProjectRequest, user=Depends(get_current_user)):
    return project_repo.create_project(user["tenant_id"], user["id"], body.title)


@app.patch("/api/projects/{project_id}")
def update_project(
    project_id: str, body: UpdateProjectRequest, user=Depends(get_current_user)
):
    project = project_repo.update_project(
        project_id, user["tenant_id"], user["id"], body.title
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.get("/api/conversations")
def list_conversations(project_id: str, user=Depends(get_current_user)):
    if not project_repo.get_project(project_id, user["tenant_id"], user["id"]):
        raise HTTPException(status_code=404, detail="Project not found")
    return conv_repo.list_conversations(user["tenant_id"], user["id"], project_id)


@app.post("/api/conversations")
def create_conversation(body: CreateConversationRequest, user=Depends(get_current_user)):
    conv = conv_repo.create_conversation(
        user["tenant_id"], user["id"], body.project_id, body.title
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Project not found")
    return conv


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str, user=Depends(get_current_user)):
    conv = conv_repo.get_conversation(conversation_id, user["tenant_id"], user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@app.patch("/api/conversations/{conversation_id}")
def update_conversation(
    conversation_id: str,
    body: UpdateConversationRequest,
    user=Depends(get_current_user),
):
    conv = conv_repo.update_conversation(
        conversation_id, user["tenant_id"], user["id"], body.title
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, user=Depends(get_current_user)):
    ok = conv_repo.delete_conversation(conversation_id, user["tenant_id"], user["id"])
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True}


@app.post("/api/chat")
def chat(body: ChatRequest, request: Request, user=Depends(get_current_user)):
    conv = conv_repo.get_conversation(body.conversation_id, user["tenant_id"], user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    user_msg = conv_repo.add_message(body.conversation_id, "user", body.message, None)
    conv_repo.touch_title_from_message(body.conversation_id, body.message)

    llm_settings = {
        "provider": request.headers.get("X-LLM-Provider", ""),
        "api_key": request.headers.get("X-LLM-API-Key", ""),
        "model": request.headers.get("X-LLM-Model", ""),
    }

    related_messages: list[dict] = []
    embedding_error: str | None = None
    embed_result = embed_text(
        body.message,
        runtime_provider=llm_settings["provider"] or None,
        runtime_api_key=llm_settings["api_key"] or None,
    )
    if embed_result["embedding"]:
        related_messages = embed_repo.search_similar(
            user["tenant_id"], embed_result["embedding"], limit=5
        )
        embed_repo.upsert_embedding(
            tenant_id=user["tenant_id"],
            conversation_id=body.conversation_id,
            message_id=user_msg["id"],
            role="user",
            content=body.message,
            embedding=embed_result["embedding"],
        )
    elif embed_result["error"]:
        embedding_error = embed_result["error"]

    try:
        summary, artifact, meta = run_agent(
            body.message,
            tenant_id=user["tenant_id"],
            user_id=user["id"],
            user_role=user["role"],
            conversation_id=body.conversation_id,
            connection_id=body.connection_id,
            llm_settings=llm_settings,
            embedding_result=embed_result,
        )
    except AgentRunError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    assistant_msg = conv_repo.add_message(
        body.conversation_id, "assistant", summary, artifact
    )

    assistant_embed = embed_text(
        summary,
        runtime_provider=llm_settings["provider"] or None,
        runtime_api_key=llm_settings["api_key"] or None,
    )
    if assistant_embed["embedding"]:
        embed_repo.upsert_embedding(
            tenant_id=user["tenant_id"],
            conversation_id=body.conversation_id,
            message_id=assistant_msg["id"],
            role="assistant",
            content=summary,
            embedding=assistant_embed["embedding"],
        )

    return {
        "user_message": user_msg,
        "assistant_message": assistant_msg,
        "artifact": artifact,
        "meta": meta,
        "related_messages": related_messages,
        "embedding_provider": embed_result["provider"],
        "embedding_error": embedding_error,
    }


@app.get("/api/database-connections")
def list_database_connections(user=Depends(get_current_user)):
    return conn_repo.list_connections(user["tenant_id"])


@app.post("/api/database-connections")
def create_database_connection(
    body: DatabaseConnectionIn, user=Depends(get_current_user)
):
    require_admin(user)
    return conn_repo.create_connection(
        tenant_id=user["tenant_id"],
        name=body.name,
        host=body.host,
        port=body.port,
        database_name=body.database_name,
        username=body.username,
        password=body.password,
        created_by=user["id"],
        sslmode=body.sslmode,
    )


def _command_llm_settings(request: Request) -> dict:
    return {
        "provider": request.headers.get("X-LLM-Provider", ""),
        "api_key": request.headers.get("X-LLM-API-Key", ""),
        "model": request.headers.get("X-LLM-Model", ""),
    }


def _command_context(user: dict, connection_id: str, role: str) -> dict:
    try:
        return command_similarity.connection_context(user["tenant_id"], connection_id, role)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="DB 스키마를 읽을 수 없습니다.") from exc


@app.post("/api/database-connections/{connection_id}/commands/seed")
def seed_database_commands(connection_id: str, body: CommandSeedRequest,
                           request: Request, user=Depends(get_current_user)):
    require_admin(user)
    context = _command_context(user, connection_id, body.role)
    try:
        commands = command_similarity.seed_commands(
            tenant_id=user["tenant_id"], user_id=user["id"], connection_id=connection_id,
            context=context, llm_settings=_command_llm_settings(request), count=body.count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except command_similarity.CommandCatalogError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"connection_id": connection_id, "saved_count": len(commands), "commands": commands}


@app.post("/api/database-connections/{connection_id}/commands")
def register_database_command(connection_id: str, body: CommandRegisterRequest,
                              request: Request, user=Depends(get_current_user)):
    require_admin(user)
    context = _command_context(user, connection_id, body.role)
    try:
        commands = command_similarity.register_commands(
            [body], tenant_id=user["tenant_id"], connection_id=connection_id,
            context=context, llm_settings=_command_llm_settings(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except command_similarity.CommandCatalogError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return commands[0]


@app.post("/api/database-connections/{connection_id}/commands/search")
def search_database_commands(connection_id: str, body: CommandSearchRequest,
                            request: Request, user=Depends(get_current_user)):
    context = _command_context(user, connection_id, user["role"])
    result = command_similarity.search_commands(
        body.command, tenant_id=user["tenant_id"], connection_id=connection_id,
        schema_text=context["schema_text"], allowed_tables=context["allowed_tables"],
        llm_settings=_command_llm_settings(request), limit=body.limit,
        min_similarity=body.min_similarity,
    )
    if result["status"] == "unavailable":
        raise HTTPException(status_code=502, detail=result["error"])
    return result


@app.post("/api/database-connections/{connection_id}/test")
def test_database_connection(connection_id: str, user=Depends(get_current_user)):
    row = conn_repo.get_connection(connection_id, user["tenant_id"])
    if not row:
        raise HTTPException(status_code=404, detail="Connection not found")
    url = conn_repo.connection_url(row)
    try:
        with psycopg.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                cur.fetchone()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Connection failed: {exc}") from exc


@app.get("/api/database-connections/{connection_id}/tables")
def list_connection_tables(connection_id: str, user=Depends(get_current_user)):
    row = conn_repo.get_connection(connection_id, user["tenant_id"])
    if not row:
        raise HTTPException(status_code=404, detail="Connection not found")
    url = conn_repo.connection_url(row)
    with psycopg.connect(url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_schema AS schema_name, table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                  AND table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name
                """
            )
            return cur.fetchall()


@app.get("/api/table-permissions")
def get_table_permissions(connection_id: str, user=Depends(get_current_user)):
    return conn_repo.list_table_permissions(user["tenant_id"], connection_id)


@app.put("/api/table-permissions")
def put_table_permissions(body: TablePermissionPut, user=Depends(get_current_user)):
    require_admin(user)
    row = conn_repo.get_connection(body.connection_id, user["tenant_id"])
    if not row:
        raise HTTPException(status_code=404, detail="Connection not found")
    return conn_repo.replace_table_permissions(
        tenant_id=user["tenant_id"],
        connection_id=body.connection_id,
        role=body.role,
        tables=body.tables,
    )


@app.post("/api/database-connections/{connection_id}/preview-sql")
def preview_sql(
    connection_id: str, body: dict, user=Depends(get_current_user)
):
    """Admin/debug helper: run a validated SELECT."""
    require_admin(user)
    row = conn_repo.get_connection(connection_id, user["tenant_id"])
    if not row:
        raise HTTPException(status_code=404, detail="Connection not found")
    sql = (body or {}).get("sql") or ""
    allowed = conn_repo.allowed_tables_for_role(
        user["tenant_id"], connection_id, user["role"]
    )
    try:
        rows = execute_readonly(
            conn_repo.connection_url(row), sql, allowed_tables=allowed or None
        )
        return {"rows": rows, "count": len(rows)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/stage")
def get_stage(project_id: str, user=Depends(get_current_user)):
    stage = stage_repo.get_or_create_stage(
        project_id, user["tenant_id"], user["id"]
    )
    if not stage:
        raise HTTPException(status_code=404, detail="Project not found")
    return stage


@app.put("/api/projects/{project_id}/stage")
def put_stage(
    project_id: str, body: StagePutRequest, user=Depends(get_current_user)
):
    stage = stage_repo.get_or_create_stage(
        project_id, user["tenant_id"], user["id"]
    )
    if not stage:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        widgets = stage_repo.replace_stage_widgets(
            stage["id"],
            [w.model_dump() for w in body.widgets],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**stage, "widgets": widgets}


@app.post("/api/projects/{project_id}/stage/widgets")
def add_stage_widget(
    project_id: str, body: StageWidgetIn, user=Depends(get_current_user)
):
    stage = stage_repo.get_or_create_stage(
        project_id, user["tenant_id"], user["id"]
    )
    if not stage:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        widget = stage_repo.add_widget(stage["id"], body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return widget


@app.patch("/api/projects/{project_id}/stage/widgets/{widget_id}")
def patch_stage_widget(
    project_id: str,
    widget_id: str,
    body: StageWidgetPatch,
    user=Depends(get_current_user),
):
    stage = stage_repo.get_or_create_stage(
        project_id, user["tenant_id"], user["id"]
    )
    if not stage:
        raise HTTPException(status_code=404, detail="Project not found")
    widget = stage_repo.patch_widget(
        stage["id"], widget_id, body.model_dump(exclude_unset=True)
    )
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found")
    return widget


@app.delete("/api/projects/{project_id}/stage/widgets/{widget_id}")
def delete_stage_widget(
    project_id: str, widget_id: str, user=Depends(get_current_user)
):
    stage = stage_repo.get_or_create_stage(
        project_id, user["tenant_id"], user["id"]
    )
    if not stage:
        raise HTTPException(status_code=404, detail="Project not found")
    ok = stage_repo.delete_widget(stage["id"], widget_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Widget not found")
    return {"ok": True}
