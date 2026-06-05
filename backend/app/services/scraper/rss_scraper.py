import datetime
import logging
import re
from urllib.parse import urljoin
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

# Matches & not already part of a valid XML entity reference or char ref
_BARE_AMP = re.compile(r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)')

# Characters illegal in XML 1.0:
#   - control chars below 0x20 except tab (0x09), LF (0x0A), CR (0x0D)
#   - DEL (0x7F)
#   - Unicode surrogates (0xD800–0xDFFF) — valid in Python strings but illegal in XML
#   - XML non-characters (0xFFFE, 0xFFFF)
_INVALID_XML_CHARS = re.compile(
    r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ud800-\udfff￾￿]'
)


def _sanitize_xml(raw: bytes) -> bytes:
    """Fix common XML issues that cause feedparser to fail."""
    try:
        text = raw.decode('utf-8', errors='replace')
        text = _INVALID_XML_CHARS.sub('', text)
        text = _BARE_AMP.sub('&amp;', text)
        return text.encode('utf-8')
    except Exception:
        return raw


def _find_feed_url_in_html(raw: bytes, base_url: str) -> str | None:
    """Return the RSS/Atom feed URL advertised by an HTML page, or None."""
    try:
        soup = BeautifulSoup(raw, "html.parser")
        for link in soup.find_all("link", rel="alternate"):
            t = link.get("type", "")
            if "rss" in t or "atom" in t:
                href = link.get("href", "")
                if href:
                    return urljoin(base_url, href)
    except Exception:
        pass
    return None


def _strip_html(text: str) -> str:
    return BeautifulSoup(text, "html.parser").get_text(separator=" ").strip()


def _is_placeholder_src(src: str) -> bool:
    """Return True for 1×1 tracking pixels, data URIs, and SVG spacers."""
    if not src:
        return True
    low = src.lower()
    return (
        low.startswith("data:")
        or "placeholder" in low
        or "blank.gif" in low
        or "1x1" in low
        or "spacer" in low
    )


def _extract_image(entry) -> str | None:
    # 1. media:thumbnail — most explicit signal
    if mt := entry.get("media_thumbnail"):
        url = mt[0].get("url", "")
        if url and not _is_placeholder_src(url):
            return url
    # 2. image enclosures
    for enc in entry.get("enclosures", []):
        if enc.get("type", "").startswith("image/"):
            url = enc.get("href", "")
            if url and not _is_placeholder_src(url):
                return url
    # 3. media:content with image medium/type
    for mc in entry.get("media_content", []):
        if mc.get("medium") == "image" or mc.get("type", "").startswith("image/"):
            url = mc.get("url", "")
            if url and not _is_placeholder_src(url):
                return url
    # 4. first real <img> inside content:encoded or summary HTML
    #    Many WordPress / CMS feeds put images only here, often with lazy-loading.
    _LAZY_ATTRS = (
        "src", "data-src", "data-lazy-src", "data-original",
        "data-wp-src", "data-full-url", "data-img-src",
    )
    html_fields = []
    if entry.get("content"):
        html_fields.append(entry.content[0].value)
    if entry.get("summary"):
        html_fields.append(entry.get("summary", ""))
    for html in html_fields:
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for img in soup.find_all("img"):
            for attr in _LAZY_ATTRS:
                val = img.get(attr, "")
                if val and val.startswith("http") and not _is_placeholder_src(val):
                    return val
            # srcset fallback — take first URL
            for ss_attr in ("srcset", "data-srcset"):
                ss = img.get(ss_attr, "")
                if ss:
                    first = ss.strip().split()[0]
                    if first.startswith("http") and not _is_placeholder_src(first):
                        return first
    return None


def _parse_feed(raw: bytes, content_type: str, source_url: str):
    """Parse feed bytes with feedparser.

    Strategy (in order):
    1. Sanitize + feedparser — handles the majority of invalid-token errors.
    2. lxml recovery mode — re-serialises the XML using lxml's error-tolerant
       parser, then feeds the clean bytes to feedparser.  Catches malformed
       tags, bad attribute syntax, and other structural issues.
    3. Raw original — last-resort fallback in case our transforms regressed.
    """
    headers = {"content-type": content_type, "content-location": source_url}
    sanitized = _sanitize_xml(raw)

    feed = feedparser.parse(sanitized, response_headers=headers)
    if not feed.bozo or feed.entries:
        return feed

    # lxml recovery pass
    try:
        from lxml import etree  # noqa: PLC0415
        lxml_parser = etree.XMLParser(recover=True, resolve_entities=False)
        root = etree.fromstring(sanitized, lxml_parser)
        recovered = etree.tostring(root, xml_declaration=True, encoding="utf-8")
        feed_lxml = feedparser.parse(recovered, response_headers=headers)
        if feed_lxml.entries:
            logger.debug("lxml recovery produced %d entries for %s",
                         len(feed_lxml.entries), source_url)
            return feed_lxml
    except Exception as exc:
        logger.debug("lxml recovery failed for %s: %s", source_url, exc)

    feed_raw = feedparser.parse(raw, response_headers=headers)
    return feed_raw if feed_raw.entries else feed


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
            raise ValueError(
                f"Feed returned HTTP {exc.response.status_code}: {self.source_url}"
            ) from exc
        except httpx.RequestError as exc:
            msg = str(exc)
            if any(s in msg for s in ("Name or service not known",
                                       "Temporary failure", "No address")):
                raise ValueError(
                    f"DNS lookup failed for {self.source_url} — "
                    "the domain may be unreachable from this server's network."
                ) from exc
            raise ValueError(f"Could not reach feed: {exc}") from exc

        # When the server returns an HTML page, try to auto-discover the feed
        # via <link rel="alternate" type="application/rss+xml">.
        if "html" in content_type.lower():
            discovered = _find_feed_url_in_html(raw, self.source_url)
            if discovered:
                logger.warning(
                    "'%s' returned HTML — auto-following advertised feed URL: %s "
                    "(update the source URL to avoid this warning)",
                    self.source_name, discovered,
                )
                try:
                    with httpx.Client(timeout=20, follow_redirects=True) as client:
                        resp2 = client.get(discovered, headers=_HEADERS)
                        resp2.raise_for_status()
                    raw = resp2.content
                    content_type = resp2.headers.get("content-type", "application/xml")
                except Exception:
                    pass  # fall through to the error path below

        feed = _parse_feed(raw, content_type, self.source_url)

        if feed.bozo and not feed.entries:
            exc_str = str(feed.bozo_exception)
            if "html" in content_type.lower() or "html" in exc_str.lower():
                hint = ""
                discovered = _find_feed_url_in_html(raw, self.source_url)
                if discovered:
                    hint = f" Suggested feed URL: {discovered}"
                raise ValueError(
                    "URL returned an HTML page, not an RSS/Atom feed. "
                    f"Check that the URL points to the actual feed (e.g. /feed/ or /rss/).{hint}"
                )
            raise ValueError(f"Failed to parse RSS feed: {feed.bozo_exception}")

        results = []
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            if not title:
                continue

            url = entry.get("link", "").strip()
            if not url:
                continue

            # Decode Google News redirect URLs immediately so the real article
            # URL is stored in the DB from the start
            if "news.google.com" in url:
                from .base import _decode_google_news_url
                decoded = _decode_google_news_url(url)
                if decoded:
                    url = decoded

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
