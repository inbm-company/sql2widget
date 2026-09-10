from app import agent_service
from app.repositories import connections


def test_format_schema_context_includes_columns_and_relationships():
    context = connections.format_schema_context(
        {
            "tables": [
                {
                    "schema": "public",
                    "name": "orders",
                    "columns": [
                        {"name": "order_id", "type": "integer", "nullable": False, "primary_key": True},
                        {"name": "customer_id", "type": "text", "nullable": False, "primary_key": False},
                    ],
                }
            ],
            "foreign_keys": [
                {
                    "table_schema": "public",
                    "table_name": "orders",
                    "column_name": "customer_id",
                    "foreign_table_schema": "public",
                    "foreign_table_name": "customers",
                    "foreign_column_name": "customer_id",
                }
            ],
        }
    )
    assert "public.orders" in context
    assert "order_id: integer [PK, NOT NULL]" in context
    assert "orders.customer_id -> public.customers.customer_id" in context
    assert "only these permitted tables" in context


def test_run_agent_passes_selected_connection_schema_to_llm(monkeypatch):
    calls = []
    monkeypatch.setattr(
        agent_service,
        "_resolve_db_url",
        lambda *args, **kwargs: ("postgresql://test", "dbconn_northwind", {"orders"}),
    )
    monkeypatch.setattr(agent_service, "effective_provider", lambda: "mock")
    monkeypatch.setattr(
        agent_service,
        "_schema_text_for_connection",
        lambda *args, **kwargs: "Tables:\n- public.orders\n  - order_id: integer [PK]",
    )

    def plan(*args, **kwargs):
        calls.append(kwargs)
        return {"plan": {"widgets": []}, "provider": "gemini", "model": "test-model"}

    monkeypatch.setattr(agent_service, "plan_with_llm", plan)
    monkeypatch.setattr(agent_service, "_materialize_plan", lambda *args, **kwargs: ("ok", {"widgets": []}))

    _, _, meta = agent_service.run_agent(
        "고객별 주문 금액을 보여줘",
        tenant_id="tenant",
        user_id="user",
        connection_id="dbconn_northwind",
        llm_settings={"provider": "gemini", "api_key": "test-key", "model": "test-model"},
    )

    assert meta["provider"] == "gemini"
    assert calls[0]["schema_text"] == "Tables:\n- public.orders\n  - order_id: integer [PK]"
