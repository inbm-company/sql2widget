"""Together AI through its OpenAI-compatible API."""

from .openai import OpenAIProvider


class TogetherProvider(OpenAIProvider):
    name = "together"
    base_url = "https://api.together.ai/v1"
    default_model = "Qwen/Qwen3.5-9B"
    # Together currently has no serverless embedding models.
    default_embedding_model = ""

    def embedding_payload(self, texts, dimensions):
        # Dedicated models may have fixed dimensions; request their native vectors.
        return {"model": self.embedding_model, "input": texts}

    def normalize_embedding(self, values, dimensions):
        if len(values) != dimensions:
            raise ValueError(f"together: embedding dimension must match {dimensions}")
        return super().normalize_embedding(values, dimensions)

    def embed(self, texts, dimensions):
        if not self.embedding_model:
            raise ValueError("together: embedding model is not configured; serverless embeddings are unavailable")
        return super().embed(texts, dimensions)
