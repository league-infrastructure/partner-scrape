"""Tests for `partner_scrape.storage`: LocalStore and S3Store (moto, offline)."""

import boto3
import pytest
from moto import mock_aws

from partner_scrape.storage import LocalStore, S3Store, store_from_location

BUCKET = "test-bucket"


@pytest.fixture(params=["local", "s3"])
def store(request, tmp_path):
    if request.param == "local":
        yield LocalStore(tmp_path / "root")
    else:
        with mock_aws():
            client = boto3.client("s3", region_name="us-east-1")
            client.create_bucket(Bucket=BUCKET)
            yield S3Store(BUCKET, "pfx", client)


def test_missing_key_reads_none(store):
    assert store.read_bytes("a/b.json") is None
    assert store.read_text("a/b.json") is None
    assert store.read_json("a/b.json") is None
    assert store.exists("a/b.json") is False


def test_bytes_round_trip(store):
    store.write_bytes("img/x.png", b"\x89PNG\x00", "image/png")
    assert store.read_bytes("img/x.png") == b"\x89PNG\x00"
    assert store.exists("img/x.png") is True


def test_text_and_json_round_trip(store):
    store.write_text("n/t.txt", "héllo")
    assert store.read_text("n/t.txt") == "héllo"
    store.write_json("n/j.json", {"a": [1, 2], "b": "é"})
    assert store.read_json("n/j.json") == {"a": [1, 2], "b": "é"}
    assert store.read_text("n/j.json").startswith('{\n  "a"')  # indent=2


def test_overwrite(store):
    store.write_text("k", "one")
    store.write_text("k", "two")
    assert store.read_text("k") == "two"


def test_list_by_prefix(store):
    for k in ("hosts/a.json", "hosts/b.json", "programs/c.json"):
        store.write_json(k, {})
    assert store.list("hosts/") == ["hosts/a.json", "hosts/b.json"]
    assert store.list() == ["hosts/a.json", "hosts/b.json", "programs/c.json"]
    assert store.list("nope/") == []


def test_local_creates_parent_dirs_and_leaves_no_tmp(tmp_path):
    s = LocalStore(tmp_path / "r")
    s.write_text("deep/er/f.txt", "x")
    assert (tmp_path / "r" / "deep" / "er" / "f.txt").read_text() == "x"
    assert not list((tmp_path / "r").rglob("*.tmp"))


def test_local_write_failure_cleans_tmp_and_raises(tmp_path):
    s = LocalStore(tmp_path)
    (tmp_path / "blocker").write_text("file, not dir")
    with pytest.raises(RuntimeError):
        s.write_text("blocker/f.txt", "x")
    assert not list(tmp_path.rglob("*.tmp"))


@mock_aws
def test_s3_applies_prefix_and_content_type():
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket=BUCKET)
    s = S3Store(BUCKET, "cache/", client)
    s.write_json("hosts/a.json", {"x": 1})
    s.write_bytes("i.png", b"1", "image/png")
    head = client.head_object(Bucket=BUCKET, Key="cache/hosts/a.json")
    assert head["ContentType"] == "application/json"
    assert client.head_object(Bucket=BUCKET, Key="cache/i.png")["ContentType"] == "image/png"
    assert s.list("hosts/") == ["hosts/a.json"]


@mock_aws
def test_s3_empty_prefix():
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket=BUCKET)
    s = S3Store(BUCKET, "", client)
    s.write_text("a.txt", "x")
    assert client.get_object(Bucket=BUCKET, Key="a.txt")["Body"].read() == b"x"
    assert s.list() == ["a.txt"]


@mock_aws
def test_s3_other_errors_propagate():
    from botocore.exceptions import ClientError

    client = boto3.client("s3", region_name="us-east-1")  # no bucket created
    with pytest.raises(ClientError):
        S3Store("missing-bucket", "p", client).read_bytes("k")


@mock_aws
def test_store_from_location():
    client = boto3.client("s3", region_name="us-east-1")
    s3 = store_from_location("s3://bkt/some/prefix/", client)
    assert isinstance(s3, S3Store)
    assert (s3.bucket, s3.prefix) == ("bkt", "some/prefix")
    assert isinstance(store_from_location("/tmp/x"), LocalStore)
    from pathlib import Path

    assert isinstance(store_from_location(Path("rel/dir")), LocalStore)


def test_storage_does_not_import_config():
    import partner_scrape.storage as m

    assert "config" not in vars(m)
