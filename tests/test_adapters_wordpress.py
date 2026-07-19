"""Tests for partner_scrape.adapters.wordpress: the WordPress REST adapter.

Every test drives the adapter through a fixture Fetcher returning
recorded/synthesized WP REST JSON (tests/fixtures/wordpress/) -- no test
here opens a real network socket, per sprint.md's test strategy for the
Adapter Framework.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from partner_scrape.adapters import run
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.wordpress import PAGE_SIZE, WordPressRestAdapter
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Provenance
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "wordpress"

API_BASE = "https://example.org"
POSTS_URL = f"{API_BASE}/wp-json/wp/v2/posts?per_page={PAGE_SIZE}"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _response(body: str, status: int = 200) -> FetchResponse:
    return FetchResponse(url="", status=status, headers={}, body=body)


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.

    A URL absent from ``responses`` raises ``KeyError`` -- a loud
    failure if the adapter under test fetches something it shouldn't.
    """

    responses: dict[str, FetchResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        return self.responses[url]


def _source(api_base: str = API_BASE, **config_overrides) -> SourceConfig:
    return SourceConfig(
        source_id="fixture_org",
        org_name="Fixture Org",
        adapter_type="wp_rest",
        config={"api_base": api_base, **config_overrides},
    )


def _posts_fetcher(body: str | None = None) -> FixtureFetcher:
    if body is None:
        body = _read_fixture("posts.json")
    return FixtureFetcher({POSTS_URL: _response(body)})


class TestFieldMapping:
    def test_valid_post_maps_title_description_url(self):
        events = run(_source(), _posts_fetcher())

        camp = next(e for e in events if "Summer Camp" in e.title)
        assert camp.title == "Summer Camp Registration Is Open!"
        assert camp.url == "https://example.org/summer-camp-registration-open/"
        assert "Sign your kids up" in camp.description
        assert "spots are limited" in camp.description
        assert "<p>" not in camp.description
        assert "&#8211;" not in camp.description
        assert camp.kind == "event"
        assert camp.source_id == "fixture_org"
        assert camp.external_id == "101"

    def test_every_field_the_adapter_sets_has_wp_rest_provenance(self):
        events = run(_source(), _posts_fetcher())

        camp = next(e for e in events if "Summer Camp" in e.title)
        assert camp.field_provenance
        for prov in camp.field_provenance.values():
            assert prov == Provenance(source="wp_rest", confidence=1.0)

    def test_start_and_location_are_left_unset_not_guessed(self):
        events = run(_source(), _posts_fetcher())

        camp = next(e for e in events if "Summer Camp" in e.title)
        assert camp.start is None
        assert camp.location == ""
        assert "start" not in camp.field_provenance
        assert "location" not in camp.field_provenance

    def test_description_falls_back_to_content_when_excerpt_is_empty(self):
        events = run(_source(), _posts_fetcher())

        spotlight = next(e for e in events if "Volunteer Spotlight" in e.title)
        assert "highlighting one of our longtime volunteers" in spotlight.description


class TestMalformedRecordIsolation:
    def test_record_with_no_title_is_skipped_rest_of_page_survives(self):
        events = run(_source(), _posts_fetcher())

        titles = {e.title for e in events}
        assert titles == {"Summer Camp Registration Is Open!", "Volunteer Spotlight: Meet Dr. Rivera"}
        assert len(events) == 2


class TestEmptyAndMalformedResponse:
    def test_empty_json_array_yields_zero_events_and_no_exception(self):
        events = run(_source(), _posts_fetcher(body="[]"))

        assert events == []

    def test_empty_body_yields_zero_events_and_a_logged_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            events = run(_source(), _posts_fetcher(body=""))

        assert events == []
        assert "unparseable" in caplog.text

    def test_non_array_body_yields_zero_events_and_a_logged_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            events = run(_source(), _posts_fetcher(body='{"not": "a list"}'))

        assert events == []
        assert "not a JSON array" in caplog.text


class TestExtractRobustness:
    def test_non_200_status_returns_no_events_without_raising(self):
        adapter = WordPressRestAdapter()
        raw = RawResponse(ref=EventRef(url=POSTS_URL), status=500, body="")

        assert list(adapter.extract(raw, _source())) == []


class TestPostTypes:
    def test_default_post_types_queries_posts_only(self):
        fetcher = _posts_fetcher()

        run(_source(), fetcher)

        assert fetcher.calls == [POSTS_URL]

    def test_configured_post_types_queries_each_collection(self):
        pages_url = f"{API_BASE}/wp-json/wp/v2/pages?per_page={PAGE_SIZE}"
        fetcher = FixtureFetcher(
            {
                POSTS_URL: _response(_read_fixture("posts.json")),
                pages_url: _response("[]"),
            }
        )

        run(_source(post_types=["posts", "pages"]), fetcher)

        assert set(fetcher.calls) == {POSTS_URL, pages_url}


class TestWpRestIsRegistered:
    def test_importing_the_adapters_package_registers_wp_rest(self):
        import partner_scrape.adapters as adapters_pkg

        assert adapters_pkg.ADAPTERS["wp_rest"] is adapters_pkg.WordPressRestAdapter
