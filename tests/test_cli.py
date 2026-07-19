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


class TestArgumentWiring:
    def test_defaults_pass_none_through_to_pipeline_run(self, monkeypatch, capsys):
        captured = {}

        def fake_run(**kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(cli, "run", fake_run)

        exit_code = cli.main([])

        assert exit_code == 0
        assert captured == {
            "registry_dir": None,
            "site_dir": None,
            "source_id": None,
            "limit": None,
            "dry_run": False,
        }

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
