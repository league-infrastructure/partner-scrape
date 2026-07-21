"""Tests for partner_scrape.config: environment-derived configuration."""

from pathlib import Path

import pytest

from partner_scrape import config


class TestScrapeCacheDir:
    def test_reads_configured_value(self, monkeypatch):
        monkeypatch.setenv("SCRAPE_CACHE_DIR", "/tmp/some-cache-dir")
        assert config.get_scrape_cache_dir() == Path("/tmp/some-cache-dir")

    def test_raises_when_unset(self, monkeypatch):
        monkeypatch.delenv("SCRAPE_CACHE_DIR", raising=False)
        with pytest.raises(RuntimeError):
            config.get_scrape_cache_dir()

    def test_raises_when_empty_string(self, monkeypatch):
        monkeypatch.setenv("SCRAPE_CACHE_DIR", "")
        with pytest.raises(RuntimeError):
            config.get_scrape_cache_dir()


class TestSiteDir:
    def test_default_site_dir_when_unset(self, monkeypatch):
        monkeypatch.delenv("SITE_DIR", raising=False)
        assert config.get_site_dir() == config.DEFAULT_SITE_DIR

    def test_default_site_dir_is_sibling_stem_ecosystem(self):
        assert config.DEFAULT_SITE_DIR.name == "stem-ecosystem"

    def test_override_via_environment(self, monkeypatch):
        monkeypatch.setenv("SITE_DIR", "/tmp/custom-site-dir")
        assert config.get_site_dir() == Path("/tmp/custom-site-dir")


class TestLeagueSyncApiKey:
    def test_reads_configured_value(self, monkeypatch):
        monkeypatch.setenv("LEAGUESYNC_API_KEY", "abc123")
        assert config.get_leaguesync_api_key() == "abc123"

    def test_strips_surrounding_single_quotes_and_whitespace(self, monkeypatch):
        # The assembled .env carries the value quoted, e.g.
        # LEAGUESYNC_API_KEY='8ac0ebe9...' -- confirmed live.
        monkeypatch.setenv("LEAGUESYNC_API_KEY", "  'abc123'  ")
        assert config.get_leaguesync_api_key() == "abc123"

    def test_strips_surrounding_double_quotes(self, monkeypatch):
        monkeypatch.setenv("LEAGUESYNC_API_KEY", '"abc123"')
        assert config.get_leaguesync_api_key() == "abc123"

    def test_raises_when_unset(self, monkeypatch):
        monkeypatch.delenv("LEAGUESYNC_API_KEY", raising=False)
        with pytest.raises(RuntimeError):
            config.get_leaguesync_api_key()

    def test_raises_when_empty_string(self, monkeypatch):
        monkeypatch.setenv("LEAGUESYNC_API_KEY", "")
        with pytest.raises(RuntimeError):
            config.get_leaguesync_api_key()

    def test_raises_when_only_quotes(self, monkeypatch):
        monkeypatch.setenv("LEAGUESYNC_API_KEY", "''")
        with pytest.raises(RuntimeError):
            config.get_leaguesync_api_key()


class TestLeagueSyncUrl:
    def test_default_url_when_unset(self, monkeypatch):
        monkeypatch.delenv("LEAGUESYNC_URL", raising=False)
        assert config.get_leaguesync_url() == "https://sync.jtlapp.net"

    def test_default_matches_module_constant(self):
        assert config.DEFAULT_LEAGUESYNC_URL == "https://sync.jtlapp.net"

    def test_override_via_environment(self, monkeypatch):
        monkeypatch.setenv("LEAGUESYNC_URL", "https://staging.example.org")
        assert config.get_leaguesync_url() == "https://staging.example.org"
