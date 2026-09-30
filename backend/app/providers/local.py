"""Local model servers exposing an OpenAI-compatible API."""

from .openai import OpenAIProvider


class LocalProvider(OpenAIProvider):
    name = "local"
    base_url = "http://host.docker.internal:11434/v1"
    default_model = ""
    default_embedding_model = ""
    requires_key = False

    def embedding_payload(self, texts, dimensions):
        # Local models usually have fixed dimensions; do not assume truncation support.
        return {"model": self.embedding_model, "input": texts}

    def normalize_embedding(self, values, dimensions):
        if len(values) != dimensions:
            raise ValueError(f"Local embedding dimension must match CHAT_EMBEDDING_DIM={dimensions}")
        return super().normalize_embedding(values, dimensions)
