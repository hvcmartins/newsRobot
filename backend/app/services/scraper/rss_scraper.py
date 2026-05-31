import datetime
import logging
import app.compat  # noqa: F401 — patch html.parser before feedparser loads
import feedparser
from bs4 import BeautifulSoup

from .base import AbstractScraper, ScrapedArticle

logger = logging.getLogger(__name__)


def _strip_html(text: str) -> str:
    return BeautifulSoup(text, "lxml").get_text(separator=" ").strip()


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
        feed = feedparser.parse(self.source_url)
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

            # Prefer summary, fall back to content
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
