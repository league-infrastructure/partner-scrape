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
            # Source-level concurrency + per-source URL cap: additive
            # default -- a file with no [acquisition_policy] section at
            # all still resolves max_urls to the package default (300).
            "max_urls": 300,
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
        # Superset (not exact-equality) check: the registry grows as
        # operational partner sources are added, so pin only the core
        # seed sources each sprint established rather than the full set.
        sources = load_sources()
        source_ids = {s.source_id for s in sources}
        assert {
            "coastalrootsfarm",
            "thelivingcoast",
            "eefkids",
            "cleansd",
            "oceanconnectors",
            "visitcmod",
            "birch-aquarium",
            "fleet-science-center",
            "jointheleague",
            "boundlessbio",
            "gossamerbio",
            "elementbiosciences",
            "shieldai",
        } <= source_ids


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

    def test_known_tec_sites_load_as_enabled(self):
        # Pre-existing count, updated for sprint 014 ticket 003's
        # zero-yield triage (2026-08-30): cleansd and ilacsd were
        # disabled (both now bot/CAPTCHA-blocked -- see their TOML
        # comments) and sd-river-park-foundation was re-typed from
        # generic_html to tec_rest (a confirmed live TEC REST API), so
        # the known-good count moved from 7 to 6 (-2, +1). Updated again
        # for sprint 014 ticket 004's verified-feed registration
        # (2026-08-30): 8 new tec_rest sources (balboa-park,
        # sdcoastkeeper, ymcasd, comic-con-museum, sandiegoarchaeology,
        # shpesd, thegarden, jasandiego), each live-verified before
        # commit -- 6 + 8 = 14. Not a behavior change -- this test just
        # asserts against the real, current registry contents.
        sources = load_active_sources()
        tec_sources = [s for s in sources if s.adapter_type == "tec_rest"]

        assert len(tec_sources) == 14
        assert all(s.enabled for s in tec_sources)

    def test_seed_source_org_names_match_dev_fetch_tec_api(self):
        sources = {s.source_id: s for s in load_active_sources()}

        assert sources["coastalrootsfarm"].org_name == "Coastal Roots Farm"
        assert sources["thelivingcoast"].org_name == "The Living Coast Discovery Center"
        assert sources["eefkids"].org_name == "EastLake Educational Foundation"
        # cleansd disabled sprint 014 ticket 003 (2026-08-30, Cloudflare
        # bot-management) -- no longer in the active set; see
        # registry/sources/cleansd.toml.
        assert sources["oceanconnectors"].org_name == "Ocean Connectors"
        assert (
            sources["visitcmod"].org_name == "San Diego Children's Discovery Museum"
        )
        assert sources["sd-river-park-foundation"].org_name == (
            "The San Diego River Park Foundation"
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
        # cleansd disabled sprint 014 ticket 003 (2026-08-30, Cloudflare
        # bot-management) -- no longer in the active set; see
        # registry/sources/cleansd.toml.
        assert sources["oceanconnectors"].config["api_base"] == (
            "https://oceanconnectors.org/wp-json/tribe/events/v1/events/"
        )
        assert sources["sd-river-park-foundation"].config["api_base"] == (
            "https://sandiegoriver.org/wp-json/tribe/events/v1/events/"
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


class TestRealJoinTheLeagueSource:
    """The real jointheleague.toml generic_html source (sprint 005 ticket 002).

    Disabled (OOP, 2026-07-20) by the leaguesync adapter's addition: this
    generic_html scrape of jointheleague.org/classes could recover
    titles/descriptions but never real schedules/dates, so
    registry/sources/leaguesync.toml (adapter_type="leaguesync", pulling
    directly from the League's own sync.jtlapp.net query API) is now the
    authoritative source for League classes. This source stays
    registered -- config/history preserved -- just disabled, so these
    tests read via ``load_sources()`` (includes disabled entries) rather
    than ``load_active_sources()``.
    """

    def test_loads_as_disabled_generic_html_source(self):
        sources = {s.source_id: s for s in load_sources()}

        league = sources["jointheleague"]
        assert league.org_name == "The LEAGUE of Amazing Programmers"
        assert league.adapter_type == "generic_html"
        assert league.enabled is False

    def test_config_matches_live_confirmed_values(self):
        sources = {s.source_id: s for s in load_sources()}

        league = sources["jointheleague"]
        assert league.config["site_url"] == "https://www.jointheleague.org"
        # Hyphenated -- confirmed live during sprint 005 planning; set
        # explicitly so this source doesn't depend on probing order even
        # after ticket 001's parse-based-acceptance hardening.
        assert league.config["sitemap_url"] == "https://www.jointheleague.org/sitemap-index.xml"

    def test_excluded_from_active_sources(self):
        # Disabled sources must never be dispatched by a real run --
        # load_active_sources() is the Pipeline's actual enumeration
        # call (pipeline.py), so this is the real behavioral guarantee
        # "disabled" provides.
        sources = {s.source_id: s for s in load_active_sources()}
        assert "jointheleague" not in sources

    def test_no_invalid_source_config_raised_loading_the_real_registry(self):
        # SUC-003's precondition: registry/sources/jointheleague.toml is
        # registered and loads with no InvalidSourceConfig -- proven
        # simply by load_sources() completing and including it
        # (InvalidSourceConfig would have been logged-and-skipped, not
        # raised, so the real assertion is presence, matching this
        # class's other tests).
        sources = {s.source_id: s for s in load_sources()}
        assert "jointheleague" in sources


class TestRealLeagueSyncSource:
    """The real leaguesync.toml source (OOP, 2026-07-20): the League's own
    sync.jtlapp.net query API, now authoritative for League classes +
    free tech clubs -- see registry/sources/leaguesync.toml.
    """

    def test_loads_as_enabled_leaguesync_source(self):
        sources = {s.source_id: s for s in load_active_sources()}

        leaguesync = sources["leaguesync"]
        assert leaguesync.org_name == "The LEAGUE of Amazing Programmers"
        assert leaguesync.adapter_type == "leaguesync"
        assert leaguesync.enabled is True

    def test_config_matches_live_confirmed_api_base(self):
        sources = {s.source_id: s for s in load_active_sources()}

        leaguesync = sources["leaguesync"]
        assert leaguesync.config["api_base"] == "https://sync.jtlapp.net"


class TestRealCompanySeedSources:
    """The four real company sources (ticket 006, SUC-007): three
    Greenhouse-backed, one Lever-backed -- ``ADAPTERS`` resolution and
    config-key correctness proven via ``SourceConfig.from_toml`` +
    ``load_active_sources()``, entirely offline (no network call)."""

    def test_three_greenhouse_and_one_lever_company_source_are_enabled(self):
        sources = {s.source_id: s for s in load_active_sources()}

        boundlessbio = sources["boundlessbio"]
        assert boundlessbio.org_name == "Boundless Bio"
        assert boundlessbio.adapter_type == "greenhouse"
        assert boundlessbio.enabled is True

        gossamerbio = sources["gossamerbio"]
        assert gossamerbio.org_name == "Gossamer Bio"
        assert gossamerbio.adapter_type == "greenhouse"
        assert gossamerbio.enabled is True

        elementbiosciences = sources["elementbiosciences"]
        assert elementbiosciences.org_name == "Element Biosciences"
        assert elementbiosciences.adapter_type == "greenhouse"
        assert elementbiosciences.enabled is True

        shieldai = sources["shieldai"]
        assert shieldai.org_name == "Shield AI"
        assert shieldai.adapter_type == "lever"
        assert shieldai.enabled is True

    def test_greenhouse_sources_carry_the_confirmed_live_board_tokens(self):
        sources = {s.source_id: s for s in load_active_sources()}

        assert sources["boundlessbio"].config["board_token"] == "boundlessbio"
        assert sources["gossamerbio"].config["board_token"] == "gossamerbio"
        assert (
            sources["elementbiosciences"].config["board_token"] == "elementbiosciences"
        )

    def test_lever_source_carries_the_confirmed_live_company_slug(self):
        sources = {s.source_id: s for s in load_active_sources()}
        assert sources["shieldai"].config["company"] == "shieldai"

    def test_la_jolla_san_diego_mixed_boards_override_location_keywords(self):
        # Boundless Bio and Element Biosciences are both La Jolla/San
        # Diego -- the default ["San Diego"] substring match alone would
        # miss a posting whose ATS location text reads "La Jolla, CA".
        sources = {s.source_id: s for s in load_active_sources()}

        assert sources["boundlessbio"].config["location_keywords"] == [
            "San Diego",
            "La Jolla",
        ]
        assert sources["elementbiosciences"].config["location_keywords"] == [
            "San Diego",
            "La Jolla",
        ]

    def test_gossamerbio_and_shieldai_use_the_default_location_keywords(self):
        # Every posting observed live during planning was already
        # labeled "San Diego" -- no override needed, matching
        # ats_filters.DEFAULT_LOCATION_KEYWORDS (["San Diego"]).
        sources = {s.source_id: s for s in load_active_sources()}

        assert "location_keywords" not in sources["gossamerbio"].config
        assert "location_keywords" not in sources["shieldai"].config

    def test_each_source_records_how_and_when_it_was_verified_live(self):
        # Mirrors sprint 005's discovered_via convention (this ticket's
        # Acceptance Criteria).
        sources = {s.source_id: s for s in load_active_sources()}

        for source_id in ("boundlessbio", "gossamerbio", "elementbiosciences", "shieldai"):
            discovered_via = sources[source_id].acquisition_policy["discovered_via"]
            assert "sprint 006 planning" in discovered_via

    def test_boundless_bio_is_enabled_despite_zero_open_postings_at_planning_time(self):
        # SUC-007's own Acceptance Criteria: a company with zero
        # currently-open matching postings is registered and enabled
        # anyway -- a legitimate zero-result state, not an error.
        sources = {s.source_id: s for s in load_active_sources()}
        assert sources["boundlessbio"].enabled is True


class TestProgramPageSourceConfig:
    """Sprint 027 ticket 005's own Testing requirement: prove a
    ``program_page``-typed TOML with ``config.program_kind`` parses into a
    ``SourceConfig`` correctly. No new loader code is expected -- this
    verifies the existing untyped-``config``-dict mechanism already
    handles the new ``adapter_type`` value, per ``registry/DESIGN.md``'s
    sprint 027 addendum.
    """

    def test_parses_program_page_fixture(self):
        # Lives in its own sibling fixtures directory, not FIXTURES_DIR
        # itself, so it doesn't perturb TestLoadSources's fixed file
        # count for that directory (matching the existing
        # registry_fetch_strategy/ subdirectory's precedent).
        source = SourceConfig.from_toml(
            FIXTURES_DIR.parent / "registry_program_page" / "program_page_good.toml"
        )

        assert source.adapter_type == "program_page"
        assert source.org_name == "Fixture Program Page Org"
        assert source.enabled is True
        assert source.config == {
            "url": "https://example.org/programs/fixture-scholars",
            "program_kind": "internship",
        }
        assert source.taxonomy_defaults == {"eligibility": "Fixture partner schools only"}

    def test_real_registry_registers_program_page_sources_for_issue_28(self):
        # Sprint 027 ticket 005: at least the majority of issue 28's ~13
        # individually-named HS internship/research program pages
        # (excluding the 3 UCSD-listing-covered programs reconciled to
        # ticket 006, and the Illumina/SD2 "closed pipeline" -- neither
        # registered here) are live-verified and enabled = true in the
        # real registry.
        sources = {s.source_id: s for s in load_sources()}

        enabled_program_pages = [
            source_id
            for source_id, source in sources.items()
            if source.adapter_type == "program_page" and source.enabled
        ]
        # 10 of the ~13 named programs are enabled = true (3 disabled
        # with a live-verification-failure reason: noaa-hutton,
        # sdzwa-internquest, scripps-reach) -- comfortably a majority.
        assert len(enabled_program_pages) >= 7

        for source_id in (
            "salk-heithoff-brody",
            "sdsc-rehs",
            "sbp-spark",
            "lji-ljidea",
            "scripps-srti",
            "niwc-seap",
            "niwc-nreip",
            "sdzwa-fellowships",
            "sdsu-expandai-robotics",
            "biocom-generation-steam",
        ):
            assert sources[source_id].adapter_type == "program_page"
            assert sources[source_id].config["program_kind"] == "internship"
            assert sources[source_id].enabled is True

    def test_disabled_program_pages_carry_a_reason_comment(self):
        # This ticket's Fix shape step 3: a page that failed live
        # verification is registered enabled = false with a reason
        # comment, not silently dropped.
        for source_id in ("noaa-hutton", "sdzwa-internquest", "scripps-reach"):
            path = DEFAULT_SOURCES_DIR / f"{source_id}.toml"
            source = SourceConfig.from_toml(path)
            assert source.adapter_type == "program_page"
            assert source.enabled is False
            assert "disabled:" in path.read_text()

    def test_scripps_reach_eligibility_override_names_partner_schools(self):
        # A fixed institutional fact (partner-schools-only) is
        # hand-authored via taxonomy_defaults.eligibility rather than
        # left to LLM inference -- this ticket's Fix shape step 1.
        source = SourceConfig.from_toml(DEFAULT_SOURCES_DIR / "scripps-reach.toml")
        assert "partner schools only" in source.taxonomy_defaults["eligibility"].lower()

    def test_ucsd_enlace_not_registered_as_an_individual_program_page(self):
        # Reconciliation with ticket 006 (this ticket's Description,
        # revised by ticket 006's own live verification -- see this
        # ticket's Notes "UPDATE" entry): ENLACE's own UCSD Summer
        # Program Finder card links to a page that extracts well
        # (a real inline deadline/eligibility), so it stays registered
        # via the listing source only, never as an individual
        # program_page here, to avoid duplicate-publishing a kind that
        # bypasses cross-source dedup. COSMOS and OPTIMUS are the
        # opposite case -- see
        # test_ucsd_cosmos_and_optimus_registered_individually_not_via_listing
        # below.
        sources = {s.source_id: s for s in load_sources()}
        for source_id in sources:
            assert "enlace" not in source_id.lower()

    def test_ucsd_cosmos_and_optimus_registered_individually_not_via_listing(self):
        # Sprint 027 ticket 006's own live verification found COSMOS's
        # and OPTIMUS's UCSD Summer Program Finder cards link to pages
        # that extract poorly (no deadline/eligibility recoverable) --
        # ticket 005's Description's own Fix shape step 4 reopens the
        # listing-only decision for exactly this case. Both are
        # registered individually instead, and the listing's own
        # link_selector excludes their card hrefs so neither is
        # double-published between the two sources.
        sources = {s.source_id: s for s in load_sources()}

        assert "ucsd-cosmos" in sources
        cosmos = sources["ucsd-cosmos"]
        assert cosmos.adapter_type == "program_page"
        assert cosmos.config["program_kind"] == "internship"
        assert cosmos.enabled is True

        assert "ucsd-optimus" in sources
        optimus = sources["ucsd-optimus"]
        assert optimus.adapter_type == "program_page"
        assert optimus.config["program_kind"] == "internship"
        # Even OPTIMUS's own best-reachable live page yielded a title
        # only (no deadline, no eligibility) -- disabled with a reason
        # comment, matching the registry's disabled-with-reason
        # convention, rather than publishing a near-empty record.
        assert optimus.enabled is False
        optimus_path = DEFAULT_SOURCES_DIR / "ucsd-optimus.toml"
        assert "disabled:" in optimus_path.read_text()

        listing = sources["ucsd-summer-program-finder"]
        link_selector = listing.config["link_selector"]
        assert "cosmos" in link_selector.lower()
        assert "moorescancercenter" in link_selector.lower()

    def test_illumina_sd2_not_registered(self):
        # Issue 28 names Illumina/SD2 STEM Scholars as a "closed
        # pipeline" -- this ticket's investigation (see its Notes)
        # found no live, public application page to register at all,
        # so it is not registered as a program_page source (or any
        # other adapter_type).
        sources = {s.source_id: s for s in load_sources()}
        for source_id in sources:
            lowered = source_id.lower()
            assert "illumina" not in lowered
            assert "sd2" not in lowered

    def test_sd_foundation_community_scholarship_registered_as_funding_opportunities(
        self,
    ):
        # Sprint 027 ticket 007 (SUC-035): the SD Foundation Community
        # Scholarship is this sprint's one deliberate non-internship
        # program_kind="program" registration, with opportunity_type
        # fixed to "Funding Opportunities" via a config override (an
        # operator-curated known fact, not left to LLM classification --
        # see adapters/program_page.py's opportunity_type_override
        # handling, generically fixture-tested by ticket 003's
        # test_program_kind_program_with_opportunity_type_override).
        #
        # Sprint 027 ticket 007's live verification found every page
        # probed on sdfoundation.org -- including this registered URL --
        # measures 840KB-965KB of raw HTML, which alone exceeded the
        # LLM's 200K-token context window (600K+ tokens measured), so
        # extract_program() always raised BadRequestError and the source
        # always yielded zero events. Registered enabled=false with a
        # reason comment (this registry's disabled-with-reason
        # convention) rather than left disabled with no explanation, so
        # the config (program_kind/opportunity_type) was preserved for a
        # future HTML-reduction capability to pick back up.
        #
        # Sprint 028 ticket 002 (issue 36, SUC-037) is that pickup: with
        # `extract.reduce_html_to_text()` (ticket 001) now wired into
        # `adapters/program_page.py`, a live
        # `discover()->fetch()->extract()` re-run against the real page
        # (a real `AnthropicProgramLLMClient`) succeeded -- one `Event`
        # with a non-empty title, eligibility, cost, and
        # `opportunity_type = "Funding Opportunities"`, no exception.
        # `enabled` flipped back to `true`.
        sources = {s.source_id: s for s in load_sources()}

        assert "sd-foundation-community-scholarship" in sources
        source = sources["sd-foundation-community-scholarship"]
        assert source.adapter_type == "program_page"
        assert source.config["program_kind"] == "program"
        assert source.config["opportunity_type"] == "Funding Opportunities"
        assert source.enabled is True

        path = DEFAULT_SOURCES_DIR / "sd-foundation-community-scholarship.toml"
        assert "RE-ENABLED" in path.read_text()


class TestProgramListingAndMultiSourceConfig:
    """Sprint 027 ticket 006's own Testing requirement: prove a
    ``program_listing``-typed TOML with ``config.link_selector`` and a
    ``program_page_multi``-typed TOML with ``config.program_kind`` both
    parse into a ``SourceConfig`` correctly. No new loader code is
    expected for either -- both are ordinary registry data under the
    existing untyped-``config``-dict mechanism (registry/DESIGN.md's
    ticket 006 exception-revision addendum).
    """

    def test_parses_program_listing_fixture_with_link_selector(self):
        # Own sibling fixtures directory, matching
        # TestProgramPageSourceConfig's precedent, so it doesn't perturb
        # TestLoadSources's fixed file count for the shared registry/
        # fixtures directory.
        source = SourceConfig.from_toml(
            FIXTURES_DIR.parent / "registry_program_listing" / "program_listing_good.toml"
        )

        assert source.adapter_type == "program_listing"
        assert source.org_name == "Fixture Program Listing Org"
        assert source.enabled is True
        assert source.config == {
            "site_url": "https://example.org",
            "listing_urls": ["/finder"],
            "program_kind": "internship",
            "link_selector": 'li[data-grade*="High School"] a.learnmore',
        }

    def test_parses_program_page_multi_fixture(self):
        source = SourceConfig.from_toml(
            FIXTURES_DIR.parent / "registry_program_page_multi" / "program_page_multi_good.toml"
        )

        assert source.adapter_type == "program_page_multi"
        assert source.org_name == "Fixture Program Page Multi Org"
        assert source.enabled is True
        assert source.config == {
            "url": "https://example.org/education/research-internships",
            "program_kind": "internship",
        }

    def test_real_registry_registers_ucsd_listing_and_sio_multi_sources(self):
        # Sprint 027 ticket 006: the UCSD Summer Program Finder
        # (program_listing, config.link_selector) and the SIO
        # research-internships page (program_page_multi) are both
        # registered, enabled, and share kind="internship" per ticket
        # 005's Architecture rationale.
        sources = {s.source_id: s for s in load_sources()}

        assert "ucsd-summer-program-finder" in sources
        listing = sources["ucsd-summer-program-finder"]
        assert listing.adapter_type == "program_listing"
        assert listing.enabled is True
        assert listing.config["program_kind"] == "internship"
        assert listing.config["site_url"] == "https://summer.ucsd.edu"
        assert "link_selector" in listing.config
        assert "High School" in listing.config["link_selector"]

        assert "sio-research-internships" in sources
        sio = sources["sio-research-internships"]
        assert sio.adapter_type == "program_page_multi"
        assert sio.enabled is True
        assert sio.config["program_kind"] == "internship"
        assert sio.config["url"] == "https://scripps.ucsd.edu/education/research-internships"


class TestCampMarketingPageProviders:
    """Sprint 028 ticket 004 (issue 29, SUC-038/SUC-041): the verified
    nonprofit/institutional camp marketing-page providers, each
    registered as a ``program_page``/``program_page_multi`` source with
    ``config.opportunity_type = "Camps"`` -- the same operator-curated-
    override convention ``sd-foundation-community-scholarship.toml``
    already established for ``"Funding Opportunities"``. No new loader
    code: every value here is ordinary registry data under the existing
    untyped-``config``-dict mechanism.
    """

    #: (source_id, org_name substring) for every enabled=true Camps
    #: source this ticket registers.
    _ENABLED_CAMPS_SOURCES = [
        "sd-zoo-classic-camp-kindergarten",
        "sd-zoo-classic-camp-first-grade",
        "sd-zoo-classic-camp-second-grade",
        "sd-zoo-classic-camp-third-grade",
        "sd-zoo-classic-camp-fourth-fifth-grade",
        "sd-zoo-classic-camp-sixth-ninth-grade",
        "sd-zoo-little-artists-camp",
        "sd-zoo-animal-art-explorers-camp",
        "sd-zoo-adventures-art-camp",
        "living-coast-camps",
        "eisca-camps",
        "sd-model-railroad-museum-camps",
        "cmod-summer-camp",
        "birch-aquarium-summer-camps",
        "fleet-science-center-camps",
    ]

    #: (source_id, reason substring expected in the file's disabled
    #: comment) for every enabled=false Camps source this ticket
    #: registers -- sprint 027 tickets 005/006's disabled-with-reason
    #: precedent.
    _DISABLED_CAMPS_SOURCES = [
        "coastal-roots-farm-camp",
        "camp-invention-morning-creek",
        "southwestern-college-yes-academy",
    ]

    def test_every_enabled_camps_source_is_registered_as_program_page_family(self):
        sources = {s.source_id: s for s in load_sources()}

        for source_id in self._ENABLED_CAMPS_SOURCES:
            assert source_id in sources, f"{source_id} not registered"
            source = sources[source_id]
            assert source.adapter_type in ("program_page", "program_page_multi")
            assert source.config["program_kind"] == "program"
            assert source.config["opportunity_type"] == "Camps"
            assert source.enabled is True

    def test_every_disabled_camps_source_has_a_documented_reason(self):
        sources = {s.source_id: s for s in load_sources()}

        for source_id in self._DISABLED_CAMPS_SOURCES:
            assert source_id in sources, f"{source_id} not registered"
            source = sources[source_id]
            assert source.adapter_type in ("program_page", "program_page_multi")
            assert source.config["opportunity_type"] == "Camps"
            assert source.enabled is False

            path = DEFAULT_SOURCES_DIR / f"{source_id}.toml"
            assert "disabled:" in path.read_text()

    def test_enabled_and_disabled_sets_together_cover_every_registered_camps_source(self):
        # Belt-and-suspenders against a source silently falling through
        # both lists above (neither enabled nor accounted-for-disabled).
        sources = load_sources()
        camps_sources = {
            s.source_id
            for s in sources
            if s.config.get("opportunity_type") == "Camps"
        }

        assert camps_sources == set(self._ENABLED_CAMPS_SOURCES) | set(
            self._DISABLED_CAMPS_SOURCES
        )

    def test_sd_zoo_nine_program_pages_each_point_at_their_own_kids_programs_url(self):
        sources = {s.source_id: s for s in load_sources()}
        zoo_source_ids = [s for s in self._ENABLED_CAMPS_SOURCES if s.startswith("sd-zoo-")]

        assert len(zoo_source_ids) == 9
        urls = {sources[s].config["url"] for s in zoo_source_ids}
        assert len(urls) == 9  # nine distinct per-program pages, no accidental duplicate
        assert all(url.startswith("https://zoo.sandiegozoo.org/kids-programs/") for url in urls)

    def test_fleet_is_registered_enabled_true_year_round(self):
        # SUC-040: Fleet's in-season-only marketing page must not be
        # gated behind enabled=false pending "season" -- the existing
        # weekly cron plus the empty-list-is-valid prompt handling
        # (ticket 003) is the deliberate substitute for a seasonal-
        # recheck subsystem.
        sources = {s.source_id: s for s in load_sources()}

        fleet = sources["fleet-science-center-camps"]
        assert fleet.enabled is True
        assert fleet.config["url"] == "https://www.fleetscience.org/events/camps"

    def test_sd_model_railroad_museum_is_the_sold_out_target(self):
        sources = {s.source_id: s for s in load_sources()}

        sdmrm = sources["sd-model-railroad-museum-camps"]
        assert sdmrm.enabled is True
        assert sdmrm.config["url"] == "https://www.sdmrm.org/summer-camps"

    def test_camp_galileo_sd_is_not_registered(self):
        # Commercial-chain scope exclusion (sprint.md's "Camp Galileo
        # tension") -- Camp Galileo SD appears in issue 29's own
        # marketing-page list but is the commercial "Galileo" studio
        # brand named in the roadmap's commercial-chain exclusion list,
        # so it must never appear in registry/sources/ under any name.
        sources = {s.source_id: s for s in load_sources()}

        for source_id, source in sources.items():
            assert "galileo" not in source_id.lower()
            assert "galileo" not in source.org_name.lower()

    def test_air_and_space_museum_and_helen_woodward_have_no_marketing_page_entry(self):
        # SUC-041/SUC-042: both orgs are registered only via the
        # activenet_camps adapter (ticket 005), never also as a
        # program_page/program_page_multi marketing-page source, to
        # avoid the dual-registration risk adapters/DESIGN.md documents
        # (the sprint 027 COSMOS/OPTIMUS/ENLACE pattern, applied here).
        sources = load_sources()

        for source in sources:
            org_lower = source.org_name.lower()
            is_marketing_page = source.adapter_type in ("program_page", "program_page_multi")
            if "air" in org_lower and "space" in org_lower:
                assert not is_marketing_page, (
                    f"{source.source_id} registers Air & Space Museum via a marketing page"
                )
            if "helen woodward" in org_lower or "woodward" in org_lower:
                assert not is_marketing_page, (
                    f"{source.source_id} registers Helen Woodward via a marketing page"
                )
