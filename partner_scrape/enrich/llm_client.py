"""The ``LLMClient`` protocol, ``EnrichmentResult``, and its one real
implementation, ``AnthropicLLMClient``.

See sprint.md's Architecture > LLM Client: the injectable interface to
one LLM enrichment call, paired with its real implementation in the
same module -- exactly the pattern ``fetch/fetcher.py`` already
established for ``Fetcher``/``UrllibFetcher`` in sprint 001. Every other
module that needs LLM enrichment (ticket 005's ``LLMEnricher``) depends
on ``LLMClient``, never on the ``anthropic`` SDK directly.

Dependency direction (sprint.md's Component & Dependency Diagram):
``LLM Client`` is a leaf/infrastructure module depending on nothing in
this package except Event Model -- it deliberately does not import
``normalize/taxonomy.py`` even though the controlled vocabularies below
overlap with it; duplication here is the accepted cost of keeping this
module's one outward dependency the external Anthropic API, not another
in-package module.

``AnthropicLLMClient`` constructs ``anthropic.Anthropic()`` with **no**
explicit ``api_key`` -- the SDK resolves ``ANTHROPIC_API_KEY`` (or
another configured credential) itself. This is deliberately not a
``config.py`` accessor; see sprint.md's Impact on Existing Components
for why that is not a boundary violation.
"""

from __future__ import annotations

import dataclasses
import json
import types
import typing
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Protocol

import anthropic

from partner_scrape.model import Event

#: Single named model-ID constant. Every real request uses this constant
#: -- never inlined at more than one call site -- so changing tiers is a
#: one-line change. Haiku is the default because enrichment is a
#: high-volume, per-event date-extraction + controlled-vocabulary
#: classification task run across the whole corpus on every scheduled
#: refresh; Haiku 4.5 handles it well at ~1/10th the cost of Opus, which
#: keeps a "refresh thousands of events weekly" pipeline affordable.
#: Bump to "claude-opus-4-8" only if classification quality proves
#: insufficient in practice.
MODEL_ID = "claude-haiku-4-5-20251001"

#: Controlled vocabularies mirrored (not imported, see module docstring)
#: from ``normalize/taxonomy.py``'s ``AREA_KEYWORDS``/``AGE_KEYWORDS``
#: labels plus ``map_cost``/``derive_time_of_day``'s output values --
#: given to the model as prompt guidance so its classification lines up
#: with the site's existing taxonomy.
_AREA_OF_INTEREST_VALUES = [
    "Biology / LifeSciences",
    "Earth Science/Ecology",
    "Coding/Computer Science/Cyber Security",
    "Engineering",
    "Physical Science",
    "Mathematics",
    "Chemistry",
    "Physics",
    "General Science",
]
_AGE_GRADE_LEVEL_VALUES = ["Family", "Pre-K", "Grades 9-12", "Grades 6-8", "Adult"]
_COST_RANGE_VALUES = [
    "Free",
    "Less than $25",
    "Less than $50",
    "Less than $100",
    "Less than $200",
    "Greater than $200",
]
_TIME_OF_DAY_VALUES = ["Morning", "Afternoon", "Evening", "All Day"]


@dataclass
class EnrichmentResult:
    """One LLM enrichment call's structured output for one Event.

    Every field mirrors a same-named field on :class:`~partner_scrape.model.Event`
    so ticket 005's ``LLMEnricher`` can apply results via ``Event.set(...)``
    with no translation layer. The recovered fields (``start`` through
    ``registration_url``) are ``Optional``: ``None`` means "the LLM did
    not recover this field" -- distinct from an Event's own ``""``/``[]``
    "unset" defaults, so the Enricher can tell "recovered but genuinely
    empty" apart from "not attempted". Classification and the relevance
    verdict are always produced -- that is this call's whole purpose.
    """

    # Recovered fields -- None means "LLM did not recover this field".
    start: datetime | None = None
    end: datetime | None = None
    all_day: bool | None = None
    location: str | None = None
    cost: str | None = None
    registration_url: str | None = None

    # Controlled-vocabulary classification -- always produced.
    areas_of_interest: list[str] = field(default_factory=list)
    age_grade_level: list[str] = field(default_factory=list)
    cost_range: str = ""
    time_of_day: list[str] = field(default_factory=list)

    # Relevance verdict (SUC-011/SUC-012's gate) -- always produced.
    relevant: bool = True
    relevance_reason: str = ""


class LLMClient(Protocol):
    """Injectable seam for one LLM enrichment call over one Event.

    Mirrors ``fetch/fetcher.py``'s ``Fetcher`` protocol pattern.
    Implementations receive the Event's currently-known fields (title,
    description, whatever date/location/cost is already present) and
    return a structured :class:`EnrichmentResult` -- never a raw string,
    never a partially-parsed dict.
    """

    def enrich_event(self, event: Event) -> EnrichmentResult:
        """Return one LLM enrichment result for ``event``."""
        ...


class LLMEnrichmentError(Exception):
    """Raised when an LLM response cannot be parsed into an EnrichmentResult.

    Covers malformed JSON, a missing text content block, and any field
    of the wrong shape/type -- every case where returning a
    partially-populated ``EnrichmentResult`` would be a silently wrong
    result rather than a caught failure. Ticket 005's ``LLMEnricher``
    fail-open path catches this specifically (not a bare ``Exception``)
    so it can distinguish "the model/API misbehaved" from an unrelated
    programming error.
    """


# --------------------------------------------------------------------
# Structured-output JSON schema, built directly from EnrichmentResult's
# shape (via dataclass field introspection) so the schema and the
# dataclass cannot drift silently -- sprint.md's Implementation Plan
# Approach.
# --------------------------------------------------------------------


def _field_json_schema(annotation: Any) -> dict[str, Any]:
    """Return the JSON schema fragment for one resolved type annotation."""
    origin = typing.get_origin(annotation)

    if origin is types.UnionType or origin is typing.Union:
        args = typing.get_args(annotation)
        nullable = type(None) in args
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) != 1:
            raise TypeError(f"Unsupported union in EnrichmentResult schema: {annotation!r}")
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
    if annotation is datetime:
        return {"type": "string", "format": "date-time"}

    raise TypeError(f"Unsupported field type for EnrichmentResult schema: {annotation!r}")


def _build_enrichment_json_schema() -> dict[str, Any]:
    hints = typing.get_type_hints(EnrichmentResult)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for f in dataclasses.fields(EnrichmentResult):
        properties[f.name] = _field_json_schema(hints[f.name])
        required.append(f.name)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


#: The structured-output schema sent on every real request -- see
#: :func:`_build_enrichment_json_schema`.
ENRICHMENT_JSON_SCHEMA = _build_enrichment_json_schema()


_SYSTEM_PROMPT = f"""You are helping curate a directory of STEM learning \
opportunities for K-12 youth in the San Diego area. You are given one \
event/program record scraped from a partner organization's website, as \
JSON. Do two things:

1. Recover any of these fields that are missing (null): start date/time, \
end date/time, whether the event is all-day, location, cost, \
registration URL. Only fill in a value that is solidly supported by the \
title/description text -- never guess a specific date, time, or amount \
that is not stated or strongly implied. Leave a field null if it cannot \
be recovered. Never overwrite a field that already has a value.
2. Classify the record and decide whether it belongs on the site:
   - areas_of_interest: zero or more of {_AREA_OF_INTEREST_VALUES}
   - age_grade_level: zero or more of {_AGE_GRADE_LEVEL_VALUES}
   - cost_range: exactly one of {_COST_RANGE_VALUES}, or "" if unknown
   - time_of_day: zero or more of {_TIME_OF_DAY_VALUES}
   - relevant: true if this is a STEM learning opportunity for youth \
(not an adult-only program, not unrelated announcement/noise), else \
false
   - relevance_reason: one short sentence explaining the relevant \
verdict

Respond only with the structured JSON the response format requires."""


def _build_user_prompt(event: Event) -> str:
    known = {
        "title": event.title,
        "description": event.description,
        "start": event.start.isoformat() if event.start is not None else None,
        "end": event.end.isoformat() if event.end is not None else None,
        "all_day": event.all_day,
        "location": event.location or None,
        "cost": event.cost or None,
        "registration_url": event.registration_url or None,
        "categories": event.categories,
        "tags": event.tags,
    }
    return (
        "Here is one scraped record. A null field is missing and should "
        "be recovered if possible.\n\n" + json.dumps(known, indent=2, default=str)
    )


# --------------------------------------------------------------------
# Response parsing/validation
# --------------------------------------------------------------------


def _expect_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise LLMEnrichmentError(f"Expected {field_name!r} to be a string, got {type(value).__name__}")
    return value


def _expect_optional_str(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _expect_str(value, field_name)


def _expect_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise LLMEnrichmentError(f"Expected {field_name!r} to be a boolean, got {type(value).__name__}")
    return value


def _expect_optional_bool(value: Any, field_name: str) -> bool | None:
    if value is None:
        return None
    return _expect_bool(value, field_name)


def _expect_str_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise LLMEnrichmentError(f"Expected {field_name!r} to be a list of strings, got {value!r}")
    return value


def _expect_optional_datetime(value: Any, field_name: str) -> datetime | None:
    if value is None:
        return None
    text = _expect_str(value, field_name)
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise LLMEnrichmentError(f"Could not parse {field_name!r} as an ISO-8601 date: {text!r}") from exc


def _result_from_dict(data: Any) -> EnrichmentResult:
    if not isinstance(data, dict):
        raise LLMEnrichmentError(f"Expected the response to be a JSON object, got {type(data).__name__}")

    missing = [name for name in ENRICHMENT_JSON_SCHEMA["required"] if name not in data]
    if missing:
        raise LLMEnrichmentError(f"Response is missing required field(s): {missing}")

    return EnrichmentResult(
        start=_expect_optional_datetime(data["start"], "start"),
        end=_expect_optional_datetime(data["end"], "end"),
        all_day=_expect_optional_bool(data["all_day"], "all_day"),
        location=_expect_optional_str(data["location"], "location"),
        cost=_expect_optional_str(data["cost"], "cost"),
        registration_url=_expect_optional_str(data["registration_url"], "registration_url"),
        areas_of_interest=_expect_str_list(data["areas_of_interest"], "areas_of_interest"),
        age_grade_level=_expect_str_list(data["age_grade_level"], "age_grade_level"),
        cost_range=_expect_str(data["cost_range"], "cost_range"),
        time_of_day=_expect_str_list(data["time_of_day"], "time_of_day"),
        relevant=_expect_bool(data["relevant"], "relevant"),
        relevance_reason=_expect_str(data["relevance_reason"], "relevance_reason"),
    )


def _extract_response_text(response: Any) -> str:
    for block in getattr(response, "content", []):
        if getattr(block, "type", None) == "text":
            return block.text
    raise LLMEnrichmentError("Anthropic response contained no text content block")


def _parse_response(response: Any) -> EnrichmentResult:
    text = _extract_response_text(response)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMEnrichmentError(f"Anthropic response was not valid JSON: {exc}") from exc
    return _result_from_dict(data)


# --------------------------------------------------------------------
# The real implementation
# --------------------------------------------------------------------


class AnthropicLLMClient:
    """The real ``LLMClient``: a thin wrapper over the ``anthropic`` SDK.

    Constructs ``anthropic.Anthropic()`` with **no** explicit
    ``api_key`` argument -- the SDK resolves ``ANTHROPIC_API_KEY`` (or
    another configured credential) itself. No retry/backoff logic here
    (the ``anthropic`` SDK already retries 429/5xx per its own
    defaults) and no caching (that's ticket 005's Enrichment Cache, a
    different module with a different reason to change). This is "the
    one thin, mockable place" the sprint brief requires: a single
    stateless call-and-parse boundary.
    """

    def __init__(self) -> None:
        self._client = anthropic.Anthropic()

    def enrich_event(self, event: Event) -> EnrichmentResult:
        response = self._client.messages.create(
            model=MODEL_ID,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_prompt(event)}],
            output_config={
                "format": {"type": "json_schema", "schema": ENRICHMENT_JSON_SCHEMA}
            },
        )
        return _parse_response(response)


# --------------------------------------------------------------------
# Test double
# --------------------------------------------------------------------


@dataclass
class FixtureLLMClient:
    """``LLMClient`` test double: returns canned ``EnrichmentResult``s.

    Never opens a socket or imports ``anthropic``. ``responses`` is
    looked up by ``key_fn(event)`` (default: the Event's ``title``) --
    pass ``key_fn=lambda event: event.identity_key()`` to key by
    acquisition identity instead. Every Event passed to
    :meth:`enrich_event` is recorded in ``calls``, in order, so tests
    (e.g. ticket 005's cache-skip call-counting assertions) can assert
    on how many times -- and with what -- this client was invoked.

    Raises:
        KeyError: if ``key_fn(event)`` is absent from ``responses`` --
            a loud failure if the Enricher under test asks this double
            to enrich an Event it wasn't told to expect.
    """

    responses: dict[Any, EnrichmentResult]
    key_fn: Callable[[Event], Any] = lambda event: event.title
    calls: list[Event] = field(default_factory=list)

    def enrich_event(self, event: Event) -> EnrichmentResult:
        self.calls.append(event)
        return self.responses[self.key_fn(event)]
