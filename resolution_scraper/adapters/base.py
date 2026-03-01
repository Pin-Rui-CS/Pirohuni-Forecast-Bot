from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import ScrapeRequest, ScrapeResult


class SourceAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def can_handle(self, request: ScrapeRequest) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def fetch(self, request: ScrapeRequest) -> ScrapeResult:
        raise NotImplementedError
