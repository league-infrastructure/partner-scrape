"""Data output goes through the data Store (sprint 038, ticket 005).

Exercises the writers against an in-memory S3 bucket (moto, offline) and
checks the keys, Content-Type, formatting parity with a LocalStore, the
image exists-skip, and the yield-history round trip.
"""

from __future__ import annotations

import json
from datetime import date

import boto3
import pytest
from moto import mock_aws

from partner_scrape import config
from partner_scrape.export.ads import AdConfig, export_ads
from partner_scrape.export.images import EventImageDownloader, ImageFetchResponse
from partner_scrape.export.writer import export_opportunities
from partner_scrape.observability.snapshot import load_snapshot, save_snapshot
from partner_scrape.observability.yield_report import YieldReport
from partner_scrape.storage import LocalStore, S3Store
from tests.test_export import _opportunity
from tests.test_export_images import LARGE_JPEG, LARGE_PNG, _FakeFetcher, _ok

BUCKET = "test-bucket"
TODAY = date(2026, 7, 1)


@pytest.fixture
def s3():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


@pytest.fixture
def s3_store(s3):
    return S3Store(BUCKET, "data", s3)


def _content_type(s3, key: str) -> str:
    return s3.head_object(Bucket=BUCKET, Key=f"data/{key}")["ContentType"]


def test_opportunities_and_meta_keys_content_type_and_formatting(s3, s3_store, tmp_path):
    opps = [_opportunity()]
    export_opportunities(opps, today=TODAY, own_data_dir=s3_store)
    export_opportunities(opps, today=TODAY, own_data_dir=tmp_path)

    assert _content_type(s3, "opportunities.json") == "application/json"
    assert _content_type(s3, "scrape-meta.json") == "application/json"
    # Same bytes as the local tree: indent=1 / ensure_ascii=False kept.
    assert s3_store.read_bytes("opportunities.json") == (
        tmp_path / "opportunities.json"
    ).read_bytes()
    assert s3_store.read_text("opportunities.json").startswith('[\n {\n  "')
    assert "regions" in json.loads(s3_store.read_text("scrape-meta.json"))


def test_omitted_data_dir_uses_the_configured_data_store(s3, monkeypatch):
    monkeypatch.setenv("DO_SPACES_ENDPOINT", "https://s3.us-east-1.amazonaws.com")
    monkeypatch.setenv("DO_SPACES_ACCESS_KEY", "test-access")
    monkeypatch.setenv("DO_SPACES_SECRET_KEY", "test-secret")
    monkeypatch.setenv("PARTNER_SCRAPE_DATA_DIR", f"s3://{BUCKET}/data")
    monkeypatch.setattr(config, "_s3_client", None)

    export_ads([AdConfig(headline="h", body="b", link="https://x.org", logo_src="l.png")])

    body = s3.get_object(Bucket=BUCKET, Key="data/ads.json")["Body"].read()
    assert json.loads(body)[0]["headline"] == "h"
    assert _content_type(s3, "ads.json") == "application/json"


def test_yield_history_round_trips_through_the_store(s3, s3_store):
    assert load_snapshot(s3_store) == {}
    save_snapshot(s3_store, YieldReport(sources=[], regions=[], generated_at=None))

    assert _content_type(s3, "yield-history.json") == "application/json"
    assert load_snapshot(s3_store) == {"__regions__": {}}


class TestImagesInStore:
    def test_image_is_uploaded_under_prefix_with_image_content_type(self, s3, s3_store):
        url = "https://example.org/a.jpg"
        downloader = EventImageDownloader(s3_store, fetcher=_FakeFetcher({url: _ok(LARGE_JPEG)}))

        filename = downloader.download(url)

        assert s3_store.read_bytes(f"images/opportunities/{filename}") == LARGE_JPEG
        assert _content_type(s3, f"images/opportunities/{filename}") == "image/jpeg"

    def test_png_gets_png_content_type(self, s3, s3_store):
        url = "https://example.org/a.png"
        downloader = EventImageDownloader(s3_store, fetcher=_FakeFetcher({url: _ok(LARGE_PNG)}))

        filename = downloader.download(url)

        assert _content_type(s3, f"images/opportunities/{filename}") == "image/png"

    def test_existing_key_is_not_rewritten(self, s3_store):
        url = "https://example.org/a.jpg"
        first = EventImageDownloader(s3_store, fetcher=_FakeFetcher({url: _ok(LARGE_JPEG)}))
        filename = first.download(url)

        writes: list[str] = []
        real_write = s3_store.write_bytes
        s3_store.write_bytes = lambda key, *a, **k: (writes.append(key), real_write(key, *a, **k))
        # A fresh downloader has an empty in-memory dedup cache, so only
        # the store's exists() check can prevent the second upload.
        second = EventImageDownloader(s3_store, fetcher=_FakeFetcher({url: _ok(LARGE_JPEG)}))

        assert second.download(url) == filename
        assert writes == []

    def test_local_store_and_prefix_are_honored(self, tmp_path):
        url = "https://example.org/a.jpg"
        downloader = EventImageDownloader(
            LocalStore(tmp_path), "pics/", fetcher=_FakeFetcher({url: _ok(LARGE_JPEG)})
        )

        filename = downloader.download(url)

        assert (tmp_path / "pics" / filename).read_bytes() == LARGE_JPEG
