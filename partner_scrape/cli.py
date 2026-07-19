"""``partner-scrape``: the aggregator engine's command-line entry point.

A thin `argparse` wrapper around `pipeline.run()` (sprint.md Architecture
> Pipeline/CLI) -- this module owns flag parsing and console output only;
every real decision (which sources, which adapters, what gets written)
belongs to `pipeline.run()` and the modules it calls. Registered as the
`partner-scrape` console script in `pyproject.toml`.

Ticket 004 (sprint 005) adds the `discover-candidates` subcommand,
dispatching to `discovery.candidate_pipeline.discover_candidates()` --
structurally separate from (and never calling into) the `run` command's
`pipeline.run()` path, per sprint.md's Design Rationale ("Hub scanning is
structurally separate from the Event/Opportunity pipeline"). It is
purely additive: every existing flag, default, and printed line of the
no-subcommand/`run` invocation is unchanged.
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
from partner_scrape.fetch import PoliteFetcher
from partner_scrape.observability.render import render_text
from partner_scrape.observability.reporter import YieldReporter
from partner_scrape.observability.snapshot import load_snapshot, save_snapshot

# `pipeline` must be imported before `discovery.candidate_pipeline` below
# -- not just style. `pipeline`'s own first import is `partner_scrape.
# adapters`, which resolves `adapters.base` before `adapters.listing_html`
# needs it. `discovery/__init__.py` (triggered by importing anything
# under `partner_scrape.discovery`) eagerly imports `discovery.listing`,
# which itself needs `adapters.base` -- if `partner_scrape.discovery` is
# the *first* of the two packages touched, `adapters.listing_html`'s own
# `from partner_scrape.discovery.listing import discover_via_listing`
# reaches back into `discovery.listing` while it is still mid-import,
# raising ImportError (a pre-existing circular dependency between
# `discovery.listing` and `adapters.listing_html`, predating this ticket,
# that simply had no direct caller import `discovery` first until now).
# Importing `pipeline` first sidesteps it with no change to either
# module.
from partner_scrape.pipeline import Enricher, run

from partner_scrape.discovery.candidate_pipeline import discover_candidates
from partner_scrape.registry.hub_schema import load_hubs


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

    # Purely additive (ticket 004, sprint 005): a `discover-candidates`
    # subcommand alongside the no-subcommand/`run` invocation above.
    # `dest="command"` defaults to `None` when no subcommand token is
    # present on the command line -- every existing top-level flag above
    # continues to parse exactly as before, unaffected by this addition
    # (confirmed: argparse only consumes a positional subcommand token
    # when one is actually given).
    subparsers = parser.add_subparsers(dest="command")
    _add_discover_candidates_subcommand(subparsers)

    return parser


def _add_discover_candidates_subcommand(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "discover-candidates",
        help="Scan curated hubs for candidate organizations and queue them for review.",
        description=(
            "Scan every configured Hub Registry entry for candidate "
            "organizations not yet in the Source Registry, optionally "
            "relevance-gate them, and persist survivors as review-marked "
            "stub TOML files under the Candidate Review Queue. Never runs "
            "the normal scrape/export -- opportunities.json is never "
            "touched by this command."
        ),
    )
    parser.add_argument(
        "--hubs-dir",
        type=Path,
        default=None,
        help=(
            "Hub Registry directory to load hubs from (default: the real "
            "seed hub registry under partner_scrape/registry/hubs/)."
        ),
    )
    parser.add_argument(
        "--candidates-dir",
        type=Path,
        default=None,
        help=(
            "Candidate Review Queue directory to write stub TOML files "
            "into (default: partner_scrape/registry/candidates/)."
        ),
    )
    parser.add_argument(
        "--registry-dir",
        type=Path,
        default=None,
        help=(
            "Source Registry directory Hub Scan's dedup check reads "
            "against (default: the real seed registry under "
            "partner_scrape/registry/sources/). Mirrors the `run` "
            "command's own --registry-dir."
        ),
    )
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        help=(
            "Skip the relevance gate entirely (no ANTHROPIC_API_KEY "
            "needed, no Anthropic API cost): every candidate already "
            "deduped against the Source Registry is queued, unfiltered. "
            "Mirrors the `run` command's --no-enrich escape hatch."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable INFO-level logging (hub/candidate counts, skip reasons).",
    )


def _run_discover_candidates(args: argparse.Namespace) -> int:
    """Handler for the `discover-candidates` subcommand.

    Constructs its own default `Fetcher` (a real `PoliteFetcher()`) and,
    unless `--no-enrich` is given, its own default relevance gate (a real
    `LLMEnricher(AnthropicLLMClient(), EnrichmentCache())`) -- the same
    "CLI constructs the default concrete implementation" role `main()`
    already plays for the `run` command. Never calls `run`/`pipeline.run`
    -- see cli.py's module docstring.
    """
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    hubs = load_hubs(args.hubs_dir)

    enricher = None
    if not args.no_enrich:
        enricher = LLMEnricher(AnthropicLLMClient(), EnrichmentCache())

    written = discover_candidates(
        hubs,
        PoliteFetcher(),
        enricher,
        sources_dir=args.registry_dir,
        candidates_dir=args.candidates_dir,
    )

    hub_noun = "hub" if len(hubs) == 1 else "hubs"
    candidate_noun = "candidate" if len(written) == 1 else "candidates"
    print(
        f"partner-scrape discover-candidates: scanned {len(hubs)} {hub_noun}, "
        f"queued {len(written)} {candidate_noun} for review."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "discover-candidates":
        return _run_discover_candidates(args)

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
