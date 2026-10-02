"""Tests for partner_scrape.config: environment-derived configuration."""

from pathlib import Path

import pytest

from partner_scrape import config


class TestCredentialError:
    """AC: CredentialError(RuntimeError) is a plain marker subclass, no
    new behavior -- sprint 023 ticket 001."""

    def test_is_a_runtime_error_subclass(self):
        assert issubclass(config.CredentialError, RuntimeError)

    def test_can_be_raised_and_caught_as_runtime_error(self):
        with pytest.raises(RuntimeError):
            raise config.CredentialError("boom")


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

    def test_raises_credential_error_specifically_when_unset(self, monkeypatch):
        # Sprint 023 ticket 001: the missing-key case raises the
        # dedicated CredentialError subclass, not just any RuntimeError
        # -- teams.pipeline.run_teams()'s new aggregate alert depends on
        # this exception type distinction.
        monkeypatch.delenv("TBA_KEY", raising=False)
        with pytest.raises(config.CredentialError):
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

    def test_raises_credential_error_specifically_when_unset(self, monkeypatch):
        # Sprint 023 ticket 001: the missing-key case raises the
        # dedicated CredentialError subclass, not just any RuntimeError
        # -- mirrors TestTbaApiKey's identical assertion.
        monkeypatch.delenv("ROBOTEVENTS_KEY", raising=False)
        with pytest.raises(config.CredentialError):
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


# -- Store factories (sprint 038 ticket 002) --------------------------------

import boto3
from moto import mock_aws

from partner_scrape.storage import LocalStore, S3Store

_DO_VARS = ("DO_SPACES_ENDPOINT", "DO_SPACES_ACCESS_KEY", "DO_SPACES_SECRET_KEY")


def _set_do_env(monkeypatch, endpoint="https://sfo3.digitaloceanspaces.com"):
    monkeypatch.setenv("DO_SPACES_ENDPOINT", endpoint)
    monkeypatch.setenv("DO_SPACES_ACCESS_KEY", "test-access")
    monkeypatch.setenv("DO_SPACES_SECRET_KEY", "test-secret")


class TestStoreDefaults:
    def test_cache_defaults_to_bucket(self, monkeypatch):
        monkeypatch.delenv("SCRAPE_CACHE_DIR")
        _set_do_env(monkeypatch)
        with mock_aws():
            store = config.get_scrape_cache_store()
        assert isinstance(store, S3Store)
        assert (store.bucket, store.prefix) == ("jtl-stem-ecosystem-scrape", "cache")

    def test_data_defaults_to_bucket(self, monkeypatch):
        monkeypatch.delenv("PARTNER_SCRAPE_DATA_DIR")
        _set_do_env(monkeypatch)
        with mock_aws():
            store = config.get_data_store()
        assert isinstance(store, S3Store)
        assert (store.bucket, store.prefix) == ("jtl-stem-ecosystem-scrape", "data")

    def test_empty_value_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("SCRAPE_CACHE_DIR", "")
        _set_do_env(monkeypatch)
        with mock_aws():
            assert isinstance(config.get_scrape_cache_store(), S3Store)


class TestExplicitLocations:
    def test_explicit_local_needs_no_credentials(self, monkeypatch, tmp_path):
        for name in _DO_VARS:
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path / "c"))
        monkeypatch.setenv("PARTNER_SCRAPE_DATA_DIR", str(tmp_path / "d"))
        assert isinstance(config.get_scrape_cache_store(), LocalStore)
        assert isinstance(config.get_data_store(), LocalStore)

    def test_explicit_s3_location(self, monkeypatch):
        _set_do_env(monkeypatch)
        monkeypatch.setenv("SCRAPE_CACHE_DIR", "s3://other-bucket/some/prefix")
        store = config.get_scrape_cache_store()
        assert (store.bucket, store.prefix) == ("other-bucket", "some/prefix")

    def test_s3_store_round_trips_under_moto(self, monkeypatch):
        # moto only intercepts AWS hosts, so use one (validation only
        # constrains digitaloceanspaces.com endpoints).
        _set_do_env(monkeypatch, "https://s3.us-east-1.amazonaws.com")
        monkeypatch.setenv("PARTNER_SCRAPE_DATA_DIR", "s3://jtl-stem-ecosystem-scrape/data")
        with mock_aws():
            boto3.client("s3", region_name="us-east-1").create_bucket(
                Bucket="jtl-stem-ecosystem-scrape"
            )
            store = config.get_data_store()
            store.write_json("sites.json", {"a": 1})
            assert store.read_json("sites.json") == {"a": 1}

    def test_client_is_shared_and_rebuilt_on_change(self, monkeypatch):
        _set_do_env(monkeypatch)
        monkeypatch.setenv("SCRAPE_CACHE_DIR", "s3://b/cache")
        first = config.get_scrape_cache_store().client
        assert config.get_scrape_cache_store().client is first
        monkeypatch.setenv("DO_SPACES_ACCESS_KEY", "rotated")
        assert config.get_scrape_cache_store().client is not first


class TestMissingCredentials:
    def test_names_all_missing_variables(self, monkeypatch):
        monkeypatch.delenv("SCRAPE_CACHE_DIR")
        for name in _DO_VARS:
            monkeypatch.delenv(name, raising=False)
        with pytest.raises(RuntimeError) as exc:
            config.get_scrape_cache_store()
        for name in _DO_VARS:
            assert name in str(exc.value)

    def test_names_only_the_missing_one(self, monkeypatch):
        monkeypatch.delenv("PARTNER_SCRAPE_DATA_DIR")
        _set_do_env(monkeypatch)
        monkeypatch.delenv("DO_SPACES_SECRET_KEY")
        with pytest.raises(RuntimeError) as exc:
            config.get_data_store()
        assert "DO_SPACES_SECRET_KEY" in str(exc.value)
        assert "DO_SPACES_ACCESS_KEY" not in str(exc.value)

    def test_empty_value_counts_as_missing(self, monkeypatch):
        monkeypatch.delenv("SCRAPE_CACHE_DIR")
        _set_do_env(monkeypatch)
        monkeypatch.setenv("DO_SPACES_ACCESS_KEY", "''")
        with pytest.raises(RuntimeError, match="DO_SPACES_ACCESS_KEY"):
            config.get_scrape_cache_store()


class TestEndpointValidation:
    @pytest.mark.parametrize(
        "endpoint",
        [
            "https://jtl-stem-ecosystem-scrape.sfo3.digitaloceanspaces.com",
            "https://sfo3.digitaloceanspaces.com/jtl-stem-ecosystem-scrape",
            "sfo3.digitaloceanspaces.com",
        ],
    )
    def test_rejects_bad_endpoint(self, monkeypatch, endpoint):
        monkeypatch.delenv("SCRAPE_CACHE_DIR")
        _set_do_env(monkeypatch, endpoint)
        with pytest.raises(RuntimeError, match="DO_SPACES_ENDPOINT"):
            config.get_scrape_cache_store()

    def test_bucket_qualified_message_is_actionable(self, monkeypatch):
        monkeypatch.delenv("SCRAPE_CACHE_DIR")
        _set_do_env(monkeypatch, "https://b.sfo3.digitaloceanspaces.com")
        with pytest.raises(RuntimeError, match=r"https://sfo3\.digitaloceanspaces\.com"):
            config.get_scrape_cache_store()

    def test_bad_endpoint_ignored_for_local_locations(self, monkeypatch):
        _set_do_env(monkeypatch, "https://b.sfo3.digitaloceanspaces.com")
        assert isinstance(config.get_scrape_cache_store(), LocalStore)


class TestRealBucketGuard:
    def test_real_bucket_without_moto_fails(self, monkeypatch):
        _set_do_env(monkeypatch)
        monkeypatch.delenv("SCRAPE_CACHE_DIR")
        with pytest.raises(pytest.fail.Exception, match="real bucket"):
            S3Store("jtl-stem-ecosystem-scrape", "cache", object())
