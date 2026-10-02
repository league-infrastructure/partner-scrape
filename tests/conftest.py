"""Shared fixtures: keep every test off the real DigitalOcean Spaces bucket."""

import os

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
    # No default location may point at the real home dir, CWD or repo:
    monkeypatch.setenv("SITE_DIR", str(tmp_path / "site"))
    monkeypatch.setenv("PARTNER_SCRAPE_EVENT_DB", str(tmp_path / "events.db"))
    monkeypatch.delenv("PARTNER_SCRAPE_REGISTRY_DIR", raising=False)
    config._s3_client = None


def pytest_addoption(parser):
    parser.addoption(
        "--run-bucket",
        action="store_true",
        default=False,
        help="run the opt-in tests that read the REAL bucket (also RUN_BUCKET_TESTS=1)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip `bucket`-marked tests (real bucket, read-only) unless opted in."""
    if config.getoption("--run-bucket") or os.environ.get("RUN_BUCKET_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="real-bucket test: pass --run-bucket or RUN_BUCKET_TESTS=1")
    for item in items:
        if "bucket" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _forbid_real_bucket(request, monkeypatch):
    """Fail any test that builds an S3Store for the real bucket outside moto.

    Tests marked `bucket` are the deliberate exception (opt-in, read-only).
    """
    if request.node.get_closest_marker("bucket"):
        return
    original = storage.S3Store.__init__

    def guarded(self, bucket, prefix, client):
        if bucket == REAL_BUCKET and not botocore_stubber.enabled:
            pytest.fail(
                f"test built an S3Store for the real bucket {REAL_BUCKET!r} "
                "without moto (mock_aws); use tmp_path locations or mock_aws."
            )
        original(self, bucket, prefix, client)

    monkeypatch.setattr(storage.S3Store, "__init__", guarded)
