"""Tests for partner_scrape.teams.pipeline: `run_teams()`'s
Registry -> TeamSource(s) -> merge_teams() -> export_teams() sequencing.

Drives the real Team Registry seed (`partner_scrape/teams/registry/
ftc-sd.toml` + `frc-sd.toml` + `fll-sd.toml`, the same ones production
loads) through a fixture Fetcher returning the live-captured 152-team
FTCScout fixture and (ticket 011-003, reopened) a curated 7-team subset
of the live-captured TBA fixture (see `tests/teams/test_sources_tba.py`'s
module docstring for why 7, not the real 78) -- no test here opens a
real network socket, and no test relies on a synthetic registry
standing in for the real one (except the two tests that specifically
need an unrecognized/erroring source, which use their own small
fixture registries under `tests/fixtures/teams/`).

Sprint 012's `fll-sd.toml` is a third real, always-active registry
entry whose `StaticRosterSource` never touches the injected fetcher (it
reads the real, committed 48-team roster straight off disk -- see
`sources/static_roster.py`'s own module docstring), so it contributes
its 48 teams to *every* unfiltered `run_teams()` call in this file
regardless of what the fixture Fetcher registers or whether TBA
succeeds. Several tests below that predate sprint 012 either add an
explicit `source="ftcscout"` filter (where the point is FTCScout's
behavior specifically) or have their expected totals/`by_league`
updated to include the FLL roster's 48 -- see each affected test's own
comment for which.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pytest

from partner_scrape import config
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.fetch.robots import robots_txt_url
from partner_scrape.teams import pipeline as teams_pipeline
from partner_scrape.teams.model import Team
from partner_scrape.teams.pipeline import (
    DEFAULT_TEAMS_REGISTRY_DIR,
    _parse_sunset_season,
    run_teams,
)
from partner_scrape.teams.sources.base import RawTeamResponse, TeamRef
from partner_scrape.teams.sources.ftcscout import DEFAULT_API_BASE, DEFAULT_REGION, _search_url
from partner_scrape.teams.sources.tba import _status_url, _teams_page_url
from partner_scrape.teams.sponsor_cache import SponsorCache
from partner_scrape.teams.sponsor_llm import FixtureSponsorLLMClient, SponsorExtractionResult

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "teams"
SEARCH_URL = _search_url(DEFAULT_API_BASE, DEFAULT_REGION)
TBA_STATUS_URL = _status_url(config.DEFAULT_TBA_URL)
TBA_PAGE0_URL = _teams_page_url(config.DEFAULT_TBA_URL, 0)
TBA_PAGE1_URL = _teams_page_url(config.DEFAULT_TBA_URL, 1)


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


def _fixture_response(name: str, status: int = 200) -> FetchResponse:
    return FetchResponse(url="", status=status, headers={}, body=(FIXTURES_DIR / name).read_text())


def _tba_responses() -> dict[str, FetchResponse]:
    return {
        TBA_STATUS_URL: _fixture_response("tba_status.json"),
        TBA_PAGE0_URL: _fixture_response("tba_teams_page0.json"),
        TBA_PAGE1_URL: _fixture_response("tba_teams_page1.json"),
    }


def _ftc_and_tba_fetcher() -> FixtureFetcher:
    """Both real sources' responses in one Fetcher -- the real Team
    Registry (ftc-sd.toml + frc-sd.toml) drives both against it."""
    responses = {
        SEARCH_URL: _fixture_response("ftcscout_search.json"),
        **_tba_responses(),
    }
    return FixtureFetcher(responses)


def _make_site(root: Path) -> Path:
    (root / "src" / "data").mkdir(parents=True)
    return root


@pytest.fixture(autouse=True)
def _clean_tba_key_env(monkeypatch):
    """Every test in this module starts with `TBA_KEY` unset,
    regardless of the real ambient environment -- `TBA_KEY` is a real,
    working credential in this project's own `.env` (sprint.md's
    Migration Concerns), so without this a test run on a machine with
    that `.env` sourced could silently behave differently than one
    without it. Tests that need a valid key set it explicitly via
    `monkeypatch.setenv("TBA_KEY", ...)`."""
    monkeypatch.delenv("TBA_KEY", raising=False)


class TestEndToEndAgainstTheRealRegistry:
    """Exercises the actual seeded `ftc-sd.toml` (not a fixture
    stand-in) so drift in the real registry file is caught here too --
    matching `tests/teams/test_sources_ftcscout.py`'s
    `TestRegistryConfig` precedent of trusting the real registry file
    in tests.

    `TBA_KEY` is unset for every test below (see `_clean_tba_key_env`)
    -- the real registry also loads `frc-sd.toml` now (ticket 011-003),
    so these FTCScout-focused tests double as a first proof that an
    unset `TBA_KEY` degrades to FTC-only output with no TBA fetch
    attempted at all; `TestTbaFailureIsolation` below covers that
    explicitly and in more detail."""

    def test_dry_run_reports_152_teams_with_no_disk_write(self, tmp_path):
        fetcher = _ftcscout_fetcher()
        site = tmp_path / "stem-ecosystem"

        # source="ftcscout": the real registry also loads frc-sd.toml and
        # (sprint 012) fll-sd.toml now -- TBA is isolated by a missing
        # TBA_KEY (see _clean_tba_key_env above), but static_roster
        # never touches the fetcher at all and always succeeds, so an
        # unfiltered run here would also publish the FLL roster's 48
        # teams. This test's whole point is FTCScout's own behavior, so
        # it filters explicitly rather than absorbing a third source's
        # count into an assertion about FTCScout.
        payload = run_teams(source="ftcscout", site_dir=site, fetcher=fetcher, dry_run=True)

        assert payload["meta"]["total"] == 152
        assert len(payload["teams"]) == 152
        assert not site.exists()

    def test_dry_run_only_fetches_the_search_url_and_robots_txt_probes(self, tmp_path):
        # Pre-ticket-013-001 this asserted `fetcher.calls == [SEARCH_URL]`
        # exactly -- true when nothing downstream of acquisition ever
        # touched the network. Sprint 013 ticket 001 added
        # `verify_team_websites()`, wired unconditionally into
        # `run_teams()` after `apply_website_overrides()` (SUC-001's
        # Main Flow has no source-filter exception), so any team whose
        # `website` the ticket 006 overlay populated now gets its
        # robots.txt probed too -- this real, live-captured FTCScout
        # fixture includes such teams (teams/DESIGN.md's Orientation:
        # 29 FTC teams gained a website via the overlay). None of those
        # robots.txt URLs are in `_ftcscout_fetcher()`'s canned
        # `responses`, so each is caught by `verify_team_websites()`'s
        # own per-team exception isolation and marked "unverified" --
        # the "unreachable page," not "crash the run," outcome ticket
        # 001 designed for. This test's original intent -- no *real
        # page content* fetch beyond the FTCScout search endpoint --
        # still holds and is asserted directly below.
        fetcher = _ftcscout_fetcher()

        run_teams(site_dir=tmp_path, fetcher=fetcher, dry_run=True)

        assert SEARCH_URL in fetcher.calls
        assert all(
            call == SEARCH_URL or call.endswith("/robots.txt") for call in fetcher.calls
        )

    def test_real_run_writes_teams_json_to_site_dir(self, tmp_path):
        fetcher = _ftcscout_fetcher()
        site = _make_site(tmp_path)

        # source="ftcscout" -- see the dry-run test above for why: the
        # real registry's fll-sd.toml (sprint 012) always succeeds
        # regardless of this fixture Fetcher, so an unfiltered run would
        # also publish 48 FLL teams here.
        run_teams(source="ftcscout", site_dir=site, fetcher=fetcher, dry_run=False)

        written = json.loads((site / "src" / "data" / "teams.json").read_text())
        assert written["meta"]["total"] == 152
        assert written["meta"]["by_league"] == {"FTC": 152}
        assert written["meta"]["out_of_region"] == 6

    def test_source_filter_ftcscout_matches_the_real_registry_entry(self, tmp_path):
        fetcher = _ftcscout_fetcher()

        payload = run_teams(source="ftcscout", site_dir=tmp_path, fetcher=fetcher, dry_run=True)

        assert payload["meta"]["total"] == 152

    def test_source_filter_tba_matches_the_real_registry_entry(self, monkeypatch, tmp_path):
        # "tba" was the unregistered-adapter_type example this test
        # class used pre-ticket-011-003 (frc-sd.toml didn't exist yet)
        # -- now it is a real, registered source, so it gets its own
        # positive test here instead.
        monkeypatch.setenv("TBA_KEY", "fixture-test-key")
        fetcher = _ftc_and_tba_fetcher()

        payload = run_teams(source="tba", site_dir=tmp_path, fetcher=fetcher, dry_run=True)

        assert payload["meta"]["total"] == 7
        assert SEARCH_URL not in fetcher.calls  # the filtered-out source is never fetched

    def test_source_filter_for_an_unknown_source_yields_zero_teams(self, tmp_path):
        fetcher = _ftcscout_fetcher()

        payload = run_teams(source="seed", site_dir=tmp_path, fetcher=fetcher, dry_run=True)

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


class TestBothRealSourcesTogether:
    """AC: with TBA fixtures present, `teams.json` carries the fixture's
    7 FRC teams -- the real Team Registry (`ftc-sd.toml` + `frc-sd.toml`
    +, since sprint 012, `fll-sd.toml`) driven against both real fixture
    sets plus the real, committed 48-team FLL static roster in one run:
    207 total (152 FTC + 7 FRC fixture + 48 FLL -- `static_roster` never
    touches the fetcher, so it always contributes regardless of which
    fixtures this class's fetcher doubles register). (Ticket 011-003's
    original AC said 59 FRC/211 total -- that number came from a
    hand-authored fixture with an undetected state_prov bug; see
    `tests/teams/test_sources_tba.py`'s module docstring and this
    reopened ticket's own commit for why the fixture -- and this
    number -- changed. The real, live `partner-scrape teams` total is
    278 (152 FTC + 78 FRC + 48 FLL); see `sources/tba.py`'s and
    `sources/static_roster.py`'s module docstrings.)"""

    def test_207_teams_total_152_ftc_7_frc_48_fll(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TBA_KEY", "fixture-test-key")
        fetcher = _ftc_and_tba_fetcher()

        payload = run_teams(site_dir=tmp_path, fetcher=fetcher, dry_run=True)

        assert payload["meta"]["total"] == 207
        assert payload["meta"]["by_league"] == {"FTC": 152, "FRC": 7, "FLL": 48}
        assert len(payload["teams"]) == 207

    def test_merge_ran_canyon_crest_academy_links_across_leagues(self, monkeypatch, tmp_path):
        # Canyon Crest Academy: FTC 7159/9837/14425 (real fixture) and
        # FRC 3128 (real fixture) -- sprint.md's dual-program example.
        monkeypatch.setenv("TBA_KEY", "fixture-test-key")
        fetcher = _ftc_and_tba_fetcher()

        payload = run_teams(site_dir=tmp_path, fetcher=fetcher, dry_run=True)
        by_id = {t["team_id"]: t for t in payload["teams"]}

        cca_ids = {"ftc-7159", "ftc-9837", "ftc-14425", "frc-3128"}
        org_keys = {by_id[tid]["org_key"] for tid in cca_ids}
        assert org_keys != {""}
        assert len(org_keys) == 1
        assert set(by_id["frc-3128"]["sibling_team_ids"]) == cca_ids - {"frc-3128"}

    def test_poway_1622_links_but_stays_two_separate_records(self, monkeypatch, tmp_path):
        # FTC 1622 and FRC 1622 -- same org (Poway High School), same
        # number, but never fused into one record. (Poway High School
        # also fields a second FTC team, 20422 "Team Spyder Too", in
        # the real fixture -- so this is a 3-team sibling group, not a
        # pair; the point under test is that ftc-1622 and frc-1622
        # specifically remain separate records that reference each
        # other, not that Poway fields exactly two teams.)
        monkeypatch.setenv("TBA_KEY", "fixture-test-key")
        fetcher = _ftc_and_tba_fetcher()

        payload = run_teams(site_dir=tmp_path, fetcher=fetcher, dry_run=True)
        team_1622 = [t for t in payload["teams"] if t["number"] == 1622]

        assert len(team_1622) == 2
        by_id = {t["team_id"]: t for t in team_1622}
        assert set(by_id) == {"ftc-1622", "frc-1622"}
        assert by_id["ftc-1622"]["org_key"] == by_id["frc-1622"]["org_key"]
        assert "frc-1622" in by_id["ftc-1622"]["sibling_team_ids"]
        assert "ftc-1622" in by_id["frc-1622"]["sibling_team_ids"]
        assert "ftc-20422" in by_id["frc-1622"]["sibling_team_ids"]

    def test_family_community_teams_never_grouped_together(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TBA_KEY", "fixture-test-key")
        fetcher = _ftc_and_tba_fetcher()

        payload = run_teams(site_dir=tmp_path, fetcher=fetcher, dry_run=True)
        empty_org_teams = [t for t in payload["teams"] if t["organization"] == ""]

        # 58 FTC Family/Community teams + the FRC no-school-reported
        # teams in the TBA fixture all get org_key == "" and no
        # siblings, never fused into one giant bogus organization.
        assert len(empty_org_teams) >= 58
        assert all(t["org_key"] == "" for t in empty_org_teams)
        assert all(t["sibling_team_ids"] == [] for t in empty_org_teams)


class TestTbaFailureIsolation:
    """AC: a simulated `TBA_KEY`-missing or TBA-401 fixture run still
    publishes a `teams.json` carrying every *other* source that
    succeeded -- per-source isolation, not a whole-run failure
    (sprint.md's Migration Concerns; this ticket's own acceptance
    criteria). Since sprint 012, "every other source that succeeded"
    is FTCScout (152, via this class's fixture Fetcher) *and*
    `static_roster` (48, the real committed FLL roster -- it never
    touches the fetcher, so a TBA-only failure never isolates it):
    200 total, not 152. TBA remains the only source these tests make
    fail."""

    def test_missing_tba_key_still_publishes_ftc_and_fll_200_teams(self, monkeypatch, tmp_path):
        monkeypatch.delenv("TBA_KEY", raising=False)
        fetcher = _ftc_and_tba_fetcher()

        payload = run_teams(site_dir=tmp_path, fetcher=fetcher, dry_run=True)

        assert payload["meta"]["total"] == 200
        assert payload["meta"]["by_league"] == {"FTC": 152, "FLL": 48}
        assert all(t["league"] in ("FTC", "FLL") for t in payload["teams"])
        # The TBA status probe was never even attempted -- the missing
        # key is caught in _auth_headers() before any fetcher.get().
        assert TBA_STATUS_URL not in fetcher.calls

    def test_tba_401_still_publishes_ftc_and_fll_200_teams(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TBA_KEY", "fixture-test-key")
        fetcher = FixtureFetcher(
            {
                SEARCH_URL: _fixture_response("ftcscout_search.json"),
                TBA_STATUS_URL: FetchResponse(url="", status=401, headers={}, body="{}"),
            }
        )

        payload = run_teams(site_dir=tmp_path, fetcher=fetcher, dry_run=True)

        assert payload["meta"]["total"] == 200
        assert payload["meta"]["by_league"] == {"FTC": 152, "FLL": 48}

    def test_missing_tba_key_writes_a_valid_teams_json_to_disk(self, monkeypatch, tmp_path):
        # Not just dry_run -- confirm the degraded run still writes a
        # real, valid teams.json rather than nothing at all.
        monkeypatch.delenv("TBA_KEY", raising=False)
        fetcher = _ftc_and_tba_fetcher()
        site = _make_site(tmp_path)

        run_teams(site_dir=site, fetcher=fetcher, dry_run=False)

        written = json.loads((site / "src" / "data" / "teams.json").read_text())
        assert written["meta"]["total"] == 200
        assert written["meta"]["by_league"] == {"FTC": 152, "FLL": 48}


class TestGeocodingAggregateDistribution:
    """AC (ticket 011-004): "Write a test asserting the aggregate
    distribution so a silent regression in the matcher is caught."

    Runs the full pipeline (both real sources' fixtures, the real
    committed FLL static roster since sprint 012, real Team Registry,
    real committed `teams/geo.py` data files -- no `geo_data_dir`
    override) and asserts the precision distribution against
    *tolerant* bounds, not exact counts: `sd-schools-public.tsv`/
    `sd-schools-private.tsv` are refreshed yearly from CDE/NCES (see
    `dev/refresh_school_directories.py`), so a routine data refresh
    that shifts a handful of matches must not fail this test -- only a
    genuinely broken matcher (e.g. the ladder resolving almost nothing,
    or every match suddenly needing review) should. Measured at ticket
    011-004's own build (2026-08-28) against the original 211-team
    corpus: 129 school (79 FTC + 50 FRC), 8 zip, 70 city, 4 none, 14
    needs_review, 6 out_of_region. Re-measured against ticket 011-003's
    reopened, corrected-fixture 159-team corpus (2026-08-28): 83 school
    (79 FTC + 4 FRC), 3 zip, 69 city, 4 none, 6 needs_review, 6
    out_of_region. Re-measured again (sprint 012, adding the real
    48-team FLL static roster -- 6 school, 7 zip, 35 city, 0 none, 0
    needs_review, 0 out_of_region, all measured against the real
    committed `fll-sd-teams.tsv` and `teams/geo.py` data): 207 total,
    89 school, 10 zip, 104 city, 4 none, 6 needs_review, 6 out_of_region
    (out_of_region comes entirely from `sources.ftcscout.
    OUT_OF_REGION_CITIES`, unaffected by either the TBA fix or the FLL
    static roster).
    """

    def test_precision_distribution_stays_within_expected_bounds(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TBA_KEY", "fixture-test-key")
        fetcher = _ftc_and_tba_fetcher()

        payload = run_teams(site_dir=tmp_path, fetcher=fetcher, dry_run=True)

        assert payload["meta"]["total"] == 207
        by_precision = payload["meta"]["by_location_precision"]

        # School precision is the ladder's top rungs (overrides + exact
        # + fuzzy CDE/NCES match) -- measured 89 at this build; a
        # healthy matcher should clear 65.
        assert by_precision.get("school", 0) >= 65
        # Every team should resolve to at least a city, except the
        # handful of genuinely out-of-region/foreign/ambiguous ones
        # (Ensenada x2, plus ambiguous "San Antonio"/"Louisville") --
        # "none" must stay a small residue, not a large fraction.
        assert by_precision.get("none", 0) <= 10
        # Every located team is accounted for.
        assert sum(by_precision.values()) == 207

        needs_review_count = sum(1 for t in payload["teams"] if t["needs_review"])
        # A small, meaningful minority -- if this ever approaches the
        # school-precision count itself, the matcher's confidence
        # scoring (or its stopword normalization) has regressed.
        assert 0 < needs_review_count <= 40

        # matched_name is recorded on every resolved team (AC).
        for team in payload["teams"]:
            if team["location_precision"] != "none":
                assert team["matched_name"] != ""
            else:
                assert team["matched_name"] == ""

        assert payload["meta"]["out_of_region"] == 6


_ALLOW_ALL_ROBOTS = "User-agent: *\nDisallow:\n"


class _StubTeamSource:
    """A `TeamSource` returning exactly the caller-supplied `Team`s,
    ignoring the injected `Fetcher` entirely -- gives this class full
    control over which `Team`s (and which `website`) `run_teams()`
    dispatches to `verify_team_websites()`/`extract_sponsors()`, without
    depending on the real 152-team FTCScout fixture (whose `website`
    coverage depends on the committed ticket 006 overlay, not something
    this class's tests should be coupled to)."""

    def __init__(self, teams: list[Team]) -> None:
        self._teams = teams

    def discover(self, source, fetcher):
        return [TeamRef(url="https://example.org/stub-source")]

    def fetch(self, ref, fetcher):
        return RawTeamResponse(ref=ref, status=200, body="")

    def extract(self, raw, source):
        return self._teams


def _one_team_registry(tmp_path: Path) -> Path:
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    (registry_dir / "ftc-sd.toml").write_text(
        'org_name = "FTC"\nadapter_type = "ftcscout"\nenabled = true\n[config]\n'
    )
    return registry_dir


class TestSponsorExtractionWiring:
    """Sprint 013 ticket 005: `extract_sponsors()` sequenced after
    `verify_team_websites()` and before `export_teams()`, with
    injectable `llm_client`/`sponsor_cache` and a `no_sponsors` escape
    hatch (the CLI's `--no-sponsors` flag)."""

    _SPONSOR_HTML = (
        "<html><body><h2>Sponsors</h2>"
        '<div><a href="https://sponsor.example.com">Real Sponsor Co</a></div>'
        "</body></html>"
    )

    def test_a_confirmed_team_gets_a_scraped_sponsor_via_the_injected_llm_client(
        self, monkeypatch, tmp_path
    ):
        website = "https://www.teamspyder.org/"
        team = Team(
            team_id="ftc-1622",
            league="FTC",
            program="FIRST Tech Challenge",
            number=1622,
            name="Team Spyder",
            organization="Poway High School",
            website=website,
        )
        monkeypatch.setattr(teams_pipeline, "_TEAM_SOURCES", {"ftcscout": _StubTeamSource([team])})

        fetcher = FixtureFetcher(
            {
                robots_txt_url(website): FetchResponse(url="", status=200, headers={}, body=_ALLOW_ALL_ROBOTS),
                website: FetchResponse(url="", status=200, headers={}, body=self._SPONSOR_HTML),
            }
        )
        llm_client = FixtureSponsorLLMClient(
            responses={
                ("Real Sponsor Co", "sponsor.example.com"): SponsorExtractionResult(
                    confirmed_sponsors=["Real Sponsor Co"]
                ),
            }
        )
        sponsor_cache = SponsorCache(cache_dir=tmp_path / "cache")

        payload = run_teams(
            registry_dir=_one_team_registry(tmp_path),
            site_dir=tmp_path,
            fetcher=fetcher,
            dry_run=True,
            llm_client=llm_client,
            sponsor_cache=sponsor_cache,
        )

        [published] = payload["teams"]
        assert published["sponsors"] == ["Real Sponsor Co"]
        assert published["sponsor_provenance"] == {"Real Sponsor Co": "scraped"}
        assert len(llm_client.calls) == 1

    def test_no_sponsors_skips_extraction_but_website_verification_still_runs(
        self, monkeypatch, tmp_path
    ):
        website = "https://www.teamspyder.org/"
        team = Team(
            team_id="ftc-1622",
            league="FTC",
            program="FIRST Tech Challenge",
            number=1622,
            name="Team Spyder",
            organization="Poway High School",
            website=website,
        )
        monkeypatch.setattr(teams_pipeline, "_TEAM_SOURCES", {"ftcscout": _StubTeamSource([team])})

        fetcher = FixtureFetcher(
            {
                robots_txt_url(website): FetchResponse(url="", status=200, headers={}, body=_ALLOW_ALL_ROBOTS),
                website: FetchResponse(url="", status=200, headers={}, body=self._SPONSOR_HTML),
            }
        )

        def _boom_llm_client():
            raise AssertionError("AnthropicSponsorLLMClient must not be constructed under no_sponsors")

        monkeypatch.setattr(teams_pipeline, "AnthropicSponsorLLMClient", _boom_llm_client)

        payload = run_teams(
            registry_dir=_one_team_registry(tmp_path),
            site_dir=tmp_path,
            fetcher=fetcher,
            dry_run=True,
            no_sponsors=True,
        )

        [published] = payload["teams"]
        # verify_team_websites() (the cheap, certain half) still ran.
        assert published["website_status"] == "confirmed"
        # extract_sponsors() (the skippable half) never ran.
        assert published["sponsors"] == []
        assert published["sponsor_provenance"] == {}

    def test_llm_client_and_sponsor_cache_default_to_real_implementations_when_omitted(
        self, monkeypatch, tmp_path
    ):
        # A confirmed website whose page has no sponsor-shaped content
        # at all -- fetch_results is non-empty (so run_teams() actually
        # reaches the default-construction line below), but
        # gather_sponsor_candidates() returns [] for this team, so
        # extract_sponsors() never calls classify_sponsors() and no real
        # network/API call is ever made. This proves run_teams() can
        # default-construct AnthropicSponsorLLMClient()/SponsorCache()
        # (matching fetcher's own default-to-production convention)
        # without raising, even with no ANTHROPIC_API_KEY configured for
        # this test (SCRAPE_CACHE_DIR is set below -- SponsorCache()'s
        # own construction requires it, same as PoliteFetcher()'s does).
        website = "https://www.teamspyder.org/"
        team = Team(
            team_id="ftc-1622",
            league="FTC",
            program="FIRST Tech Challenge",
            number=1622,
            name="Team Spyder",
            website=website,
        )
        monkeypatch.setattr(teams_pipeline, "_TEAM_SOURCES", {"ftcscout": _StubTeamSource([team])})
        monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path / "cache"))

        no_sponsor_content_html = "<html><body><p>Nothing sponsor-shaped here.</p></body></html>"
        fetcher = FixtureFetcher(
            {
                robots_txt_url(website): FetchResponse(url="", status=200, headers={}, body=_ALLOW_ALL_ROBOTS),
                website: FetchResponse(url="", status=200, headers={}, body=no_sponsor_content_html),
            }
        )

        payload = run_teams(
            registry_dir=_one_team_registry(tmp_path),
            site_dir=tmp_path,
            fetcher=fetcher,
            dry_run=True,
        )

        [published] = payload["teams"]
        assert published["website_status"] == "confirmed"
        assert published["sponsors"] == []


class TestParseSunsetSeason:
    def test_parses_yyyy_yy_to_june_first_of_second_year(self):
        assert _parse_sunset_season("2026-27") == date(2027, 6, 1)

    def test_strips_surrounding_whitespace(self):
        assert _parse_sunset_season("  2026-27  ") == date(2027, 6, 1)

    def test_century_rollover_is_handled(self):
        assert _parse_sunset_season("2099-00") == date(2100, 6, 1)

    def test_malformed_values_return_none(self):
        assert _parse_sunset_season("not-a-season") is None
        assert _parse_sunset_season("2026") is None
        assert _parse_sunset_season("2026-2027") is None
        assert _parse_sunset_season("") is None


class TestSunsetSeasonWarning:
    """AC: `run_teams()` logs `logging.WARNING` exactly once per run
    when an active source's `sunset_season` has passed `today`, and
    logs nothing when it is absent or not yet passed.

    Drives the real registry (`fll-sd.toml`'s real, committed
    `sunset_season = "2026-27"`, parsed as ending 2027-06-01 --
    `_parse_sunset_season()`'s own docstring) filtered to
    `source="static_roster"` so only that one source runs, isolating
    this test from FTC/TBA network-shaped concerns entirely -- a plain
    `FixtureFetcher({})` is enough since `static_roster` never calls it.
    """

    def test_a_date_past_the_sunset_season_logs_exactly_one_warning(self, tmp_path, caplog):
        with caplog.at_level(logging.WARNING, logger="partner_scrape.teams.pipeline"):
            run_teams(
                source="static_roster",
                site_dir=tmp_path,
                fetcher=FixtureFetcher({}),
                dry_run=True,
                today=date(2027, 6, 2),  # one day past the parsed 2027-06-01 end
            )

        sunset_records = [
            r for r in caplog.records if "sunset season" in r.getMessage()
        ]
        assert len(sunset_records) == 1
        assert sunset_records[0].levelno == logging.WARNING
        assert "fll-sd" in sunset_records[0].getMessage()
        assert "2026-27" in sunset_records[0].getMessage()

    def test_a_date_on_the_season_end_itself_is_not_yet_past(self, tmp_path, caplog):
        # 2027-06-01 is the parsed end date itself -- "past" means
        # strictly after, not on-or-after (an FLL season concluding on
        # its own last day is not yet "over" the moment that day
        # begins).
        with caplog.at_level(logging.WARNING, logger="partner_scrape.teams.pipeline"):
            run_teams(
                source="static_roster",
                site_dir=tmp_path,
                fetcher=FixtureFetcher({}),
                dry_run=True,
                today=date(2027, 6, 1),
            )

        assert "sunset season" not in caplog.text

    def test_a_date_well_before_the_sunset_season_logs_nothing(self, tmp_path, caplog):
        with caplog.at_level(logging.WARNING, logger="partner_scrape.teams.pipeline"):
            run_teams(
                source="static_roster",
                site_dir=tmp_path,
                fetcher=FixtureFetcher({}),
                dry_run=True,
                today=date(2026, 8, 28),
            )

        assert "sunset season" not in caplog.text

    def test_a_source_with_no_sunset_season_never_warns(self, tmp_path, caplog):
        # ftc-sd.toml carries no sunset_season at all -- absent, not
        # merely unpassed.
        with caplog.at_level(logging.WARNING, logger="partner_scrape.teams.pipeline"):
            run_teams(
                source="ftcscout",
                site_dir=tmp_path,
                fetcher=_ftcscout_fetcher(),
                dry_run=True,
                today=date(2099, 1, 1),
            )

        assert "sunset season" not in caplog.text
