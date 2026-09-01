"""Tests for partner_scrape.teams.description_extract: sprint 021
ticket 004's orchestration -- gather content -> cache lookup ->
summarize on a miss -> no-email/length guard -> publish
`Team.description`/`description_status`/`description_provenance`/
`description_fetched_at`.

Every test drives `extract_descriptions()` through a fixture
`DescriptionLLMClient` (`FixtureDescriptionLLMClient` or a small raising
double) and a real `DescriptionCache` rooted at `tmp_path` -- no test
here opens a real network socket or calls the real `anthropic` SDK.

The **required** test in this file, matching this ticket's own
acceptance criteria, is `TestNoEmailGuard`: a fixture LLM client
configured to return text containing an email address must have that
result dropped and logged, never published. This is the no-email
guard's layer 3 of 3 (module docstring) -- everything else in this file
is defense-in-depth or sequencing/failure-isolation coverage around it.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import partner_scrape.teams.description_extract as description_extract_module
from partner_scrape.teams.description_cache import DescriptionCache
from partner_scrape.teams.description_candidates import gather_description_content
from partner_scrape.teams.description_extract import extract_descriptions
from partner_scrape.teams.description_llm import (
    DescriptionExtractionResult,
    FixtureDescriptionLLMClient,
)
from partner_scrape.teams.model import Team

#: A real-shaped (hand-authored, matching sponsor_extract's own test
#: fixture precedent) team homepage carrying a meta description, a
#: title, and a heading/paragraph -- gather_description_content()
#: extracts and concatenates all three into a non-empty content string.
_DESCRIPTION_HTML = """
<html>
<head>
<meta name="description" content="Team Spyder is a FIRST Tech Challenge robotics team from Poway.">
<title>Team Spyder | FTC 1622</title>
</head>
<body>
<h1>Team Spyder</h1>
<p>We build robots, compete regionally, and love STEM outreach.</p>
</body>
</html>
"""

#: A page with no description-shaped content at all -- no meta
#: description, no title, no heading/paragraph text -- matching
#: gather_description_content()'s own documented "" return contract.
_NO_CONTENT_HTML = "<html><body><div></div></body></html>"

_FIXED_CLOCK = lambda: datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)  # noqa: E731


def _team(**overrides) -> Team:
    defaults: dict = dict(
        team_id="ftc-1622",
        league="FTC",
        program="FIRST Tech Challenge",
        number=1622,
        name="Team Spyder",
        organization="Poway High School",
        website="https://www.teamspyder.org/",
        sources=["ftcscout"],
    )
    defaults.update(overrides)
    return Team(**defaults)


class TestSuccessfulSummarization:
    """AC: extract_descriptions() sets all four fields correctly on a
    successful summarization."""

    def test_all_four_fields_set_on_success(self, tmp_path):
        team = _team()
        content = gather_description_content(_DESCRIPTION_HTML, team.website)
        assert content  # sanity: really gathered something

        llm_client = FixtureDescriptionLLMClient(
            responses={
                content: DescriptionExtractionResult(
                    description="Team Spyder is a FTC robotics team from Poway."
                ),
            }
        )
        cache = DescriptionCache(cache_dir=tmp_path)

        extract_descriptions(
            [team],
            {team.team_id: _DESCRIPTION_HTML},
            llm_client,
            cache,
            clock=_FIXED_CLOCK,
        )

        assert team.description == "Team Spyder is a FTC robotics team from Poway."
        assert team.description_status == "generated"
        assert team.description_provenance == "team_website"
        assert team.description_fetched_at == "2026-08-30T12:00:00+00:00"


class TestNoEmailGuard:
    """The required test (this ticket's own acceptance criteria): a
    fixture LLM response containing an email address is rejected --
    description stays empty, description_status == "unavailable",
    logged, never published."""

    def test_an_email_in_the_llm_response_is_rejected_and_logged(self, tmp_path, caplog):
        team = _team()
        content = gather_description_content(_DESCRIPTION_HTML, team.website)
        llm_client = FixtureDescriptionLLMClient(
            responses={
                content: DescriptionExtractionResult(
                    description="Contact us at coach@teamspyder.org for more info."
                ),
            }
        )
        cache = DescriptionCache(cache_dir=tmp_path)

        with caplog.at_level(logging.WARNING):
            extract_descriptions(
                [team], {team.team_id: _DESCRIPTION_HTML}, llm_client, cache
            )

        assert team.description == ""
        assert team.description_status == "unavailable"
        assert team.description_provenance == ""
        assert team.description_fetched_at == ""
        assert team.team_id in caplog.text
        # The guard deliberately never logs the raw email-carrying text
        # itself (module docstring) -- only the rejection is logged.
        assert "coach@teamspyder.org" not in caplog.text


class TestEmptyLlmResponse:
    """AC: an empty LLM response (nothing substantive to summarize)
    yields description_status == "unavailable", never "generated" with
    an empty string."""

    def test_empty_description_never_publishes_as_generated(self, tmp_path):
        team = _team()
        content = gather_description_content(_DESCRIPTION_HTML, team.website)
        llm_client = FixtureDescriptionLLMClient(
            responses={content: DescriptionExtractionResult(description="")}
        )
        cache = DescriptionCache(cache_dir=tmp_path)

        extract_descriptions([team], {team.team_id: _DESCRIPTION_HTML}, llm_client, cache)

        assert team.description == ""
        assert team.description_status == "unavailable"
        assert team.description_provenance == ""
        assert team.description_fetched_at == ""


class TestLengthGuard:
    """Defense-in-depth: a response exceeding the documented maximum
    length is rejected the same way as an email match, mirroring
    sponsor_extract._MAX_SPONSOR_NAME_LENGTH's own precedent."""

    def test_an_oversized_response_is_rejected(self, tmp_path, caplog):
        team = _team()
        content = gather_description_content(_DESCRIPTION_HTML, team.website)
        oversized = "A" * (description_extract_module._MAX_DESCRIPTION_LENGTH + 1)
        llm_client = FixtureDescriptionLLMClient(
            responses={content: DescriptionExtractionResult(description=oversized)}
        )
        cache = DescriptionCache(cache_dir=tmp_path)

        with caplog.at_level(logging.WARNING):
            extract_descriptions([team], {team.team_id: _DESCRIPTION_HTML}, llm_client, cache)

        assert team.description == ""
        assert team.description_status == "unavailable"
        assert team.team_id in caplog.text

    def test_a_response_at_exactly_the_cap_is_not_rejected(self, tmp_path):
        team = _team()
        content = gather_description_content(_DESCRIPTION_HTML, team.website)
        exactly_at_cap = "A" * description_extract_module._MAX_DESCRIPTION_LENGTH
        llm_client = FixtureDescriptionLLMClient(
            responses={content: DescriptionExtractionResult(description=exactly_at_cap)}
        )
        cache = DescriptionCache(cache_dir=tmp_path)

        extract_descriptions([team], {team.team_id: _DESCRIPTION_HTML}, llm_client, cache)

        assert team.description == exactly_at_cap
        assert team.description_status == "generated"

    def test_a_real_genuine_long_description_observed_live_is_not_rejected(self, tmp_path):
        # Regression test for this ticket's own required pre-close
        # live-run review (see the ticket's Notes): this is the exact
        # 546-character description a real live run generated for team
        # ftc-11212 ("The Clueless"), verbatim -- every fact in it was
        # independently verified against the team's own live website
        # (no fabrication). It was wrongly rejected by an initial
        # _MAX_DESCRIPTION_LENGTH == 500; this proves the corrected
        # bound (800) accepts it. Mirrors sponsor_extract.py's own
        # `test_a_long_but_genuine_organization_name_is_not_denylisted`
        # precedent -- a length guard tuned against real, live-observed
        # genuine content, not just a guess.
        real_description = (
            "The Clueless is a FIRST Tech Challenge (FTC) team founded in 2016 with 13 "
            "members from 8 middle and high schools across San Diego that has set the "
            "world record twice, qualified to the World Championship 6 times, and won "
            "the divisional Inspire Award three times. Beyond competing, the team runs "
            "community initiatives including Unity Robotics (which has founded 9 new "
            "FLL teams), a Global Mentorship Program (matching 40 teams), IGNITE "
            "(founding 8 FTC teams in South Africa), and an EV3 donation program "
            "(distributing 105+ EV3s to 2,000+ students)."
        )
        assert len(real_description) == 546  # sanity: the exact live-observed length
        assert not description_extract_module._is_rejected(_team(), real_description)

        team = _team()
        content = gather_description_content(_DESCRIPTION_HTML, team.website)
        llm_client = FixtureDescriptionLLMClient(
            responses={content: DescriptionExtractionResult(description=real_description)}
        )
        cache = DescriptionCache(cache_dir=tmp_path)

        extract_descriptions([team], {team.team_id: _DESCRIPTION_HTML}, llm_client, cache)

        assert team.description == real_description
        assert team.description_status == "generated"


class TestNoFetchResultsEntry:
    """AC: a team with no fetch_results entry (never website_status ==
    "confirmed") never reaches this flow -- description_status stays at
    its dataclass default, "none"."""

    def test_a_team_absent_from_fetch_results_is_never_touched(self, tmp_path):
        team = _team()

        class _BoomLLMClient:
            def summarize_description(self, content, context):
                raise AssertionError("summarize_description must not be called")

        extract_descriptions(
            [team], {}, _BoomLLMClient(), DescriptionCache(cache_dir=tmp_path)
        )

        assert team.description == ""
        assert team.description_status == "none"
        assert team.description_provenance == ""
        assert team.description_fetched_at == ""


class TestEmptyGatheredContentSkipsCacheAndLlm:
    """A confirmed page with no description-shaped content at all --
    skipped before any cache lookup or LLM call, matching
    sponsor_extract.py's own candidate-list cost-control gate.
    description_status is explicitly set to "unavailable" (a confirmed
    fetch existed, but gathering found nothing usable), distinct from
    "none" (no confirmed fetch at all)."""

    def test_no_description_shaped_page_makes_no_cache_or_llm_call(self, tmp_path):
        team = _team()
        assert gather_description_content(_NO_CONTENT_HTML, team.website) == ""

        class _BoomLLMClient:
            def summarize_description(self, content, context):
                raise AssertionError("summarize_description must not be called")

        class _BoomCache:
            def lookup(self, team_id, content):
                raise AssertionError("cache.lookup must not be called")

            def store(self, team_id, content, result):
                raise AssertionError("cache.store must not be called")

        extract_descriptions(
            [team], {team.team_id: _NO_CONTENT_HTML}, _BoomLLMClient(), _BoomCache()
        )

        assert team.description == ""
        assert team.description_status == "unavailable"


class TestFailOpen:
    """AC: a cache/LLM failure is caught per team, logged, and leaves
    that team's description fields unpopulated -- never aborts
    extraction for any other team."""

    def test_a_failing_team_is_skipped_but_a_second_team_still_succeeds(self, tmp_path, caplog):
        @dataclass
        class _RaisesForOneTeam:
            fails_for_team_id: str
            result: DescriptionExtractionResult

            def summarize_description(self, content, context):
                if context.get("team_id") == self.fails_for_team_id:
                    raise RuntimeError("simulated summarization failure")
                return self.result

        failing_team = _team(team_id="ftc-1", number=1)
        working_team = _team(team_id="ftc-2", number=2, name="Other Team")

        llm_client = _RaisesForOneTeam(
            fails_for_team_id="ftc-1",
            result=DescriptionExtractionResult(description="A working robotics team."),
        )
        cache = DescriptionCache(cache_dir=tmp_path)

        with caplog.at_level(logging.ERROR):
            extract_descriptions(
                [failing_team, working_team],
                {
                    failing_team.team_id: _DESCRIPTION_HTML,
                    working_team.team_id: _DESCRIPTION_HTML,
                },
                llm_client,
                cache,
            )

        # The failing team's description fields are left unpopulated --
        # never a partially-applied result.
        assert failing_team.description == ""
        assert failing_team.description_status == "unavailable"
        assert failing_team.description_provenance == ""
        assert failing_team.description_fetched_at == ""
        assert failing_team.team_id in caplog.text

        # The second, unrelated team was processed normally.
        assert working_team.description == "A working robotics team."
        assert working_team.description_status == "generated"
        assert working_team.description_provenance == "team_website"


class TestCacheHitSkipsTheLlmCall:
    """AC: a cache hit (same team, same content hash) makes zero LLM
    calls."""

    def test_identical_team_and_content_across_two_calls_makes_one_llm_call(self, tmp_path):
        team_website = "https://www.teamspyder.org/"
        content = gather_description_content(_DESCRIPTION_HTML, team_website)
        llm_client = FixtureDescriptionLLMClient(
            responses={content: DescriptionExtractionResult(description="A robotics team.")}
        )
        cache = DescriptionCache(cache_dir=tmp_path)

        team_a = _team()
        extract_descriptions([team_a], {team_a.team_id: _DESCRIPTION_HTML}, llm_client, cache)

        # A second, distinct Team object -- same team_id, same fetched
        # page -- against the same (persisted) cache: this is the
        # second extract_descriptions() call the AC describes, not a
        # second team.
        team_b = _team()
        extract_descriptions([team_b], {team_b.team_id: _DESCRIPTION_HTML}, llm_client, cache)

        assert len(llm_client.calls) == 1
        assert team_b.description == "A robotics team."
        assert team_b.description_status == "generated"


class TestSummarizeContext:
    """The context dict passed to summarize_description() carries at
    least the team_id, for logging/fixture-lookup use (description_llm.py's
    own DescriptionLLMClient protocol docstring)."""

    def test_context_carries_team_id(self, tmp_path):
        team = _team()
        content = gather_description_content(_DESCRIPTION_HTML, team.website)
        llm_client = FixtureDescriptionLLMClient(
            responses={content: DescriptionExtractionResult(description="")}
        )
        cache = DescriptionCache(cache_dir=tmp_path)

        extract_descriptions([team], {team.team_id: _DESCRIPTION_HTML}, llm_client, cache)

        assert len(llm_client.calls) == 1
        _, context = llm_client.calls[0]
        assert context["team_id"] == "ftc-1622"


class TestNoForbiddenImports:
    def test_module_imports_nothing_from_enrich_adapters_pipeline_run_or_sponsor_extract(self):
        # AST-level check, matching sponsor_extract.py's own
        # test_sponsor_extract.py forbidden-import-scan precedent -- a
        # source-level guarantee, not just "the module as currently
        # written happens not to import it." Also forbids importing
        # sponsor_extract.py itself: description extraction mirrors
        # sponsor extraction's shape but never modifies or imports it
        # (module docstring; sprint.md's Scope).
        path = Path(description_extract_module.__file__)
        tree = ast.parse(path.read_text(), filename=str(path))
        forbidden_prefixes = (
            "partner_scrape.enrich",
            "partner_scrape.adapters",
            "partner_scrape.pipeline",
            "partner_scrape.teams.sponsor_extract",
        )
        offenders: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(forbidden_prefixes):
                        offenders.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith(forbidden_prefixes):
                    offenders.append(node.module)
        assert offenders == []
