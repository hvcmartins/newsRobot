import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

# Shared prompt used by every provider for source discovery.
DISCOVER_PROMPT = """\
You are a news research expert. Based on the company profile below, suggest \
10-12 reliable news sources the company should monitor.

Prefer sources that publish RSS or Atom feeds — use the actual feed URL, not \
the homepage. For well-known publications you can produce correct feed URLs \
from memory (e.g. https://techcrunch.com/feed/, \
https://feeds.reuters.com/reuters/businessNews).

Company profile:
{topic_profile}

Return ONLY a JSON array — no surrounding text, no markdown fences.
Each element must have exactly these keys:
  name        (string)  – publication name
  url         (string)  – RSS/Atom feed URL, or homepage if no feed exists
  type        (string)  – "rss" or "scrape"
  category    (string)  – one of: Technology, Finance, Business, Politics, \
Science, Health, Sports, World News, Environment, Other
  description (string)  – one sentence about what the source covers
  reason      (string)  – one sentence on why it matches the profile

Example element:
{{"name":"Reuters Business","url":"https://feeds.reuters.com/reuters/businessNews",\
"type":"rss","category":"Finance","description":"Global business news",\
"reason":"Covers financial markets relevant to the company"}}
"""


def extract_sources_from_text(raw: str) -> list[dict]:
    """Last-resort extractor: pull sources from mangled or truncated output.

    Scans for "url": "https://..." and nearby "name": "..." patterns.
    Works even when JSON is partially truncated by a token limit.
    """
    _VALID_TYPES = {"rss", "scrape"}
    _VALID_CATS = {
        "Technology", "Finance", "Business", "Politics", "Science",
        "Health", "Sports", "World News", "Environment", "Other",
    }
    url_re = re.compile(r'"url"\s*:\s*"(https?://[^"]+)"')
    name_re = re.compile(r'"name"\s*:\s*"([^"]+)"')
    type_re = re.compile(r'"type"\s*:\s*"(rss|scrape)"')
    cat_re = re.compile(r'"category"\s*:\s*"([^"]*)"')
    desc_re = re.compile(r'"description"\s*:\s*"([^"]*)"')
    reason_re = re.compile(r'"reason"\s*:\s*"([^"]*)"')

    result: list[dict] = []
    seen: set[str] = set()
    for m in url_re.finditer(raw):
        url = m.group(1).strip()
        if not url or url in seen:
            continue
        # Search for sibling fields within a window around this URL
        ws = max(0, m.start() - 300)
        we = min(len(raw), m.end() + 400)
        ctx = raw[ws:we]

        name_m = name_re.search(ctx)
        if not name_m:
            continue
        name = name_m.group(1).strip()
        if not name:
            continue

        type_m = type_re.search(ctx)
        src_type = type_m.group(1) if type_m and type_m.group(1) in _VALID_TYPES else "rss"

        cat_m = cat_re.search(ctx)
        cat = cat_m.group(1) if cat_m and cat_m.group(1) in _VALID_CATS else "Other"

        desc_m = desc_re.search(ctx)
        desc = desc_m.group(1).strip() if desc_m else ""

        reason_m = reason_re.search(ctx)
        reason = reason_m.group(1).strip() if reason_m else ""

        seen.add(url)
        result.append({
            "name": name, "url": url, "type": src_type,
            "category": cat, "description": desc, "reason": reason,
        })
    return result


def repair_json_array(raw: str) -> str:
    """Fix common small-model JSON mistakes before parsing.

    Handles several output patterns seen from local (llama.cpp) models:
    - Objects wrapped in square brackets: ["key": "val"] → {"key": "val"}
    - Mixed brackets: ["key": "val"} or {"key": "val"] → {"key": "val"}
    - Missing outer array: bare {...}, {...} items wrapped in [...]
    """
    result: list[str] = []
    # stack tracks what each opener *should* be based on what follows it
    stack: list[str] = []  # 'obj' or 'arr'
    in_string = False
    i = 0
    n = len(raw)

    while i < n:
        c = raw[i]

        if in_string:
            result.append(c)
            if c == '\\' and i + 1 < n:
                i += 1
                result.append(raw[i])
            elif c == '"':
                in_string = False
            i += 1
            continue

        if c == '"':
            in_string = True
            result.append(c)
            i += 1
            continue

        if c in '[{':
            # Peek past whitespace to decide: object or array?
            j = i + 1
            while j < n and raw[j] in ' \t\n\r':
                j += 1
            is_obj = False
            if j < n and raw[j] == '"':
                # Find end of key string
                k = j + 1
                while k < n and not (raw[k] == '"' and raw[k - 1] != '\\'):
                    k += 1
                k += 1  # past closing quote
                while k < n and raw[k] in ' \t\n\r':
                    k += 1
                if k < n and raw[k] == ':':
                    is_obj = True
            stack.append('obj' if is_obj else 'arr')
            result.append('{' if is_obj else '[')
            i += 1
            continue

        if c in ']}':
            # Close the most recent container with the correct bracket
            kind = stack.pop() if stack else 'arr'
            result.append('}' if kind == 'obj' else ']')
            i += 1
            continue

        result.append(c)
        i += 1

    joined = ''.join(result).strip()

    # If no outer array wrapper, collect top-level {...} objects and wrap
    if not joined.startswith('['):
        objs: list[str] = []
        depth = 0
        start: int | None = None
        for idx, ch in enumerate(joined):
            if ch == '{':
                if depth == 0:
                    start = idx
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start is not None:
                    objs.append(joined[start:idx + 1])
                    start = None
        if objs:
            joined = '[' + ','.join(objs) + ']'

    # Remove trailing commas before closing bracket
    joined = re.sub(r',(\s*\])', r'\1', joined)
    return joined


# Shorter prompt for local (constrained-context) models — fewer fields,
# fewer items, explicit bracket instruction, and a worked example.
DISCOVER_PROMPT_SHORT = """\
List 6 RSS news feed sources for this company profile:
{topic_profile}

Rules:
- Use CURLY BRACES {{}} for each object, NOT square brackets [].
- Output ONLY the JSON array, no other text.
- Required keys: name, url, type, category, description, reason
- type must be "rss" or "scrape"
- category must be one of: Technology, Finance, Business, Politics, Science, Health, Sports, World News, Environment, Other

Example (follow this format exactly):
[
{{"name":"BBC News","url":"https://feeds.bbci.co.uk/news/rss.xml","type":"rss","category":"World News","description":"Global news from the BBC","reason":"Broad international coverage"}},
{{"name":"Reuters Business","url":"https://feeds.reuters.com/reuters/businessNews","type":"rss","category":"Finance","description":"Business and finance news","reason":"Covers markets and deals"}}
]
"""
    """Coerce AI output to a clean list of source dicts."""
    _VALID_TYPES = {"rss", "scrape"}
    _VALID_CATS = {
        "Technology", "Finance", "Business", "Politics", "Science",
        "Health", "Sports", "World News", "Environment", "Other",
    }
    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        name = str(item.get("name", "")).strip()
        if not url or not name or not url.startswith("http"):
            continue
        result.append({
            "name": name,
            "url": url,
            "type": item.get("type", "rss") if item.get("type") in _VALID_TYPES else "rss",
            "category": item.get("category", "Other") if item.get("category") in _VALID_CATS else "Other",
            "description": str(item.get("description", "")).strip(),
            "reason": str(item.get("reason", "")).strip(),
        })
    return result


@dataclass
class RelevanceResult:
    score: float
    reason: str


@dataclass
class EnrichmentResult:
    summary: Optional[str]
    category: Optional[str]
    relevance: Optional[RelevanceResult]


class AIProvider(ABC):
    @abstractmethod
    def score_relevance(self, title: str, excerpt: str,
                        topic_profile: str) -> RelevanceResult:
        ...

    @abstractmethod
    def summarize(self, title: str, excerpt: str) -> str:
        ...

    @abstractmethod
    def categorize(self, title: str, excerpt: str,
                   categories: list[str]) -> str:
        ...

    @abstractmethod
    def are_duplicates(self, title1: str, excerpt1: str,
                       title2: str, excerpt2: str) -> bool:
        ...

    @abstractmethod
    def suggest_keywords(self, topic_profile: str) -> list[str]:
        ...

    @abstractmethod
    def recommend_sources(self, topic_profile: str,
                          catalog: list[dict]) -> list[int]:
        ...

    @abstractmethod
    def discover_sources(self, topic_profile: str) -> list[dict]:
        """Return a list of suggested source dicts: name, url, type, category,
        description, reason.  Prefer RSS feed URLs over plain websites."""
        ...
