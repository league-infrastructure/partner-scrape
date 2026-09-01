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

Ticket 002 (sprint 011) adds the `teams` subcommand, dispatching to
`teams.pipeline.run_teams()` -- structurally separate from (and never
calling into) the `run` command's `pipeline.run()` path, for the same
reason as `discover-candidates` plus one more: rosters refresh
annually while opportunities refresh weekly, and a future TBA
credential failure (ticket 011-003) must never sit inside `run`'s own
process/exit code. Also purely additive.

Ticket 007 (sprint 018) adds the `directory` subcommand, dispatching to
`directory.pipeline.run_directory()` -- structurally separate from (and
never calling into) `run`'s or `teams`'s own paths, for the same
"disjoint standing-data pipeline" reasoning as `teams` above. One
subcommand covers both Places (ticket 007) and Clubs (ticket 018-008,
the sprint's Hack Club chapters proof of concept), per sprint.md's Open
Questions recommendation ("one directory command ... mirrors teams"),
rather than a second subcommand -- `directory.pipeline.run_directory()`
itself is where ticket 018-008 added its Club dispatch, not a new CLI
subcommand or CLI flag. Also purely additive: this subcommand's own
flags, defaults, and printed output shape are unchanged by ticket
018-008 beyond reporting a clubs count alongside the places count.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from partner_scrape.config import get_own_data_dir, get_site_dir
from partner_scrape.export import publish
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

from partner_scrape.directory.pipeline import run_directory
from partner_scrape.discovery.candidate_pipeline import discover_candidates
from partner_scrape.registry.hub_schema import load_hubs
from partner_scrape.teams.pipeline import run_teams

logger = logging.getLogger(__name__)


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
            "the real seed registry under registry/sources/)."
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
            "(default: {own-data-dir}/yield-history.json -- this repo's "
            "own data/ directory per Config.get_own_data_dir(), not "
            "--site-dir). Ignored when --no-report is given."
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
    _add_teams_subcommand(subparsers)
    _add_directory_subcommand(subparsers)

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
            "seed hub registry under registry/hubs/)."
        ),
    )
    parser.add_argument(
        "--candidates-dir",
        type=Path,
        default=None,
        help=(
            "Candidate Review Queue directory to write stub TOML files "
            "into (default: registry/candidates/)."
        ),
    )
    parser.add_argument(
        "--registry-dir",
        type=Path,
        default=None,
        help=(
            "Source Registry directory Hub Scan's dedup check reads "
            "against (default: the real seed registry under "
            "registry/sources/). Mirrors the `run` "
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


def _add_teams_subcommand(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "teams",
        help="Acquire, locate, and publish San Diego FIRST robotics teams as teams.json.",
        description=(
            "Run the Teams pipeline: load this subsystem's own Team "
            "Registry (partner_scrape/teams/registry/, disjoint from the "
            "Opportunity Source Registry), acquire each active team "
            "source, and publish teams.json into partner-scrape's own "
            "data directory. Never runs the normal scrape/export -- "
            "opportunities.json and scrape-meta.json are never touched "
            "by this command."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute the teams.json payload without writing anything to disk.",
    )
    parser.add_argument(
        "--source",
        dest="source",
        default=None,
        metavar="SOURCE",
        help=(
            "Only run this single acquisition source, by adapter_type "
            "(e.g. 'ftcscout', 'tba', 'static_roster', or "
            "'robotevents') -- not a Team Registry file's stem. "
            "Omitted, every active team source runs."
        ),
    )
    parser.add_argument(
        "--no-sponsors",
        action="store_true",
        help=(
            "Skip sponsor extraction (no ANTHROPIC_API_KEY needed, no "
            "Anthropic API cost) -- website verification still runs, "
            "and any pre-existing structured sponsor data is still "
            "published. Sponsor extraction is the uncertain, "
            "network+LLM-dependent half of this command; this is its "
            "escape hatch."
        ),
    )
    parser.add_argument(
        "--no-descriptions",
        action="store_true",
        help=(
            "Skip description extraction (no ANTHROPIC_API_KEY needed, "
            "no Anthropic API cost) -- website verification and sponsor "
            "extraction still run. Description extraction (sprint 021 "
            "ticket 004) is the uncertain, network+LLM-dependent half "
            "of publishing Team.description; this is its escape hatch, "
            "mirroring --no-sponsors exactly."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable INFO-level logging (per-source team counts, skip reasons).",
    )


def _add_directory_subcommand(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "directory",
        help="Publish the curated Places and Clubs directories as places.json and clubs.json.",
        description=(
            "Run the Directory pipeline: load this subsystem's own "
            "Registry (partner_scrape/directory/registry/, disjoint from "
            "the Opportunity Source Registry and from teams/registry/), "
            "acquire each active place/club source, and publish "
            "{site_dir}/src/data/places.json and "
            "{site_dir}/src/data/clubs.json. Never runs the normal "
            "scrape/export or the teams pipeline -- opportunities.json, "
            "scrape-meta.json, and teams.json are never touched by this "
            "command."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute the places.json/clubs.json payloads without writing anything to --site-dir.",
    )
    parser.add_argument(
        "--source",
        dest="source",
        default=None,
        metavar="SOURCE",
        help=(
            "Only run this single acquisition source, by adapter_type "
            "(e.g. 'static_roster' or 'hack_club_static_roster') -- not "
            "a Registry file's stem. Omitted, every active place/club "
            "source runs."
        ),
    )
    parser.add_argument(
        "--site-dir",
        type=Path,
        default=None,
        help=(
            "Sibling stem-ecosystem checkout to write places.json and "
            "clubs.json into (default: ../stem-ecosystem, or $SITE_DIR) "
            "-- same default and override as the `run`/`teams` "
            "commands' --site-dir."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable INFO-level logging (per-source place counts, skip reasons).",
    )


def _run_directory(args: argparse.Namespace) -> int:
    """Handler for the `directory` subcommand.

    Constructs its own default `Fetcher` (a real `PoliteFetcher()`) and
    passes it explicitly into `run_directory()` -- the same "CLI
    constructs the default concrete implementation" role `_run_teams`
    already plays for its own pipeline. Never calls
    `run`/`pipeline.run()` or `run_teams()` -- see cli.py's module
    docstring.
    """
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    payload = run_directory(
        source=args.source,
        site_dir=args.site_dir,
        fetcher=PoliteFetcher(),
        dry_run=args.dry_run,
    )
    places = payload["places"]
    # `.get(..., [])`, not `payload["clubs"]`: the real `run_directory()`
    # always populates "clubs" (a list, possibly empty), but existing
    # ticket-007 wiring tests monkeypatch `cli.run_directory` with a
    # places-only fake payload -- this stays backward compatible with
    # those doubles rather than requiring every one of them to grow a
    # "clubs" key it has no reason to know about.
    clubs = payload.get("clubs", [])

    clubs_noun = "club" if len(clubs) == 1 else "clubs"
    noun = "place" if len(places) == 1 else "places"
    suffix = " (dry run -- nothing written)" if args.dry_run else ""
    print(
        f"partner-scrape directory: wrote {len(places)} {noun} and "
        f"{len(clubs)} {clubs_noun}{suffix}."
    )
    return 0


def _run_teams(args: argparse.Namespace) -> int:
    """Handler for the `teams` subcommand.

    Constructs its own default `Fetcher` (a real `PoliteFetcher()`) and
    passes it explicitly into `run_teams()` -- the same "CLI constructs
    the default concrete implementation" role `main()` already plays
    for the `run` command's `Fetcher`, and `_run_discover_candidates`
    plays for its own. Never calls `run`/`pipeline.run()` -- see cli.py's
    module docstring. Sponsor extraction's `llm_client`/`sponsor_cache`
    and description extraction's `description_llm_client`/
    `description_cache` (sprint 021 ticket 004) are left unset here, not
    constructed by this handler -- `run_teams()` itself defaults and
    lazily constructs those (see its own docstring), matching this
    command's existing "let run_teams() own its own defaults" convention
    for `fetcher` not being any different from those four in that
    respect, except `fetcher` is always needed while the other four are
    skippable via `--no-sponsors`/`--no-descriptions`.
    """
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    payload = run_teams(
        source=args.source,
        fetcher=PoliteFetcher(),
        dry_run=args.dry_run,
        no_sponsors=args.no_sponsors,
        no_descriptions=args.no_descriptions,
    )
    teams = payload["teams"]

    noun = "team" if len(teams) == 1 else "teams"
    suffix = " (dry run -- nothing written)" if args.dry_run else ""
    print(f"partner-scrape teams: wrote {len(teams)} {noun}{suffix}.")
    return 0


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

    if args.command == "teams":
        return _run_teams(args)

    if args.command == "directory":
        return _run_directory(args)

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
        # Ticket 006 (sprint 025): the snapshot read (here) and the
        # snapshot write (below, at the single save_snapshot() call)
        # share one default location -- own_data_dir/yield-history.json
        # -- not {site-dir}/src/data/yield-history.json. Sprint 020
        # ticket 007 added a second, independent own_data_dir write
        # alongside the site-dir one and the site-dir *read* stayed
        # put; this consolidates both onto own_data_dir together.
        # Pointing the read at a location that stops being written
        # would freeze every future found/dropped delta computation
        # against a permanently stale snapshot -- see this ticket's
        # file for the full reasoning.
        yield_history_path = (
            args.yield_history
            if args.yield_history is not None
            else get_own_data_dir() / "yield-history.json"
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

    # Sprint 009 ticket 004: project every partner's accumulated
    # per-partner log (written by partner_log.record() inside run(),
    # across this and every prior run) into the published
    # public/data/ tree. Unlike partner_log.record(), which only needs
    # this run's Opportunities, publish.project() needs *every*
    # partner's full history to produce a correct current/past split --
    # a --source/--limit-scoped run must never regenerate the published
    # tree from a partial view. So it is sequenced here rather than
    # called from inside pipeline.run(), and skipped under --dry-run:
    # it writes nothing anywhere.
    #
    # Sprint 018 ticket 001 (issue 43): publish.project() reads every
    # partner's *entire* accumulated .jsonl history, including lines
    # written before a field (e.g. `eligibility`, sprint 015) existed on
    # `Opportunity` -- a KeyError there is a real, standing failure mode
    # (confirmed via a live production run's traceback, not
    # hypothetical), and it used to be fatal to the whole process: an
    # uncaught exception here crashed `main()` before the rest of this
    # function ran. publish.project() failing must never again take the
    # rest of the run down with it: this run's own opportunities.json/
    # teams.json/etc. were already written straight to --site-dir by
    # run() above, independently of publish.project(). Matches this
    # codebase's per-source error-isolation convention
    # (pipeline._run_one_source): logged loudly via logger.exception,
    # never a bare silent pass -- surfaced to the caller as a non-zero
    # exit code below instead.
    publish_failed = False
    if not args.dry_run:
        publish_site_dir = args.site_dir if args.site_dir is not None else get_site_dir()
        try:
            publish.project(
                site_dir=publish_site_dir,
                partners_path=publish_site_dir / "src" / "data" / "partners.json",
            )
        except Exception:
            publish_failed = True
            logger.exception(
                "publish.project() failed; public/data/ was not refreshed "
                "this run. Continuing so the rest of this run's output "
                "(yield report, exit code) is still produced -- "
                "investigate and re-run to refresh public/data/."
            )

    noun = "opportunity" if len(payload) == 1 else "opportunities"
    suffix = " (dry run -- nothing written)" if args.dry_run else ""
    print(f"partner-scrape: wrote {len(payload)} {noun}{suffix}.")

    if yield_reporter is not None:
        report = yield_reporter.report(previous_snapshot)
        print(render_text(report))
        # --dry-run computes the would-be export payload without writing
        # anything to --site-dir (run()'s own dry_run contract); the
        # yield-history snapshot follows the same "nothing written"
        # promise here, even though (as of ticket 006) it no longer
        # lives under --site-dir itself.
        if not args.dry_run:
            assert yield_history_path is not None  # set above whenever yield_reporter is
            # Ticket 006 (sprint 025): a single save_snapshot() call, at
            # yield_history_path -- which already defaults to
            # own_data_dir/yield-history.json above, the same path
            # load_snapshot() read from before run() executed. Sprint
            # 020 ticket 007's second, independent own_data_dir write
            # (alongside a site-dir one) is gone: it's now redundant
            # with this single call.
            save_snapshot(yield_history_path, report)

    # A publish.project() failure above is real (public/data/ is stale
    # until re-run) even though the rest of this run succeeded -- signal
    # it via a non-zero exit rather than the unconditional 0 this
    # function returned before sprint 018 ticket 001, so the failure is
    # visible to a caller/CI job checking the exit code, not just to
    # whoever happens to read the log.
    return 1 if publish_failed else 0


if __name__ == "__main__":
    sys.exit(main())
