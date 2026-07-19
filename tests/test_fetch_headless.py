"""Tests for partner_scrape.fetch.headless: PlaywrightFetcher.

Every test exercises PlaywrightFetcher through an injected fixture
``page_factory`` (``FixtureHeadlessPage`` below) -- no test in this
file launches a real browser or imports the real ``playwright``
package, per sprint.md's Design Rationale ("PlaywrightFetcher defers
its real import playwright call to first real (non-fixture) use").
This file (and the module it tests) must import and run cleanly with
``playwright`` fully uninstalled -- confirmed by running this suite in
this project's default environment, which does not install the
``headless`` optional dependency group at all.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from partner_scrape.fetch.cache import PoliteFetcher, read_cache_entry
from partner_scrape.fetch.headless import (
    NETWORK_IDLE_TIMEOUT_MS,
    HEADLESS_EXTRA_NAME,
    PlaywrightFetcher,
    PlaywrightNotInstalledError,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "fetch"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


@dataclass
class _FixtureNavigationResponse:
    """Stand-in for a real Playwright navigation ``Response`` -- the
    only piece of it PlaywrightFetcher reads is ``status`` (and,
    optionally, ``headers``).
    """

    status: int
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class FixtureHeadlessPage:
    """HeadlessPage test double -- returns canned rendered HTML and a
    canned navigation response per URL, no real browser process
    involved.

    ``pages`` maps a URL to ``(status, html)``. ``errors`` maps a URL
    to an exception ``goto()`` should raise instead of returning
    normally, for exercising a timeout/navigation-failure case. Every
    call to ``goto()`` is recorded in ``calls`` so tests can assert on
    the wait strategy (``wait_until``/``timeout``) PlaywrightFetcher
    applied.
    """

    pages: dict[str, tuple[int, str]]
    errors: dict[str, Exception] = field(default_factory=dict)
    calls: list[dict[str, object]] = field(default_factory=list)
    extra_headers_calls: list[dict[str, str]] = field(default_factory=list)
    _current_url: str | None = field(default=None, repr=False)

    def goto(self, url: str, timeout: float | None = None, wait_until: str | None = None):
        self.calls.append({"url": url, "timeout": timeout, "wait_until": wait_until})
        if url in self.errors:
            raise self.errors[url]
        status, _html = self.pages[url]
        self._current_url = url
        return _FixtureNavigationResponse(status=status)

    def content(self) -> str:
        assert self._current_url is not None
        _status, html = self.pages[self._current_url]
        return html

    def set_extra_http_headers(self, headers: dict[str, str]) -> None:
        self.extra_headers_calls.append(dict(headers))


class TestPlaywrightFetcherGet:
    def test_returns_fetch_response_with_fixture_html_and_real_status(self):
        url = "https://example.org/events"
        html = "<html><body>Rendered via headless browser</body></html>"
        # A deliberately non-200 status proves PlaywrightFetcher reads
        # the real navigation response rather than hardcoding 200 --
        # PoliteFetcher's cache-write branches on this exact value.
        page = FixtureHeadlessPage(pages={url: (201, html)})
        fetcher = PlaywrightFetcher(page_factory=lambda: page)

        response = fetcher.get(url)

        assert response.url == url
        assert response.body == html
        assert response.status == 201

    def test_status_is_not_hardcoded_200_for_a_non_2xx_navigation(self):
        url = "https://example.org/missing"
        page = FixtureHeadlessPage(pages={url: (404, "<html>not found</html>")})
        fetcher = PlaywrightFetcher(page_factory=lambda: page)

        response = fetcher.get(url)

        assert response.status == 404

    def test_applies_bounded_network_idle_wait(self):
        url = "https://example.org/events"
        page = FixtureHeadlessPage(pages={url: (200, "<html></html>")})
        fetcher = PlaywrightFetcher(page_factory=lambda: page)

        fetcher.get(url)

        assert len(page.calls) == 1
        assert page.calls[0]["wait_until"] == "networkidle"
        assert page.calls[0]["timeout"] == NETWORK_IDLE_TIMEOUT_MS

    def test_page_factory_is_called_at_most_once_across_multiple_gets(self):
        url1 = "https://example.org/a"
        url2 = "https://example.org/b"
        page = FixtureHeadlessPage(pages={url1: (200, "a"), url2: (200, "b")})
        factory_calls = []

        def factory():
            factory_calls.append(1)
            return page

        fetcher = PlaywrightFetcher(page_factory=factory)
        fetcher.get(url1)
        fetcher.get(url2)

        assert len(factory_calls) == 1

    def test_navigation_error_propagates(self):
        url = "https://example.org/slow"
        page = FixtureHeadlessPage(
            pages={},
            errors={url: TimeoutError("networkidle wait timed out")},
        )
        fetcher = PlaywrightFetcher(page_factory=lambda: page)

        with pytest.raises(TimeoutError):
            fetcher.get(url)

    def test_forwards_conditional_headers_to_the_page_when_present(self):
        url = "https://example.org/events"
        page = FixtureHeadlessPage(pages={url: (304, "")})
        fetcher = PlaywrightFetcher(page_factory=lambda: page)

        fetcher.get(url, headers={"If-None-Match": '"abc123"'})

        assert page.extra_headers_calls == [{"If-None-Match": '"abc123"'}]

    def test_no_extra_headers_call_when_headers_is_none(self):
        url = "https://example.org/events"
        page = FixtureHeadlessPage(pages={url: (200, "ok")})
        fetcher = PlaywrightFetcher(page_factory=lambda: page)

        fetcher.get(url)

        assert page.extra_headers_calls == []


class TestNoRealPlaywrightImport:
    def test_fixture_backed_use_never_imports_the_real_playwright_package(self):
        url = "https://example.org/events"
        page = FixtureHeadlessPage(pages={url: (200, "<html></html>")})
        fetcher = PlaywrightFetcher(page_factory=lambda: page)

        fetcher.get(url)

        assert "playwright" not in sys.modules

    def test_constructing_without_a_page_factory_does_not_import_playwright(self):
        # Constructing a PlaywrightFetcher with no injected page_factory
        # must not, by itself, trigger the deferred real import --
        # only an actual (non-fixture) get() call may.
        PlaywrightFetcher()

        assert "playwright" not in sys.modules


class TestPlaywrightNotInstalled:
    def test_missing_playwright_produces_an_actionable_error_not_a_bare_import_error(
        self, monkeypatch
    ):
        # Force the deferred `from playwright.sync_api import
        # sync_playwright` import to fail deterministically,
        # regardless of whether playwright happens to be installed in
        # whatever environment runs this test -- this is what "forces
        # the deferred-import path to fail" per the ticket's
        # acceptance criteria.
        monkeypatch.setitem(sys.modules, "playwright", None)
        monkeypatch.setitem(sys.modules, "playwright.sync_api", None)

        fetcher = PlaywrightFetcher()

        with pytest.raises(PlaywrightNotInstalledError) as exc_info:
            fetcher.get("https://example.org/events")

        message = str(exc_info.value)
        assert HEADLESS_EXTRA_NAME in message
        assert "playwright" in message.lower()

    def test_error_is_not_a_bare_import_error_instance(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "playwright", None)
        monkeypatch.setitem(sys.modules, "playwright.sync_api", None)

        fetcher = PlaywrightFetcher()

        with pytest.raises(PlaywrightNotInstalledError) as exc_info:
            fetcher.get("https://example.org/events")

        # It's fine (and true) that this chains from an ImportError
        # via `raise ... from exc`, but the raised exception itself
        # must be the named, actionable type -- not a bare ImportError
        # propagating unadorned.
        assert not isinstance(exc_info.value, ImportError)
        assert isinstance(exc_info.value.__cause__, ImportError)


class TestPoliteFetcherWrapsPlaywrightFetcher:
    """PlaywrightFetcher, wrapped by PoliteFetcher, is exercised through
    the exact same robots.txt / rate-limit / cache code path
    UrllibFetcher already is (mirrors test_fetch_cache.py's
    TestRobotsCheck/TestCacheWrite patterns) -- zero changes required
    to fetch/cache.py, fetch/robots.py, or fetch/throttle.py.
    """

    def test_allowed_url_is_fetched_and_rendered_html_is_cached(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SCRAPE_CACHE_DIR", raising=False)
        url = "https://example.org/events"
        robots_url = "https://example.org/robots.txt"
        html = "<html><body>Rendered Event Listing</body></html>"
        page = FixtureHeadlessPage(
            pages={
                robots_url: (200, _read_fixture("robots_allow_all.txt")),
                url: (200, html),
            }
        )
        fetcher = PlaywrightFetcher(page_factory=lambda: page)
        polite = PoliteFetcher(cache_dir=tmp_path, fetcher=fetcher)

        response = polite.get(url)

        assert response.status == 200
        assert response.body == html

        entry = read_cache_entry(tmp_path, url)
        assert entry is not None
        assert entry["body"] == html
        assert entry["status"] == 200

    def test_disallowed_url_is_never_navigated_to(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SCRAPE_CACHE_DIR", raising=False)
        url = "https://example.org/events/secret"
        robots_url = "https://example.org/robots.txt"
        page = FixtureHeadlessPage(
            pages={robots_url: (200, _read_fixture("robots_disallow_events.txt"))}
        )
        fetcher = PlaywrightFetcher(page_factory=lambda: page)
        polite = PoliteFetcher(cache_dir=tmp_path, fetcher=fetcher)

        from partner_scrape.fetch.robots import RobotsDisallowed

        with pytest.raises(RobotsDisallowed):
            polite.get(url)

        navigated_urls = [call["url"] for call in page.calls]
        assert robots_url in navigated_urls
        assert url not in navigated_urls
