"""Tests for partner_scrape.adapters.program_cache: content_hash and
ProgramExtractionCache.

Every test uses a tmp_path-based cache_dir (never the real configured
SCRAPE_CACHE_DIR).
"""

from __future__ import annotations

import json
from typing import Any

from partner_scrape.adapters.program_cache import (
    _CACHE_SCHEMA_VERSION,
    ProgramExtractionCache,
    content_hash,
)
from partner_scrape.adapters.program_llm import ProgramExtractionResult


def _sample_result(**overrides: Any) -> ProgramExtractionResult:
    defaults: dict[str, Any] = dict(
        program_name="Fixture Research Experience for High School Students",
        audience_grades=["10th grade", "11th grade", "12th grade"],
        date_start="2026-12-01",
        date_end="2027-02-15",
        cost="$2,500 stipend",
        eligibility="San Diego County residents in grades 10-12.",
        is_open=True,
        opportunity_type="Work-based Learning",
    )
    defaults.update(overrides)
    return ProgramExtractionResult(**defaults)


# ---------------------------------------------------------------------
# content_hash
# ---------------------------------------------------------------------


class TestContentHash:
    def test_same_body_hashes_identically(self):
        assert content_hash("hello world") == content_hash("hello world")

    def test_different_body_changes_the_hash(self):
        assert content_hash("hello world") != content_hash("goodbye world")


# ---------------------------------------------------------------------
# ProgramExtractionCache round-trip (AC)
# ---------------------------------------------------------------------


class TestProgramExtractionCacheLookupMiss:
    def test_lookup_returns_none_for_an_unseen_url(self, tmp_path):
        cache = ProgramExtractionCache(cache_dir=tmp_path)

        assert cache.lookup("https://example.org/unseen", "body") is None


class TestProgramExtractionCacheRoundTrip:
    def test_store_then_lookup_returns_an_equivalent_result(self, tmp_path):
        cache = ProgramExtractionCache(cache_dir=tmp_path)
        url = "https://example.org/fre-hs"
        body = "the page body"
        result = _sample_result()

        cache.store(url, body, result)
        looked_up = cache.lookup(url, body)

        assert looked_up == result

    def test_changed_body_for_the_same_url_is_a_cache_miss(self, tmp_path):
        """AC: a changed body (different content hash) for the same URL is
        treated as a cache miss, not a stale hit."""
        cache = ProgramExtractionCache(cache_dir=tmp_path)
        url = "https://example.org/fre-hs"
        cache.store(url, "original body", _sample_result())

        assert cache.lookup(url, "a completely different body") is None

    def test_distinct_urls_do_not_collide(self, tmp_path):
        cache = ProgramExtractionCache(cache_dir=tmp_path)
        result_a = _sample_result(program_name="Program A")
        result_b = _sample_result(program_name="Program B")

        cache.store("https://example.org/a", "body a", result_a)
        cache.store("https://example.org/b", "body b", result_b)

        assert cache.lookup("https://example.org/a", "body a") == result_a
        assert cache.lookup("https://example.org/b", "body b") == result_b

    def test_store_overwrites_a_prior_entry_for_the_same_url(self, tmp_path):
        cache = ProgramExtractionCache(cache_dir=tmp_path)
        url = "https://example.org/fre-hs"
        body = "the page body"
        cache.store(url, body, _sample_result(program_name="First"))
        cache.store(url, body, _sample_result(program_name="Second"))

        assert cache.lookup(url, body).program_name == "Second"

    def test_entry_is_persisted_as_a_file_under_cache_dir(self, tmp_path):
        cache = ProgramExtractionCache(cache_dir=tmp_path)
        cache.store("https://example.org/fre-hs", "body", _sample_result())

        written = list((tmp_path / "program_extraction_cache").glob("*.json"))
        assert len(written) == 1


class TestProgramExtractionCacheLookupManyMiss:
    def test_lookup_many_returns_none_for_an_unseen_url(self, tmp_path):
        cache = ProgramExtractionCache(cache_dir=tmp_path)

        assert cache.lookup_many("https://example.org/unseen", "body") is None


class TestProgramExtractionCacheLookupManyRoundTrip:
    """The list-valued counterpart to
    ``TestProgramExtractionCacheRoundTrip`` above -- ticket 006 exception
    revision's ``lookup_many``/``store_many``, for ``program_page_multi``
    sources.
    """

    def test_store_many_then_lookup_many_returns_equivalent_results(self, tmp_path):
        cache = ProgramExtractionCache(cache_dir=tmp_path)
        url = "https://example.org/sio-internships"
        body = "the page body"
        results = [_sample_result(program_name="A"), _sample_result(program_name="B")]

        cache.store_many(url, body, results)
        looked_up = cache.lookup_many(url, body)

        assert looked_up == results

    def test_changed_body_for_the_same_url_is_a_cache_miss(self, tmp_path):
        cache = ProgramExtractionCache(cache_dir=tmp_path)
        url = "https://example.org/sio-internships"
        cache.store_many(url, "original body", [_sample_result()])

        assert cache.lookup_many(url, "a completely different body") is None

    def test_store_many_overwrites_a_prior_entry_for_the_same_url(self, tmp_path):
        cache = ProgramExtractionCache(cache_dir=tmp_path)
        url = "https://example.org/sio-internships"
        body = "the page body"
        cache.store_many(url, body, [_sample_result(program_name="First")])
        cache.store_many(url, body, [_sample_result(program_name="Second")])

        [result] = cache.lookup_many(url, body)
        assert result.program_name == "Second"

    def test_entry_is_persisted_as_a_file_under_cache_dir(self, tmp_path):
        cache = ProgramExtractionCache(cache_dir=tmp_path)
        cache.store_many("https://example.org/sio-internships", "body", [_sample_result()])

        written = list((tmp_path / "program_extraction_cache").glob("*.json"))
        assert len(written) == 1

    def test_empty_list_round_trips(self, tmp_path):
        cache = ProgramExtractionCache(cache_dir=tmp_path)
        url = "https://example.org/sio-internships"
        cache.store_many(url, "body", [])

        assert cache.lookup_many(url, "body") == []

    def test_a_stale_schema_version_is_a_miss(self, tmp_path):
        cache = ProgramExtractionCache(cache_dir=tmp_path)
        url = "https://example.org/sio-internships"
        body = "body"
        cache.store_many(url, body, [_sample_result()])

        [written] = list((tmp_path / "program_extraction_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        entry["schema_version"] = _CACHE_SCHEMA_VERSION - 1
        written.write_text(json.dumps(entry))

        assert cache.lookup_many(url, body) is None


class TestProgramExtractionCacheDefaultsToConfiguredCacheDir:
    def test_cache_dir_defaults_to_config_scrape_cache_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))

        cache = ProgramExtractionCache()

        assert cache.cache_dir == tmp_path


# ---------------------------------------------------------------------
# Cache schema versioning
# ---------------------------------------------------------------------


class TestCacheSchemaVersion:
    def test_a_fresh_entry_is_written_with_the_current_schema_version(self, tmp_path):
        cache = ProgramExtractionCache(cache_dir=tmp_path)
        cache.store("https://example.org/fre-hs", "body", _sample_result())

        [written] = list((tmp_path / "program_extraction_cache").glob("*.json"))
        entry = json.loads(written.read_text())

        assert entry["schema_version"] == _CACHE_SCHEMA_VERSION

    def test_entry_missing_schema_version_key_is_a_miss_not_a_deserialization_error(self, tmp_path):
        cache = ProgramExtractionCache(cache_dir=tmp_path)
        url = "https://example.org/fre-hs"
        body = "body"
        cache.store(url, body, _sample_result())

        [written] = list((tmp_path / "program_extraction_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        del entry["schema_version"]
        written.write_text(json.dumps(entry))

        assert cache.lookup(url, body) is None

    def test_entry_with_a_stale_schema_version_is_a_miss(self, tmp_path):
        cache = ProgramExtractionCache(cache_dir=tmp_path)
        url = "https://example.org/fre-hs"
        body = "body"
        cache.store(url, body, _sample_result())

        [written] = list((tmp_path / "program_extraction_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        entry["schema_version"] = _CACHE_SCHEMA_VERSION - 1
        written.write_text(json.dumps(entry))

        assert cache.lookup(url, body) is None

    def test_a_re_stored_entry_after_a_miss_is_a_hit_on_the_next_lookup(self, tmp_path):
        cache = ProgramExtractionCache(cache_dir=tmp_path)
        url = "https://example.org/fre-hs"
        body = "body"

        cache.store(url, body, _sample_result(program_name="stale"))
        [written] = list((tmp_path / "program_extraction_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        del entry["schema_version"]
        written.write_text(json.dumps(entry))
        assert cache.lookup(url, body) is None  # forces the one-time miss

        cache.store(url, body, _sample_result(program_name="fresh"))

        assert cache.lookup(url, body).program_name == "fresh"


# ---------------------------------------------------------------------
# Sprint 029 ticket 006: _CACHE_SCHEMA_VERSION bumps 2 -> 3 for
# registration_deadline's addition to ProgramExtractionResult.
# ---------------------------------------------------------------------


class TestSchemaVersionBumpForRegistrationDeadline:
    """AC: ``_CACHE_SCHEMA_VERSION`` is 3; a pre-bump (``schema_version:
    2``) cache entry -- written before ``registration_deadline`` existed
    on ``ProgramExtractionResult``, so its stored ``result`` has no such
    key -- is treated as a cache miss, not a deserialization error. This
    is load-bearing, not only tidy: tickets 001/002's real dry-runs
    already populated cache entries for this revision's affected
    competition sources under the old, now-corrected prompt; without
    this bump, a re-verification run would read those stale entries back
    and never invoke the corrected prompt at all.
    """

    def test_current_schema_version_is_3(self):
        assert _CACHE_SCHEMA_VERSION == 3

    def test_schema_version_2_entry_missing_registration_deadline_is_a_miss(self, tmp_path):
        cache = ProgramExtractionCache(cache_dir=tmp_path)
        url = "https://example.org/fre-hs"
        body = "body"
        cache.store(url, body, _sample_result())

        [written] = list((tmp_path / "program_extraction_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        entry["schema_version"] = 2
        # The pre-bump on-disk shape: no registration_deadline key at
        # all in the stored result (not even an empty string).
        del entry["result"]["registration_deadline"]
        written.write_text(json.dumps(entry))

        # A clean miss -- not a KeyError from _result_from_jsonable, since
        # the version check short-circuits before deserialization is
        # ever attempted.
        assert cache.lookup(url, body) is None

    def test_schema_version_2_entry_is_a_miss_for_lookup_many_too(self, tmp_path):
        cache = ProgramExtractionCache(cache_dir=tmp_path)
        url = "https://example.org/sio-internships"
        body = "body"
        cache.store_many(url, body, [_sample_result()])

        [written] = list((tmp_path / "program_extraction_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        entry["schema_version"] = 2
        for result in entry["results"]:
            del result["registration_deadline"]
        written.write_text(json.dumps(entry))

        assert cache.lookup_many(url, body) is None
