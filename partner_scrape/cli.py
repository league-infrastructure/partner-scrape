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

from partner_scrape.config import get_site_dir
from partner_scrape.enrich.cache import EnrichmentCache
from partner_scrape.enrich.enricher import LLMEnricher
from partner_scrape.enrich.llm_client import AnthropicLLMClient
from partner_scrape.observability.render import render_text
from partner_scrape.observability.reporter import YieldReporter
from partner_scrape.observability.snapshot import load_snapshot, save_snapshot
from partner_scrape.pipeline import Enricher, run


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
        "--no-enrich",
        action="store_true",
        help=(
            "Skip LLM enrichment and the relevance gate entirely (no "
            "ANTHROPIC_API_KEY needed, no Anthropic API cost). Sources are "
            "still discovered, extracted, normalized, and exported -- "
            "just without LLM-recovered fields, classification, or "
            "relevance filtering. Matches sprint 001's original "
            "(pre-enrichment) behavior exactly."
        ),
    )
    parser.add_argument(
        "--yield-history",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Path to the per-source yield-history snapshot JSON file "
            "(default: {site-dir}/src/data/yield-history.json, resolved "
            "the same way --site-dir resolves against Config.get_site_dir()). "
            "Ignored when --no-report is given."
        ),
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help=(
            "Skip constructing a YieldReporter entirely -- run() behaves "
            "exactly as it did before sprint 004 (reporter=None): no yield "
            "report is printed, and yield-history.json is neither read nor "
            "written."
        ),
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

    # Enrichment defaults to on (sprint.md's Architecture Open Question 5:
    # matches issue 04's framing of enrichment as normal production
    # behavior, not an opt-in extra). --no-enrich is the escape hatch --
    # preserves sprint 001's exact original enrichers=() behavior for
    # local/dry-run usage that wants to avoid real Anthropic API cost and
    # the ANTHROPIC_API_KEY requirement.
    enrichers: tuple[Enricher, ...]
    if args.no_enrich:
        enrichers = ()
    else:
        enrichers = (LLMEnricher(AnthropicLLMClient(), EnrichmentCache()),)

    # Yield reporting defaults to on (sprint 004's Architecture > CLI
    # wiring: cli.py plays the same "constructs the default concrete
    # implementation" role for YieldReporter it already plays for
    # LLMEnricher). --no-report is the escape hatch that restores
    # run()'s exact pre-sprint-004 behavior (reporter=None) -- used by
    # tests and any local usage that doesn't want yield-history.json
    # read or written at all.
    yield_reporter: YieldReporter | None = None
    yield_history_path: Path | None = None
    previous_snapshot: dict[str, object] = {}
    if not args.no_report:
        resolved_site_dir = args.site_dir if args.site_dir is not None else get_site_dir()
        yield_history_path = (
            args.yield_history
            if args.yield_history is not None
            else resolved_site_dir / "src" / "data" / "yield-history.json"
        )
        previous_snapshot = load_snapshot(yield_history_path)
        yield_reporter = YieldReporter()

    payload = run(
        registry_dir=args.registry_dir,
        site_dir=args.site_dir,
        source_id=args.source_id,
        limit=args.limit,
        dry_run=args.dry_run,
        enrichers=enrichers,
        reporter=yield_reporter,
    )

    noun = "opportunity" if len(payload) == 1 else "opportunities"
    suffix = " (dry run -- nothing written)" if args.dry_run else ""
    print(f"partner-scrape: wrote {len(payload)} {noun}{suffix}.")

    if yield_reporter is not None:
        report = yield_reporter.report(previous_snapshot)
        print(render_text(report))
        # --dry-run computes the would-be export payload without writing
        # anything to --site-dir (run()'s own dry_run contract); the
        # yield-history snapshot is site-dir-adjacent output, so it
        # follows the same "nothing written" promise here.
        if not args.dry_run:
            assert yield_history_path is not None  # set above whenever yield_reporter is
            save_snapshot(yield_history_path, report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
