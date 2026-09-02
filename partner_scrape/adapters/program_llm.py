"""The ``ProgramLLMClient`` protocol, ``ProgramExtractionResult``, and its
one real implementation, ``AnthropicProgramLLMClient``.

Sprint 027 ticket 002: the reusable extraction engine `ProgramPageAdapter`/
`ProgramListingAdapter` (tickets 003/004) call to turn a fetched curated
program page's raw body into a structured, program-shaped field set --
program name, audience/grades, date range, application window/deadline,
paid/cost, eligibility, open/closed status -- that no structured API
publishes and no deterministic extraction ladder rung could recover.

Deliberately mirrors, never imports, ``enrich/llm_client.py`` -- same
injectable-Protocol/JSON-schema-from-dataclass *shape* (a real
Anthropic-backed client plus a fixture test double), same rationale as
``teams/sponsor_llm.py``'s sprint 013 precedent: a second small module
sharing the shape costs less than reaching across the ``adapters`` ->
``enrich`` layering this codebase has never needed. See
``adapters/DESIGN.md``'s sprint 027 section ("Deliberately mirrors, never
imports, `enrich/llm_client.py`") for the full rationale. Every controlled
vocabulary value below is duplicated from ``enrich/llm_client.py``
deliberately, per that same "mirrors, never imports" rule -- do not import
``_OPPORTUNITY_TYPE_VALUES`` from there.

``AnthropicProgramLLMClient`` constructs ``anthropic.Anthropic()`` with
**no** explicit ``api_key`` argument -- the SDK resolves
``ANTHROPIC_API_KEY`` itself, matching ``enrich/llm_client.py``'s exact
credential convention.

**(Sprint 029 ticket 006)** ``extract_program``/``extract_programs`` gain
two backward-compatible keyword-only parameters, ``profile`` and
``reference_date``, selecting between this module's original
application-window *program* system prompts (default, unchanged) and a
new single-dated-event *competition* prompt pair
(``_SYSTEM_PROMPT_COMPETITION``/``_SYSTEM_PROMPT_COMPETITION_MULTI``),
fixing a systematic date-vs-deadline-framing and year-inference
extraction failure tickets 001/002's own live-verification found in the
unrevised prompts when applied to a competition/tournament page. See
``adapters/DESIGN.md``'s "Revision (2026-09-02 -- sprint 029
competition-genre extraction fix)" section for the full evidence and
design write-up. ``ProgramExtractionResult`` gains one new field,
``registration_deadline``, populated only by the competition profile.

**(Sprint 030 ticket 004)** ``profile`` accepts a third value, ``"pd"``,
for an educator professional-development page (a workshop, summit, or
conference/chapter meeting) -- its own prompt pair
(``_SYSTEM_PROMPT_PD``/``_SYSTEM_PROMPT_PD_MULTI``), neither the base
``"program"`` profile's application-window framing nor the
``"competition"`` profile's competition/tournament vocabulary, both of
which were found to actively mislead the model on this genre's pages.
See ``adapters/DESIGN.md``'s "Revision (2026-09-02 -- sprint 030
educator-PD extraction profile)" section for the full reasoning. No
``ProgramExtractionResult`` field is added -- the existing fields
already cover a PD event's shape (``registration_deadline`` for a
stated RSVP/registration cutoff distinct from the event date,
``audience_grades`` reused to hold an educator-audience descriptor like
"K-5 teachers" rather than a student grade band). No
``ProgramExtractionCache._CACHE_SCHEMA_VERSION`` bump either -- the
stored-entry shape is unchanged.
"""

from __future__ import annotations

import dataclasses
import json
import types
import typing
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Protocol

import anthropic

#: Single named model-ID constant -- every real request uses this
#: constant, never inlined at more than one call site, mirroring
#: ``enrich/llm_client.py``'s ``MODEL_ID`` convention. Program-page
#: extraction is low-volume (a curated registry of ~15-40 pages, not the
#: whole per-Event enrichment corpus) and the source text is often a
#: dense, information-bearing prose page, so this uses the stronger tier
#: rather than ``enrich/llm_client.py``'s high-volume Haiku default.
MODEL_ID = "claude-haiku-4-5-20251001"

#: Controlled vocabulary mirrored (not imported, see module docstring)
#: from ``enrich/llm_client.py``'s ``_OPPORTUNITY_TYPE_VALUES`` -- given to
#: the model as prompt guidance so its classification lines up with the
#: site's existing taxonomy.
_OPPORTUNITY_TYPE_VALUES = [
    "Out-of-school Programs",
    "Online",
    "Professional Development / Conferences",
    "School Programs",
    "Career Connections",
    "Volunteering",
    "Funding Opportunities",
    "Camps",
    "Competitions",
]

#: Provenance constants for the ``Event.set(...)`` calls tickets 003/004's
#: adapters make when mapping a ``ProgramExtractionResult`` onto an
#: ``Event`` -- mirrors ``enrich/llm_client.py``'s ``LLM_SOURCE``/
#: ``LLM_CONFIDENCE`` naming convention (that module does not actually
#: define constants by these exact names today, but this module's own
#: adapters need one, so it is introduced here).
PROGRAM_LLM_SOURCE = "program_llm_extraction"
PROGRAM_LLM_CONFIDENCE = 0.9


@dataclass
class ProgramExtractionResult:
    """One LLM extraction call's structured output for one program page.

    Unlike ``enrich/llm_client.py``'s ``EnrichmentResult`` (which recovers
    *missing* fields on an already-adapter-extracted ``Event``), this
    drives a fetch+extract call for a whole curated page from scratch,
    against a bespoke program-page schema -- there is no pre-existing
    ``Event`` to compare against, so every field here is a plain,
    non-Optional value (an empty string/list means "not stated on the
    page", not "not attempted").
    """

    program_name: str = ""
    audience_grades: list[str] = field(default_factory=list)
    #: ISO date (``YYYY-MM-DD``) or ``""`` -- the application window's
    #: open date.
    date_start: str = ""
    #: ISO date (``YYYY-MM-DD``) or ``""`` -- the application deadline.
    date_end: str = ""
    cost: str = ""
    eligibility: str = ""
    is_open: bool = True
    opportunity_type: str = ""
    #: ISO date (``YYYY-MM-DD``) or ``""`` -- (sprint 029 ticket 006) a
    #: registration/team-signup/paperwork deadline stated *separately*
    #: from the event's own date. Populated only by ``profile=
    #: "competition"``'s field rules; always ``""`` for the base
    #: ``profile="program"`` (an application-window program's one
    #: deadline is already ``date_end`` -- see ``_FIELD_EXTRACTION_RULES``).
    #: Never mapped onto ``Event.start``/``Event.end`` -- see
    #: ``adapters/program_page.py``'s ``_map_result_to_event``.
    registration_deadline: str = ""


class ProgramLLMClient(Protocol):
    """Injectable seam for one LLM extraction call over one program page.

    Mirrors ``enrich/llm_client.py``'s ``LLMClient`` protocol pattern.
    Implementations receive a URL (for context/logging) and the fetched
    page's raw body text, and return a structured
    :class:`ProgramExtractionResult` -- never a raw string, never a
    partially-parsed dict.
    """

    def extract_program(
        self,
        url: str,
        body: str,
        *,
        profile: str = "program",
        reference_date: date | None = None,
    ) -> ProgramExtractionResult:
        """Return one LLM extraction result for the page at ``url``.

        **(Sprint 029 ticket 006)** ``profile`` selects the system prompt
        variant: ``"program"`` (default, unchanged) for an
        application-window program page, or ``"competition"`` for a
        single-dated-event competition/tournament page (its own
        ``date_start``/``date_end``-vs-``registration_deadline``
        framing). **(Sprint 030 ticket 004)** ``profile="pd"`` selects a
        third variant for an educator professional-development page (a
        workshop, summit, or conference/chapter meeting) -- its own
        date-vs-registration-deadline framing and educator-audience
        vocabulary, sharing the competition profile's "the primary date
        is the event's own date" structure but none of its
        competition/tournament wording. ``reference_date`` (default
        ``None``, meaning "no reference date line is added to the
        prompt" -- byte-identical to pre-revision behavior) is injected
        into the *user* prompt as "Page fetched on: ``<ISO date>``",
        used by both the competition and pd profiles' shared
        year-inference rule. All are optional and backward-compatible:
        every call site that omits them is unaffected.
        """
        ...

    def extract_programs(
        self,
        url: str,
        body: str,
        *,
        profile: str = "program",
        reference_date: date | None = None,
    ) -> list[ProgramExtractionResult]:
        """Return one LLM extraction result *per inline program record*
        found on the page at ``url``.

        **(Ticket 006 exception revision)** For a page whose body holds N
        distinct program sections (SIO's shape -- see
        ``adapters/DESIGN.md``'s Revision note), rather than the single
        record :meth:`extract_program` recovers for a page dedicated to
        one program.

        **(Sprint 029 ticket 006, Sprint 030 ticket 004)**
        ``profile``/``reference_date`` -- see :meth:`extract_program`.
        """
        ...


class ProgramLLMExtractionError(Exception):
    """Raised when an LLM response cannot be parsed into a
    ``ProgramExtractionResult``.

    Covers malformed JSON, a missing text content block, and any field of
    the wrong shape/type -- mirrors ``enrich/llm_client.py``'s
    ``LLMEnrichmentError`` so callers can distinguish "the model/API
    misbehaved" from an unrelated programming error.
    """


# --------------------------------------------------------------------
# Structured-output JSON schema, built directly from
# ProgramExtractionResult's shape (via dataclass field introspection) so
# the schema and the dataclass cannot drift silently -- mirrors
# enrich/llm_client.py's _build_enrichment_json_schema()/_field_json_schema
# shape.
# --------------------------------------------------------------------


def _field_json_schema(annotation: Any) -> dict[str, Any]:
    """Return the JSON schema fragment for one resolved type annotation."""
    origin = typing.get_origin(annotation)

    if origin is types.UnionType or origin is typing.Union:
        args = typing.get_args(annotation)
        nullable = type(None) in args
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) != 1:
            raise TypeError(f"Unsupported union in ProgramExtractionResult schema: {annotation!r}")
        inner = _field_json_schema(non_none[0])
        if nullable:
            return {"anyOf": [inner, {"type": "null"}]}
        return inner

    if origin is list:
        (item_type,) = typing.get_args(annotation)
        return {"type": "array", "items": _field_json_schema(item_type)}

    if annotation is str:
        return {"type": "string"}
    if annotation is bool:
        return {"type": "boolean"}

    raise TypeError(f"Unsupported field type for ProgramExtractionResult schema: {annotation!r}")


def _build_program_extraction_json_schema() -> dict[str, Any]:
    hints = typing.get_type_hints(ProgramExtractionResult)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for f in dataclasses.fields(ProgramExtractionResult):
        properties[f.name] = _field_json_schema(hints[f.name])
        required.append(f.name)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


#: The structured-output schema sent on every real request -- see
#: :func:`_build_program_extraction_json_schema`.
PROGRAM_EXTRACTION_JSON_SCHEMA = _build_program_extraction_json_schema()


def _build_program_list_extraction_json_schema() -> dict[str, Any]:
    """The list-valued counterpart to
    :func:`_build_program_extraction_json_schema`, for
    ``extract_programs()``'s one-page/N-record shape (ticket 006
    exception revision). Wraps the identical per-record object schema --
    built the same dataclass-introspection way, never duplicated by hand
    -- in ``{"programs": [...]}``.
    """
    return {
        "type": "object",
        "properties": {
            "programs": {"type": "array", "items": PROGRAM_EXTRACTION_JSON_SCHEMA}
        },
        "required": ["programs"],
        "additionalProperties": False,
    }


#: The structured-output schema sent on every real ``extract_programs()``
#: request -- see :func:`_build_program_list_extraction_json_schema`.
PROGRAM_LIST_EXTRACTION_JSON_SCHEMA = _build_program_list_extraction_json_schema()


#: The per-field extraction rules, shared verbatim between the
#: single-record (:data:`_SYSTEM_PROMPT`) and multi-record
#: (:data:`_SYSTEM_PROMPT_MULTI`) system prompts -- ticket 006 exception
#: revision's ``extract_programs()`` asks the model to apply these exact
#: same rules once per distinct program section rather than once for the
#: whole page.
_FIELD_EXTRACTION_RULES = f"""- program_name: the program's name, as titled on the page.
- audience_grades: zero or more grade/audience descriptors actually named \
on the page (e.g. "9th grade", "high school", "undergraduate"), as short \
strings in the page's own words.
- date_start: the application window's open date, as an ISO date \
(YYYY-MM-DD), or "" if not stated.
- date_end: the application deadline, as an ISO date (YYYY-MM-DD), or "" \
if not stated.
- cost: a short description of program cost or stipend/pay (e.g. "Free", \
"Paid stipend", "$500 fee"), or "" if not stated.
- eligibility: a short free-text summary of eligibility requirements \
(grade level, residency, citizenship, GPA, etc.), or "" if not stated.
- is_open: true if open for enrollment/application; false if closed, \
full, or sold out. Default to true when the page gives no clear signal \
either way.
- opportunity_type: exactly one of {_OPPORTUNITY_TYPE_VALUES}, based on \
what kind of opportunity this is. Use "Out-of-school Programs" as the \
general default whenever nothing more specific clearly applies -- this \
field is never left blank.
- registration_deadline: always "" for this page type -- an \
application-window program's one deadline is already date_end."""


#: (Sprint 029 ticket 006) The per-field extraction rules for the
#: competition/tournament genre, shared verbatim between the
#: single-record (:data:`_SYSTEM_PROMPT_COMPETITION`) and multi-record
#: (:data:`_SYSTEM_PROMPT_COMPETITION_MULTI`) system prompts, the same
#: way :data:`_FIELD_EXTRACTION_RULES` is shared between the base
#: single-/multi-record prompts. Unlike the base profile's rules (a
#: prose *program* page whose primary date is an application window),
#: this profile's page is a single dated *event* -- see
#: ``adapters/DESIGN.md``'s "Revision (2026-09-02 -- sprint 029
#: competition-genre extraction fix)" section for the live evidence
#: (``sd-brain-bee``, ``seaperch-sd-regional``, ``tritonhacks``) this
#: rewrite directly addresses.
_FIELD_EXTRACTION_RULES_COMPETITION = f"""- program_name: the competition or tournament's name, as titled on the \
page.
- audience_grades: zero or more grade/audience descriptors actually named \
on the page (e.g. "9th grade", "high school", "undergraduate"), as short \
strings in the page's own words.
- date_start: the competition/tournament event's OWN date, as an ISO date \
(YYYY-MM-DD), or "" if not stated -- the first day of the event if it \
spans multiple days. Look for the date under any of: "Event Date," \
"Competition Date," "Tournament Date," "Save the Date," as well as \
ordinary prose. This is NEVER a registration, sign-up, or paperwork \
deadline -- put that in registration_deadline instead, never here.
- date_end: the event's own last day, as an ISO date (YYYY-MM-DD), if it \
spans multiple days, else "". It is NOT a registration, sign-up, or \
paperwork deadline -- put that in registration_deadline instead, never \
here.
- registration_deadline: a registration, team-signup, or paperwork \
deadline (e.g. a Technical Design Report submission due date) stated \
separately from the event's own date, as an ISO date (YYYY-MM-DD), or "" \
if none is stated or the page states only one date.
- cost: a short description of program cost or stipend/pay (e.g. "Free", \
"Paid stipend", "$500 fee"), or "" if not stated.
- eligibility: a short free-text summary of eligibility requirements \
(grade level, residency, citizenship, GPA, etc.), or "" if not stated.
- is_open: true if open for enrollment/application; false if closed, \
full, or sold out. Default to true when the page gives no clear signal \
either way.
- opportunity_type: exactly one of {_OPPORTUNITY_TYPE_VALUES}, based on \
what kind of opportunity this is. Use "Out-of-school Programs" as the \
general default whenever nothing more specific clearly applies -- this \
field is never left blank.

Year inference (a narrow, explicit exception to "never guess a date not \
stated," scoped only to a year component): if a date on the page states \
a month and day but no year, infer the soonest year (this one, or next) \
in which that month/day falls on or after the reference date stated \
above ("Page fetched on: <date>") -- never leave the year off, and do \
not default to the current calendar year if that month/day has already \
passed relative to the reference date."""


_SYSTEM_PROMPT = f"""You are helping curate a directory of STEM learning \
opportunities for learners of all ages in the San Diego area. You are \
given the raw text of one curated program page -- a paid summer research \
placement, an internship, a scholarship, or a similar application-window \
program -- scraped from a lab, university, or organization's website. \
Extract the following fields, using only what is solidly supported by the \
page text. Never guess a specific date, grade, or amount that is not \
stated or strongly implied.

{_FIELD_EXTRACTION_RULES}

Respond only with the structured JSON the response format requires."""


#: (Ticket 006 exception revision) System prompt for ``extract_programs()``
#: -- a page whose body holds N distinct program sections inline (SIO's
#: shape: a ``<div class="page-section">`` block per program, each with
#: its own deadline in prose on the summary page itself, not a link to a
#: page that carries it), rather than one page dedicated to one program.
_SYSTEM_PROMPT_MULTI = f"""You are helping curate a directory of STEM learning \
opportunities for learners of all ages in the San Diego area. You are \
given the raw text of one curated page that describes MULTIPLE distinct \
programs -- each a paid summer research placement, an internship, a \
scholarship, or a similar application-window program -- as separate \
inline sections on the same page, rather than links out to separate \
detail pages. Identify every distinct program described on the page, and \
for EACH one extract the following fields, using only what is solidly \
supported by that program's own section of the page text. Never guess a \
specific date, grade, or amount that is not stated or strongly implied \
for that program, and never blend two distinct programs' details into \
one record.

{_FIELD_EXTRACTION_RULES}

If no distinct programs are described on the page, return an empty list.

Respond only with the structured JSON the response format requires: a \
single object with one key, "programs", whose value is a list with \
exactly one entry per distinct program found on the page."""


#: (Sprint 029 ticket 006) System prompt for ``extract_program(...,
#: profile="competition")`` -- one page dedicated to a single-dated
#: competition/tournament event, as opposed to :data:`_SYSTEM_PROMPT`'s
#: application-window program genre. See ``adapters/DESIGN.md``'s
#: "Revision (2026-09-02 -- sprint 029 competition-genre extraction
#: fix)" section.
_SYSTEM_PROMPT_COMPETITION = f"""You are helping curate a directory of STEM learning \
opportunities for learners of all ages in the San Diego area. You are \
given the raw text of one curated competition or tournament page -- a \
single dated event, such as a robotics league match, an academic bowl, \
a hackathon, or a science fair -- scraped from an organization's \
website. Unlike an application-window program, this page's primary date \
is the event's OWN date, not an application or registration deadline. \
Extract the following fields, using only what is solidly supported by \
the page text. Never guess a specific date, grade, or amount that is \
not stated or strongly implied, except for the narrow year-inference \
rule below.

{_FIELD_EXTRACTION_RULES_COMPETITION}

Respond only with the structured JSON the response format requires."""


#: (Sprint 029 ticket 006) The ``profile="competition"`` counterpart to
#: :data:`_SYSTEM_PROMPT_MULTI` -- one page whose body holds N inline
#: competition/tournament records rather than one.
_SYSTEM_PROMPT_COMPETITION_MULTI = f"""You are helping curate a directory of STEM learning \
opportunities for learners of all ages in the San Diego area. You are \
given the raw text of one curated page that describes MULTIPLE distinct \
competitions or tournaments -- each a single dated event -- as separate \
inline sections on the same page, rather than links out to separate \
detail pages. Identify every distinct competition described on the \
page, and for EACH one extract the following fields, using only what is \
solidly supported by that competition's own section of the page text. \
Never guess a specific date, grade, or amount that is not stated or \
strongly implied for that competition, except for the narrow \
year-inference rule below, and never blend two distinct competitions' \
details into one record.

{_FIELD_EXTRACTION_RULES_COMPETITION}

If no distinct competitions are described on the page, return an empty \
list.

Respond only with the structured JSON the response format requires: a \
single object with one key, "programs", whose value is a list with \
exactly one entry per distinct competition found on the page."""


#: (Sprint 030 ticket 004) The per-field extraction rules for the
#: educator professional-development genre, shared verbatim between the
#: single-record (:data:`_SYSTEM_PROMPT_PD`) and multi-record
#: (:data:`_SYSTEM_PROMPT_PD_MULTI`) system prompts, the same way
#: :data:`_FIELD_EXTRACTION_RULES_COMPETITION` is shared between the
#: competition single-/multi-record prompts. Shares the competition
#: profile's "the primary date is the event's own date, not an
#: application window" structure and its narrow reference-date
#: year-inference rule, but replaces every competition/tournament
#: vocabulary cue with educator-PD phrasing ("Workshop Date," "Session
#: Date," "Registration closes," "RSVP by") and reframes ``eligibility``/
#: ``audience_grades`` around the educator audience -- see
#: ``adapters/DESIGN.md``'s "Revision (2026-09-02 -- sprint 030
#: educator-PD extraction profile)" section for why an educator-PD page
#: is its own third genre, neither ``"program"`` nor ``"competition"``.
_FIELD_EXTRACTION_RULES_PD = f"""- program_name: the workshop, summit, or conference/chapter meeting's \
name, as titled on the page.
- audience_grades: zero or more educator-audience descriptors actually \
named on the page (e.g. "K-5 teachers", "STEM coordinators", "high \
school science teachers", "district administrators"), as short strings \
in the page's own words -- this is an educator audience, never a \
student grade band.
- date_start: the workshop/session/summit's OWN date, as an ISO date \
(YYYY-MM-DD), or "" if not stated -- the first day of the event if it \
spans multiple days. Look for the date under any of: "Workshop Date," \
"Session Date," "Event Date," "Save the Date," as well as ordinary \
prose. This is NEVER a registration, RSVP, or sign-up deadline -- put \
that in registration_deadline instead, never here.
- date_end: the event's own last day, as an ISO date (YYYY-MM-DD), if it \
spans multiple days, else "". It is NOT a registration, RSVP, or \
sign-up deadline -- put that in registration_deadline instead, never \
here.
- registration_deadline: a registration, RSVP, or sign-up deadline \
(e.g. "Registration closes," "RSVP by") stated separately from the \
event's own date, as an ISO date (YYYY-MM-DD), or "" if none is stated \
or the page states only one date.
- cost: a short description of program cost or stipend/pay (e.g. "Free", \
"Paid stipend", "$500 fee"), or "" if not stated.
- eligibility: a short free-text summary of *educator* eligibility \
requirements (grade band taught, district, subject area, credential), \
or "" if not stated -- this describes the teacher/educator attending, \
never a student.
- is_open: true if open for registration/RSVP; false if closed, full, \
or sold out. Default to true when the page gives no clear signal either \
way.
- opportunity_type: exactly one of {_OPPORTUNITY_TYPE_VALUES}, based on \
what kind of opportunity this is. Use "Professional Development / \
Conferences" as the default whenever nothing more specific clearly \
applies -- this field is never left blank.

Year inference (a narrow, explicit exception to "never guess a date not \
stated," scoped only to a year component): if a date on the page states \
a month and day but no year, infer the soonest year (this one, or next) \
in which that month/day falls on or after the reference date stated \
above ("Page fetched on: <date>") -- never leave the year off, and do \
not default to the current calendar year if that month/day has already \
passed relative to the reference date."""


_SYSTEM_PROMPT_PD = f"""You are helping curate a directory of STEM learning \
opportunities for learners of all ages in the San Diego area. You are \
given the raw text of one curated educator professional-development page \
-- a workshop, summit, or conference/chapter meeting for K-12 educators, \
such as a teacher training day, a STEM educators summit, or a CSTA-SD \
chapter meeting -- scraped from an organization's website. The audience \
of this page is teachers and other educators, not students. Unlike an \
application-window program, this page's primary date is the event's OWN \
date, not an application or registration deadline. Extract the \
following fields, using only what is solidly supported by the page \
text. Never guess a specific date, grade, or amount that is not stated \
or strongly implied, except for the narrow year-inference rule below.

{_FIELD_EXTRACTION_RULES_PD}

Respond only with the structured JSON the response format requires."""


#: (Sprint 030 ticket 004) The ``profile="pd"`` counterpart to
#: :data:`_SYSTEM_PROMPT_MULTI`/:data:`_SYSTEM_PROMPT_COMPETITION_MULTI`
#: -- one page whose body holds N inline educator-PD event records
#: rather than one (e.g. a CSTA-SD chapter's own upcoming-meetings
#: list).
_SYSTEM_PROMPT_PD_MULTI = f"""You are helping curate a directory of STEM learning \
opportunities for learners of all ages in the San Diego area. You are \
given the raw text of one curated page that describes MULTIPLE distinct \
educator professional-development events -- each a workshop, summit, or \
conference/chapter meeting for K-12 educators -- as separate inline \
sections on the same page, rather than links out to separate detail \
pages. The audience of these events is teachers and other educators, \
not students. Identify every distinct event described on the page, and \
for EACH one extract the following fields, using only what is solidly \
supported by that event's own section of the page text. Never guess a \
specific date, grade, or amount that is not stated or strongly implied \
for that event, except for the narrow year-inference rule below, and \
never blend two distinct events' details into one record.

{_FIELD_EXTRACTION_RULES_PD}

If no distinct events are described on the page, return an empty list.

Respond only with the structured JSON the response format requires: a \
single object with one key, "programs", whose value is a list with \
exactly one entry per distinct event found on the page."""


def _build_user_prompt(url: str, body: str, reference_date: date | None = None) -> str:
    """Build the per-call user prompt.

    **(Sprint 029 ticket 006)** ``reference_date``, when given, is
    injected as a "Page fetched on: ``<ISO date>``" line -- used by the
    competition profile's year-inference rule (see
    ``_FIELD_EXTRACTION_RULES_COMPETITION``). Injected into the *user*
    prompt, never the system prompt, since it varies per call rather
    than being static text. ``reference_date=None`` (every pre-revision
    call site) omits the line entirely, so the prompt is byte-identical
    to pre-revision behavior.
    """
    reference_line = f"Page fetched on: {reference_date.isoformat()}\n\n" if reference_date is not None else ""
    return (
        f"Program page URL: {url}\n\n"
        + reference_line
        + "Here is the page's raw text. Extract the fields the response "
        "format requires.\n\n" + body
    )


# --------------------------------------------------------------------
# Response parsing/validation
# --------------------------------------------------------------------


def _expect_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ProgramLLMExtractionError(
            f"Expected {field_name!r} to be a string, got {type(value).__name__}"
        )
    return value


def _expect_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ProgramLLMExtractionError(
            f"Expected {field_name!r} to be a boolean, got {type(value).__name__}"
        )
    return value


def _expect_str_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ProgramLLMExtractionError(f"Expected {field_name!r} to be a list of strings, got {value!r}")
    return value


def _result_from_dict(data: Any) -> ProgramExtractionResult:
    if not isinstance(data, dict):
        raise ProgramLLMExtractionError(f"Expected the response to be a JSON object, got {type(data).__name__}")

    missing = [name for name in PROGRAM_EXTRACTION_JSON_SCHEMA["required"] if name not in data]
    if missing:
        raise ProgramLLMExtractionError(f"Response is missing required field(s): {missing}")

    return ProgramExtractionResult(
        program_name=_expect_str(data["program_name"], "program_name"),
        audience_grades=_expect_str_list(data["audience_grades"], "audience_grades"),
        date_start=_expect_str(data["date_start"], "date_start"),
        date_end=_expect_str(data["date_end"], "date_end"),
        cost=_expect_str(data["cost"], "cost"),
        eligibility=_expect_str(data["eligibility"], "eligibility"),
        is_open=_expect_bool(data["is_open"], "is_open"),
        opportunity_type=_expect_str(data["opportunity_type"], "opportunity_type"),
        registration_deadline=_expect_str(data["registration_deadline"], "registration_deadline"),
    )


def _extract_response_text(response: Any) -> str:
    for block in getattr(response, "content", []):
        if getattr(block, "type", None) == "text":
            return block.text
    raise ProgramLLMExtractionError("Anthropic response contained no text content block")


def _parse_response(response: Any) -> ProgramExtractionResult:
    text = _extract_response_text(response)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProgramLLMExtractionError(f"Anthropic response was not valid JSON: {exc}") from exc
    return _result_from_dict(data)


def _results_from_dict(data: Any) -> list[ProgramExtractionResult]:
    """The list-valued counterpart to :func:`_result_from_dict`, for a
    ``{"programs": [...]}``-shaped response (ticket 006 exception
    revision's ``extract_programs()``).
    """
    if not isinstance(data, dict):
        raise ProgramLLMExtractionError(f"Expected the response to be a JSON object, got {type(data).__name__}")

    if "programs" not in data:
        raise ProgramLLMExtractionError("Response is missing required field(s): ['programs']")

    programs = data["programs"]
    if not isinstance(programs, list):
        raise ProgramLLMExtractionError(
            f"Expected 'programs' to be a list, got {type(programs).__name__}"
        )
    return [_result_from_dict(item) for item in programs]


def _parse_programs_response(response: Any) -> list[ProgramExtractionResult]:
    text = _extract_response_text(response)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProgramLLMExtractionError(f"Anthropic response was not valid JSON: {exc}") from exc
    return _results_from_dict(data)


# --------------------------------------------------------------------
# The real implementation
# --------------------------------------------------------------------


class AnthropicProgramLLMClient:
    """The real ``ProgramLLMClient``: a thin wrapper over the ``anthropic`` SDK.

    Constructs ``anthropic.Anthropic()`` with **no** explicit ``api_key``
    argument -- the SDK resolves ``ANTHROPIC_API_KEY`` itself, matching
    ``enrich/llm_client.py``'s ``AnthropicLLMClient`` exactly. No retry/
    backoff logic here (the ``anthropic`` SDK already retries 429/5xx per
    its own defaults) and no caching (that's ``program_cache.py``'s job).
    Production-only: no test in this codebase constructs or calls this
    class.
    """

    def __init__(self) -> None:
        self._client = anthropic.Anthropic()

    def extract_program(
        self,
        url: str,
        body: str,
        *,
        profile: str = "program",
        reference_date: date | None = None,
    ) -> ProgramExtractionResult:
        if profile == "competition":
            system_prompt = _SYSTEM_PROMPT_COMPETITION
        elif profile == "pd":
            system_prompt = _SYSTEM_PROMPT_PD
        else:
            system_prompt = _SYSTEM_PROMPT
        response = self._client.messages.create(
            model=MODEL_ID,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": _build_user_prompt(url, body, reference_date)}],
            output_config={
                "format": {"type": "json_schema", "schema": PROGRAM_EXTRACTION_JSON_SCHEMA}
            },
        )
        return _parse_response(response)

    def extract_programs(
        self,
        url: str,
        body: str,
        *,
        profile: str = "program",
        reference_date: date | None = None,
    ) -> list[ProgramExtractionResult]:
        """(Ticket 006 exception revision) One call, N results -- for a
        page whose body holds N inline program records (SIO's shape).
        ``max_tokens`` is raised over :meth:`extract_program`'s to make
        room for a list-valued response of unknown-but-bounded length.

        **(Sprint 029 ticket 006, Sprint 030 ticket 004)**
        ``profile``/``reference_date`` -- see :meth:`extract_program`.
        """
        if profile == "competition":
            system_prompt = _SYSTEM_PROMPT_COMPETITION_MULTI
        elif profile == "pd":
            system_prompt = _SYSTEM_PROMPT_PD_MULTI
        else:
            system_prompt = _SYSTEM_PROMPT_MULTI
        response = self._client.messages.create(
            model=MODEL_ID,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": _build_user_prompt(url, body, reference_date)}],
            output_config={
                "format": {"type": "json_schema", "schema": PROGRAM_LIST_EXTRACTION_JSON_SCHEMA}
            },
        )
        return _parse_programs_response(response)


# --------------------------------------------------------------------
# Test double
# --------------------------------------------------------------------


@dataclass
class FixtureProgramLLMClient:
    """``ProgramLLMClient`` test double: returns canned
    ``ProgramExtractionResult``s (single or list-valued).

    Never opens a socket or imports ``anthropic``. ``responses`` (for
    :meth:`extract_program`) and ``list_responses`` (for
    :meth:`extract_programs`, ticket 006 exception revision) are each
    looked up by the identical ``key_fn(url, body)`` (default: the URL
    alone) -- the same lookup mechanism extended to a second canned-value
    dict rather than a second test-double class. Every ``(url, body)``
    pair passed to :meth:`extract_program`/:meth:`extract_programs` is
    recorded in ``calls``/``list_calls`` respectively, in order, so tests
    can assert on how many times -- and with what -- this client was
    invoked (e.g. a cache-hit test proving a second run makes no further
    call).

    Raises:
        KeyError: if neither ``(key_fn(url, body), profile)`` nor plain
            ``key_fn(url, body)`` is present in the relevant responses
            dict -- a loud failure if the code under test asks this
            double to extract a page it wasn't told to expect.

    **(Sprint 029 ticket 006)** :meth:`extract_program`/
    :meth:`extract_programs` accept the same ``profile``/
    ``reference_date`` keyword-only parameters as the real
    ``ProgramLLMClient`` Protocol. By default they are ignored: canned
    responses never depend on them, so no pre-existing fixture-test call
    site needs to change, and ``calls``/``list_calls`` keep recording
    only ``(url, body)`` exactly as before.

    **(Sprint 030 ticket 004)** A test that *does* want a distinct
    canned result per ``profile`` for the same ``(url, body)`` -- e.g.
    proving a ``profile="pd"`` call never returns the ``"program"``- or
    ``"competition"``-profile fixture registered for the same URL --
    registers it under the tuple key ``(key_fn(url, body), profile)``
    instead of the plain ``key_fn(url, body)`` key. Lookup tries the
    profile-qualified key first and falls back to the plain key, so
    every existing registration (all keyed plainly, with no matching
    profile-qualified entry) is unaffected -- this is a strictly
    additive lookup, not a second test-double class or a change to
    ``key_fn``'s own two-argument signature.
    """

    responses: dict[Any, ProgramExtractionResult] = field(default_factory=dict)
    list_responses: dict[Any, list[ProgramExtractionResult]] = field(default_factory=dict)
    key_fn: Callable[[str, str], Any] = lambda url, body: url
    calls: list[tuple[str, str]] = field(default_factory=list)
    list_calls: list[tuple[str, str]] = field(default_factory=list)

    def extract_program(
        self,
        url: str,
        body: str,
        *,
        profile: str = "program",
        reference_date: date | None = None,
    ) -> ProgramExtractionResult:
        self.calls.append((url, body))
        key = self.key_fn(url, body)
        profiled_key = (key, profile)
        if profiled_key in self.responses:
            return self.responses[profiled_key]
        return self.responses[key]

    def extract_programs(
        self,
        url: str,
        body: str,
        *,
        profile: str = "program",
        reference_date: date | None = None,
    ) -> list[ProgramExtractionResult]:
        self.list_calls.append((url, body))
        key = self.key_fn(url, body)
        profiled_key = (key, profile)
        if profiled_key in self.list_responses:
            return self.list_responses[profiled_key]
        return self.list_responses[key]
