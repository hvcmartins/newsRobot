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


def normalise_discovered(raw: list) -> list[dict]:
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
