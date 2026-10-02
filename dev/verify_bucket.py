#!/usr/bin/env python3
"""Opt-in verification of the code against the REAL DigitalOcean Spaces bucket.

Run by hand (sprint 038 ticket 008), never from the default test suite
(the ``bucket``-marked pytest tests wrap :func:`check_counts` and
:func:`check_byte_identity` and are skipped unless ``--run-bucket`` /
``RUN_BUCKET_TESTS=1``). Credentials come from the process environment
(``DO_SPACES_ENDPOINT/ACCESS_KEY/SECRET_KEY``, assembled into ``.env`` by
``dotconfig load prod``):

    set -a; source .env; set +a
    uv run python dev/verify_bucket.py check
    uv run python dev/verify_bucket.py run --source coastalrootsfarm

``check`` is strictly read-only: object counts per ``cache/`` folder and
for ``data/`` against expectations, plus byte-identity of every local
``data/`` file (ETag == md5, no download) and a sample of cache objects
(downloaded, parsed as JSON).

``run`` executes ONE source of the real pipeline in-process against the
real ``cache/`` prefix and counts cache hits/misses, HTTP fetches and
LLM calls. PRODUCTION-DATA SAFETY: the live ``data/`` prefix is never
used as the output location. The run's data Store is always a scratch
``verify/<timestamp>/data`` prefix (the script refuses a user-supplied
location that is, or is under, ``data/``), every write/delete in the
process is guarded against the live ``data/`` prefix, the live
``data/opportunities.json`` ETag/LastModified is compared before and
after, and the scratch prefix is deleted afterwards (``--keep-scratch``
to inspect it). Writes to ``cache/`` are additive and small (one source).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
BUCKET = "jtl-stem-ecosystem-scrape"
CACHE_PREFIX = "cache/"
DATA_PREFIX = "data/"
LIVE_MARKER_KEY = "data/opportunities.json"

#: Object counts per ``cache/`` folder at upload time (sprint 038, 22,852
#: objects). The local cache tree no longer exists, so these are recorded
#: baselines; runs only ever ADD objects, hence ">=" in :func:`check_counts`.
#: ``--local-cache DIR`` compares exactly against a local tree instead.
EXPECTED_CACHE_MIN = {
    "enrichment": 17301,
    "hosts": 5113,
    "partner_log": 202,
    "sitemaps": 82,
    "programs": 67,
    "descriptions": 53,
    "sponsors": 34,
}
#: Local data tree (repo ``data/``, minus ``mirrors/``) is expected 1:1
#: under ``data/`` in the bucket.
LOCAL_DATA_DIR = REPO_ROOT / "data"
LOCAL_DATA_EXCLUDE = ("mirrors/",)


class SafetyError(RuntimeError):
    """An attempted operation would touch the live data/ prefix."""


# -- bucket access -----------------------------------------------------


def _client() -> Any:
    from partner_scrape import config

    return config._get_s3_client()


def list_objects(client: Any, prefix: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page in client.get_paginator("list_objects_v2").paginate(
        Bucket=BUCKET, Prefix=prefix
    ):
        out.extend(page.get("Contents", []))
    return out


def head(client: Any, key: str) -> dict[str, Any]:
    r = client.head_object(Bucket=BUCKET, Key=key)
    return {"etag": r["ETag"].strip('"'), "last_modified": str(r["LastModified"]),
            "size": r["ContentLength"]}


# -- check (read-only) -------------------------------------------------


def local_data_files(root: Path = LOCAL_DATA_DIR) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            if not rel.startswith(LOCAL_DATA_EXCLUDE):
                files[rel] = p
    return files


def check_counts(client: Any, local_cache: Path | None = None) -> list[str]:
    """Return a list of failure messages (empty == pass); prints a report."""
    failures: list[str] = []
    objs = list_objects(client, CACHE_PREFIX)
    by_folder = Counter(o["Key"][len(CACHE_PREFIX):].split("/")[0] for o in objs)
    print(f"cache/: {len(objs)} objects")
    for folder, minimum in EXPECTED_CACHE_MIN.items():
        have = by_folder.get(folder, 0)
        if local_cache is not None:
            want = sum(1 for p in (local_cache / folder).rglob("*") if p.is_file())
            ok, rule = have == want, f"== local {want}"
        else:
            ok, rule = have >= minimum, f">= {minimum}"
        print(f"  cache/{folder}: {have} (expected {rule}) {'ok' if ok else 'FAIL'}")
        if not ok:
            failures.append(f"cache/{folder}: {have} not {rule}")
    for folder in sorted(set(by_folder) - set(EXPECTED_CACHE_MIN)):
        print(f"  cache/{folder}: {by_folder[folder]} (unexpected folder)")
        failures.append(f"cache/{folder}: unexpected folder")

    data = {o["Key"][len(DATA_PREFIX):] for o in list_objects(client, DATA_PREFIX)}
    local = set(local_data_files())
    missing, extra = sorted(local - data), sorted(data - local)
    print(f"data/: {len(data)} objects; local data/ minus mirrors: {len(local)}")
    print(f"  missing from bucket: {len(missing)}; only in bucket: {len(extra)}")
    if missing:
        failures.append(f"data/: {len(missing)} local files missing in bucket, e.g. {missing[:3]}")
    if extra:
        failures.append(f"data/: {len(extra)} bucket-only objects, e.g. {extra[:3]}")
    return failures


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def check_byte_identity(client: Any, cache_sample: int = 25) -> list[str]:
    """Every local data file's md5 equals the bucket ETag (no download);
    a deterministic sample of cache objects is downloaded and parsed."""
    failures: list[str] = []
    etags = {
        o["Key"][len(DATA_PREFIX):]: o["ETag"].strip('"')
        for o in list_objects(client, DATA_PREFIX)
    }
    compared = mismatched = multipart = 0
    for rel, path in local_data_files().items():
        etag = etags.get(rel)
        if etag is None:
            continue  # reported by check_counts
        if "-" in etag:
            multipart += 1
            continue
        compared += 1
        if _md5(path) != etag:
            mismatched += 1
            failures.append(f"data/{rel}: local md5 != bucket ETag")
    print(f"data byte-identity (md5 vs ETag): compared {compared}, "
          f"mismatched {mismatched}, multipart-skipped {multipart}")

    keys = sorted(o["Key"] for o in list_objects(client, CACHE_PREFIX))
    step = max(1, len(keys) // cache_sample)
    sample = keys[::step][:cache_sample]
    bad = 0
    for key in sample:
        body = client.get_object(Bucket=BUCKET, Key=key)["Body"].read()
        try:
            json.loads(body)
        except ValueError:
            bad += 1
            failures.append(f"{key}: not valid JSON")
    print(f"cache sample: downloaded {len(sample)} objects, {bad} not valid JSON")
    return failures


# -- one-source real run ------------------------------------------------


def guard_live_data(client: Any) -> None:
    """Make every mutating call in this process refuse the live data/ prefix."""
    from botocore.client import BaseClient

    original = BaseClient._make_api_call

    def guarded(self, operation_name, api_params):
        if operation_name in {
            "PutObject", "DeleteObject", "DeleteObjects", "CopyObject",
            "CreateMultipartUpload", "UploadPart", "CompleteMultipartUpload",
        }:
            key = api_params.get("Key", "")
            if api_params.get("Bucket") == BUCKET and key.startswith(DATA_PREFIX):
                raise SafetyError(f"refusing {operation_name} on live key {key!r}")
            if operation_name == "DeleteObjects":
                for o in api_params.get("Delete", {}).get("Objects", []):
                    if o["Key"].startswith(DATA_PREFIX):
                        raise SafetyError(f"refusing DeleteObjects on live key {o['Key']!r}")
        return original(self, operation_name, api_params)

    BaseClient._make_api_call = guarded  # type: ignore[method-assign]


def scratch_location(ts: str) -> str:
    return f"s3://{BUCKET}/verify/{ts}/data"


def validate_data_location(location: str) -> None:
    """Refuse anything that is, or is under, the live data/ prefix."""
    parsed = urlparse(location)
    if parsed.scheme != "s3" or parsed.netloc != BUCKET:
        raise SafetyError(f"data location must be s3://{BUCKET}/verify/...: {location!r}")
    prefix = parsed.path.strip("/")
    if prefix == "data" or prefix.startswith("data/") or not prefix.startswith("verify/"):
        raise SafetyError(f"data location {location!r} is not a verify/ scratch prefix")


class Counters:
    def __init__(self) -> None:
        self.cache_reads: Counter[str] = Counter()   # "<folder>:hit|miss"
        self.cache_writes: Counter[str] = Counter()  # folder
        self.http: Counter[str] = Counter()          # status
        self.page_cache: Counter[str] = Counter()    # hit|miss
        self.llm_calls = 0
        self.written_keys: list[str] = []


def install_counters(c: Counters) -> None:
    from partner_scrape.fetch import cache as fetch_cache
    from partner_scrape.fetch.fetcher import UrllibFetcher
    from partner_scrape.storage import S3Store

    orig_read, orig_write = S3Store.read_bytes, S3Store.write_bytes

    def read_bytes(self, key):
        data = orig_read(self, key)
        if self.prefix == "cache":
            c.cache_reads[f"{key.split('/')[0]}:{'hit' if data is not None else 'miss'}"] += 1
        return data

    def write_bytes(self, key, data, content_type=None):
        orig_write(self, key, data, content_type)
        full = self._key(key)
        c.written_keys.append(full)
        if self.prefix == "cache":
            c.cache_writes[key.split("/")[0]] += 1

    S3Store.read_bytes, S3Store.write_bytes = read_bytes, write_bytes  # type: ignore[method-assign]

    orig_entry = fetch_cache.read_cache_entry

    def read_entry(cache, url):
        entry = orig_entry(cache, url)
        c.page_cache["hit" if entry is not None else "miss"] += 1
        return entry

    fetch_cache.read_cache_entry = read_entry

    orig_get = UrllibFetcher.get

    def get(self, url, headers=None):
        resp = orig_get(self, url, headers)
        c.http[str(resp.status)] += 1
        return resp

    UrllibFetcher.get = get  # type: ignore[method-assign]

    try:
        from anthropic.resources.messages import Messages

        orig_create = Messages.create

        def create(self, *a, **kw):
            c.llm_calls += 1
            return orig_create(self, *a, **kw)

        Messages.create = create  # type: ignore[method-assign]
    except ImportError:
        pass


def run_one_source(args: argparse.Namespace) -> list[str]:
    from partner_scrape import cli, config

    client = _client()
    guard_live_data(client)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    data_loc = args.data_location or scratch_location(ts)
    validate_data_location(data_loc)
    scratch_prefix = urlparse(data_loc).path.strip("/") + "/"

    os.environ["PARTNER_SCRAPE_DATA_DIR"] = data_loc
    os.environ["SCRAPE_CACHE_DIR"] = f"s3://{BUCKET}/cache"
    config._s3_client = None
    # Belt and braces: the data Store must resolve to the scratch prefix.
    resolved = config.get_data_store()
    if getattr(resolved, "prefix", None) != scratch_prefix.strip("/"):
        raise SafetyError(f"data store resolved to {getattr(resolved, 'prefix', None)!r}")

    before = head(client, LIVE_MARKER_KEY)
    live_before = {o["Key"]: (o["ETag"], str(o["LastModified"]))
                   for o in list_objects(client, DATA_PREFIX)}
    cache_before = {o["Key"]: o["ETag"] for o in list_objects(client, CACHE_PREFIX)}

    counters = Counters()
    install_counters(counters)
    argv = ["--source", args.source, "--verbose"]
    if args.site_dir:
        argv += ["--site-dir", args.site_dir]
    if args.no_enrich:
        argv.append("--no-enrich")
    print(f"running: partner-scrape {' '.join(argv)}\n  data -> {data_loc}\n  cache -> s3://{BUCKET}/cache")
    started = time.time()
    rc = cli.main(argv)
    elapsed = time.time() - started

    failures: list[str] = []
    if rc != 0:
        failures.append(f"pipeline exited {rc}")

    cache_after = {o["Key"]: o["ETag"] for o in list_objects(client, CACHE_PREFIX)}
    added = sorted(set(cache_after) - set(cache_before))
    changed = sorted(k for k in cache_before if k in cache_after and cache_before[k] != cache_after[k])
    removed = sorted(set(cache_before) - set(cache_after))
    live_after = {o["Key"]: (o["ETag"], str(o["LastModified"]))
                  for o in list_objects(client, DATA_PREFIX)}
    after = head(client, LIVE_MARKER_KEY)
    live_untouched = live_before == live_after and before == after
    scratch_keys = [o["Key"] for o in list_objects(client, scratch_prefix)]

    print(f"\n== results ({elapsed:.1f}s, exit {rc}) ==")
    print(f"page-cache lookups:  {dict(counters.page_cache)}")
    print(f"HTTP responses:      {dict(counters.http)}  (304 == revalidated cache hit)")
    print(f"cache store reads:   {dict(sorted(counters.cache_reads.items()))}")
    print(f"cache store writes:  {dict(sorted(counters.cache_writes.items()))}")
    print(f"LLM calls (Messages.create): {counters.llm_calls}")
    print(f"cache/ objects: +{len(added)} new, {len(changed)} content-changed, {len(removed)} removed")
    for k in added[:20]:
        print(f"  new: {k}")
    for k in changed[:20]:
        print(f"  changed: {k}")
    print(f"scratch output ({scratch_prefix}): {len(scratch_keys)} objects")
    print(f"live data/: {len(live_after)} objects (before {len(live_before)}); "
          f"{LIVE_MARKER_KEY} before={before} after={after}")
    print(f"live data/ untouched: {live_untouched}")

    if removed:
        failures.append(f"{len(removed)} cache objects were removed")
    if not live_untouched:
        failures.append("live data/ changed during the run")
    log_keys = [k for k in counters.written_keys if k.startswith("cache/partner_log/")]
    print(f"partner_log objects written: {sorted(set(log_keys))}")

    if not args.keep_scratch:
        for key in scratch_keys:
            assert key.startswith("verify/"), key
            client.delete_object(Bucket=BUCKET, Key=key)
        left = list_objects(client, scratch_prefix)
        print(f"scratch cleanup: deleted {len(scratch_keys)}, {len(left)} left")
        if left:
            failures.append("scratch prefix not fully cleaned")
    else:
        print(f"scratch kept at s3://{BUCKET}/{scratch_prefix}")
    return failures


# -- CLI ---------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="read-only counts + byte-identity checks")
    check.add_argument("--local-cache", type=Path, default=None,
                       help="local cache tree to compare exact per-folder counts against")
    run = sub.add_parser("run", help="one-source real pipeline run (scratch data prefix)")
    run.add_argument("--source", required=True, help="registry source id, e.g. coastalrootsfarm")
    run.add_argument("--site-dir", default=None)
    run.add_argument("--no-enrich", action="store_true")
    run.add_argument("--data-location", default=None,
                     help=f"s3://{BUCKET}/verify/... scratch location (default: generated)")
    run.add_argument("--keep-scratch", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "check":
        client = _client()
        failures = check_counts(client, args.local_cache) + check_byte_identity(client)
    else:
        failures = run_one_source(args)
    print("\nPASS" if not failures else "\nFAIL:\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
