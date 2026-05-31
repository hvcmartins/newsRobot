import json
import logging
import httpx
from .base import AIProvider, RelevanceResult, DISCOVER_PROMPT, normalise_discovered, repair_json_array

logger = logging.getLogger(__name__)

_CATEGORIES = [
    "Technology", "Finance", "Business", "Politics", "Science",
    "Health", "Sports", "World News", "Environment", "Other"
]


class OllamaProvider(AIProvider):
    def __init__(self, base_url: str, model: str):
        self._base_url = base_url.rstrip("/")
        self._model = model

    def _ask(self, prompt: str, max_tokens: int = 512) -> str:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{self._base_url}/v1/chat/completions",
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def _ask_array(self, prompt: str) -> list:
        raw = self._ask(prompt, max_tokens=2048)
        try:
            start = raw.index("[")
            end = raw.rindex("]") + 1
            return json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError):
            pass
        try:
            return json.loads(repair_json_array(raw))
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("Ollama array parse failed: %s", raw[:300])
            raise ValueError("Could not parse source list from Ollama response") from exc

    def _ask_json(self, prompt: str) -> dict:
        raw = self._ask(prompt)
        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            return json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("Ollama JSON parse failed: %s", raw)
            raise ValueError(f"Invalid JSON from Ollama: {raw}") from exc

    def score_relevance(self, title, excerpt, topic_profile) -> RelevanceResult:
        data = self._ask_json(
            f"Company profile: {topic_profile}\nTitle: {title}\nExcerpt: {excerpt or ''}\n"
            f"Rate relevance 0.0-1.0.\nReturn JSON: {{\"score\": 0.0, \"reason\": \"\"}}"
        )
        return RelevanceResult(score=float(data.get("score", 0.5)),
                               reason=str(data.get("reason", "")))

    def summarize(self, title, excerpt) -> str:
        return self._ask(
            f"Summarize in 2-3 sentences.\nTitle: {title}\nExcerpt: {excerpt or ''}"
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
            f"Same story?\nA: {title1}\nB: {title2}\n"
            f'Return JSON: {{"duplicate": false}}'
        )
        return bool(data.get("duplicate", False))

    def suggest_keywords(self, topic_profile) -> list[str]:
        data = self._ask_json(
            f"Suggest 10 news keywords for: {topic_profile}\n"
            f'Return JSON: {{"keywords": ["k1"]}}'
        )
        return [str(k) for k in data.get("keywords", [])]

    def discover_sources(self, topic_profile) -> list[dict]:
        return normalise_discovered(self._ask_array(DISCOVER_PROMPT.format(topic_profile=topic_profile)))

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
