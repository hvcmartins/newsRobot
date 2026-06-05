from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import base64
import datetime
import json
import logging
import re

import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Hosts that Google redirects to when it can't resolve the real URL
# (cookie consent pages, login walls, etc.). Never save these as article URLs.
_BAD_REDIRECT_HOSTS = frozenset({
    'consent.google.com',
    'accounts.google.com',
})


def _is_bad_redirect(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        return any(host == h or host.endswith('.' + h) for h in _BAD_REDIRECT_HOSTS)
    except Exception:
        return False


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

_OG_HEADERS = _BROWSER_HEADERS  # kept for backward compat

_GOOGLE_NEWS_RE = re.compile(r'https?://news\.google\.com/', re.I)


def _decode_google_news_url(google_url: str) -> str | None:
    """Fast decode of a Google News URL using local base64 parsing only.

    Works for older token formats where the URL is stored as plaintext inside
    the protobuf payload.  Returns None for newer encrypted tokens — callers
    that can afford HTTP requests should use resolve_article_url() instead.
    """
    match = re.search(r'/(?:articles|read)/([A-Za-z0-9_-]+)', google_url)
    if not match:
        return None
    encoded = match.group(1) + '=' * (-len(match.group(1)) % 4)
    try:
        data = base64.urlsafe_b64decode(encoded)
        text = data.decode('latin-1')
        for prefix in ('https://', 'http://'):
            idx = text.find(prefix)
            if idx >= 0:
                url = text[idx:]
                url = re.sub(r'[\x00-\x1f\x7f-\xff].*', '', url)
                url = url.split()[0] if url else url
                if url.startswith('http') and '.' in url:
                    return url
    except Exception:
        pass
    return None


def _decode_google_news_url_api(google_url: str) -> str | None:
    """Decode a Google News URL via Google's own batchexecute API.

    Makes 2 HTTP requests — use this during async enrichment, not during
    synchronous RSS scraping where speed matters.
    """
    try:
        from googlenewsdecoder import new_decoderv1
        result = new_decoderv1(google_url)
        if result.get('status') and result.get('decoded_url'):
            decoded = result['decoded_url']
            if decoded.startswith('http') and not _GOOGLE_NEWS_RE.search(decoded):
                return decoded
            logger.debug("_decode_google_news_url_api: bad URL returned: %s", decoded)
    except Exception as exc:
        logger.debug("_decode_google_news_url_api failed: %s", exc)
    return None


def _extract_og_image_from_soup(soup: BeautifulSoup,
                                base_url: str | None = None) -> str | None:
    """Return the best image URL from og:image / twitter:image / JSON-LD."""
    from urllib.parse import urljoin

    def _resolve(raw: str) -> str | None:
        raw = raw.strip()
        if not raw:
            return None
        if raw.startswith("//"):          # protocol-relative
            raw = "https:" + raw
        elif raw.startswith("/") and base_url:  # site-relative
            raw = urljoin(base_url, raw)
        if not raw.startswith("http"):
            return None
        if "placeholder" in raw.lower():
            return None
        return raw

    for prop, attr in [
        ("og:image", "property"),
        ("og:image:secure_url", "property"),
        ("twitter:image", "name"),
        ("twitter:image:src", "name"),
    ]:
        tag = soup.find("meta", attrs={attr: prop})
        if tag:
            resolved = _resolve(tag.get("content", ""))
            if resolved:
                return resolved

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            candidates = data if isinstance(data, list) else data.get("@graph", [data])
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                img = item.get("image")
                if isinstance(img, str):
                    resolved = _resolve(img)
                    if resolved:
                        return resolved
                if isinstance(img, dict):
                    resolved = _resolve(img.get("url", ""))
                    if resolved:
                        return resolved
                if isinstance(img, list) and img:
                    first = img[0]
                    if isinstance(first, str):
                        resolved = _resolve(first)
                        if resolved:
                            return resolved
                    if isinstance(first, dict):
                        resolved = _resolve(first.get("url", ""))
                        if resolved:
                            return resolved
        except Exception:
            pass
    return None


def resolve_article_url(url: str, timeout: int = 10) -> str:
    """Return the real article URL for a Google News redirect URL.

    Resolution order:
    1. Fast local base64 decode (works for older token formats, no HTTP)
    2. googlenewsdecoder API (2 HTTP requests — handles current encrypted tokens)
    Always returns a non-empty string (original URL on failure).
    """
    if not _GOOGLE_NEWS_RE.search(url):
        return url

    decoded = _decode_google_news_url(url)
    if decoded:
        return decoded

    decoded = _decode_google_news_url_api(url)
    if decoded:
        return decoded

    return url


def fetch_og_image(url: str, timeout: int = 10) -> str | None:
    """Fetch an article URL and extract the best available image.

    Handles Google News redirect URLs by decoding the real URL first.
    When decode fails, follows HTTP redirects to reach the real article.
    Skips raise_for_status so paywalled pages that include og:image in
    their 4xx HTML are still parsed.
    """
    if _GOOGLE_NEWS_RE.search(url):
        real = resolve_article_url(url, timeout)
        if real != url:
            url = real
        # If decode/resolution still stuck on Google News, fall through and
        # follow redirects — the HTTP GET may land on the real article.

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers=_BROWSER_HEADERS)
        final_url = str(resp.url)
        if _is_bad_redirect(final_url):
            logger.debug("fetch_og_image: bad redirect to %s — skipping", final_url)
            return None
        return _extract_og_image_from_soup(
            BeautifulSoup(resp.text, "html.parser"), base_url=final_url
        )
    except Exception as exc:
        logger.debug("fetch_og_image failed for %s: %s", url, exc)
    return None


@dataclass
class ScrapedArticle:
    title: str
    url: str
    excerpt: Optional[str] = None
    published_at: Optional[datetime.datetime] = None
    image_url: Optional[str] = None
    source_name: str = ""


class AbstractScraper(ABC):
    def __init__(self, source_url: str, source_name: str):
        self.source_url = source_url
        self.source_name = source_name

    @abstractmethod
    def fetch(self) -> list[ScrapedArticle]:
        ...
