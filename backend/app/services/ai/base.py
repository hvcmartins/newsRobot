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
