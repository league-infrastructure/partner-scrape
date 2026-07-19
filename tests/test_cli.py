"""Tests for partner_scrape.cli: the `partner-scrape` console-script entry point.

Exercises argument parsing and wiring into `pipeline.run()` by
monkeypatching `cli.run` -- these tests never construct a real `Fetcher`
or touch the network; end-to-end behavior of the real pipeline is
`test_pipeline_e2e.py`'s job. This file is deliberately thin: it only
proves the CLI's flags parse and reach `pipeline.run()` with the right
values, and that the console-script entry point declared in
`pyproject.toml` resolves to `partner_scrape.cli:main`.

Ticket 004 (sprint 005) adds `TestDiscoverCandidatesSubcommand`,
`TestDiscoverCandidatesEndToEnd`, and `TestExistingRunCommandUnaffected`
below, covering the new `discover-candidates` subcommand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from partner_scrape import cli
from partner_scrape.enrich.enricher import LLMEnricher
from partner_scrape.enrich.llm_client import AnthropicLLMClient
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.observability.reporter import YieldReporter


@pytest.fixture(autouse=True)
def _cache_dir(tmp_path, monkeypatch):
    """Point SCRAPE_CACHE_DIR (and, as of ticket 003, SITE_DIR) at a
    tmp_path for every test in this file.

    `cli.main()` instantiates a real `EnrichmentCache()` by default
    (enrichment-on is the new default, ticket 006) *before* the
    monkeypatched `cli.run` is ever reached -- `EnrichmentCache()`
    reads `SCRAPE_CACHE_DIR` eagerly at construction (see
    `config.get_scrape_cache_dir`'s "no sane default" `RuntimeError`),
    so every test in this file needs it set even though none of them
    ever touch the real configured cache directory.

    As of ticket 003, `cli.main()` also resolves a default
    `--yield-history` path via `Config.get_site_dir()` *before* calling
    the monkeypatched `cli.run` -- unlike `cli.run`'s own `site_dir`
    resolution (which lives inside `pipeline.run()` and is never reached
    once `cli.run` is replaced), this resolution happens unconditionally
    in `cli.main()` itself. Without overriding `SITE_DIR`, any test here
    that omits `--site-dir` would resolve against the real sibling
    `../stem-ecosystem` checkout and, for a default (non---no-report,
    non---dry-run) run, write a real `yield-history.json` into it. Every
    test in this file must stay hermetic, so `SITE_DIR` is pinned to the
    same `tmp_path` unconditionally.
    """
    monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("SITE_DIR", str(tmp_path))
    return tmp_path


class TestArgumentWiring:
    def test_defaults_pass_none_through_to_pipeline_run(self, monkeypatch, capsys):
        captured = {}

        def fake_run(**kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(cli, "run", fake_run)

        exit_code = cli.main([])

        assert exit_code == 0
        enrichers = captured.pop("enrichers")
        reporter = captured.pop("reporter")
        assert captured == {
            "registry_dir": None,
            "site_dir": None,
            "source_id": None,
            "limit": None,
            "dry_run": False,
        }
        # Enrichment defaults to on (sprint.md Open Question 5): a real
        # LLMEnricher(AnthropicLLMClient(), EnrichmentCache()) is built
        # and passed through, with no --no-enrich flag given.
        assert len(enrichers) == 1
        [enricher] = enrichers
        assert isinstance(enricher, LLMEnricher)
        assert isinstance(enricher.llm_client, AnthropicLLMClient)
        # Yield reporting defaults to on too (ticket 003): a real
        # YieldReporter is built and passed through, with no --no-report
        # flag given.
        assert isinstance(reporter, YieldReporter)

    def test_flags_are_parsed_and_forwarded(self, monkeypatch, tmp_path):
        captured = {}

        def fake_run(**kwargs):
            captured.update(kwargs)
            return [{"slug": "a"}, {"slug": "b"}]

        monkeypatch.setattr(cli, "run", fake_run)

        registry_dir = tmp_path / "registry"
        site_dir = tmp_path / "site"

        exit_code = cli.main(
            [
                "--registry-dir",
                str(registry_dir),
                "--site-dir",
                str(site_dir),
                "--dry-run",
                "--limit",
                "3",
                "--source",
                "coastalrootsfarm",
            ]
        )

        assert exit_code == 0
        assert captured["registry_dir"] == registry_dir
        assert captured["site_dir"] == site_dir
        assert captured["dry_run"] is True
        assert captured["limit"] == 3
        assert captured["source_id"] == "coastalrootsfarm"

    def test_prints_a_summary_including_the_written_count(self, monkeypatch, capsys):
        monkeypatch.setattr(cli, "run", lambda **kwargs: [{"slug": "a"}, {"slug": "b"}])

        cli.main([])

        out = capsys.readouterr().out
        assert "2" in out
        assert "opportunities" in out

    def test_dry_run_summary_notes_nothing_was_written(self, monkeypatch, capsys):
        monkeypatch.setattr(cli, "run", lambda **kwargs: [{"slug": "a"}])

        cli.main(["--dry-run"])

        out = capsys.readouterr().out
        assert "dry run" in out.lower()


class TestNoEnrichFlag:
    def test_no_enrich_passes_an_empty_enrichers_tuple(self, monkeypatch):
        captured = {}

        def fake_run(**kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(cli, "run", fake_run)

        exit_code = cli.main(["--no-enrich"])

        assert exit_code == 0
        # Preserves sprint 001's exact original enrichers=() behavior --
        # the escape hatch from real Anthropic API cost/ANTHROPIC_API_KEY.
        assert captured["enrichers"] == ()

    def test_no_enrich_never_constructs_an_anthropic_client(self, monkeypatch):
        def _boom(*args, **kwargs):
            raise AssertionError(
                "AnthropicLLMClient must not be constructed under --no-enrich"
            )

        monkeypatch.setattr(cli, "AnthropicLLMClient", _boom)
        monkeypatch.setattr(cli, "run", lambda **kwargs: [])

        exit_code = cli.main(["--no-enrich"])  # must not raise

        assert exit_code == 0

    def test_no_enrich_flag_appears_in_help_text(self, capsys):
        with pytest.raises(SystemExit):
            cli.main(["--help"])

        out = capsys.readouterr().out
        assert "--no-enrich" in out


class TestYieldReportWiring:
    """Ticket 003: `--yield-history`/`--no-report` and the default
    YieldReporter wiring. `cli.run` is monkeypatched throughout, same
    convention as the rest of this file -- these tests prove `cli.main`
    wires the reporter/snapshot path correctly, not the real pipeline's
    behavior (that's `test_pipeline_e2e.py`'s job). The `_cache_dir`
    autouse fixture pins `SITE_DIR` to `tmp_path` for every test in this
    file, so any test below that omits `--site-dir` still cannot reach
    the real sibling `../stem-ecosystem` checkout.
    """

    def test_default_run_passes_a_real_yield_reporter_into_run(self, monkeypatch):
        captured = {}

        def fake_run(**kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(cli, "run", fake_run)

        exit_code = cli.main(["--no-enrich"])

        assert exit_code == 0
        assert isinstance(captured["reporter"], YieldReporter)

    def test_no_report_passes_reporter_none_into_run(self, monkeypatch):
        captured = {}

        def fake_run(**kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(cli, "run", fake_run)

        exit_code = cli.main(["--no-enrich", "--no-report"])

        assert exit_code == 0
        # run() is called exactly as it was before this ticket:
        # reporter omitted/None (sprint.md's `--no-report` contract).
        assert captured["reporter"] is None

    def test_no_report_never_constructs_a_yield_reporter(self, monkeypatch):
        def _boom(*args, **kwargs):
            raise AssertionError(
                "YieldReporter must not be constructed under --no-report"
            )

        monkeypatch.setattr(cli, "YieldReporter", _boom)
        monkeypatch.setattr(cli, "run", lambda **kwargs: [])

        exit_code = cli.main(["--no-enrich", "--no-report"])  # must not raise

        assert exit_code == 0

    def test_no_report_never_touches_snapshot_io(self, monkeypatch):
        def _boom(*args, **kwargs):
            raise AssertionError("snapshot I/O must not run under --no-report")

        monkeypatch.setattr(cli, "load_snapshot", _boom)
        monkeypatch.setattr(cli, "save_snapshot", _boom)
        monkeypatch.setattr(cli, "run", lambda **kwargs: [])

        exit_code = cli.main(["--no-enrich", "--no-report"])  # must not raise

        assert exit_code == 0

    def test_default_yield_history_path_resolves_under_the_site_dir(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(cli, "run", lambda **kwargs: [])

        site_dir = tmp_path / "site"
        cli.main(["--no-enrich", "--site-dir", str(site_dir)])

        expected = site_dir / "src" / "data" / "yield-history.json"
        assert expected.exists()

    def test_explicit_yield_history_flag_overrides_the_default_path(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(cli, "run", lambda **kwargs: [])

        site_dir = tmp_path / "site"
        history_path = tmp_path / "custom" / "history.json"
        cli.main(
            [
                "--no-enrich",
                "--site-dir",
                str(site_dir),
                "--yield-history",
                str(history_path),
            ]
        )

        assert history_path.exists()
        assert not (site_dir / "src" / "data" / "yield-history.json").exists()

    def test_report_text_prints_after_the_existing_summary_line_by_default(
        self, monkeypatch, capsys, tmp_path
    ):
        monkeypatch.setattr(cli, "run", lambda **kwargs: [])

        cli.main(["--no-enrich", "--site-dir", str(tmp_path / "site")])

        out = capsys.readouterr().out
        assert "ALERTS" in out
        assert "Per-source detail" in out
        summary_index = out.index("partner-scrape: wrote")
        alerts_index = out.index("ALERTS")
        assert alerts_index > summary_index

    def test_no_report_flag_suppresses_the_report_and_skips_history_write(
        self, monkeypatch, capsys, tmp_path
    ):
        monkeypatch.setattr(cli, "run", lambda **kwargs: [{"slug": "a"}])

        site_dir = tmp_path / "site"
        cli.main(["--no-enrich", "--no-report", "--site-dir", str(site_dir)])

        out = capsys.readouterr().out
        assert "ALERTS" not in out
        assert "Per-source detail" not in out
        assert not (site_dir / "src" / "data" / "yield-history.json").exists()

    def test_dry_run_prints_the_report_but_does_not_persist_history(
        self, monkeypatch, capsys, tmp_path
    ):
        monkeypatch.setattr(cli, "run", lambda **kwargs: [{"slug": "a"}])

        site_dir = tmp_path / "site"
        cli.main(["--no-enrich", "--dry-run", "--site-dir", str(site_dir)])

        out = capsys.readouterr().out
        assert "ALERTS" in out
        assert not (site_dir / "src" / "data" / "yield-history.json").exists()

    def test_no_report_and_yield_history_flags_appear_in_help_text(self, capsys):
        with pytest.raises(SystemExit):
            cli.main(["--help"])

        out = capsys.readouterr().out
        assert "--no-report" in out
        assert "--yield-history" in out


class TestHelp:
    def test_help_flag_exits_cleanly_without_calling_pipeline_run(self, monkeypatch):
        def _boom(**kwargs):
            raise AssertionError("pipeline.run must not be called for --help")

        monkeypatch.setattr(cli, "run", _boom)

        with pytest.raises(SystemExit) as exc_info:
            cli.main(["--help"])

        assert exc_info.value.code == 0


class TestConsoleScriptEntryPoint:
    def test_pyproject_declares_the_partner_scrape_console_script(self):
        pyproject = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()

        assert "[project.scripts]" in pyproject
        assert 'partner-scrape = "partner_scrape.cli:main"' in pyproject


# ---------------------------------------------------------------------
# Ticket 004 (sprint 005): the `discover-candidates` subcommand.
# ---------------------------------------------------------------------

#: Fixture Hub Registry directory pointing at the same fixture hub page
#: (tests/fixtures/hubs/example_hub.html) test_discovery_hub_scan.py and
#: test_discovery_candidate_pipeline.py already exercise.
CLI_HUBS_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "cli_discover_hubs"
#: Fixture Source Registry directory used by Hub Scan's own dedup check.
CLI_SOURCES_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "hub_scan_registry"
HUB_PAGE_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "hubs"

CALENDAR_URL = "https://examplehub.org/calendar"
ROBOTS_URL = "https://examplehub.org/robots.txt"
_ALLOW_ALL_ROBOTS = "User-agent: *\nDisallow:\n"


@dataclass
class _FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.
    A URL absent from ``responses`` raises ``KeyError``: a loud failure
    if the real end-to-end test below ever reaches for something it
    shouldn't (the concrete proof of "no live network call")."""

    responses: dict[str, FetchResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        return self.responses[url]


class TestDiscoverCandidatesSubcommand:
    """CLI wiring tests, mirroring `TestArgumentWiring`'s pattern above:
    `cli.discover_candidates` is monkeypatched, so these prove flags
    parse and reach it with the right values -- not the real discovery
    flow's own behavior (that's test_discovery_candidate_pipeline.py's
    job, and `TestDiscoverCandidatesEndToEnd` below)."""

    def test_defaults_pass_none_dirs_and_a_real_enricher(self, monkeypatch):
        captured = {}

        def fake_discover_candidates(hubs, fetcher, enricher=None, **kwargs):
            captured["hubs"] = hubs
            captured["fetcher"] = fetcher
            captured["enricher"] = enricher
            captured.update(kwargs)
            return []

        monkeypatch.setattr(cli, "discover_candidates", fake_discover_candidates)

        exit_code = cli.main(["discover-candidates"])

        assert exit_code == 0
        assert captured["candidates_dir"] is None
        assert captured["sources_dir"] is None
        # Relevance gating defaults to on, same "CLI constructs the
        # default concrete implementation" convention as the `run`
        # command's own --no-enrich precedent.
        assert isinstance(captured["enricher"], LLMEnricher)
        assert isinstance(captured["enricher"].llm_client, AnthropicLLMClient)

    def test_hubs_dir_flag_is_forwarded_to_load_hubs(self, monkeypatch):
        captured = {}

        def fake_discover_candidates(hubs, fetcher, enricher=None, **kwargs):
            captured["hubs"] = hubs
            return []

        monkeypatch.setattr(cli, "discover_candidates", fake_discover_candidates)

        exit_code = cli.main(["discover-candidates", "--hubs-dir", str(CLI_HUBS_FIXTURE_DIR)])

        assert exit_code == 0
        hub_ids = {h.hub_id for h in captured["hubs"]}
        assert hub_ids == {"example_hub"}

    def test_candidates_dir_flag_is_forwarded(self, monkeypatch, tmp_path):
        captured = {}

        def fake_discover_candidates(hubs, fetcher, enricher=None, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(cli, "discover_candidates", fake_discover_candidates)

        candidates_dir = tmp_path / "candidates"
        exit_code = cli.main(["discover-candidates", "--candidates-dir", str(candidates_dir)])

        assert exit_code == 0
        assert captured["candidates_dir"] == candidates_dir

    def test_registry_dir_flag_is_forwarded_as_sources_dir(self, monkeypatch, tmp_path):
        captured = {}

        def fake_discover_candidates(hubs, fetcher, enricher=None, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(cli, "discover_candidates", fake_discover_candidates)

        registry_dir = tmp_path / "registry"
        exit_code = cli.main(["discover-candidates", "--registry-dir", str(registry_dir)])

        assert exit_code == 0
        assert captured["sources_dir"] == registry_dir

    def test_no_enrich_passes_none_as_the_enricher(self, monkeypatch):
        captured = {}

        def fake_discover_candidates(hubs, fetcher, enricher=None, **kwargs):
            captured["enricher"] = enricher
            return []

        monkeypatch.setattr(cli, "discover_candidates", fake_discover_candidates)

        exit_code = cli.main(["discover-candidates", "--no-enrich"])

        assert exit_code == 0
        assert captured["enricher"] is None

    def test_no_enrich_never_constructs_an_anthropic_client(self, monkeypatch):
        def _boom(*args, **kwargs):
            raise AssertionError(
                "AnthropicLLMClient must not be constructed under --no-enrich"
            )

        monkeypatch.setattr(cli, "AnthropicLLMClient", _boom)
        monkeypatch.setattr(cli, "discover_candidates", lambda *a, **kw: [])

        exit_code = cli.main(["discover-candidates", "--no-enrich"])  # must not raise

        assert exit_code == 0

    def test_prints_a_summary_including_hub_and_candidate_counts(self, monkeypatch, capsys):
        monkeypatch.setattr(
            cli,
            "discover_candidates",
            lambda hubs, fetcher, enricher=None, **kw: [object(), object()],
        )

        cli.main(["discover-candidates", "--hubs-dir", str(CLI_HUBS_FIXTURE_DIR)])

        out = capsys.readouterr().out
        assert "1" in out  # one fixture hub scanned
        assert "2" in out  # two candidates queued
        assert "discover-candidates" in out

    def test_never_calls_the_run_pipeline(self, monkeypatch):
        def _boom(**kwargs):
            raise AssertionError("discover-candidates must never call pipeline.run()")

        monkeypatch.setattr(cli, "run", _boom)
        monkeypatch.setattr(cli, "discover_candidates", lambda *a, **kw: [])

        exit_code = cli.main(["discover-candidates"])  # must not raise

        assert exit_code == 0

    def test_help_flag_exits_cleanly_without_calling_discover_candidates(self, monkeypatch):
        def _boom(*args, **kwargs):
            raise AssertionError("discover_candidates must not be called for --help")

        monkeypatch.setattr(cli, "discover_candidates", _boom)

        with pytest.raises(SystemExit) as exc_info:
            cli.main(["discover-candidates", "--help"])

        assert exc_info.value.code == 0

    def test_discover_candidates_help_text_lists_its_flags(self, capsys):
        with pytest.raises(SystemExit):
            cli.main(["discover-candidates", "--help"])

        out = capsys.readouterr().out
        assert "--hubs-dir" in out
        assert "--candidates-dir" in out
        assert "--registry-dir" in out
        assert "--no-enrich" in out

    def test_top_level_help_text_mentions_the_discover_candidates_subcommand(self, capsys):
        with pytest.raises(SystemExit):
            cli.main(["--help"])

        out = capsys.readouterr().out
        assert "discover-candidates" in out


class TestDiscoverCandidatesEndToEnd:
    """A genuine end-to-end run: `cli.main` is exercised unmodified (no
    `cli.discover_candidates` monkeypatch) all the way down through the
    real Hub Registry load, Hub Scan, relevance gate, and Candidate
    Review Queue write -- only `cli.PoliteFetcher` (the CLI's own default
    `Fetcher` construction point for this subcommand) is substituted with
    a canned fixture Fetcher, so no real socket is ever opened. Mirrors
    this ticket's Acceptance Criteria: "partner-scrape discover-candidates
    runs end-to-end against a fixture hubs directory and fixture
    registry, with no live network call, and prints a summary."
    """

    def test_runs_end_to_end_against_fixture_hubs_and_registry(self, monkeypatch, tmp_path, capsys):
        fetcher = _FixtureFetcher(
            {
                ROBOTS_URL: FetchResponse(url="", status=200, headers={}, body=_ALLOW_ALL_ROBOTS),
                CALENDAR_URL: FetchResponse(
                    url="",
                    status=200,
                    headers={},
                    body=(HUB_PAGE_FIXTURES_DIR / "example_hub.html").read_text(),
                ),
            }
        )
        monkeypatch.setattr(cli, "PoliteFetcher", lambda: fetcher)

        candidates_dir = tmp_path / "candidates"
        exit_code = cli.main(
            [
                "discover-candidates",
                "--hubs-dir",
                str(CLI_HUBS_FIXTURE_DIR),
                "--registry-dir",
                str(CLI_SOURCES_FIXTURE_DIR),
                "--candidates-dir",
                str(candidates_dir),
                "--no-enrich",
            ]
        )

        assert exit_code == 0
        # No live network call: every URL the fixture Fetcher was asked
        # for came from its own canned `responses` dict (a real socket
        # attempt would have raised KeyError instead).
        assert fetcher.calls
        # Prints a summary.
        out = capsys.readouterr().out
        assert "discover-candidates" in out
        assert "hub" in out.lower()
        assert "candidate" in out.lower()
        # And the candidates were actually queued for review -- exactly
        # the two genuinely-new orgs on the fixture hub page; the other
        # two (linked to orgs present in the fixture registry) are
        # deduped out by Hub Scan's own dedup check.
        written = list(candidates_dir.glob("*.toml"))
        assert len(written) == 2
        assert {p.stem for p in written} == {"brand-new-stem-org", "another-new-org"}

    def test_never_writes_opportunities_json_anywhere_under_tmp_path(
        self, monkeypatch, tmp_path, capsys
    ):
        monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))
        fetcher = _FixtureFetcher(
            {
                ROBOTS_URL: FetchResponse(url="", status=200, headers={}, body=_ALLOW_ALL_ROBOTS),
                CALENDAR_URL: FetchResponse(
                    url="",
                    status=200,
                    headers={},
                    body=(HUB_PAGE_FIXTURES_DIR / "example_hub.html").read_text(),
                ),
            }
        )
        monkeypatch.setattr(cli, "PoliteFetcher", lambda: fetcher)

        cli.main(
            [
                "discover-candidates",
                "--hubs-dir",
                str(CLI_HUBS_FIXTURE_DIR),
                "--candidates-dir",
                str(tmp_path / "candidates"),
                "--no-enrich",
            ]
        )

        assert not list(tmp_path.rglob("opportunities.json"))


class TestExistingRunCommandUnaffected:
    """The existing `partner-scrape` (no subcommand / `run`) CLI
    behavior, flags, and output are unchanged by this ticket's addition
    -- explicit regression coverage on top of every pre-existing test in
    this file (all of which still exercise the no-subcommand path
    unmodified)."""

    def test_no_subcommand_still_dispatches_to_the_run_pipeline(self, monkeypatch):
        captured = {}

        def fake_run(**kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(cli, "run", fake_run)

        exit_code = cli.main([])

        assert exit_code == 0
        assert captured  # pipeline.run() was reached with its usual kwargs

    def test_no_subcommand_never_calls_discover_candidates(self, monkeypatch):
        def _boom(*args, **kwargs):
            raise AssertionError("the no-subcommand/run path must never call discover_candidates")

        monkeypatch.setattr(cli, "discover_candidates", _boom)
        monkeypatch.setattr(cli, "run", lambda **kwargs: [])

        exit_code = cli.main([])  # must not raise

        assert exit_code == 0
