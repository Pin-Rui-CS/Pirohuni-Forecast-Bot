from __future__ import annotations

from urllib.parse import urlparse

import httpx

from ..config import ScraperConfig
from ..models import ResolutionSignal, ScrapeRequest, ScrapeResult, utc_now_iso
from .base import SourceAdapter


class WikipediaAdapter(SourceAdapter):
    name = "wikipedia_api"

    def __init__(self, config: ScraperConfig) -> None:
        self.config = config

    def can_handle(self, request: ScrapeRequest) -> bool:
        return "wikipedia.org" in urlparse(request.url).netloc.lower()

    async def fetch(self, request: ScrapeRequest) -> ScrapeResult:
        parsed = urlparse(request.url)
        host = parsed.netloc.lower()
        if ".wikipedia.org" not in host:
            return ScrapeResult(
                url=request.url,
                ok=False,
                signals=[],
                error="Unsupported Wikipedia host format.",
            )

        lang = host.split(".wikipedia.org")[0].split(".")[-1] or "en"
        api_url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "meta": "siteinfo",
            "siprop": "statistics",
            "format": "json",
        }
        headers = {"User-Agent": self.config.user_agent}

        async with httpx.AsyncClient(timeout=self.config.request_timeout_s) as client:
            response = await client.get(api_url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()

        stats = payload.get("query", {}).get("statistics", {})
        articles = stats.get("articles")
        if articles is None:
            return ScrapeResult(
                url=request.url,
                ok=False,
                signals=[],
                error="Could not find article statistics in MediaWiki response.",
            )

        conf = (
            "high"
            if "article" in request.resolution_text.lower()
            and "wikipedia" in request.resolution_text.lower()
            else "medium"
        )
        signal = ResolutionSignal(
            url=request.url,
            metric=f"wikipedia_article_count_{lang}",
            value=int(articles),
            as_of_utc=utc_now_iso(),
            parser=self.name,
            confidence=conf,
            note="Retrieved from MediaWiki siteinfo.statistics.",
            raw={"lang": lang, "statistics": stats},
        )
        return ScrapeResult(url=request.url, ok=True, signals=[signal], error=None)
