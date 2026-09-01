"""Tests for partner_scrape.export.ads: the Ad Content Export module.

Every test that inspects the write side passes an explicit `own_data_dir`
under `tmp_path` (mirroring `test_export.py`'s own convention -- no test
writes to the real sibling `stem-ecosystem` checkout, which this module
no longer writes to at all -- see ads.py's module docstring).
`TestLoadAdConfigs` runs against a synthetic `tests/fixtures/ad_registry/`
directory (mirroring `test_registry_hub_schema.py`'s pattern);
`TestRealSeedAdRegistry` separately exercises the real, hand-authored
`registry/ads/league.toml` seed content.

Sprint 020 ticket 004 added a second, similarly-defaulting `own_data_dir`
parameter to `export_ads()`, alongside an original write into a sibling
`stem-ecosystem` checkout's `site_dir`. Sprint 025 ticket 003 removed
that `site_dir` write (and the parameter itself) entirely --
`own_data_dir` is now the function's sole write target. The
module-level `_own_data_dir_default` autouse fixture below pins
`own_data_dir`'s *default* resolution to a throwaway directory for
every test in this file, so a test that never passes `own_data_dir`
explicitly still can't reach this repo's real `data/` directory
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

    `own_data_dir` resolves via a `config` accessor when omitted --
    `config.get_own_data_dir()` always returns this repo's real `data/`
    directory (`DEFAULT_OWN_DATA_DIR` is "not overridable via
    environment variable" by design). A test that never passes
    `own_data_dir` explicitly would otherwise auto-create and write
    real files into this repo's actual `data/` directory on every test
    run -- contradicting sprint.md's Test Strategy ("Hermetic
    throughout ... tests pass an explicit tmp_path, never the real
    default").

    Resolved via `tmp_path_factory` (outside the current test's own
    `tmp_path` tree), matching `test_export.py`'s identical
    `_own_data_dir_default` fixture for `export_opportunities()`.
    """
    fake_own_data_dir = tmp_path_factory.mktemp("own-data-default")
    monkeypatch.setattr(ads, "get_own_data_dir", lambda: fake_own_data_dir)


class TestExportAdsWritesSchema:
    def test_written_json_is_an_array_of_documented_schema_objects(self, tmp_path):
        own_data_dir = tmp_path / "own-data"

        payload = export_ads([_ad()], own_data_dir=own_data_dir)

        assert payload == [
            {
                "headline": "Give Your Kid a Head Start in Code",
                "body": "Short pitch text.",
                "link": "https://www.jointheleague.org/",
                "logo_src": "the_league_of_amazing.png",
            }
        ]
        written = json.loads((own_data_dir / "ads.json").read_text())
        assert written == payload

    def test_extensible_to_multiple_advertisers_without_a_schema_break(self, tmp_path):
        own_data_dir = tmp_path / "own-data"

        payload = export_ads(
            [_ad(headline="Ad One"), _ad(headline="Ad Two")], own_data_dir=own_data_dir
        )

        assert [entry["headline"] for entry in payload] == ["Ad One", "Ad Two"]
        written = json.loads((own_data_dir / "ads.json").read_text())
        assert [entry["headline"] for entry in written] == ["Ad One", "Ad Two"]

    def test_empty_ad_configs_writes_an_empty_array(self, tmp_path):
        own_data_dir = tmp_path / "own-data"

        payload = export_ads([], own_data_dir=own_data_dir)

        assert payload == []
        written = json.loads((own_data_dir / "ads.json").read_text())
        assert written == []


class TestDryRun:
    def test_dry_run_returns_the_payload_but_writes_nothing(self):
        payload = export_ads([_ad()], dry_run=True)

        assert len(payload) == 1

    def test_dry_run_payload_matches_non_dry_run_payload(self):
        dry_payload = export_ads([_ad()], dry_run=True)
        real_payload = export_ads([_ad()])

        assert dry_payload == real_payload


class TestOwnDataDirErrors:
    """Sprint 025 ticket 003: with the `site_dir` write removed,
    `own_data_dir`'s own failure path -- previously untested because a
    `site_dir` failure always propagated first -- is the only failure
    path `export_ads` has left, and gets its own direct test (mirrors
    `test_export.py`'s `TestOwnDataDirErrors`)."""

    def test_own_data_dir_occupied_by_a_file_raises_a_clear_error(self, tmp_path):
        # own_data_dir itself is a plain file, not a directory --
        # `Path.mkdir(parents=True, exist_ok=True)` cannot succeed here
        # even with exist_ok=True (that only forgives an *existing
        # directory*, not an existing file) -- simulates an
        # unwritable/broken own_data_dir without relying on OS
        # permission bits (which root can bypass in some CI sandboxes).
        own_data_dir = tmp_path / "own-data"
        own_data_dir.write_text("not a directory")

        with pytest.raises(RuntimeError, match="own_data_dir"):
            export_ads([_ad()], own_data_dir=own_data_dir)


class TestOwnDataDirIsolation:
    """Sprint 025 ticket 003 (issue 21, "stop writing to the
    stem-ecosystem checkout"): `export_ads()` no longer accepts a
    `site_dir` parameter and never writes into a sibling
    `stem-ecosystem` checkout's `src/data/` -- `own_data_dir` is the
    sole write target. Inverts this module's pre-ticket
    `test_writes_only_under_the_given_own_data_dir` (which also
    asserted a `site_dir` write happened) into a proof that no such
    write happens, alongside the equivalent isolation proof for
    `own_data_dir` itself (mirrors `test_export.py`'s
    `TestOwnDataDirIsolation`).
    """

    def test_writes_only_under_the_given_own_data_dir(self, tmp_path):
        own_data_dir = tmp_path / "own-data"

        export_ads([_ad()], own_data_dir=own_data_dir)

        written_files = sorted(p for p in tmp_path.rglob("*") if p.is_file())
        assert written_files == sorted([own_data_dir / "ads.json"])

    def test_no_site_dir_shaped_write_occurs_anywhere(self, tmp_path):
        """Direct inversion of the pre-ticket `site_dir` write proof: a
        `src/data/ads.json` -- the removed `site_dir` write's exact old
        shape -- must never be created, confirmed even when a directory
        that happens to look like an old `site_dir` checkout already
        exists under `tmp_path`."""
        stale_site_dir_lookalike = tmp_path / "stem-ecosystem"
        (stale_site_dir_lookalike / "src" / "data").mkdir(parents=True)
        own_data_dir = tmp_path / "own-data"

        export_ads([_ad()], own_data_dir=own_data_dir)

        assert not (stale_site_dir_lookalike / "src" / "data" / "ads.json").exists()


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
    """Loading the actual registry/ads/ directory."""

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

    def test_real_seed_ad_exports_cleanly_to_a_tmp_own_data_dir(self, tmp_path):
        own_data_dir = tmp_path / "own-data"

        payload = export_ads(load_ad_configs(), own_data_dir=own_data_dir)

        assert len(payload) >= 1
        for entry in payload:
            assert set(entry.keys()) == {"headline", "body", "link", "logo_src"}


class TestOwnDataDirPublish:
    """Sprint 020 ticket 004 (issue 60) added this write path -- the
    already-computed `ads.json` payload written into partner-scrape's
    own `data/` directory via `config.get_own_data_dir()`. Sprint 025
    ticket 003 removed the sibling `stem-ecosystem` write this used to
    run alongside (see `TestOwnDataDirIsolation` above for the
    isolation/inversion proof) -- `own_data_dir` is now this function's
    only write target, and these tests cover its own defaulting,
    auto-creation, and dry_run behavior in isolation. Mirrors
    `test_export.py`'s `TestOwnDataDirPublish` structure and naming
    conventions, scoped to `ads.json`.
    """

    def test_omitted_own_data_dir_resolves_via_config_get_own_data_dir(
        self, tmp_path, monkeypatch
    ):
        fake_own_data_dir = tmp_path / "fake-own-data"
        monkeypatch.setattr(ads, "get_own_data_dir", lambda: fake_own_data_dir)

        export_ads([_ad()])

        assert (fake_own_data_dir / "ads.json").exists()

    def test_missing_own_data_dir_is_created_automatically_never_raises(self, tmp_path):
        own_data_dir = tmp_path / "does-not-exist-yet" / "nested"
        assert not own_data_dir.exists()

        export_ads([_ad()], own_data_dir=own_data_dir)

        assert (own_data_dir / "ads.json").exists()

    def test_dry_run_writes_nothing_to_own_data_dir(self, tmp_path):
        own_data_dir = tmp_path / "own-data"

        payload = export_ads([_ad()], own_data_dir=own_data_dir, dry_run=True)

        assert len(payload) == 1
        assert not own_data_dir.exists()
