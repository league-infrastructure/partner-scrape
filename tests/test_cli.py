"""Tests for partner_scrape.cli: the `partner-scrape` console-script entry point.

Exercises argument parsing and wiring into `pipeline.run()` by
monkeypatching `cli.run` -- these tests never construct a real `Fetcher`
or touch the network; end-to-end behavior of the real pipeline is
`test_pipeline_e2e.py`'s job. This file is deliberately thin: it only
proves the CLI's flags parse and reach `pipeline.run()` with the right
values, and that the console-script entry point declared in
`pyproject.toml` resolves to `partner_scrape.cli:main`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from partner_scrape import cli
from partner_scrape.enrich.enricher import LLMEnricher
from partner_scrape.enrich.llm_client import AnthropicLLMClient
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
