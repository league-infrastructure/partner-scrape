"""Tests for partner_scrape.fetch: the Fetcher protocol, robots.txt
check, per-domain rate limiting, conditional GET, and the on-disk
cache.

Every test exercises the module through an injected fixture Fetcher
(``FixtureFetcher`` below) -- no test in this file opens a real
network socket, per sprint.md's test strategy for Fetch & Cache.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pytest

from partner_scrape.fetch.cache import (
    PoliteFetcher,
    cache_path,
    conditional_headers,
    read_cache_entry,
)
from partner_scrape.fetch.fetcher import FetchResponse, UrllibFetcher
from partner_scrape.fetch.robots import RobotsDisallowed, is_allowed
from partner_scrape.fetch.throttle import Throttle

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "fetch"

BOT_USER_AGENT = "STEM-Calendar-Bot/1.0 (educational research)"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


@pytest.fixture(autouse=True)
def _no_real_cache_dir(monkeypatch):
    """Guard rail: never let a test silently fall through to the real
    SCRAPE_CACHE_DIR. Tests exercising PoliteFetcher's config-default
    path explicitly monkeypatch this to a tmp_path; every other test
    passes ``cache_dir`` directly and never touches this at all.
    """
    monkeypatch.delenv("SCRAPE_CACHE_DIR", raising=False)


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.

    Each value in ``responses`` is either one ``FetchResponse``
    (returned for every call to that URL) or a list of them (popped in
    call order; the last element repeats once the list is down to one).
    A URL absent from ``responses`` raises ``KeyError`` -- a loud
    failure if code under test fetches something it shouldn't (e.g. a
    robots.txt-disallowed target URL).
    """

    responses: dict[str, FetchResponse | list[FetchResponse]]
    calls: list[tuple[str, dict[str, str] | None]] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append((url, headers))
        canned = self.responses[url]
        if isinstance(canned, list):
            return canned.pop(0) if len(canned) > 1 else canned[0]
        return canned


class FakeClock:
    """A fake monotonic clock: starts at ``start``, only moves via advance()."""

    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _response(
    url: str,
    status: int = 200,
    headers: dict[str, str] | None = None,
    body: str = "",
) -> FetchResponse:
    return FetchResponse(
        url=url,
        status=status,
        headers=headers or {},
        body=body,
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class TestRobotsCheck:
    def test_disallowed_url_is_never_fetched(self, tmp_path):
        url = "https://example.org/events/secret"
        robots_url = "https://example.org/robots.txt"
        fetcher = FixtureFetcher(
            {robots_url: _response(robots_url, body=_read_fixture("robots_disallow_events.txt"))}
        )
        polite = PoliteFetcher(cache_dir=tmp_path, fetcher=fetcher)

        with pytest.raises(RobotsDisallowed):
            polite.get(url)

        fetched_urls = [call_url for call_url, _ in fetcher.calls]
        assert robots_url in fetched_urls
        assert url not in fetched_urls

    def test_allowed_url_is_fetched(self, tmp_path):
        url = "https://example.org/api/events"
        robots_url = "https://example.org/robots.txt"
        fetcher = FixtureFetcher(
            {
                robots_url: _response(robots_url, body=_read_fixture("robots_allow_all.txt")),
                url: _response(url, body=_read_fixture("sample_body_v1.json")),
            }
        )
        polite = PoliteFetcher(cache_dir=tmp_path, fetcher=fetcher)

        response = polite.get(url)

        assert response.status == 200
        assert url in [call_url for call_url, _ in fetcher.calls]

    def test_respect_robots_false_skips_the_check_entirely(self, tmp_path):
        url = "https://example.org/api/events"
        # Deliberately no robots.txt entry configured -- if the code
        # tried to check it anyway, FixtureFetcher would raise KeyError.
        fetcher = FixtureFetcher({url: _response(url, body="ok")})
        polite = PoliteFetcher(cache_dir=tmp_path, fetcher=fetcher)

        response = polite.get(url, respect_robots=False)

        assert response.status == 200

    def test_missing_robots_txt_is_treated_as_allow_all(self, tmp_path):
        url = "https://example.org/api/events"
        robots_url = "https://example.org/robots.txt"
        fetcher = FixtureFetcher(
            {
                robots_url: _response(robots_url, status=404, body=""),
                url: _response(url, body="ok"),
            }
        )
        polite = PoliteFetcher(cache_dir=tmp_path, fetcher=fetcher)

        response = polite.get(url)

        assert response.status == 200

    def test_is_allowed_directly_reports_disallow(self):
        url = "https://example.org/events/secret"
        robots_url = "https://example.org/robots.txt"
        fetcher = FixtureFetcher(
            {robots_url: _response(robots_url, body=_read_fixture("robots_disallow_events.txt"))}
        )

        assert is_allowed(url, fetcher, BOT_USER_AGENT) is False

    def test_is_allowed_directly_reports_allow(self):
        url = "https://example.org/api/events"
        robots_url = "https://example.org/robots.txt"
        fetcher = FixtureFetcher(
            {robots_url: _response(robots_url, body=_read_fixture("robots_allow_all.txt"))}
        )

        assert is_allowed(url, fetcher, BOT_USER_AGENT) is True


class TestCacheWrite:
    def test_first_fetch_stores_body_headers_and_timestamp(self, tmp_path):
        url = "https://example.org/api/events"
        robots_url = "https://example.org/robots.txt"
        body = _read_fixture("sample_body_v1.json")
        etag = '"abc123"'
        last_modified = "Wed, 01 Jan 2026 00:00:00 GMT"
        fetcher = FixtureFetcher(
            {
                robots_url: _response(robots_url, body=_read_fixture("robots_allow_all.txt")),
                url: _response(
                    url,
                    status=200,
                    headers={"ETag": etag, "Last-Modified": last_modified},
                    body=body,
                ),
            }
        )
        fixed_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        polite = PoliteFetcher(cache_dir=tmp_path, fetcher=fetcher, clock=lambda: fixed_time)

        response = polite.get(url)

        assert response.status == 200
        assert response.body == body
        assert response.fetched_at == fixed_time

        entry = read_cache_entry(tmp_path, url)
        assert entry is not None
        assert entry["url"] == url
        assert entry["status"] == 200
        assert entry["body"] == body
        assert entry["headers"]["ETag"] == etag
        assert entry["headers"]["Last-Modified"] == last_modified
        assert entry["fetched_at"] == fixed_time.isoformat()

        path = cache_path(tmp_path, url)
        assert path.exists()
        assert path.parent.name == "example.org"

    def test_cache_dir_defaults_to_configured_scrape_cache_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))
        polite = PoliteFetcher(fetcher=FixtureFetcher({}))

        assert polite.cache_dir == tmp_path

    def test_raises_when_scrape_cache_dir_unset_and_no_override_given(self):
        with pytest.raises(RuntimeError):
            PoliteFetcher(fetcher=FixtureFetcher({}))


class TestConditionalGet:
    def test_second_fetch_sends_conditional_headers_derived_from_cache(self, tmp_path):
        url = "https://example.org/api/events"
        robots_url = "https://example.org/robots.txt"
        etag = '"abc123"'
        last_modified = "Wed, 01 Jan 2026 00:00:00 GMT"
        first = _response(
            url, status=200, headers={"ETag": etag, "Last-Modified": last_modified}, body="body-v1"
        )
        second = _response(url, status=304, headers={}, body="")
        fetcher = FixtureFetcher(
            {
                robots_url: _response(robots_url, body=_read_fixture("robots_allow_all.txt")),
                url: [first, second],
            }
        )
        polite = PoliteFetcher(cache_dir=tmp_path, fetcher=fetcher)

        polite.get(url)  # primes the cache -- no conditional headers yet
        polite.get(url)  # repeat fetch -- should send conditional headers

        url_calls = [headers for call_url, headers in fetcher.calls if call_url == url]
        assert len(url_calls) == 2
        assert url_calls[0] == {}
        assert url_calls[1] == {
            "If-None-Match": etag,
            "If-Modified-Since": last_modified,
        }

    def test_conditional_headers_empty_with_no_cached_entry(self):
        assert conditional_headers(None) == {}

    def test_conditional_headers_builds_both_headers_when_present(self):
        entry = {
            "headers": {
                "ETag": '"x"',
                "Last-Modified": "Mon, 01 Jan 2026 00:00:00 GMT",
            }
        }
        assert conditional_headers(entry) == {
            "If-None-Match": '"x"',
            "If-Modified-Since": "Mon, 01 Jan 2026 00:00:00 GMT",
        }

    def test_conditional_headers_partial_when_only_etag_present(self):
        entry = {"headers": {"ETag": '"x"'}}
        assert conditional_headers(entry) == {"If-None-Match": '"x"'}

    def test_conditional_headers_header_lookup_is_case_insensitive(self):
        entry = {
            "headers": {
                "etag": '"x"',
                "last-modified": "Mon, 01 Jan 2026 00:00:00 GMT",
            }
        }
        assert conditional_headers(entry) == {
            "If-None-Match": '"x"',
            "If-Modified-Since": "Mon, 01 Jan 2026 00:00:00 GMT",
        }


class TestReuseOn304:
    def test_304_reuses_cached_body_and_does_not_rewrite_it(self, tmp_path):
        url = "https://example.org/api/events"
        robots_url = "https://example.org/robots.txt"
        etag = '"abc123"'
        first = _response(url, status=200, headers={"ETag": etag}, body="body-v1")
        second = _response(url, status=304, headers={}, body="")
        fetcher = FixtureFetcher(
            {
                robots_url: _response(robots_url, body=_read_fixture("robots_allow_all.txt")),
                url: [first, second],
            }
        )
        first_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        second_time = datetime(2026, 1, 15, tzinfo=timezone.utc)
        clock_values = iter([first_time, second_time])
        polite = PoliteFetcher(cache_dir=tmp_path, fetcher=fetcher, clock=lambda: next(clock_values))

        response1 = polite.get(url)
        entry_after_first = read_cache_entry(tmp_path, url)

        response2 = polite.get(url)
        entry_after_second = read_cache_entry(tmp_path, url)

        assert response1.fetched_at == first_time
        assert response2.status == 200  # the original successful status, reused
        assert response2.body == "body-v1"
        assert response2.fetched_at == second_time

        assert entry_after_second["body"] == entry_after_first["body"] == "body-v1"
        assert entry_after_second["headers"] == entry_after_first["headers"]
        assert entry_after_second["status"] == entry_after_first["status"] == 200
        assert entry_after_second["fetched_at"] == second_time.isoformat()
        assert entry_after_first["fetched_at"] == first_time.isoformat()


class TestRateLimiting:
    def test_enforces_minimum_delay_between_fetches_to_same_domain(self, tmp_path):
        clock = FakeClock(start=0.0)
        sleeps: list[float] = []

        def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)
            clock.advance(seconds)

        throttle = Throttle(clock=clock, sleep=fake_sleep)
        url1 = "https://example.org/api/events/a"
        url2 = "https://example.org/api/events/b"
        fetcher = FixtureFetcher(
            {url1: _response(url1, body="a"), url2: _response(url2, body="b")}
        )
        polite = PoliteFetcher(cache_dir=tmp_path, fetcher=fetcher, throttle=throttle)

        polite.get(url1, rate_limit_seconds=2.0, respect_robots=False)
        polite.get(url2, rate_limit_seconds=2.0, respect_robots=False)

        assert sleeps == [2.0]

    def test_no_delay_once_enough_time_has_elapsed(self, tmp_path):
        clock = FakeClock(start=0.0)
        sleeps: list[float] = []
        throttle = Throttle(clock=clock, sleep=lambda seconds: sleeps.append(seconds))
        url1 = "https://example.org/api/events/a"
        url2 = "https://example.org/api/events/b"
        fetcher = FixtureFetcher(
            {url1: _response(url1, body="a"), url2: _response(url2, body="b")}
        )
        polite = PoliteFetcher(cache_dir=tmp_path, fetcher=fetcher, throttle=throttle)

        polite.get(url1, rate_limit_seconds=2.0, respect_robots=False)
        clock.advance(5.0)
        polite.get(url2, rate_limit_seconds=2.0, respect_robots=False)

        assert sleeps == []

    def test_throttle_wait_directly_sleeps_the_remaining_time(self):
        clock = FakeClock(start=0.0)
        sleeps: list[float] = []
        throttle = Throttle(clock=clock, sleep=lambda seconds: sleeps.append(seconds))

        throttle.wait("example.org", rate_limit_seconds=3.0)
        assert sleeps == []  # first call for this domain -- nothing to wait on

        throttle.wait("example.org", rate_limit_seconds=3.0)
        assert sleeps == [3.0]

    def test_throttle_domains_are_independent(self):
        clock = FakeClock(start=0.0)
        sleeps: list[float] = []
        throttle = Throttle(clock=clock, sleep=lambda seconds: sleeps.append(seconds))

        throttle.wait("a.org", rate_limit_seconds=5.0)
        throttle.wait("b.org", rate_limit_seconds=5.0)

        assert sleeps == []


class TestPoliteFetcherWiring:
    def test_default_fetcher_is_urllib_based(self, tmp_path):
        polite = PoliteFetcher(cache_dir=tmp_path)
        assert isinstance(polite.fetcher, UrllibFetcher)

    def test_default_throttle_is_a_real_throttle(self, tmp_path):
        polite = PoliteFetcher(cache_dir=tmp_path)
        assert isinstance(polite.throttle, Throttle)
