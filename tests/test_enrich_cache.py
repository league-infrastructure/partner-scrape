"""Tests for partner_scrape.enrich.cache: content_hash and EnrichmentCache.

Every test uses a tmp_path-based cache_dir (never the real configured
SCRAPE_CACHE_DIR), per sprint.md's testing policy for this sprint.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from partner_scrape.enrich.cache import EnrichmentCache, content_hash
from partner_scrape.enrich.llm_client import EnrichmentResult
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
