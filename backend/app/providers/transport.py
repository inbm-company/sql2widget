"""HTTP transport shared by OpenAI-compatible providers."""

from urllib.parse import urlsplit

import httpx


def validate_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("Base URL must be an HTTP(S) URL without credentials, query or fragment")
    return value.rstrip("/")


def post_json(base_url, path, *, api_key, payload, timeout=60.0):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{validate_base_url(base_url)}{path}", headers=headers, json=payload,
        )
        response.raise_for_status()
        return response.json()
