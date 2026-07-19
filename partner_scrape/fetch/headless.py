"""Headless Fetcher: ``PlaywrightFetcher``, retrieving one URL's fully
client-rendered HTML via a real headless browser.

See sprint.md's Architecture > Headless Fetcher: ``PlaywrightFetcher``
implements the exact same ``Fetcher.get(url, headers=None) ->
FetchResponse`` contract ``fetch/fetcher.py``'s ``UrllibFetcher``
does, so it drops into ``PoliteFetcher``'s existing ``fetcher=``
constructor parameter (``fetch/cache.py``) with zero changes to
``PoliteFetcher``, ``fetch/robots.py``, or ``fetch/throttle.py`` -- no
adapter or discovery module ever needs to know headless fetching
exists (Pipeline, ticket 005, is the only module that constructs this
class).

**Critical constraint**: ``playwright`` is an optional dependency
group (``pyproject.toml``: ``[project.optional-dependencies] headless
= ["playwright>=1.40"]``), never a base dependency. The real ``import
playwright`` call is deferred all the way into
:func:`_default_page_factory`, which only runs on the first real
(non-fixture) call to :meth:`PlaywrightFetcher.get` -- never at module
import time, never in ``__init__``. Tests inject a fixture
``page_factory`` (matching this repo's existing ``Fetcher``/
``LLMClient`` DI pattern -- see ``fetch/fetcher.py`` and
``enrich/llm_client.py`` -- applied one level deeper here, since the
*dependency itself*, not just the network call, must be avoidable) and
so never trigger that import; the whole default test suite runs with
``playwright`` fully uninstalled.
"""

from __future__ import annotations

from typing import Callable, Protocol

from partner_scrape.fetch.fetcher import DEFAULT_USER_AGENT, FetchResponse

#: Fixed network-idle wait timeout (milliseconds), applied before
#: reading rendered content. No per-source tuning this ticket (see
#: sprint.md's Architecture > Open Question 4) -- a future ``config``
#: key can introduce per-source overrides if a real registered site
#: ever needs one; this constant is the single source of truth until
#: then.
NETWORK_IDLE_TIMEOUT_MS = 15_000

#: Name of the optional dependency group (pyproject.toml
#: ``[project.optional-dependencies]`` key) that provides
#: ``playwright`` -- named here once so the actionable error message
#: below and ``pyproject.toml`` cannot silently drift apart.
HEADLESS_EXTRA_NAME = "headless"


class HeadlessNavigationResponse(Protocol):
    """The minimal shape read off a Playwright navigation ``Response``
    (or a fixture double standing in for one).
    """

    status: int


class HeadlessPage(Protocol):
    """The minimal Playwright ``Page``-shaped seam this module depends
    on. Deliberately narrow -- a fixture test double needs only
    ``goto``/``content`` to stand in for a real browser page, exactly
    as ``fetch/fetcher.py``'s ``Fetcher`` protocol lets
    ``FixtureFetcher`` stand in for ``UrllibFetcher`` with no real
    socket.
    """

    def goto(
        self,
        url: str,
        timeout: float | None = None,
        wait_until: str | None = None,
    ) -> HeadlessNavigationResponse:
        """Navigate to ``url``, waiting for ``wait_until`` (bounded by
        ``timeout`` milliseconds) before returning the navigation
        response.
        """
        ...

    def content(self) -> str:
        """Return the current (fully rendered) page HTML."""
        ...


class PlaywrightNotInstalledError(RuntimeError):
    """Raised when a real (non-fixture) ``PlaywrightFetcher`` is used
    but the ``playwright`` package is not installed.

    Deliberately not a bare ``ImportError`` reraised as-is -- this
    names the specific optional dependency group an operator needs to
    install, matching sprint.md's explicit requirement that a source
    flagged ``headless`` without ``playwright`` installed produce "a
    clear, actionable error ... rather than a bare ImportError". Still
    just an ``Exception`` subclass, so Pipeline's existing per-source
    ``try/except`` (SUC-008's error flow) catches it with no new
    error-handling code.
    """

    def __init__(self) -> None:
        super().__init__(
            "PlaywrightFetcher requires the optional "
            f"{HEADLESS_EXTRA_NAME!r} dependency group, which is not "
            "installed. Install it with: "
            f"uv sync --extra {HEADLESS_EXTRA_NAME} "
            "(see pyproject.toml's [project.optional-dependencies])."
        )


def _default_page_factory() -> HeadlessPage:
    """Lazily import ``playwright`` and launch a real headless browser
    page.

    This is the ONLY place in this module -- and, transitively, in
    ``partner_scrape.fetch`` -- that imports ``playwright``. It is
    called at most once per :class:`PlaywrightFetcher` instance, only
    when that instance is constructed with no injected
    ``page_factory`` and :meth:`PlaywrightFetcher.get` is actually
    called for the first time. Fixture-backed tests always inject
    their own ``page_factory`` and so never reach this function, which
    is what lets the default test suite import and exercise this
    module with ``playwright`` fully uninstalled.

    No credentials or secrets are placed in the launched browser's
    profile/environment (sprint.md's Migration Concerns risk note).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PlaywrightNotInstalledError() from exc

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch()
    context = browser.new_context(user_agent=DEFAULT_USER_AGENT)
    return context.new_page()


class PlaywrightFetcher:
    """The headless ``Fetcher``: retrieves one URL's fully
    client-rendered HTML via a real (or, in tests, fixture-double)
    browser page.

    Implements the same ``Fetcher.get(url, headers=None) ->
    FetchResponse`` contract ``UrllibFetcher`` does (``fetch/
    fetcher.py``) -- ``PoliteFetcher`` (``fetch/cache.py``) neither
    knows nor cares which concrete ``Fetcher`` it wraps.

    ``page_factory``, if given, is called at most once (its return
    value is cached and reused across every ``get()`` call on this
    instance) and must return a ``HeadlessPage``-shaped object -- real
    or fixture. Omit it to get a single lazily-constructed real
    Playwright page, built only on the first real ``get()`` call
    (never at ``__init__`` time, never at module import time) -- see
    :func:`_default_page_factory`.
    """

    def __init__(self, page_factory: Callable[[], HeadlessPage] | None = None) -> None:
        self._page_factory = page_factory or _default_page_factory
        self._page: HeadlessPage | None = None

    def _get_page(self) -> HeadlessPage:
        if self._page is None:
            self._page = self._page_factory()
        return self._page

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        """Navigate to ``url``, wait for network-idle (bounded by
        :data:`NETWORK_IDLE_TIMEOUT_MS`), and return the rendered HTML
        as a ``FetchResponse``.

        ``status`` on the returned ``FetchResponse`` is always taken
        from the real navigation response -- never hardcoded -- so
        ``PoliteFetcher``'s ``200 <= status < 300`` cache-write branch
        behaves identically for a headless fetch and a static one.

        Raises:
            PlaywrightNotInstalledError: no ``page_factory`` was
                injected and the ``playwright`` package is not
                installed.
        """
        page = self._get_page()
        if headers:
            set_extra_headers = getattr(page, "set_extra_http_headers", None)
            if set_extra_headers is not None:
                set_extra_headers(headers)

        navigation = page.goto(url, timeout=NETWORK_IDLE_TIMEOUT_MS, wait_until="networkidle")
        body = page.content()
        response_headers = dict(getattr(navigation, "headers", None) or {})

        return FetchResponse(
            url=url,
            status=navigation.status,
            headers=response_headers,
            body=body,
        )
