from __future__ import annotations

import re

import httpx

from ..config import ScraperConfig
from ..models import ResolutionSignal, ScrapeRequest, ScrapeResult, utc_now_iso
from .base import SourceAdapter

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover - optional dependency safety
    BeautifulSoup = None


KEYWORD_NUMBER_RE = re.compile(
    r"(articles?|count|total|value|population|cases)\D{0,30}(-?\d[\d,]*(?:\.\d+)?)",
    flags=re.IGNORECASE,
)
GENERIC_NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def _coerce_number(number_text: str) -> float | int | None:
    cleaned = number_text.replace(",", "").strip()
    if not cleaned:
        return None
    try:
        value = float(cleaned)
        return int(value) if value.is_integer() else value
    except ValueError:
        return None


def extract_number_from_html_text(text: str) -> tuple[float | int | None, str]:
    keyword_match = KEYWORD_NUMBER_RE.search(text)
    if keyword_match:
        value = _coerce_number(keyword_match.group(2))
        if value is not None:
            return value, "keyword_number_regex"

    generic_match = GENERIC_NUMBER_RE.search(text)
    if generic_match:
        value = _coerce_number(generic_match.group(0))
        if value is not None:
            return value, "generic_number_regex"

    return None, "none"


class StaticHtmlAdapter(SourceAdapter):
    name = "html_static"

    def __init__(self, config: ScraperConfig) -> None:
        self.config = config

    def can_handle(self, request: ScrapeRequest) -> bool:
        # Keep this broad; it acts as a fallback for unknown sources.
        return True

    async def fetch(self, request: ScrapeRequest) -> ScrapeResult:
        headers = {"User-Agent": self.config.user_agent}
        async with httpx.AsyncClient(timeout=self.config.request_timeout_s) as client:
            response = await client.get(request.url, headers=headers)
            response.raise_for_status()
            html = response.text

        lowered = html.lower()
        if "__next_data__" in lowered or "enable javascript" in lowered:
            return ScrapeResult(
                url=request.url,
                ok=False,
                signals=[],
                error="Likely JS-rendered page; static HTML insufficient.",
            )

        if BeautifulSoup is not None:
            soup = BeautifulSoup(html, "lxml")
            text = " ".join(soup.stripped_strings)
            title = soup.title.get_text(strip=True) if soup.title else ""
        else:
            text = re.sub(r"<[^>]+>", " ", html)
            title = ""

        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 20:
            return ScrapeResult(
                url=request.url,
                ok=False,
                signals=[],
                error="Insufficient page text for static parsing.",
            )

        value, extraction_method = extract_number_from_html_text(text)
        if value is None:
            return ScrapeResult(
                url=request.url,
                ok=False,
                signals=[],
                error="No parseable number found in static HTML text.",
            )

        signal = ResolutionSignal(
            url=request.url,
            metric="html_detected_value",
            value=value,
            as_of_utc=utc_now_iso(),
            parser=self.name,
            confidence="low",
            note=f"Extraction method: {extraction_method}. Title: {title[:120]}",
            raw={"title": title[:240]},
        )
        return ScrapeResult(url=request.url, ok=True, signals=[signal], error=None)
