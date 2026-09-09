import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row

from app import config
from app.agent_service import run_agent
from app.auth import (
    create_access_token,
    get_current_user,
    issue_refresh_token,
    rotate_refresh_token,
    verify_password,
)
from app.contracts import (
    ChatRequest,
    CreateConversationRequest,
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
from app.llm import effective_provider
from app.query import execute_readonly
from app.repositories import connections as conn_repo
from app.repositories import conversations as conv_repo
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


@app.get("/api/conversations")
def list_conversations(user=Depends(get_current_user)):
    return conv_repo.list_conversations(user["tenant_id"], user["id"])


@app.post("/api/conversations")
def create_conversation(body: CreateConversationRequest, user=Depends(get_current_user)):
    return conv_repo.create_conversation(user["tenant_id"], user["id"], body.title)


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

    summary, artifact, meta = run_agent(
        body.message,
        tenant_id=user["tenant_id"],
        user_id=user["id"],
        user_role=user["role"],
        conversation_id=body.conversation_id,
        connection_id=body.connection_id,
        llm_settings={
            "provider": request.headers.get("X-LLM-Provider", ""),
            "api_key": request.headers.get("X-LLM-API-Key", ""),
            "model": request.headers.get("X-LLM-Model", ""),
        },
    )
    assistant_msg = conv_repo.add_message(
        body.conversation_id, "assistant", summary, artifact
    )
    return {
        "user_message": user_msg,
        "assistant_message": assistant_msg,
        "artifact": artifact,
        "meta": meta,
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


@app.get("/api/conversations/{conversation_id}/stage")
def get_stage(conversation_id: str, user=Depends(get_current_user)):
    stage = stage_repo.get_or_create_stage(
        conversation_id, user["tenant_id"], user["id"]
    )
    if not stage:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return stage


@app.put("/api/conversations/{conversation_id}/stage")
def put_stage(
    conversation_id: str, body: StagePutRequest, user=Depends(get_current_user)
):
    stage = stage_repo.get_or_create_stage(
        conversation_id, user["tenant_id"], user["id"]
    )
    if not stage:
        raise HTTPException(status_code=404, detail="Conversation not found")
    try:
        widgets = stage_repo.replace_stage_widgets(
            stage["id"],
            [w.model_dump() for w in body.widgets],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**stage, "widgets": widgets}


@app.post("/api/conversations/{conversation_id}/stage/widgets")
def add_stage_widget(
    conversation_id: str, body: StageWidgetIn, user=Depends(get_current_user)
):
    stage = stage_repo.get_or_create_stage(
        conversation_id, user["tenant_id"], user["id"]
    )
    if not stage:
        raise HTTPException(status_code=404, detail="Conversation not found")
    try:
        widget = stage_repo.add_widget(stage["id"], body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return widget


@app.patch("/api/conversations/{conversation_id}/stage/widgets/{widget_id}")
def patch_stage_widget(
    conversation_id: str,
    widget_id: str,
    body: StageWidgetPatch,
    user=Depends(get_current_user),
):
    stage = stage_repo.get_or_create_stage(
        conversation_id, user["tenant_id"], user["id"]
    )
    if not stage:
        raise HTTPException(status_code=404, detail="Conversation not found")
    widget = stage_repo.patch_widget(
        stage["id"], widget_id, body.model_dump(exclude_unset=True)
    )
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found")
    return widget


@app.delete("/api/conversations/{conversation_id}/stage/widgets/{widget_id}")
def delete_stage_widget(
    conversation_id: str, widget_id: str, user=Depends(get_current_user)
):
    stage = stage_repo.get_or_create_stage(
        conversation_id, user["tenant_id"], user["id"]
    )
    if not stage:
        raise HTTPException(status_code=404, detail="Conversation not found")
    ok = stage_repo.delete_widget(stage["id"], widget_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Widget not found")
    return {"ok": True}
