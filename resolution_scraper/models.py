from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

Confidence = Literal["high", "medium", "low"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class ScrapeRequest:
    question_id: int
    question_title: str
    question_type: str
    scheduled_resolve_time: str | None
    url: str
    resolution_text: str


@dataclass(slots=True)
class ResolutionSignal:
    url: str
    metric: str
    value: float | int | str | None
    as_of_utc: str
    parser: str
    confidence: Confidence
    note: str = ""
    raw: dict[str, Any] | None = None


@dataclass(slots=True)
class ScrapeResult:
    url: str
    ok: bool
    signals: list[ResolutionSignal]
    error: str | None = None
