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
import threading
import time
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
class _FixtureRawResponse:
    """Stand-in for a real Playwright ``APIResponse`` (what
    ``page.request.get()`` returns) -- the raw-request counterpart to
    ``_FixtureNavigationResponse``. ``status``/``headers`` are plain
    attributes and ``text()`` is a method, matching the real
    ``playwright.sync_api.APIResponse`` surface this module reads.
    """

    status: int
    body: str
    headers: dict[str, str] = field(default_factory=dict)

    def text(self) -> str:
        return self.body


@dataclass
class FixtureRequestContext:
    """HeadlessRequestContext test double -- what
    ``FixtureHeadlessPage.request`` returns. Returns a canned
    ``_FixtureRawResponse`` per URL, no real browser process involved.

    ``responses`` maps a URL to ``(status, body)``. ``errors`` maps a
    URL to an exception ``get()`` should raise instead of returning
    normally. Every call is recorded in ``calls``.
    """

    responses: dict[str, tuple[int, str]] = field(default_factory=dict)
    errors: dict[str, Exception] = field(default_factory=dict)
    calls: list[dict[str, object]] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None):
        self.calls.append({"url": url, "headers": headers})
        if url in self.errors:
            raise self.errors[url]
        status, body = self.responses[url]
        return _FixtureRawResponse(status=status, body=body)


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

    ``request`` (a ``FixtureRequestContext``) stands in for the real
    ``page.request`` (``APIRequestContext``) property -- the raw,
    non-navigating retrieval path a non-HTML target
    (``_looks_like_raw_resource``) is routed through instead of
    ``goto``/``content`` (sprint 015, issue 37).
    """

    pages: dict[str, tuple[int, str]]
    errors: dict[str, Exception] = field(default_factory=dict)
    calls: list[dict[str, object]] = field(default_factory=list)
    extra_headers_calls: list[dict[str, str]] = field(default_factory=list)
    request: FixtureRequestContext = field(default_factory=FixtureRequestContext)
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

    def test_applies_bounded_load_wait_strategy(self):
        # Sprint 014 revision: wait_until="load", not the stricter
        # "networkidle" this method used before this ticket's own live
        # validation found "networkidle" times out for real Wix sites
        # that keep a persistent background connection open
        # indefinitely (see NETWORK_IDLE_TIMEOUT_MS's docstring and
        # fetch/DESIGN.md's sprint 014 section) -- the timeout bound
        # itself (NETWORK_IDLE_TIMEOUT_MS) is unchanged.
        url = "https://example.org/events"
        page = FixtureHeadlessPage(pages={url: (200, "<html></html>")})
        fetcher = PlaywrightFetcher(page_factory=lambda: page)

        fetcher.get(url)

        assert len(page.calls) == 1
        assert page.calls[0]["wait_until"] == "load"
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
            errors={url: TimeoutError("load wait timed out")},
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


class TestPlaywrightFetcherRawResourcePath:
    """Sprint 015 / issue 37: ``PlaywrightFetcher.get()`` routes a
    non-HTML target (``.xml`` and friends -- ``_looks_like_raw_resource``)
    through ``page.request.get()`` instead of ``page.goto()`` +
    ``page.content()``. Each test sets up ``page.goto()`` (via ``pages``/
    ``errors``) to reproduce one of the two live failure modes ticket
    003-014 recorded, then proves the real fix -- routing through
    ``page.request`` instead -- returns the real raw body and never
    calls ``goto()`` at all, so neither failure mode is even reachable.
    """

    def test_xml_target_avoids_the_html_wrapped_markup_failure_mode(self):
        # Failure mode 1 (5 confirmed sites): if get() navigated to a
        # raw .xml target, page.content() would return this
        # Chromium-viewer-wrapped markup instead of the real sitemap
        # body. Registering it under `pages` proves the fix doesn't
        # merely avoid crashing -- it avoids this wrong-content path
        # entirely, never touching goto()/content() for this URL.
        url = "https://example.org/sitemap.xml"
        real_xml = '<?xml version="1.0"?><urlset><url><loc>https://example.org/events/a/</loc></url></urlset>'
        wrapped_markup = "<html><head></head><body>Chromium XML viewer wrapper</body></html>"
        page = FixtureHeadlessPage(
            pages={url: (200, wrapped_markup)},
            request=FixtureRequestContext(responses={url: (200, real_xml)}),
        )
        fetcher = PlaywrightFetcher(page_factory=lambda: page)

        response = fetcher.get(url)

        assert response.body == real_xml
        assert response.status == 200
        assert page.calls == []  # goto() never called for this URL

    def test_xml_target_avoids_the_aborted_navigation_failure_mode(self):
        # Failure mode 2 (4 confirmed sites): if get() navigated to a
        # raw .xml target, goto() would raise net::ERR_ABORTED.
        # Registering that under `errors` proves the fix doesn't hit
        # this path at all -- get() must not raise, because it never
        # calls goto() for this URL in the first place.
        url = "https://example.org/sitemap.xml"
        real_xml = '<?xml version="1.0"?><urlset><url><loc>https://example.org/events/b/</loc></url></urlset>'
        page = FixtureHeadlessPage(
            pages={},
            errors={url: Exception("net::ERR_ABORTED at " + url)},
            request=FixtureRequestContext(responses={url: (200, real_xml)}),
        )
        fetcher = PlaywrightFetcher(page_factory=lambda: page)

        response = fetcher.get(url)

        assert response.body == real_xml
        assert response.status == 200
        assert page.calls == []  # goto() never called (never raised, either)

    def test_status_for_the_raw_path_is_not_hardcoded_200(self):
        url = "https://example.org/sitemap.xml"
        page = FixtureHeadlessPage(
            pages={},
            request=FixtureRequestContext(responses={url: (404, "")}),
        )
        fetcher = PlaywrightFetcher(page_factory=lambda: page)

        response = fetcher.get(url)

        assert response.status == 404

    def test_headers_are_forwarded_directly_to_the_raw_request(self):
        url = "https://example.org/sitemap.xml"
        page = FixtureHeadlessPage(
            pages={},
            request=FixtureRequestContext(responses={url: (200, "<urlset></urlset>")}),
        )
        fetcher = PlaywrightFetcher(page_factory=lambda: page)

        fetcher.get(url, headers={"If-None-Match": '"abc123"'})

        assert page.request.calls == [
            {"url": url, "headers": {"If-None-Match": '"abc123"'}}
        ]
        # set_extra_http_headers is the navigation-path mechanism --
        # the raw path forwards headers straight through get() instead.
        assert page.extra_headers_calls == []

    def test_response_headers_are_read_from_the_raw_response(self):
        url = "https://example.org/sitemap.xml"

        @dataclass
        class _RawResponseWithHeaders:
            status: int
            _body: str
            headers: dict[str, str]

            def text(self) -> str:
                return self._body

        class _Request:
            def get(self, url, headers=None):
                return _RawResponseWithHeaders(
                    status=200, _body="<urlset></urlset>", headers={"Content-Type": "text/xml"}
                )

        page = FixtureHeadlessPage(pages={}, request=_Request())
        fetcher = PlaywrightFetcher(page_factory=lambda: page)

        response = fetcher.get(url)

        assert response.headers == {"Content-Type": "text/xml"}

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.org/sitemap.xml",
            "https://example.org/feed.json",
            "https://example.org/data.csv",
            "https://example.org/feed.rss",
            "https://example.org/feed.atom",
            "https://example.org/sitemap.xml?cachebust=1",
        ],
    )
    def test_recognized_raw_extensions_all_route_through_the_raw_path(self, url):
        page = FixtureHeadlessPage(
            pages={}, request=FixtureRequestContext(responses={url: (200, "raw body")})
        )
        fetcher = PlaywrightFetcher(page_factory=lambda: page)

        response = fetcher.get(url)

        assert response.body == "raw body"
        assert page.calls == []

    def test_txt_target_still_navigates_not_raw_path(self):
        # Deliberate exclusion: .txt is not in _RAW_RESOURCE_EXTENSIONS
        # (see its docstring) because fetch/robots.py fetches
        # robots.txt through this same get() for every source, and
        # this ticket's evidenced bug is about .xml sitemaps, not
        # robots.txt -- changing that path is an unrelated behavior
        # change this ticket does not make.
        url = "https://example.org/robots.txt"
        body = "User-agent: *\nAllow: /"
        page = FixtureHeadlessPage(pages={url: (200, body)})
        fetcher = PlaywrightFetcher(page_factory=lambda: page)

        response = fetcher.get(url)

        assert response.body == body
        assert len(page.calls) == 1
        assert page.request.calls == []

    def test_html_target_still_navigates_and_never_uses_the_raw_path(self):
        # The existing navigate-and-render behavior for a normal HTML
        # page is unaffected: no request-path call is made for it.
        url = "https://example.org/events"
        html = "<html><body>Rendered via headless browser</body></html>"
        page = FixtureHeadlessPage(pages={url: (200, html)})
        fetcher = PlaywrightFetcher(page_factory=lambda: page)

        response = fetcher.get(url)

        assert response.body == html
        assert len(page.calls) == 1
        assert page.request.calls == []


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


class TestPlaywrightFetcherConcurrencySafety:
    """Sprint 014 ticket 002: ``PlaywrightFetcher.get()`` holds an
    instance-owned ``threading.Lock`` for its whole duration (page
    construction through ``content()``) as defense in depth against
    concurrent, multi-threaded access to the one shared browser page --
    see fetch/DESIGN.md's sprint 014 section. This proves the lock
    actually *prevents interleaving*, not merely that it exists: an
    instrumented fixture page double sleeps between ``goto()`` and
    ``content()`` so that, absent the lock, a second thread's call
    would almost certainly interleave into that window.
    """

    def test_two_threads_calling_get_on_one_instance_never_interleave(self):
        url_a = "https://example.org/a"
        url_b = "https://example.org/b"
        pages = {url_a: (200, "A-content"), url_b: (200, "B-content")}

        events: list[tuple[str, str]] = []
        events_lock = threading.Lock()

        class SlowFixtureHeadlessPage:
            """Instrumented double: records (url, phase) into the
            shared ``events`` list, with an artificial delay between
            ``goto()`` and ``content()`` -- the window in which an
            unlocked second thread's call would interleave.
            """

            def __init__(self) -> None:
                self._current_url: str | None = None

            def goto(self, url: str, timeout: float | None = None, wait_until: str | None = None):
                with events_lock:
                    events.append((url, "goto-start"))
                self._current_url = url
                time.sleep(0.05)
                with events_lock:
                    events.append((url, "goto-end"))
                status, _html = pages[url]
                return _FixtureNavigationResponse(status=status)

            def content(self) -> str:
                assert self._current_url is not None
                with events_lock:
                    events.append((self._current_url, "content"))
                _status, html = pages[self._current_url]
                return html

        page = SlowFixtureHeadlessPage()
        fetcher = PlaywrightFetcher(page_factory=lambda: page)
        results: dict[str, object] = {}

        def call(name: str, url: str) -> None:
            results[name] = fetcher.get(url)

        t1 = threading.Thread(target=call, args=("t1", url_a))
        t2 = threading.Thread(target=call, args=("t2", url_b))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Ownership assertion: every (goto-start, goto-end, content)
        # triplet for one URL is contiguous -- never interrupted by the
        # other URL's events. If the lock did not cover the whole
        # get() call (or did not cover page construction through
        # content()), the artificial delay above would let the other
        # thread's goto-start land inside this window.
        urls_in_order = [url for url, _phase in events]
        assert urls_in_order in (
            [url_a, url_a, url_a, url_b, url_b, url_b],
            [url_b, url_b, url_b, url_a, url_a, url_a],
        )

        # Correctness, not just non-crashing: each call returns the
        # content matching the URL IT requested -- never the other
        # thread's content (misattribution is the actual hazard a bare
        # "no exception raised" check would miss).
        assert results["t1"].url == url_a
        assert results["t1"].body == "A-content"
        assert results["t2"].url == url_b
        assert results["t2"].body == "B-content"

    def test_page_construction_itself_is_covered_by_the_lock(self):
        # Two threads racing on the very first get() call -- before
        # self._page exists -- must not both build a page: the lock
        # must cover _get_page() (construction), not just navigation.
        build_calls: list[int] = []
        build_lock = threading.Lock()
        url = "https://example.org/first"
        page = FixtureHeadlessPage(pages={url: (200, "content")})

        def factory():
            with build_lock:
                build_calls.append(1)
            time.sleep(0.02)
            return page

        fetcher = PlaywrightFetcher(page_factory=factory)

        threads = [threading.Thread(target=fetcher.get, args=(url,)) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(build_calls) == 1
