from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import datetime


@dataclass
class ScrapedArticle:
    title: str
    url: str
    excerpt: Optional[str] = None
    published_at: Optional[datetime.datetime] = None
    image_url: Optional[str] = None
    source_name: str = ""


class AbstractScraper(ABC):
    def __init__(self, source_url: str, source_name: str):
        self.source_url = source_url
        self.source_name = source_name

    @abstractmethod
    def fetch(self) -> list[ScrapedArticle]:
        ...
