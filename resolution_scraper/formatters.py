from __future__ import annotations

from .models import ResolutionSignal, ScrapeResult


def _confidence_rank(level: str) -> int:
    if level == "high":
        return 3
    if level == "medium":
        return 2
    return 1


def format_resolution_snapshot(
    signals: list[ResolutionSignal],
    max_items: int = 5,
) -> str:
    if not signals:
        return "No structured resolution-source signals extracted."

    ordered = sorted(signals, key=lambda s: _confidence_rank(s.confidence), reverse=True)
    chosen = ordered[:max_items]
    lines = []
    for signal in chosen:
        lines.append(
            f"- [{signal.confidence}] {signal.metric} = {signal.value} "
            f"(as_of={signal.as_of_utc}, parser={signal.parser}, url={signal.url})"
        )
    return "\n".join(lines)


def format_scrape_errors(results: list[ScrapeResult], max_items: int = 3) -> str:
    failed = [r for r in results if not r.ok and r.error]
    if not failed:
        return ""
    lines = ["Resolution scrape errors:"]
    for item in failed[:max_items]:
        lines.append(f"- {item.url}: {item.error}")
    return "\n".join(lines)
