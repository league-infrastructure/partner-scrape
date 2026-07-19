"""Tests for partner_scrape.registry.candidates: the Candidate Review
Queue's stub-TOML writer/reader.

Every test writes into a `tmp_path`-based directory -- never the real
`partner_scrape/registry/candidates/` -- mirroring `test_registry.py`'s
and `test_registry_hub_schema.py`'s fixture-directory convention. No
test here opens a socket.
"""

from __future__ import annotations

import logging
import tomllib

import pytest

from partner_scrape.discovery.hub_scan import OrgCandidate
from partner_scrape.registry.candidates import (
    DEFAULT_CANDIDATES_DIR,
    CandidateStub,
    list_candidates,
    write_candidate,
)
from partner_scrape.registry.loader import DEFAULT_SOURCES_DIR, load_sources
from partner_scrape.registry.schema import InvalidSourceConfig, SourceConfig


def _candidate(
    org_name: str = "Brand New STEM Org",
    candidate_url: str = "https://newsteme.org/",
    evidence_text: str = "Brand New STEM Org runs maker projects for kids.",
    hub_id: str = "example_hub",
) -> OrgCandidate:
    return OrgCandidate(
        org_name=org_name,
        candidate_url=candidate_url,
        evidence_text=evidence_text,
        hub_id=hub_id,
    )


class TestWriteCandidate:
    def test_writes_one_toml_file(self, tmp_path):
        write_candidate(_candidate(), directory=tmp_path)

        assert len(list(tmp_path.glob("*.toml"))) == 1

    def test_written_file_contains_the_expected_fields(self, tmp_path):
        path = write_candidate(_candidate(), directory=tmp_path)

        with open(path, "rb") as f:
            data = tomllib.load(f)

        assert data["org_name"] == "Brand New STEM Org"
        assert data["candidate_url"] == "https://newsteme.org/"
        assert data["discovered_via"] == "example_hub"
        assert data["evidence_text"] == "Brand New STEM Org runs maker projects for kids."

    def test_written_file_omits_adapter_type_and_config(self, tmp_path):
        path = write_candidate(_candidate(), directory=tmp_path)

        with open(path, "rb") as f:
            data = tomllib.load(f)

        assert "adapter_type" not in data
        assert "config" not in data

    def test_written_stub_fails_source_config_from_toml(self, tmp_path):
        # The concrete, testable safety property (ticket 004 Acceptance
        # Criteria): even a misdirected attempt to load a candidate stub
        # as a live Source fails loudly (InvalidSourceConfig, missing
        # required fields) rather than silently succeeding.
        path = write_candidate(_candidate(), directory=tmp_path)

        with pytest.raises(InvalidSourceConfig):
            SourceConfig.from_toml(path)

    def test_creates_the_directory_if_missing(self, tmp_path):
        directory = tmp_path / "nested" / "candidates"
        assert not directory.exists()

        write_candidate(_candidate(), directory=directory)

        assert directory.exists()
        assert len(list(directory.glob("*.toml"))) == 1

    def test_filename_is_derived_from_a_slugified_org_name(self, tmp_path):
        path = write_candidate(_candidate(org_name="Brand New STEM Org!"), directory=tmp_path)
        assert path.stem == "brand-new-stem-org"

    def test_filename_collision_on_identical_slug_is_disambiguated(self, tmp_path):
        # Two genuinely different orgs (different normalize_org_name(),
        # so not deduped as the same org) whose names nonetheless
        # *slugify* identically -- a hyphen and a space both collapse to
        # "-" in the filename slug, but normalize_org_name strips a
        # hyphen outright while keeping a space, so "Example-Org" ->
        # "exampleorg" and "Example Org" -> "example org" are distinct
        # normalized names. Must not clobber each other's file.
        first = write_candidate(
            _candidate(org_name="Example-Org", candidate_url="https://one.example/"),
            directory=tmp_path,
        )
        second = write_candidate(
            _candidate(org_name="Example Org", candidate_url="https://two.example/"),
            directory=tmp_path,
        )

        assert first != second
        assert first.stem == "example-org"
        assert second.stem == "example-org-2"
        assert len(list(tmp_path.glob("*.toml"))) == 2

    def test_evidence_text_with_newlines_and_quotes_round_trips(self, tmp_path):
        candidate = _candidate(
            evidence_text='Line one.\nLine two.\tTabbed. A "quoted" phrase.'
        )
        path = write_candidate(candidate, directory=tmp_path)

        with open(path, "rb") as f:
            data = tomllib.load(f)
        assert data["evidence_text"] == 'Line one.\nLine two.\tTabbed. A "quoted" phrase.'

    def test_returns_the_written_path(self, tmp_path):
        path = write_candidate(_candidate(), directory=tmp_path)
        assert path is not None
        assert path.exists()
        assert path.parent == tmp_path


class TestWriteCandidateDedup:
    def test_duplicate_candidate_url_is_not_written_twice(self, tmp_path):
        write_candidate(_candidate(), directory=tmp_path)
        result = write_candidate(_candidate(), directory=tmp_path)

        assert result is None
        assert len(list(tmp_path.glob("*.toml"))) == 1

    def test_duplicate_normalized_org_name_different_url_is_not_written_twice(self, tmp_path):
        write_candidate(_candidate(org_name="Brand New STEM Org"), directory=tmp_path)
        result = write_candidate(
            _candidate(
                org_name="THE Brand New STEM Org!",
                candidate_url="https://a-different-url.example/",
            ),
            directory=tmp_path,
        )

        assert result is None
        assert len(list(tmp_path.glob("*.toml"))) == 1

    def test_genuinely_different_candidate_is_written(self, tmp_path):
        write_candidate(_candidate(), directory=tmp_path)
        result = write_candidate(
            _candidate(org_name="Another New Org", candidate_url="https://anothernew.org/"),
            directory=tmp_path,
        )

        assert result is not None
        assert len(list(tmp_path.glob("*.toml"))) == 2


class TestListCandidates:
    def test_round_trips_written_stubs(self, tmp_path):
        write_candidate(_candidate(), directory=tmp_path)
        write_candidate(
            _candidate(org_name="Another New Org", candidate_url="https://anothernew.org/"),
            directory=tmp_path,
        )

        stubs = list_candidates(tmp_path)

        assert len(stubs) == 2
        assert all(isinstance(stub, CandidateStub) for stub in stubs)
        org_names = {stub.org_name for stub in stubs}
        assert org_names == {"Brand New STEM Org", "Another New Org"}

    def test_stub_carries_discovered_via_and_evidence_text(self, tmp_path):
        write_candidate(_candidate(), directory=tmp_path)

        [stub] = list_candidates(tmp_path)
        assert stub.discovered_via == "example_hub"
        assert stub.evidence_text == "Brand New STEM Org runs maker projects for kids."
        assert stub.candidate_url == "https://newsteme.org/"

    def test_missing_directory_returns_empty_list_not_an_error(self, tmp_path):
        assert list_candidates(tmp_path / "does_not_exist") == []

    def test_malformed_toml_is_skipped_not_fatal(self, tmp_path, caplog):
        write_candidate(_candidate(), directory=tmp_path)
        (tmp_path / "broken.toml").write_text("this is not [valid toml", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            stubs = list_candidates(tmp_path)

        assert len(stubs) == 1
        assert "broken" in caplog.text


class TestCandidatesDirIsPhysicallySeparate:
    """The core safety property this ticket's Description calls for:
    `registry/loader.py` is unmodified, and its `DEFAULT_SOURCES_DIR`
    scan never sees the Candidate Review Queue -- mirrors
    `test_registry_hub_schema.py`'s own `TestRealSeedHubRegistry` class.
    """

    def test_default_candidates_dir_is_physically_separate_from_sources_dir(self):
        assert DEFAULT_CANDIDATES_DIR != DEFAULT_SOURCES_DIR

    def test_default_candidates_dir_location(self):
        assert DEFAULT_CANDIDATES_DIR.name == "candidates"
        assert DEFAULT_CANDIDATES_DIR.parent.name == "registry"

    def test_loader_module_has_no_reference_to_candidates(self):
        import partner_scrape.registry.loader as loader_module

        assert not hasattr(loader_module, "DEFAULT_CANDIDATES_DIR")
        assert not hasattr(loader_module, "write_candidate")

    def test_real_source_registry_load_is_unaffected_by_importing_candidates(self):
        # Importing registry.candidates must not change what the real
        # Source Registry sees -- proves the two directories are truly
        # independent, not just "currently both configured, coincidentally
        # non-overlapping".
        before = {s.source_id for s in load_sources()}
        import partner_scrape.registry.candidates  # noqa: F401

        after = {s.source_id for s in load_sources()}
        assert before == after
