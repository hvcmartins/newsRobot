import json
import logging
import re
import time
from .base import (AIProvider, RelevanceResult, EnrichmentResult,
                   RELEVANCE_SYSTEM_TPL, RELEVANCE_USER_TPL,
                   ENRICH_USER_TPL, ENRICH_NO_PROFILE_TPL,
                   DISCOVER_SYSTEM, DISCOVER_USER_TPL,
                   SUGGEST_CATEGORIES_PROMPT,
                   normalise_discovered, repair_json_array, extract_sources_from_text,
                   strip_thinking)
from .stats import record_tokens

logger = logging.getLogger(__name__)

_CATEGORIES = [
    "Technology", "Finance", "Business", "Politics", "Science",
    "Health", "Sports", "World News", "Environment", "Other"
]


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str, base_url: str | None = None,
                 extra_body: dict | None = None):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._extra_body = extra_body or {}
        # Append /no_think to every prompt when enable_thinking=False is requested.
        # Works at the model level (Qwen3 instruction tuning) even if the server
        # ignores the enable_thinking flag in extra_body.
        self._no_think = self._extra_body.get("enable_thinking") is False

    def _ask(self, prompt: str, max_tokens: int = 512,
             system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        p = prompt + "\n/no_think" if self._no_think else prompt
        messages.append({"role": "user", "content": p})
        t0 = time.monotonic()
        resp = self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=messages,
            **({"extra_body": self._extra_body} if self._extra_body else {}),
        )
        if resp.usage:
            record_tokens(resp.usage.completion_tokens, time.monotonic() - t0)
        # Strip <think>…</think> reasoning blocks (Qwen3, DeepSeek-R1, etc.)
        return strip_thinking(resp.choices[0].message.content.strip())

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
        logger.warning("Failed to parse JSON array from OpenAI: %s", raw[:300])
        raise ValueError("Could not parse source list from AI response")

    def _ask_json(self, prompt: str, system: str | None = None) -> dict:
        raw = self._ask(prompt, system=system)
        cleaned = re.sub(r'```(?:json)?\s*', '', raw).strip()
        try:
            start = cleaned.index("{")
            end = cleaned.rindex("}") + 1
            return json.loads(cleaned[start:end])
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("Failed to parse JSON from AI response: %r", raw[:600])
            raise ValueError(f"Invalid JSON from AI: {cleaned[:300]}") from exc

    def enrich_article(self, title, excerpt, topic_profile, categories) -> EnrichmentResult:
        cats_str = ", ".join(categories) if categories else "Other"
        if topic_profile:
            system = RELEVANCE_SYSTEM_TPL.format(topic_profile=topic_profile)
            user = ENRICH_USER_TPL.format(
                title=title, excerpt=(excerpt or "(none)")[:1500], categories=cats_str,
            )
        else:
            system = None
            user = ENRICH_NO_PROFILE_TPL.format(
                title=title, excerpt=(excerpt or "(none)")[:1500], categories=cats_str,
            )
        raw = self._ask(user, max_tokens=800, system=system)
        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        cleaned = re.sub(r'```(?:json)?\s*', '', raw).strip()
        try:
            data = json.loads(cleaned[cleaned.index("{"):cleaned.rindex("}") + 1])
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("enrich_article raw response: %r", raw[:600])
            raise ValueError(f"enrich_article JSON parse failed: {cleaned[:300]}") from exc
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
        return EnrichmentResult(score=score, reason=reason, summary=summary, category=category)

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
            f"Same story?\nArticle 1: {title1}\n{excerpt1 or ''}\n\n"
            f"Article 2: {title2}\n{excerpt2 or ''}\n"
            f'Return JSON: {{"duplicate": true}}'
        )
        return bool(data.get("duplicate", False))

    def suggest_keywords(self, topic_profile) -> list[str]:
        data = self._ask_json(
            f"Suggest 10-15 news monitoring keywords for: {topic_profile}\n"
            f'Return JSON: {{"keywords": ["k1"]}}'
        )
        return [str(k) for k in data.get("keywords", [])]

    def suggest_categories(self, topic_profile) -> list[str]:
        data = self._ask_json(SUGGEST_CATEGORIES_PROMPT.format(topic_profile=topic_profile))
        return [str(c).strip() for c in data.get("categories", []) if str(c).strip()]

    def discover_sources(self, topic_profile) -> list[dict]:
        user = DISCOVER_USER_TPL.format(topic_profile=topic_profile)
        return normalise_discovered(self._ask_array(user, system=DISCOVER_SYSTEM))

    def recommend_sources(self, topic_profile, catalog) -> list[int]:
        if not catalog:
            return []
        catalog_text = "\n".join(
            f"ID {s['id']}: {s['name']} ({s['category']})" for s in catalog[:50]
        )
        data = self._ask_json(
            f"Profile: {topic_profile}\nSources:\n{catalog_text}\n"
            f"Return up to 10 best IDs.\nReturn JSON: {{\"ids\": [1]}}"
        )
        return [int(i) for i in data.get("ids", [])]
