"""Tests for partner_scrape.discovery.sitemap: sitemap-diff discovery.

Every test drives ``discover_changed_urls`` through a fixture Fetcher
returning recorded sitemap XML (tests/fixtures/sitemaps/) and a
tmp_path-based ``SCRAPE_CACHE_DIR`` (monkeypatched) -- no test here
opens a real network socket or touches the real cache directory, per
sprint.md's test strategy for Sitemap Discovery.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from partner_scrape.discovery.sitemap import discover_changed_urls
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "sitemaps"

SITE_URL = "https://example.org"
ROOT_SITEMAP_URL = f"{SITE_URL}/sitemap_index.xml"

#: The three event URLs tests/fixtures/sitemaps/events_sitemap.xml
#: contains, in file order.
EVENT_URLS = [
    "https://example.org/events/tide-pool-exploration/",
    "https://example.org/events/beach-cleanup/",
    "https://example.org/events/star-party/",
]

#: events_sitemap.xml's actual (current, "live") lastmod per URL.
CURRENT_LASTMODS = {
    EVENT_URLS[0]: "2026-06-01",
    EVENT_URLS[1]: "2026-06-05",
    EVENT_URLS[2]: "2026-06-10",
}


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _response(body: str, status: int = 200) -> FetchResponse:
    return FetchResponse(url="", status=status, headers={}, body=body)


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.

    A URL absent from ``responses`` raises ``KeyError`` -- a loud
    failure if discovery fetches something it shouldn't (e.g. a
    sitemap-index child that isn't event-related).
    """

    responses: dict[str, FetchResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        return self.responses[url]


def _source() -> SourceConfig:
    return SourceConfig(
        source_id="fixture_org",
        org_name="Fixture Org",
        adapter_type="generic_html",
        config={"site_url": SITE_URL},
    )


@pytest.fixture(autouse=True)
def _cache_dir(tmp_path, monkeypatch):
    """Point SCRAPE_CACHE_DIR at a tmp_path for every test in this file
    -- no test here ever touches the real configured cache directory.
    """
    monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))
    return tmp_path


def _write_snapshot(tmp_path: Path, lastmods: dict[str, str]) -> None:
    snapshot_path = tmp_path / "sitemap_snapshots" / "fixture_org.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(lastmods))


class TestUnchangedSnapshot:
    def test_all_unchanged_lastmod_yields_zero_refs(self, tmp_path):
        _write_snapshot(tmp_path, CURRENT_LASTMODS)
        fetcher = FixtureFetcher(
            {ROOT_SITEMAP_URL: _response(_read_fixture("events_sitemap.xml"))}
        )

        refs = discover_changed_urls(_source(), fetcher)

        assert refs == []


class TestChangedLastmod:
    def test_one_bumped_lastmod_yields_exactly_that_ref(self, tmp_path):
        stale = dict(CURRENT_LASTMODS)
        stale[EVENT_URLS[2]] = "2025-01-01"  # stale -- live sitemap has 2026-06-10
        _write_snapshot(tmp_path, stale)
        fetcher = FixtureFetcher(
            {ROOT_SITEMAP_URL: _response(_read_fixture("events_sitemap.xml"))}
        )

        refs = discover_changed_urls(_source(), fetcher)

        assert [r.url for r in refs] == [EVENT_URLS[2]]
        assert refs[0].context["lastmod"] == "2026-06-10"


class TestFirstRun:
    def test_no_snapshot_file_yields_every_matching_url(self):
        fetcher = FixtureFetcher(
            {ROOT_SITEMAP_URL: _response(_read_fixture("events_sitemap.xml"))}
        )

        refs = discover_changed_urls(_source(), fetcher)

        assert [r.url for r in refs] == EVENT_URLS


class TestSitemapIndexRecursion:
    def test_only_event_named_child_sitemap_is_fetched(self):
        fetcher = FixtureFetcher(
            {
                ROOT_SITEMAP_URL: _response(_read_fixture("sitemap_index.xml")),
                "https://example.org/events-sitemap.xml": _response(
                    _read_fixture("events_sitemap.xml")
                ),
                # Deliberately no entry for page-sitemap.xml -- KeyError
                # if discovery ever tries to fetch it.
            }
        )

        refs = discover_changed_urls(_source(), fetcher)

        assert sorted(r.url for r in refs) == sorted(EVENT_URLS)
        assert "https://example.org/page-sitemap.xml" not in fetcher.calls


class TestMalformedSitemap:
    def test_malformed_sitemap_yields_zero_refs_and_logs_warning(self, caplog):
        fetcher = FixtureFetcher(
            {ROOT_SITEMAP_URL: _response(_read_fixture("malformed.xml"))}
        )

        with caplog.at_level(logging.WARNING):
            refs = discover_changed_urls(_source(), fetcher)

        assert refs == []
        assert "not valid XML" in caplog.text

    def test_malformed_sitemap_does_not_raise(self):
        fetcher = FixtureFetcher(
            {ROOT_SITEMAP_URL: _response(_read_fixture("malformed.xml"))}
        )

        discover_changed_urls(_source(), fetcher)  # must not raise

    def test_malformed_sitemap_leaves_existing_snapshot_untouched(self, tmp_path):
        _write_snapshot(tmp_path, CURRENT_LASTMODS)
        snapshot_path = tmp_path / "sitemap_snapshots" / "fixture_org.json"
        before = snapshot_path.read_text()
        fetcher = FixtureFetcher(
            {ROOT_SITEMAP_URL: _response(_read_fixture("malformed.xml"))}
        )

        discover_changed_urls(_source(), fetcher)

        assert snapshot_path.read_text() == before


class TestUnreachableSitemap:
    def test_non_200_status_on_both_candidates_yields_zero_refs_and_warns(self, caplog):
        fetcher = FixtureFetcher(
            {
                ROOT_SITEMAP_URL: _response("", status=404),
                f"{SITE_URL}/sitemap.xml": _response("", status=404),
            }
        )

        with caplog.at_level(logging.WARNING):
            refs = discover_changed_urls(_source(), fetcher)

        assert refs == []
        assert "no reachable sitemap" in caplog.text.lower()

    def test_falls_back_to_sitemap_xml_when_index_is_unreachable(self):
        fetcher = FixtureFetcher(
            {
                ROOT_SITEMAP_URL: _response("", status=404),
                f"{SITE_URL}/sitemap.xml": _response(_read_fixture("events_sitemap.xml")),
            }
        )

        refs = discover_changed_urls(_source(), fetcher)

        assert [r.url for r in refs] == EVENT_URLS


class TestRoundTrip:
    def test_second_call_against_unchanged_fixture_yields_zero_refs(self):
        fetcher = FixtureFetcher(
            {ROOT_SITEMAP_URL: _response(_read_fixture("events_sitemap.xml"))}
        )

        first_refs = discover_changed_urls(_source(), fetcher)
        second_refs = discover_changed_urls(_source(), fetcher)

        assert [r.url for r in first_refs] == EVENT_URLS
        assert second_refs == []

    def test_snapshot_written_after_first_run_matches_live_sitemap(self, tmp_path):
        fetcher = FixtureFetcher(
            {ROOT_SITEMAP_URL: _response(_read_fixture("events_sitemap.xml"))}
        )

        discover_changed_urls(_source(), fetcher)

        snapshot_path = tmp_path / "sitemap_snapshots" / "fixture_org.json"
        assert json.loads(snapshot_path.read_text()) == CURRENT_LASTMODS
