"""Tests for partner_scrape.registry: SourceConfig, the TOML directory
loader, and the real seed data.

Fixture tests run against ``tests/fixtures/registry/`` (synthetic,
hand-built well-formed and malformed files) so they don't depend on the
production registry's exact contents. A separate class exercises the
real ``partner_scrape/registry/sources/`` seed directory.
"""

from pathlib import Path

import pytest

from partner_scrape.registry.loader import (
    DEFAULT_SOURCES_DIR,
    load_active_sources,
    load_sources,
)
from partner_scrape.registry.schema import InvalidSourceConfig, SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "registry"


class TestSourceConfigFromToml:
    def test_parses_valid_file(self):
        source = SourceConfig.from_toml(FIXTURES_DIR / "good_one.toml")

        assert source.org_name == "Fixture Org One"
        assert source.adapter_type == "tec_rest"
        assert source.config == {
            "api_base": "https://example.org/wp-json/tribe/events/v1/events/"
        }
        assert source.enabled is True

    def test_source_id_derived_from_filename_stem(self):
        source = SourceConfig.from_toml(FIXTURES_DIR / "good_two.toml")
        assert source.source_id == "good_two"

    def test_taxonomy_defaults_and_acquisition_policy_default_when_absent(self):
        source = SourceConfig.from_toml(FIXTURES_DIR / "good_one.toml")

        assert source.taxonomy_defaults == {}
        assert source.acquisition_policy == {
            "rate_limit_seconds": 1.0,
            "respect_robots": True,
            "discovered_via": "manual",
            # ticket 005: additive default -- a file with no
            # [acquisition_policy] section at all (good_one.toml) still
            # resolves fetch_strategy to "static", today's exact
            # pre-ticket-005 fetch behavior.
            "fetch_strategy": "static",
        }

    def test_fetch_strategy_defaults_to_static_when_acquisition_policy_omits_it(self):
        # A source with an [acquisition_policy] section that sets other
        # keys but not fetch_strategy must still default it to "static"
        # -- the merge in SourceConfig.from_toml is per-key, not
        # all-or-nothing.
        source = SourceConfig.from_toml(
            FIXTURES_DIR.parent / "registry_fetch_strategy" / "partial_acquisition_policy.toml"
        )
        assert source.acquisition_policy["rate_limit_seconds"] == 2.5
        assert source.acquisition_policy["fetch_strategy"] == "static"

    def test_taxonomy_defaults_read_when_present(self):
        source = SourceConfig.from_toml(FIXTURES_DIR / "good_two.toml")
        assert source.taxonomy_defaults == {"areas_of_interest": ["environment"]}

    def test_enabled_false_is_parseable(self):
        source = SourceConfig.from_toml(FIXTURES_DIR / "disabled.toml")
        assert source.enabled is False

    def test_missing_required_field_raises_invalid_source_config(self):
        with pytest.raises(InvalidSourceConfig):
            SourceConfig.from_toml(FIXTURES_DIR / "missing_adapter_type.toml")


class TestLoadSources:
    def test_loads_all_wellformed_files(self):
        sources = load_sources(FIXTURES_DIR)
        source_ids = {s.source_id for s in sources}

        assert {"good_one", "good_two", "disabled"} <= source_ids

    def test_skips_file_missing_required_field(self):
        sources = load_sources(FIXTURES_DIR)
        source_ids = {s.source_id for s in sources}

        assert "missing_adapter_type" not in source_ids

    def test_skips_malformed_toml_file(self):
        sources = load_sources(FIXTURES_DIR)
        source_ids = {s.source_id for s in sources}

        assert "broken_syntax" not in source_ids

    def test_bad_files_do_not_prevent_the_rest_of_the_directory_loading(self):
        # Five files in the fixture dir, two intentionally broken --
        # the other three must still come back.
        sources = load_sources(FIXTURES_DIR)
        assert len(sources) == 3

    def test_includes_disabled_entries_as_parseable(self):
        sources = load_sources(FIXTURES_DIR)
        disabled = [s for s in sources if s.source_id == "disabled"]

        assert len(disabled) == 1
        assert disabled[0].enabled is False

    def test_defaults_to_the_real_registry_directory_when_no_argument_given(self):
        sources = load_sources()
        assert {s.source_id for s in sources} == {
            "coastalrootsfarm",
            "thelivingcoast",
            "eefkids",
            "cleansd",
            "oceanconnectors",
            "visitcmod",
            "birch-aquarium",
            "fleet-science-center",
        }


class TestLoadActiveSources:
    def test_excludes_disabled_entries(self):
        sources = load_active_sources(FIXTURES_DIR)
        source_ids = {s.source_id for s in sources}

        assert "disabled" not in source_ids

    def test_includes_enabled_entries(self):
        sources = load_active_sources(FIXTURES_DIR)
        source_ids = {s.source_id for s in sources}

        assert {"good_one", "good_two"} <= source_ids


class TestRealSeedRegistry:
    """Loading the actual partner_scrape/registry/sources/ directory."""

    def test_default_sources_dir_points_at_the_real_registry(self):
        assert DEFAULT_SOURCES_DIR.name == "sources"
        assert DEFAULT_SOURCES_DIR.parent.name == "registry"

    def test_six_known_tec_sites_load_as_enabled(self):
        sources = load_active_sources()
        tec_sources = [s for s in sources if s.adapter_type == "tec_rest"]

        assert len(tec_sources) == 6
        assert all(s.enabled for s in tec_sources)

    def test_seed_source_org_names_match_dev_fetch_tec_api(self):
        sources = {s.source_id: s for s in load_active_sources()}

        assert sources["coastalrootsfarm"].org_name == "Coastal Roots Farm"
        assert sources["thelivingcoast"].org_name == "The Living Coast Discovery Center"
        assert sources["eefkids"].org_name == "EastLake Educational Foundation"
        assert sources["cleansd"].org_name == "I Love A Clean San Diego"
        assert sources["oceanconnectors"].org_name == "Ocean Connectors"
        assert (
            sources["visitcmod"].org_name == "San Diego Children's Discovery Museum"
        )

    def test_seed_source_api_bases_match_dev_fetch_tec_api(self):
        sources = {s.source_id: s for s in load_active_sources()}

        assert sources["coastalrootsfarm"].config["api_base"] == (
            "https://coastalrootsfarm.org/wp-json/tribe/events/v1/events/"
        )
        assert sources["thelivingcoast"].config["api_base"] == (
            "https://www.thelivingcoast.org/wp-json/tribe/events/v1/events/"
        )
        assert sources["eefkids"].config["api_base"] == (
            "https://eefkids.org/wp-json/tribe/events/v1/events/"
        )
        assert sources["cleansd"].config["api_base"] == (
            "https://www.cleansd.org/wp-json/tribe/events/v1/events/"
        )
        assert sources["oceanconnectors"].config["api_base"] == (
            "https://oceanconnectors.org/wp-json/tribe/events/v1/events/"
        )
        assert sources["visitcmod"].config["api_base"] == (
            "https://visitcmod.org/wp-json/tribe/events/v1/events/"
        )


class TestRealBirchAquariumSource:
    """The real birch-aquarium.toml Localist source (ticket 002)."""

    def test_loads_as_enabled_localist_source(self):
        sources = {s.source_id: s for s in load_active_sources()}

        birch = sources["birch-aquarium"]
        assert birch.org_name == "Birch Aquarium at Scripps"
        assert birch.adapter_type == "localist"
        assert birch.enabled is True

    def test_config_matches_live_confirmed_values(self):
        sources = {s.source_id: s for s in load_active_sources()}

        birch = sources["birch-aquarium"]
        assert birch.config["api_base"] == "https://calendar.ucsd.edu/api/2/events"
        assert birch.config["group_id"] == "49845193640602"
        assert birch.config["days"] == 180
        assert birch.config["pp"] == 50


class TestRealFleetScienceCenterSource:
    """The real fleet-science-center.toml listing_html source (ticket 004)."""

    def test_loads_as_enabled_listing_html_source(self):
        sources = {s.source_id: s for s in load_active_sources()}

        fleet = sources["fleet-science-center"]
        assert fleet.org_name == "Fleet Science Center"
        assert fleet.adapter_type == "listing_html"
        assert fleet.enabled is True

    def test_config_matches_live_confirmed_values(self):
        sources = {s.source_id: s for s in load_active_sources()}

        fleet = sources["fleet-science-center"]
        assert fleet.config["site_url"] == "https://www.fleetscience.org"
        assert fleet.config["listing_urls"] == ["/events"]
