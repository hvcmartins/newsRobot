import logging
from .base import AIProvider
from .null import NullProvider

logger = logging.getLogger(__name__)

_provider: AIProvider | None = None

_DEFAULT_MODELS = {
    "claude":     "claude-haiku-4-5-20251001",
    "openai":     "gpt-4o-mini",
    "perplexity": "llama-3.1-sonar-small-128k-online",
    "gemini":     "gemini-2.5-flash",
    "ollama":     "llama3.2",
}

# Providers that use OpenAI-compatible APIs — just different base URLs
_OPENAI_COMPATIBLE_BASE_URLS = {
    "perplexity": "https://api.perplexity.ai",
    "gemini":     "https://generativelanguage.googleapis.com/v1beta/openai/",
}


def get_ai_provider(db=None) -> AIProvider:
    global _provider
    if _provider is not None:
        return _provider
    _provider = _build_provider(db)
    return _provider


def reset_provider():
    """Force re-initialization on next call — call this after saving AI config."""
    global _provider
    _provider = None


def _build_provider(db=None) -> AIProvider:
    config = _load_config(db)

    if config is None or not config.is_enabled or config.provider in ("none", "", None):
        logger.info("AI disabled — using NullProvider")
        return NullProvider()

    name = config.provider.lower()
    key = config.api_key
    model = config.model or _DEFAULT_MODELS.get(name, "")

    if name == "claude":
        if not key:
            logger.warning("Claude selected but no API key — NullProvider")
            return NullProvider()
        from .claude import ClaudeProvider
        logger.info("AI: Claude (model=%s)", model)
        return ClaudeProvider(api_key=key, model=model)

    if name in ("openai", "perplexity", "gemini"):
        if not key:
            logger.warning("%s selected but no API key — NullProvider", name)
            return NullProvider()
        from .openai_provider import OpenAIProvider
        base_url = config.base_url or _OPENAI_COMPATIBLE_BASE_URLS.get(name)
        logger.info("AI: %s (model=%s, base_url=%s)", name, model, base_url)
        return OpenAIProvider(api_key=key, model=model, base_url=base_url)

    if name == "llamacpp":
        try:
            import llama_cpp  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "llama-cpp-python is not installed in this container. "
                "Rebuild the Docker image to include it."
            )
        from .local_models import model_path, get_status
        mid = config.local_model_id or "llama-3.2-3b"
        status = get_status(mid)
        if status.get("status") != "ready":
            raise RuntimeError(
                f"Model '{mid}' is not downloaded yet (status: {status.get('status')}). "
                "Go to AI Settings and download the model first."
            )
        p = model_path(mid)
        cpu_pct = getattr(config, 'cpu_limit_percent', 80) or 80
        from .llamacpp_provider import LlamaCppProvider
        logger.info("AI: llama.cpp (model=%s, cpu_limit=%d%%)", mid, cpu_pct)
        return LlamaCppProvider(model_path=str(p), cpu_limit_percent=cpu_pct)

    if name == "ollama":
        from .ollama import OllamaProvider
        base_url = config.base_url or "http://localhost:11434"
        logger.info("AI: Ollama (url=%s, model=%s)", base_url, model)
        return OllamaProvider(base_url=base_url, model=model)

    logger.warning("Unknown AI provider '%s' — NullProvider", name)
    return NullProvider()


def _load_config(db=None):
    try:
        from app.models.ai_config import AIConfig
        if db is not None:
            return db.query(AIConfig).first()
        from app.database import SessionLocal
        session = SessionLocal()
        try:
            return session.query(AIConfig).first()
        finally:
            session.close()
    except Exception as exc:
        logger.warning("Could not load AI config: %s", exc)
        return None
