"""Tests for partner_scrape.registry.hub_schema: HubConfig and the Hub
Registry's TOML directory loader.

Fixture tests run against ``tests/fixtures/hub_registry/`` (synthetic,
hand-built well-formed and malformed files), mirroring
``test_registry.py``'s pattern for the Source Registry. A separate class
exercises the real ``partner_scrape/registry/hubs/`` seed directory and
confirms it stays invisible to the Source Registry's own default load.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from partner_scrape.registry.hub_schema import (
    DEFAULT_HUBS_DIR,
    HubConfig,
    InvalidHubConfig,
    load_hubs,
)
from partner_scrape.registry.loader import DEFAULT_SOURCES_DIR, load_sources

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "hub_registry"


class TestHubConfigFromToml:
    def test_parses_valid_file(self):
        hub = HubConfig.from_toml(FIXTURES_DIR / "good_hub_one.toml")

        assert hub.hub_name == "Fixture Hub One"
        assert hub.page_urls == ["https://fixturehub1.org/calendar"]
        assert hub.config == {}

    def test_hub_id_derived_from_filename_stem(self):
        hub = HubConfig.from_toml(FIXTURES_DIR / "good_hub_two.toml")
        assert hub.hub_id == "good_hub_two"

    def test_multiple_page_urls_and_optional_config_parsed(self):
        hub = HubConfig.from_toml(FIXTURES_DIR / "good_hub_two.toml")

        assert hub.page_urls == [
            "https://fixturehub2.org/events/a",
            "https://fixturehub2.org/events/b",
        ]
        assert hub.config == {"note": "irrelevant hub-specific scan hint"}

    def test_missing_required_field_raises_invalid_hub_config(self):
        with pytest.raises(InvalidHubConfig):
            HubConfig.from_toml(FIXTURES_DIR / "missing_page_urls.toml")


class TestLoadHubs:
    def test_loads_all_wellformed_files(self):
        hubs = load_hubs(FIXTURES_DIR)
        hub_ids = {h.hub_id for h in hubs}

        assert {"good_hub_one", "good_hub_two"} <= hub_ids

    def test_skips_file_missing_required_field(self):
        hubs = load_hubs(FIXTURES_DIR)
        hub_ids = {h.hub_id for h in hubs}

        assert "missing_page_urls" not in hub_ids

    def test_skips_malformed_toml_file(self):
        hubs = load_hubs(FIXTURES_DIR)
        hub_ids = {h.hub_id for h in hubs}

        assert "broken_syntax" not in hub_ids

    def test_bad_files_do_not_prevent_the_rest_of_the_directory_loading(self):
        # Four files in the fixture dir, two intentionally broken -- the
        # other two must still come back.
        hubs = load_hubs(FIXTURES_DIR)
        assert len(hubs) == 2

    def test_malformed_file_is_logged_not_fatal(self, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            hubs = load_hubs(FIXTURES_DIR)

        assert len(hubs) == 2
        assert "missing_page_urls" in caplog.text or "broken_syntax" in caplog.text

    def test_defaults_to_the_real_hubs_directory_when_no_argument_given(self):
        hubs = load_hubs()
        assert {h.hub_id for h in hubs} == {"example-regional-calendar"}


class TestRealSeedHubRegistry:
    """Loading the actual partner_scrape/registry/hubs/ directory."""

    def test_default_hubs_dir_points_at_the_real_hub_registry(self):
        assert DEFAULT_HUBS_DIR.name == "hubs"
        assert DEFAULT_HUBS_DIR.parent.name == "registry"

    def test_hubs_dir_is_physically_separate_from_sources_dir(self):
        assert DEFAULT_HUBS_DIR != DEFAULT_SOURCES_DIR

    def test_example_seed_hub_loads_successfully(self):
        hubs = {h.hub_id: h for h in load_hubs()}

        seed = hubs["example-regional-calendar"]
        assert seed.hub_name
        assert seed.page_urls
        assert all(isinstance(url, str) and url for url in seed.page_urls)

    def test_example_seed_hub_is_clearly_marked_as_a_template(self):
        hubs = {h.hub_id: h for h in load_hubs()}
        seed = hubs["example-regional-calendar"]

        # Not a live hub -- proven here by the hub_name itself flagging
        # it as a template, not just by a source comment a test can't see.
        assert "template" in seed.hub_name.lower() or "not live" in seed.hub_name.lower()

    def test_default_source_registry_scan_never_sees_hub_files(self):
        # The core safety property this ticket's Description calls for:
        # registry/loader.py's DEFAULT_SOURCES_DIR scan is untouched by
        # this ticket -- the hub directory is physically separate, so the
        # real Source Registry load never includes the seed hub's id.
        source_ids = {s.source_id for s in load_sources()}
        assert "example-regional-calendar" not in source_ids
