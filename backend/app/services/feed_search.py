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


def web_search_feeds(topic_profile: str, max_results: int = 8) -> list[dict]:
    """Return RSS feeds found via DuckDuckGo search for the topic profile.

    Falls back to an empty list on any network/parse failure — caller must
    treat this as a best-effort augmentation, not a required step.
    """
    queries = _build_queries(topic_profile)
    page_urls: set[str] = set()

    for q in queries[:4]:
        try:
            hits = _ddg_search(f"{q} news RSS feed")
            page_urls.update(hits[:6])
        except Exception as exc:
            logger.debug("DDG search failed for %r: %s", q, exc)

    if not page_urls:
        return []

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
    stopwords = {
        "the","a","an","and","or","but","in","on","at","to","for","of","with",
        "is","are","we","our","that","this","have","been","will","be","as","by",
        "from","it","its","about","also","which","they","them","their","has",
        "more","than","into","can","was","were","when","if","all","each","very",
        "both","over","such","how","what","who","new","news","com","www",
    }
    words = re.findall(r'[A-Za-z]{4,}', profile)
    kws = list(dict.fromkeys(w.lower() for w in words if w.lower() not in stopwords))[:12]
    queries = [" ".join(kws[i:i + 2]) for i in range(0, min(len(kws), 8), 2)]
    return queries[:4] if queries else ["general news"]


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
