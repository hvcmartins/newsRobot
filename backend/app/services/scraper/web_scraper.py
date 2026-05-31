import logging
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup

from .base import AbstractScraper, ScrapedArticle

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "NewsRobot/1.0 (news aggregator)"}


class WebScraper(AbstractScraper):
    def __init__(self, source_url: str, source_name: str, css_selector: str):
        super().__init__(source_url, source_name)
        self.css_selector = css_selector

    def fetch(self) -> list[ScrapedArticle]:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            resp = client.get(self.source_url, headers=_HEADERS)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select(self.css_selector)

        results = []
        for item in items:
            title_el = item.find(["h1", "h2", "h3"]) or item.find("a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title:
                continue

            a_el = item.find("a", href=True)
            if not a_el:
                continue
            raw_url = a_el["href"]
            url = raw_url if raw_url.startswith("http") else urljoin(self.source_url, raw_url)

            p_el = item.find("p")
            excerpt = p_el.get_text(strip=True)[:600] if p_el else None

            img_el = item.find("img")
            image_url = None
            if img_el:
                src = img_el.get("src") or img_el.get("data-src", "")
                image_url = src if src.startswith("http") else urljoin(self.source_url, src)

            results.append(ScrapedArticle(
                title=title,
                url=url,
                excerpt=excerpt,
                published_at=None,
                image_url=image_url,
                source_name=self.source_name,
            ))

        return results
