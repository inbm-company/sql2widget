import os


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required env: {name}")
    return value


APP_ENV = env("APP_ENV", "development")
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
    "postgresql://agent4any:agent4any@127.0.0.1:5435/agent4any_stage_global",
)
LLM_PROVIDER = env("LLM_PROVIDER", "mock")
LLM_API_KEY = env("LLM_API_KEY", "")
LLM_BASE_URL = env("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = env("LLM_MODEL", "gpt-4o-mini")
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
