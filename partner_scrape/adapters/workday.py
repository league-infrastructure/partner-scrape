"""Workday CXS (public job-search) API adapter.

See sprint 031's ticket 005 and SUC-058: Workday's public job-search
endpoint (``POST /wday/cxs/{tenant}/{site}/jobs``) has no GET-based
equivalent -- see ``fetch/DESIGN.md``'s sprint 031 section for the
``Fetcher.post()`` addition this required (ticket 004) and its own
Design Rationale. This is the first (and, as of this sprint, only)
adapter that calls ``Fetcher.post()``.

**Live verification result (2026-09-02, plain POST vs. browser-like
headers)**: issue 31's own census found a headerless plain request
403s. Live-confirmed here: adding ``Accept: application/json``,
``Referer`` (set to the tenant's own careers page), and a realistic
browser ``User-Agent`` (:data:`BROWSER_USER_AGENT`) clears the 403 for
every one of the six tenants probed -- no headless browser, no TLS/JA3
fingerprint workaround needed. A bare, headerless ``GET`` to the same
path returns ``400`` (Workday's CXS endpoint only accepts ``POST``);
this ticket did not need to separately reproduce the 403 issue 31's
census recorded, since the acceptance criterion is "does POST-with-
headers work," which it does, for all six.

Per-tenant live-verification results (2026-09-02, ``searchText=""``,
every page of every tenant's board fetched, run through
``ats_filters.classify_posting`` with only ``title``/``locationsText``
-- Workday's list-view API returns no ``department``/commitment field
at all, unlike Greenhouse/SmartRecruiters/Workable, so the STEM check
here relies on title text alone):

- **Northrop Grumman** (``ngc``/``wd1``/``Northrop_Grumman_External_Site``):
  3715 raw postings, 173 San Diego, 0 matches.
- **Cubic** (``cubic``/``wd1``/``cubic_USA_careers``): 55 raw postings,
  11 San Diego, 0 matches. (A second, broader ``cubic_global_careers``
  site also resolves live but was not registered -- it mixes in
  non-US/non-San-Diego postings this adapter's default
  ``location_keywords`` already filters out, so the narrower US site is
  the better default; a source could still override ``site`` to it.)
- **Illumina** (``illumina``/``wd1``/``illumina-careers``): 154 raw
  postings, 49 San Diego, 0 matches. A separate
  ``illumina-universityrecruiting`` site also resolves live (200, valid
  JSON) but currently has 0 total postings -- noted here, not
  registered, since issue 31 names only the one required Illumina
  registration and this sprint's own "don't build speculatively" norm
  applies to a second site with nothing live to show for it yet.
- **Dexcom** (``dexcom``/``wd1``/``Dexcom``): 295 raw postings, 53 San
  Diego, 0 matches -- including 3 intern-titled postings live at
  verification time (``2027 US Summer Internship - Early Interest``,
  San Diego; two Facilities-intern roles in Penang, Malaysia), none of
  which carry a STEM keyword in their *title* (the only field this
  adapter can classify against for Workday), which is why 0 survive
  ``classify_posting`` despite real internship activity existing on the
  board -- a concrete instance of this module's own department-field
  limitation above, not a bug.
- **ResMed** (``resmed``/``wd3``/``ResMed_External_Careers``, issue 31's
  "likely"): confirmed live, 219 raw postings, 27 San Diego, 0 matches.
  Registered per this ticket's own acceptance criteria (confirmed
  tenant/site pair).
- **Sempra/SDG&E** (issue 31's other "likely"): *not* confirmed --
  no public Workday tenant found under any of ``sempra``/``sdge``/
  ``sempraenergy``/``sdgande`` across the three most common shard hosts
  (``wd1``/``wd3``/``wd5``); every guess returned Workday's own
  tenant-not-found response. Not registered, per this ticket's own
  "otherwise noted as unconfirmed ... not registered" instruction.

Every tenant's ``robots.txt`` was live-checked (via
``urllib.robotparser``, this project's own bot user agent) against the
exact ``/wday/cxs/{tenant}/{site}/jobs`` path each registration POSTs
to -- every one of the five allows it (none carries a blanket
``Disallow: /`` the way ``api.smartrecruiters.com`` does; each only
disallows a narrow ``/refreshFacet/`` (and, for ResMed, ``/myjobs/``)
path unrelated to this endpoint). All five are registered
``enabled = true``.

**Northrop Grumman's "HS Internship Program" req**: live search (both
broad ``searchText`` queries and a full 3715-posting scan of every page
currently on the board) found no currently-live "High School"-titled
posting on the public ``Northrop_Grumman_External_Site`` this adapter
targets. The specific req this sprint's issue names (confirmed to
exist via web search, e.g. "2026 High School Internship Program
Technical Intern - San Diego CA") resolves to a *different* Workday
site, ``Northrop_Grumman_Restricted_Site`` -- live-probed here and
confirmed to return ``403 permission denied`` for this project's bot,
distinct from (and not fixed by) the browser-like headers that clear
the public site's 403. Per this ticket's own fallback ("carefully
hand-modeled, if a given tenant stays blocked even to this ticket's own
live verification"), ``tests/fixtures/workday/jobs_page1.json`` hand-
models a representative HS Internship Program-shaped record (title
containing an actual STEM keyword, since Workday's real "Technical
Intern" short title does not contain one from :data:`STEM_KEYWORDS
<partner_scrape.adapters.ats_filters.STEM_KEYWORDS>` and this ticket
does not modify ``ats_filters.py``) to prove the shape survives
classification, rather than asserting a live pipeline run currently
extracts this exact req.

Real response shape (confirmed live, e.g. Northrop Grumman)::

    {"total": 3715, "jobPostings": [{"title": "Manager Programs 2",
      "externalPath": "/job/United-States-Maryland-Baltimore/Manager-
        Programs-2_R10248675",
      "timeType": "Full time", "locationsText":
        "United States-Maryland-Baltimore",
      "postedOn": "Posted Today", "bulletFields": ["R10248675"]}, ...],
     "facets": [...], "userAuthenticated": false}

Field mapping: ``external_id`` <- ``bulletFields[0]`` (Workday's own
requisition number, e.g. ``"R10248675"``), falling back to ``""`` when
absent; ``title`` <- ``title``; ``location`` <- ``locationsText``
(**note**: a posting open at more than one office comes back as e.g.
``"2 Locations"`` with no city name at all -- such a posting can never
match ``is_local_posting``, a known, accepted limitation of this list-
view field, not something this adapter works around); ``registration_url``
<- the site's own careers base URL (``{api_base}/{site}``) with
``externalPath`` joined on. Every field this adapter sets is high-trust
(:data:`CONFIDENCE` 1.0), matching every other adapter in this family.

**Design Rationale: leave ``Event.start`` unset for every posting.**
Workday's list-view API's only date signal, ``postedOn``, is always a
relative string ("Posted Today", "Posted Yesterday", "Posted 30+ Days
Ago") -- there is no absolute timestamp field anywhere in the list
response. Parsing or guessing an absolute date from a relative string
would fabricate a date the source itself never asserts (see
``adapters/DESIGN.md``'s sprint 031 section for the full write-up,
including the alternatives considered and rejected). A Workday-sourced
internship instead gets ``normalize.run()``'s existing rolling-
availability treatment for an unset ``start``/``date_end``, identical
to a Greenhouse/Lever/SmartRecruiters/Workable posting with no
parseable date.

``ats_filters.classify_posting`` is called with only ``title`` and
``location`` -- Workday's list-view API has no ``department`` or
commitment-type field of any kind (unlike every other adapter in this
family), so there is nothing to pass for those parameters; the STEM
check here rests entirely on the posting's title text (see the
Dexcom live-verification note above for a concrete case where this
matters). Every raw posting is run through
``adapters.ats_filters.classify_posting`` *before* an ``Event`` is
constructed; only a match becomes an ``Event``, with
``kind="internship"`` and the verdict's default
``age_grade_level``/``time_of_day`` applied via ``Event.set(...)``.
Deliberately does not set ``Event.cost``/``Event.cost_range`` -- same
contract as ``greenhouse.py``/``lever.py``/``smartrecruiters.py``/
``workable.py`` (see ``ats_filters.py``'s module docstring). Workday's
list-view API also carries no description/content field, so
``Event.description`` is never set by this adapter (same as
``smartrecruiters.py``).
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any, Iterable

from partner_scrape.adapters.ats_filters import classify_posting
from partner_scrape.adapters.base import EventRef, RawResponse, acquisition_kwargs
from partner_scrape.fetch import Fetcher
from partner_scrape.model import Event
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: This adapter's provenance source name, recorded on every field it sets.
SOURCE_NAME = "workday"

#: Workday's public CXS API is a structured, first-party feed -- every
#: field this adapter sets is maximally trusted, matching every other
#: adapter in this family.
CONFIDENCE = 1.0

#: Realistic browser User-Agent -- live-confirmed (2026-09-02) that a
#: headerless plain POST 403s (issue 31's own census) but this header
#: set (this, plus ``Accept``/``Referer`` below) clears it for every one
#: of the six tenants probed during this ticket's live verification.
#: No headless browser or TLS/JA3 fingerprint workaround was needed.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

#: Postings per page. Workday's CXS ``jobs`` endpoint hard-caps this
#: server-side at 20 -- live-confirmed (2026-09-02): a probe with
#: ``limit=21`` (and every larger value tried) returns ``400``, while
#: ``limit=20`` returns ``200``. Unlike ``smartrecruiters.py``'s/
#: ``tec.py``'s page-size choices (each server-capped higher), this is
#: not a tunable convenience -- it is Workday's actual hard limit.
PAGE_SIZE = 20

#: Hard cap on pages enumerated for a single source, as a backstop
#: against a source that misreports ``total``. At PAGE_SIZE=20 this is
#: 20,000 postings -- well above the largest real tenant live-verified
#: this ticket (Northrop Grumman, 3715) -- so hitting it means the
#: source is misreporting, not that a real employer's board is this
#: large.
MAX_PAGES = 1000


def _jobs_url(source: SourceConfig) -> str:
    """Build this source's ``POST /wday/cxs/{tenant}/{site}/jobs`` URL.

    ``api_base`` (e.g. ``"https://ngc.wd1.myworkdayjobs.com"``) is
    required and has no codebase-wide default -- unlike Greenhouse's
    single global API host, Workday shards its API host per tenant
    (``wd1``, ``wd3``, ``wd5``, ...), confirmed per tenant during this
    ticket's own live verification (module docstring).
    """
    api_base = source.config["api_base"].rstrip("/")
    tenant = source.config["tenant"]
    site = source.config["site"]
    return f"{api_base}/wday/cxs/{tenant}/{site}/jobs"


def _careers_url(source: SourceConfig) -> str:
    """Build this source's own careers page URL -- the base
    ``externalPath`` is joined onto for ``registration_url``, and also
    used as this adapter's ``Referer`` header value (module docstring).
    """
    api_base = source.config["api_base"].rstrip("/")
    site = source.config["site"]
    return f"{api_base}/{site}"


def _request_headers(source: SourceConfig) -> dict[str, str]:
    """Browser-like headers this ticket live-confirmed clear Workday's
    403 on a plain POST (module docstring): a realistic ``User-Agent``,
    ``Accept: application/json``, and a ``Referer`` set to the tenant's
    own careers page. ``Content-Type: application/json`` is added
    automatically by ``UrllibFetcher.post()`` (ticket 004) and does not
    need to be repeated here.
    """
    return {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept": "application/json",
        "Referer": _careers_url(source),
    }


def _page_body(offset: int) -> dict[str, Any]:
    """This source's search body for one page at ``offset`` -- an empty
    ``searchText`` returns every posting (not a filtered subset):
    filtering is this adapter's own job via ``ats_filters.classify_posting``,
    not Workday's fuzzy full-text search (live-confirmed during this
    ticket's verification to rank on loose word overlap, not exact
    phrase/field matching -- unsuitable for this adapter's filtering
    needs even before considering that every other adapter in this
    family filters locally, not via the vendor's own search).
    """
    return {"appliedFacets": {}, "limit": PAGE_SIZE, "offset": offset, "searchText": ""}


def _external_id(raw_job: dict[str, Any]) -> str:
    """Workday's own requisition number, e.g. ``"R10248675"`` --
    ``bulletFields`` is a list whose first (and, in every live-observed
    response, only) element is this ID. Returns ``""`` if absent/empty,
    matching this family's other adapters' fallback convention.
    """
    bullet_fields = raw_job.get("bulletFields")
    if isinstance(bullet_fields, list) and bullet_fields:
        return str(bullet_fields[0] or "")
    return ""


def _extract_one(raw_job: dict[str, Any], source: SourceConfig, careers_base: str) -> Event | None:
    """Map one raw Workday ``jobPostings[]`` record into a canonical
    internship ``Event``.

    Returns ``None`` when the posting does not pass
    ``ats_filters.classify_posting`` -- not an error, simply not a
    match, so the caller must not treat it as a skipped/malformed
    record.

    Raises:
        ValueError: the record has no usable title.

    Caught by the caller (``extract()``) and treated as a per-record
    skip -- never fatal to the rest of the page, matching this family's
    per-record isolation convention. Unlike ``greenhouse.py``'s/
    ``smartrecruiters.py``'s ``_extract_one``, there is no date-parsing
    failure mode here: ``Event.start`` is deliberately never set (module
    docstring's Design Rationale).
    """
    title = (raw_job.get("title") or "").strip()
    if not title:
        raise ValueError("job record has no title")

    location = (raw_job.get("locationsText") or "").strip()
    location_keywords = source.config.get("location_keywords")

    verdict = classify_posting(title, location=location, location_keywords=location_keywords)
    if verdict is None:
        return None

    event = Event(kind="internship", source_id=source.source_id)
    event.external_id = _external_id(raw_job)

    event.set("title", title, source=SOURCE_NAME, confidence=CONFIDENCE)

    # Event.start deliberately left unset -- postedOn is always a
    # relative string ("Posted Today", "Posted 30+ Days Ago"), never an
    # absolute timestamp. See module docstring's Design Rationale.

    if location:
        event.set("location", location, source=SOURCE_NAME, confidence=CONFIDENCE)

    external_path = (raw_job.get("externalPath") or "").strip()
    if external_path:
        event.set(
            "registration_url",
            careers_base + external_path,
            source=SOURCE_NAME,
            confidence=CONFIDENCE,
        )

    # This family's classification defaults -- deliberately no
    # cost/cost_range (see module docstring and ats_filters.py).
    event.set(
        "age_grade_level", verdict.age_grade_level, source=SOURCE_NAME, confidence=CONFIDENCE
    )
    event.set("time_of_day", verdict.time_of_day, source=SOURCE_NAME, confidence=CONFIDENCE)

    return event


class WorkdayAdapter:
    """``Adapter`` for Workday's public CXS job-search API (``workday``)."""

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[EventRef]:
        """Probe ``offset=0`` to learn ``total``, then enumerate one
        ``EventRef`` per page (``context={"offset": N}``).

        Every ``EventRef`` shares the same ``url`` (this source's one
        jobs-search endpoint) -- pagination lives entirely in
        ``context["offset"]``, which ``fetch()`` reads back out to build
        each page's request body. This is exactly why
        ``PoliteFetcher.post()`` (ticket 004) never caches: a URL-keyed
        cache would collide every one of these same-URL, different-body
        pages onto one entry.

        A probe that fails to fetch or parse is treated as "exactly one
        page" rather than raising -- per-source failure isolation
        belongs to the Pipeline, so this adapter degrades gracefully,
        matching ``smartrecruiters.py``'s/``tec.py``'s probe-then-
        paginate convention. Page count is also capped at
        :data:`MAX_PAGES` as a backstop against a source that misreports
        ``total``.
        """
        url = _jobs_url(source)
        headers = _request_headers(source)
        probe = fetcher.post(url, body=_page_body(0), headers=headers, **acquisition_kwargs(source))

        total_pages = 1
        if probe.status == 200:
            try:
                data = json.loads(probe.body)
                total = max(0, int(data.get("total", 0)))
                total_pages = max(1, math.ceil(total / PAGE_SIZE)) if total else 1
            except (json.JSONDecodeError, TypeError, ValueError):
                logger.warning(
                    "Workday probe for %s returned unparseable JSON; assuming 1 page", url
                )
        else:
            logger.warning(
                "Workday probe for %s returned status %s; assuming 1 page", url, probe.status
            )

        if total_pages > MAX_PAGES:
            logger.warning(
                "Workday source %s reports %d pages; capping at %d", url, total_pages, MAX_PAGES
            )
            total_pages = MAX_PAGES

        return [
            EventRef(url=url, context={"offset": page * PAGE_SIZE}) for page in range(total_pages)
        ]

    def fetch(self, ref: EventRef, fetcher: Fetcher, source: SourceConfig) -> RawResponse:
        offset = int(ref.context.get("offset", 0))
        response = fetcher.post(
            ref.url, body=_page_body(offset), headers=_request_headers(source), **acquisition_kwargs(source)
        )
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        if raw.status != 200:
            logger.warning(
                "Workday page fetch %s returned status %s; skipping", raw.ref.url, raw.status
            )
            return []

        try:
            data = json.loads(raw.body)
        except json.JSONDecodeError:
            logger.warning("Workday page %s returned unparseable JSON; skipping", raw.ref.url)
            return []

        if not isinstance(data, dict):
            logger.warning(
                "Workday page %s returned an unexpected JSON shape; skipping", raw.ref.url
            )
            return []

        careers_base = _careers_url(source)

        events: list[Event] = []
        for raw_job in data.get("jobPostings", []):
            if not isinstance(raw_job, dict):
                logger.warning(
                    "Skipping malformed Workday job record on %s: not an object", raw.ref.url
                )
                continue
            try:
                event = _extract_one(raw_job, source, careers_base)
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping malformed Workday job record on %s: %s", raw.ref.url, exc
                )
                continue
            if event is not None:
                events.append(event)
        return events
