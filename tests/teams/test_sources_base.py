"""Tests for partner_scrape.teams.sources.base: the TeamSource protocol
and its structural isolation from partner_scrape.adapters.base.

The isolation test (``TestNoAdaptersBaseReference``) is the acceptance
criterion that matters most here: a team source reachable from
``adapters.base.ADAPTERS`` would become reachable from
``pipeline.run()``, which would hand a ``Team`` to ``normalize.run()``
and crash on a type it doesn't expect (see ``sources/base.py``'s module
docstring). It scans every ``.py`` file actually shipped in
``partner_scrape.teams.sources`` via ``ast`` -- a source-level check,
not just "the currently-written modules happen not to import it" --
so a future addition to this package (e.g. ticket 011-003's ``tba.py``)
that adds the forbidden import fails this test too, not just today's.
"""

from __future__ import annotations

import ast
from pathlib import Path

import partner_scrape.teams.sources as teams_sources_pkg
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.registry.schema import SourceConfig
from partner_scrape.teams.model import Team
from partner_scrape.teams.sources.base import RawTeamResponse, TeamRef, run


def _imports_adapters_base(py_path: Path) -> bool:
    tree = ast.parse(py_path.read_text(), filename=str(py_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.startswith("partner_scrape.adapters") for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("partner_scrape.adapters"):
                return True
    return False


class TestNoAdaptersBaseReference:
    def test_no_module_in_teams_sources_imports_partner_scrape_adapters(self):
        pkg_dir = Path(teams_sources_pkg.__file__).resolve().parent
        py_files = sorted(pkg_dir.glob("*.py"))

        # Sanity check the scan itself isn't vacuously true because the
        # directory is empty or misconfigured.
        assert py_files
        assert any(f.name == "ftcscout.py" for f in py_files)

        offenders = [f.name for f in py_files if _imports_adapters_base(f)]
        assert offenders == []

    def test_adapters_base_ADAPTERS_has_no_teams_entry(self):
        # Belt-and-suspenders: even if some future teams source did
        # import adapters.base, it must never register itself in the
        # dispatch table pipeline.run() consumes.
        from partner_scrape.adapters.base import ADAPTERS

        assert "ftcscout" not in ADAPTERS


class _FakeSource:
    """Minimal TeamSource double for exercising base.run()'s chaining."""

    def __init__(self, teams: list[Team]):
        self._teams = teams
        self.discover_calls = 0
        self.fetch_calls: list[TeamRef] = []

    def discover(self, source: SourceConfig, fetcher):
        self.discover_calls += 1
        return [TeamRef(url="https://example.org/teams")]

    def fetch(self, ref: TeamRef, fetcher) -> RawTeamResponse:
        self.fetch_calls.append(ref)
        response = fetcher.get(ref.url)
        return RawTeamResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawTeamResponse, source: SourceConfig):
        return self._teams


class _StubFetcher:
    def get(self, url: str, headers=None) -> FetchResponse:
        return FetchResponse(url=url, status=200, headers={}, body="[]")


def _source() -> SourceConfig:
    return SourceConfig(
        source_id="ftc-sd",
        org_name="FIRST Tech Challenge -- San Diego County",
        adapter_type="ftcscout",
        config={},
    )


class TestRunChaining:
    def test_run_chains_discover_fetch_extract_and_returns_extracted_teams(self):
        expected = [Team(team_id="ftc-1622", league="FTC", number=1622, name="Team Spyder")]
        source_double = _FakeSource(expected)

        teams = run(_source(), source_double, _StubFetcher())

        assert teams == expected
        assert source_double.discover_calls == 1
        assert len(source_double.fetch_calls) == 1

    def test_run_returns_empty_list_when_extract_yields_nothing(self):
        source_double = _FakeSource([])

        teams = run(_source(), source_double, _StubFetcher())

        assert teams == []
