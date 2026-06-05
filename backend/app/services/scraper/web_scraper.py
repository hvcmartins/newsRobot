import datetime
import json
import logging
import re
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup

from .base import AbstractScraper, ScrapedArticle

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "NewsRobot/1.0 (news aggregator)"}

# Meta properties that carry publication dates
_DATE_META_PROPS = [
    "article:published_time",
    "og:article:published_time",
    "datePublished",
    "publish_date",
    "pubdate",
    "date",
    "DC.date",
    "DC.date.issued",
    "dc.date",
    "sailthru.date",
    "parsely-pub-date",
]

# CSS class name fragments that often wrap dates
_DATE_CLASS_HINTS = re.compile(
    r"(date|time|published|publish|posted|created|timestamp|when)",
    re.IGNORECASE,
)


# Relative date patterns: "2 hours ago", "3 days ago", "yesterday", etc.
_RELATIVE_DATE = re.compile(
    r'^(?:just\s+now'
    r'|(\d+)\s+(second|minute|hour|day|week|month)s?\s+ago'
    r'|yesterday'
    r'|today)$',
    re.IGNORECASE,
)


def _parse_relative_date(value: str) -> datetime.datetime | None:
    """Convert relative date strings to absolute datetimes."""
    now = datetime.datetime.utcnow()
    v = value.strip().lower()
    if v in ("just now", "agora", "à l'instant"):
        return now
    if v == "yesterday":
        return (now - datetime.timedelta(days=1)).replace(hour=12, minute=0, second=0)
    if v == "today":
        return now.replace(hour=12, minute=0, second=0)
    m = re.match(r'(\d+)\s+(second|minute|hour|day|week|month)s?\s+ago', v, re.IGNORECASE)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        deltas = {
            "second": datetime.timedelta(seconds=n),
            "minute": datetime.timedelta(minutes=n),
            "hour":   datetime.timedelta(hours=n),
            "day":    datetime.timedelta(days=n),
            "week":   datetime.timedelta(weeks=n),
            "month":  datetime.timedelta(days=n * 30),
        }
        return now - deltas[unit]
    return None


def _parse_date(value: str) -> datetime.datetime | None:
    """Try common date formats, return tz-naive datetime or None."""
    if not value:
        return None
    value = value.strip()

    # Relative dates: "2 hours ago", "yesterday", etc.
    rel = _parse_relative_date(value)
    if rel:
        return rel

    # Remove trailing timezone name in parens e.g. "Tue, 13 May 2025 10:00 (GMT)"
    value = re.sub(r"\s*\([^)]+\)\s*$", "", value).strip()
    # Remove trailing standalone timezone word e.g. "June 2, 2026 - 3:46 pm DILI"
    value = re.sub(r"\s+[A-Z]{2,5}$", "", value).strip()
    # Normalise "Month D, YYYY - H:MM am/pm" → "Month D, YYYY H:MM am/pm"
    value = re.sub(r"\s*-\s*(\d{1,2}:\d{2})", r" \1", value)
    # Normalise ISO 8601: strip sub-seconds
    iso_clean = re.sub(r"(\d{2}:\d{2}:\d{2})\.\d+", r"\1", value)

    candidates = [value] if value == iso_clean else [iso_clean, value]
    for candidate in candidates:
        for fmt in (
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%a, %d %b %Y %H:%M:%S %z",   # RFC 2822  e.g. Tue, 13 May 2025 10:00:00 +0000
            "%a, %d %b %Y %H:%M:%S %Z",   # RFC 2822 with named tz e.g. GMT
            "%B %d, %Y %I:%M %p",          # June 2, 2026 3:46 pm  (after dash normalisation)
            "%B %d, %Y %H:%M",             # June 2, 2026 15:46
            "%B %d, %Y",
            "%d %B %Y",
            "%b %d, %Y",
            "%d %b %Y",
            "%m/%d/%Y",
            "%d/%m/%Y",
        ):
            try:
                dt = datetime.datetime.strptime(candidate, fmt)
                return dt.replace(tzinfo=None)
            except ValueError:
                continue
    return None


def _extract_jsonld_date(soup: BeautifulSoup) -> datetime.datetime | None:
    """Extract datePublished from JSON-LD structured data (most reliable source)."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            # Handle single object or @graph array
            candidates = []
            if isinstance(data, list):
                candidates = data
            elif isinstance(data, dict):
                candidates = data.get("@graph", [data])
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                # Look for article-like types
                item_type = item.get("@type", "")
                if isinstance(item_type, list):
                    item_type = " ".join(item_type)
                for key in ("datePublished", "dateCreated", "dateModified"):
                    raw = item.get(key)
                    if raw and isinstance(raw, str):
                        dt = _parse_date(raw)
                        if dt:
                            return dt
        except Exception:
            continue
    return None


def _extract_date_from_item(item) -> datetime.datetime | None:
    """Try to find a publication date within an article item element."""
    # 1. <time datetime="..."> or itemprop="datePublished"
    for time_el in item.find_all("time"):
        for attr in ("datetime", "content"):
            val = time_el.get(attr, "")
            if val:
                dt = _parse_date(val)
                if dt:
                    return dt
        # Fall back to visible text of the <time> element
        dt = _parse_date(time_el.get_text(strip=True))
        if dt:
            return dt

    # 2. itemprop="datePublished" / "dateCreated" on any element
    for prop in ("datePublished", "dateCreated", "dateModified"):
        el = item.find(attrs={"itemprop": prop})
        if el:
            dt = _parse_date(el.get("content", "") or el.get("datetime", "") or el.get_text(strip=True))
            if dt:
                return dt

    # 3. data-* date attributes
    for el in item.find_all(True):
        for attr in ("data-date", "data-published", "data-pubdate", "data-time",
                     "data-timestamp", "data-post-date", "datetime"):
            val = el.get(attr, "")
            if val:
                dt = _parse_date(val)
                if dt:
                    return dt

    # 4. Elements whose class name hints at a date
    for el in item.find_all(True):
        classes = " ".join(el.get("class", []))
        if _DATE_CLASS_HINTS.search(classes):
            txt = el.get_text(strip=True)
            if txt and len(txt) < 60:
                dt = _parse_date(txt)
                if dt:
                    return dt

    return None


def _extract_page_date(soup: BeautifulSoup) -> datetime.datetime | None:
    """Extract publication date from page-level metadata (JSON-LD, meta tags, microdata)."""
    # JSON-LD is the most reliable
    dt = _extract_jsonld_date(soup)
    if dt:
        return dt

    # Standard meta tags
    for prop in _DATE_META_PROPS:
        for attr in ("property", "name", "itemprop"):
            tag = soup.find("meta", attrs={attr: prop})
            if tag:
                dt = _parse_date(tag.get("content", ""))
                if dt:
                    return dt

    # itemprop="datePublished" anywhere on the page
    for prop in ("datePublished", "dateCreated"):
        el = soup.find(attrs={"itemprop": prop})
        if el:
            dt = _parse_date(
                el.get("content", "") or el.get("datetime", "") or el.get_text(strip=True)
            )
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

        try:
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception:
            soup = BeautifulSoup(resp.text, "html.parser")
        page_date = _extract_page_date(soup)
        items = soup.select(self.css_selector)
        logger.debug("WebScraper '%s': %d items, page_date=%s",
                     self.source_name, len(items), page_date)

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
                # Try src attributes in priority order; skip placeholders / data URIs
                _lazy_attrs = (
                    "src", "data-src", "data-lazy-src", "data-original",
                    "data-wp-src", "data-full-url", "data-img-src",
                )
                raw_src = ""
                for attr in _lazy_attrs:
                    val = img_el.get(attr, "")
                    if val and not val.startswith("data:") and "placeholder" not in val.lower():
                        raw_src = val
                        break
                # Fall back to first URL in srcset when src is a 1×1 spacer
                if not raw_src:
                    for ss_attr in ("srcset", "data-srcset"):
                        ss = img_el.get(ss_attr, "")
                        if ss:
                            first = ss.strip().split()[0]
                            if first.startswith("http"):
                                raw_src = first
                                break
                if raw_src:
                    image_url = (raw_src if raw_src.startswith("http")
                                 else urljoin(self.source_url, raw_src))

            published_at = _extract_date_from_item(item) or page_date

            results.append(ScrapedArticle(
                title=title,
                url=url,
                excerpt=excerpt,
                published_at=published_at,
                image_url=image_url,
                source_name=self.source_name,
            ))

        return results
