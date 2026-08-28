"""Tests for partner_scrape.teams.export: the teams.json publish step.

``tests/fixtures/teams/ftcscout_search.json`` (the same live-captured
152-record fixture ticket 001's ftcscout tests use) drives the
email-privacy regression test and the two-hard-invariant tests below,
via the real FTCScoutSource/sources.base.run chain -- no test in this
module opens a real network socket.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.teams.export import TEAMS_SCHEMA_FIELDS, export_teams, to_json_dict
from partner_scrape.teams.model import Team
from partner_scrape.teams.sources.base import run as run_source
from partner_scrape.teams.sources.ftcscout import DEFAULT_API_BASE, DEFAULT_REGION, FTCScoutSource, _search_url
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


def _real_fixture_teams() -> list[Team]:
    """All 152 San Diego FTC teams, extracted from the real live-captured
    fixture through the real FTCScoutSource -- used by the privacy and
    hard-invariant tests so they exercise realistic, full-scale output."""
    body = (FIXTURES_DIR / "ftcscout_search.json").read_text()
    fetcher = FixtureFetcher({SEARCH_URL: FetchResponse(url="", status=200, headers={}, body=body)})
    return run_source(_source_config(), FTCScoutSource(), fetcher)


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
    the full 152-team fixture set, not just a single hand-built Team, so
    a real-scale export is what's actually proven byte-identical."""

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
    never leaks one either, over the full 152-team live-captured
    fixture."""

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
