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


@pytest.fixture(autouse=True)
def _cache_dir(tmp_path, monkeypatch):
    """Point SCRAPE_CACHE_DIR at a tmp_path for every test in this file.

    `cli.main()` instantiates a real `EnrichmentCache()` by default
    (enrichment-on is the new default, ticket 006) *before* the
    monkeypatched `cli.run` is ever reached -- `EnrichmentCache()`
    reads `SCRAPE_CACHE_DIR` eagerly at construction (see
    `config.get_scrape_cache_dir`'s "no sane default" `RuntimeError`),
    so every test in this file needs it set even though none of them
    ever touch the real configured cache directory.
    """
    monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))
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
