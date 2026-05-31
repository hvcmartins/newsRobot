import json
import logging
from .base import AIProvider, RelevanceResult

logger = logging.getLogger(__name__)

_CATEGORIES = [
    "Technology", "Finance", "Business", "Politics", "Science",
    "Health", "Sports", "World News", "Environment", "Other",
]


class LlamaCppProvider(AIProvider):
    def __init__(self, model_path: str):
        self._model_path = model_path
        self._llm = None  # lazy-loaded on first use

    def _get_llm(self):
        if self._llm is None:
            from llama_cpp import Llama
            import os
            n_threads = os.cpu_count() or 4
            logger.info("Loading llama.cpp model from %s (threads=%d)", self._model_path, n_threads)
            self._llm = Llama(
                model_path=self._model_path,
                n_ctx=2048,
                n_threads=n_threads,
                verbose=False,
            )
        return self._llm

    def _ask(self, prompt: str) -> str:
        llm = self._get_llm()
        resp = llm.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.1,
        )
        return resp["choices"][0]["message"]["content"].strip()

    def _ask_json(self, prompt: str) -> dict:
        raw = self._ask(prompt)
        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            return json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("llama.cpp JSON parse failed: %s", raw)
            raise ValueError(f"Invalid JSON from local model: {raw}") from exc

    def score_relevance(self, title, excerpt, topic_profile) -> RelevanceResult:
        data = self._ask_json(
            f"Company profile: {topic_profile}\n"
            f"Article: {title}\n{excerpt or ''}\n"
            f"Rate relevance 0.0-1.0.\n"
            f'Return JSON only: {{"score": 0.5, "reason": "one sentence"}}'
        )
        return RelevanceResult(score=float(data.get("score", 0.5)),
                               reason=str(data.get("reason", "")))

    def summarize(self, title, excerpt) -> str:
        return self._ask(
            f"Summarize in 2-3 sentences. Be factual.\n"
            f"Title: {title}\nExcerpt: {excerpt or ''}"
        )

    def categorize(self, title, excerpt, categories) -> str:
        cats = categories or _CATEGORIES
        data = self._ask_json(
            f"Classify into one of: {', '.join(cats)}.\n"
            f"Title: {title}\nExcerpt: {excerpt or ''}\n"
            f'Return JSON only: {{"category": "Name"}}'
        )
        cat = data.get("category", "Other")
        return cat if cat in cats else "Other"

    def are_duplicates(self, title1, excerpt1, title2, excerpt2) -> bool:
        data = self._ask_json(
            f"Same story?\nA: {title1}\nB: {title2}\n"
            f'Return JSON only: {{"duplicate": false}}'
        )
        return bool(data.get("duplicate", False))

    def suggest_keywords(self, topic_profile) -> list[str]:
        data = self._ask_json(
            f"Suggest 10 news monitoring keywords for: {topic_profile}\n"
            f'Return JSON only: {{"keywords": ["k1", "k2"]}}'
        )
        return [str(k) for k in data.get("keywords", [])]

    def recommend_sources(self, topic_profile, catalog) -> list[int]:
        if not catalog:
            return []
        catalog_text = "\n".join(
            f"ID {s['id']}: {s['name']} ({s['category']})" for s in catalog[:30]
        )
        data = self._ask_json(
            f"Profile: {topic_profile}\nSources:\n{catalog_text}\n"
            f"Return top 10 relevant source IDs.\n"
            f'Return JSON only: {{"ids": [1, 2]}}'
        )
        return [int(i) for i in data.get("ids", [])]
