import json
import logging
import time
import threading
from .base import (AIProvider, RelevanceResult,
                   DISCOVER_PROMPT_SHORT, SUGGEST_CATEGORIES_PROMPT,
                   normalise_discovered, repair_json_array, extract_sources_from_text,
                   strip_thinking)

logger = logging.getLogger(__name__)

_CATEGORIES = [
    "Technology", "Finance", "Business", "Politics", "Science",
    "Health", "Sports", "World News", "Environment", "Other",
]


class LlamaCppProvider(AIProvider):
    def __init__(self, model_path: str, cpu_limit_percent: int = 80,
                 n_gpu_layers: int = -1):
        self._model_path = model_path
        self._cpu_limit_percent = max(25, min(100, cpu_limit_percent))
        self._n_gpu_layers = n_gpu_layers
        self._llm = None
        self._load_lock = threading.Lock()   # prevents concurrent model loads (OOM)
        self._infer_lock = threading.Lock()  # llama_cpp is not thread-safe for inference

    def _get_llm(self):
        # Double-checked locking: cheap check outside, safe load inside
        if self._llm is None:
            with self._load_lock:
                if self._llm is None:
                    from llama_cpp import Llama
                    import os
                    total = os.cpu_count() or 4
                    n_threads = max(1, round(total * self._cpu_limit_percent / 100))
                    logger.info(
                        "Loading llama.cpp model from %s (threads=%d/%d, cpu=%d%%, gpu_layers=%d)",
                        self._model_path, n_threads, total,
                        self._cpu_limit_percent, self._n_gpu_layers,
                    )
                    self._llm = Llama(
                        model_path=self._model_path,
                        n_ctx=8192,
                        n_threads=n_threads,
                        n_gpu_layers=self._n_gpu_layers,
                        verbose=False,
                    )
        return self._llm

    def _ask(self, prompt: str, max_tokens: int = 512) -> str:
        from .stats import record_tokens
        llm = self._get_llm()
        # Serialize all inference calls — llama_cpp's Llama object is not
        # thread-safe; concurrent calls from the enrichment thread pool
        # cause segfaults that crash the entire container.
        t0 = time.monotonic()
        with self._infer_lock:
            resp = llm.create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.1,
            )
        usage = resp.get("usage", {})
        if usage.get("completion_tokens"):
            record_tokens(usage["completion_tokens"], time.monotonic() - t0)
        # Strip <think>…</think> blocks (Qwen3, DeepSeek-R1, etc.)
        return strip_thinking(resp["choices"][0]["message"]["content"].strip())

    def _ask_json(self, prompt: str) -> dict:
        raw = self._ask(prompt)
        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            return json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("llama.cpp JSON parse failed: %s", raw)
            raise ValueError(f"Invalid JSON from local model: {raw}") from exc

    # Multiple-choice labels → (score, reason) — small models pick letters
    # far more reliably than generating arbitrary floating-point numbers.
    _RELEVANCE_CHOICES = {
        'A': (0.90, "Directly relevant to the company's core business"),
        'B': (0.70, "Useful industry or market context for the company"),
        'C': (0.40, "Loosely related — tangential connection"),
        'D': (0.10, "Not relevant to the company"),
    }

    def score_relevance(self, title, excerpt, topic_profile) -> RelevanceResult:
        profile_short = (topic_profile or "")[:250]
        excerpt_short = (excerpt or "")[:150]
        # /no_think suppresses Qwen3 reasoning mode — without it the thinking
        # block consumes all of max_tokens=8 before the answer letter is generated.
        prompt = (
            f"Company profile: {profile_short}\n\n"
            f"News article:\nTitle: {title[:150]}\n{excerpt_short}\n\n"
            "How relevant is this article to the company? Choose ONE letter:\n"
            "A - Essential: directly about their industry, products, or competitors\n"
            "B - Useful: relevant market, regulatory, or technology news\n"
            "C - Marginal: only loosely related\n"
            "D - Irrelevant: unrelated topic\n\n"
            "Reply with exactly one letter (A, B, C, or D): /no_think"
        )
        raw = self._ask(prompt, max_tokens=16).strip()
        logger.debug("llama.cpp relevance raw: %r", raw[:30])

        # Match the first A/B/C/D in the response
        import re as _re
        m = _re.search(r'\b([ABCD])\b', raw.upper())
        if m:
            letter = m.group(1)
            score, reason = self._RELEVANCE_CHOICES[letter]
            logger.info("llama.cpp relevance: %s → %.2f", letter, score)
            return RelevanceResult(score=score, reason=reason)

        logger.warning("llama.cpp: could not parse relevance letter from %r — defaulting 0.5", raw[:50])
        return RelevanceResult(score=0.5, reason="")

    def enrich_article(self, title, excerpt, topic_profile, categories,
                       accepted_languages=None, translation_language=None):
        from app.services.ai.openai_provider import _build_translation_instruction
        from app.services.ai.base import (ENRICH_USER_TPL, ENRICH_NO_PROFILE_TPL,
                                          RELEVANCE_SYSTEM_TPL, EnrichmentResult)
        cats_str = ", ".join(categories) if categories else "Other"
        trans = _build_translation_instruction(accepted_languages, translation_language)
        if topic_profile:
            prompt = (RELEVANCE_SYSTEM_TPL.format(topic_profile=topic_profile) + "\n\n"
                      + ENRICH_USER_TPL.format(
                          title=title, excerpt=(excerpt or "(none)")[:800],
                          categories=cats_str, translation_instruction=trans))
        else:
            prompt = ENRICH_NO_PROFILE_TPL.format(
                title=title, excerpt=(excerpt or "(none)")[:800],
                categories=cats_str, translation_instruction=trans)
        try:
            data = self._ask_json(prompt)
        except ValueError:
            # JSON parse failed — fall back to individual calls (no translation)
            return super().enrich_article(title, excerpt, topic_profile, categories)

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

    def suggest_categories(self, topic_profile) -> list[str]:
        data = self._ask_json(SUGGEST_CATEGORIES_PROMPT.format(
            topic_profile=(topic_profile or "")[:600]
        ))
        return [str(c).strip() for c in data.get("categories", []) if str(c).strip()]

    def discover_sources(self, topic_profile, accepted_languages=None) -> list[dict]:
        from app.services.ai.base import build_language_constraint
        lang = build_language_constraint(accepted_languages)
        # Use a shorter prompt and more tokens so the response isn't truncated
        prompt = DISCOVER_PROMPT_SHORT.format(topic_profile=topic_profile,
                                              language_constraint=lang)
        raw = self._ask(prompt, max_tokens=2048)
        logger.debug("llama.cpp discover raw output: %s", raw[:500])

        # Attempt 1: standard JSON parse
        try:
            start = raw.index("[")
            end = raw.rindex("]") + 1
            sources = normalise_discovered(json.loads(raw[start:end]))
            if sources:
                return sources
        except (ValueError, json.JSONDecodeError):
            pass

        # Attempt 2: bracket-repair then parse
        try:
            sources = normalise_discovered(json.loads(repair_json_array(raw)))
            if sources:
                return sources
        except (ValueError, json.JSONDecodeError):
            pass

        # Attempt 3: regex extraction — recovers sources from truncated/mangled output
        sources = extract_sources_from_text(raw)
        if sources:
            logger.info("llama.cpp discover: recovered %d sources via regex extractor", len(sources))
            return sources

        logger.warning("llama.cpp discover failed to parse output: %s", raw[:400])
        raise ValueError("Could not parse source list from local model")

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
