"""Search the web for RSS/Atom feeds relevant to a topic profile.

Used by the catalog discover endpoint to augment AI-only suggestions with
sources actually found on the internet via DuckDuckGo HTML search.
"""
import logging
import re
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

_SKIP_DOMAINS = {
    "amazon.com", "youtube.com", "wikipedia.org", "facebook.com",
    "twitter.com", "instagram.com", "linkedin.com", "reddit.com",
    "tiktok.com", "pinterest.com", "google.com", "apple.com",
}


def _load_search_creds() -> tuple[str, dict] | None:
    """Return (provider, kwargs) for the best available search backend, or None."""
    try:
        from app.database import SessionLocal
        from app.models.ai_config import AIConfig
        db = SessionLocal()
        try:
            cfg = db.query(AIConfig).first()
            if cfg:
                if cfg.serper_api_key:
                    return "serper", {"api_key": cfg.serper_api_key}
                if cfg.google_search_api_key and cfg.google_search_cx:
                    return "google", {"api_key": cfg.google_search_api_key,
                                      "cx": cfg.google_search_cx}
        finally:
            db.close()
    except Exception as exc:
        logger.debug("Could not load search creds: %s", exc)
    return None


def _serper_search(query: str, api_key: str) -> list[str]:
    """Google Search results via Serper.dev."""
    resp = httpx.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": 10},
        timeout=10,
    )
    resp.raise_for_status()
    urls: list[str] = []
    for item in resp.json().get("organic", []):
        link = item.get("link", "")
        if link.startswith("http"):
            netloc = urlparse(link).netloc.replace("www.", "")
            if netloc not in _SKIP_DOMAINS:
                urls.append(link)
    return urls


def _google_search(query: str, api_key: str, cx: str) -> list[str]:
    """Google Custom Search JSON API (legacy — requires existing PSE engine)."""
    resp = httpx.get(
        "https://www.googleapis.com/customsearch/v1",
        params={"key": api_key, "cx": cx, "q": query, "num": 10},
        timeout=10,
    )
    resp.raise_for_status()
    urls: list[str] = []
    for item in resp.json().get("items", []):
        link = item.get("link", "")
        if link.startswith("http"):
            netloc = urlparse(link).netloc.replace("www.", "")
            if netloc not in _SKIP_DOMAINS:
                urls.append(link)
    return urls


def _ai_search_queries(profile: str) -> list[str] | None:
    """Ask the AI to generate one targeted search query per topic area in the profile."""
    try:
        from app.services.ai.factory import get_ai_provider
        from app.services.ai.null import NullProvider
        ai = get_ai_provider()
        if isinstance(ai, NullProvider):
            return None

        prompt = (
            "You are building search queries to find RSS news feeds.\n"
            "The profile below has multiple topic sections. Generate ONE short search query "
            "per section (2-4 words each), covering as many sections as possible (up to 8 queries).\n\n"
            "Rules:\n"
            "- Each query must be specific: use organisation names, country names, or exact topics\n"
            "- Do NOT include the words 'news', 'RSS', or 'feed' — they will be added automatically\n"
            "- Do NOT use generic terms like 'information', 'coverage', 'embassy', 'updates'\n"
            "- Prefer internationally recognised names (e.g. 'Timor-Leste', 'ASEAN', 'CPLP', 'UNESCO')\n\n"
            f"Profile:\n{profile[:1200]}\n\n"
            'Return JSON only: {"queries": ["Timor-Leste politics", "ASEAN summits", "EU ASEAN policy", "OACPS ACP", "CPLP lusophone", "SIDS climate finance", "UNESCO cultural heritage", "Brussels diplomacy"]}'
        )
        if hasattr(ai, '_ask_json'):
            data = ai._ask_json(prompt)
            queries = [str(q).strip() for q in data.get("queries", []) if str(q).strip()]
            # Strip any accidental "news"/"RSS"/"feed" the model added anyway
            cleaned = []
            for q in queries:
                q = re.sub(r'\b(news|rss|feed)\b', '', q, flags=re.IGNORECASE).strip()
                q = re.sub(r'\s{2,}', ' ', q).strip(' ,')
                if q:
                    cleaned.append(q)
            if cleaned:
                logger.info("AI generated %d search queries: %s", len(cleaned), cleaned)
                return cleaned[:8]
    except Exception as exc:
        logger.debug("AI query generation failed: %s", exc)
    return None


def web_search_feeds(topic_profile: str, max_results: int = 12) -> list[dict]:
    """Return RSS feeds found via web search for the topic profile.

    Priority: Serper.dev → Google Custom Search → DuckDuckGo.
    Uses AI to generate one targeted query per topic section; falls back
    to proper-noun extraction. Returns empty list on failure.
    """
    creds = _load_search_creds()
    if creds:
        provider, kwargs = creds
        logger.info("Source discovery: using %s", provider)
    else:
        logger.info("Source discovery: using DuckDuckGo (add a Serper.dev key in AI Settings for better results)")

    queries = _ai_search_queries(topic_profile) or _build_queries(topic_profile)
    page_urls: set[str] = set()

    for q in queries[:8]:
        search_q = f"{q} RSS feed"
        try:
            if creds and provider == "serper":
                hits = _serper_search(search_q, **kwargs)
            elif creds and provider == "google":
                hits = _google_search(search_q, **kwargs)
            else:
                hits = _ddg_search(search_q)
            page_urls.update(hits[:6])
        except Exception as exc:
            logger.debug("Search failed for %r: %s", search_q, exc)

    results: list[dict] = []
    seen_feed_urls: set[str] = set()

    with httpx.Client(
        timeout=httpx.Timeout(8.0),
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; NewsRobot/1.0)"},
    ) as client:
        for page_url in list(page_urls)[:14]:
            try:
                for feed in _find_feeds(client, page_url):
                    if feed["url"] not in seen_feed_urls:
                        seen_feed_urls.add(feed["url"])
                        results.append(feed)
            except Exception as exc:
                logger.debug("Feed check failed for %s: %s", page_url, exc)
            if len(results) >= max_results:
                break

    logger.info("Web feed search found %d feeds for profile", len(results))
    return results[:max_results]


def _build_queries(profile: str) -> list[str]:
    """Fallback query builder: extract capitalised phrases and proper nouns."""
    # Prefer capitalised words (proper nouns, place names, organisations)
    proper = re.findall(r'\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*\b', profile)
    seen: set[str] = set()
    unique = [p for p in proper if p.lower() not in seen and not seen.add(p.lower())]  # type: ignore[func-returns-value]

    # Build queries from the top proper nouns — use them as-is, not word-paired
    queries = [p for p in unique[:4]]

    if not queries:
        # Last resort: pick longest uncommon lowercase words
        stopwords = {
            "the","and","for","with","that","this","have","from","they","their",
            "which","will","about","also","more","into","when","each","both","over",
            "news","information","coverage","needs","embassy","country",
        }
        words = re.findall(r'\b[a-z]{5,}\b', profile.lower())
        queries = list(dict.fromkeys(w for w in words if w not in stopwords))[:4]

    return queries if queries else ["international news"]


def _ddg_search(query: str) -> list[str]:
    resp = httpx.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query, "b": ""},
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.5",
        },
        timeout=12,
        follow_redirects=True,
    )
    resp.raise_for_status()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "html.parser")

    urls: list[str] = []
    for a in soup.select("a.result__url, a.result__a"):
        href = a.get("href", "")
        if href.startswith("http") and "duckduckgo.com" not in href:
            urls.append(href)

    # Fallback: parse uddg= redirect links
    for a in soup.select("a[href*='uddg=']"):
        href = a.get("href", "")
        try:
            from urllib.parse import parse_qs, urlparse as _up
            target = parse_qs(_up(href).query).get("uddg", [""])[0]
            if target.startswith("http"):
                urls.append(target)
        except Exception:
            pass

    seen: set[str] = set()
    result: list[str] = []
    for u in urls:
        netloc = urlparse(u).netloc.replace("www.", "")
        if u not in seen and netloc not in _SKIP_DOMAINS:
            seen.add(u)
            result.append(u)
    return result[:10]


def _find_feeds(client: httpx.Client, url: str) -> list[dict]:
    low = url.lower()
    if any(low.endswith(x) for x in (".xml", "/feed", "/rss", "/rss.xml", "/atom.xml", "/feed.xml")):
        try:
            r = client.head(url, timeout=5)
            if r.status_code < 400:
                return [_make_source(url, _url_to_name(url), "Direct feed URL")]
        except Exception:
            pass
        return []

    try:
        resp = client.get(url, timeout=7)
    except Exception:
        return []

    ct = resp.headers.get("content-type", "")
    if any(t in ct for t in ("rss", "atom", "xml")):
        return [_make_source(url, _url_to_name(url), "Feed content-type")]

    if "html" not in ct:
        return []

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "html.parser")

    feeds: list[dict] = []
    for tag in soup.find_all("link", rel="alternate"):
        t = tag.get("type", "")
        if "rss" in t or "atom" in t:
            href = tag.get("href", "")
            if href:
                feed_url = urljoin(url, href)
                title = tag.get("title", "") or _url_to_name(feed_url)
                feeds.append(_make_source(feed_url, title, f"Feed link on {urlparse(url).netloc}"))

    if not feeds:
        base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        for path in ("/feed", "/rss.xml", "/feed.xml", "/atom.xml", "/rss"):
            feed_url = base + path
            try:
                r = client.head(feed_url, timeout=4)
                if r.status_code < 400:
                    feeds.append(_make_source(feed_url, _url_to_name(url), f"Standard feed path on {urlparse(url).netloc}"))
                    break
            except Exception:
                pass

    return feeds


def _make_source(url: str, name: str, reason: str) -> dict:
    return {
        "name": name,
        "url": url,
        "type": "rss",
        "category": "Other",
        "description": f"News source at {urlparse(url).netloc}",
        "reason": reason or "Found via web search",
    }


def _url_to_name(url: str) -> str:
    domain = urlparse(url).netloc
    domain = re.sub(r"^(www\.|feeds?\.|rss\.)", "", domain)
    parts = domain.split(".")
    return " ".join(p.capitalize() for p in parts[:2]) if len(parts) >= 2 else domain.capitalize()
