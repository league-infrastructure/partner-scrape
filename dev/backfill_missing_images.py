#!/usr/bin/env python3
"""One-off (and future integrity-check) backfill for
``data/images/opportunities/``.

RUN THIS BY HAND whenever a check against the real ``data/`` tree
reports missing files -- most notably right after sprint 025's first
production run, which redirected ``EventImageDownloader``'s write
target to ``data/images/opportunities/`` and populated it with only
that run's *current* opportunities (375 images), not the accumulated
history ``export/publish.py``'s ``project()`` publishes via
``data/partners/<slug>/events.json`` and ``.../past-events.json``
(which reflect every opportunity ever seen for that partner, via the
persistent per-partner log under ``SCRAPE_CACHE_DIR``). That gap
turned up 172 referenced-but-missing filenames, all confirmed to
still exist, unresized, in the sibling ``stem-ecosystem`` checkout's
``public/images/opportunities/`` -- see sprint 026's ticket 001 for
the full incident writeup.

Check-only (default, no ``--source-dir``):

    uv run python dev/backfill_missing_images.py

Reports referenced/existing/missing counts for two independent
checks -- the ``data/partners/*/{events,past-events}.json`` set and
the ``data/opportunities.json`` set, kept separate because they are
independent contracts with independent producers -- and exits
non-zero if either shows any missing filename. Safe to wire into a
future CI gate.

Backfill (copies from a source directory of un-resized originals,
byte-identical, never re-encoded):

    uv run python dev/backfill_missing_images.py \\
        --source-dir ../stem-ecosystem/public/images/opportunities

Add ``--dry-run`` to preview what would be copied without writing.

This is a **standalone provisioning script**, matching
``dev/refresh_school_directories.py``'s convention: stdlib only (no
import of ``partner_scrape.*``), never imported by runtime code, run
by hand. It does not fetch anything over the network -- it only
compares and copies files already present on disk.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data"

#: Sub-path, relative to a data dir, where opportunity images live.
IMAGES_SUBDIR = Path("images") / "opportunities"


def _referenced_from_partners(data_dir: Path) -> set[str]:
    """Collect every non-empty ``image_src`` filename referenced across
    ``data_dir/partners/*/events.json`` and ``.../past-events.json``.
    """
    referenced: set[str] = set()
    partners_dir = data_dir / "partners"
    for pattern in ("*/events.json", "*/past-events.json"):
        for path in sorted(partners_dir.glob(pattern)):
            doc = json.loads(path.read_text(encoding="utf-8"))
            for event in doc.get("events", []):
                image_src = event.get("image_src")
                if image_src:
                    referenced.add(image_src)
    return referenced


def _referenced_from_opportunities(data_dir: Path) -> set[str]:
    """Collect every non-empty ``image_src`` filename referenced in
    ``data_dir/opportunities.json`` (a bare list of opportunity
    records). Kept independent of the partners-derived set -- see
    this module's docstring.
    """
    path = data_dir / "opportunities.json"
    records = json.loads(path.read_text(encoding="utf-8"))
    return {r["image_src"] for r in records if r.get("image_src")}


def _existing_images(data_dir: Path) -> set[str]:
    images_dir = data_dir / IMAGES_SUBDIR
    if not images_dir.exists():
        return set()
    return {p.name for p in images_dir.glob("*") if p.is_file()}


def _report(label: str, referenced: set[str], existing: set[str]) -> set[str]:
    missing = referenced - existing
    print(f"  {label}: {len(referenced)} referenced, {len(existing & referenced)} present, {len(missing)} missing")
    if missing:
        for name in sorted(missing):
            print(f"    missing: {name}")
    return missing


def check(data_dir: Path, *, heading: str) -> tuple[set[str], set[str]]:
    """Run both checks and print a report. Returns
    ``(missing_from_partners, missing_from_opportunities)``.
    """
    print(heading)
    existing = _existing_images(data_dir)
    partners_referenced = _referenced_from_partners(data_dir)
    opportunities_referenced = _referenced_from_opportunities(data_dir)
    missing_partners = _report("partners (events.json + past-events.json)", partners_referenced, existing)
    missing_opportunities = _report("opportunities.json", opportunities_referenced, existing)
    return missing_partners, missing_opportunities


def backfill(data_dir: Path, source_dir: Path, missing: set[str], *, dry_run: bool) -> tuple[list[str], list[str]]:
    """Copy every filename in ``missing`` that exists in ``source_dir``
    into ``data_dir/images/opportunities`` via ``shutil.copy2`` (exact
    byte copy, preserves mtime, no re-encode). Returns
    ``(copied, not_found_in_source)``.
    """
    images_dir = data_dir / IMAGES_SUBDIR
    images_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    not_found: list[str] = []
    for name in sorted(missing):
        src = source_dir / name
        if not src.exists():
            not_found.append(name)
            continue
        dest = images_dir / name
        if dry_run:
            print(f"  would copy: {name}")
        else:
            shutil.copy2(src, dest)
            print(f"  copied: {name}")
        copied.append(name)

    if not_found:
        print(f"\n  NOT FOUND IN SOURCE EITHER ({len(not_found)}):")
        for name in sorted(not_found):
            print(f"    {name}")

    return copied, not_found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Data directory to check/backfill (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help="Directory of source images to backfill from. Omit for check-only mode.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --source-dir, report what would be copied without writing anything.",
    )
    args = parser.parse_args()

    data_dir: Path = args.data_dir

    missing_partners, missing_opportunities = check(data_dir, heading="Before:")

    if args.source_dir is not None:
        # Copy the union of both missing sets -- the two checks are
        # independent contracts (see this module's docstring), but a
        # backfill run should close both gaps in one pass regardless
        # of how much overlap exists between them.
        to_copy = missing_partners | missing_opportunities
        print(f"\nBackfilling {len(to_copy)} missing filename(s) from {args.source_dir} ...")
        copied, not_found = backfill(data_dir, args.source_dir, to_copy, dry_run=args.dry_run)
        verb = "Would copy" if args.dry_run else "Copied"
        print(f"\n{verb} {len(copied)} file(s); {len(not_found)} not found in source either.")

        if not args.dry_run:
            missing_partners, missing_opportunities = check(data_dir, heading="\nAfter:")
        else:
            print("\n(dry run -- skipping after-check, no files were written)")

    total_missing = len(missing_partners) + len(missing_opportunities)
    if total_missing:
        print(f"\nFAIL: {total_missing} referenced filename(s) still missing.")
        return 1
    print("\nOK: all referenced images present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
