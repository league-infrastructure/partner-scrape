"""Sprint 005 ticket 005: `pipeline.run()`'s new Ad Content Export call site.

Proves `export_ads()` is really wired into `run()` -- not just declared
-- over a real end-to-end call: the existing fixture-only Source Registry
(`tests/fixtures/e2e_registry/`, reused unchanged from
`test_pipeline_e2e.py`) plus a small fixture Ad Registry
(`tests/fixtures/ad_registry/`, reused unchanged from
`test_export_ads.py`), asserting a single `run()` call writes both
`opportunities.json` and `ads.json` into the same `tmp_path` site dir,
and that `dry_run=True` writes neither.

No test here opens a socket, matching every other file in this suite's
own convention -- `FixtureFetcher` raises for any URL it wasn't given a
canned response for.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.pipeline import run

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
E2E_REGISTRY_DIR = FIXTURES_DIR / "e2e_registry"
AD_REGISTRY_DIR = FIXTURES_DIR / "ad_registry"
PARTNERS_FIXTURE = FIXTURES_DIR / "partners.json"

TODAY = date(2026, 7, 19)

TEC_API_BASE = "https://coastalrootsfarm.example/wp-json/tribe/events/v1/events/"
TEC_PROBE_URL = f"{TEC_API_BASE}?per_page=1&status=publish&start_date=now"
TEC_PAGE1_URL = f"{TEC_API_BASE}?per_page=50&page=1&status=publish&start_date=now"
ICAL_FEED_URL = "https://thelivingcoast.example/events/?ical=1"


class NoFixtureResponse(RuntimeError):
    """Raised by FixtureFetcher for a URL with no canned response."""


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket."""

    responses: dict[str, FetchResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        if url not in self.responses:
            raise NoFixtureResponse(f"no fixture response configured for {url!r}")
        return self.responses[url]


def _response(body: str, status: int = 200) -> FetchResponse:
    return FetchResponse(url="", status=status, headers={}, body=body)


def _fixture_fetcher() -> FixtureFetcher:
    tec_body = (E2E_REGISTRY_DIR / "tec_events.json").read_text()
    ical_body = (E2E_REGISTRY_DIR / "feed.ics").read_text()
    return FixtureFetcher(
        {
            TEC_PROBE_URL: _response(tec_body),
            TEC_PAGE1_URL: _response(tec_body),
            ICAL_FEED_URL: _response(ical_body),
            # brokensource.toml's URLs are deliberately absent.
        }
    )


def _site_dir(tmp_path: Path) -> Path:
    site_dir = tmp_path / "stem-ecosystem"
    data_dir = site_dir / "src" / "data"
    data_dir.mkdir(parents=True)
    shutil.copy(PARTNERS_FIXTURE, data_dir / "partners.json")
    return site_dir


class TestAdsExportWiredIntoPipelineRun:
    def test_a_single_run_produces_both_opportunities_json_and_ads_json(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        run(
            registry_dir=E2E_REGISTRY_DIR,
            site_dir=site_dir,
            ads_dir=AD_REGISTRY_DIR,
            fetcher=fetcher,
            today=TODAY,
        )

        opportunities_path = site_dir / "src" / "data" / "opportunities.json"
        ads_path = site_dir / "src" / "data" / "ads.json"
        assert opportunities_path.exists()
        assert ads_path.exists()

        written_ads = json.loads(ads_path.read_text())
        headlines = {entry["headline"] for entry in written_ads}
        assert {"Fixture Ad One", "Fixture Ad Two"} <= headlines
        for entry in written_ads:
            assert set(entry.keys()) == {"headline", "body", "link", "logo_src"}

    def test_runs_own_opportunities_return_value_is_unaffected_by_the_ads_call(self, tmp_path):
        # This ticket's Acceptance Criteria: "existing run() callers/
        # tests that don't care about ads are unaffected (additive
        # change)" -- run()'s return value is still exactly the
        # opportunities payload, not e.g. a tuple including ads.
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        payload = run(
            registry_dir=E2E_REGISTRY_DIR,
            site_dir=site_dir,
            ads_dir=AD_REGISTRY_DIR,
            fetcher=fetcher,
            today=TODAY,
        )

        assert isinstance(payload, list)
        assert len(payload) == 2
        assert all(isinstance(record, dict) for record in payload)
        assert all("headline" not in record for record in payload)

    def test_omitted_ads_dir_falls_back_to_the_real_seeded_league_registry(self, tmp_path):
        # No ads_dir override -- exercises the production default path
        # (partner_scrape/registry/ads/), proving the League's real seed
        # content reaches a real run() call end to end.
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        run(
            registry_dir=E2E_REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            today=TODAY,
        )

        written_ads = json.loads((site_dir / "src" / "data" / "ads.json").read_text())
        assert len(written_ads) >= 1
        assert written_ads[0]["link"].startswith("https://www.jointheleague.org")

    def test_dry_run_writes_neither_opportunities_json_nor_ads_json(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        payload = run(
            registry_dir=E2E_REGISTRY_DIR,
            site_dir=site_dir,
            ads_dir=AD_REGISTRY_DIR,
            fetcher=fetcher,
            today=TODAY,
            dry_run=True,
        )

        assert len(payload) == 2
        assert not (site_dir / "src" / "data" / "opportunities.json").exists()
        assert not (site_dir / "src" / "data" / "ads.json").exists()
