from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ScraperConfig:
    request_timeout_s: float = 12.0
    max_retries: int = 2
    retry_backoff_s: float = 0.75
    user_agent: str = "Pirohuni-Forecast-Bot/1.0"
    use_browser_fallback: bool = False
    browser_timeout_s: float = 20.0
    per_run_cache_ttl_s: int = 3600
    max_parallel_fetches: int = 4
