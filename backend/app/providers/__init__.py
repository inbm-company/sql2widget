"""Resolve provider-specific credentials and defaults."""

from app import config
from .gemini import GeminiProvider
from .local import LocalProvider
from .openai import OpenAIProvider

ALIASES = {"google": "gemini", "openai_compatible": "openai", "compatible": "openai"}
PROVIDERS = {"openai": OpenAIProvider, "gemini": GeminiProvider, "local": LocalProvider}


def provider_name(value):
    name = (value or "mock").lower()
    return ALIASES.get(name, name)


def resolve_provider(*, runtime_provider=None, runtime_api_key=None, runtime_model=None,
                     runtime_base_url=None, runtime_embedding_model=None):
    name = provider_name(runtime_provider or config.LLM_PROVIDER)
    provider_class = PROVIDERS.get(name)
    if provider_class is None:
        raise ValueError("No AI provider configured" if name == "mock" else "Unsupported AI provider")
    use_server = not runtime_provider or name == provider_name(config.LLM_PROVIDER)
    use_server_key = use_server and (
        name == "gemini" or not runtime_base_url
        or runtime_base_url.rstrip("/") == config.LLM_BASE_URL.rstrip("/")
    )
    embedding_model = runtime_embedding_model
    if embedding_model is None and use_server:
        embedding_model = config.LLM_EMBEDDING_MODEL or None
    return provider_class(
        api_key=runtime_api_key or (config.LLM_API_KEY if use_server_key else ""),
        model=runtime_model or (config.LLM_MODEL if use_server and name != "gemini" else None),
        base_url=(runtime_base_url if name in {"local", "openai"} else None)
            or (config.LLM_BASE_URL if use_server and name != "gemini" else None),
        embedding_model=embedding_model,
    )
