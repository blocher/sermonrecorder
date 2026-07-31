from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from django.conf import settings

from .processing import PermanentProcessingError, RetryableProcessingError


@dataclass(frozen=True)
class MagisteriumCitation:
    cited_text: str
    document_title: str
    document_author: str
    document_year: str
    document_reference: str
    source_url: str


@dataclass(frozen=True)
class MagisteriumChatResult:
    content: str
    citations: tuple[MagisteriumCitation, ...]


@dataclass(frozen=True)
class MagisteriumSearchHit:
    title: str
    author: str
    year: str
    excerpt: str
    source_url: str
    category: str


class MagisteriumClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        tier: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ):
        self.api_key = (api_key if api_key is not None else settings.MAGISTERIUM_API_KEY).strip()
        self.tier = (tier if tier is not None else settings.MAGISTERIUM_TIER).strip()
        self.base_url = (
            base_url if base_url is not None else settings.MAGISTERIUM_BASE_URL
        ).rstrip("/")
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.MAGISTERIUM_TIMEOUT_SECONDS
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search(
        self,
        query: str,
        *,
        num_results: int = 5,
        category: str = "auto",
    ) -> tuple[MagisteriumSearchHit, ...]:
        payload: dict[str, Any] = {
            "query": query[:1024],
            "numResults": max(1, min(num_results, 100)),
            "category": category,
        }
        if self.tier:
            payload["tier"] = self.tier
        data = self._post("/search", payload)
        return _parse_search_hits(data)

    def chat(self, message: str, *, model: str = "magisterium-1") -> MagisteriumChatResult:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "stream": False,
        }
        if self.tier:
            payload["tier"] = self.tier
        data = self._post("/chat/completions", payload)
        choices = data.get("choices") or []
        if not choices:
            raise RetryableProcessingError(
                "Magisterium chat returned no choices."
            )
        message_payload = choices[0].get("message") or {}
        content = str(message_payload.get("content") or "").strip()
        citations = tuple(
            MagisteriumCitation(
                cited_text=str(item.get("cited_text") or "").strip(),
                document_title=str(item.get("document_title") or "").strip(),
                document_author=str(item.get("document_author") or "").strip(),
                document_year=str(item.get("document_year") or "").strip(),
                document_reference=str(item.get("document_reference") or "").strip(),
                source_url=str(item.get("source_url") or "").strip(),
            )
            for item in data.get("citations") or []
            if isinstance(item, dict)
        )
        return MagisteriumChatResult(content=content, citations=citations)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise PermanentProcessingError(
                "MAGISTERIUM_API_KEY is not configured."
            )
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Pewcorder/0.1",
        }
        if self.tier:
            headers["X-Magisterium-Tier"] = self.tier
        timeout = httpx.Timeout(self.timeout_seconds)
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as error:
            raise RetryableProcessingError(
                "Magisterium API request timed out."
            ) from error
        except httpx.HTTPError as error:
            raise RetryableProcessingError(
                f"Magisterium API request failed: {error}"
            ) from error

        if response.status_code in {408, 429} or response.status_code >= 500:
            raise RetryableProcessingError(
                f"Magisterium API temporary error ({response.status_code})."
            )
        if response.status_code == 401:
            detail = _error_message(response)
            raise PermanentProcessingError(
                f"Magisterium API authentication failed: {detail}"
            )
        if response.status_code >= 400:
            detail = _error_message(response)
            raise RetryableProcessingError(
                f"Magisterium API error ({response.status_code}): {detail}"
            )
        try:
            data = response.json()
        except ValueError as error:
            raise RetryableProcessingError(
                "Magisterium API returned invalid JSON."
            ) from error
        if not isinstance(data, dict):
            raise RetryableProcessingError(
                "Magisterium API returned an unexpected payload."
            )
        return data


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return (response.text or f"HTTP {response.status_code}").strip()
    if isinstance(payload, dict):
        for key in ("message", "error", "detail"):
            value = payload.get(key)
            if isinstance(value, dict):
                nested = value.get("message") or value.get("code")
                if nested:
                    return str(nested)
            if value:
                return str(value)
    return f"HTTP {response.status_code}"


def _parse_search_hits(data: dict[str, Any]) -> tuple[MagisteriumSearchHit, ...]:
    raw_items = _search_item_list(data)
    hits: list[MagisteriumSearchHit] = []
    seen: set[str] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        document_title = _first_str(
            item,
            "document_title",
            "documentTitle",
            "name",
        )
        section_title = _first_str(item, "title")
        title = document_title or section_title
        if document_title and section_title and section_title.casefold() != document_title.casefold():
            title = f"{document_title} — {section_title}"
        author = _first_str(
            item,
            "document_author",
            "author",
            "documentAuthor",
        )
        year = _first_str(item, "document_year", "year", "documentYear")
        reference = _first_str(item, "ref", "document_reference", "documentReference")
        if not year and reference:
            year = reference
        excerpt = _first_str(
            item,
            "cited_text",
            "text",
            "excerpt",
            "snippet",
            "content",
            "passage",
        )
        source_url = _first_str(item, "source_url", "url", "sourceUrl", "link")
        category = _first_str(item, "category", "source_category") or "auto"
        if not title and not excerpt:
            continue
        dedupe_key = (source_url or title or excerpt).casefold()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        hits.append(
            MagisteriumSearchHit(
                title=title or "Untitled source",
                author=author,
                year=year,
                excerpt=excerpt,
                source_url=source_url,
                category=category,
            )
        )
    return tuple(hits)


def _search_item_list(data: dict[str, Any]) -> list[Any]:
    nested = data.get("data")
    candidates: list[Any] = [
        data.get("results"),
        data.get("documents"),
        data.get("items"),
        nested.get("results") if isinstance(nested, dict) else None,
        nested.get("documents") if isinstance(nested, dict) else None,
        nested.get("items") if isinstance(nested, dict) else None,
        nested if isinstance(nested, list) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, list):
            return candidate
    return []


def _first_str(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""
