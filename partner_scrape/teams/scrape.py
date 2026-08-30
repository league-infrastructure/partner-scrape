"""Website liveness verification (``teams.scrape``).

Sprint 013 ticket 001: the first stage that actually looks at a team's
page. ``verify_team_websites()`` fetches every ``Team.website`` (by now
the corrected, enlarged set ticket 006's
``teams.website_overrides.apply_website_overrides()`` produces) through
the same ``fetcher`` parameter ``teams.pipeline.run_teams()`` already
threads through every other stage that touches the network -- a real
``fetch.PoliteFetcher`` in production, so robots.txt, per-domain
throttling, and conditional-GET caching all apply with zero new
plumbing (sprint.md's Design Rationale, "the website-fetch and
sponsor-classification stages reuse the single `fetcher`/new
`llm_client` parameters already ... threaded through `run_teams()`,
rather than constructing their own").

**Per-page robots-check-then-fetch, matching
``discovery/hub_scan.py::scan_hub()``'s already-proven pattern
exactly** -- ``fetch.is_allowed()`` is checked explicitly before every
``fetcher.get()`` call, rather than relying on ``PoliteFetcher.get()``'s
own internal robots check (which raises ``RobotsDisallowed`` instead of
letting a per-team loop continue cleanly to the next team). A disallowed
URL is logged and the team is marked ``"unverified"``, exactly like a
non-2xx response or a transport error -- robots.txt is a reason a page
could not be verified, not a distinct outcome a caller needs to
distinguish from any other unreachable page.

**Fetched HTML is returned, never assigned to a ``Team`` field.**
``teams/export.py``'s ``TEAMS_SCHEMA_FIELDS`` is derived from
``dataclasses.fields(Team)``, so anything added to that dataclass
auto-publishes to the public ``teams.json`` -- see sprint.md's Design
Rationale ("fetched HTML is threaded through `run_teams()` as a local,
non-model `dict[team_id, str]`, never stored on `Team`") and
``model.Team``'s own "no email field, ever" precedent for the same
category of guarantee applied to a different kind of contact-carrying
content. ``run_teams()`` holds this function's returned dict as a plain
local variable and will hand it to sprint 013 ticket 005's
``teams.sponsor_extract.extract_sponsors()``.
"""

from __future__ import annotations

import logging

from partner_scrape.fetch import DEFAULT_USER_AGENT, Fetcher, is_allowed
from partner_scrape.teams.model import Team

logger = logging.getLogger(__name__)


def _status_reason(status: int) -> str:
    """A short, human-readable reason string for a non-2xx ``status``,
    distinguishing ``UrllibFetcher``'s synthetic transport-error
    sentinel (``0`` -- DNS/TLS/timeout/reset, never a real HTTP status)
    from a genuine HTTP error code, for clearer warning logs.
    """
    if status == 0:
        return "transport error (no HTTP response received)"
    return f"HTTP {status}"


def verify_team_websites(
    teams: list[Team],
    fetcher: Fetcher,
    *,
    user_agent: str = DEFAULT_USER_AGENT,
) -> dict[str, str]:
    """Fetch and classify every team's declared website, in place.

    For each ``Team`` in ``teams``:

    - An empty ``website`` sets ``website_status = "none"`` -- never
      fetched at all.
    - A non-empty ``website`` disallowed by its site's robots.txt
      (``fetch.is_allowed()``, checked before any request) sets
      ``website_status = "unverified"`` and logs a warning naming the
      team and the reason; the URL is never requested.
    - An allowed URL is fetched via ``fetcher.get()``. A 2xx response
      sets ``website_status = "confirmed"`` and the fetched body is
      added to the returned dict, keyed by ``team_id``. Any other
      response -- a 3xx/4xx/5xx, or ``UrllibFetcher``'s synthetic
      transport-error sentinel status ``0`` -- sets
      ``website_status = "unverified"`` and logs a warning naming the
      team and the reason.

    Never raises: a fetch failure or robots disallow for one team is
    isolated to that team and never affects any other team's status or
    aborts the loop, matching ``discovery/hub_scan.py::scan_hub()``'s
    same per-page isolation contract. Both the robots check and the
    fetch call are additionally wrapped in their own ``except
    Exception`` (marking that one team ``"unverified"`` and logging,
    same as any other reason a page could not be verified) -- a real
    ``Fetcher`` (``UrllibFetcher``/``PoliteFetcher``) never raises here
    by contract (a transport failure comes back as
    ``FetchResponse(status=0)``, not an exception), so this is belt-
    and-suspenders defense-in-depth, matching the per-source
    ``try/except`` one level up in ``run_teams()``'s own source loop,
    rather than a behavior any real caller should rely on. Confirmed
    live, not just theoretical: a ``PoliteFetcher`` whose target site's
    robots.txt blanket-disallows everything (``Disallow: /``) raises
    ``RobotsDisallowed`` from *inside* ``is_allowed()``'s own
    ``fetcher.get(robots_txt_url(url))`` call -- ``PoliteFetcher.get()``
    re-checks robots.txt against itself before returning robots.txt's
    own content, and a blanket disallow also matches the ``/robots.txt``
    path -- and this ``except Exception`` is what keeps that team
    ``"unverified"`` rather than aborting the whole run. Logs one
    INFO-level summary line (aggregate confirmed/unverified/none counts
    and 2xx rate) after every team has been processed -- SUC-001's
    postcondition that "a live run's log reports the aggregate 2xx
    rate."

    Args:
        teams: every ``Team`` to verify (order irrelevant), already
            merged/geocoded/overlay-applied by the earlier pipeline
            stages. Mutated in place.
        fetcher: the same ``Fetcher`` ``run_teams()`` threads through
            every other network-touching stage -- a real
            ``PoliteFetcher`` in production (robots/throttle/cache
            apply for free), a fixture double in tests.
        user_agent: the user agent both the robots check and (via
            request headers, indirectly through ``fetcher``) the fetch
            itself are evaluated against. Defaults to
            ``fetch.DEFAULT_USER_AGENT``, matching every other caller
            of ``fetch.is_allowed()`` in this codebase
            (``discovery/hub_scan.py``) and ``PoliteFetcher``'s own
            default.

    Returns:
        ``{team_id: fetched_html_body}`` for ``confirmed`` teams only
        -- never for ``unverified``/``none`` teams, and never stored
        anywhere on a ``Team``.
    """
    fetched_bodies: dict[str, str] = {}
    confirmed = 0
    unverified = 0
    none_count = 0

    for team in teams:
        if not team.website:
            team.website_status = "none"
            none_count += 1
            continue

        try:
            allowed = is_allowed(team.website, fetcher, user_agent)
        except Exception as exc:
            # Belt-and-suspenders, matching run_teams()'s own per-source
            # try/except one level up: a real Fetcher (UrllibFetcher/
            # PoliteFetcher) never raises here by contract (transport
            # failures come back as FetchResponse(status=0)), but this
            # keeps one team's fetch-layer bug from aborting every
            # other team's verification -- the same per-unit isolation
            # SUC-001's Error Flows require for a "fetch failure",
            # applied defensively rather than trusting the contract
            # alone. Observed live, not just theoretical: a
            # PoliteFetcher whose site's robots.txt blanket-disallows
            # everything ("Disallow: /") raises RobotsDisallowed from
            # *inside* is_allowed()'s own fetcher.get(robots_txt_url)
            # call, because PoliteFetcher.get() re-checks robots.txt
            # against itself before returning robots.txt's own content.
            team.website_status = "unverified"
            unverified += 1
            logger.warning(
                "Team %s (%s) robots.txt check for %s raised %s; "
                "marking unverified",
                team.team_id,
                team.name,
                team.website,
                type(exc).__name__,
            )
            continue

        if not allowed:
            team.website_status = "unverified"
            unverified += 1
            logger.warning(
                "Team %s (%s) website %s disallowed by robots.txt; "
                "marking unverified",
                team.team_id,
                team.name,
                team.website,
            )
            continue

        try:
            response = fetcher.get(team.website)
        except Exception as exc:
            team.website_status = "unverified"
            unverified += 1
            logger.warning(
                "Team %s (%s) fetch of %s raised %s; marking unverified",
                team.team_id,
                team.name,
                team.website,
                type(exc).__name__,
            )
            continue

        if 200 <= response.status < 300:
            team.website_status = "confirmed"
            confirmed += 1
            fetched_bodies[team.team_id] = response.body
        else:
            team.website_status = "unverified"
            unverified += 1
            logger.warning(
                "Team %s (%s) website %s unreachable (%s); marking unverified",
                team.team_id,
                team.name,
                team.website,
                _status_reason(response.status),
            )

    checked = confirmed + unverified
    rate = (confirmed / checked * 100) if checked else 0.0
    logger.info(
        "Website verification: %d confirmed, %d unverified, %d none "
        "(%.0f%% of %d checked URLs returned 2xx)",
        confirmed,
        unverified,
        none_count,
        rate,
        checked,
    )

    return fetched_bodies
