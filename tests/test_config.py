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


class TestTbaApiKey:
    """Mirrors TestLeagueSyncApiKey exactly -- get_tba_api_key() is a
    line-for-line copy of get_leaguesync_api_key() (ticket 011-003)."""

    def test_reads_configured_value(self, monkeypatch):
        monkeypatch.setenv("TBA_KEY", "abc123")
        assert config.get_tba_api_key() == "abc123"

    def test_strips_surrounding_single_quotes_and_whitespace(self, monkeypatch):
        # The assembled .env carries the value quoted, e.g.
        # TBA_KEY='abc123' -- matching LEAGUESYNC_API_KEY's convention.
        monkeypatch.setenv("TBA_KEY", "  'abc123'  ")
        assert config.get_tba_api_key() == "abc123"

    def test_strips_surrounding_double_quotes(self, monkeypatch):
        monkeypatch.setenv("TBA_KEY", '"abc123"')
        assert config.get_tba_api_key() == "abc123"

    def test_raises_when_unset(self, monkeypatch):
        monkeypatch.delenv("TBA_KEY", raising=False)
        with pytest.raises(RuntimeError):
            config.get_tba_api_key()

    def test_raises_when_empty_string(self, monkeypatch):
        monkeypatch.setenv("TBA_KEY", "")
        with pytest.raises(RuntimeError):
            config.get_tba_api_key()

    def test_raises_when_only_quotes(self, monkeypatch):
        monkeypatch.setenv("TBA_KEY", "''")
        with pytest.raises(RuntimeError):
            config.get_tba_api_key()


class TestTbaUrl:
    def test_default_url_when_unset(self, monkeypatch):
        monkeypatch.delenv("TBA_URL", raising=False)
        assert config.get_tba_url() == config.DEFAULT_TBA_URL

    def test_default_matches_module_constant(self):
        assert config.DEFAULT_TBA_URL == "https://www.thebluealliance.com"

    def test_override_via_environment(self, monkeypatch):
        monkeypatch.setenv("TBA_URL", "https://staging.example.org")
        assert config.get_tba_url() == "https://staging.example.org"


class TestRobotEventsApiKey:
    """Mirrors TestTbaApiKey exactly -- get_robotevents_api_key() is a
    line-for-line copy of get_tba_api_key() (sprint 016 ticket 004)."""

    def test_reads_configured_value(self, monkeypatch):
        monkeypatch.setenv("ROBOTEVENTS_KEY", "abc123")
        assert config.get_robotevents_api_key() == "abc123"

    def test_strips_surrounding_single_quotes_and_whitespace(self, monkeypatch):
        # The assembled .env carries the value quoted, e.g.
        # ROBOTEVENTS_KEY='abc123' -- matching TBA_KEY's convention.
        monkeypatch.setenv("ROBOTEVENTS_KEY", "  'abc123'  ")
        assert config.get_robotevents_api_key() == "abc123"

    def test_strips_surrounding_double_quotes(self, monkeypatch):
        monkeypatch.setenv("ROBOTEVENTS_KEY", '"abc123"')
        assert config.get_robotevents_api_key() == "abc123"

    def test_raises_when_unset(self, monkeypatch):
        monkeypatch.delenv("ROBOTEVENTS_KEY", raising=False)
        with pytest.raises(RuntimeError):
            config.get_robotevents_api_key()

    def test_raises_when_empty_string(self, monkeypatch):
        monkeypatch.setenv("ROBOTEVENTS_KEY", "")
        with pytest.raises(RuntimeError):
            config.get_robotevents_api_key()

    def test_raises_when_only_quotes(self, monkeypatch):
        monkeypatch.setenv("ROBOTEVENTS_KEY", "''")
        with pytest.raises(RuntimeError):
            config.get_robotevents_api_key()


class TestRobotEventsUrl:
    def test_default_url_when_unset(self, monkeypatch):
        monkeypatch.delenv("ROBOTEVENTS_URL", raising=False)
        assert config.get_robotevents_url() == config.DEFAULT_ROBOTEVENTS_URL

    def test_default_matches_module_constant(self):
        assert config.DEFAULT_ROBOTEVENTS_URL == "https://www.robotevents.com/api/v2"

    def test_override_via_environment(self, monkeypatch):
        monkeypatch.setenv("ROBOTEVENTS_URL", "https://staging.example.org")
        assert config.get_robotevents_url() == "https://staging.example.org"
