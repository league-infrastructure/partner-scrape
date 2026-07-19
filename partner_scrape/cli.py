"""``partner-scrape``: the aggregator engine's command-line entry point.

A thin `argparse` wrapper around `pipeline.run()` (sprint.md Architecture
> Pipeline/CLI) -- this module owns flag parsing and console output only;
every real decision (which sources, which adapters, what gets written)
belongs to `pipeline.run()` and the modules it calls. Registered as the
`partner-scrape` console script in `pyproject.toml`.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from partner_scrape.pipeline import run


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="partner-scrape",
        description=(
            "Run the STEM ecosystem partner-scrape aggregator engine: "
            "Registry -> Adapters -> Normalize -> Export."
        ),
    )
    parser.add_argument(
        "--registry-dir",
        type=Path,
        default=None,
        help=(
            "Source Registry directory to load sources from (default: "
            "the real seed registry under partner_scrape/registry/sources/)."
        ),
    )
    parser.add_argument(
        "--site-dir",
        type=Path,
        default=None,
        help=(
            "Sibling stem-ecosystem checkout to write opportunities.json / "
            "scrape-meta.json into (default: ../stem-ecosystem, or $SITE_DIR)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute the export payload without writing anything to --site-dir.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Only run the first N active sources (useful for a quick smoke test).",
    )
    parser.add_argument(
        "--source",
        dest="source_id",
        default=None,
        metavar="SOURCE_ID",
        help="Only run this single source (matches the registry TOML file's stem).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable INFO-level logging (per-source yield counts, skip reasons).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    payload = run(
        registry_dir=args.registry_dir,
        site_dir=args.site_dir,
        source_id=args.source_id,
        limit=args.limit,
        dry_run=args.dry_run,
    )

    noun = "opportunity" if len(payload) == 1 else "opportunities"
    suffix = " (dry run -- nothing written)" if args.dry_run else ""
    print(f"partner-scrape: wrote {len(payload)} {noun}{suffix}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
