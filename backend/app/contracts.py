from typing import Any, Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class CreateConversationRequest(BaseModel):
    title: str | None = None


class UpdateConversationRequest(BaseModel):
    title: str


class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    connection_id: str | None = None


class LayoutItem(BaseModel):
    i: str
    x: int = 0
    y: int = 0
    w: int = 4
    h: int = 4


class StageWidgetIn(BaseModel):
    source_widget_id: str | None = None
    source_artifact_id: str | None = None
    component: str
    title: str = ""
    props: dict[str, Any] = Field(default_factory=dict)
    layout: LayoutItem


class StageWidgetPatch(BaseModel):
    title: str | None = None
    props: dict[str, Any] | None = None
    layout: LayoutItem | None = None


class StagePutRequest(BaseModel):
    widgets: list[StageWidgetIn] = Field(default_factory=list)


class DatabaseConnectionIn(BaseModel):
    name: str
    host: str
    port: int = 5432
    database_name: str
    username: str
    password: str
    sslmode: str = "prefer"


class TablePermissionPut(BaseModel):
    connection_id: str
    role: str = "user"
    tables: list[dict[str, str]] = Field(default_factory=list)


ArtifactType = Literal["widget", "dashboard", "report"]
