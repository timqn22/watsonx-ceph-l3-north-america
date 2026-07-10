"""Redmine REST API client.

Ported and slimmed from the original prototype's scraper. Supports delta
polling (``updated_since``) so periodic syncs only fetch what changed, and
retries transient 5xx errors with backoff. Talks JSON only.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PAGE_CAP = 100  # Redmine hard limit per page


class RedmineClient:
    """Thin wrapper over the Redmine issues API."""

    def __init__(
        self,
        base_url: str = "https://tracker.ceph.com",
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        headers = {"Accept": "application/json"}
        if api_key:
            headers["X-Redmine-API-Key"] = api_key
        self._client = httpx.Client(headers=headers, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET with simple exponential backoff on 5xx / network errors."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        delay = 1.0
        for attempt in range(4):
            try:
                resp = self._client.get(url, params=params)
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        "server error", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status is not None and status < 500 and status != 429:
                    logger.warning("Redmine GET %s failed (%s)", url, status)
                    raise
                if attempt == 3:
                    logger.error("Redmine GET %s failed after retries: %s", url, exc)
                    raise
                time.sleep(delay)
                delay *= 2
        raise RuntimeError("unreachable")

    def iter_issues(
        self,
        *,
        project_id: str | None = None,
        status: str = "open",  # open | closed | *
        updated_since: str | None = None,
        max_issues: int = 0,
        include: str | None = "journals",
        delay: float = 0.3,
    ) -> Iterator[dict[str, Any]]:
        """Yield issues page by page, newest updates first.

        ``updated_since`` uses Redmine's ``>=`` filter operator on updated_on so
        repeated syncs are cheap. ``max_issues`` of 0 means no cap.
        """
        offset = 0
        yielded = 0
        while True:
            params: dict[str, Any] = {
                "limit": PAGE_CAP,
                "offset": offset,
                "status_id": status,
                "sort": "updated_on:desc",
            }
            if project_id:
                params["project_id"] = project_id
            if include:
                params["include"] = include
            if updated_since:
                params["updated_on"] = f">={updated_since}"

            payload = self._get("issues.json", params)
            issues = payload.get("issues", [])
            if not issues:
                break

            for issue in issues:
                yield issue
                yielded += 1
                if max_issues and yielded >= max_issues:
                    return

            offset += PAGE_CAP
            if offset >= payload.get("total_count", 0):
                break
            time.sleep(delay)
