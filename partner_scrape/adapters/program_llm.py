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
"""

from __future__ import annotations

import dataclasses
import json
import types
import typing
from dataclasses import dataclass, field
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


class ProgramLLMClient(Protocol):
    """Injectable seam for one LLM extraction call over one program page.

    Mirrors ``enrich/llm_client.py``'s ``LLMClient`` protocol pattern.
    Implementations receive a URL (for context/logging) and the fetched
    page's raw body text, and return a structured
    :class:`ProgramExtractionResult` -- never a raw string, never a
    partially-parsed dict.
    """

    def extract_program(self, url: str, body: str) -> ProgramExtractionResult:
        """Return one LLM extraction result for the page at ``url``."""
        ...

    def extract_programs(self, url: str, body: str) -> list[ProgramExtractionResult]:
        """Return one LLM extraction result *per inline program record*
        found on the page at ``url``.

        **(Ticket 006 exception revision)** For a page whose body holds N
        distinct program sections (SIO's shape -- see
        ``adapters/DESIGN.md``'s Revision note), rather than the single
        record :meth:`extract_program` recovers for a page dedicated to
        one program.
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
field is never left blank."""


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


def _build_user_prompt(url: str, body: str) -> str:
    return (
        f"Program page URL: {url}\n\n"
        "Here is the page's raw text. Extract the fields the response "
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

    def extract_program(self, url: str, body: str) -> ProgramExtractionResult:
        response = self._client.messages.create(
            model=MODEL_ID,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_prompt(url, body)}],
            output_config={
                "format": {"type": "json_schema", "schema": PROGRAM_EXTRACTION_JSON_SCHEMA}
            },
        )
        return _parse_response(response)

    def extract_programs(self, url: str, body: str) -> list[ProgramExtractionResult]:
        """(Ticket 006 exception revision) One call, N results -- for a
        page whose body holds N inline program records (SIO's shape).
        ``max_tokens`` is raised over :meth:`extract_program`'s to make
        room for a list-valued response of unknown-but-bounded length.
        """
        response = self._client.messages.create(
            model=MODEL_ID,
            max_tokens=4096,
            system=_SYSTEM_PROMPT_MULTI,
            messages=[{"role": "user", "content": _build_user_prompt(url, body)}],
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
        KeyError: if ``key_fn(url, body)`` is absent from the relevant
            responses dict -- a loud failure if the code under test asks
            this double to extract a page it wasn't told to expect.
    """

    responses: dict[Any, ProgramExtractionResult] = field(default_factory=dict)
    list_responses: dict[Any, list[ProgramExtractionResult]] = field(default_factory=dict)
    key_fn: Callable[[str, str], Any] = lambda url, body: url
    calls: list[tuple[str, str]] = field(default_factory=list)
    list_calls: list[tuple[str, str]] = field(default_factory=list)

    def extract_program(self, url: str, body: str) -> ProgramExtractionResult:
        self.calls.append((url, body))
        return self.responses[self.key_fn(url, body)]

    def extract_programs(self, url: str, body: str) -> list[ProgramExtractionResult]:
        self.list_calls.append((url, body))
        return self.list_responses[self.key_fn(url, body)]
