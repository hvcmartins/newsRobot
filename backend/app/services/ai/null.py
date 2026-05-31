from .base import AIProvider, RelevanceResult


class NullProvider(AIProvider):
    """No-op provider used when AI_ENABLED=false or provider=none."""

    def score_relevance(self, title, excerpt, topic_profile) -> RelevanceResult:
        return RelevanceResult(score=0.5, reason="AI disabled")

    def summarize(self, title, excerpt) -> str:
        return excerpt or ""

    def categorize(self, title, excerpt, categories) -> str:
        return "Uncategorized"

    def are_duplicates(self, title1, excerpt1, title2, excerpt2) -> bool:
        return False

    def suggest_keywords(self, topic_profile) -> list[str]:
        return []

    def recommend_sources(self, topic_profile, catalog) -> list[int]:
        return []

    def discover_sources(self, topic_profile) -> list[dict]:
        return []
