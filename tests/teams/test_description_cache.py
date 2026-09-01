"""Tests for partner_scrape.teams.description_cache: content_hash and
DescriptionCache.

Every test uses a tmp_path-based cache_dir (never the real configured
SCRAPE_CACHE_DIR), mirroring `tests/teams/test_sponsor_cache.py`'s
testing policy exactly.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from partner_scrape.teams.description_cache import _CACHE_SCHEMA_VERSION, DescriptionCache, content_hash
from partner_scrape.teams.description_llm import DescriptionExtractionResult

DESCRIPTION_CACHE_MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "partner_scrape" / "teams" / "description_cache.py"
)


# ---------------------------------------------------------------------
# Zero imports from partner_scrape.enrich (AC)
# ---------------------------------------------------------------------


class TestNoForbiddenImports:
    def test_description_cache_module_imports_nothing_from_partner_scrape_enrich(self):
        tree = ast.parse(DESCRIPTION_CACHE_MODULE_PATH.read_text(), filename=str(DESCRIPTION_CACHE_MODULE_PATH))
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

    def test_description_cache_module_imports_nothing_from_sponsor_cache(self):
        """AC: mirrors sponsor_cache.py in shape, never by import."""
        tree = ast.parse(DESCRIPTION_CACHE_MODULE_PATH.read_text(), filename=str(DESCRIPTION_CACHE_MODULE_PATH))
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "sponsor_cache" in node.module:
                    offenders.append(node.module)
        assert offenders == []


# ---------------------------------------------------------------------
# content_hash
# ---------------------------------------------------------------------


class TestContentHash:
    def test_same_content_hashes_identically(self):
        a = "Poway High School's FTC robotics team."
        b = "Poway High School's FTC robotics team."

        assert content_hash(a) == content_hash(b)

    def test_different_content_changes_the_hash(self):
        a = "Poway High School's FTC robotics team."
        b = "A different team's description text."

        assert content_hash(a) != content_hash(b)

    def test_empty_content_hashes_consistently(self):
        assert content_hash("") == content_hash("")


# ---------------------------------------------------------------------
# DescriptionCache round-trip
# ---------------------------------------------------------------------


class TestDescriptionCacheLookupMiss:
    def test_lookup_returns_none_when_no_entry_exists(self, tmp_path):
        cache = DescriptionCache(cache_dir=tmp_path)

        assert cache.lookup("ftc-12499", "Some content.") is None


class TestDescriptionCacheRoundTrip:
    def test_store_then_lookup_returns_an_equivalent_result(self, tmp_path):
        cache = DescriptionCache(cache_dir=tmp_path)
        result = DescriptionExtractionResult(description="A robotics team from Poway.")

        cache.store("ftc-12499", "Poway High School's FTC robotics team.", result)
        looked_up = cache.lookup("ftc-12499", "Poway High School's FTC robotics team.")

        assert looked_up == result

    def test_lookup_misses_when_content_changes(self, tmp_path):
        cache = DescriptionCache(cache_dir=tmp_path)
        cache.store("ftc-12499", "Original content.", DescriptionExtractionResult(description="A team."))

        assert cache.lookup("ftc-12499", "Changed content.") is None

    def test_distinct_team_ids_do_not_collide_even_with_the_same_content(self, tmp_path):
        cache = DescriptionCache(cache_dir=tmp_path)
        content = "Shared homepage boilerplate."
        result_a = DescriptionExtractionResult(description="Team A's description.")
        result_b = DescriptionExtractionResult(description="")

        cache.store("ftc-12499", content, result_a)
        cache.store("ftc-99999", content, result_b)

        assert cache.lookup("ftc-12499", content) == result_a
        assert cache.lookup("ftc-99999", content) == result_b

    def test_store_overwrites_a_prior_entry_for_the_same_key(self, tmp_path):
        cache = DescriptionCache(cache_dir=tmp_path)
        content = "Some content."
        cache.store("ftc-12499", content, DescriptionExtractionResult(description=""))
        cache.store("ftc-12499", content, DescriptionExtractionResult(description="A robotics team."))

        assert cache.lookup("ftc-12499", content).description == "A robotics team."

    def test_entry_is_persisted_as_a_file_under_cache_dir(self, tmp_path):
        cache = DescriptionCache(cache_dir=tmp_path)
        cache.store("ftc-12499", "Some content.", DescriptionExtractionResult(description="A robotics team."))

        written = list((tmp_path / "description_extraction_cache").glob("*.json"))
        assert len(written) == 1


class TestDescriptionCacheDefaultsToConfiguredCacheDir:
    def test_cache_dir_defaults_to_config_scrape_cache_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))

        cache = DescriptionCache()

        assert cache.cache_dir == tmp_path


# ---------------------------------------------------------------------
# Cache schema versioning, mirroring sponsor_cache.py's precedent.
# ---------------------------------------------------------------------


class TestCacheSchemaVersion:
    def test_a_fresh_entry_is_written_with_the_current_schema_version(self, tmp_path):
        cache = DescriptionCache(cache_dir=tmp_path)
        cache.store("ftc-12499", "Some content.", DescriptionExtractionResult(description="A robotics team."))

        [written] = list((tmp_path / "description_extraction_cache").glob("*.json"))
        entry = json.loads(written.read_text())

        assert entry["schema_version"] == _CACHE_SCHEMA_VERSION

    def test_entry_missing_schema_version_key_is_a_miss_not_a_deserialization_error(self, tmp_path):
        cache = DescriptionCache(cache_dir=tmp_path)
        content = "Some content."
        cache.store("ftc-12499", content, DescriptionExtractionResult(description="A robotics team."))

        [written] = list((tmp_path / "description_extraction_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        del entry["schema_version"]
        written.write_text(json.dumps(entry))

        assert cache.lookup("ftc-12499", content) is None

    def test_entry_with_a_stale_schema_version_is_a_miss(self, tmp_path):
        cache = DescriptionCache(cache_dir=tmp_path)
        content = "Some content."
        cache.store("ftc-12499", content, DescriptionExtractionResult(description="A robotics team."))

        [written] = list((tmp_path / "description_extraction_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        entry["schema_version"] = _CACHE_SCHEMA_VERSION - 1
        written.write_text(json.dumps(entry))

        assert cache.lookup("ftc-12499", content) is None

    def test_a_re_stored_entry_after_a_miss_is_a_hit_on_the_next_lookup(self, tmp_path):
        cache = DescriptionCache(cache_dir=tmp_path)
        content = "Some content."

        cache.store("ftc-12499", content, DescriptionExtractionResult(description=""))
        [written] = list((tmp_path / "description_extraction_cache").glob("*.json"))
        entry = json.loads(written.read_text())
        del entry["schema_version"]
        written.write_text(json.dumps(entry))
        assert cache.lookup("ftc-12499", content) is None  # forces the one-time miss

        cache.store("ftc-12499", content, DescriptionExtractionResult(description="A robotics team."))

        assert cache.lookup("ftc-12499", content).description == "A robotics team."


# ---------------------------------------------------------------------
# Cache-hit skips the LLM entirely (AC)
# ---------------------------------------------------------------------


class TestCacheHitSkipsTheLlmEntirely:
    def test_a_cache_hit_for_the_same_team_id_and_content_hash_makes_zero_llm_calls(self, tmp_path):
        """AC: a hit returns the cached DescriptionExtractionResult
        without any LLM call. Uses FixtureDescriptionLLMClient to prove
        no call is made when the caller consults the cache first --
        mirrors the fixture cache-skip call-counting convention ticket
        004's orchestration will itself rely on."""
        from partner_scrape.teams.description_llm import FixtureDescriptionLLMClient

        cache = DescriptionCache(cache_dir=tmp_path)
        content = "Poway High School's FTC robotics team."
        stored = DescriptionExtractionResult(description="A robotics team from Poway.")
        cache.store("ftc-12499", content, stored)

        llm_client = FixtureDescriptionLLMClient(responses={})

        # Simulate the cache-first lookup pattern ticket 004's
        # orchestration will use: consult the cache, only call the LLM
        # client on a miss.
        cached = cache.lookup("ftc-12499", content)
        if cached is None:
            llm_client.summarize_description(content, {"team_id": "ftc-12499"})
            result = llm_client  # pragma: no cover - unreachable on a hit
        else:
            result = cached

        assert result == stored
        assert llm_client.calls == []
