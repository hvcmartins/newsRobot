import json
import logging
from .base import AIProvider, RelevanceResult, DISCOVER_PROMPT, normalise_discovered

logger = logging.getLogger(__name__)

_CATEGORIES = [
    "Technology", "Finance", "Business", "Politics", "Science",
    "Health", "Sports", "World News", "Environment", "Other"
]


class ClaudeProvider(AIProvider):
    def __init__(self, api_key: str, model: str):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def _ask(self, prompt: str, max_tokens: int = 512) -> str:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    def _ask_array(self, prompt: str) -> list:
        raw = self._ask(prompt, max_tokens=2048)
        try:
            start = raw.index("[")
            end = raw.rindex("]") + 1
            return json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("Failed to parse JSON array from Claude: %s", raw[:300])
            raise ValueError("Could not parse source list from Claude response") from exc

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
        prompt = (
            f"Company profile: {topic_profile}\n\n"
            f"Article title: {title}\n"
            f"Article excerpt: {excerpt or '(none)'}\n\n"
            "Rate how relevant this article is to the company (0.0 = irrelevant, "
            "1.0 = highly relevant). Be strict — only score above 0.5 if the article "
            "is clearly useful to this company.\n"
            'Return JSON only: {"score": 0.0, "reason": "one sentence"}'
        )
        data = self._ask_json(prompt)
        return RelevanceResult(
            score=float(data.get("score", 0.5)),
            reason=str(data.get("reason", "")),
        )

    def summarize(self, title, excerpt) -> str:
        prompt = (
            f"Summarize this news article in 2-3 concise sentences. "
            f"Be factual and neutral.\n\nTitle: {title}\nExcerpt: {excerpt or '(none)'}"
        )
        return self._ask(prompt)

    def categorize(self, title, excerpt, categories) -> str:
        cats = categories or _CATEGORIES
        prompt = (
            f"Classify this article into exactly one of these categories: "
            f"{', '.join(cats)}.\n\n"
            f"Title: {title}\nExcerpt: {excerpt or '(none)'}\n\n"
            f'Return JSON only: {{"category": "CategoryName"}}'
        )
        data = self._ask_json(prompt)
        cat = data.get("category", "Other")
        return cat if cat in cats else "Other"

    def are_duplicates(self, title1, excerpt1, title2, excerpt2) -> bool:
        prompt = (
            "Do these two news articles cover the same story?\n\n"
            f"Article 1: {title1}\n{excerpt1 or ''}\n\n"
            f"Article 2: {title2}\n{excerpt2 or ''}\n\n"
            'Return JSON only: {"duplicate": true}'
        )
        data = self._ask_json(prompt)
        return bool(data.get("duplicate", False))

    def suggest_keywords(self, topic_profile) -> list[str]:
        prompt = (
            f"Based on this company description, suggest 10-15 specific search keywords "
            f"for a news monitoring system. Include product names, industry terms, and "
            f"key topics.\n\nDescription: {topic_profile}\n\n"
            f'Return JSON only: {{"keywords": ["keyword1", "keyword2"]}}'
        )
        data = self._ask_json(prompt)
        return [str(k) for k in data.get("keywords", [])]

    def discover_sources(self, topic_profile) -> list[dict]:
        return normalise_discovered(self._ask_array(DISCOVER_PROMPT.format(topic_profile=topic_profile)))

    def recommend_sources(self, topic_profile, catalog) -> list[int]:
        if not catalog:
            return []
        catalog_text = "\n".join(
            f"ID {s['id']}: {s['name']} ({s['category']}) — {s.get('description', '')}"
            for s in catalog[:50]
        )
        prompt = (
            f"Company profile: {topic_profile}\n\n"
            f"Available news sources:\n{catalog_text}\n\n"
            f"Which source IDs are most relevant? Return up to 10 best matches.\n"
            f'Return JSON only: {{"ids": [1, 2, 3]}}'
        )
        data = self._ask_json(prompt)
        return [int(i) for i in data.get("ids", [])]
