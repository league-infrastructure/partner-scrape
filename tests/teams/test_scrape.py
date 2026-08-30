"""Tests for partner_scrape.teams.scrape: per-team website liveness
verification (sprint 013 ticket 001).

Every test drives ``verify_team_websites`` through a fixture ``Fetcher``
returning canned responses -- no test here opens a real network socket,
matching every other ``teams/`` test module's convention.
``FixtureFetcher`` mirrors ``tests/test_discovery_hub_scan.py``'s own
double (the module the ticket names as the per-page robots-check-then-
fetch pattern to match): a URL absent from ``responses`` raises
``KeyError`` -- a loud failure if ``verify_team_websites`` ever fetches
something it shouldn't (a robots.txt-disallowed team page, or any URL
at all for a team with no ``website``).
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass, field

from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.fetch.robots import robots_txt_url
from partner_scrape.teams.model import Team
from partner_scrape.teams.scrape import verify_team_websites

_ALLOW_ALL_ROBOTS = "User-agent: *\nDisallow:\n"
_DISALLOW_ALL_ROBOTS = "User-agent: *\nDisallow: /\n"


def _response(body: str = "", status: int = 200) -> FetchResponse:
    return FetchResponse(url="", status=status, headers={}, body=body)


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.

    A URL absent from ``responses`` raises ``KeyError`` -- a loud
    failure if ``verify_team_websites`` fetches something it shouldn't.
    """

    responses: dict[str, FetchResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        return self.responses[url]


def _team(team_id: str = "frc-1234", website: str = "", name: str = "Team Example") -> Team:
    return Team(team_id=team_id, league="FRC", name=name, website=website)


class TestConfirmedOnTwoHundred:
    def test_2xx_sets_confirmed_and_returns_body(self):
        url = "https://team1234.example.org/"
        fetcher = FixtureFetcher(
            {
                robots_txt_url(url): _response(_ALLOW_ALL_ROBOTS),
                url: _response("<html>Team 1234 homepage</html>", status=200),
            }
        )
        team = _team(website=url)

        result = verify_team_websites([team], fetcher)

        assert team.website_status == "confirmed"
        assert result == {"frc-1234": "<html>Team 1234 homepage</html>"}

    def test_a_2xx_other_than_200_also_confirms(self):
        url = "https://team1234.example.org/"
        fetcher = FixtureFetcher(
            {
                robots_txt_url(url): _response(_ALLOW_ALL_ROBOTS),
                url: _response("content", status=204),
            }
        )
        team = _team(website=url)

        verify_team_websites([team], fetcher)

        assert team.website_status == "confirmed"


class TestUnverifiedOnNonTwoHundred:
    def test_404_sets_unverified_logs_and_excludes_body(self, caplog):
        url = "https://deadteam.example.org/"
        fetcher = FixtureFetcher(
            {
                robots_txt_url(url): _response(_ALLOW_ALL_ROBOTS),
                url: _response("", status=404),
            }
        )
        team = _team(website=url)

        with caplog.at_level(logging.WARNING):
            result = verify_team_websites([team], fetcher)

        assert team.website_status == "unverified"
        assert result == {}
        assert team.team_id in caplog.text
        assert "404" in caplog.text

    def test_500_sets_unverified_and_excludes_body(self, caplog):
        url = "https://brokenteam.example.org/"
        fetcher = FixtureFetcher(
            {
                robots_txt_url(url): _response(_ALLOW_ALL_ROBOTS),
                url: _response("", status=500),
            }
        )
        team = _team(website=url)

        with caplog.at_level(logging.WARNING):
            result = verify_team_websites([team], fetcher)

        assert team.website_status == "unverified"
        assert result == {}

    def test_transport_error_status_zero_sets_unverified_and_logs(self, caplog):
        # UrllibFetcher's synthetic sentinel for DNS/TLS/timeout/reset
        # failures -- never an HTTP status, must not be mistaken for a
        # 2xx or crash the range check.
        url = "https://unreachable.example.org/"
        fetcher = FixtureFetcher(
            {
                robots_txt_url(url): _response(_ALLOW_ALL_ROBOTS),
                url: _response("", status=0),
            }
        )
        team = _team(website=url)

        with caplog.at_level(logging.WARNING):
            result = verify_team_websites([team], fetcher)

        assert team.website_status == "unverified"
        assert result == {}
        assert "transport error" in caplog.text.lower()


class TestNoWebsiteMeansNone:
    def test_empty_website_sets_none_and_is_never_fetched(self):
        fetcher = FixtureFetcher({})
        team = _team(website="")

        result = verify_team_websites([team], fetcher)

        assert team.website_status == "none"
        assert result == {}
        assert fetcher.calls == []


class TestRobotsCompliance:
    def test_disallowed_url_sets_unverified_never_fetched_never_raises(self):
        url = "https://disallowed.example.org/private"
        fetcher = FixtureFetcher(
            {
                robots_txt_url(url): _response(_DISALLOW_ALL_ROBOTS),
                # Deliberately no entry for `url` itself -- if
                # verify_team_websites ever called fetcher.get(url) here
                # it must raise KeyError and fail this test loudly.
            }
        )
        team = _team(website=url)

        result = verify_team_websites([team], fetcher)  # must not raise

        assert team.website_status == "unverified"
        assert result == {}
        assert url not in fetcher.calls

    def test_disallowed_team_does_not_affect_other_teams(self):
        disallowed_url = "https://disallowed.example.org/private"
        allowed_url = "https://allowed.example.org/"
        fetcher = FixtureFetcher(
            {
                robots_txt_url(disallowed_url): _response(_DISALLOW_ALL_ROBOTS),
                robots_txt_url(allowed_url): _response(_ALLOW_ALL_ROBOTS),
                allowed_url: _response("<html>allowed</html>", status=200),
            }
        )
        blocked = _team(team_id="frc-1", website=disallowed_url)
        ok = _team(team_id="frc-2", website=allowed_url)

        result = verify_team_websites([blocked, ok], fetcher)

        assert blocked.website_status == "unverified"
        assert ok.website_status == "confirmed"
        assert result == {"frc-2": "<html>allowed</html>"}


class TestMixedTeamsIsolated:
    def test_each_teams_outcome_is_independent(self):
        confirmed_url = "https://good.example.org/"
        unverified_url = "https://bad.example.org/"
        fetcher = FixtureFetcher(
            {
                robots_txt_url(confirmed_url): _response(_ALLOW_ALL_ROBOTS),
                confirmed_url: _response("<html>ok</html>", status=200),
                robots_txt_url(unverified_url): _response(_ALLOW_ALL_ROBOTS),
                unverified_url: _response("", status=404),
            }
        )
        good = _team(team_id="frc-1", website=confirmed_url)
        bad = _team(team_id="frc-2", website=unverified_url)
        none_team = _team(team_id="ftc-1", website="")

        result = verify_team_websites([good, bad, none_team], fetcher)

        assert good.website_status == "confirmed"
        assert bad.website_status == "unverified"
        assert none_team.website_status == "none"
        assert result == {"frc-1": "<html>ok</html>"}


class TestNeverLeaksHtmlOntoTeamFields:
    """The regression test ticket 001's Acceptance Criteria and
    sprint.md's Test Strategy both require: no fetched HTML body ever
    reaches a `Team` field. A cheap proxy for "not multi-KB page
    content": no field's string value exceeds a small bound after a
    real (confirmed, large-body) fetch.
    """

    def test_no_field_value_after_verification_carries_page_content(self):
        url = "https://team1234.example.org/"
        big_body = "<html>" + ("sponsor logo wall " * 500) + "</html>"
        assert len(big_body) > 2000  # sanity check the fixture is actually big
        fetcher = FixtureFetcher(
            {
                robots_txt_url(url): _response(_ALLOW_ALL_ROBOTS),
                url: _response(big_body, status=200),
            }
        )
        team = _team(website=url)

        result = verify_team_websites([team], fetcher)

        # Confirms the body really was fetched and returned -- so the
        # field-scan below is a real regression test, not vacuously
        # true because nothing large was ever produced.
        assert result[team.team_id] == big_body

        for f in dataclasses.fields(team):
            value = getattr(team, f.name)
            assert len(str(value)) < 2000, (
                f"Team.{f.name} unexpectedly carries a long value after "
                "verify_team_websites() -- possible HTML-body leak onto a "
                "Team field"
            )
