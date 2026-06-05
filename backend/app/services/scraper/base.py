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
    """Extract the real article URL from a Google News URL by decoding its base64 payload.

    Google News encodes the target URL as a protobuf message in the URL path.
    This decodes it without any HTTP request.
    """
    match = re.search(r'/articles/([A-Za-z0-9_-]+)', google_url)
    if not match:
        return None
    encoded = match.group(1)
    encoded += '=' * (-len(encoded) % 4)
    try:
        data = base64.urlsafe_b64decode(encoded)
        # The real URL is a UTF-8 string embedded in a protobuf message.
        # Scan for the http prefix rather than parsing protobuf fields.
        text = data.decode('latin-1')
        for prefix in ('https://', 'http://'):
            idx = text.find(prefix)
            if idx >= 0:
                url = text[idx:]
                # Strip binary garbage that follows the URL in the protobuf
                url = re.sub(r'[\x00-\x1f\x7f-\xff].*', '', url)
                if url.startswith('http'):
                    return url
    except Exception as exc:
        logger.debug("_decode_google_news_url failed for %s: %s", google_url, exc)
    return None


def _extract_og_image_from_soup(soup: BeautifulSoup) -> str | None:
    """Return the best image URL from og:image / twitter:image / JSON-LD."""
    for prop, attr in [
        ("og:image", "property"),
        ("og:image:secure_url", "property"),
        ("twitter:image", "name"),
        ("twitter:image:src", "name"),
    ]:
        tag = soup.find("meta", attrs={attr: prop})
        if tag:
            content = tag.get("content", "").strip()
            if content and content.startswith("http") and "placeholder" not in content.lower():
                return content

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            candidates = data if isinstance(data, list) else data.get("@graph", [data])
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                img = item.get("image")
                if isinstance(img, str) and img.startswith("http"):
                    return img
                if isinstance(img, dict):
                    val = img.get("url", "")
                    if val.startswith("http"):
                        return val
                if isinstance(img, list) and img:
                    first = img[0]
                    if isinstance(first, str) and first.startswith("http"):
                        return first
                    if isinstance(first, dict):
                        val = first.get("url", "")
                        if val.startswith("http"):
                            return val
        except Exception:
            pass
    return None


def resolve_article_url(url: str, timeout: int = 10) -> str:
    """Return the real article URL, resolving Google News redirect URLs.

    Fast path: decode the real URL from the base64 payload in the URL path —
    no HTTP request needed.  Falls back to HTTP redirect-following if the decode
    fails.  Always returns a non-empty string (original URL on failure).
    """
    if not _GOOGLE_NEWS_RE.search(url):
        return url

    decoded = _decode_google_news_url(url)
    if decoded:
        return decoded

    # Fallback: follow HTTP redirects
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers=_BROWSER_HEADERS)
            resp.raise_for_status()
        final_url = str(resp.url)
        if not _GOOGLE_NEWS_RE.search(final_url) and not _is_bad_redirect(final_url):
            return final_url
        soup = BeautifulSoup(resp.text, "html.parser")
        for prop, attr in [("og:url", "property"), ("og:url", "name")]:
            tag = soup.find("meta", attrs={attr: prop})
            if tag:
                content = tag.get("content", "").strip()
                if content and content.startswith("http") and not _GOOGLE_NEWS_RE.search(content):
                    return content
        canonical = soup.find("link", rel="canonical")
        if canonical:
            href = canonical.get("href", "").strip()
            if href and href.startswith("http") and not _GOOGLE_NEWS_RE.search(href):
                return href
    except Exception as exc:
        logger.debug("resolve_article_url HTTP fallback failed for %s: %s", url, exc)

    return url


def fetch_og_image(url: str, timeout: int = 10) -> str | None:
    """Fetch an article URL and extract the best available image.

    Handles Google News redirect URLs by decoding the real URL first.
    """
    if _GOOGLE_NEWS_RE.search(url):
        real = resolve_article_url(url, timeout)
        if real == url:
            logger.debug("Could not resolve Google News URL for og:image: %s", url)
            return None
        url = real

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers=_BROWSER_HEADERS)
            resp.raise_for_status()
        return _extract_og_image_from_soup(BeautifulSoup(resp.text, "html.parser"))
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
