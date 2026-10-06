import os


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required env: {name}")
    return value


JWT_ISSUER = "sql2widget"
APP_ENV = env("APP_ENV", "development")
ADMIN_EMAIL = env("ADMIN_EMAIL", "admin@example.com" if APP_ENV == "production" else "admin.local@example.com").strip().lower()
VIEWER_EMAIL = env("VIEWER_EMAIL", "viewer@example.com" if APP_ENV == "production" else "viewer.local@example.com").strip().lower()
APP_SECRET = env("APP_SECRET", "dev-secret-replace-with-at-least-32-chars!!")
DATABASE_URL = env(
    "DATABASE_URL",
    "postgresql://agent4any:agent4any@127.0.0.1:5432/agent4any",
)
DEMO_CUSTOMER_DATABASE_URL = env(
    "DEMO_CUSTOMER_DATABASE_URL",
    "postgresql://agent4any:agent4any@127.0.0.1:5433/agent4any_customer_demo",
)
STAGE_GLOBAL_DATABASE_URL = env(
    "STAGE_GLOBAL_DATABASE_URL",
    "postgresql://agent4any:agent4any@127.0.0.1:5547/agent4any_stage_global",
)
NORTHWIND_DATABASE_URL = env(
    "NORTHWIND_DATABASE_URL",
    "postgresql://agent4any:agent4any@127.0.0.1:5548/agent4any_northwind",
)
SKAX_NMS_DATABASE_URL = env(
    "SKAX_NMS_DATABASE_URL",
    "postgresql://agent4any:agent4any@127.0.0.1:5549/agent4any_skax_nms",
)
CHAT_VECTOR_DATABASE_URL = env(
    "CHAT_VECTOR_DATABASE_URL",
    "postgresql://agent4any:agent4any@127.0.0.1:5550/agent4any_chat_vector",
)
CHAT_EMBEDDING_DIM = int(env("CHAT_EMBEDDING_DIM", "1536"))
LLM_PROVIDER = env("LLM_PROVIDER", "mock")
LLM_API_KEY = env("LLM_API_KEY", "")
LLM_BASE_URL = env("LLM_BASE_URL", "http://host.docker.internal:11434/v1" if LLM_PROVIDER == "local" else "https://api.openai.com/v1")
LLM_MODEL = env("LLM_MODEL", "" if LLM_PROVIDER == "local" else "gpt-4o-mini")
LLM_EMBEDDING_MODEL = env("LLM_EMBEDDING_MODEL", "")
# 채팅 의도 라우팅(TypeSafe Jev). 키가 없으면 라우팅을 일반 LLM이 대신한다.
TYPESAFE_API_KEY = env("TYPESAFE_API_KEY", "")
TYPESAFE_BASE_URL = env("TYPESAFE_BASE_URL", "https://api.typesafe.ai")
TYPESAFE_MODEL = env("TYPESAFE_MODEL", "jev-latest")
# 이 값 미만의 confidence는 되묻기로 처리한다. 실제 질문 데이터로 검증해 조정할 것.
ROUTE_MIN_CONFIDENCE = float(env("ROUTE_MIN_CONFIDENCE", "0.5"))
# 허용 테이블이 이 개수를 넘으면 SQL 계획에 관련 테이블만 전달한다(작은 DB는 전부 전달).
SCHEMA_LINK_MIN_TABLES = int(env("SCHEMA_LINK_MIN_TABLES", "20"))
CORS_ORIGINS = [
    o.strip()
    for o in env(
        "CORS_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    ).split(",")
    if o.strip()
]
JWT_ACCESS_MINUTES = int(env("JWT_ACCESS_MINUTES", "30"))
JWT_REFRESH_DAYS = int(env("JWT_REFRESH_DAYS", "14"))

ALLOWED_COMPONENTS = frozenset(
    {
        "KpiStat",
        "DataTable",
        "RankList",
        "BarChart",
        "LineChart",
        "PieChart",
        "MarkdownBlock",
        "SourceList",
        "FilterBar",
        "KpiSparkline",
        "PieTable",
        "BarTable",
    }
)
