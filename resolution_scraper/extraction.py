from __future__ import annotations

import re
from urllib.parse import urlparse

MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^)]+)\)")
PLAIN_URL_RE = re.compile(r"(https?://[^\s)>\]]+)")


def _clean_url(url: str) -> str:
    return url.rstrip(".,;:!?")


def extract_resolution_urls(
    resolution_criteria: str,
    fine_print: str = "",
    description: str = "",
) -> list[str]:
    text = "\n".join(
        part for part in [resolution_criteria, fine_print, description] if part
    )

    urls: list[str] = []
    urls.extend(MARKDOWN_LINK_RE.findall(text))
    urls.extend(PLAIN_URL_RE.findall(text))

    deduped: list[str] = []
    seen = set()
    for raw_url in urls:
        url = _clean_url(raw_url)
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def classify_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()

    if "wikipedia.org" in host:
        return "wikipedia"
    if path.endswith(".json") or "api" in path or "format=json" in parsed.query:
        return "json_api"
    if path.endswith(".csv"):
        return "csv"
    if path.endswith(".xml"):
        return "xml"
    if path.endswith(".pdf"):
        return "pdf"
    return "html"
