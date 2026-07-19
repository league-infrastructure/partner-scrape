"""Per-domain rate limiting for polite fetching.

A small in-memory ``{domain: last_fetch_time}`` map. Both the clock and
the sleep function are injectable so tests can verify "at least N
seconds between fetches to the same domain" deterministically -- no
real wall-clock wait, per this ticket's Acceptance Criteria.
"""

from __future__ import annotations

import time
from typing import Callable

#: Applied when a caller doesn't pass an explicit ``rate_limit_seconds``.
#: Kept in sync with the Source Registry's own
#: ``_ACQUISITION_POLICY_DEFAULTS["rate_limit_seconds"]`` (ticket 002) --
#: this module doesn't import that constant (Fetch & Cache has no
#: dependency on Registry, per sprint.md's dependency diagram), so the
#: value is simply duplicated here deliberately.
DEFAULT_RATE_LIMIT_SECONDS = 1.0


class Throttle:
    """Enforces a minimum delay between requests to the same domain."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._clock = clock
        self._sleep = sleep
        self._last_fetch: dict[str, float] = {}

    def wait(
        self, domain: str, rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS
    ) -> None:
        """Block until ``rate_limit_seconds`` have elapsed since the last
        call for ``domain``, then record this call as the new last-fetch
        time for it.

        The recorded last-fetch time after sleeping is computed as
        ``last + rate_limit_seconds`` rather than re-reading the clock,
        so behavior is deterministic under an injected fake clock/sleep
        pair regardless of whether the fake ``sleep`` also advances the
        fake clock.
        """
        now = self._clock()
        last = self._last_fetch.get(domain)
        if last is None:
            self._last_fetch[domain] = now
            return

        elapsed = now - last
        remaining = rate_limit_seconds - elapsed
        if remaining > 0:
            self._sleep(remaining)
            self._last_fetch[domain] = last + rate_limit_seconds
        else:
            self._last_fetch[domain] = now
