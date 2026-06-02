"""Thread-safe rolling stats for AI inference — tokens/s and seconds/article."""
import collections
import threading

_lock = threading.Lock()
# Rolling window of (completion_tokens, elapsed_seconds) per AI call
_token_samples: collections.deque = collections.deque(maxlen=10)
# Rolling window of elapsed seconds per enriched article
_article_samples: collections.deque = collections.deque(maxlen=10)


def record_tokens(completion_tokens: int, elapsed_seconds: float) -> None:
    if completion_tokens > 0 and elapsed_seconds > 0:
        with _lock:
            _token_samples.append((completion_tokens, elapsed_seconds))


def record_article(elapsed_seconds: float) -> None:
    if elapsed_seconds > 0:
        with _lock:
            _article_samples.append(elapsed_seconds)


def get_stats() -> dict:
    with _lock:
        tps: float | None = None
        if _token_samples:
            total_tok = sum(t for t, _ in _token_samples)
            total_sec = sum(s for _, s in _token_samples)
            if total_sec > 0:
                tps = round(total_tok / total_sec, 1)

        secs_per_article: float | None = None
        if _article_samples:
            secs_per_article = round(sum(_article_samples) / len(_article_samples), 1)

    return {
        "tokens_per_second": tps,
        "seconds_per_article": secs_per_article,
    }
