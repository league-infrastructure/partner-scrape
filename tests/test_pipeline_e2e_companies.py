"""End-to-end dry-run test proving tickets 001-005 compose correctly: a
fixture Greenhouse source and a fixture Lever source, run through the
real `pipeline.run(..., dry_run=True)`, produce internship Opportunities
with `opportunity_type="Work-based Learning"` (sprint.md's Design
Rationale) -- the only place in sprint 006 proving the whole chain
(Registry -> Greenhouse/Lever Adapter -> ATS Filters -> Relevance Gate
bypass -> Normalize collapse/dedup bypass -> Site Export) end-to-end
(ticket 006's own Acceptance Criteria).

Mirrors `tests/test_pipeline_e2e.py`'s `TestWalkingSkeletonEndToEnd`
pattern (fixture-only registry dir under `tests/fixtures/
e2e_companies_registry/`, fixture `Fetcher`, tmp_path-backed `site_dir`
with a copied `partners.json`) -- no test here opens a real socket.
Neither fixture company ("Fixture Robotics Co" / "Fixture Biotech Co")
matches an entry in `tests/fixtures/partners.json`, which is fine and
deliberate: SUC-005's documented partner-join error flow is "no match ->
keep the org name, leave partner_id unset, do not fail the record" --
exactly the path this test also exercises.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from partner_scrape.adapters.greenhouse import DEFAULT_API_BASE as GREENHOUSE_API_BASE
from partner_scrape.adapters.lever import DEFAULT_API_BASE as LEVER_API_BASE
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.pipeline import run

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
E2E_COMPANIES_REGISTRY_DIR = FIXTURES_DIR / "e2e_companies_registry"
PARTNERS_FIXTURE = FIXTURES_DIR / "partners.json"

TODAY = date(2026, 7, 19)

GREENHOUSE_BOARD_TOKEN = "fixturerobotics"
GREENHOUSE_URL = f"{GREENHOUSE_API_BASE}/{GREENHOUSE_BOARD_TOKEN}/jobs?content=true"

LEVER_COMPANY = "fixturebiotech"
LEVER_URL = f"{LEVER_API_BASE}/{LEVER_COMPANY}?mode=json"


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.

    A URL absent from ``responses`` raises ``KeyError`` -- a loud
    failure if the pipeline fetches something it shouldn't. Kept as a
    separate, file-local definition rather than importing across test
    files, matching this suite's existing per-file fixture-double
    convention (every other test file in this suite, e.g.
    `test_pipeline_e2e.py`, defines its own `FixtureFetcher` rather than
    sharing one).
    """

    responses: dict[str, FetchResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        return self.responses[url]


def _response(body: str, status: int = 200) -> FetchResponse:
    return FetchResponse(url="", status=status, headers={}, body=body)


def _fixture_fetcher() -> FixtureFetcher:
    greenhouse_body = (E2E_COMPANIES_REGISTRY_DIR / "greenhouse_jobs.json").read_text()
    lever_body = (E2E_COMPANIES_REGISTRY_DIR / "lever_postings.json").read_text()
    return FixtureFetcher(
        {
            GREENHOUSE_URL: _response(greenhouse_body),
            LEVER_URL: _response(lever_body),
        }
    )


def _site_dir(tmp_path: Path) -> Path:
    """A tmp_path-backed stand-in for the sibling stem-ecosystem repo,
    with `src/data/partners.json` seeded from the shared fixture --
    never the real `../stem-ecosystem` checkout."""
    site_dir = tmp_path / "stem-ecosystem"
    data_dir = site_dir / "src" / "data"
    data_dir.mkdir(parents=True)
    shutil.copy(PARTNERS_FIXTURE, data_dir / "partners.json")
    return site_dir


class TestCompanyInternshipsEndToEnd:
    def test_only_matching_postings_become_internship_opportunities(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        payload = run(
            registry_dir=E2E_COMPANIES_REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            today=TODAY,
            dry_run=True,
        )

        titles = {record["title"] for record in payload}
        assert titles == {
            "Software Engineering Intern",
            "Bioinformatics Research Associate",
        }
        # Non-matching postings (full-time, non-STEM) never became
        # Opportunities at all -- filtered inside each adapter's
        # extract(), before Normalize/Export ever see them.
        assert "Senior Robotics Engineer" not in titles
        assert "Director of Sales" not in titles

    def test_internship_opportunities_have_work_based_learning_type_and_expected_fields(
        self, tmp_path
    ):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        payload = run(
            registry_dir=E2E_COMPANIES_REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            today=TODAY,
            dry_run=True,
        )

        assert len(payload) == 2
        for record in payload:
            assert record["opportunity_type"] == "Work-based Learning"
            assert record["link"]
            # Neither fixture posting carries a deadline -- sprint.md's
            # Design Rationale: "still present in the feed" is itself
            # the "still open" signal, not a date.
            assert record["date_end"] == ""
            assert record["availability"] == "Rolling — apply anytime"
            # ticket 002's own contract: neither adapter sets a cost
            # badge for an internship (ats_filters.py's module
            # docstring).
            assert record["cost_range"] == ""

        [greenhouse_record] = [
            r for r in payload if r["title"] == "Software Engineering Intern"
        ]
        assert greenhouse_record["partner_name"] == "Fixture Robotics Co"
        assert greenhouse_record["link"] == (
            "https://boards.greenhouse.io/fixturerobotics/jobs/9101"
        )

        [lever_record] = [
            r for r in payload if r["title"] == "Bioinformatics Research Associate"
        ]
        assert lever_record["partner_name"] == "Fixture Biotech Co"
        assert lever_record["link"] == (
            "https://jobs.lever.co/fixturebiotech/e2e-lever-0001/apply"
        )

    def test_dry_run_writes_nothing_to_disk(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        run(
            registry_dir=E2E_COMPANIES_REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            today=TODAY,
            dry_run=True,
        )

        assert not (site_dir / "src" / "data" / "opportunities.json").exists()
        assert not (site_dir / "src" / "data" / "scrape-meta.json").exists()

    def test_no_network_access_every_fetch_is_a_known_fixture_url(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        run(
            registry_dir=E2E_COMPANIES_REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            today=TODAY,
            dry_run=True,
        )

        assert set(fetcher.calls) == {GREENHOUSE_URL, LEVER_URL}
