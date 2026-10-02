"""Shared fixtures: keep every test off the real DigitalOcean Spaces bucket."""

import pytest
from moto.core.models import botocore_stubber

from partner_scrape import config, storage

REAL_BUCKET = "jtl-stem-ecosystem-scrape"


@pytest.fixture(autouse=True)
def _local_storage_locations(tmp_path, monkeypatch):
    """Point both storage locations at tmp_path so config never defaults to
    the real bucket. Tests wanting s3:// override these under moto."""
    monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("PARTNER_SCRAPE_DATA_DIR", str(tmp_path / "data"))
    config._s3_client = None


@pytest.fixture(autouse=True)
def _forbid_real_bucket(monkeypatch):
    """Fail any test that builds an S3Store for the real bucket outside moto."""
    original = storage.S3Store.__init__

    def guarded(self, bucket, prefix, client):
        if bucket == REAL_BUCKET and not botocore_stubber.enabled:
            pytest.fail(
                f"test built an S3Store for the real bucket {REAL_BUCKET!r} "
                "without moto (mock_aws); use tmp_path locations or mock_aws."
            )
        original(self, bucket, prefix, client)

    monkeypatch.setattr(storage.S3Store, "__init__", guarded)
