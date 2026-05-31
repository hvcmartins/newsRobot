from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


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
