"""Tests for partner_scrape.enrich.cache: content_hash and EnrichmentCache.

Every test uses a tmp_path-based cache_dir (never the real configured
SCRAPE_CACHE_DIR), per sprint.md's testing policy for this sprint.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from partner_scrape.enrich.cache import _CACHE_SCHEMA_VERSION, EnrichmentCache, content_hash
from partner_scrape.enrich.llm_client import PROMPT_VERSION, EnrichmentResult
from partner_scrape.model import Event


def _sample_event(**overrides: Any) -> Event:
    defaults: dict[str, Any] = dict(
        source_id="fixture_org",
        title="Robotics Night",
        description="Hands-on robotics for kids.",
    )
    defaults.update(overrides)
    return Event(**defaults)


def _sample_result(**overrides: Any) -> EnrichmentResult:
    defaults: dict[str, Any] = dict(
        start=datetime(2026, 8, 15, 18, 0, 0),
        end=datetime(2026, 8, 15, 20, 0, 0),
        all_day=False,
        location="Fixture Library",
        cost="Free",
        registration_url="https://example.org/register",
        areas_of_interest=["Engineering"],
        age_grade_level=["Grades 6-8"],
        cost_range="Free",
        time_of_day=["Evening"],
        opportunity_type="Out-of-school Programs",
        relevant=True,
        relevance_reason="A hands-on youth robotics program.",
    )
    defaults.update(overrides)
    return EnrichmentResult(**defaults)


# ---------------------------------------------------------------------
# content_hash
# ---------------------------------------------------------------------


class TestContentHash:
    def test_same_enrichable_fields_hash_identically(self):
        a = _sample_event(title="Robotics Night", description="desc")
        b = _sample_event(title="Robotics Night", description="desc")

        assert content_hash(a) == content_hash(b)

    def test_different_title_changes_the_hash(self):
        a = _sample_event(title="Robotics Night")
        b = _sample_event(title="Robotics Day")

        assert content_hash(a) != content_hash(b)

    def test_different_start_changes_the_hash(self):
        a = _sample_event(title="Robotics Night")
        b = _sample_event(title="Robotics Night", start=datetime(2026, 8, 15, 18, 0))

        assert content_hash(a) != content_hash(b)

    def test_classification_fields_do_not_affect_the_hash(self):
        """areas_of_interest/age_grade_level/cost_range/time_of_day/relevant
        are fields *this cache itself* round-trips onto the Event -- they
        must never feed back into the hash, or reapplying a cached result
        would immediately invalidate its own cache entry."""
        a = _sample_event(title="Robotics Night")
        b = _sample_event(title="Robotics Night")
        b.set("areas_of_interest", ["Engineering"], source="llm_enrichment", confidence=0.7)
        b.set("relevant", True, source="llm_enrichment", confidence=0.7)

        assert content_hash(a) == content_hash(b)

    def test_field_provenance_bookkeeping_does_not_affect_the_hash(self):
        a = _sample_event(title="Robotics Night")
        b = _sample_event(title="Robotics Night")
        b.set("title", "Robotics Night", source="generic_html", confidence=0.5)

        assert content_hash(a) == content_hash(b)


# ---------------------------------------------------------------------
# EnrichmentCache round-trip
# ---------------------------------------------------------------------


class TestEnrichmentCacheLookupMiss:
    def test_lookup_returns_none_when_no_entry_exists(self, tmp_path):
        cache = EnrichmentCache(cache_dir=tmp_path)

        assert cache.lookup(_sample_event()) is None


class TestEnrichmentCacheRoundTrip:
    def test_store_then_lookup_returns_an_equivalent_result(self, tmp_path):
        cache = EnrichmentCache(cache_dir=tmp_path)
        event = _sample_event()
        result = _sample_result()

        cache.store(event, result)
        looked_up = cache.lookup(event)

        assert looked_up == result

    def test_lookup_misses_when_enrichable_content_changed_since_store(self, tmp_path):
        cache = EnrichmentCache(cache_dir=tmp_path)
        event = _sample_event(title="Robotics Night")
        cache.store(event, _sample_result())

        changed_event = _sample_event(title="Robotics Night", description="a new description")

        assert cache.lookup(changed_event) is None

    def test_distinct_identity_keys_do_not_collide(self, tmp_path):
        cache = EnrichmentCache(cache_dir=tmp_path)
        event_a = _sample_event(source_id="org_a", title="Robotics Night")
        event_b = _sample_event(source_id="org_b", title="Robotics Night")
        result_a = _sample_result(relevance_reason="org_a's event")
        result_b = _sample_result(relevance_reason="org_b's event")

        cache.store(event_a, result_a)
        cache.store(event_b, result_b)

        assert cache.lookup(event_a) == result_a
        assert cache.lookup(event_b) == result_b

    def test_store_overwrites_a_prior_entry_for_the_same_identity_key(self, tmp_path):
        cache = EnrichmentCache(cache_dir=tmp_path)
        event = _sample_event()
        cache.store(event, _sample_result(relevance_reason="first"))
        cache.store(event, _sample_result(relevance_reason="second"))

        assert cache.lookup(event).relevance_reason == "second"

    def test_entry_is_persisted_as_a_file_under_cache_dir(self, tmp_path):
        cache = EnrichmentCache(cache_dir=tmp_path)
        cache.store(_sample_event(), _sample_result())

        written = list((tmp_path / "enrichment_cache").glob("*.json"))
        assert len(written) == 1


class TestEnrichmentCacheDefaultsToConfiguredCacheDir:
    def test_cache_dir_defaults_to_config_scrape_cache_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))

        cache = EnrichmentCache()

        assert cache.cache_dir == tmp_path


# ---------------------------------------------------------------------
# Cache schema versioning (sprint 009, issue 13). content_hash covers
# only *input* fields, so it cannot detect an EnrichmentResult *output*
# shape change like adding opportunity_type -- an explicit schema
# version is the separate signal that catches that.
# ---------------------------------------------------------------------


class TestCacheSchemaVersion:
    def test_a_fresh_entry_is_written_with_the_current_schema_version(self, tmp_path):
        cache = EnrichmentCache(cache_dir=tmp_path)
        cache.store(_sample_event(), _sample_result())

        [written] = list((tmp_path / "enrichment_cache").glob("*.json"))
        entry = json.loads(written.read_text())

        assert entry["schema_version"] == _CACHE_SCHEMA_VERSION

    def test_entry_missing_schema_version_key_is_a_miss_not_a_deserialization_error(
        self, tmp_path
    ):
        """A pre-sprint-009 cache entry has no `schema_version` key at
        all (it predates the concept). `lookup()` must treat that as a
        miss -- forcing exactly one re-enrichment -- rather than raising
        while deserializing a `result` dict that lacks `opportunity_type`."""
        cache = EnrichmentCache(cache_dir=tmp_path)
        event = _sample_event()
        cache.store(event, _sample_result())

        [written] = list((tmp_path / "enrichment_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        del entry["schema_version"]
        del entry["result"]["opportunity_type"]  # pre-sprint-009 shape
        written.write_text(json.dumps(entry))

        assert cache.lookup(event) is None

    def test_entry_with_a_stale_schema_version_is_a_miss(self, tmp_path):
        cache = EnrichmentCache(cache_dir=tmp_path)
        event = _sample_event()
        cache.store(event, _sample_result())

        [written] = list((tmp_path / "enrichment_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        entry["schema_version"] = _CACHE_SCHEMA_VERSION - 1
        written.write_text(json.dumps(entry))

        assert cache.lookup(event) is None

    def test_a_re_stored_entry_after_a_miss_is_a_hit_on_the_next_lookup(self, tmp_path):
        """After the one-time re-enrichment a stale/missing-version entry
        forces, storing the fresh result must produce a normal cache hit
        on the following lookup -- not a repeated miss."""
        cache = EnrichmentCache(cache_dir=tmp_path)
        event = _sample_event()

        cache.store(event, _sample_result(relevance_reason="stale"))
        [written] = list((tmp_path / "enrichment_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        del entry["schema_version"]
        written.write_text(json.dumps(entry))
        assert cache.lookup(event) is None  # forces the one-time miss

        cache.store(event, _sample_result(relevance_reason="fresh"))

        assert cache.lookup(event).relevance_reason == "fresh"


# ---------------------------------------------------------------------
# Cache prompt versioning (sprint 014, issue 22). content_hash covers
# only *input* fields, never the prompt text, so it cannot detect a
# change to the prompt's own semantics (the all-ages gate widening) --
# an explicit, independent prompt_version is the signal that catches
# that, mirroring _CACHE_SCHEMA_VERSION's convention above but checked
# separately, never conflated with it.
# ---------------------------------------------------------------------


class TestCachePromptVersion:
    def test_a_fresh_entry_is_written_with_the_current_prompt_version(self, tmp_path):
        cache = EnrichmentCache(cache_dir=tmp_path)
        cache.store(_sample_event(), _sample_result())

        [written] = list((tmp_path / "enrichment_cache").glob("*.json"))
        entry = json.loads(written.read_text())

        assert entry["prompt_version"] == PROMPT_VERSION

    def test_entry_missing_prompt_version_key_is_a_miss_not_a_deserialization_error(
        self, tmp_path
    ):
        """A pre-sprint-014 cache entry has no `prompt_version` key at
        all (it predates the concept, and was written under the old,
        narrower K-12-only prompt). `lookup()` must treat that as a
        miss -- forcing exactly one re-enrichment -- the same shape as
        a missing `schema_version`, but checked independently."""
        cache = EnrichmentCache(cache_dir=tmp_path)
        event = _sample_event()
        cache.store(event, _sample_result())

        [written] = list((tmp_path / "enrichment_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        del entry["prompt_version"]  # pre-sprint-014 entry
        written.write_text(json.dumps(entry))

        assert cache.lookup(event) is None

    def test_entry_with_a_stale_prompt_version_is_a_miss(self, tmp_path):
        cache = EnrichmentCache(cache_dir=tmp_path)
        event = _sample_event()
        cache.store(event, _sample_result())

        [written] = list((tmp_path / "enrichment_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        entry["prompt_version"] = PROMPT_VERSION - 1
        written.write_text(json.dumps(entry))

        assert cache.lookup(event) is None

    def test_a_re_stored_entry_after_a_prompt_version_miss_is_a_hit_on_the_next_lookup(
        self, tmp_path
    ):
        """After the one-time re-enrichment a stale/missing prompt
        version forces, storing the fresh result must produce a normal
        cache hit on the following lookup -- not a repeated miss."""
        cache = EnrichmentCache(cache_dir=tmp_path)
        event = _sample_event()

        cache.store(event, _sample_result(relevance_reason="stale"))
        [written] = list((tmp_path / "enrichment_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        del entry["prompt_version"]
        written.write_text(json.dumps(entry))
        assert cache.lookup(event) is None  # forces the one-time miss

        cache.store(event, _sample_result(relevance_reason="fresh"))

        assert cache.lookup(event).relevance_reason == "fresh"


class TestSchemaAndPromptVersionAreCheckedIndependently:
    """AC: bumping one version without the other forces exactly the
    intended re-check, not both or neither."""

    def test_stale_schema_version_alone_is_a_miss_even_with_current_prompt_version(
        self, tmp_path
    ):
        cache = EnrichmentCache(cache_dir=tmp_path)
        event = _sample_event()
        cache.store(event, _sample_result())

        [written] = list((tmp_path / "enrichment_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        entry["schema_version"] = _CACHE_SCHEMA_VERSION - 1
        entry["prompt_version"] = PROMPT_VERSION
        written.write_text(json.dumps(entry))

        assert cache.lookup(event) is None

    def test_stale_prompt_version_alone_is_a_miss_even_with_current_schema_version(
        self, tmp_path
    ):
        cache = EnrichmentCache(cache_dir=tmp_path)
        event = _sample_event()
        cache.store(event, _sample_result())

        [written] = list((tmp_path / "enrichment_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        entry["schema_version"] = _CACHE_SCHEMA_VERSION
        entry["prompt_version"] = PROMPT_VERSION - 1
        written.write_text(json.dumps(entry))

        assert cache.lookup(event) is None

    def test_both_versions_current_is_a_hit(self, tmp_path):
        cache = EnrichmentCache(cache_dir=tmp_path)
        event = _sample_event()
        cache.store(event, _sample_result())

        [written] = list((tmp_path / "enrichment_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        entry["schema_version"] = _CACHE_SCHEMA_VERSION
        entry["prompt_version"] = PROMPT_VERSION
        written.write_text(json.dumps(entry))

        assert cache.lookup(event) is not None

    def test_both_versions_stale_is_a_miss(self, tmp_path):
        cache = EnrichmentCache(cache_dir=tmp_path)
        event = _sample_event()
        cache.store(event, _sample_result())

        [written] = list((tmp_path / "enrichment_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        entry["schema_version"] = _CACHE_SCHEMA_VERSION - 1
        entry["prompt_version"] = PROMPT_VERSION - 1
        written.write_text(json.dumps(entry))

        assert cache.lookup(event) is None
