"""Tests for partner_scrape.export.ads: the Ad Content Export module.

Every test passes an explicit `site_dir` under `tmp_path` for the write
side (mirroring `test_export.py`'s own convention -- no test writes to
the real sibling `stem-ecosystem` checkout). `TestLoadAdConfigs` runs
against a synthetic `tests/fixtures/ad_registry/` directory (mirroring
`test_registry_hub_schema.py`'s pattern); `TestRealSeedAdRegistry`
separately exercises the real, hand-authored
`partner_scrape/registry/ads/league.toml` seed content.

Sprint 020 ticket 004 adds a second, similarly-defaulting `own_data_dir`
parameter to `export_ads()`. Every test written before that ticket
predates the parameter and never passes it explicitly -- the
module-level `_own_data_dir_default` autouse fixture below pins its
default resolution to a throwaway directory for every test in this
file, so none of them can reach this repo's real `data/` directory
(mirrors `test_export.py`'s identical fixture for
`export_opportunities()`, sprint 020 ticket 003).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from partner_scrape.export import ads
from partner_scrape.export.ads import (
    DEFAULT_ADS_DIR,
    AdConfig,
    InvalidAdConfig,
    export_ads,
    load_ad_configs,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "ad_registry"


def _site_dir(tmp_path: Path) -> Path:
    """A tmp_path-backed stand-in for the sibling stem-ecosystem repo,
    with `src/data` pre-created (matching a real checkout's layout)."""
    site_dir = tmp_path / "stem-ecosystem"
    (site_dir / "src" / "data").mkdir(parents=True)
    return site_dir


def _ad(
    headline: str = "Give Your Kid a Head Start in Code",
    body: str = "Short pitch text.",
    link: str = "https://www.jointheleague.org/",
    logo_src: str = "the_league_of_amazing.png",
) -> AdConfig:
    return AdConfig(headline=headline, body=body, link=link, logo_src=logo_src)


@pytest.fixture(autouse=True)
def _own_data_dir_default(tmp_path_factory, monkeypatch):
    """Pin `ads.get_own_data_dir()`'s resolution to a throwaway
    directory for every test in this file (sprint 020 ticket 004).

    `own_data_dir` (like `site_dir`) resolves via a `config` accessor
    when omitted, but unlike `site_dir` it has no environment-variable
    override -- `config.get_own_data_dir()` always returns this repo's
    real `data/` directory (`DEFAULT_OWN_DATA_DIR` is "not overridable
    via environment variable" by design). Every test written before
    this ticket predates the `own_data_dir` parameter and so never
    passes it explicitly; without this fixture, each such test's
    non-`dry_run` call would auto-create and write real files into
    this repo's actual `data/` directory on every test run --
    contradicting sprint.md's Test Strategy ("Hermetic throughout ...
    tests pass an explicit tmp_path, never the real default").

    Resolved via `tmp_path_factory` (outside the current test's own
    `tmp_path` tree), matching `test_export.py`'s identical
    `_own_data_dir_default` fixture for `export_opportunities()`.
    """
    fake_own_data_dir = tmp_path_factory.mktemp("own-data-default")
    monkeypatch.setattr(ads, "get_own_data_dir", lambda: fake_own_data_dir)


class TestExportAdsWritesSchema:
    def test_written_json_is_an_array_of_documented_schema_objects(self, tmp_path):
        site_dir = _site_dir(tmp_path)

        payload = export_ads([_ad()], site_dir=site_dir)

        assert payload == [
            {
                "headline": "Give Your Kid a Head Start in Code",
                "body": "Short pitch text.",
                "link": "https://www.jointheleague.org/",
                "logo_src": "the_league_of_amazing.png",
            }
        ]
        written = json.loads((site_dir / "src" / "data" / "ads.json").read_text())
        assert written == payload

    def test_extensible_to_multiple_advertisers_without_a_schema_break(self, tmp_path):
        site_dir = _site_dir(tmp_path)

        payload = export_ads(
            [_ad(headline="Ad One"), _ad(headline="Ad Two")], site_dir=site_dir
        )

        assert [entry["headline"] for entry in payload] == ["Ad One", "Ad Two"]
        written = json.loads((site_dir / "src" / "data" / "ads.json").read_text())
        assert [entry["headline"] for entry in written] == ["Ad One", "Ad Two"]

    def test_empty_ad_configs_writes_an_empty_array(self, tmp_path):
        site_dir = _site_dir(tmp_path)

        payload = export_ads([], site_dir=site_dir)

        assert payload == []
        written = json.loads((site_dir / "src" / "data" / "ads.json").read_text())
        assert written == []


class TestDryRun:
    def test_dry_run_returns_the_payload_but_writes_nothing(self, tmp_path):
        site_dir = _site_dir(tmp_path)

        payload = export_ads([_ad()], site_dir=site_dir, dry_run=True)

        assert len(payload) == 1
        assert not (site_dir / "src" / "data" / "ads.json").exists()

    def test_dry_run_payload_matches_non_dry_run_payload(self, tmp_path):
        site_dir = _site_dir(tmp_path)

        dry_payload = export_ads([_ad()], site_dir=site_dir, dry_run=True)
        real_payload = export_ads([_ad()], site_dir=site_dir)

        assert dry_payload == real_payload


class TestSiteDirErrors:
    def test_missing_site_dir_raises_a_clear_error_naming_the_path(self, tmp_path):
        missing = tmp_path / "does-not-exist"

        with pytest.raises(RuntimeError, match="site_dir"):
            export_ads([_ad()], site_dir=missing)

    def test_missing_site_dir_writes_nothing(self, tmp_path):
        missing = tmp_path / "does-not-exist"

        with pytest.raises(RuntimeError):
            export_ads([_ad()], site_dir=missing)

        assert not missing.exists()

    def test_data_path_occupied_by_a_file_raises_a_clear_error(self, tmp_path):
        site_dir = tmp_path / "stem-ecosystem"
        (site_dir / "src").mkdir(parents=True)
        # `src/data` is a plain file here, not a directory -- simulates an
        # unwritable/broken site checkout without relying on OS
        # permission bits (which root can bypass in some CI sandboxes).
        (site_dir / "src" / "data").write_text("not a directory")

        with pytest.raises(RuntimeError, match="site_dir"):
            export_ads([_ad()], site_dir=site_dir)


class TestSiteDirDefaulting:
    def test_explicit_site_dir_never_consults_config_default(self, tmp_path, monkeypatch):
        site_dir = _site_dir(tmp_path)

        def _boom():
            raise AssertionError("get_site_dir() must not be called when site_dir is explicit")

        monkeypatch.setattr(ads, "get_site_dir", _boom)

        export_ads([_ad()], site_dir=site_dir)

    def test_omitted_site_dir_resolves_via_config_get_site_dir(self, tmp_path, monkeypatch):
        fake_site_dir = _site_dir(tmp_path)
        monkeypatch.setattr(ads, "get_site_dir", lambda: fake_site_dir)

        export_ads([_ad()])

        assert (fake_site_dir / "src" / "data" / "ads.json").exists()


class TestAdConfigFromToml:
    def test_parses_valid_file(self):
        ad = AdConfig.from_toml(FIXTURES_DIR / "good_ad_one.toml")

        assert ad.headline == "Fixture Ad One"
        assert ad.body == "Fixture pitch text for ad one."
        assert ad.link == "https://fixture-advertiser-one.example/"
        assert ad.logo_src == "fixture_ad_one.png"

    def test_missing_required_field_raises_invalid_ad_config(self):
        with pytest.raises(InvalidAdConfig):
            AdConfig.from_toml(FIXTURES_DIR / "missing_body.toml")


class TestLoadAdConfigs:
    def test_loads_all_wellformed_files(self):
        loaded = load_ad_configs(FIXTURES_DIR)
        headlines = {ad.headline for ad in loaded}

        assert {"Fixture Ad One", "Fixture Ad Two"} <= headlines

    def test_skips_file_missing_required_field(self):
        loaded = load_ad_configs(FIXTURES_DIR)
        headlines = {ad.headline for ad in loaded}

        assert "Missing Body Field" not in headlines

    def test_skips_malformed_toml_file(self):
        loaded = load_ad_configs(FIXTURES_DIR)

        # Only the two well-formed fixture files survive; the malformed
        # and missing-field files are both skipped, not fatal.
        assert len(loaded) == 2

    def test_malformed_and_invalid_files_are_logged_not_fatal(self, caplog):
        with caplog.at_level(logging.WARNING, logger="partner_scrape.export.ads"):
            loaded = load_ad_configs(FIXTURES_DIR)

        assert len(loaded) == 2
        assert "missing_body" in caplog.text or "broken_syntax" in caplog.text

    def test_defaults_to_the_real_ads_directory_when_no_argument_given(self):
        loaded = load_ad_configs()

        assert {ad.headline for ad in loaded} != set()


class TestRealSeedAdRegistry:
    """Loading the actual partner_scrape/registry/ads/ directory."""

    def test_default_ads_dir_points_at_the_real_ad_registry(self):
        assert DEFAULT_ADS_DIR.name == "ads"
        assert DEFAULT_ADS_DIR.parent.name == "registry"

    def test_league_seed_ad_loads_with_all_required_fields_populated(self):
        loaded = load_ad_configs()

        assert len(loaded) >= 1
        league = loaded[0]
        assert league.headline
        assert league.body
        assert league.link.startswith("https://www.jointheleague.org")
        assert league.logo_src == "the_league_of_amazing.png"

    def test_real_seed_ad_exports_cleanly_to_a_tmp_site_dir(self, tmp_path):
        site_dir = _site_dir(tmp_path)

        payload = export_ads(load_ad_configs(), site_dir=site_dir)

        assert len(payload) >= 1
        for entry in payload:
            assert set(entry.keys()) == {"headline", "body", "link", "logo_src"}


class TestOwnDataDirPublish:
    """Sprint 020 ticket 004 (issue 60): the third write path -- the
    same already-computed `ads.json` payload written to `site_dir`,
    written again into partner-scrape's own `data/` directory via
    `config.get_own_data_dir()`. Mirrors `test_export.py`'s
    `TestOwnDataDirPublish` structure and naming conventions, scoped to
    `ads.json`.
    """

    def test_own_data_dir_content_matches_site_dir_content_exactly(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        own_data_dir = tmp_path / "own-data"

        export_ads([_ad()], site_dir=site_dir, own_data_dir=own_data_dir)

        site_ads = (site_dir / "src" / "data" / "ads.json").read_text()
        own_ads = (own_data_dir / "ads.json").read_text()

        assert own_ads == site_ads

    def test_writes_only_under_the_given_own_data_dir(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        own_data_dir = tmp_path / "own-data"

        export_ads([_ad()], site_dir=site_dir, own_data_dir=own_data_dir)

        written_files = sorted(p for p in tmp_path.rglob("*") if p.is_file())
        assert written_files == sorted(
            [
                site_dir / "src" / "data" / "ads.json",
                own_data_dir / "ads.json",
            ]
        )

    def test_omitted_own_data_dir_resolves_via_config_get_own_data_dir(
        self, tmp_path, monkeypatch
    ):
        site_dir = _site_dir(tmp_path)
        fake_own_data_dir = tmp_path / "fake-own-data"
        monkeypatch.setattr(ads, "get_own_data_dir", lambda: fake_own_data_dir)

        export_ads([_ad()], site_dir=site_dir)

        assert (fake_own_data_dir / "ads.json").exists()

    def test_missing_own_data_dir_is_created_automatically_never_raises(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        own_data_dir = tmp_path / "does-not-exist-yet" / "nested"
        assert not own_data_dir.exists()

        export_ads([_ad()], site_dir=site_dir, own_data_dir=own_data_dir)

        assert (own_data_dir / "ads.json").exists()

    def test_dry_run_writes_nothing_to_own_data_dir(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        own_data_dir = tmp_path / "own-data"

        payload = export_ads(
            [_ad()], site_dir=site_dir, own_data_dir=own_data_dir, dry_run=True
        )

        assert len(payload) == 1
        assert not own_data_dir.exists()
        assert not (site_dir / "src" / "data" / "ads.json").exists()
