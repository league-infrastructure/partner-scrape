"""Tests for partner_scrape.teams.export: the teams.json publish step.

``tests/fixtures/teams/ftcscout_search.json`` (the same live-captured
152-record fixture ticket 001's ftcscout tests use) drives the
email-privacy regression test and the two-hard-invariant tests below,
via the real FTCScoutSource/sources.base.run chain -- no test in this
module opens a real network socket.

Sprint 012: ``_real_fixture_teams()`` was extended (not replaced) to
also include the real, committed 48-team FLL static roster
(``teams.sources.static_roster.StaticRosterSource``, reading the real
``teams/data/fll-sd-teams.tsv`` -- no network, no fixture copy needed,
since the committed roster already contains no contact field to leak).
This confirms ``TestNoEmailInExport``'s privacy regression actually
exercises the FLL rows this ticket adds, not just the pre-existing FTC
ones -- exactly the sprint 011 ticket-011-003 lesson applied to this
ticket's own new data source.

Sprint 013 ticket 005: ``_real_fixture_teams()`` was extended again to
also run one team's fetched page through the real
``teams.sponsor_extract.extract_sponsors()`` (a fixture LLM client, no
network) so the privacy regression -- and every other assertion driven
by this helper -- exercises output that includes a scraped sponsor name
and ``sponsor_provenance``, not just the two structured sources' own
fields.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.teams.export import (
    TEAMS_SCHEMA_FIELDS,
    _natural_number_key,
    export_teams,
    to_json_dict,
)
from partner_scrape.teams.model import Team
from partner_scrape.teams.sources.base import run as run_source
from partner_scrape.teams.sources.ftcscout import DEFAULT_API_BASE, DEFAULT_REGION, FTCScoutSource, _search_url
from partner_scrape.teams.sources.static_roster import StaticRosterSource
from partner_scrape.teams.sponsor_cache import content_hash
from partner_scrape.teams.sponsor_candidates import gather_sponsor_candidates
from partner_scrape.teams.sponsor_extract import extract_sponsors
from partner_scrape.teams.sponsor_llm import FixtureSponsorLLMClient, SponsorExtractionResult
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "teams"
SEARCH_URL = _search_url(DEFAULT_API_BASE, DEFAULT_REGION)

#: A loose but sufficient email-address pattern for the privacy
#: regression test -- matching `local@domain.tld`, case-insensitive.
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket."""

    responses: dict[str, FetchResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        return self.responses[url]


def _source_config() -> SourceConfig:
    return SourceConfig(
        source_id="ftc-sd",
        org_name="FIRST Tech Challenge -- San Diego County",
        adapter_type="ftcscout",
        config={},
    )


def _static_roster_source_config() -> SourceConfig:
    return SourceConfig(
        source_id="fll-sd",
        org_name="FIRST LEGO League -- San Diego County (static roster)",
        adapter_type="static_roster",
        # No roster_path override -- StaticRosterSource falls back to
        # DEFAULT_ROSTER_PATH, the real committed teams/data/
        # fll-sd-teams.tsv, matching this file's "trust the real data"
        # convention for the FTCScout fixture above.
        config={},
    )


@dataclass
class _InMemorySponsorCache:
    """A `SponsorCache`-shaped double (`.lookup`/`.store`, keyed the
    same way) that never touches disk -- used only by
    `_real_fixture_teams()` below, which is called from many test
    methods, not all of which have a `tmp_path` to hand a real
    `SponsorCache` a cache directory."""

    _store: dict[tuple[str, str], SponsorExtractionResult] = field(default_factory=dict)

    def lookup(self, team_id: str, candidates: list[str]) -> SponsorExtractionResult | None:
        return self._store.get((team_id, content_hash(candidates)))

    def store(self, team_id: str, candidates: list[str], result: SponsorExtractionResult) -> None:
        self._store[(team_id, content_hash(candidates))] = result


#: A synthetic sponsor-shaped page for the one team `_real_fixture_teams()`
#: runs through `extract_sponsors()` -- see that function's own docstring
#: for why (sprint 013 ticket 005).
_SCRAPED_SPONSOR_HTML = (
    "<html><body><h2>Sponsors</h2>"
    '<div><a href="https://scraped-sponsor.example.com">Scraped Sponsor Co</a></div>'
    "</body></html>"
)


def _real_fixture_teams() -> list[Team]:
    """All 152 San Diego FTC teams (from the live-captured fixture,
    through the real FTCScoutSource) plus the real, committed 48-team
    FLL static roster (through the real StaticRosterSource, sprint
    012) -- 200 teams total. Used by the privacy and hard-invariant
    tests so they exercise realistic, full-scale output across every
    source this subsystem has, not just the two live ones.

    Sprint 013 ticket 005: also runs "Team Spyder" (ftc-1622) through
    `extract_sponsors()` with a synthetic fetched page and a
    `FixtureSponsorLLMClient` (no network), so the returned corpus
    carries a real scraped sponsor name and populated
    `sponsor_provenance` too -- not just the two structured sources'
    own fields.
    """
    body = (FIXTURES_DIR / "ftcscout_search.json").read_text()
    fetcher = FixtureFetcher({SEARCH_URL: FetchResponse(url="", status=200, headers={}, body=body)})
    ftc_teams = run_source(_source_config(), FTCScoutSource(), fetcher)

    # StaticRosterSource never touches the injected fetcher (it reads
    # the committed roster straight off disk) -- reusing the same
    # FixtureFetcher here is just convenient, not load-bearing; a
    # Fetcher that raised on any call would work identically.
    fll_teams = run_source(_static_roster_source_config(), StaticRosterSource(), fetcher)

    teams = [*ftc_teams, *fll_teams]

    spyder = next(t for t in teams if t.team_id == "ftc-1622")
    candidates = gather_sponsor_candidates(_SCRAPED_SPONSOR_HTML, spyder.website)
    llm_client = FixtureSponsorLLMClient(
        responses={
            tuple(candidates): SponsorExtractionResult(confirmed_sponsors=["Scraped Sponsor Co"]),
        }
    )
    extract_sponsors([spyder], {spyder.team_id: _SCRAPED_SPONSOR_HTML}, llm_client, _InMemorySponsorCache())

    return teams


def _make_site(root: Path, *, opportunities: str = "[]", scrape_meta: str = "{}") -> Path:
    data_dir = root / "src" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "opportunities.json").write_text(opportunities)
    (data_dir / "scrape-meta.json").write_text(scrape_meta)
    return root


def _make_team(**overrides) -> Team:
    defaults = dict(
        team_id="ftc-1622",
        league="FTC",
        program="FIRST Tech Challenge",
        number=1622,
        name="Team Spyder",
        organization="Poway High School",
        org_type="school",
        city="Poway",
        sources=["ftcscout"],
    )
    defaults.update(overrides)
    return Team(**defaults)


class TestSchemaFieldSet:
    def test_sources_is_dropped_as_bookkeeping(self):
        assert "sources" not in TEAMS_SCHEMA_FIELDS

    def test_every_other_team_field_is_present(self):
        from dataclasses import fields

        expected = {f.name for f in fields(Team) if f.name != "sources"}
        assert set(TEAMS_SCHEMA_FIELDS) == expected

    def test_to_json_dict_projects_exactly_the_schema_fields(self):
        team = _make_team()
        result = to_json_dict(team)

        assert set(result.keys()) == set(TEAMS_SCHEMA_FIELDS)
        assert "sources" not in result
        assert result["team_id"] == "ftc-1622"


class TestNaturalSortKey:
    """Sprint 016 ticket 005: `_natural_number_key` backs `export_teams()`'s
    sort now that `Team.number` is `str` (VEX designations are
    alphanumeric). See that function's own docstring for the tuple shape
    (`(leading_digit_run_as_int, full_string)`)."""

    def test_purely_numeric_strings_sort_numerically_not_lexicographically(self):
        assert _natural_number_key("99") < _natural_number_key("100")

    def test_alphanumeric_siblings_share_the_leading_digit_run(self):
        a = _natural_number_key("90210A")
        b = _natural_number_key("90210B")

        assert a[0] == b[0] == 90210
        assert a < b  # tiebreaker: full-string comparison

    def test_empty_string_sorts_first(self):
        assert _natural_number_key("") == (0, "")

    def test_coerces_a_non_string_input(self):
        # Team.number is a plain, untyped field (matching Team.league's
        # convention) -- this key must not crash on a Team whose number
        # happens to still be an int (see model.py's docstring on why
        # ftcscout.py/tba.py/static_roster.py were not also touched by
        # this ticket).
        assert _natural_number_key(1622) == (1622, "1622")


class TestExportSortOrder:
    """Sprint 016 ticket 005's own regression requirement: a mixed
    FTC/FRC/FLL fixture set (all-numeric `number` values) must sort
    identically to its pre-widen order, and a VEX fixture's alphanumeric
    siblings must sort adjacently."""

    def test_mixed_ftc_frc_fll_numeric_numbers_sort_identically_to_pre_widen_order(
        self, tmp_path
    ):
        site = _make_site(tmp_path)
        teams = [
            _make_team(team_id="ftc-100", league="FTC", number="100", name="Hundred"),
            _make_team(team_id="ftc-99", league="FTC", number="99", name="Ninety-Nine"),
            _make_team(team_id="ftc-9", league="FTC", number="9", name="Nine"),
            _make_team(team_id="frc-2", league="FRC", number="2", name="Two"),
            _make_team(team_id="frc-10", league="FRC", number="10", name="Ten"),
            _make_team(team_id="fll-1", league="FLL", number="1", name="One"),
        ]

        payload = export_teams(teams, site_dir=site)
        ordered_ids = [t["team_id"] for t in payload["teams"]]

        # Grouped by league (FLL, FRC, FTC alphabetically), each group
        # numerically ascending -- "9" before "99" before "100", not the
        # lexicographic "100" before "9" a bare string sort would give.
        assert ordered_ids == ["fll-1", "frc-2", "frc-10", "ftc-9", "ftc-99", "ftc-100"]

    def test_vex_alphanumeric_siblings_sort_adjacently(self, tmp_path):
        site = _make_site(tmp_path)
        teams = [
            _make_team(team_id="vex-90210C", league="VEX", number="90210C", name="C"),
            _make_team(team_id="vex-90210A", league="VEX", number="90210A", name="A"),
            _make_team(team_id="vex-90210B", league="VEX", number="90210B", name="B"),
        ]

        payload = export_teams(teams, site_dir=site)
        ordered_ids = [t["team_id"] for t in payload["teams"]]

        assert ordered_ids == ["vex-90210A", "vex-90210B", "vex-90210C"]


class TestPayloadShape:
    def test_payload_has_meta_and_teams_keys(self, tmp_path):
        site = _make_site(tmp_path)

        payload = export_teams([_make_team()], site_dir=site)

        assert set(payload.keys()) == {"meta", "teams"}
        assert isinstance(payload["teams"], list)
        assert len(payload["teams"]) == 1

    def test_meta_carries_generated_total_by_league_and_out_of_region(self, tmp_path):
        site = _make_site(tmp_path)
        teams = [
            _make_team(team_id="ftc-1", number=1, in_region=True),
            _make_team(team_id="ftc-2", number=2, in_region=False),
            _make_team(team_id="frc-1", league="FRC", number=1, in_region=True),
        ]

        payload = export_teams(teams, site_dir=site)
        meta = payload["meta"]

        assert meta["total"] == 3
        assert meta["by_league"] == {"FTC": 2, "FRC": 1}
        assert meta["out_of_region"] == 1
        assert meta["generated"]

    def test_meta_carries_location_precision_breakdown(self, tmp_path):
        site = _make_site(tmp_path)
        teams = [
            _make_team(team_id="ftc-1", number=1, location_precision="none"),
            _make_team(team_id="ftc-2", number=2, location_precision="city"),
        ]

        payload = export_teams(teams, site_dir=site)

        assert payload["meta"]["by_location_precision"] == {"none": 1, "city": 1}

    def test_teams_are_written_to_disk_at_the_documented_path(self, tmp_path):
        site = _make_site(tmp_path)

        export_teams([_make_team()], site_dir=site)

        written = json.loads((site / "src" / "data" / "teams.json").read_text())
        assert written["meta"]["total"] == 1
        assert written["teams"][0]["team_id"] == "ftc-1622"


class TestDryRun:
    def test_dry_run_computes_the_payload_without_writing(self, tmp_path):
        site = _make_site(tmp_path)

        payload = export_teams([_make_team()], site_dir=site, dry_run=True)

        assert payload["meta"]["total"] == 1
        assert not (site / "src" / "data" / "teams.json").exists()

    def test_dry_run_never_touches_a_nonexistent_site_dir(self, tmp_path):
        absent = tmp_path / "not-checked-out"

        payload = export_teams([_make_team()], site_dir=absent, dry_run=True)

        assert payload["meta"]["total"] == 1
        assert not absent.exists()


class TestUnwritableSiteDirFailsLoudly:
    def test_missing_src_data_raises_runtime_error(self, tmp_path):
        site = tmp_path / "no-data-dir"
        site.mkdir()

        with pytest.raises(RuntimeError, match="Cannot write teams export"):
            export_teams([_make_team()], site_dir=site)


class TestHardInvariants:
    """SUC-001's two hard invariants: a `teams` run never writes or
    touches `opportunities.json`/`scrape-meta.json` -- covered here with
    the full 200-team (152 FTC + 48 FLL) fixture set, not just a single
    hand-built Team, so a real-scale export is what's actually proven
    byte-identical."""

    def test_opportunities_and_scrape_meta_are_byte_identical_after_a_teams_run(self, tmp_path):
        opportunities_body = json.dumps([{"title": "Untouched Opportunity"}])
        scrape_meta_body = json.dumps({"last_updated": "2026-01-01T00:00:00Z"})
        site = _make_site(
            tmp_path, opportunities=opportunities_body, scrape_meta=scrape_meta_body
        )

        export_teams(_real_fixture_teams(), site_dir=site)

        data_dir = site / "src" / "data"
        assert (data_dir / "opportunities.json").read_text() == opportunities_body
        assert (data_dir / "scrape-meta.json").read_text() == scrape_meta_body

    def test_no_opportunities_or_scrape_meta_file_is_created_when_absent(self, tmp_path):
        data_dir = tmp_path / "src" / "data"
        data_dir.mkdir(parents=True)

        export_teams(_real_fixture_teams(), site_dir=tmp_path)

        assert not (data_dir / "opportunities.json").exists()
        assert not (data_dir / "scrape-meta.json").exists()
        assert (data_dir / "teams.json").exists()


class TestNoEmailInExport:
    """The structural no-email invariant, checked at the export layer:
    no key or value anywhere in the written teams.json matches an
    email-address pattern. `model.Team` has no `email` field at all
    (tests/teams/test_model.py's job to prove that structurally) -- this
    test is the end-to-end regression that the *published artifact*
    never leaks one either, over the full 200-team fixture (152 FTC +
    48 FLL, sprint 012) -- including the FLL rows whose upstream source
    carries 6 real coach email addresses that must never reach this
    file (see `sources/static_roster.py`'s module docstring)."""

    def test_written_json_contains_no_email_pattern(self, tmp_path):
        site = _make_site(tmp_path)

        export_teams(_real_fixture_teams(), site_dir=site)

        raw_text = (site / "src" / "data" / "teams.json").read_text()
        assert not _EMAIL_PATTERN.search(raw_text)

    def test_dry_run_payload_contains_no_email_pattern(self):
        payload = export_teams(_real_fixture_teams(), site_dir=Path("/unused"), dry_run=True)

        serialized = json.dumps(payload)
        assert not _EMAIL_PATTERN.search(serialized)

    def test_no_key_or_value_in_the_parsed_payload_matches_an_email(self, tmp_path):
        site = _make_site(tmp_path)
        export_teams(_real_fixture_teams(), site_dir=site)
        parsed = json.loads((site / "src" / "data" / "teams.json").read_text())

        def _walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    assert not _EMAIL_PATTERN.search(str(key))
                    _walk(value)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)
            else:
                assert not _EMAIL_PATTERN.search(str(node))

        _walk(parsed)


class TestSponsorExtractionFixtureIsWired:
    """Sanity check that `_real_fixture_teams()`'s sponsor-extraction
    step (sprint 013 ticket 005, added to this file's own corpus so
    `TestNoEmailInExport` exercises sponsor-extraction output too) is
    actually producing output -- so a silent regression there could not
    hide behind the privacy regression test still passing vacuously."""

    def test_team_spyder_carries_the_scraped_sponsor_and_provenance(self, tmp_path):
        site = _make_site(tmp_path)
        payload = export_teams(_real_fixture_teams(), site_dir=site)

        spyder = next(t for t in payload["teams"] if t["team_id"] == "ftc-1622")
        assert "Scraped Sponsor Co" in spyder["sponsors"]
        assert spyder["sponsor_provenance"]["Scraped Sponsor Co"] == "scraped"
