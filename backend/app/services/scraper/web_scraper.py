import datetime
import logging
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup

from .base import AbstractScraper, ScrapedArticle

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "NewsRobot/1.0 (news aggregator)"}

# Meta properties that typically carry publication dates
_DATE_META_PROPS = [
    "article:published_time",
    "og:article:published_time",
    "datePublished",
    "publish_date",
    "pubdate",
    "date",
]


def _parse_date(value: str) -> datetime.datetime | None:
    """Try common date formats, return None if unparseable."""
    if not value:
        return None
    value = value.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%B %d, %Y",
        "%d %B %Y",
        "%b %d, %Y",
    ):
        try:
            dt = datetime.datetime.strptime(value[:25], fmt)
            return dt.replace(tzinfo=None)
        except ValueError:
            continue
    return None


def _extract_date_from_item(item, page_soup: BeautifulSoup | None) -> datetime.datetime | None:
    """Try to find a publication date within an article item element."""
    # 1. <time datetime="..."> inside the item
    time_el = item.find("time")
    if time_el:
        dt = _parse_date(time_el.get("datetime", ""))
        if dt:
            return dt
        dt = _parse_date(time_el.get_text(strip=True))
        if dt:
            return dt

    # 2. data-date / data-published attributes on any element in the item
    for el in item.find_all(True):
        for attr in ("data-date", "data-published", "data-pubdate", "datetime"):
            val = el.get(attr, "")
            if val:
                dt = _parse_date(val)
                if dt:
                    return dt

    return None


def _extract_page_date(soup: BeautifulSoup) -> datetime.datetime | None:
    """Extract publication date from page-level meta tags."""
    for prop in _DATE_META_PROPS:
        tag = soup.find("meta", attrs={"property": prop})
        if not tag:
            tag = soup.find("meta", attrs={"name": prop})
        if tag:
            dt = _parse_date(tag.get("content", ""))
            if dt:
                return dt
    return None


class WebScraper(AbstractScraper):
    def __init__(self, source_url: str, source_name: str, css_selector: str):
        super().__init__(source_url, source_name)
        self.css_selector = css_selector

    def fetch(self) -> list[ScrapedArticle]:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            resp = client.get(self.source_url, headers=_HEADERS)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        page_date = _extract_page_date(soup)
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

            published_at = _extract_date_from_item(item, soup) or page_date

            results.append(ScrapedArticle(
                title=title,
                url=url,
                excerpt=excerpt,
                published_at=published_at,
                image_url=image_url,
                source_name=self.source_name,
            ))

        return results
