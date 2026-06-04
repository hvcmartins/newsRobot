from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import datetime
import json
import logging
import re

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Browser-like headers — required for Google News and paywalled sites
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

_OG_HEADERS = _BROWSER_HEADERS  # kept for backward compat imports elsewhere

_GOOGLE_NEWS_RE = re.compile(r'https?://news\.google\.com/', re.I)


def _extract_og_image_from_soup(soup: BeautifulSoup) -> str | None:
    """Return og:image / twitter:image / JSON-LD image from a parsed page."""
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


def _real_url_from_google_page(soup: BeautifulSoup) -> str | None:
    """Extract the original article URL from a Google News HTML page."""
    # og:url almost always points to the real article on Google News pages
    for prop, attr in [("og:url", "property"), ("og:url", "name")]:
        tag = soup.find("meta", attrs={attr: prop})
        if tag:
            content = tag.get("content", "").strip()
            if content and content.startswith("http") and not _GOOGLE_NEWS_RE.search(content):
                return content

    # canonical link
    canonical = soup.find("link", rel="canonical")
    if canonical:
        href = canonical.get("href", "").strip()
        if href and href.startswith("http") and not _GOOGLE_NEWS_RE.search(href):
            return href

    # meta refresh
    meta_refresh = soup.find("meta", attrs={"http-equiv": re.compile(r"^refresh$", re.I)})
    if meta_refresh:
        content = meta_refresh.get("content", "")
        m = re.search(r'url=(.+)', content, re.I)
        if m:
            href = m.group(1).strip().strip("'\"")
            if href.startswith("http") and not _GOOGLE_NEWS_RE.search(href):
                return href

    return None


def resolve_article_url(url: str, timeout: int = 10) -> str:
    """For Google News URLs, return the resolved real article URL.

    Falls back to the original URL on any error so callers never get None.
    """
    if not _GOOGLE_NEWS_RE.search(url):
        return url
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers=_BROWSER_HEADERS)
            resp.raise_for_status()
        final_url = str(resp.url)
        # HTTP redirect landed us on the real article
        if not _GOOGLE_NEWS_RE.search(final_url):
            return final_url
        # Still on Google — parse the page for the real URL
        soup = BeautifulSoup(resp.text, "html.parser")
        real = _real_url_from_google_page(soup)
        if real:
            return real
    except Exception as exc:
        logger.debug("resolve_article_url failed for %s: %s", url, exc)
    return url  # give back the original rather than None


def fetch_og_image(url: str, timeout: int = 10) -> str | None:
    """Fetch an article URL and extract the best available image.

    Handles Google News redirect URLs by resolving them first.
    """
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            # Google News URLs need resolving before we can get the article image
            if _GOOGLE_NEWS_RE.search(url):
                resp = client.get(url, headers=_BROWSER_HEADERS)
                resp.raise_for_status()
                final_url = str(resp.url)

                if _GOOGLE_NEWS_RE.search(final_url):
                    # Still on Google — find the real URL and re-fetch
                    soup = BeautifulSoup(resp.text, "html.parser")
                    real = _real_url_from_google_page(soup)
                    if not real:
                        logger.debug("Could not resolve Google News URL: %s", url)
                        return None
                    resp = client.get(real, headers=_BROWSER_HEADERS)
                    resp.raise_for_status()

                soup = BeautifulSoup(resp.text, "html.parser")
            else:
                resp = client.get(url, headers=_BROWSER_HEADERS)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

        return _extract_og_image_from_soup(soup)
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
