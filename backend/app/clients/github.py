"""GitHub REST API client for pull requests.

Handles token auth and primary rate limiting (sleeps until reset when the
remaining budget runs low). Anonymous use is possible but capped at 60 req/hr,
so a token is strongly recommended for periodic polling.

Note: the GitHub "list pulls" endpoint cannot filter by ``updated_at`` server
side, so delta polling is done client-side -- results come back sorted by
updated desc and we stop once we pass the cursor.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_ROOT = "https://api.github.com"


class GitHubClient:
    """Thin wrapper over the GitHub pulls API."""

    def __init__(self, token: str | None = None, timeout: float = 30.0) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(headers=headers, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def _respect_rate_limit(self, resp: httpx.Response) -> None:
        """Sleep until reset if we're nearly out of primary-rate budget."""
        remaining = resp.headers.get("X-RateLimit-Remaining")
        reset = resp.headers.get("X-RateLimit-Reset")
        if remaining is not None and reset is not None and int(remaining) < 10:
            wait = max(0, int(reset) - int(time.time())) + 1
            logger.warning("GitHub rate limit low; sleeping %ss", wait)
            time.sleep(min(wait, 120))  # cap the nap so a demo never hangs long

    def iter_pulls(
        self,
        repo: str,
        *,
        state: str = "open",  # open | closed | all
        updated_since: str | None = None,
        max_pulls: int = 0,
        delay: float = 0.2,
    ) -> Iterator[dict[str, Any]]:
        """Yield pull requests for ``owner/name``, newest updates first.

        Stops early once a PR older than ``updated_since`` is seen (the list is
        sorted by updated desc), giving cheap delta polling.
        """
        page = 1
        yielded = 0
        while True:
            url = f"{API_ROOT}/repos/{repo}/pulls"
            params = {
                "state": state,
                "sort": "updated",
                "direction": "desc",
                "per_page": 100,
                "page": page,
            }
            resp = self._client.get(url, params=params)
            self._respect_rate_limit(resp)
            resp.raise_for_status()
            pulls = resp.json()
            if not pulls:
                break

            for pr in pulls:
                if updated_since and pr.get("updated_at", "") < updated_since:
                    return  # everything after this is older too
                yield pr
                yielded += 1
                if max_pulls and yielded >= max_pulls:
                    return

            if len(pulls) < 100:
                break
            page += 1
            time.sleep(delay)
