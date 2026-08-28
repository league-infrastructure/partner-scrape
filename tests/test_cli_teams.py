"""Tests for partner_scrape.cli's `teams` subcommand (sprint 011,
ticket 002).

Mirrors `test_cli.py`'s existing convention exactly:
`TestArgumentWiring`-style classes monkeypatch `cli.run_teams` to prove
flag parsing/wiring only, and `TestTeamsEndToEnd` exercises the real
`run_teams()` -> `FTCScoutSource` chain against the actual seeded
`partner_scrape/teams/registry/ftc-sd.toml`, substituting only
`cli.PoliteFetcher` with a fixture double so no real socket is opened --
the same substitution point `TestDiscoverCandidatesEndToEnd` in
`test_cli.py` already uses for its own subcommand.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from partner_scrape import cli
from partner_scrape.fetch import PoliteFetcher
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.teams.sources.ftcscout import DEFAULT_API_BASE, DEFAULT_REGION, _search_url

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "teams"
SEARCH_URL = _search_url(DEFAULT_API_BASE, DEFAULT_REGION)


@pytest.fixture(autouse=True)
def _cache_dir(tmp_path, monkeypatch):
    """`_run_teams` constructs a real `PoliteFetcher()` before calling
    `run_teams()` -- even in wiring tests that monkeypatch `cli.run_teams`
    itself -- and `PoliteFetcher()`'s default `cache_dir` reads
    `SCRAPE_CACHE_DIR` eagerly (see `config.get_scrape_cache_dir`'s "no
    sane default" `RuntimeError`). `SITE_DIR` is pinned too so any test
    that omits `--site-dir` can never reach the real sibling
    `../stem-ecosystem` checkout, matching `test_cli.py`'s own `_cache_dir`
    fixture."""
    monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("SITE_DIR", str(tmp_path))
    # `cli.main()`'s no-subcommand/`run` path calls `publish.project(...)`
    # after `run()` returns, which raises loudly on a missing curated
    # `partners.json` -- only `TestNeverCrossesIntoTheOtherPipeline`'s
    # regression test below reaches that path at all, but it is stubbed
    # here unconditionally, matching `test_cli.py`'s own `_cache_dir`
    # fixture, so this file never needs to know about that unrelated
    # pipeline step.
    monkeypatch.setattr(
        cli.publish,
        "project",
        lambda **kwargs: {"partner_count": 0, "current_event_count": 0, "past_event_count": 0},
    )
    return tmp_path


@dataclass
class _FixtureFetcher:
    responses: dict[str, FetchResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        return self.responses[url]


def _ftcscout_fixture_fetcher() -> _FixtureFetcher:
    body = (FIXTURES_DIR / "ftcscout_search.json").read_text()
    return _FixtureFetcher({SEARCH_URL: FetchResponse(url="", status=200, headers={}, body=body)})


def _make_site(root: Path) -> Path:
    (root / "src" / "data").mkdir(parents=True)
    return root


class TestArgumentWiring:
    def test_defaults_pass_none_through_and_construct_a_polite_fetcher(self, monkeypatch):
        captured = {}

        def fake_run_teams(**kwargs):
            captured.update(kwargs)
            return {"meta": {"total": 0}, "teams": []}

        monkeypatch.setattr(cli, "run_teams", fake_run_teams)

        exit_code = cli.main(["teams"])

        assert exit_code == 0
        assert captured["source"] is None
        assert captured["site_dir"] is None
        assert captured["dry_run"] is False
        assert isinstance(captured["fetcher"], PoliteFetcher)

    def test_flags_are_parsed_and_forwarded(self, monkeypatch, tmp_path):
        captured = {}

        def fake_run_teams(**kwargs):
            captured.update(kwargs)
            return {"meta": {"total": 0}, "teams": []}

        monkeypatch.setattr(cli, "run_teams", fake_run_teams)

        site_dir = tmp_path / "site"
        exit_code = cli.main(
            ["teams", "--dry-run", "--source", "ftcscout", "--site-dir", str(site_dir)]
        )

        assert exit_code == 0
        assert captured["dry_run"] is True
        assert captured["source"] == "ftcscout"
        assert captured["site_dir"] == site_dir

    def test_prints_a_summary_including_the_written_team_count(self, monkeypatch, capsys):
        monkeypatch.setattr(
            cli,
            "run_teams",
            lambda **kwargs: {
                "meta": {"total": 2},
                "teams": [{"team_id": "ftc-1"}, {"team_id": "ftc-2"}],
            },
        )

        cli.main(["teams"])

        out = capsys.readouterr().out
        assert "2" in out
        assert "teams" in out

    def test_dry_run_summary_notes_nothing_was_written(self, monkeypatch, capsys):
        monkeypatch.setattr(
            cli,
            "run_teams",
            lambda **kwargs: {"meta": {"total": 1}, "teams": [{"team_id": "ftc-1"}]},
        )

        cli.main(["teams", "--dry-run"])

        out = capsys.readouterr().out
        assert "dry run" in out.lower()

    def test_help_text_lists_the_teams_flags(self, capsys):
        with pytest.raises(SystemExit):
            cli.main(["teams", "--help"])

        out = capsys.readouterr().out
        assert "--dry-run" in out
        assert "--source" in out
        assert "--site-dir" in out
        assert "--no-mirror" in out

    def test_top_level_help_text_mentions_the_teams_subcommand(self, capsys):
        with pytest.raises(SystemExit):
            cli.main(["--help"])

        out = capsys.readouterr().out
        assert "teams" in out


class TestMirrorWiring:
    def test_mirror_is_called_when_not_dry_run_and_not_no_mirror(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            cli, "run_teams", lambda **kwargs: {"meta": {"total": 0}, "teams": []}
        )
        captured = {}

        def fake_mirror(primary, targets, **kwargs):
            captured["primary"] = primary
            captured["targets"] = targets

        monkeypatch.setattr(cli, "mirror_site_data", fake_mirror)
        monkeypatch.setattr(cli, "get_mirror_site_dirs", lambda: [tmp_path / "mirror-target"])

        site_dir = tmp_path / "site"
        exit_code = cli.main(["teams", "--site-dir", str(site_dir)])

        assert exit_code == 0
        assert captured["primary"] == site_dir
        assert captured["targets"] == [tmp_path / "mirror-target"]

    def test_no_mirror_flag_skips_mirroring(self, monkeypatch, tmp_path):
        def _boom(*args, **kwargs):
            raise AssertionError("mirror_site_data must not be called under --no-mirror")

        monkeypatch.setattr(
            cli, "run_teams", lambda **kwargs: {"meta": {"total": 0}, "teams": []}
        )
        monkeypatch.setattr(cli, "mirror_site_data", _boom)
        monkeypatch.setattr(cli, "get_mirror_site_dirs", lambda: [tmp_path / "mirror-target"])

        exit_code = cli.main(["teams", "--no-mirror"])  # must not raise

        assert exit_code == 0

    def test_dry_run_skips_mirroring(self, monkeypatch, tmp_path):
        def _boom(*args, **kwargs):
            raise AssertionError("mirror_site_data must not be called under --dry-run")

        monkeypatch.setattr(
            cli, "run_teams", lambda **kwargs: {"meta": {"total": 0}, "teams": []}
        )
        monkeypatch.setattr(cli, "mirror_site_data", _boom)
        monkeypatch.setattr(cli, "get_mirror_site_dirs", lambda: [tmp_path / "mirror-target"])

        exit_code = cli.main(["teams", "--dry-run"])  # must not raise

        assert exit_code == 0

    def test_no_mirror_targets_configured_skips_mirror_call(self, monkeypatch, tmp_path):
        def _boom(*args, **kwargs):
            raise AssertionError("mirror_site_data must not be called with no targets")

        monkeypatch.setattr(
            cli, "run_teams", lambda **kwargs: {"meta": {"total": 0}, "teams": []}
        )
        monkeypatch.setattr(cli, "mirror_site_data", _boom)
        monkeypatch.setattr(cli, "get_mirror_site_dirs", lambda: [])

        exit_code = cli.main(["teams"])  # must not raise

        assert exit_code == 0


class TestNeverCrossesIntoTheOtherPipeline:
    """The two subcommands' structural isolation, at the CLI layer: a
    `teams` invocation must never reach `pipeline.run()`, and the
    default `run` invocation must never reach `run_teams()`."""

    def test_teams_never_calls_the_opportunities_pipeline(self, monkeypatch):
        def _boom(**kwargs):
            raise AssertionError("teams subcommand must never call pipeline.run()")

        monkeypatch.setattr(cli, "run", _boom)
        monkeypatch.setattr(
            cli, "run_teams", lambda **kwargs: {"meta": {"total": 0}, "teams": []}
        )

        exit_code = cli.main(["teams"])  # must not raise

        assert exit_code == 0

    def test_default_run_never_calls_run_teams(self, monkeypatch):
        def _boom(**kwargs):
            raise AssertionError("the no-subcommand/run path must never call run_teams")

        monkeypatch.setattr(cli, "run_teams", _boom)
        monkeypatch.setattr(cli, "run", lambda **kwargs: [])

        exit_code = cli.main([])  # must not raise

        assert exit_code == 0


class TestTeamsEndToEnd:
    """A genuine end-to-end run against the real seeded
    `partner_scrape/teams/registry/ftc-sd.toml` -- only `cli.PoliteFetcher`
    is substituted with a fixture double, so no real socket is ever
    opened. Matches this ticket's Acceptance Criteria: "partner-scrape
    teams --dry-run -v against ticket 001's fixture reports 152 FTC
    teams with no network access and no disk write."
    """

    def test_dry_run_reports_152_teams_with_no_network_and_no_disk_write(
        self, monkeypatch, tmp_path, capsys
    ):
        fetcher = _ftcscout_fixture_fetcher()
        monkeypatch.setattr(cli, "PoliteFetcher", lambda: fetcher)

        site_dir = tmp_path / "site"
        exit_code = cli.main(
            ["teams", "--dry-run", "-v", "--site-dir", str(site_dir)]
        )

        assert exit_code == 0
        # No live network call: every URL the fixture Fetcher was asked
        # for came from its own canned `responses` dict.
        assert fetcher.calls == [SEARCH_URL]
        out = capsys.readouterr().out
        assert "152" in out
        assert "dry run" in out.lower()
        assert not site_dir.exists()

    def test_real_run_writes_teams_json_and_mirrors_to_a_target(self, monkeypatch, tmp_path):
        fetcher = _ftcscout_fixture_fetcher()
        monkeypatch.setattr(cli, "PoliteFetcher", lambda: fetcher)

        site_dir = _make_site(tmp_path / "site")
        target = _make_site(tmp_path / "mirror-target")
        monkeypatch.setattr(cli, "get_mirror_site_dirs", lambda: [target])

        exit_code = cli.main(["teams", "--site-dir", str(site_dir)])

        assert exit_code == 0
        primary_teams = json.loads((site_dir / "src" / "data" / "teams.json").read_text())
        assert primary_teams["meta"]["total"] == 152
        mirrored_teams = json.loads((target / "src" / "data" / "teams.json").read_text())
        assert mirrored_teams == primary_teams

    def test_no_mirror_flag_leaves_the_target_untouched(self, monkeypatch, tmp_path):
        fetcher = _ftcscout_fixture_fetcher()
        monkeypatch.setattr(cli, "PoliteFetcher", lambda: fetcher)

        site_dir = _make_site(tmp_path / "site")
        target = _make_site(tmp_path / "mirror-target")
        monkeypatch.setattr(cli, "get_mirror_site_dirs", lambda: [target])

        exit_code = cli.main(["teams", "--site-dir", str(site_dir), "--no-mirror"])

        assert exit_code == 0
        assert not (target / "src" / "data" / "teams.json").exists()

    def test_never_writes_opportunities_json_or_scrape_meta_anywhere(
        self, monkeypatch, tmp_path
    ):
        fetcher = _ftcscout_fixture_fetcher()
        monkeypatch.setattr(cli, "PoliteFetcher", lambda: fetcher)
        # No mirror target configured here -- keeps this test hermetic to
        # tmp_path (an unmonkeypatched get_mirror_site_dirs() would
        # default to this repo's own site/ checkout, which every other
        # test in this class explicitly avoids via a fixture target).
        monkeypatch.setattr(cli, "get_mirror_site_dirs", lambda: [])

        site_dir = _make_site(tmp_path / "site")
        cli.main(["teams", "--site-dir", str(site_dir)])

        assert not list(tmp_path.rglob("opportunities.json"))
        assert not list(tmp_path.rglob("scrape-meta.json"))
