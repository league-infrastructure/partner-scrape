"""Tests for dev/verify_bucket.py.

Offline tests cover the production-data safety guards. The `bucket`-marked
tests read the REAL bucket (read-only) and are skipped unless opted in:

    set -a; source .env; set +a
    uv run pytest --run-bucket tests/dev/test_verify_bucket.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parent.parent.parent / "dev" / "verify_bucket.py"
_spec = importlib.util.spec_from_file_location("verify_bucket", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
verify_bucket = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = verify_bucket
_spec.loader.exec_module(verify_bucket)

BUCKET = verify_bucket.BUCKET


@pytest.mark.parametrize(
    "location",
    [
        f"s3://{BUCKET}/data",
        f"s3://{BUCKET}/data/",
        f"s3://{BUCKET}/data/sub",
        f"s3://{BUCKET}/cache",
        f"s3://{BUCKET}",
        f"s3://other-bucket/verify/x/data",
        "/tmp/local",
    ],
)
def test_live_or_foreign_data_locations_are_refused(location):
    with pytest.raises(verify_bucket.SafetyError):
        verify_bucket.validate_data_location(location)


def test_scratch_location_is_accepted():
    verify_bucket.validate_data_location(verify_bucket.scratch_location("20260101T000000Z"))


def test_guard_blocks_writes_to_live_data_prefix():
    from botocore.client import BaseClient

    original = BaseClient._make_api_call
    try:
        verify_bucket.guard_live_data(None)
        with pytest.raises(verify_bucket.SafetyError):
            BaseClient._make_api_call(
                object(), "PutObject", {"Bucket": BUCKET, "Key": "data/opportunities.json"}
            )
        with pytest.raises(verify_bucket.SafetyError):
            BaseClient._make_api_call(
                object(), "DeleteObjects",
                {"Bucket": BUCKET, "Delete": {"Objects": [{"Key": "data/x.json"}]}},
            )
    finally:
        BaseClient._make_api_call = original


@pytest.fixture
def real_client():
    from partner_scrape import config

    config._s3_client = None
    return config._get_s3_client()


@pytest.mark.bucket
def test_real_bucket_counts(real_client):
    assert verify_bucket.check_counts(real_client) == []


@pytest.mark.bucket
def test_real_bucket_byte_identity(real_client):
    assert verify_bucket.check_byte_identity(real_client) == []
