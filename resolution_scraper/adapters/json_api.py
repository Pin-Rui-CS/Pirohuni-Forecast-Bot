from __future__ import annotations

from collections import deque
from urllib.parse import urlparse

import httpx

from ..config import ScraperConfig
from ..models import ResolutionSignal, ScrapeRequest, ScrapeResult, utc_now_iso
from .base import SourceAdapter


class JsonApiAdapter(SourceAdapter):
    name = "json_api"

    def __init__(self, config: ScraperConfig) -> None:
        self.config = config
        self.priority_keys = [
            "value",
            "count",
            "total",
            "articles",
            "result",
            "latest",
            "data",
        ]

    def can_handle(self, request: ScrapeRequest) -> bool:
        parsed = urlparse(request.url)
        path = parsed.path.lower()
        return (
            path.endswith(".json")
            or "api" in path
            or "format=json" in parsed.query.lower()
        )

    def _extract_numeric_value(self, payload: object) -> tuple[str, float | int] | None:
        queue = deque([("$", payload)])
        visited = 0
        max_nodes = 2000

        while queue and visited < max_nodes:
            path, current = queue.popleft()
            visited += 1

            if isinstance(current, bool):
                continue
            if isinstance(current, (int, float)):
                return path, current

            if isinstance(current, dict):
                keys = list(current.keys())
                ordered_keys = [
                    k for k in self.priority_keys if k in current
                ] + [k for k in keys if k not in self.priority_keys]
                for key in ordered_keys:
                    queue.append((f"{path}.{key}", current[key]))
            elif isinstance(current, list):
                for i, item in enumerate(current[:20]):
                    queue.append((f"{path}[{i}]", item))

        return None

    async def fetch(self, request: ScrapeRequest) -> ScrapeResult:
        headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "application/json, text/plain, */*",
        }
        async with httpx.AsyncClient(timeout=self.config.request_timeout_s) as client:
            response = await client.get(request.url, headers=headers)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "json" not in content_type and not request.url.lower().endswith(".json"):
                # If the URL looked like an API but didn't return JSON, skip gracefully.
                return ScrapeResult(
                    url=request.url,
                    ok=False,
                    signals=[],
                    error=f"Expected JSON response, got content-type '{content_type}'.",
                )
            payload = response.json()

        extracted = self._extract_numeric_value(payload)
        if extracted is None:
            return ScrapeResult(
                url=request.url,
                ok=False,
                signals=[],
                error="No numeric value found in JSON payload.",
            )

        path, value = extracted
        signal = ResolutionSignal(
            url=request.url,
            metric="json_numeric_value",
            value=value,
            as_of_utc=utc_now_iso(),
            parser=self.name,
            confidence="medium",
            note=f"Heuristic extraction path: {path}",
            raw={"path": path},
        )
        return ScrapeResult(url=request.url, ok=True, signals=[signal], error=None)
