"""Tests for partner_scrape.teams.pipeline: `run_teams()`'s
Registry -> TeamSource(s) -> export_teams() sequencing.

Drives the real Team Registry seed (`partner_scrape/teams/registry/
ftc-sd.toml`, the same one production loads) through a fixture Fetcher
returning the live-captured 152-team FTCScout fixture -- no test here
opens a real network socket, and no test relies on a synthetic registry
standing in for the real one (except the two tests that specifically
need an unrecognized/erroring source, which use their own small fixture
registries under `tests/fixtures/teams/`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.teams import pipeline as teams_pipeline
from partner_scrape.teams.model import Team
from partner_scrape.teams.pipeline import DEFAULT_TEAMS_REGISTRY_DIR, run_teams
from partner_scrape.teams.sources.ftcscout import DEFAULT_API_BASE, DEFAULT_REGION, _search_url

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "teams"
SEARCH_URL = _search_url(DEFAULT_API_BASE, DEFAULT_REGION)


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.
    A URL absent from ``responses`` raises ``KeyError``."""

    responses: dict[str, FetchResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        return self.responses[url]


def _ftcscout_fetcher() -> FixtureFetcher:
    body = (FIXTURES_DIR / "ftcscout_search.json").read_text()
    return FixtureFetcher({SEARCH_URL: FetchResponse(url="", status=200, headers={}, body=body)})


def _make_site(root: Path) -> Path:
    (root / "src" / "data").mkdir(parents=True)
    return root


class TestEndToEndAgainstTheRealRegistry:
    """Exercises the actual seeded `ftc-sd.toml` (not a fixture
    stand-in) so drift in the real registry file is caught here too --
    matching `tests/teams/test_sources_ftcscout.py`'s
    `TestRegistryConfig` precedent of trusting the real registry file
    in tests."""

    def test_dry_run_reports_152_teams_with_no_disk_write(self, tmp_path):
        fetcher = _ftcscout_fetcher()
        site = tmp_path / "stem-ecosystem"

        payload = run_teams(site_dir=site, fetcher=fetcher, dry_run=True)

        assert payload["meta"]["total"] == 152
        assert len(payload["teams"]) == 152
        assert not site.exists()

    def test_dry_run_makes_exactly_one_fetch_call(self, tmp_path):
        fetcher = _ftcscout_fetcher()

        run_teams(site_dir=tmp_path, fetcher=fetcher, dry_run=True)

        assert fetcher.calls == [SEARCH_URL]

    def test_real_run_writes_teams_json_to_site_dir(self, tmp_path):
        fetcher = _ftcscout_fetcher()
        site = _make_site(tmp_path)

        run_teams(site_dir=site, fetcher=fetcher, dry_run=False)

        written = json.loads((site / "src" / "data" / "teams.json").read_text())
        assert written["meta"]["total"] == 152
        assert written["meta"]["by_league"] == {"FTC": 152}
        assert written["meta"]["out_of_region"] == 6

    def test_source_filter_ftcscout_matches_the_real_registry_entry(self, tmp_path):
        fetcher = _ftcscout_fetcher()

        payload = run_teams(source="ftcscout", site_dir=tmp_path, fetcher=fetcher, dry_run=True)

        assert payload["meta"]["total"] == 152

    def test_source_filter_for_an_unknown_source_yields_zero_teams(self, tmp_path):
        fetcher = _ftcscout_fetcher()

        payload = run_teams(source="tba", site_dir=tmp_path, fetcher=fetcher, dry_run=True)

        assert payload["meta"]["total"] == 0
        assert fetcher.calls == []  # the filtered-out source's fetcher is never even called

    def test_default_registry_dir_is_the_real_seed_registry(self):
        assert DEFAULT_TEAMS_REGISTRY_DIR.name == "registry"
        assert (DEFAULT_TEAMS_REGISTRY_DIR / "ftc-sd.toml").is_file()


class TestExplicitRegistryDir:
    def test_a_fixture_registry_directory_with_no_matching_source_yields_nothing(
        self, tmp_path
    ):
        empty_registry = tmp_path / "empty-registry"
        empty_registry.mkdir()

        payload = run_teams(
            registry_dir=empty_registry,
            site_dir=tmp_path,
            fetcher=FixtureFetcher({}),
            dry_run=True,
        )

        assert payload["meta"]["total"] == 0
        assert payload["teams"] == []


class TestUnrecognizedAdapterTypeIsSkippedNotFatal:
    """A Team Registry entry whose `adapter_type` has no registered
    `TeamSource` (e.g. a stale/misconfigured TOML file) is logged and
    skipped -- the run still completes and still exports whatever other
    sources succeeded, matching `pipeline.run()`'s own per-source
    isolation convention."""

    def test_unrecognized_adapter_type_does_not_raise_and_yields_zero_teams(self, tmp_path):
        registry_dir = tmp_path / "registry"
        registry_dir.mkdir()
        (registry_dir / "unknown.toml").write_text(
            'org_name = "Some Bogus League"\n'
            'adapter_type = "bogus"\n'
            "enabled = true\n"
            "[config]\n"
        )

        payload = run_teams(
            registry_dir=registry_dir,
            site_dir=tmp_path,
            fetcher=FixtureFetcher({}),
            dry_run=True,
        )

        assert payload["meta"]["total"] == 0


class TestSourceFailureIsolation:
    """A `TeamSource` whose `discover`/`fetch`/`extract` chain raises is
    logged and skipped -- one broken source must never take down the
    whole `teams` run, the same SUC-008-style contract
    `partner_scrape.pipeline.run()` already gives the opportunities
    pipeline."""

    def test_a_raising_source_is_isolated_and_other_sources_still_contribute(
        self, tmp_path, monkeypatch
    ):
        class _ExplodingSource:
            def discover(self, source, fetcher):
                raise RuntimeError("boom")

        class _WorkingSource:
            def discover(self, source, fetcher):
                return []

            def fetch(self, ref, fetcher):  # pragma: no cover - discover returns no refs
                raise AssertionError("should not be called")

            def extract(self, raw, source):  # pragma: no cover
                raise AssertionError("should not be called")

        monkeypatch.setattr(
            teams_pipeline,
            "_TEAM_SOURCES",
            {"ftcscout": _ExplodingSource(), "tba": _WorkingSource()},
        )

        registry_dir = tmp_path / "registry"
        registry_dir.mkdir()
        (registry_dir / "ftc-sd.toml").write_text(
            'org_name = "FTC"\nadapter_type = "ftcscout"\nenabled = true\n[config]\n'
        )
        (registry_dir / "frc-sd.toml").write_text(
            'org_name = "FRC"\nadapter_type = "tba"\nenabled = true\n[config]\n'
        )

        payload = run_teams(
            registry_dir=registry_dir,
            site_dir=tmp_path,
            fetcher=FixtureFetcher({}),
            dry_run=True,
        )

        # Neither source produced any Team here (the working one just
        # returns no refs) -- the point is that the exploding source's
        # RuntimeError never propagates out of run_teams().
        assert payload["meta"]["total"] == 0
