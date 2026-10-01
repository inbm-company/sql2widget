"""OpenAI-compatible requests and response parsing."""

import json

from . import transport


class OpenAIProvider:
    name = "openai"
    base_url = "https://api.openai.com/v1"
    default_model = "gpt-4o-mini"
    default_embedding_model = "text-embedding-3-small"
    requires_key = True

    def __init__(self, *, api_key="", model=None, base_url=None, embedding_model=None):
        self.api_key = api_key.strip()
        self.model = (model or self.default_model).strip()
        self.base_url = transport.validate_base_url(base_url or self.base_url)
        self.embedding_model = (embedding_model or self.default_embedding_model).strip()
        if self.requires_key and not self.api_key:
            raise ValueError(f"{self.name}: API key is required")
        if not self.model:
            raise ValueError(f"{self.name}: chat model is required")

    def plan(self, system_hint, user_content, timeout=None):
        data = transport.post_json(
            self.base_url, "/chat/completions", api_key=self.api_key, **({"timeout": timeout} if timeout else {}),
            payload={
                "model": self.model, "temperature": 0.1,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_hint},
                    {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
                ],
            },
        )
        return json.loads(data["choices"][0]["message"]["content"]), data.get("usage") or {}

    def embedding_payload(self, texts, dimensions):
        return {"model": self.embedding_model, "input": texts, "dimensions": dimensions}

    def normalize_embedding(self, values, dimensions):
        values = values[:dimensions]
        if len(values) != dimensions:
            raise ValueError(f"Embedding dimension must be {dimensions}")
        norm = sum(value * value for value in values) ** 0.5
        return [value / norm for value in values] if norm else values

    def embed(self, texts, dimensions):
        if not self.embedding_model:
            raise ValueError("Local embedding model is not configured")
        data = transport.post_json(
            self.base_url, "/embeddings", api_key=self.api_key,
            payload=self.embedding_payload(texts, dimensions),
        )
        ordered = sorted(enumerate(data["data"]), key=lambda pair: pair[1].get("index", pair[0]))
        if [item.get("index", position) for position, item in ordered] != list(range(len(texts))):
            raise ValueError("Embedding response did not cover every question")
        return [self.normalize_embedding(item["embedding"], dimensions) for _, item in ordered]
