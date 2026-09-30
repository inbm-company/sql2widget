"""Gemini through Google's OpenAI-compatible API."""

from .openai import OpenAIProvider


class GeminiProvider(OpenAIProvider):
    name = "gemini"
    base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
    default_model = "gemini-3.6-flash"
    default_embedding_model = "gemini-embedding-001"
