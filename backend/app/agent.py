"""Widget artifact sanitization shared by the LLM planning path."""

from __future__ import annotations

import secrets
from typing import Any

from app.config import ALLOWED_COMPONENTS


def _wid(prefix: str = "wgt") -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def _aid() -> str:
    return f"art_{secrets.token_hex(6)}"


def sanitize_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    widgets = []
    for w in artifact.get("widgets") or []:
        component = w.get("component")
        if component not in ALLOWED_COMPONENTS:
            component = "DataTable"
            if "columns" not in (w.get("props") or {}):
                w = {
                    **w,
                    "props": {
                        "columns": [{"key": "info", "label": "Info"}],
                        "rows": [{"info": "Unsupported component fell back to table"}],
                    },
                }
        widgets.append({**w, "component": component, "widget_id": w.get("widget_id") or _wid()})
    return {**artifact, "artifact_id": artifact.get("artifact_id") or _aid(), "widgets": widgets}
