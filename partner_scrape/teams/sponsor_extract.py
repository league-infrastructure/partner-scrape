"""Sponsor extraction orchestration (``teams.sponsor_extract``).

Sprint 013 ticket 005: the piece that actually runs sponsor extraction --
everything tickets 001 (fetched page bodies), 003
(``sponsor_candidates.gather_sponsor_candidates``), and 004
(``sponsor_llm.SponsorLLMClient``/``sponsor_cache.SponsorCache``) built
gets wired together here into one per-team pipeline stage:

    gather candidates -> cache lookup -> classify on a miss ->
    verbatim-candidate validation -> denylist guard (defense-in-depth) ->
    normalize/dedup/merge into ``Team.sponsors`` -> ``Team.sponsor_provenance``
    updated.

:func:`extract_sponsors` mutates ``teams`` in place, parallel in shape to
``teams.merge.merge_teams()``/``teams.geo.geocode_teams()``, and is called
once by ``teams.pipeline.run_teams()`` after ``verify_team_websites()``
(ticket 001) and before ``export_teams()``.

**This module is the actual security boundary's enforcement point.**
``sponsor_candidates.py`` never invents a name (it only lifts strings
present on the page); ``sponsor_llm.py``'s prompt asks the model to
*select*, never *generate*. Neither of those is a code-level guarantee on
its own -- a misbehaving or adversarially-prompted model could still
return a name absent from the candidate list. :func:`extract_sponsors`
is where that is actually checked and enforced: any name returned by
``classify_sponsors()`` that is not present verbatim in the candidate
list :func:`~partner_scrape.teams.sponsor_candidates.gather_sponsor_candidates`
produced is dropped and logged, never published (sprint.md's Design
Rationale, "the deterministic candidate-gathering pass is the actual
security boundary, the LLM only narrows within it" -- this is the layer
that turns that narrowing into a hard code-level guarantee). A small
denylist (common CMS/hosting vendor names, the team's own
``organization``, the page's own hostname) is layered on top as
defense-in-depth, catching anything a permissive classification might
still let through even after the verbatim check.

Sponsor-name deduplication reuses
``normalize.partners.normalize_org_name`` (never a second normalizer,
per sprint.md's Design Rationale) as the match key: a scraped name whose
normalized key already appears among a team's existing (structured)
sponsors is absorbed into that entry rather than duplicated -- the
structured display name and ``"structured"`` provenance always win over
a same-company scraped variant.

Every per-team failure -- a network error, a malformed LLM response
(``SponsorClassificationError``), a missing ``ANTHROPIC_API_KEY`` -- is
caught here and logged, leaving that team's ``sponsors``/
``sponsor_provenance`` exactly as the structured sources already set
them. This matches ``enrich/``'s project-wide "fail open, always"
convention (SUC-004's Error Flows): one team's classification failure
never aborts the run, and never touches any other team.

Deliberately mirrors, but never imports, ``enrich/``'s orchestration
shape. ``teams/`` has a standing, explicitly documented invariant of
zero edges into ``enrich/``, ``adapters/``, ``normalize.run()``, or
``pipeline.run()`` -- this module imports only
``normalize.partners.normalize_org_name`` (reused read-only, the one
sanctioned exception, matching ``teams.merge``'s own precedent) plus
sibling ``teams/`` modules.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from partner_scrape.normalize.partners import normalize_org_name
from partner_scrape.teams.model import Team
from partner_scrape.teams.sponsor_cache import SponsorCache
from partner_scrape.teams.sponsor_candidates import gather_sponsor_candidates
from partner_scrape.teams.sponsor_llm import SponsorLLMClient

logger = logging.getLogger(__name__)

#: Common CMS/website-hosting/site-builder vendor names -- defense-in-depth
#: on top of ``sponsor_candidates.py``'s own deterministic denylist (which
#: already filters most of these before the LLM ever sees them) and
#: ``sponsor_llm.py``'s prompt-level exclusion list (which only asks the
#: model not to select them). Checked case-insensitively against the
#: LLM's *selected* output, catching anything that survives both earlier
#: layers. Deliberately a small, local, duplicated list rather than an
#: import from ``sponsor_candidates.py``/``sponsor_llm.py`` -- each layer
#: changes for its own reason (module docstring; sprint.md's Design
#: Rationale on why ``teams/``'s new modules duplicate rather than share
#: infrastructure).
_CMS_HOSTING_DENYLIST = frozenset(
    {
        "wix",
        "squarespace",
        "wordpress",
        "godaddy",
        "weebly",
        "google sites",
        "canva",
        "blogspot",
        "hostinger",
    }
)

#: Maximum accepted length for a confirmed sponsor name -- discovered
#: necessary during this ticket's own required pre-close live-run
#: review (sprint 011 ticket-011-003's lesson, applied): a real team
#: page's embedded social post carried its full caption text as an
#: `<img alt>`/link-text attribute (e.g. "A huge thank you to
#: @generalatomics for hosting Team 5137 Iron Kodiaks on Wednesday! ...
#: #ironkodiaks #team5137 ..."), which survived gather_sponsor_candidates()
#: (no length gate there -- only a candidate-*count* cap) and was then
#: selected by the classification call. No real company name is
#: anywhere close to this length; this is defense-in-depth against a
#: whole caption/sentence being published as if it were a name, not a
#: plausible false rejection of a genuine (if long) organization name --
#: the longest genuine name observed in this project's own live sponsor
#: data is under 50 characters.
#:
#: **Not sufficient alone**: the same live review found the identical
#: embedded post also contributed a second, independently-truncated
#: candidate (a platform-side alt-text truncation, well under this
#: length cap on its own: "A huge thank you to @generalatomics for
#: hosting Te"). See :func:`_looks_like_social_caption` below for the
#: companion check that catches this shorter fragment too.
_MAX_SPONSOR_NAME_LENGTH = 80

#: An "@" mention or "#" hashtag anywhere in a candidate is a strong,
#: low-false-positive signal that it is social-media caption text, not
#: a company name -- no genuine sponsor name observed anywhere in this
#: project's data (structured or scraped) contains either character.
#: Catches a caption fragment too short for _MAX_SPONSOR_NAME_LENGTH
#: alone to reject (see that constant's own docstring).
_SOCIAL_CAPTION_MARKERS = ("@", "#")


def _looks_like_social_caption(name: str) -> bool:
    return any(marker in name for marker in _SOCIAL_CAPTION_MARKERS)


def _hostname(url: str) -> str:
    """``url``'s hostname, lowercased and with a leading ``www.``
    stripped -- matching ``sponsor_candidates.py``'s own ``_own_host``
    convention exactly (duplicated, not imported: that helper is
    private to its own module)."""
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _is_denylisted(name: str, organization: str, own_host: str) -> bool:
    """Whether ``name`` (an LLM-confirmed, already verbatim-validated
    candidate) should still be dropped as defense-in-depth: a common
    CMS/hosting vendor name, the page's own hostname (a team that lists
    its own domain as if it were a sponsor), the team's own
    ``organization`` (compared via :func:`normalize_org_name`, so "Poway
    High School" and "Poway High" match), a candidate longer than
    :data:`_MAX_SPONSOR_NAME_LENGTH`, or one containing an "@"/"#"
    social-caption marker (:func:`_looks_like_social_caption`) -- a
    whole social-post caption or fragment of one, not a name -- see
    those constants' own docstrings -- SUC-004's Main Flow, and this
    module's own docstring.
    """
    cleaned = name.strip().casefold()
    if not cleaned:
        return True
    if len(name.strip()) > _MAX_SPONSOR_NAME_LENGTH:
        return True
    if _looks_like_social_caption(name):
        return True
    if cleaned in _CMS_HOSTING_DENYLIST:
        return True
    if own_host and cleaned in (own_host, f"www.{own_host}"):
        return True
    if organization and normalize_org_name(name) == normalize_org_name(organization):
        return True
    return False


def _classify_and_guard(
    team: Team,
    candidates: list[str],
    llm_client: SponsorLLMClient,
    cache: SponsorCache,
) -> list[str]:
    """Steps 2-5 of SUC-004's Main Flow for one team: cache lookup,
    classify on a miss (caching the raw result), then verbatim-candidate
    validation followed by the denylist guard on whatever the model
    returned -- applied identically whether ``result`` came from the
    cache or a fresh call, since the safety property must hold
    regardless of path.

    Returns the surviving, already-guarded sponsor names -- never a name
    absent from ``candidates``, never a denylisted one.
    """
    result = cache.lookup(team.team_id, candidates)
    if result is None:
        context = {"organization": team.organization, "hostname": _hostname(team.website)}
        result = llm_client.classify_sponsors(candidates, context)
        cache.store(team.team_id, candidates, result)

    candidate_set = set(candidates)
    own_host = _hostname(team.website)
    confirmed: list[str] = []
    for name in result.confirmed_sponsors:
        if name not in candidate_set:
            # The structural anti-hallucination guarantee: never trust a
            # name the model returned that was not verbatim in the
            # candidate list this call was given. See module docstring.
            logger.warning(
                "Sponsor classification for team %s (%s) returned %r, "
                "which is not present verbatim in the candidate list; "
                "dropping it, never publishing",
                team.team_id,
                team.name,
                name,
            )
            continue
        if _is_denylisted(name, team.organization, own_host):
            logger.info(
                "Sponsor candidate %r for team %s (%s) matched the "
                "defense-in-depth denylist; dropping",
                name,
                team.team_id,
                team.name,
            )
            continue
        confirmed.append(name)
    return confirmed


def _merge_sponsors(team: Team, confirmed: list[str]) -> bool:
    """Step 6 of SUC-004's Main Flow: dedup ``confirmed`` against
    ``team.sponsors``' existing entries via :func:`normalize_org_name`.
    A normalized key already present (structured or previously scraped)
    keeps its existing display name and provenance; a genuinely new key
    is appended to ``sponsors`` with ``"scraped"`` provenance.

    Mutates ``team`` in place. Returns whether ``team`` gained at least
    one new sponsor.
    """
    existing_keys = {normalize_org_name(name) for name in team.sponsors}
    gained = False
    for name in confirmed:
        key = normalize_org_name(name)
        if not key or key in existing_keys:
            continue
        team.sponsors.append(name)
        team.sponsor_provenance[name] = "scraped"
        existing_keys.add(key)
        gained = True
    return gained


def extract_sponsors(
    teams: list[Team],
    fetch_results: dict[str, str],
    llm_client: SponsorLLMClient,
    cache: SponsorCache,
) -> None:
    """Run sponsor extraction once per team with an entry in
    ``fetch_results`` (``teams.scrape.verify_team_websites()``'s output,
    ticket 001), mutating ``teams`` in place.

    For each such team: gather candidates (skipping straight to the next
    team, with no cache lookup and no LLM call, when the candidate list
    is empty); look up/classify/validate/guard (see
    :func:`_classify_and_guard`); dedup/merge the survivors into
    ``Team.sponsors``/``Team.sponsor_provenance`` (see
    :func:`_merge_sponsors`).

    Every per-team failure from the cache-lookup-through-merge steps
    (network error, malformed LLM response, missing
    ``ANTHROPIC_API_KEY``) is caught, logged, and leaves that team's
    ``sponsors``/``sponsor_provenance`` exactly as the structured
    sources already set them -- fail-open, matching ``enrich/``'s
    project-wide convention (SUC-004's Error Flows). Never aborts the
    run for any other team.

    Args:
        teams: every merged/geocoded/overlay-applied ``Team`` this run
            produced (order irrelevant). Mutated in place.
        fetch_results: ``{team_id: fetched_html_body}``, ticket 001's
            ``verify_team_websites()`` return value -- only teams with an
            entry here (``website_status == "confirmed"``) are
            considered.
        llm_client: the injectable ``SponsorLLMClient`` -- a real
            ``AnthropicSponsorLLMClient`` in production, a
            ``FixtureSponsorLLMClient`` in tests.
        cache: the ``SponsorCache`` keyed by
            ``(team_id, content_hash(candidates))`` -- a hit skips the
            LLM call entirely.
    """
    processed = 0
    gained_sponsor = 0
    failed = 0

    for team in teams:
        html = fetch_results.get(team.team_id)
        if html is None:
            continue

        candidates = gather_sponsor_candidates(html, team.website)
        if not candidates:
            continue

        processed += 1

        try:
            confirmed = _classify_and_guard(team, candidates, llm_client, cache)
        except Exception:
            # Fail-open (SUC-004's Error Flows): a network error, a
            # SponsorClassificationError, or a missing
            # ANTHROPIC_API_KEY for this one team must never abort the
            # run or touch any other team -- team.sponsors/
            # sponsor_provenance are left exactly as the structured
            # sources already set them.
            logger.exception(
                "Sponsor extraction failed for team %s (%s); leaving its "
                "existing sponsors/provenance unchanged",
                team.team_id,
                team.name,
            )
            failed += 1
            continue

        if _merge_sponsors(team, confirmed):
            gained_sponsor += 1

    logger.info(
        "Sponsor extraction: %d team(s) with sponsor-shaped page content "
        "processed, %d gained a new scraped sponsor, %d failed and were "
        "skipped",
        processed,
        gained_sponsor,
        failed,
    )
