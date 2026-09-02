"""`UrllibFetcher`'s transport-layer behavior.

Every test here drives `UrllibFetcher.get` with `urllib.request.urlopen`
monkeypatched, so no socket is ever opened -- matching the no-network
rule the rest of `tests/` follows.
"""

from __future__ import annotations

import http.client
import json
import socket
import ssl
import urllib.error

import pytest

from partner_scrape.fetch.fetcher import (
    TRANSPORT_ERROR_STATUS,
    UrllibFetcher,
    sanitize_url,
)


class _FakeResponse:
    """Minimal stand-in for the object `urlopen` yields."""

    status = 200
    headers = {"Content-Type": "text/html"}

    def read(self):
        return b"<html></html>"

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


@pytest.mark.parametrize(
    "raised",
    [
        urllib.error.URLError(ssl.SSLCertVerificationError("unable to get local issuer")),
        urllib.error.URLError(socket.gaierror(8, "nodename nor servname provided")),
        urllib.error.URLError(ConnectionResetError(54, "Connection reset by peer")),
        TimeoutError("The read operation timed out"),
        http.client.InvalidURL("URL can't contain control characters"),
        UnicodeError("IDNA encoding failed"),
    ],
    ids=["tls", "dns", "reset", "timeout", "invalid-url", "idna"],
)
def test_transport_failures_become_a_status_not_an_exception(monkeypatch, raised):
    """A failure with no HTTP response must not propagate.

    The pipeline's only handler is per-*source*, so a raised exception
    here discards every event that source already produced. Each of
    these six real-world failures must instead surface as a non-2xx
    `FetchResponse` the caller can skip.
    """

    def boom(*args, **kwargs):
        raise raised

    monkeypatch.setattr("urllib.request.urlopen", boom)

    response = UrllibFetcher().get("https://example.org/events")

    assert response.status == TRANSPORT_ERROR_STATUS
    assert response.body == ""
    assert response.url == "https://example.org/events"


def test_http_error_still_reports_its_own_status(monkeypatch):
    """A real HTTP status (403, 404, 304) must survive unchanged."""

    def forbidden(*args, **kwargs):
        raise urllib.error.HTTPError(
            url="https://example.org/", code=403, msg="Forbidden", hdrs=None, fp=None
        )

    monkeypatch.setattr("urllib.request.urlopen", forbidden)

    assert UrllibFetcher().get("https://example.org/").status == 403


def test_success_path_is_unchanged(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _FakeResponse())

    response = UrllibFetcher().get("https://example.org/")

    assert response.status == 200
    assert response.body == "<html></html>"


def test_request_is_verified_against_certifi(monkeypatch):
    """`get` must pass an explicit, verifying TLS context.

    The platform default trust store rejects chains that certifi
    accepts, so an omitted context is the awissd.org/calendar.ucsd.edu
    failure. Verification must stay on.
    """
    seen = {}

    def capture(request, timeout=None, context=None):
        seen["context"] = context
        return _FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", capture)
    UrllibFetcher().get("https://example.org/")

    assert isinstance(seen["context"], ssl.SSLContext)
    assert seen["context"].verify_mode == ssl.CERT_REQUIRED
    assert seen["context"].check_hostname is True


def test_urls_with_spaces_are_encoded_before_the_request(monkeypatch):
    """A raw space in a linked PDF path must not abort the source."""
    seen = {}

    def capture(request, timeout=None, context=None):
        seen["url"] = request.full_url
        return _FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", capture)
    messy = "https://example.org/docs/Column_ Deborah publishes a book.pdf"

    response = UrllibFetcher().get(messy)

    assert " " not in seen["url"]
    assert seen["url"] == "https://example.org/docs/Column_%20Deborah%20publishes%20a%20book.pdf"
    # The caller's cache key is the URL it asked for, not the encoded form.
    assert response.url == messy


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://example.org/a b", "https://example.org/a%20b"),
        # Already-encoded input must not be double-encoded.
        ("https://example.org/a%20b", "https://example.org/a%20b"),
        # Query strings and their separators survive.
        ("https://example.org/e?a=1&b=2", "https://example.org/e?a=1&b=2"),
        ("https://example.org/e?q=a b", "https://example.org/e?q=a%20b"),
        # Fragments and ordinary URLs are untouched.
        ("https://example.org/plain", "https://example.org/plain"),
    ],
)
def test_sanitize_url(url, expected):
    assert sanitize_url(url) == expected


class TestPost:
    """``UrllibFetcher.post()`` (sprint 031) -- added for Workday's
    ``POST /wday/cxs/{tenant}/{site}/jobs`` search endpoint. Reuses
    ``get()``'s exact transport-error handling (``_execute``), so these
    tests focus on what's new: method, body encoding, and headers.
    """

    def test_sends_method_post_json_body_and_content_type(self, monkeypatch):
        seen = {}

        def capture(request, timeout=None, context=None):
            seen["method"] = request.get_method()
            seen["data"] = request.data
            seen["headers"] = dict(request.header_items())
            return _FakeResponse()

        monkeypatch.setattr("urllib.request.urlopen", capture)

        UrllibFetcher().post("https://example.org/wday/cxs/acme/careers/jobs", body={"offset": 0})

        assert seen["method"] == "POST"
        assert json.loads(seen["data"]) == {"offset": 0}
        assert seen["headers"]["Content-type"] == "application/json"
        assert "STEM-Calendar-Bot" in seen["headers"]["User-agent"]

    def test_caller_headers_are_merged_on_top_of_defaults(self, monkeypatch):
        seen = {}

        def capture(request, timeout=None, context=None):
            seen["headers"] = dict(request.header_items())
            return _FakeResponse()

        monkeypatch.setattr("urllib.request.urlopen", capture)

        UrllibFetcher().post(
            "https://example.org/wday/cxs/acme/careers/jobs",
            body={"offset": 0},
            headers={"Referer": "https://acme.com/careers", "Accept": "application/json"},
        )

        assert seen["headers"]["Referer"] == "https://acme.com/careers"
        assert seen["headers"]["Accept"] == "application/json"

    def test_success_path_returns_status_and_body(self, monkeypatch):
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _FakeResponse())

        response = UrllibFetcher().post("https://example.org/jobs", body={"offset": 0})

        assert response.status == 200
        assert response.body == "<html></html>"

    @pytest.mark.parametrize(
        "raised",
        [
            urllib.error.URLError(ssl.SSLCertVerificationError("unable to get local issuer")),
            urllib.error.URLError(socket.gaierror(8, "nodename nor servname provided")),
            urllib.error.URLError(ConnectionResetError(54, "Connection reset by peer")),
            TimeoutError("The read operation timed out"),
            http.client.InvalidURL("URL can't contain control characters"),
            UnicodeError("IDNA encoding failed"),
        ],
        ids=["tls", "dns", "reset", "timeout", "invalid-url", "idna"],
    )
    def test_transport_failures_become_a_status_not_an_exception(self, monkeypatch, raised):
        """Same connection-level failures as ``get()``'s equivalent test --
        ``post()`` must degrade identically, per this ticket's
        acceptance criteria ("reusing get()'s exact transport-error
        handling").
        """

        def boom(*args, **kwargs):
            raise raised

        monkeypatch.setattr("urllib.request.urlopen", boom)

        response = UrllibFetcher().post("https://example.org/jobs", body={"offset": 0})

        assert response.status == TRANSPORT_ERROR_STATUS
        assert response.body == ""
        assert response.url == "https://example.org/jobs"

    def test_http_error_still_reports_its_own_status(self, monkeypatch):
        def forbidden(*args, **kwargs):
            raise urllib.error.HTTPError(
                url="https://example.org/jobs", code=403, msg="Forbidden", hdrs=None, fp=None
            )

        monkeypatch.setattr("urllib.request.urlopen", forbidden)

        response = UrllibFetcher().post("https://example.org/jobs", body={"offset": 0})

        assert response.status == 403

    def test_url_is_sanitized_before_the_request(self, monkeypatch):
        seen = {}

        def capture(request, timeout=None, context=None):
            seen["url"] = request.full_url
            return _FakeResponse()

        monkeypatch.setattr("urllib.request.urlopen", capture)
        messy = "https://example.org/wday/cxs/acme/careers/jobs?q=a b"

        response = UrllibFetcher().post(messy, body={"offset": 0})

        assert " " not in seen["url"]
        assert response.url == messy
