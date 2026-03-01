from __future__ import annotations

import re

from ..config import ScraperConfig
from ..models import ResolutionSignal, ScrapeRequest, ScrapeResult, utc_now_iso
from .base import SourceAdapter
from .html_static import extract_number_from_html_text

try:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    from playwright.async_api import async_playwright
except Exception:  # pragma: no cover - optional dependency safety
    PlaywrightTimeoutError = Exception
    async_playwright = None


class BrowserAdapter(SourceAdapter):
    name = "browser_playwright"

    def __init__(self, config: ScraperConfig) -> None:
        self.config = config

    def can_handle(self, request: ScrapeRequest) -> bool:
        return True

    async def fetch(self, request: ScrapeRequest) -> ScrapeResult:
        if async_playwright is None:
            return ScrapeResult(
                url=request.url,
                ok=False,
                signals=[],
                error="Playwright is not installed in this environment.",
            )

        timeout_ms = int(self.config.browser_timeout_s * 1000)
        browser = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(request.url, wait_until="networkidle", timeout=timeout_ms)
                body_text = await page.inner_text("body")
                text = re.sub(r"\s+", " ", body_text).strip()
        except PlaywrightTimeoutError:
            return ScrapeResult(
                url=request.url,
                ok=False,
                signals=[],
                error="Playwright timed out while rendering page.",
            )
        except Exception as exc:
            return ScrapeResult(
                url=request.url,
                ok=False,
                signals=[],
                error=f"Playwright browser parse failed: {exc}",
            )
        finally:
            if browser is not None:
                await browser.close()

        if len(text) < 20:
            return ScrapeResult(
                url=request.url,
                ok=False,
                signals=[],
                error="Rendered page text too short for extraction.",
            )

        value, extraction_method = extract_number_from_html_text(text)
        if value is None:
            return ScrapeResult(
                url=request.url,
                ok=False,
                signals=[],
                error="No parseable number found after browser render.",
            )

        signal = ResolutionSignal(
            url=request.url,
            metric="browser_detected_value",
            value=value,
            as_of_utc=utc_now_iso(),
            parser=self.name,
            confidence="low",
            note=f"Extraction method: {extraction_method}.",
            raw=None,
        )
        return ScrapeResult(url=request.url, ok=True, signals=[signal], error=None)
