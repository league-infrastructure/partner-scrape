"""Tests for partner_scrape.teams.sources.static_roster: the FLL
static-roster TeamSource.

Unlike ftcscout.py/tba.py's tests, most of this module drives
``StaticRosterSource`` against the **real, committed roster**
(``partner_scrape/teams/data/fll-sd-teams.tsv``, exposed here as
``DEFAULT_ROSTER_PATH``) rather than a copied-in fixture -- per the
sprint 011 ticket-011-003 lesson (a hand-authored fixture that didn't
match the real API shipped an undetected defect for a full ticket),
this is the strongest possible form of "a direct excerpt of the real
committed roster's rows": it *is* the file, not a copy that could
silently drift from it. ``fll_roster_malformed.tsv`` under
``tests/fixtures/teams/`` is hand-authored (the real 48-row roster has
no malformed rows) to exercise per-row error isolation, matching
``ftcscout_search_malformed.json``'s precedent.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.registry.loader import load_active_sources
from partner_scrape.registry.schema import SourceConfig
from partner_scrape.teams.sources.base import RawTeamResponse, TeamRef, run
from partner_scrape.teams.sources.static_roster import (
    DEFAULT_DATA_DIR,
    DEFAULT_ROSTER_PATH,
    PROGRAM_BY_RAW,
    StaticRosterSource,
    _extract_one,
    _map_organization,
    _parse_area,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "teams"
TEAMS_REGISTRY_DIR = (
    Path(__file__).resolve().parents[2] / "partner_scrape" / "teams" / "registry"
)

#: A loose but sufficient email-address pattern, matching every other
#: privacy regression test in this suite (e.g.
#: tests/teams/test_export.py).
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _real_source_config() -> SourceConfig:
    sources = load_active_sources(TEAMS_REGISTRY_DIR)
    matches = [s for s in sources if s.adapter_type == "static_roster"]
    assert len(matches) == 1, "expected exactly one static_roster registry entry"
    return matches[0]


class _NeverCalledFetcher:
    """`Fetcher` double that raises on any call -- proves
    `StaticRosterSource` never touches it, exercised through the full
    `sources.base.run()` chain (discover -> fetch -> extract), the
    "runtime-call assertion" precedent `teams/DESIGN.md`'s Constraints
    section describes as this module's counterpart to
    `test_sources_base.py`'s forbidden-import AST scan."""

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        raise AssertionError("StaticRosterSource must never call the injected Fetcher")


class TestNeverTouchesFetcher:
    def test_run_never_calls_fetcher_get(self):
        teams = run(_real_source_config(), StaticRosterSource(), _NeverCalledFetcher())
        assert len(teams) == 48


class TestDiscover:
    def test_discover_returns_a_local_path_not_a_url(self):
        refs = StaticRosterSource().discover(_real_source_config(), _NeverCalledFetcher())

        assert len(refs) == 1
        assert refs[0].url == str(DEFAULT_ROSTER_PATH)
        assert not refs[0].url.startswith("http")

    def test_discover_falls_back_to_default_roster_path_when_config_omits_it(self):
        source = SourceConfig(
            source_id="fll-sd", org_name="FLL", adapter_type="static_roster", config={}
        )

        refs = StaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs[0].url == str(DEFAULT_ROSTER_PATH)

    def test_discover_resolves_a_relative_roster_path_against_data_dir(self):
        source = SourceConfig(
            source_id="fll-sd",
            org_name="FLL",
            adapter_type="static_roster",
            config={"roster_path": "fll-sd-teams.tsv"},
        )

        refs = StaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs[0].url == str(DEFAULT_DATA_DIR / "fll-sd-teams.tsv")

    def test_discover_leaves_an_absolute_roster_path_untouched(self, tmp_path):
        absolute = tmp_path / "custom-roster.tsv"
        source = SourceConfig(
            source_id="fll-sd",
            org_name="FLL",
            adapter_type="static_roster",
            config={"roster_path": str(absolute)},
        )

        refs = StaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs[0].url == str(absolute)


class TestFetch:
    def test_fetch_reads_the_file_directly_ignoring_fetcher(self):
        ref = TeamRef(url=str(DEFAULT_ROSTER_PATH))

        raw = StaticRosterSource().fetch(ref, _NeverCalledFetcher())

        assert raw.status == 200
        assert "Meeps" in raw.body

    def test_fetch_raises_for_a_missing_file(self, tmp_path):
        ref = TeamRef(url=str(tmp_path / "does-not-exist.tsv"))

        with pytest.raises(OSError):
            StaticRosterSource().fetch(ref, _NeverCalledFetcher())


class TestExtractAgainstTheRealRoster:
    """Drives extract() against the real, committed 48-row roster (via
    the full sources.base.run() chain) -- see this module's own
    docstring for why this is the strongest available fixture."""

    def _real_teams(self):
        return run(_real_source_config(), StaticRosterSource(), _NeverCalledFetcher())

    def test_extracts_exactly_48_teams(self):
        assert len(self._real_teams()) == 48

    def test_every_team_is_fll_league(self):
        assert all(t.league == "FLL" for t in self._real_teams())

    def test_program_split_matches_the_roster_breakdown(self):
        teams = self._real_teams()

        challenge = [t for t in teams if t.program == PROGRAM_BY_RAW["Challenge"]]
        explore = [t for t in teams if t.program == PROGRAM_BY_RAW["Explore"]]

        # Roster breakdown: "FLL Challenge (grades 4-8) 32, FLL Explore
        # (grades 2-4) 16" -- the upstream export's own tally.
        assert len(challenge) == 32
        assert len(explore) == 16

    def test_32_family_community_teams_have_empty_organization(self):
        teams = self._real_teams()

        family = [t for t in teams if t.org_type == "family_community"]

        # Roster breakdown: "Family/Community 32" -- the 28 pure home
        # teams plus 4 sponsor-backed-but-no-school teams (Apple, DoD
        # STEM, Qualcomm, and the bare "& Family/Community" artifact),
        # all correctly mapped to the same "never group" bucket.
        assert len(family) == 32
        assert all(t.organization == "" for t in family)
        assert all(t.sponsors == [] for t in family)

    def test_a_school_affiliated_team_carries_its_real_school_name(self):
        by_id = {t.team_id: t for t in self._real_teams()}

        carmel_del_mar = by_id["fll-74482"]

        assert carmel_del_mar.organization == "Carmel Del Mar Elementary"
        assert carmel_del_mar.org_type == "school"
        assert carmel_del_mar.name == "Diggin' Dynamos"
        assert carmel_del_mar.city == "Carmel Valley"
        assert carmel_del_mar.postal_code == "92130"

    def test_the_leading_ampersand_artifact_still_maps_to_family_community(self):
        # Team 29255 "Meeps": upstream organization cell is the bare
        # artifact "& Family/Community" -- no sponsor name at all.
        by_id = {t.team_id: t for t in self._real_teams()}

        meeps = by_id["fll-29255"]

        assert meeps.organization == ""
        assert meeps.org_type == "family_community"

    def test_a_sponsor_backed_home_team_also_maps_to_family_community(self):
        # Team 71667 "We Dig Legos": "Apple & Family/Community" -- a
        # real sponsor name, but still no sponsoring SCHOOL.
        by_id = {t.team_id: t for t in self._real_teams()}

        team = by_id["fll-71667"]

        assert team.organization == ""
        assert team.org_type == "family_community"

    def test_team_ids_are_unique(self):
        ids = [t.team_id for t in self._real_teams()]

        assert len(ids) == len(set(ids))
        assert all(tid.startswith("fll-") for tid in ids)

    def test_no_source_sets_location_precision_or_coordinates(self):
        # AC: static_roster.py never sets latitude/longitude/
        # location_precision itself -- that stays geocode_teams()'s job,
        # run after this source the same way it runs after
        # FTCScout/TBA.
        for team in self._real_teams():
            assert team.location_precision == "none"
            assert team.latitude is None
            assert team.longitude is None
            assert team.matched_name == ""
            assert team.needs_review is False

    def test_sources_field_records_static_roster_provenance(self):
        for team in self._real_teams():
            assert team.sources == ["static_roster"]

    def test_no_field_on_any_team_contains_an_email_address_pattern(self):
        # Defense in depth on top of "the committed file has no contact
        # column at all" -- see this module's own docstring.
        for team in self._real_teams():
            values = (
                team.team_id,
                team.league,
                team.program,
                team.name,
                team.organization,
                team.city,
                team.postal_code,
                team.matched_name,
            )
            for value in values:
                assert not _EMAIL_PATTERN.search(value or "")


class TestMalformedRowIsolation:
    """`fll_roster_malformed.tsv` (hand-authored -- the real 48-row
    roster has no malformed rows) carries three broken rows (no number,
    no name, an unrecognized program) plus one good row, matching
    `ftcscout_search_malformed.json`'s precedent for exercising
    per-record error isolation."""

    def test_malformed_rows_are_skipped_and_logged_not_raised(self, caplog):
        body = (FIXTURES_DIR / "fll_roster_malformed.tsv").read_text()
        ref = TeamRef(url="fll_roster_malformed.tsv")
        raw = RawTeamResponse(ref=ref, status=200, body=body)

        teams = StaticRosterSource().extract(raw, _real_source_config())

        assert len(teams) == 1
        assert teams[0].team_id == "fll-12345"
        assert teams[0].name == "Good Row"


class TestMapOrganization:
    def test_plain_family_community_maps_to_empty_organization(self):
        assert _map_organization("Family/Community") == ("", "family_community")

    def test_leading_ampersand_artifact_maps_to_empty_organization(self):
        assert _map_organization("& Family/Community") == ("", "family_community")

    def test_sponsor_prefixed_family_community_maps_to_empty_organization(self):
        assert _map_organization("Apple & Family/Community") == ("", "family_community")
        assert _map_organization(
            "DoD STEM & Family/Community & Raise the Bar Robotics"
        ) == ("", "family_community")

    def test_a_real_school_name_maps_to_school(self):
        assert _map_organization("Carmel Del Mar Elementary") == (
            "Carmel Del Mar Elementary",
            "school",
        )

    def test_an_empty_cell_maps_to_unknown(self):
        assert _map_organization("") == ("", "unknown")
        assert _map_organization("   ") == ("", "unknown")


class TestParseArea:
    """Every real shape observed in the upstream roster's "Area /
    Neighborhood" column -- see sources/static_roster.py's own
    docstring for the full accounting of this "known dirt"."""

    def test_clean_city_and_zip(self):
        assert _parse_area("Carmel Valley (92130)") == ("Carmel Valley", "92130")

    def test_home_team_disclaimer_has_no_zip(self):
        assert _parse_area("San Diego (home team — not published)") == ("San Diego", "")

    def test_sponsor_backed_disclaimer_has_no_zip(self):
        assert _parse_area("San Diego (home / sponsor-backed)") == ("San Diego", "")

    def test_multi_site_slash_zip_shorthand_is_ambiguous_no_zip(self):
        # "92130/75" is shorthand for two different ZIPs (92130, 92075)
        # -- never guessed, and the first named place wins for city.
        assert _parse_area("Carmel Valley / Solana Beach (92130/75)") == (
            "Carmel Valley",
            "",
        )

    def test_multi_site_slash_single_zip_is_unambiguous(self):
        assert _parse_area("Santaluz / PHR (92127)") == ("Santaluz", "92127")

    def test_multi_site_plus_two_zips_no_parens_is_ambiguous_no_zip(self):
        # Autra Academy's two campuses -- the one roster row with no
        # parenthetical at all.
        assert _parse_area("Carmel Valley 92130 + La Jolla 92037") == (
            "Carmel Valley",
            "",
        )

    def test_empty_cell(self):
        assert _parse_area("") == ("", "")
        assert _parse_area("   ") == ("", "")


class TestExtractOne:
    def test_unrecognized_program_raises_value_error(self):
        with pytest.raises(ValueError, match="unrecognized program"):
            _extract_one(
                {
                    "number": "12345",
                    "name": "Some Team",
                    "program": "Regional",
                    "organization": "Family/Community",
                    "area": "San Diego (home team — not published)",
                    "district": "—",
                }
            )

    def test_non_numeric_number_raises_value_error(self):
        with pytest.raises(ValueError, match="no usable number or name"):
            _extract_one(
                {
                    "number": "not-a-number",
                    "name": "Some Team",
                    "program": "Challenge",
                    "organization": "Family/Community",
                    "area": "San Diego (home team — not published)",
                    "district": "—",
                }
            )

    def test_blank_name_raises_value_error(self):
        with pytest.raises(ValueError, match="no usable number or name"):
            _extract_one(
                {
                    "number": "12345",
                    "name": "  ",
                    "program": "Challenge",
                    "organization": "Family/Community",
                    "area": "San Diego (home team — not published)",
                    "district": "—",
                }
            )


class TestRegistryConfig:
    """AC: partner_scrape/teams/registry/fll-sd.toml registers the
    static_roster source, reusing registry.schema.SourceConfig /
    registry.loader.load_active_sources verbatim (no new schema)."""

    def test_fll_sd_toml_loads_via_load_active_sources(self):
        source = _real_source_config()

        assert source.source_id == "fll-sd"
        assert source.adapter_type == "static_roster"
        assert source.enabled is True
        assert source.config.get("sunset_season") == "2026-27"

    def test_loaded_source_config_drives_discover_to_the_real_roster_file(self):
        source = _real_source_config()

        refs = StaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs == [TeamRef(url=str(DEFAULT_ROSTER_PATH))]
