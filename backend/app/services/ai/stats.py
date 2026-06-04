"""Thread-safe rolling stats for AI inference — tokens/s, seconds/article, usage history."""
import collections
import datetime
import threading
import time

_lock = threading.Lock()
# Rolling window of (completion_tokens, elapsed_seconds) — used for live tps display
_token_samples: collections.deque = collections.deque(maxlen=10)
_article_samples: collections.deque = collections.deque(maxlen=10)

# Full call log: (unix_ts, tokens_in, tokens_out) per API call.
# 50k entries ≈ months at typical enrichment rates; a few days at burst speed.
_call_log: collections.deque = collections.deque(maxlen=50_000)


def record_tokens(completion_tokens: int, elapsed_seconds: float,
                  input_tokens: int = 0) -> None:
    if completion_tokens > 0 and elapsed_seconds > 0:
        ts = time.time()
        with _lock:
            _token_samples.append((completion_tokens, elapsed_seconds))
            _call_log.append((ts, input_tokens, completion_tokens))


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


def get_usage_buckets(bucket_seconds: int, n_buckets: int) -> list[dict]:
    """Return n_buckets aligned time buckets with call counts and token totals.

    Buckets run from (now - bucket_seconds*n_buckets) to now in steps of
    bucket_seconds.  Each bucket's `ts` is its start time as a UTC ISO string.
    """
    now = time.time()
    window_start = now - bucket_seconds * n_buckets
    buckets = [
        {"ts": datetime.datetime.utcfromtimestamp(
             window_start + i * bucket_seconds).isoformat() + "Z",
         "calls": 0, "tokens_in": 0, "tokens_out": 0}
        for i in range(n_buckets)
    ]
    with _lock:
        for ts, tin, tout in _call_log:
            if ts < window_start:
                continue
            idx = int((ts - window_start) / bucket_seconds)
            if 0 <= idx < n_buckets:
                buckets[idx]["calls"] += 1
                buckets[idx]["tokens_in"] += tin
                buckets[idx]["tokens_out"] += tout
    return buckets


def get_usage_today() -> dict:
    """Total calls and tokens since UTC midnight today (in-memory only)."""
    today_midnight = datetime.datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0
    ).timestamp()
    calls = tokens_in = tokens_out = 0
    with _lock:
        for ts, tin, tout in _call_log:
            if ts >= today_midnight:
                calls += 1
                tokens_in += tin
                tokens_out += tout
    return {"calls": calls, "tokens_in": tokens_in, "tokens_out": tokens_out}
