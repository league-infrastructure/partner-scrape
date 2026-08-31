"""Tests for partner_scrape.cli's `directory` subcommand (sprint 018,
ticket 007).

Mirrors `test_cli_teams.py`'s existing convention exactly:
`TestArgumentWiring`-style classes monkeypatch `cli.run_directory` to
prove flag parsing/wiring only, and `TestDirectoryEndToEnd` exercises
the real `run_directory()` -> `StaticRosterSource` chain against the
actual seeded `partner_scrape/directory/registry/places-sd.toml`,
substituting only `cli.PoliteFetcher` with a fixture double that raises
on any call -- proving the real run touches no network, the same
substitution point `TestTeamsEndToEnd` in `test_cli_teams.py` already
uses for its own subcommand.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from partner_scrape import cli
from partner_scrape.fetch import PoliteFetcher
from partner_scrape.fetch.fetcher import FetchResponse


@pytest.fixture(autouse=True)
def _cache_dir(tmp_path, monkeypatch):
    """`_run_directory` constructs a real `PoliteFetcher()` before
    calling `run_directory()` -- even in wiring tests that monkeypatch
    `cli.run_directory` itself -- and `PoliteFetcher()`'s default
    `cache_dir` reads `SCRAPE_CACHE_DIR` eagerly. `SITE_DIR` is pinned
    too so any test that omits `--site-dir` can never reach the real
    sibling `../stem-ecosystem` checkout, matching `test_cli_teams.py`'s
    own `_cache_dir` fixture."""
    monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("SITE_DIR", str(tmp_path))
    monkeypatch.setattr(
        cli.publish,
        "project",
        lambda **kwargs: {"partner_count": 0, "current_event_count": 0, "past_event_count": 0},
    )
    return tmp_path


class _NeverCalledFetcher:
    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        raise AssertionError("directory subcommand must never call the injected Fetcher")


def _make_site(root: Path) -> Path:
    (root / "src" / "data").mkdir(parents=True)
    return root


class TestArgumentWiring:
    def test_defaults_pass_none_through_and_construct_a_polite_fetcher(self, monkeypatch):
        captured = {}

        def fake_run_directory(**kwargs):
            captured.update(kwargs)
            return {"meta": {"total": 0}, "places": []}

        monkeypatch.setattr(cli, "run_directory", fake_run_directory)

        exit_code = cli.main(["directory"])

        assert exit_code == 0
        assert captured["source"] is None
        assert captured["site_dir"] is None
        assert captured["dry_run"] is False
        assert isinstance(captured["fetcher"], PoliteFetcher)

    def test_flags_are_parsed_and_forwarded(self, monkeypatch, tmp_path):
        captured = {}

        def fake_run_directory(**kwargs):
            captured.update(kwargs)
            return {"meta": {"total": 0}, "places": []}

        monkeypatch.setattr(cli, "run_directory", fake_run_directory)

        site_dir = tmp_path / "site"
        exit_code = cli.main(
            [
                "directory",
                "--dry-run",
                "--source",
                "static_roster",
                "--site-dir",
                str(site_dir),
            ]
        )

        assert exit_code == 0
        assert captured["dry_run"] is True
        assert captured["source"] == "static_roster"
        assert captured["site_dir"] == site_dir

    def test_prints_a_summary_including_the_written_place_count(self, monkeypatch, capsys):
        monkeypatch.setattr(
            cli,
            "run_directory",
            lambda **kwargs: {
                "meta": {"total": 2},
                "places": [{"place_id": "a"}, {"place_id": "b"}],
            },
        )

        cli.main(["directory"])

        out = capsys.readouterr().out
        assert "2" in out
        assert "places" in out

    def test_dry_run_summary_notes_nothing_was_written(self, monkeypatch, capsys):
        monkeypatch.setattr(
            cli,
            "run_directory",
            lambda **kwargs: {"meta": {"total": 1}, "places": [{"place_id": "a"}]},
        )

        cli.main(["directory", "--dry-run"])

        out = capsys.readouterr().out
        assert "dry run" in out.lower()

    def test_help_text_lists_the_directory_flags(self, capsys):
        with pytest.raises(SystemExit):
            cli.main(["directory", "--help"])

        out = capsys.readouterr().out
        assert "--dry-run" in out
        assert "--source" in out
        assert "--site-dir" in out
        assert "--no-mirror" in out

    def test_top_level_help_text_mentions_the_directory_subcommand(self, capsys):
        with pytest.raises(SystemExit):
            cli.main(["--help"])

        out = capsys.readouterr().out
        assert "directory" in out


class TestMirrorWiring:
    def test_mirror_is_called_when_not_dry_run_and_not_no_mirror(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            cli, "run_directory", lambda **kwargs: {"meta": {"total": 0}, "places": []}
        )
        captured = {}

        def fake_mirror(primary, targets, **kwargs):
            captured["primary"] = primary
            captured["targets"] = targets

        monkeypatch.setattr(cli, "mirror_site_data", fake_mirror)
        monkeypatch.setattr(cli, "get_mirror_site_dirs", lambda: [tmp_path / "mirror-target"])

        site_dir = tmp_path / "site"
        exit_code = cli.main(["directory", "--site-dir", str(site_dir)])

        assert exit_code == 0
        assert captured["primary"] == site_dir
        assert captured["targets"] == [tmp_path / "mirror-target"]

    def test_no_mirror_flag_skips_mirroring(self, monkeypatch, tmp_path):
        def _boom(*args, **kwargs):
            raise AssertionError("mirror_site_data must not be called under --no-mirror")

        monkeypatch.setattr(
            cli, "run_directory", lambda **kwargs: {"meta": {"total": 0}, "places": []}
        )
        monkeypatch.setattr(cli, "mirror_site_data", _boom)
        monkeypatch.setattr(cli, "get_mirror_site_dirs", lambda: [tmp_path / "mirror-target"])

        exit_code = cli.main(["directory", "--no-mirror"])  # must not raise

        assert exit_code == 0

    def test_dry_run_skips_mirroring(self, monkeypatch, tmp_path):
        def _boom(*args, **kwargs):
            raise AssertionError("mirror_site_data must not be called under --dry-run")

        monkeypatch.setattr(
            cli, "run_directory", lambda **kwargs: {"meta": {"total": 0}, "places": []}
        )
        monkeypatch.setattr(cli, "mirror_site_data", _boom)
        monkeypatch.setattr(cli, "get_mirror_site_dirs", lambda: [tmp_path / "mirror-target"])

        exit_code = cli.main(["directory", "--dry-run"])  # must not raise

        assert exit_code == 0

    def test_no_mirror_targets_configured_skips_mirror_call(self, monkeypatch, tmp_path):
        def _boom(*args, **kwargs):
            raise AssertionError("mirror_site_data must not be called with no targets")

        monkeypatch.setattr(
            cli, "run_directory", lambda **kwargs: {"meta": {"total": 0}, "places": []}
        )
        monkeypatch.setattr(cli, "mirror_site_data", _boom)
        monkeypatch.setattr(cli, "get_mirror_site_dirs", lambda: [])

        exit_code = cli.main(["directory"])  # must not raise

        assert exit_code == 0


class TestNeverCrossesIntoOtherPipelines:
    """The three subcommands' structural isolation, at the CLI layer."""

    def test_directory_never_calls_the_opportunities_pipeline(self, monkeypatch):
        def _boom(**kwargs):
            raise AssertionError("directory subcommand must never call pipeline.run()")

        monkeypatch.setattr(cli, "run", _boom)
        monkeypatch.setattr(
            cli, "run_directory", lambda **kwargs: {"meta": {"total": 0}, "places": []}
        )

        exit_code = cli.main(["directory"])  # must not raise

        assert exit_code == 0

    def test_directory_never_calls_run_teams(self, monkeypatch):
        def _boom(**kwargs):
            raise AssertionError("directory subcommand must never call run_teams()")

        monkeypatch.setattr(cli, "run_teams", _boom)
        monkeypatch.setattr(
            cli, "run_directory", lambda **kwargs: {"meta": {"total": 0}, "places": []}
        )

        exit_code = cli.main(["directory"])  # must not raise

        assert exit_code == 0

    def test_default_run_never_calls_run_directory(self, monkeypatch):
        def _boom(**kwargs):
            raise AssertionError("the no-subcommand/run path must never call run_directory")

        monkeypatch.setattr(cli, "run_directory", _boom)
        monkeypatch.setattr(cli, "run", lambda **kwargs: [])

        exit_code = cli.main([])  # must not raise

        assert exit_code == 0

    def test_teams_never_calls_run_directory(self, monkeypatch):
        def _boom(**kwargs):
            raise AssertionError("the teams subcommand must never call run_directory")

        monkeypatch.setattr(cli, "run_directory", _boom)
        monkeypatch.setattr(
            cli, "run_teams", lambda **kwargs: {"meta": {"total": 0}, "teams": []}
        )

        exit_code = cli.main(["teams"])  # must not raise

        assert exit_code == 0


class TestDirectoryEndToEnd:
    """A genuine end-to-end run against the real seeded
    `partner_scrape/directory/registry/places-sd.toml` and the real
    committed `places.toml` roster -- only `cli.PoliteFetcher` is
    substituted with a double that raises on any call, so no real
    socket is ever opened (the static_roster source never calls it
    anyway, but this proves that structurally, not just by reading the
    source)."""

    def test_dry_run_reports_19_places_with_no_network_and_no_disk_write(
        self, monkeypatch, tmp_path, capsys
    ):
        monkeypatch.setattr(cli, "PoliteFetcher", lambda: _NeverCalledFetcher())

        site_dir = tmp_path / "site"
        exit_code = cli.main(
            ["directory", "--dry-run", "-v", "--site-dir", str(site_dir)]
        )

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "19" in out
        assert "dry run" in out.lower()
        assert not site_dir.exists()

    def test_real_run_writes_places_json_and_mirrors_to_a_target(self, monkeypatch, tmp_path):
        monkeypatch.setattr(cli, "PoliteFetcher", lambda: _NeverCalledFetcher())

        site_dir = _make_site(tmp_path / "site")
        target = _make_site(tmp_path / "mirror-target")
        monkeypatch.setattr(cli, "get_mirror_site_dirs", lambda: [target])

        exit_code = cli.main(["directory", "--site-dir", str(site_dir)])

        assert exit_code == 0
        primary_places = json.loads((site_dir / "src" / "data" / "places.json").read_text())
        assert primary_places["meta"]["total"] == 19
        mirrored_places = json.loads((target / "src" / "data" / "places.json").read_text())
        assert mirrored_places == primary_places

    def test_no_mirror_flag_leaves_the_target_untouched(self, monkeypatch, tmp_path):
        monkeypatch.setattr(cli, "PoliteFetcher", lambda: _NeverCalledFetcher())

        site_dir = _make_site(tmp_path / "site")
        target = _make_site(tmp_path / "mirror-target")
        monkeypatch.setattr(cli, "get_mirror_site_dirs", lambda: [target])

        exit_code = cli.main(["directory", "--site-dir", str(site_dir), "--no-mirror"])

        assert exit_code == 0
        assert not (target / "src" / "data" / "places.json").exists()

    def test_never_writes_opportunities_json_scrape_meta_or_teams_json_anywhere(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(cli, "PoliteFetcher", lambda: _NeverCalledFetcher())
        monkeypatch.setattr(cli, "get_mirror_site_dirs", lambda: [])

        site_dir = _make_site(tmp_path / "site")
        cli.main(["directory", "--site-dir", str(site_dir)])

        assert not list(tmp_path.rglob("opportunities.json"))
        assert not list(tmp_path.rglob("scrape-meta.json"))
        assert not list(tmp_path.rglob("teams.json"))
