import json
import logging
import time
import httpx
from .base import (AIProvider, RelevanceResult, EnrichmentResult,
                   RELEVANCE_SYSTEM_TPL, RELEVANCE_USER_TPL,
                   ENRICH_USER_TPL, ENRICH_NO_PROFILE_TPL,
                   DISCOVER_SYSTEM, DISCOVER_USER_TPL,
                   SUGGEST_CATEGORIES_PROMPT,
                   normalise_discovered, repair_json_array, extract_sources_from_text,
                   strip_thinking)

logger = logging.getLogger(__name__)

_CATEGORIES = [
    "Technology", "Finance", "Business", "Politics", "Science",
    "Health", "Sports", "World News", "Environment", "Other"
]


class OllamaProvider(AIProvider):
    def __init__(self, base_url: str, model: str):
        self._base_url = base_url.rstrip("/")
        self._model = model
        from .stats import record_tokens as _rt
        self._record_tokens = _rt

    def _ask(self, prompt: str, max_tokens: int = 512,
             system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        t0 = time.monotonic()
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{self._base_url}/v1/chat/completions",
                json={
                    "model": self._model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        if usage.get("completion_tokens"):
            self._record_tokens(usage["completion_tokens"], time.monotonic() - t0,
                                usage.get("prompt_tokens", 0))
        return strip_thinking(data["choices"][0]["message"]["content"].strip())

    def _ask_array(self, prompt: str, system: str | None = None) -> list:
        raw = self._ask(prompt, max_tokens=2048, system=system)
        try:
            start = raw.index("[")
            end = raw.rindex("]") + 1
            return json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError):
            pass
        try:
            return json.loads(repair_json_array(raw))
        except (ValueError, json.JSONDecodeError):
            pass
        extracted = extract_sources_from_text(raw)
        if extracted:
            return extracted
        logger.warning("Ollama array parse failed: %s", raw[:300])
        raise ValueError("Could not parse source list from Ollama response")

    def _ask_json(self, prompt: str, system: str | None = None) -> dict:
        raw = self._ask(prompt, system=system)
        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            return json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("Ollama JSON parse failed: %s", raw)
            raise ValueError(f"Invalid JSON from Ollama: {raw}") from exc

    def enrich_article(self, title, excerpt, topic_profile, categories,
                       accepted_languages=None, translation_language=None) -> EnrichmentResult:
        from app.services.ai.openai_provider import _build_translation_instruction
        cats_str = ", ".join(categories) if categories else "Other"
        trans = _build_translation_instruction(accepted_languages, translation_language)
        if topic_profile:
            system = RELEVANCE_SYSTEM_TPL.format(topic_profile=topic_profile)
            user = ENRICH_USER_TPL.format(
                title=title, excerpt=(excerpt or "(none)")[:1500],
                categories=cats_str, translation_instruction=trans,
            )
        else:
            system = None
            user = ENRICH_NO_PROFILE_TPL.format(
                title=title, excerpt=(excerpt or "(none)")[:1500],
                categories=cats_str, translation_instruction=trans,
            )
        raw = self._ask(user, max_tokens=800, system=system)
        try:
            data = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"enrich_article JSON parse failed: {raw[:200]}") from exc
        translated_title = (str(data["translated_title"]).strip()
                            if isinstance(data.get("translated_title"), str) else None)
        if topic_profile:
            score = max(0.0, min(1.0, float(data.get("score", 0.5))))
            reason = str(data.get("reason", ""))
            summary = str(data["summary"]).strip() if isinstance(data.get("summary"), str) else None
            category = str(data["category"]).strip() if isinstance(data.get("category"), str) else None
        else:
            score, reason = 0.5, ""
            summary = str(data.get("summary", "")).strip() or None
            category = str(data.get("category", "")).strip() or None
        if category and categories and category not in categories:
            category = None
        return EnrichmentResult(score=score, reason=reason, summary=summary,
                                category=category, translated_title=translated_title)

    def score_relevance(self, title, excerpt, topic_profile) -> RelevanceResult:
        system = RELEVANCE_SYSTEM_TPL.format(topic_profile=topic_profile)
        user = RELEVANCE_USER_TPL.format(
            title=title,
            excerpt=(excerpt or "(none)")[:1500],
        )
        data = self._ask_json(user, system=system)
        return RelevanceResult(
            score=max(0.0, min(1.0, float(data.get("score", 0.5)))),
            reason=str(data.get("reason", data.get("thinking", ""))),
        )

    def summarize(self, title, excerpt) -> str:
        return self._ask(
            f"Summarize in 2-3 concise, factual sentences.\nTitle: {title}\nExcerpt: {excerpt or ''}"
        )

    def categorize(self, title, excerpt, categories) -> str:
        cats = categories or _CATEGORIES
        data = self._ask_json(
            f"Classify into one of: {', '.join(cats)}.\n"
            f"Title: {title}\nExcerpt: {excerpt or ''}\n"
            f'Return JSON: {{"category": "Name"}}'
        )
        cat = data.get("category", "Other")
        return cat if cat in cats else "Other"

    def are_duplicates(self, title1, excerpt1, title2, excerpt2) -> bool:
        data = self._ask_json(
            "Do these two news articles cover the same story?\n\n"
            f"Article 1: {title1}\n{(excerpt1 or '')[:300]}\n\n"
            f"Article 2: {title2}\n{(excerpt2 or '')[:300]}\n\n"
            'Return JSON only: {"duplicate": true}'
        )
        return bool(data.get("duplicate", False))

    def suggest_keywords(self, topic_profile) -> list[str]:
        data = self._ask_json(
            f"Suggest 10 news keywords for: {topic_profile}\n"
            f'Return JSON: {{"keywords": ["k1"]}}'
        )
        return [str(k) for k in data.get("keywords", [])]

    def suggest_categories(self, topic_profile) -> list[str]:
        data = self._ask_json(SUGGEST_CATEGORIES_PROMPT.format(topic_profile=topic_profile))
        return [str(c).strip() for c in data.get("categories", []) if str(c).strip()]

    def discover_sources(self, topic_profile, accepted_languages=None) -> list[dict]:
        from app.services.ai.base import build_language_constraint
        lang = build_language_constraint(accepted_languages)
        system = DISCOVER_SYSTEM.format(language_constraint=lang)
        user = DISCOVER_USER_TPL.format(topic_profile=topic_profile)
        return normalise_discovered(self._ask_array(user, system=system))

    def recommend_sources(self, topic_profile, catalog) -> list[int]:
        if not catalog:
            return []
        catalog_text = "\n".join(
            f"ID {s['id']}: {s['name']} ({s['category']})" for s in catalog[:30]
        )
        data = self._ask_json(
            f"Profile: {topic_profile}\nSources:\n{catalog_text}\n"
            f'Return top 10 IDs. JSON: {{"ids": [1]}}'
        )
        return [int(i) for i in data.get("ids", [])]
