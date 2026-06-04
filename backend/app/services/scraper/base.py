from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import datetime
import json
import logging

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_OG_HEADERS = {
    "User-Agent": "NewsRobot/1.0 (news aggregator)",
    "Accept": "text/html,application/xhtml+xml,*/*",
}


def fetch_og_image(url: str, timeout: int = 10) -> str | None:
    """Fetch an article URL and extract the best available image via OG/Twitter meta or JSON-LD."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers=_OG_HEADERS)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1. og:image / twitter:image meta tags
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

        # 2. JSON-LD image field
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
