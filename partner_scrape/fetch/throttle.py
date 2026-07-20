"""Per-domain rate limiting for polite fetching.

A small in-memory ``{domain: last_fetch_time}`` map. Both the clock and
the sleep function are injectable so tests can verify "at least N
seconds between fetches to the same domain" deterministically -- no
real wall-clock wait, per this ticket's Acceptance Criteria.

Thread-safety: a single ``Throttle`` instance is shared across every
worker thread in the pipeline's source-level ``ThreadPoolExecutor``
(concurrent sources, per-domain politeness -- see ``pipeline.py``'s
``run()``). Two concurrent ``wait()`` calls for the *same* domain must
never interleave their read-check-sleep-write sequence (that would
corrupt ``_last_fetch`` and could let both calls through without
actually waiting the full interval), while two calls for *different*
domains must never block each other (that would defeat the whole point
of fetching different sources concurrently). A per-domain
``threading.Lock`` gives both: ``wait()`` for a given domain is fully
serialized end-to-end (check, sleep, update all happen atomically with
respect to other threads on that same domain), while unrelated domains
proceed under their own, independent locks.
"""

from __future__ import annotations

import threading
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
    """Enforces a minimum delay between requests to the same domain.

    Safe to share across threads: ``wait()`` for one domain never blocks
    ``wait()`` for a different domain, but concurrent calls for the same
    domain are serialized so the per-domain interval is still enforced
    exactly (never less than ``rate_limit_seconds`` apart), regardless
    of how many threads race to fetch that domain at once.
    """

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._clock = clock
        self._sleep = sleep
        self._last_fetch: dict[str, float] = {}
        # One lock per domain (created lazily, on first use) -- this is
        # what lets unrelated domains proceed fully concurrently. The
        # locks dict itself is a second piece of shared mutable state,
        # so creating a new entry in it is guarded by `_locks_guard`.
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def _lock_for(self, domain: str) -> threading.Lock:
        """Return this domain's lock, creating it on first use.

        Guarded by `_locks_guard` only for the (fast) dict lookup/insert
        -- never held while waiting on the per-domain lock itself, so
        this never becomes a second cross-domain bottleneck.
        """
        with self._locks_guard:
            lock = self._locks.get(domain)
            if lock is None:
                lock = threading.Lock()
                self._locks[domain] = lock
            return lock

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

        The whole check-sleep-update sequence runs under ``domain``'s
        own lock, so concurrent callers for the same domain queue up
        and each still waits its full share of the interval -- none of
        them can read a stale ``_last_fetch[domain]`` value that lets
        them slip through early.
        """
        with self._lock_for(domain):
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
