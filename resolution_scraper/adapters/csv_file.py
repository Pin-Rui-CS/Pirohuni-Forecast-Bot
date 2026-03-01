from __future__ import annotations

import csv
from io import StringIO
from urllib.parse import urlparse

import httpx

from ..config import ScraperConfig
from ..models import ResolutionSignal, ScrapeRequest, ScrapeResult, utc_now_iso
from .base import SourceAdapter


class CsvAdapter(SourceAdapter):
    name = "csv"

    def __init__(self, config: ScraperConfig) -> None:
        self.config = config
        self.numeric_priority = ["count", "total", "value", "articles", "cases"]

    def can_handle(self, request: ScrapeRequest) -> bool:
        return urlparse(request.url).path.lower().endswith(".csv")

    @staticmethod
    def _parse_number(text: str | None) -> float | int | None:
        if text is None:
            return None
        cleaned = text.strip().replace(",", "")
        if not cleaned:
            return None
        try:
            value = float(cleaned)
            return int(value) if value.is_integer() else value
        except ValueError:
            return None

    def _select_numeric_column(self, row: dict[str, str]) -> tuple[str, float | int] | None:
        keys = list(row.keys())
        ordered = [k for k in keys if any(p in k.lower() for p in self.numeric_priority)]
        ordered += [k for k in keys if k not in ordered]
        for key in ordered:
            value = self._parse_number(row.get(key))
            if value is not None:
                return key, value
        return None

    async def fetch(self, request: ScrapeRequest) -> ScrapeResult:
        headers = {"User-Agent": self.config.user_agent}
        async with httpx.AsyncClient(timeout=self.config.request_timeout_s) as client:
            response = await client.get(request.url, headers=headers)
            response.raise_for_status()
            content = response.text

        reader = csv.DictReader(StringIO(content))
        rows = list(reader)
        if not rows:
            return ScrapeResult(
                url=request.url,
                ok=False,
                signals=[],
                error="CSV has no data rows.",
            )

        last_row = rows[-1]
        selected = self._select_numeric_column(last_row)
        if selected is None:
            return ScrapeResult(
                url=request.url,
                ok=False,
                signals=[],
                error="No numeric column found in final CSV row.",
            )

        column, value = selected
        signal = ResolutionSignal(
            url=request.url,
            metric=f"csv_{column}",
            value=value,
            as_of_utc=utc_now_iso(),
            parser=self.name,
            confidence="medium",
            note="Using last CSV row with heuristic numeric column selection.",
            raw={"row_index": len(rows) - 1, "column": column},
        )
        return ScrapeResult(url=request.url, ok=True, signals=[signal], error=None)
