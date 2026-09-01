"""Description extraction orchestration (``teams.description_extract``).

Sprint 021 ticket 004: the piece that actually runs description
extraction -- everything tickets 002
(``description_candidates.gather_description_content``) and 003
(``description_llm.DescriptionLLMClient``/
``description_cache.DescriptionCache``) built gets wired together here
into one per-team pipeline stage:

    gather content -> cache lookup -> summarize on a miss ->
    no-email/length validation -> publish (``Team.description``/
    ``description_status``/``description_provenance``/
    ``description_fetched_at``).

:func:`extract_descriptions` mutates ``teams`` in place, structurally
parallel to ``teams.sponsor_extract.extract_sponsors()`` -- mirrored in
shape, never imported (``teams/DESIGN.md``'s "teams/ has zero edges into
enrich/, adapters/, normalize.run(), or pipeline.run()" invariant,
restated for this sprint's new modules; the same restriction applies
between description extraction and sponsor extraction themselves --
sprint.md's Scope: "description extraction is a new, parallel subsystem
that mirrors sponsor extraction's shape, never modifies it"). Called
once by ``teams.pipeline.run_teams()`` after ``canonicalize_sponsors()``
and before ``export_teams()``.

**No-email guard, layer 3 of 3.** ``description_candidates.py`` strips
every email-address-shaped substring from the *gathered* content before
it ever reaches an LLM (layer 1); ``description_llm.py``'s system
prompt explicitly instructs the model never to include contact
information (layer 2). Neither of those is a code-level guarantee on
its own -- a misbehaving or adversarially-prompted model could still
echo something email-shaped back. :func:`extract_descriptions` is where
that is actually checked and enforced: the raw ``description`` text a
summarization call returns is matched against the same email pattern
``description_candidates.py`` uses (an independent, duplicated copy --
production code never imports test code, and each guard layer is kept
independently correct rather than sharing one import) before it can be
published. A match is dropped and logged exactly like an empty result --
``description`` stays empty, ``description_status = "unavailable"``,
never published (mirrors ``sponsor_extract.py``'s own ``_is_denylisted()``
role: a deterministic, code-level check that does not trust the LLM's
compliance with its own instructions alone).

**Length guard, defense-in-depth.** A response longer than
:data:`_MAX_DESCRIPTION_LENGTH` is rejected the same way -- logged,
``description_status = "unavailable"``, never published -- mirroring
``sponsor_extract._MAX_SPONSOR_NAME_LENGTH``'s own precedent (discovered
necessary during that ticket's required pre-close live-run review: a
runaway or instruction-ignoring response should never be published
wholesale just because it parsed as valid JSON).

**Three-state ``description_status`` vocabulary.** A team absent from
``fetch_results`` (no confirmed website at all) is never touched by this
function -- ``description_status`` stays at its dataclass default,
``"none"``. Every team *with* a ``fetch_results`` entry that this
function does examine ends at exactly one of the other two states:
``"generated"`` on success, or ``"unavailable"`` for every other
outcome -- empty gathered content, an empty LLM response (a legitimate,
expected result for a page with nothing substantive to summarize -- see
``description_llm.DescriptionExtractionResult``'s own docstring), a
no-email/length guard rejection, or a caught cache/LLM failure. This is
a deliberate design choice, not an oversight: ``"none"`` is reserved
exclusively for "this stage never attempted this team at all," so that
``description_status`` can honestly answer "did we find anything worth
showing" for every team whose website *was* reachable, distinct from
whether we ever looked (``teams/model.py``'s own field docstring; the
whole point of a separate ``description_status`` alongside
``website_status``, per sprint.md's Design Rationale, is that a
reachable site can still have nothing extractable).

**Fail-open per team.** Every per-team failure -- a network error, a
malformed LLM response (``DescriptionClassificationError``), a missing
``ANTHROPIC_API_KEY`` -- is caught here and logged, leaving that team's
four description fields unpopulated (``description_status`` set to
``"unavailable"``, the other three fields at their dataclass defaults)
and never aborting extraction for any other team. Matches
``enrich/``'s and ``sponsor_extract.py``'s project-wide "fail open,
always" convention (SUC-023's Error Flows): one team's summarization
failure never aborts the run, and never touches any other team.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Callable

from partner_scrape.teams.description_cache import DescriptionCache
from partner_scrape.teams.description_candidates import gather_description_content
from partner_scrape.teams.description_llm import (
    DescriptionExtractionResult,
    DescriptionLLMClient,
)
from partner_scrape.teams.model import Team

logger = logging.getLogger(__name__)

#: Matches an email address anywhere in an LLM's raw response text --
#: the no-email guard's layer 3 of 3 (module docstring). An independent
#: copy of ``description_candidates._EMAIL_RE``/``tests/teams/
#: test_export.py``'s own ``_EMAIL_PATTERN`` (same pattern, kept
#: duplicated rather than imported -- production code must never depend
#: on test code, and each guard layer is independently correct), so
#: every layer of the guard rejects the same shape of string.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

#: Maximum accepted length, in characters, of a published description --
#: defense-in-depth against a runaway or instruction-ignoring
#: summarization response (mirrors
#: ``sponsor_extract._MAX_SPONSOR_NAME_LENGTH``'s own precedent and
#: rationale). Tuned from this ticket's own required pre-close live-run
#: review (see the ticket's Notes): an initial guess of 500 wrongly
#: rejected a genuine, fully-accurate, fact-checked-against-the-real-
#: site 546-character summary for a team with an unusually large number
#: of distinct, real community programs to describe ("ftc-11212", The
#: Clueless) -- every fact in that summary was independently verified
#: against the team's own live website (no fabrication), so the defect
#: was this bound being calibrated too tightly, not the model
#: misbehaving. 800 gives that observed genuine case (and others like
#: it) comfortable headroom while remaining well under (60% of) the
#: input bound (``description_candidates.MAX_CONTENT_CHARS`` == 2000
#: characters), so it still meaningfully guards against the model
#: ignoring its "1-2 sentence" instruction altogether and echoing back
#: most or all of the gathered content verbatim.
_MAX_DESCRIPTION_LENGTH = 800


def _lookup_or_summarize(
    team: Team,
    content: str,
    llm_client: DescriptionLLMClient,
    cache: DescriptionCache,
) -> DescriptionExtractionResult:
    """Step 2 of SUC-023's Main Flow for one team: cache lookup,
    summarizing on a miss (caching the raw result). Applied identically
    whether ``result`` came from the cache or a fresh call, since the
    no-email/length guard below must hold regardless of path.
    """
    result = cache.lookup(team.team_id, content)
    if result is None:
        result = llm_client.summarize_description(content, {"team_id": team.team_id})
        cache.store(team.team_id, content, result)
    return result


def _is_rejected(team: Team, description: str) -> bool:
    """No-email guard layer 3 of 3, plus the length guard (module
    docstring) -- both applied, in code, to the LLM's raw returned
    text, never trusting its own prompt-level compliance alone. Logs
    and returns ``True`` for a description that must never be
    published; ``False`` for one safe to publish.
    """
    if _EMAIL_RE.search(description):
        # Deliberately does not log the raw description text here --
        # unlike the length case below, this branch means the text
        # itself may carry an email address; logging it verbatim would
        # partially defeat the guard's own purpose by placing contact
        # information into application logs.
        logger.warning(
            "Description for team %s (%s) contained an email-address-shaped "
            "substring in the LLM's raw response; rejecting, never "
            "publishing (no-email guard, layer 3 of 3)",
            team.team_id,
            team.name,
        )
        return True

    if len(description) > _MAX_DESCRIPTION_LENGTH:
        logger.warning(
            "Description for team %s (%s) exceeded the maximum length "
            "(%d > %d characters); rejecting, never publishing: %r",
            team.team_id,
            team.name,
            len(description),
            _MAX_DESCRIPTION_LENGTH,
            description,
        )
        return True

    return False


def extract_descriptions(
    teams: list[Team],
    fetch_results: dict[str, str],
    llm_client: DescriptionLLMClient,
    cache: DescriptionCache,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> None:
    """Run description extraction once per team with an entry in
    ``fetch_results`` (``teams.scrape.verify_team_websites()``'s output,
    the same dict ``teams.sponsor_extract.extract_sponsors()`` already
    consumes -- no second fetch), mutating ``teams`` in place.

    For each such team: gather content (skipping straight to the next
    team, with no cache lookup and no LLM call, and marking
    ``description_status = "unavailable"``, when the gathered content is
    empty -- the same cost-control gate
    ``sponsor_extract.py``'s own candidate-list check already provides
    for the sponsor pipeline); look up/summarize (see
    :func:`_lookup_or_summarize`); reject an empty LLM response (a
    legitimate, expected "nothing substantive to summarize" result, per
    ``DescriptionExtractionResult``'s own docstring) or one that fails
    the no-email/length guard (see :func:`_is_rejected`); otherwise
    publish ``description``/``description_status``/
    ``description_provenance``/``description_fetched_at``.

    Every per-team failure from the cache-lookup-through-summarize steps
    (network error, malformed LLM response, missing
    ``ANTHROPIC_API_KEY``) is caught, logged, and leaves that team's
    ``description_status`` set to ``"unavailable"`` (the other three
    description fields at their dataclass defaults) -- fail-open,
    matching ``enrich/``'s and ``sponsor_extract.py``'s project-wide
    convention (SUC-023's Error Flows). Never aborts the run for any
    other team.

    Args:
        teams: every merged/geocoded/overlay-applied/sponsor-extracted
            ``Team`` this run produced (order irrelevant). Mutated in
            place.
        fetch_results: ``{team_id: fetched_html_body}``,
            ``verify_team_websites()``'s return value -- only teams with
            an entry here (``website_status == "confirmed"``) are
            considered.
        llm_client: the injectable ``DescriptionLLMClient`` -- a real
            ``AnthropicDescriptionLLMClient`` in production, a
            ``FixtureDescriptionLLMClient`` in tests.
        cache: the ``DescriptionCache`` keyed by
            ``(team_id, content_hash(content))`` -- a hit skips the LLM
            call entirely.
        clock: returns the current UTC ``datetime`` used to stamp
            ``description_fetched_at`` on a successful summarization.
            Defaults to the real wall clock; tests inject a fixed
            ``datetime`` for determinism (matching
            ``EnrichmentCache``/``SponsorCache``'s own testable-clock
            convention).
    """
    processed = 0
    generated = 0
    unavailable = 0
    failed = 0

    for team in teams:
        html = fetch_results.get(team.team_id)
        if html is None:
            continue

        content = gather_description_content(html, team.website)
        if not content:
            team.description_status = "unavailable"
            unavailable += 1
            continue

        processed += 1

        try:
            result = _lookup_or_summarize(team, content, llm_client, cache)
        except Exception:
            # Fail-open (SUC-023's Error Flows): a network error, a
            # DescriptionClassificationError, or a missing
            # ANTHROPIC_API_KEY for this one team must never abort the
            # run or touch any other team.
            logger.exception(
                "Description extraction failed for team %s (%s); leaving "
                "its description unavailable",
                team.team_id,
                team.name,
            )
            team.description_status = "unavailable"
            failed += 1
            continue

        description = result.description.strip()

        if not description:
            # A legitimate, expected result (DescriptionExtractionResult's
            # own docstring: "an empty description is a valid, expected
            # result, not an error") -- never published as
            # description_status == "generated" with an empty string.
            team.description_status = "unavailable"
            unavailable += 1
            continue

        if _is_rejected(team, description):
            team.description_status = "unavailable"
            unavailable += 1
            continue

        team.description = description
        team.description_status = "generated"
        team.description_provenance = "team_website"
        team.description_fetched_at = clock().isoformat()
        generated += 1

    logger.info(
        "Description extraction: %d team(s) with description-shaped page "
        "content processed, %d generated, %d had nothing publishable, "
        "%d failed",
        processed,
        generated,
        unavailable,
        failed,
    )
