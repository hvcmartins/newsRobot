import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


def strip_thinking(text: str) -> str:
    """Remove <think>…</think> reasoning blocks emitted by models like Qwen3 / DeepSeek-R1.

    Applied in every provider's _ask() so JSON parsing never sees thinking tokens,
    regardless of whether the server-side thinking suppression is available.
    """
    return re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL).strip()

# ── Relevance scoring prompts ─────────────────────────────────────────────────
# Split into system (stable: profile + rubric) and user (variable: article).
# The system part is sent as a cacheable system message in capable providers,
# so scoring many articles against the same profile reuses the cached context.

RELEVANCE_SYSTEM_TPL = """\
You are a relevance classifier for a corporate news monitoring system.

## Company Profile
{topic_profile}

## Scoring Scale
  0.9–1.0  Core business — directly about their industry, key markets, \
regulators, major clients, or named organisations in the profile
  0.7–0.8  Useful intelligence — relevant market trends, competitor moves, \
policy changes, or technology shifts in their space
  0.4–0.6  Background context — loosely related sector or region; \
worth knowing but not actionable
  0.1–0.3  Marginal — only a passing reference to something in the profile
  0.0      No connection at all

Be strict: most articles should score below 0.5 unless they clearly match \
something specific in the profile."""

RELEVANCE_USER_TPL = """\
Article to evaluate:
Title: {title}
Excerpt: {excerpt}

Step 1 – Which specific topics, regions, or organisations from the profile \
does this article touch? If nothing, write "none".
Step 2 – Score it using the scale above.

Return JSON only:
{{"thinking": "<what this article is about + which profile area it touches>", \
"score": 0.0, "reason": "<one sentence justification>"}}"""


# ── Source discovery prompts ───────────────────────────────────────────────────
# Split into system (stable instructions) and user (per-tenant profile).

DISCOVER_SYSTEM = """\
You are a news research expert. Suggest 12-15 reliable news sources for the \
company profile you will receive.

Rules:
- Cover EVERY major topic section in the profile — not just the most prominent one.
- Only suggest sources that genuinely publish on those topics.
- Prefer RSS/Atom feed URLs over homepages. Use real, working feed URLs you \
know (e.g. https://techcrunch.com/feed/, \
https://feeds.reuters.com/reuters/businessNews, \
https://feeds.bbci.co.uk/news/world/rss.xml).
- Do NOT invent URLs — if unsure of the exact feed path, use the homepage URL \
and set type to "scrape".
- Aim for diversity: different publishers, different countries, different formats.

Return ONLY a JSON array — no surrounding text, no markdown fences.
Each element must have exactly these keys:
  name        (string)  – publication name
  url         (string)  – RSS/Atom feed URL, or homepage if no feed exists
  type        (string)  – "rss" or "scrape"
  category    (string)  – one of: Technology, Finance, Business, Politics, \
Science, Health, Sports, World News, Environment, Other
  description (string)  – one sentence about what the source covers
  reason      (string)  – one sentence on why it matches this specific profile

Example element:
{"name":"Reuters Business","url":"https://feeds.reuters.com/reuters/businessNews",\
"type":"rss","category":"Finance","description":"Global business news",\
"reason":"Covers financial markets relevant to the company"}"""

DISCOVER_USER_TPL = "Company profile:\n{topic_profile}\n\nSuggest the sources now."

# ── Category suggestion prompt ─────────────────────────────────────────────────
SUGGEST_CATEGORIES_PROMPT = """\
Read the topic profile below and extract the main news categories this \
organisation monitors.

Rules:
- Derive category names from the profile's section headings and key subject areas.
- Use specific, descriptive names (2–5 words), not generic terms like "Other" \
or "General News".
- Return 6–12 categories that together cover the full profile.
- Prefer names like "ASEAN Regional Affairs", "EU Institutional News", \
"Climate Finance", "Diplomatic Protocol" over "Politics", "Finance", "Science".

Profile:
{topic_profile}

Return JSON only: {{"categories": ["Category One", "Category Two", ...]}}"""

# Keep the combined prompt for any legacy / one-shot usage.
DISCOVER_PROMPT = DISCOVER_SYSTEM + "\n\nCompany profile:\n{topic_profile}\n\nSuggest the sources now."

# Shorter prompt for local (constrained-context) models — fewer items,
# explicit curly-brace rule, and a worked example.
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


def repair_json_array(raw: str) -> str:
    """Fix common small-model JSON mistakes before parsing.

    Handles several output patterns seen from local (llama.cpp) models:
    - Objects wrapped in square brackets: ["key": "val"] → {"key": "val"}
    - Mixed brackets: ["key": "val"} or {"key": "val"] → {"key": "val"}
    - Missing outer array: bare {...}, {...} items wrapped in [...]
    """
    result: list[str] = []
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
                k = j + 1
                while k < n and not (raw[k] == '"' and raw[k - 1] != '\\'):
                    k += 1
                k += 1
                while k < n and raw[k] in ' \t\n\r':
                    k += 1
                if k < n and raw[k] == ':':
                    is_obj = True
            stack.append('obj' if is_obj else 'arr')
            result.append('{' if is_obj else '[')
            i += 1
            continue

        if c in ']}':
            kind = stack.pop() if stack else 'arr'
            result.append('}' if kind == 'obj' else ']')
            i += 1
            continue

        result.append(c)
        i += 1

    joined = ''.join(result).strip()

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

    joined = re.sub(r',(\s*\])', r'\1', joined)
    return joined


# ── Combined enrichment prompts ───────────────────────────────────────────────
# Used by capable providers (Claude, OpenAI, Ollama) to do relevance scoring +
# summary + category in a single API call, cutting 3 round-trips to 1.
# The system block is the same RELEVANCE_SYSTEM_TPL (profile + rubric) so it
# benefits from prompt caching on Claude.

ENRICH_USER_TPL = """\
Article to evaluate:
Title: {title}
Excerpt: {excerpt}

Complete all in one pass:
1. Score relevance (0.0–1.0) using the rubric above.
2. If score ≥ 0.5: write a 2–3 sentence factual summary and pick the best \
category from: {categories}
3. If score < 0.5: set summary and category to null — no need to generate them.

Return JSON only:
{{"score": 0.0, "reason": "<one sentence>", \
"summary": "<2-3 sentences>" or null, "category": "<name>" or null}}"""

ENRICH_NO_PROFILE_TPL = """\
Article:
Title: {title}
Excerpt: {excerpt}

1. Write a 2–3 sentence factual summary.
2. Pick the best category from: {categories}

Return JSON only:
{{"summary": "<2-3 sentences>", "category": "<name>"}}"""


@dataclass
class RelevanceResult:
    score: float
    reason: str


@dataclass
class EnrichmentResult:
    score: float           # relevance score; 0.5 default when no profile
    reason: str            # relevance justification; empty when no profile
    summary: str | None    # AI summary; None if below threshold or not generated
    category: str | None   # assigned category; None if below threshold


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
    def suggest_categories(self, topic_profile: str) -> list[str]:
        """Return a list of news category names derived from the topic profile.
        These replace the generic fixed list (Technology, Finance…) so articles
        are classified into categories that are meaningful for this tenant."""
        ...

    def enrich_article(self, title: str, excerpt: str,
                       topic_profile: str | None,
                       categories: list[str]) -> "EnrichmentResult":
        """Score relevance, summarise, and categorise in one shot.

        Default: chains individual methods (safe for all providers).
        Capable providers override this with a single combined API call.
        """
        score, reason = 0.5, ""
        if topic_profile:
            rel = self.score_relevance(title, excerpt, topic_profile)
            score, reason = rel.score, rel.reason
            if score < 0.5:
                return EnrichmentResult(score=score, reason=reason,
                                        summary=None, category=None)
        summary = self.summarize(title, excerpt)
        category = self.categorize(title, excerpt, categories)
        return EnrichmentResult(score=score, reason=reason,
                                summary=summary, category=category)

    @abstractmethod
    def recommend_sources(self, topic_profile: str,
                          catalog: list[dict]) -> list[int]:
        ...

    @abstractmethod
    def discover_sources(self, topic_profile: str) -> list[dict]:
        """Return a list of suggested source dicts: name, url, type, category,
        description, reason.  Prefer RSS feed URLs over plain websites."""
        ...
