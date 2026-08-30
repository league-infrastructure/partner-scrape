"""Tests for partner_scrape.teams.sponsor_extract: sprint 013 ticket
005's orchestration -- gather candidates -> cache lookup -> classify on
a miss -> verbatim-candidate validation -> denylist guard -> normalize/
dedup/merge into ``Team.sponsors``/``Team.sponsor_provenance``.

Every test drives ``extract_sponsors()`` through a fixture
``SponsorLLMClient`` (``FixtureSponsorLLMClient`` or a small raising
double) and a real ``SponsorCache`` rooted at ``tmp_path`` -- no test
here opens a real network socket or calls the real ``anthropic`` SDK.

The **required** test in this file, matching this ticket's own
acceptance criteria, is ``TestHallucinationGuard``: a fixture LLM client
configured to return a name absent from the candidate list must have
that name dropped and logged, never published. This is the structural
anti-hallucination guarantee `sponsor_extract.py`'s own module docstring
describes -- everything else in this file is defense-in-depth or
sequencing/failure-isolation coverage around it.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from pathlib import Path

import partner_scrape.teams.sponsor_extract as sponsor_extract_module
from partner_scrape.teams.model import Team
from partner_scrape.teams.sponsor_candidates import gather_sponsor_candidates
from partner_scrape.teams.sponsor_cache import SponsorCache
from partner_scrape.teams.sponsor_extract import extract_sponsors
from partner_scrape.teams.sponsor_llm import FixtureSponsorLLMClient, SponsorExtractionResult

#: A real-shaped (hand-authored, matching TestDenylist's precedent in
#: tests/teams/test_sponsor_candidates.py) sponsor-heading page: two
#: genuine outbound sponsor links plus the team's own school name as an
#: <img alt> -- gather_sponsor_candidates() has no way to know that name
#: is the team's own (it never receives `organization`), so it survives
#: into the candidate list exactly as ticket 005's own denylist guard
#: (step 5, defense-in-depth) is designed to catch.
_SPONSORS_HTML = """
<html><body>
<h2>Sponsors</h2>
<div>
  <a href="https://acme-robotics.example.com">Acme Robotics</a>
  <a href="https://nordyne.example.com">Nordyne Corp</a>
  <img alt="Poway High School">
</div>
</body></html>
"""


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


class TestEndToEndFixture:
    """AC: "a candidate list mixing real sponsor names with an obvious
    non-sponsor (the team's own school name) -- only the real sponsors
    reach Team.sponsors." The fixture LLM client below deliberately
    selects all three (simulating an imperfect classification -- every
    name is verbatim in the candidate list, so this is not the
    hallucination case tested separately below) to prove
    extract_sponsors()'s own denylist guard, not just the LLM prompt, is
    what keeps the team's own name out."""

    def test_only_real_sponsors_reach_team_sponsors(self, tmp_path):
        team = _team()
        candidates = gather_sponsor_candidates(_SPONSORS_HTML, team.website)
        assert "Poway High School" in candidates  # sanity: really is a candidate here
        assert "Acme Robotics" in candidates
        assert "Nordyne Corp" in candidates

        llm_client = FixtureSponsorLLMClient(
            responses={
                tuple(candidates): SponsorExtractionResult(
                    confirmed_sponsors=["Acme Robotics", "Nordyne Corp", "Poway High School"]
                ),
            }
        )
        cache = SponsorCache(cache_dir=tmp_path)

        extract_sponsors([team], {team.team_id: _SPONSORS_HTML}, llm_client, cache)

        assert team.sponsors == ["Acme Robotics", "Nordyne Corp"]
        assert team.sponsor_provenance == {
            "Acme Robotics": "scraped",
            "Nordyne Corp": "scraped",
        }


class TestHallucinationGuard:
    """The required test (this ticket's own acceptance criteria): a
    fixture LLM client that returns a name absent from the candidate
    list has that name dropped and logged, never published -- the
    structural anti-hallucination guarantee, enforced in code."""

    def test_a_name_not_in_the_candidate_list_is_dropped_and_logged(self, tmp_path, caplog):
        team = _team()
        candidates = gather_sponsor_candidates(_SPONSORS_HTML, team.website)
        llm_client = FixtureSponsorLLMClient(
            responses={
                tuple(candidates): SponsorExtractionResult(
                    confirmed_sponsors=["Acme Robotics", "Definitely Not A Real Candidate Inc."]
                ),
            }
        )
        cache = SponsorCache(cache_dir=tmp_path)

        with caplog.at_level(logging.WARNING):
            extract_sponsors([team], {team.team_id: _SPONSORS_HTML}, llm_client, cache)

        assert team.sponsors == ["Acme Robotics"]
        assert "Definitely Not A Real Candidate Inc." not in team.sponsors
        assert "Definitely Not A Real Candidate Inc." not in team.sponsor_provenance
        assert "Definitely Not A Real Candidate Inc." in caplog.text

    def test_an_oversized_caption_selected_by_the_llm_is_still_dropped(self, tmp_path):
        # End-to-end version of TestDenylistDefenseInDepth's unit test,
        # reproducing the exact live-observed failure mode this ticket's
        # required pre-close review caught (module docstring's
        # _MAX_SPONSOR_NAME_LENGTH note): an oversized, caption-like
        # candidate that genuinely came from the page (so it is *not*
        # rejected by the verbatim/hallucination guard above) and that
        # the classification call selected anyway must still never
        # publish.
        caption = (
            "A huge thank you to @generalatomics for hosting Team 5137 Iron "
            "Kodiaks on Wednesday! We had an amazing time touring your "
            "facility, learning from your team, and seeing engineering in "
            "action. #ironkodiaks #team5137 #generalatomics"
        )
        html = f'<html><body><h2>Sponsors</h2><div><img alt="{caption}"></div></body></html>'
        team = _team()
        candidates = gather_sponsor_candidates(html, team.website)
        assert caption in candidates  # genuinely a candidate, not a hallucination

        llm_client = FixtureSponsorLLMClient(
            responses={tuple(candidates): SponsorExtractionResult(confirmed_sponsors=[caption])}
        )
        cache = SponsorCache(cache_dir=tmp_path)

        extract_sponsors([team], {team.team_id: html}, llm_client, cache)

        assert team.sponsors == []
        assert team.sponsor_provenance == {}


class TestStructuredScrapedDedup:
    """AC: "Qualcomm" (structured) and a scraped "Qualcomm Inc." for the
    same team collapse to one entry via the shared match key, keeping
    the structured display name and "structured" provenance.

    ``_merge_sponsors`` matches via ``teams.sponsor_canonical.
    canonical_key`` -- ``normalize_org_name`` (reused verbatim, module
    docstring's "never a second normalizer") plus a corporate-suffix
    strip ``sponsor_canonical.py`` layers on top of it. This ticket's
    original pass reused ``normalize_org_name`` directly, which does
    **not** strip corporate suffixes ("Inc.", "Incorporated", "LLC",
    ...): ``normalize_org_name("Qualcomm Inc.") == "qualcomm inc"``, not
    ``"qualcomm"``, so sprint.md's own motivating dedup example did not
    actually collapse (see ``TestPreviouslyKnownLimitationNowResolved``
    below and ``sponsor_canonical.py``'s own module docstring for the
    full story of why and how this was fixed when the ticket was
    reopened)."""

    def test_a_case_and_punctuation_variant_is_absorbed_into_the_existing_structured_entry(
        self, tmp_path
    ):
        team = _team(sponsors=["Qualcomm"], sponsor_provenance={"Qualcomm": "structured"})
        html = '<html><body><h2>Sponsors</h2><div><img alt="QUALCOMM."></div></body></html>'
        candidates = gather_sponsor_candidates(html, team.website)
        assert candidates == ["QUALCOMM."]

        llm_client = FixtureSponsorLLMClient(
            responses={
                tuple(candidates): SponsorExtractionResult(confirmed_sponsors=["QUALCOMM."]),
            }
        )
        cache = SponsorCache(cache_dir=tmp_path)

        extract_sponsors([team], {team.team_id: html}, llm_client, cache)

        assert team.sponsors == ["Qualcomm"]
        assert team.sponsor_provenance == {"Qualcomm": "structured"}


class TestPreviouslyKnownLimitationNowResolved:
    """This ticket's *first* pass documented a real gap: sprint.md's own
    motivating dedup example ("Qualcomm" structured merging with a
    scraped "Qualcomm Inc.") did not actually collapse, because
    ``normalize_org_name`` -- reused verbatim, per this ticket's own
    "do not write a second normalizer" instruction -- does not strip
    corporate suffixes. That was correctly left unchecked rather than
    misreported, and the ticket was reopened over it: the consequence
    across the *whole* live corpus was worse than this one example
    suggested (130 "distinct" sponsor strings for ~110 real companies).

    The fix (``sponsor_canonical.canonical_key``, layered *on top of*
    ``normalize_org_name`` -- never a change to that shared function
    itself, per this ticket's own scope boundary) closes this exact gap:
    reproduced here as the resolved case, replacing the old
    ``TestKnownNormalizeOrgNameLimitation`` class that asserted the
    former (broken) behavior."""

    def test_qualcomm_inc_now_merges_with_qualcomm(self, tmp_path):
        team = _team(sponsors=["Qualcomm"], sponsor_provenance={"Qualcomm": "structured"})
        html = '<html><body><h2>Sponsors</h2><div><img alt="Qualcomm Inc."></div></body></html>'
        candidates = gather_sponsor_candidates(html, team.website)
        assert candidates == ["Qualcomm Inc."]

        llm_client = FixtureSponsorLLMClient(
            responses={
                tuple(candidates): SponsorExtractionResult(confirmed_sponsors=["Qualcomm Inc."]),
            }
        )
        cache = SponsorCache(cache_dir=tmp_path)

        extract_sponsors([team], {team.team_id: html}, llm_client, cache)

        # Now collapses to one entry, keeping the structured display
        # name and provenance -- the originally-motivating example from
        # sprint.md's own Design Rationale.
        assert team.sponsors == ["Qualcomm"]
        assert team.sponsor_provenance == {"Qualcomm": "structured"}


class TestCacheHitSkipsTheLlmCall:
    """AC: a cache hit (same team, same candidate content hash) makes
    zero LLM calls."""

    def test_identical_team_and_candidates_across_two_calls_makes_one_llm_call(self, tmp_path):
        candidates = gather_sponsor_candidates(_SPONSORS_HTML, "https://www.teamspyder.org/")
        llm_client = FixtureSponsorLLMClient(
            responses={
                tuple(candidates): SponsorExtractionResult(confirmed_sponsors=["Acme Robotics"]),
            }
        )
        cache = SponsorCache(cache_dir=tmp_path)

        team_a = _team()
        extract_sponsors([team_a], {team_a.team_id: _SPONSORS_HTML}, llm_client, cache)

        # A second, distinct Team object -- same team_id, same fetched
        # page -- against the same (persisted) cache: this is the
        # second extract_sponsors() call the AC describes, not a
        # second team.
        team_b = _team()
        extract_sponsors([team_b], {team_b.team_id: _SPONSORS_HTML}, llm_client, cache)

        assert len(llm_client.calls) == 1
        assert team_b.sponsors == ["Acme Robotics"]


class TestFailOpen:
    """AC: an LLM call failure is caught per-team, logged, and leaves
    that team's sponsors/sponsor_provenance unchanged from whatever
    structured sources set -- verified it never aborts extract_sponsors()
    or affects any other team."""

    def test_a_failing_team_is_skipped_but_a_second_team_still_succeeds(self, tmp_path, caplog):
        @dataclass
        class _RaisesForOneOrganization:
            fails_for_organization: str
            result: SponsorExtractionResult

            def classify_sponsors(self, candidates, context):
                if context.get("organization") == self.fails_for_organization:
                    raise RuntimeError("simulated classification failure")
                return self.result

        failing_team = _team(
            team_id="ftc-1",
            number=1,
            organization="Failing School",
            sponsors=["Existing Sponsor"],
            sponsor_provenance={"Existing Sponsor": "structured"},
        )
        working_team = _team(
            team_id="ftc-2",
            number=2,
            name="Other Team",
            organization="Working School",
            website="https://www.otherteam.org/",
        )
        llm_client = _RaisesForOneOrganization(
            fails_for_organization="Failing School",
            result=SponsorExtractionResult(confirmed_sponsors=["Acme Robotics"]),
        )
        cache = SponsorCache(cache_dir=tmp_path)

        with caplog.at_level(logging.ERROR):
            extract_sponsors(
                [failing_team, working_team],
                {
                    failing_team.team_id: _SPONSORS_HTML,
                    working_team.team_id: _SPONSORS_HTML,
                },
                llm_client,
                cache,
            )

        # The failing team's prior structured data is untouched.
        assert failing_team.sponsors == ["Existing Sponsor"]
        assert failing_team.sponsor_provenance == {"Existing Sponsor": "structured"}
        assert failing_team.team_id in caplog.text

        # The second, unrelated team was processed normally.
        assert working_team.sponsors == ["Acme Robotics"]
        assert working_team.sponsor_provenance == {"Acme Robotics": "scraped"}


class TestEmptyCandidatesSkipCacheAndLlm:
    """AC (SUC-004 Main Flow step 1): a page with no sponsor-shaped
    content is skipped before any cache lookup or LLM call."""

    def test_no_sponsor_shaped_page_makes_no_cache_or_llm_call(self, tmp_path):
        team = _team()
        html = "<html><body><p>Nothing sponsor-shaped here.</p></body></html>"
        assert gather_sponsor_candidates(html, team.website) == []

        class _BoomLLMClient:
            def classify_sponsors(self, candidates, context):
                raise AssertionError("classify_sponsors must not be called")

        class _BoomCache:
            def lookup(self, team_id, candidates):
                raise AssertionError("cache.lookup must not be called")

            def store(self, team_id, candidates, result):
                raise AssertionError("cache.store must not be called")

        extract_sponsors([team], {team.team_id: html}, _BoomLLMClient(), _BoomCache())

        assert team.sponsors == []
        assert team.sponsor_provenance == {}

    def test_a_team_absent_from_fetch_results_is_never_touched(self, tmp_path):
        team = _team()

        class _BoomLLMClient:
            def classify_sponsors(self, candidates, context):
                raise AssertionError("classify_sponsors must not be called")

        extract_sponsors([team], {}, _BoomLLMClient(), SponsorCache(cache_dir=tmp_path))

        assert team.sponsors == []


class TestClassificationContext:
    """AC (SUC-004 Main Flow step 2): context carries at least
    team.organization and the page's own hostname."""

    def test_context_carries_organization_and_hostname(self, tmp_path):
        team = _team()
        candidates = gather_sponsor_candidates(_SPONSORS_HTML, team.website)
        llm_client = FixtureSponsorLLMClient(
            responses={tuple(candidates): SponsorExtractionResult(confirmed_sponsors=[])}
        )
        cache = SponsorCache(cache_dir=tmp_path)

        extract_sponsors([team], {team.team_id: _SPONSORS_HTML}, llm_client, cache)

        assert len(llm_client.calls) == 1
        _, context = llm_client.calls[0]
        assert context["organization"] == "Poway High School"
        assert context["hostname"] == "teamspyder.org"


class TestDenylistDefenseInDepth:
    """Direct unit coverage of `_is_denylisted` -- the layer this
    ticket adds on top of ticket 003's own deterministic denylist and
    ticket 004's prompt-level exclusions (module docstring)."""

    def test_common_cms_hosting_vendor_names_are_denylisted(self):
        assert sponsor_extract_module._is_denylisted("Wix", "", "") is True
        assert sponsor_extract_module._is_denylisted("wix", "", "") is True
        assert sponsor_extract_module._is_denylisted("Squarespace", "", "") is True

    def test_the_pages_own_hostname_is_denylisted(self):
        assert sponsor_extract_module._is_denylisted("teamspyder.org", "", "teamspyder.org") is True
        assert sponsor_extract_module._is_denylisted("www.teamspyder.org", "", "teamspyder.org") is True

    def test_an_organization_name_variant_is_denylisted_via_normalize_org_name(self):
        assert (
            sponsor_extract_module._is_denylisted("The Poway High School", "Poway High School", "") is True
        )

    def test_an_oversized_caption_like_candidate_is_denylisted(self):
        # Discovered live (this ticket's required pre-close --dry-run
        # review, sprint 011 ticket-011-003's lesson applied): a real
        # team page carried a full Instagram caption as an <img alt>
        # (a social-post embed), which gather_sponsor_candidates() has
        # no length gate for and the classification call selected
        # anyway -- see _MAX_SPONSOR_NAME_LENGTH's own docstring.
        caption = (
            "A huge thank you to @generalatomics for hosting Team 5137 Iron "
            "Kodiaks on Wednesday! We had an amazing time touring your "
            "facility, learning from your team, and seeing engineering in "
            "action. #ironkodiaks #team5137 #generalatomics"
        )
        assert len(caption) > sponsor_extract_module._MAX_SPONSOR_NAME_LENGTH
        assert sponsor_extract_module._is_denylisted(caption, "", "") is True

    def test_a_long_but_genuine_organization_name_is_not_denylisted(self):
        # The longest genuine name observed in this project's own live
        # sponsor data is well under the cap -- confirms the length
        # guard does not also reject legitimate long foundation/org
        # names.
        name = "General Atomics Sciences Education Foundation"
        assert len(name) <= sponsor_extract_module._MAX_SPONSOR_NAME_LENGTH
        assert sponsor_extract_module._is_denylisted(name, "", "") is False

    def test_a_short_truncated_caption_fragment_is_denylisted_via_at_marker(self):
        # Discovered on the *second* live --dry-run review, after the
        # length cap above was added: the same real embedded social
        # post also contributed an independently-truncated fragment,
        # short enough to slip under _MAX_SPONSOR_NAME_LENGTH on its
        # own -- the length cap alone was not sufficient.
        fragment = "A huge thank you to @generalatomics for hosting Te"
        assert len(fragment) <= sponsor_extract_module._MAX_SPONSOR_NAME_LENGTH
        assert sponsor_extract_module._is_denylisted(fragment, "", "") is True

    def test_a_hashtag_marker_alone_is_denylisted(self):
        assert sponsor_extract_module._is_denylisted("#teamspyder2026", "", "") is True

    def test_a_genuine_sponsor_is_not_denylisted(self):
        assert (
            sponsor_extract_module._is_denylisted("Acme Robotics", "Poway High School", "teamspyder.org")
            is False
        )


class TestNoForbiddenImports:
    def test_module_imports_nothing_from_enrich_adapters_or_pipeline_run(self):
        # AST-level check, matching tests/teams/test_sources_base.py's
        # and this ticket's sibling modules' (test_sponsor_llm.py,
        # test_sponsor_cache.py, test_sponsor_candidates.py) own
        # forbidden-import-scan precedent -- a source-level guarantee,
        # not just "the module as currently written happens not to
        # import it."
        path = Path(sponsor_extract_module.__file__)
        tree = ast.parse(path.read_text(), filename=str(path))
        forbidden_prefixes = (
            "partner_scrape.enrich",
            "partner_scrape.adapters",
            "partner_scrape.pipeline",
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
