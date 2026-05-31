import datetime
import logging
import app.compat  # noqa: F401 — patch html.parser before feedparser loads
import feedparser
import httpx
from bs4 import BeautifulSoup

from .base import AbstractScraper, ScrapedArticle

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "NewsRobot/1.0 (RSS aggregator)",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
}


def _strip_html(text: str) -> str:
    return BeautifulSoup(text, "html.parser").get_text(separator=" ").strip()


def _extract_image(entry) -> str | None:
    if mt := entry.get("media_thumbnail"):
        return mt[0].get("url")
    for enc in entry.get("enclosures", []):
        if enc.get("type", "").startswith("image/"):
            return enc.get("href")
    for mc in entry.get("media_content", []):
        if mc.get("medium") == "image" or mc.get("type", "").startswith("image/"):
            return mc.get("url")
    return None


class RssScraper(AbstractScraper):
    def fetch(self) -> list[ScrapedArticle]:
        # Pre-fetch with httpx so feedparser only does parsing, not networking.
        # This avoids feedparser's urllib-based fetching which fails in some
        # container DNS configurations, and gives cleaner error messages.
        try:
            with httpx.Client(timeout=20, follow_redirects=True) as client:
                resp = client.get(self.source_url, headers=_HEADERS)
                resp.raise_for_status()
            raw = resp.content
            content_type = resp.headers.get("content-type", "application/xml")
        except httpx.HTTPStatusError as exc:
            raise ValueError(f"Feed returned HTTP {exc.response.status_code}: {self.source_url}") from exc
        except httpx.RequestError as exc:
            raise ValueError(f"Could not reach feed ({exc}): {self.source_url}") from exc

        feed = feedparser.parse(
            raw,
            response_headers={"content-type": content_type,
                               "content-location": self.source_url},
        )

        if feed.bozo and not feed.entries:
            raise ValueError(f"Failed to parse RSS feed: {feed.bozo_exception}")

        results = []
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            if not title:
                continue

            url = entry.get("link", "").strip()
            if not url:
                continue

            raw_excerpt = entry.get("summary", "")
            if entry.get("content"):
                raw_excerpt = entry.content[0].value
            excerpt = _strip_html(raw_excerpt)[:600] if raw_excerpt else None

            pub = None
            if entry.get("published_parsed"):
                try:
                    pub = datetime.datetime(*entry.published_parsed[:6],
                                           tzinfo=datetime.timezone.utc)
                except (TypeError, ValueError):
                    pass
            elif entry.get("updated_parsed"):
                try:
                    pub = datetime.datetime(*entry.updated_parsed[:6],
                                           tzinfo=datetime.timezone.utc)
                except (TypeError, ValueError):
                    pass

            results.append(ScrapedArticle(
                title=title,
                url=url,
                excerpt=excerpt,
                published_at=pub,
                image_url=_extract_image(entry),
                source_name=self.source_name,
            ))

        return results
