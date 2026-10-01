"""로컬(OpenAI 호환) 서버의 모델 목록 조회."""
from __future__ import annotations

from urllib.parse import urlsplit

import httpx

TIMEOUT_SECONDS = 5.0


class LocalModelsError(Exception):
    """모델 목록을 가져오지 못했을 때 사용자에게 보여줄 메시지를 담는다."""


def list_models(base_url: str, api_key: str = "") -> list[str]:
    """`{base_url}/models`를 호출해 모델 id를 정렬해 반환한다."""
    parts = urlsplit((base_url or "").strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise LocalModelsError("Base URL은 http:// 또는 https:// 로 시작해야 합니다.")
    url = f"{base_url.strip().rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        res = httpx.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
        res.raise_for_status()
        items = res.json().get("data")
    except httpx.HTTPStatusError as exc:
        raise LocalModelsError(f"모델 목록 요청이 실패했습니다 (HTTP {exc.response.status_code}). Base URL과 API key를 확인하세요.") from exc
    except httpx.RequestError as exc:
        raise LocalModelsError("로컬 서버에 연결하지 못했습니다. 서버 실행 여부와 Base URL을 확인하세요.") from exc
    except ValueError as exc:
        raise LocalModelsError("모델 목록 응답이 OpenAI 호환 형식이 아닙니다.") from exc
    if not isinstance(items, list):
        raise LocalModelsError("모델 목록 응답이 OpenAI 호환 형식이 아닙니다.")
    return sorted({m["id"] for m in items if isinstance(m, dict) and isinstance(m.get("id"), str)})
