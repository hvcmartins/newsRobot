import logging
from .base import AIProvider
from .null import NullProvider

logger = logging.getLogger(__name__)

_provider: AIProvider | None = None


def get_ai_provider() -> AIProvider:
    global _provider
    if _provider is not None:
        return _provider
    _provider = _build_provider()
    return _provider


def _build_provider() -> AIProvider:
    from app.config import settings

    if not settings.ai_enabled or settings.ai_provider in ("none", ""):
        logger.info("AI disabled — using NullProvider")
        return NullProvider()

    provider = settings.ai_provider.lower()

    if provider == "claude":
        if not settings.ai_api_key:
            logger.warning("AI_API_KEY not set for Claude — falling back to NullProvider")
            return NullProvider()
        from .claude import ClaudeProvider
        logger.info("Using Claude AI provider (model=%s)", settings.ai_model)
        return ClaudeProvider(api_key=settings.ai_api_key, model=settings.ai_model)

    if provider == "openai":
        if not settings.ai_api_key:
            logger.warning("AI_API_KEY not set for OpenAI — falling back to NullProvider")
            return NullProvider()
        from .openai_provider import OpenAIProvider
        logger.info("Using OpenAI provider (model=%s)", settings.ai_model)
        return OpenAIProvider(api_key=settings.ai_api_key, model=settings.ai_model)

    if provider == "ollama":
        from .ollama import OllamaProvider
        logger.info("Using Ollama provider (url=%s, model=%s)",
                    settings.ai_base_url, settings.ai_model)
        return OllamaProvider(base_url=settings.ai_base_url, model=settings.ai_model)

    logger.warning("Unknown AI provider '%s' — falling back to NullProvider", provider)
    return NullProvider()


def reset_provider():
    """Force re-initialization on next call (useful after config changes)."""
    global _provider
    _provider = None
