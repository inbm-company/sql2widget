from typing import Any, Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class CreateConversationRequest(BaseModel):
    project_id: str
    title: str | None = None


class UpdateConversationRequest(BaseModel):
    title: str


class CreateProjectRequest(BaseModel):
    title: str | None = None


class UpdateProjectRequest(BaseModel):
    title: str


class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    connection_id: str | None = None


class QuestionWidgetIn(BaseModel):
    component: str
    title: str = Field(min_length=1, max_length=300)
    sql: str = Field(min_length=1, max_length=20000)


class QuestionPlanIn(BaseModel):
    summary: str = Field(default="결과를 준비했습니다.", max_length=1000)
    artifact_type: Literal["widget", "dashboard", "report"] = "widget"
    widgets: list[QuestionWidgetIn] = Field(min_length=1, max_length=6)


class QuestionIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    plan: QuestionPlanIn


class QuestionRegisterRequest(QuestionIn):
    pass


class QuestionSeedRequest(BaseModel):
    offset: int = Field(default=0, ge=0)


class QuestionSearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=10)
    min_similarity: float = Field(default=0.75, ge=0, le=1)


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
