"""Tests for partner_scrape.adapters.lever: the Lever ATS adapter.

Every test drives the adapter through a fixture Fetcher returning
recorded/synthesized Lever postings JSON (tests/fixtures/lever/) -- no
test here opens a real network socket, per sprint.md's test strategy for
the Adapter Framework and this ticket's "ALL tests offline" constraint.

``tests/fixtures/lever/postings.json`` is a **top-level JSON array** (the
one structural difference from Greenhouse/TEC/Localist -- see
``adapters/lever.py``'s module docstring) mixing five postings so a
single fixture exercises every filtering axis at once:
  - "Robotics Software Associate" (San Diego, Engineering,
    ``categories.commitment="Internship"``) -- keeps: internship (via
    the *commitment* field, not the title -- "Robotics Software
    Associate" alone does not match the internship-title regex) + STEM +
    San Diego.
  - "Senior Backend Engineer" (San Diego, Engineering,
    ``commitment="Full Time Employee"``) -- drops: not an internship/
    early-career role.
  - "Data Science Intern" (Austin, TX) -- drops: not San Diego-local
    under the default ``location_keywords`` (also proves the
    ``location_keywords`` override, below).
  - "Marketing Intern" (San Diego, Marketing) -- drops: not STEM.
  - a record with no ``text`` key -- malformed, must be skipped without
    aborting the rest of the response.

``tests/fixtures/lever/postings_hosted_url_only.json`` is a single
matching posting with no ``applyUrl`` key, proving ``registration_url``
falls back to ``hostedUrl``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from partner_scrape.adapters import run
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.lever import DEFAULT_API_BASE, LeverAdapter
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Provenance
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "lever"

COMPANY = "fixtureco"
POSTINGS_URL = f"{DEFAULT_API_BASE}/{COMPANY}?mode=json"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _response(body: str, status: int = 200) -> FetchResponse:
    return FetchResponse(url="", status=status, headers={}, body=body)


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.

    A URL absent from ``responses`` raises ``KeyError`` -- a loud
    failure if the adapter under test fetches something it shouldn't.
    """

    responses: dict[str, FetchResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        return self.responses[url]


def _source(company: str = COMPANY, location_keywords: list[str] | None = None) -> SourceConfig:
    config: dict = {"company": company}
    if location_keywords is not None:
        config["location_keywords"] = location_keywords
    return SourceConfig(
        source_id="fixture_co",
        org_name="Fixture Co",
        adapter_type="lever",
        config=config,
    )


def _fetcher(fixture_name: str = "postings.json") -> FixtureFetcher:
    return FixtureFetcher({POSTINGS_URL: _response(_read_fixture(fixture_name))})


class TestDiscover:
    def test_discover_returns_exactly_one_ref_for_the_postings_url(self):
        adapter = LeverAdapter()

        refs = adapter.discover(_source(), FixtureFetcher({}))

        assert [r.url for r in refs] == [POSTINGS_URL]

    def test_discover_honors_an_api_base_override(self):
        adapter = LeverAdapter()
        source = SourceConfig(
            source_id="fixture_co",
            org_name="Fixture Co",
            adapter_type="lever",
            config={"company": COMPANY, "api_base": "https://example.org/custom/postings"},
        )

        refs = adapter.discover(source, FixtureFetcher({}))

        assert [r.url for r in refs] == [f"https://example.org/custom/postings/{COMPANY}?mode=json"]

    def test_missing_company_raises(self):
        adapter = LeverAdapter()
        source = SourceConfig(
            source_id="fixture_co",
            org_name="Fixture Co",
            adapter_type="lever",
            config={},
        )

        try:
            adapter.discover(source, FixtureFetcher({}))
        except KeyError:
            pass
        else:
            raise AssertionError("expected KeyError for missing company")


class TestFieldMapping:
    def test_matching_posting_maps_all_documented_fields(self):
        events = run(_source(), _fetcher())

        assert len(events) == 1
        intern = events[0]
        assert intern.title == "Robotics Software Associate"
        assert intern.kind == "internship"
        assert intern.source_id == "fixture_co"
        assert intern.external_id == "1a2b3c4d-0001-4a1a-9c1a-000000000001"
        assert intern.start == datetime.fromtimestamp(1780329000000 / 1000, tz=timezone.utc)
        assert intern.location == "San Diego, CA"
        assert (
            intern.description
            == "Join our robotics software team for a hands-on internship building "
            "autonomous systems for San Diego Bay operations."
        )

    def test_apply_url_is_preferred_over_hosted_url_when_both_present(self):
        events = run(_source(), _fetcher())

        intern = events[0]
        assert intern.registration_url == (
            "https://jobs.lever.co/fixtureco/1a2b3c4d-0001-4a1a-9c1a-000000000001/apply"
        )

    def test_hosted_url_used_when_apply_url_absent(self):
        events = run(_source(), _fetcher("postings_hosted_url_only.json"))

        assert len(events) == 1
        intern = events[0]
        assert intern.registration_url == (
            "https://jobs.lever.co/fixtureco/1a2b3c4d-0006-4a1a-9c1a-000000000006"
        )

    def test_matching_posting_gets_classification_defaults_and_no_cost(self):
        events = run(_source(), _fetcher())

        intern = events[0]
        assert intern.age_grade_level == ["Grades 9-12", "Undergraduate"]
        assert intern.time_of_day == ["All Day"]
        assert intern.cost == ""
        assert intern.cost_range == ""
        assert "cost" not in intern.field_provenance
        assert "cost_range" not in intern.field_provenance

    def test_every_field_the_adapter_sets_has_lever_provenance_at_full_confidence(self):
        events = run(_source(), _fetcher())

        intern = events[0]
        assert intern.field_provenance
        for prov in intern.field_provenance.values():
            assert prov == Provenance(source="lever", confidence=1.0)


class TestCommitmentBasedInternshipSignal:
    def test_posting_kept_via_commitment_field_despite_non_internship_title(self):
        """"Robotics Software Associate" has no internship keyword in its
        title -- it only matches because ``categories.commitment`` is
        "Internship" (SUC-002's stronger-than-title-regex signal).
        """
        events = run(_source(), _fetcher())

        titles = {e.title for e in events}
        assert titles == {"Robotics Software Associate"}


class TestTopLevelArrayShape:
    def test_extract_parses_a_bare_top_level_array_not_a_jobs_wrapper(self):
        """The one shape difference from every other adapter in this
        codebase: Lever's response is a bare JSON array, not
        ``{"jobs": [...]}``.
        """
        adapter = LeverAdapter()
        raw = RawResponse(
            ref=EventRef(url=POSTINGS_URL), status=200, body=_read_fixture("postings.json")
        )

        events = list(adapter.extract(raw, _source()))

        assert len(events) == 1


class TestFiltering:
    def test_only_the_internship_stem_san_diego_posting_survives_under_default_keywords(self):
        events = run(_source(), _fetcher())

        titles = {e.title for e in events}
        assert titles == {"Robotics Software Associate"}

    def test_full_time_san_diego_posting_is_dropped(self):
        events = run(_source(), _fetcher())
        assert "Senior Backend Engineer" not in {e.title for e in events}

    def test_intern_in_another_city_is_dropped(self):
        events = run(_source(), _fetcher())
        assert "Data Science Intern" not in {e.title for e in events}

    def test_non_stem_san_diego_intern_is_dropped(self):
        events = run(_source(), _fetcher())
        assert "Marketing Intern" not in {e.title for e in events}


class TestLocationKeywordsOverride:
    def test_override_widens_the_match_set_with_no_code_change(self):
        source = _source(location_keywords=["Austin"])

        events = run(source, _fetcher())

        titles = {e.title for e in events}
        assert titles == {"Data Science Intern"}


class TestMalformedRecordIsolation:
    def test_missing_text_record_is_skipped_rest_of_response_survives(self):
        events = run(_source(), _fetcher())

        # 5 records in the fixture: 1 missing text (skipped), 3 filtered
        # out by classify_posting, 1 kept.
        assert len(events) == 1
        assert all(e.title for e in events)


class TestEmptyResponse:
    def test_empty_postings_list_yields_zero_events_and_no_exception(self):
        events = run(_source(), _fetcher("postings_empty.json"))
        assert events == []


class TestExtractRobustness:
    def test_non_200_status_returns_no_events_without_raising(self):
        adapter = LeverAdapter()
        raw = RawResponse(ref=EventRef(url=POSTINGS_URL), status=500, body="")

        assert list(adapter.extract(raw, _source())) == []

    def test_unparseable_json_body_returns_no_events_without_raising(self):
        adapter = LeverAdapter()
        raw = RawResponse(ref=EventRef(url=POSTINGS_URL), status=200, body="not json {")

        assert list(adapter.extract(raw, _source())) == []

    def test_unexpected_json_shape_returns_no_events_without_raising(self):
        """An object wrapper (Greenhouse/TEC's shape) is *not* Lever's shape."""
        adapter = LeverAdapter()
        raw = RawResponse(ref=EventRef(url=POSTINGS_URL), status=200, body='{"jobs": []}')

        assert list(adapter.extract(raw, _source())) == []
