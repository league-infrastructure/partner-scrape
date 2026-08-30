"""Tests for partner_scrape.teams.sponsor_cache: content_hash and
SponsorCache.

Every test uses a tmp_path-based cache_dir (never the real configured
SCRAPE_CACHE_DIR), mirroring `tests/test_enrich_cache.py`'s testing
policy.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from partner_scrape.teams.sponsor_cache import _CACHE_SCHEMA_VERSION, SponsorCache, content_hash
from partner_scrape.teams.sponsor_llm import SponsorExtractionResult

SPONSOR_CACHE_MODULE_PATH = Path(__file__).resolve().parents[2] / "partner_scrape" / "teams" / "sponsor_cache.py"


# ---------------------------------------------------------------------
# Zero imports from partner_scrape.enrich (AC)
# ---------------------------------------------------------------------


class TestNoForbiddenImports:
    def test_sponsor_cache_module_imports_nothing_from_partner_scrape_enrich(self):
        tree = ast.parse(SPONSOR_CACHE_MODULE_PATH.read_text(), filename=str(SPONSOR_CACHE_MODULE_PATH))
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders.extend(
                    alias.name for alias in node.names if alias.name.startswith("partner_scrape.enrich")
                )
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("partner_scrape.enrich"):
                    offenders.append(node.module)
        assert offenders == []


# ---------------------------------------------------------------------
# content_hash
# ---------------------------------------------------------------------


class TestContentHash:
    def test_same_candidate_list_hashes_identically(self):
        a = ["Qualcomm", "Nordson"]
        b = ["Qualcomm", "Nordson"]

        assert content_hash(a) == content_hash(b)

    def test_different_candidate_list_changes_the_hash(self):
        a = ["Qualcomm", "Nordson"]
        b = ["Qualcomm", "Viasat"]

        assert content_hash(a) != content_hash(b)

    def test_different_order_changes_the_hash(self):
        """gather_sponsor_candidates() returns a deterministic,
        discovery-ordered list for an unchanged page, so order-sensitivity
        is not a real-world false-miss risk -- but the hash must still be
        a straightforward, unambiguous function of its exact input."""
        a = ["Qualcomm", "Nordson"]
        b = ["Nordson", "Qualcomm"]

        assert content_hash(a) != content_hash(b)

    def test_empty_candidate_list_hashes_consistently(self):
        assert content_hash([]) == content_hash([])


# ---------------------------------------------------------------------
# SponsorCache round-trip
# ---------------------------------------------------------------------


class TestSponsorCacheLookupMiss:
    def test_lookup_returns_none_when_no_entry_exists(self, tmp_path):
        cache = SponsorCache(cache_dir=tmp_path)

        assert cache.lookup("ftc-12499", ["Qualcomm"]) is None


class TestSponsorCacheRoundTrip:
    def test_store_then_lookup_returns_an_equivalent_result(self, tmp_path):
        cache = SponsorCache(cache_dir=tmp_path)
        result = SponsorExtractionResult(confirmed_sponsors=["Qualcomm"])

        cache.store("ftc-12499", ["Qualcomm", "Wix"], result)
        looked_up = cache.lookup("ftc-12499", ["Qualcomm", "Wix"])

        assert looked_up == result

    def test_lookup_misses_when_candidate_list_changes(self, tmp_path):
        cache = SponsorCache(cache_dir=tmp_path)
        cache.store("ftc-12499", ["Qualcomm"], SponsorExtractionResult(confirmed_sponsors=["Qualcomm"]))

        assert cache.lookup("ftc-12499", ["Qualcomm", "Nordson"]) is None

    def test_distinct_team_ids_do_not_collide_even_with_the_same_candidates(self, tmp_path):
        cache = SponsorCache(cache_dir=tmp_path)
        candidates = ["Qualcomm"]
        result_a = SponsorExtractionResult(confirmed_sponsors=["Qualcomm"])
        result_b = SponsorExtractionResult(confirmed_sponsors=[])

        cache.store("ftc-12499", candidates, result_a)
        cache.store("ftc-99999", candidates, result_b)

        assert cache.lookup("ftc-12499", candidates) == result_a
        assert cache.lookup("ftc-99999", candidates) == result_b

    def test_store_overwrites_a_prior_entry_for_the_same_key(self, tmp_path):
        cache = SponsorCache(cache_dir=tmp_path)
        candidates = ["Qualcomm"]
        cache.store("ftc-12499", candidates, SponsorExtractionResult(confirmed_sponsors=[]))
        cache.store("ftc-12499", candidates, SponsorExtractionResult(confirmed_sponsors=["Qualcomm"]))

        assert cache.lookup("ftc-12499", candidates).confirmed_sponsors == ["Qualcomm"]

    def test_entry_is_persisted_as_a_file_under_cache_dir(self, tmp_path):
        cache = SponsorCache(cache_dir=tmp_path)
        cache.store("ftc-12499", ["Qualcomm"], SponsorExtractionResult(confirmed_sponsors=["Qualcomm"]))

        written = list((tmp_path / "sponsor_extraction_cache").glob("*.json"))
        assert len(written) == 1


class TestSponsorCacheDefaultsToConfiguredCacheDir:
    def test_cache_dir_defaults_to_config_scrape_cache_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))

        cache = SponsorCache()

        assert cache.cache_dir == tmp_path


# ---------------------------------------------------------------------
# Cache schema versioning, mirroring enrich/cache.py's precedent.
# ---------------------------------------------------------------------


class TestCacheSchemaVersion:
    def test_a_fresh_entry_is_written_with_the_current_schema_version(self, tmp_path):
        cache = SponsorCache(cache_dir=tmp_path)
        cache.store("ftc-12499", ["Qualcomm"], SponsorExtractionResult(confirmed_sponsors=["Qualcomm"]))

        [written] = list((tmp_path / "sponsor_extraction_cache").glob("*.json"))
        entry = json.loads(written.read_text())

        assert entry["schema_version"] == _CACHE_SCHEMA_VERSION

    def test_entry_missing_schema_version_key_is_a_miss_not_a_deserialization_error(self, tmp_path):
        cache = SponsorCache(cache_dir=tmp_path)
        candidates = ["Qualcomm"]
        cache.store("ftc-12499", candidates, SponsorExtractionResult(confirmed_sponsors=["Qualcomm"]))

        [written] = list((tmp_path / "sponsor_extraction_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        del entry["schema_version"]
        written.write_text(json.dumps(entry))

        assert cache.lookup("ftc-12499", candidates) is None

    def test_entry_with_a_stale_schema_version_is_a_miss(self, tmp_path):
        cache = SponsorCache(cache_dir=tmp_path)
        candidates = ["Qualcomm"]
        cache.store("ftc-12499", candidates, SponsorExtractionResult(confirmed_sponsors=["Qualcomm"]))

        [written] = list((tmp_path / "sponsor_extraction_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        entry["schema_version"] = _CACHE_SCHEMA_VERSION - 1
        written.write_text(json.dumps(entry))

        assert cache.lookup("ftc-12499", candidates) is None

    def test_a_re_stored_entry_after_a_miss_is_a_hit_on_the_next_lookup(self, tmp_path):
        cache = SponsorCache(cache_dir=tmp_path)
        candidates = ["Qualcomm"]

        cache.store("ftc-12499", candidates, SponsorExtractionResult(confirmed_sponsors=[]))
        [written] = list((tmp_path / "sponsor_extraction_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        del entry["schema_version"]
        written.write_text(json.dumps(entry))
        assert cache.lookup("ftc-12499", candidates) is None  # forces the one-time miss

        cache.store("ftc-12499", candidates, SponsorExtractionResult(confirmed_sponsors=["Qualcomm"]))

        assert cache.lookup("ftc-12499", candidates).confirmed_sponsors == ["Qualcomm"]
