import json
import logging
from .base import (AIProvider, RelevanceResult, DISCOVER_PROMPT, RELEVANCE_PROMPT_RICH,
                   normalise_discovered, repair_json_array, extract_sources_from_text)

logger = logging.getLogger(__name__)

_CATEGORIES = [
    "Technology", "Finance", "Business", "Politics", "Science",
    "Health", "Sports", "World News", "Environment", "Other"
]


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def _ask(self, prompt: str, max_tokens: int = 512) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()

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
        except (ValueError, json.JSONDecodeError):
            pass
        extracted = extract_sources_from_text(raw)
        if extracted:
            return extracted
        logger.warning("Failed to parse JSON array from OpenAI: %s", raw[:300])
        raise ValueError("Could not parse source list from AI response")

    def _ask_json(self, prompt: str) -> dict:
        raw = self._ask(prompt)
        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            return json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("Failed to parse JSON from AI response: %s", raw)
            raise ValueError(f"Invalid JSON from AI: {raw}") from exc

    def score_relevance(self, title, excerpt, topic_profile) -> RelevanceResult:
        prompt = RELEVANCE_PROMPT_RICH.format(
            topic_profile=topic_profile,
            title=title,
            excerpt=(excerpt or "(none)")[:1500],
        )
        data = self._ask_json(prompt)
        return RelevanceResult(
            score=max(0.0, min(1.0, float(data.get("score", 0.5)))),
            reason=str(data.get("reason", data.get("thinking", ""))),
        )

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

    def discover_sources(self, topic_profile) -> list[dict]:
        return normalise_discovered(self._ask_array(DISCOVER_PROMPT.format(topic_profile=topic_profile)))

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
