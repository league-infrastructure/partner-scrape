"""The ``Fetcher`` protocol and its real, stdlib-based implementation.

Every other piece of this package (``robots.py``, ``cache.py``) talks to
remote resources exclusively through a ``Fetcher`` -- never directly
through ``urllib``. That is the injectable seam sprint.md's Design
Rationale calls for: production code uses ``UrllibFetcher`` (stdlib
``urllib.request``, zero new dependencies, matching
``dev/fetch_tec_api.py``'s proven approach), while tests substitute a
fixture-backed fake that returns canned responses with no real socket
ever opened.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

#: Polite default User-Agent, matching dev/fetch_tec_api.py's
#: already-proven value for these sites.
DEFAULT_USER_AGENT = "STEM-Calendar-Bot/1.0 (educational research)"


@dataclass
class FetchResponse:
    """One raw HTTP response, exactly as retrieved (or replayed from cache).

    ``status`` is whatever actually came back over the wire -- including
    ``304`` for a conditional-GET "not modified" reply. Turning a 304
    into a reused cached body is the cache layer's job (``cache.py``),
    not this dataclass's.
    """

    url: str
    status: int
    headers: dict[str, str]
    body: str
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class Fetcher(Protocol):
    """Injectable seam for retrieving one URL.

    Implementations must not raise on a 304 or other non-2xx status --
    return a ``FetchResponse`` describing it instead, so callers (the
    robots check, the cache layer) can inspect ``status`` uniformly
    without a try/except around every call.
    """

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        """Issue a GET request to ``url`` with optional extra ``headers``."""
        ...


class UrllibFetcher:
    """The real ``Fetcher``: stdlib ``urllib.request``, no new dependency."""

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT, timeout: float = 30.0):
        self.user_agent = user_agent
        self.timeout = timeout

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        request_headers = {"User-Agent": self.user_agent, **(headers or {})}
        request = urllib.request.Request(url, headers=request_headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                return FetchResponse(
                    url=url,
                    status=response.status,
                    headers=dict(response.headers.items()),
                    body=body,
                )
        except urllib.error.HTTPError as exc:
            # A 304 (and other non-2xx) arrive as HTTPError from
            # urlopen -- normalize them into the same FetchResponse
            # shape a 2xx gets, so callers never need a try/except.
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            headers = dict(exc.headers.items()) if exc.headers else {}
            return FetchResponse(url=url, status=exc.code, headers=headers, body=body)
