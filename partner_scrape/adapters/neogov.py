"""NEOGOV/governmentjobs.com job-listing JSON adapter.

See sprint 031's ticket 006 and SUC-059: unlike Workday/SmartRecruiters/
Workable, issue 31's census carried no confirmed endpoint shape for
``governmentjobs.com`` -- only that County of San Diego, City of San
Diego, SANDAG, and Port of San Diego each publish through it. This
ticket's own required first step was live discovery before any parsing
code: a plain ``curl`` against each agency's public careers page
(``https://www.governmentjobs.com/careers/{agency}``) renders an empty
``<div id="job-list-container">`` server-side ("0 jobs found" is a
static placeholder) -- the real job list is populated client-side, by
an AJAX call the page's own JS makes after load. Tracing that call
through the site's own minified ``AgencyPages/search`` JS bundle (its
``loadJobsOnMaps`` map-view search path, not the default HTML-fragment
search path) found the real, structured JSON endpoint this adapter
uses::

    GET https://www.governmentjobs.com/careers/{agency}/home/loadJobsOnMaps

confirmed live 2026-09-02 for all four agencies, with no session/cookie
required -- only three request headers the page's own AJAX call sends
(``X-Requested-With: XMLHttpRequest``, an ``Accept: application/json,
text/javascript, */*; q=0.01`` matching jQuery's own default AJAX
Accept header, and a ``Referer`` naming the agency's own careers page)::

    {"success": true, "jobList": [{"ID": 5448382, "Classification":
      "Safety and Training Manager", "Location": "City of San Diego, CA",
      "JobType": "Permanent, Full Time", "SalaryInfo": "$107,432.00 -
      $130,187.20 Annually", "FullDescription": "...", "OpenDate":
      "Posted 5 days ago", "CloseDate": "Closes in 6 days",
      "PostingDate": "08/28/26", "ClosingDate": "09/08/26",
      "DepartmentName": "N/A - Multiple Departments", "Categories":
      ["Human Resources", "Safety", "Training"], "JobNumber":
      "JH-T11922-202608", "Continuous": false, "JobTitle":
      "safety-and-training-manager", ...}], ...}

Confirmed **not paginated** for any of the four agencies' current
result sets (32/1/72/5 postings respectively, 2026-09-02) -- the whole
``jobList`` for an agency's currently-open postings comes back in one
response, mirroring ``workable.py``'s "no probe-then-paginate" shape.

Field mapping: ``external_id`` <- ``ID``; ``title`` <- ``Classification``
(NEOGOV's own field name for a posting's job title); ``start`` <- parsed
``PostingDate`` (``MM/DD/YY``, interpreted as UTC midnight -- the only
absolute-date field this endpoint returns; ``OpenDate``/``CloseDate``
are relative display strings ("Posted 5 days ago") like Workday's own
``postedOn``, not used here); ``location`` <- ``Location`` (already a
single display string, e.g. ``"City of San Diego, CA"``);
``description`` <- ``FullDescription`` (plain text, confirmed live --
unlike Workable's ``description``, no HTML tags to strip);
``registration_url`` <- built from ``ID`` and ``JobTitle`` (live-
confirmed to be the exact URL path slug, not a display value:
``https://www.governmentjobs.com/careers/{agency}/jobs/{ID}/{JobTitle}``
resolves live). No ``end``/deadline field is set even when
``ClosingDate`` carries an absolute date -- matching every other
adapter in this family (see ``workday.py``'s own Design Rationale in
``adapters/DESIGN.md``): a NEOGOV posting's ``Continuous`` postings
(no closing date at all) and dated ones are both left to
``normalize.run()``'s existing internship rolling-availability branch,
rather than adding a new, family-inconsistent mapping for only this one
adapter. Every field this adapter sets is high-trust (:data:`CONFIDENCE`
1.0), matching ``greenhouse.py``'s/``lever.py``'s/``smartrecruiters.py``'s/
``workable.py``'s convention.

``Categories`` (a list, e.g. ``["Internship"]`` -- confirmed live as
NEOGOV's own internship-program tag, distinct from ``JobType``, which
carries commitment-*schedule* values like "Temporary - Part Time"
rather than an internship signal) is joined and passed into
``ats_filters.classify_posting`` as the ``commitment`` signal, the same
role Lever's ``categories.commitment``/SmartRecruiters'
``typeOfEmployment.label``/Workable's ``employment_type`` play for
their own adapters. ``DepartmentName`` is passed as the
STEM-classification ``department`` text.

Every raw posting is run through ``adapters.ats_filters.classify_posting``
*before* an ``Event`` is constructed; only a match becomes an ``Event``,
with ``kind="internship"`` and the verdict's default
``age_grade_level``/``time_of_day`` applied via ``Event.set(...)``.
Deliberately does not set ``Event.cost``/``Event.cost_range`` -- same
contract as every other adapter in this family (see ``ats_filters.py``'s
module docstring).

**GENUINE ROBOTS BLOCK, all four agencies registered ``enabled =
false``.** ``www.governmentjobs.com/robots.txt`` (confirmed live
2026-09-02, applies to every agency registered under it -- one shared
host, one shared robots.txt) carries a named-crawler allow list
(Googlebot, bingbot, yahoobot, msnbot, gsa-crawler-www, NHN, Twitterbot,
facebookexternalhit) followed by ``User-agent: *`` / ``Disallow: /`` --
the identical "carve out a few named partners, block every other bot"
shape ``servicenow.toml``'s SmartRecruiters registration (sprint 031
ticket 002) already documents and disables for. This project's
``PoliteFetcher`` respects robots.txt by default
(``acquisition_policy.respect_robots`` defaults to ``true``) and would
raise ``RobotsDisallowed`` for this bot's user agent against any path
under this host, including ``/home/loadJobsOnMaps``. No stakeholder
decision exists yet to override ``respect_robots`` for this vendor (the
same gap ``servicenow.toml``'s own header comment names) -- registered
``enabled = false`` per this sprint's own "``enabled = false`` only for
a genuine block" standard, not assumed ``respect_robots = false``. The
adapter itself is fully built and tested against fixtures reproducing
the live response shape above; flipping any of the four sources to
``enabled = true`` needs no further adapter code, only a registry edit
plus (per ``servicenow.toml``'s own precedent) a stakeholder decision
to override ``respect_robots`` for this vendor.

Live-verification result (2026-09-02, all four agencies, recorded in
ticket 006's own Notes): 110 total postings fetched (32 City of San
Diego, 1 SANDAG, 72 County of San Diego, 5 Port of San Diego); 2 postings
across the batch carry NEOGOV's own ``"Internship"`` ``Categories`` tag
(both at County of San Diego -- a general "Student Worker" program and
a "Student Organizer Internship Program"), plus 2 more titled "Junior
Engineer - Civil (Student)"/"Student Engineer" (City of San Diego, no
``"Internship"`` category and no internship-pattern word in the title).
0 of the 110 pass ``classify_posting``'s internship + STEM + San Diego
test -- both actual ``"Internship"``-tagged postings are general
student-worker programs with no STEM-coded title/department (Human
Resources; a department-spanning "Administrative Assistant/Community
Services/.../Human Services" list), and the two student-engineer titles
carry no recognized internship-pattern word or ``Categories`` tag for
``is_internship_posting`` to match on. A working, zero-match pass, not
a failure, per this sprint's own Success Criteria -- and, per issue 31's
own framing, this is exactly the seasonal case: cadence matters more
than any single run's yield for these four sources.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from partner_scrape.adapters.ats_filters import classify_posting
from partner_scrape.adapters.base import EventRef, RawResponse, acquisition_kwargs
from partner_scrape.fetch import Fetcher
from partner_scrape.model import Event
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: This adapter's provenance source name, recorded on every field it sets.
SOURCE_NAME = "neogov"

#: NEOGOV's ``loadJobsOnMaps`` endpoint is a structured, first-party
#: feed -- every field this adapter sets is maximally trusted, matching
#: every other adapter in this family's convention.
CONFIDENCE = 1.0

#: Default NEOGOV/governmentjobs.com careers host, per this ticket's
#: confirmed-live shape. A source's ``config`` may override this with
#: its own ``api_base`` key (mirrors ``greenhouse.py``'s/``workable.py``'s
#: own ``api_base`` config convention).
DEFAULT_API_BASE = "https://www.governmentjobs.com/careers"


def _parse_posting_date(value: str) -> datetime | None:
    """Parse a NEOGOV ``PostingDate`` (``MM/DD/YY``).

    Returns ``None`` for an absent/empty value. Raises ``ValueError`` on
    an unparseable non-empty value -- left uncaught here so the caller
    (``_extract_one``) can isolate it as a whole-record failure, matching
    ``smartrecruiters.py``'s/``workable.py``'s ``_parse_*`` convention.
    Interpreted as UTC midnight, matching this codebase's existing
    UTC-aware-datetime convention for a date-only source field.
    """
    if not value:
        return None
    parsed = datetime.strptime(value, "%m/%d/%y")
    return parsed.replace(tzinfo=timezone.utc)


def _detail_url(api_base: str, agency: str, job_id: Any, job_title_slug: str) -> str:
    """Build this posting's public detail/apply page.

    Live-confirmed (module docstring): ``JobTitle`` is the exact URL
    path slug, not merely a display value -- the constructed URL
    resolves with no extra network call needed to look it up.
    """
    return f"{api_base}/{agency}/jobs/{job_id}/{job_title_slug}"


def _extract_one(
    raw_job: dict[str, Any], source: SourceConfig, api_base: str, agency: str
) -> Event | None:
    """Map one raw NEOGOV job record into a canonical internship ``Event``.

    Returns ``None`` when the posting does not pass
    ``ats_filters.classify_posting`` -- not an error, simply not a
    match, so the caller must not treat it as a skipped/malformed
    record.

    Raises:
        ValueError: the record has no usable title (``Classification``).
        ValueError: a ``PostingDate`` value is present but unparseable.

    Both are caught by the caller (``extract()``) and treated as a
    per-record skip -- never fatal to the rest of the response, matching
    every other adapter in this family's per-record isolation convention.
    """
    title = (raw_job.get("Classification") or "").strip()
    if not title:
        raise ValueError("job record has no Classification/title")

    location = (raw_job.get("Location") or "").strip()
    department = (raw_job.get("DepartmentName") or "").strip()
    categories = [c for c in (raw_job.get("Categories") or []) if c]
    commitment = ", ".join(categories)
    location_keywords = source.config.get("location_keywords")

    verdict = classify_posting(
        title,
        commitment=commitment,
        department=department,
        location=location,
        location_keywords=location_keywords,
    )
    if verdict is None:
        return None

    event = Event(kind="internship", source_id=source.source_id)
    job_id = raw_job.get("ID")
    event.external_id = str(job_id) if job_id is not None else ""

    event.set("title", title, source=SOURCE_NAME, confidence=CONFIDENCE)

    start = _parse_posting_date(raw_job.get("PostingDate") or "")
    if start is not None:
        event.set("start", start, source=SOURCE_NAME, confidence=CONFIDENCE)

    if location:
        event.set("location", location, source=SOURCE_NAME, confidence=CONFIDENCE)

    description = (raw_job.get("FullDescription") or "").strip()
    if description:
        event.set("description", description, source=SOURCE_NAME, confidence=CONFIDENCE)

    job_title_slug = (raw_job.get("JobTitle") or "").strip()
    if job_id is not None and job_title_slug:
        event.set(
            "registration_url",
            _detail_url(api_base, agency, job_id, job_title_slug),
            source=SOURCE_NAME,
            confidence=CONFIDENCE,
        )

    # Same classification-defaults contract as every other adapter in
    # this family -- deliberately no cost/cost_range (see module
    # docstring and ats_filters.py).
    event.set(
        "age_grade_level", verdict.age_grade_level, source=SOURCE_NAME, confidence=CONFIDENCE
    )
    event.set("time_of_day", verdict.time_of_day, source=SOURCE_NAME, confidence=CONFIDENCE)

    return event


def _jobs_url(api_base: str, agency: str) -> str:
    """Build this source's one job-listing JSON URL (module docstring)."""
    return f"{api_base}/{agency}/home/loadJobsOnMaps"


def _request_headers(api_base: str, agency: str) -> dict[str, str]:
    """Build the three headers the endpoint needs (module docstring).

    Live-confirmed 2026-09-02: no session/cookie is required, only these
    headers -- ``X-Requested-With``/``Accept`` matching the page's own
    jQuery AJAX call shape, and a ``Referer`` naming the agency's own
    careers page.
    """
    return {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": f"{api_base}/{agency}",
    }


class NeogovAdapter:
    """``Adapter`` for the NEOGOV/governmentjobs.com job-listing JSON endpoint (``neogov``)."""

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[EventRef]:
        """Return exactly one ``EventRef`` for this agency's job-listing URL.

        Confirmed not paginated for any of this ticket's four agencies
        (module docstring) -- there is no probe/page-count step to run,
        mirroring ``workable.py``'s ``discover()``.
        """
        api_base = source.config.get("api_base") or DEFAULT_API_BASE
        agency = source.config["agency"]
        return [EventRef(url=_jobs_url(api_base, agency), context={"agency": agency})]

    def fetch(self, ref: EventRef, fetcher: Fetcher, source: SourceConfig) -> RawResponse:
        api_base = source.config.get("api_base") or DEFAULT_API_BASE
        agency = source.config["agency"]
        response = fetcher.get(
            ref.url, headers=_request_headers(api_base, agency), **acquisition_kwargs(source)
        )
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        if raw.status != 200:
            logger.warning(
                "NEOGOV agency fetch %s returned status %s; skipping", raw.ref.url, raw.status
            )
            return []

        try:
            data = json.loads(raw.body)
        except json.JSONDecodeError:
            logger.warning("NEOGOV agency %s returned unparseable JSON; skipping", raw.ref.url)
            return []

        if not isinstance(data, dict):
            logger.warning(
                "NEOGOV agency %s returned an unexpected JSON shape; skipping", raw.ref.url
            )
            return []

        if data.get("success") is False:
            logger.warning("NEOGOV agency %s reported success=false; skipping", raw.ref.url)
            return []

        api_base = source.config.get("api_base") or DEFAULT_API_BASE
        agency = source.config.get("agency", "")

        events: list[Event] = []
        for raw_job in data.get("jobList", []):
            if not isinstance(raw_job, dict):
                logger.warning(
                    "Skipping malformed NEOGOV job record on %s: not an object", raw.ref.url
                )
                continue
            try:
                event = _extract_one(raw_job, source, api_base, agency)
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping malformed NEOGOV job record on %s: %s", raw.ref.url, exc
                )
                continue
            if event is not None:
                events.append(event)
        return events
