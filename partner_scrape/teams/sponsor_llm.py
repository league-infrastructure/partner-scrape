"""The ``SponsorLLMClient`` protocol, ``SponsorExtractionResult``, and its
real and fixture implementations.

Sprint 013 ticket 004: the injectable LLM-classification infrastructure
ticket 005's orchestration (``sponsor_extract.py``) calls -- no
orchestration logic here, only the client protocol and its two
implementations. Issue 21 names false positives as the dominant risk: an
LLM asked "what are this page's sponsors?" over open text will
confidently return the CMS vendor, the hosting provider, the school
district, or the site's own domain. The mitigation is architectural, not
just prompt wording: **this client's contract is classification of a
given candidate list, never open-ended generation.**
:func:`~partner_scrape.teams.sponsor_candidates.gather_sponsor_candidates`
(ticket 003) is the only source of the ``candidates`` this call ever
sees; ticket 005 then rejects, in code, any name this call returns that
is not present verbatim in that candidate list. See ``sprint.md``'s
Design Rationale ("the LLM's role is constrained classification over
deterministically-gathered candidates, never open-ended generation") for
the full reasoning.

Deliberately mirrors, but never imports, ``enrich/llm_client.py``'s
``LLMClient``/``EnrichmentResult``/``AnthropicLLMClient``/
``FixtureLLMClient`` shape (same JSON-schema-from-dataclass generation
pattern, same "no explicit api_key" SDK construction, same strict
response-parsing helpers). ``teams/`` has a standing, explicitly
documented invariant of zero edges into ``enrich/``, ``adapters/``,
``normalize.run()``, or ``pipeline.run()`` (``teams/DESIGN.md``'s
Purpose/Constraints sections; ``tests/teams/test_sources_base.py``'s
forbidden-import precedent for ``adapters.base`` is the same spirit) --
importing ``enrich.llm_client``, even for one small helper, would be the
first crack in that boundary. Duplicating a ~15-line schema-builder
helper is the accepted cost (``sprint.md``'s Design Rationale).

``AnthropicSponsorLLMClient`` constructs ``anthropic.Anthropic()`` with
**no** explicit ``api_key`` -- the SDK resolves ``ANTHROPIC_API_KEY``
itself. This is deliberately not a ``config.py`` accessor, exactly
matching ``enrich.llm_client.AnthropicLLMClient``'s own documented
reason for the same choice.
"""

from __future__ import annotations

import dataclasses
import json
import typing
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

import anthropic

#: Single named model-ID constant, redefined locally (same value as
#: ``enrich.llm_client.MODEL_ID``, not imported -- see module
#: docstring). Haiku is the default: sponsor classification is a
#: high-volume, per-team-page selection task over a short candidate
#: list, run across the whole team corpus -- the same cost/quality
#: tradeoff ``enrich.llm_client.MODEL_ID``'s own comment documents.
MODEL_ID = "claude-haiku-4-5-20251001"

#: Common CMS/website-hosting/site-builder vendor names -- named
#: explicitly in the system prompt (below) so the model excludes them
#: even though ``sponsor_candidates.py`` already denylists most of them
#: deterministically; naming them again here is defense-in-depth for any
#: vendor name that survives to the candidate list in some other form
#: (e.g. an unusual capitalization the deterministic denylist's
#: casefolded match still catches, but a *prompt-only* second layer over
#: the LLM boundary costs nothing to add).
_CMS_HOSTING_VENDOR_NAMES = (
    "Wix",
    "Squarespace",
    "WordPress",
    "GoDaddy",
    "Weebly",
    "Google Sites",
    "Canva",
    "Blogspot",
    "Hostinger",
)

#: The FIRST robotics program itself and its aggregators -- never a
#: sponsor, always the program the team competes in or a site that
#: tracks it.
_PROGRAM_AND_AGGREGATOR_NAMES = (
    "FIRST",
    "FIRST Inspires",
    "FIRST Robotics Competition",
    "FIRST Tech Challenge",
    "FIRST LEGO League",
    "FTC",
    "FRC",
    "FLL",
    "The Blue Alliance",
    "FTCScout",
    "RobotEvents",
)


@dataclass
class SponsorExtractionResult:
    """One LLM classification call's structured output.

    ``confirmed_sponsors`` is the subset of the *given* candidate list
    the model judged to be genuine third-party sponsor organizations --
    never a name outside that list. Ticket 005's orchestration is the
    layer that actually enforces that in code (validating every returned
    name against the original candidate list verbatim); this dataclass
    is just the call's raw structured result.
    """

    confirmed_sponsors: list[str] = field(default_factory=list)


class SponsorLLMClient(Protocol):
    """Injectable seam for one LLM sponsor-classification call.

    Mirrors ``enrich/llm_client.py``'s ``LLMClient`` protocol pattern,
    parallel in shape but with no import relationship to it (module
    docstring). Implementations receive a bounded candidate list (see
    :func:`~partner_scrape.teams.sponsor_candidates.gather_sponsor_candidates`)
    and a ``context`` dict carrying at least ``"organization"`` (the
    team's own organization/school name) and ``"hostname"`` (the page's
    own hostname) -- both used to name explicit exclusions in the
    prompt -- and return a structured :class:`SponsorExtractionResult`,
    never a raw string, never a partially-parsed dict.
    """

    def classify_sponsors(self, candidates: list[str], context: dict[str, Any]) -> SponsorExtractionResult:
        """Return which of ``candidates`` are genuine sponsor names.

        ``context`` carries page/team framing the prompt uses to name
        explicit exclusions -- expected keys are ``"organization"`` (the
        team's own organization/school name) and ``"hostname"`` (the
        page's own hostname), either of which may be absent or empty.
        """
        ...


class SponsorClassificationError(Exception):
    """Raised when an LLM response cannot be parsed into a
    SponsorExtractionResult.

    Covers malformed JSON, a missing text content block, and any field
    of the wrong shape/type -- every case where returning a
    partially-populated ``SponsorExtractionResult`` would be a silently
    wrong result rather than a caught failure. Ticket 005's
    ``extract_sponsors()`` fail-open path (SUC-004's Error Flows) catches
    this specifically, not a bare ``Exception``, so it can distinguish
    "the model/API misbehaved" from an unrelated programming error.
    """


# --------------------------------------------------------------------
# Structured-output JSON schema, built directly from
# SponsorExtractionResult's shape (via dataclass field introspection) so
# the schema and the dataclass cannot drift silently -- duplicating, not
# importing, enrich/llm_client.py's _build_enrichment_json_schema
# pattern (module docstring).
# --------------------------------------------------------------------


def _field_json_schema(annotation: Any) -> dict[str, Any]:
    """Return the JSON schema fragment for one resolved type annotation."""
    origin = typing.get_origin(annotation)

    if origin is list:
        (item_type,) = typing.get_args(annotation)
        return {"type": "array", "items": _field_json_schema(item_type)}

    if annotation is str:
        return {"type": "string"}
    if annotation is bool:
        return {"type": "boolean"}

    raise TypeError(f"Unsupported field type for SponsorExtractionResult schema: {annotation!r}")


def _build_sponsor_extraction_json_schema() -> dict[str, Any]:
    hints = typing.get_type_hints(SponsorExtractionResult)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for f in dataclasses.fields(SponsorExtractionResult):
        properties[f.name] = _field_json_schema(hints[f.name])
        required.append(f.name)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


#: The structured-output schema sent on every real request -- see
#: :func:`_build_sponsor_extraction_json_schema`.
SPONSOR_EXTRACTION_JSON_SCHEMA = _build_sponsor_extraction_json_schema()


def _build_system_prompt(context: dict[str, Any]) -> str:
    """Build this call's system prompt, naming ``context``'s
    organization/hostname explicitly in the exclusion list (SUC-004's
    Main Flow; this ticket's acceptance criteria).

    Rebuilt per call (unlike ``enrich/llm_client.py``'s static
    module-level ``_SYSTEM_PROMPT``) because the exclusions this prompt
    must name -- the team's own organization name and its own website
    hostname -- are per-team, not fixed vocabulary.
    """
    organization = str(context.get("organization") or "").strip()
    hostname = str(context.get("hostname") or "").strip()

    exclusions = []
    if organization:
        exclusions.append(f'this team\'s own organization/school name, "{organization}"')
    if hostname:
        exclusions.append(f'this team\'s own website hostname, "{hostname}"')
    exclusions.append(
        "the FIRST robotics program itself and its aggregators (e.g. "
        + ", ".join(_PROGRAM_AND_AGGREGATOR_NAMES)
        + ")"
    )
    exclusions.append(
        "common CMS/website-hosting/site-builder vendor names (e.g. "
        + ", ".join(_CMS_HOSTING_VENDOR_NAMES)
        + ")"
    )
    exclusions.append("social media platforms, navigation labels, and other non-company boilerplate")

    exclusion_lines = "\n".join(f"- {item}" for item in exclusions)

    return f"""You are helping curate sponsor listings for a directory of San Diego \
County FIRST robotics teams (FTC/FRC/FLL). You are given a bounded list of candidate \
strings gathered deterministically from one team's website -- text and hostnames pulled \
from footer logo walls and "Sponsors"/"Our Partners" sections.

Your only job is to SELECT the subset of candidates that are genuine third-party \
organizations sponsoring this team. Never invent, expand, correct, or rephrase a name: \
every name you return must be copied verbatim, character-for-character, from the \
candidate list you are given in the next message. A name that is not an exact match to \
one of the given candidates is a mistake, not a helpful correction.

Exclude from your selection, even if present in the candidate list:
{exclusion_lines}

If nothing in the candidate list is a genuine sponsor, return an empty list -- an empty \
result is correct and expected for many pages; do not select a candidate you are unsure \
about just to avoid an empty answer. Respond only with the structured JSON the response \
format requires."""


def _build_user_prompt(candidates: list[str]) -> str:
    return (
        "Here is the bounded candidate list gathered from this team's page. Select only "
        "the candidates that are genuine third-party sponsor organizations -- copy each "
        "selected name exactly as it appears below:\n\n" + json.dumps({"candidates": candidates}, indent=2)
    )


# --------------------------------------------------------------------
# Response parsing/validation
# --------------------------------------------------------------------


def _expect_str_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise SponsorClassificationError(f"Expected {field_name!r} to be a list of strings, got {value!r}")
    return value


def _result_from_dict(data: Any) -> SponsorExtractionResult:
    if not isinstance(data, dict):
        raise SponsorClassificationError(f"Expected the response to be a JSON object, got {type(data).__name__}")

    missing = [name for name in SPONSOR_EXTRACTION_JSON_SCHEMA["required"] if name not in data]
    if missing:
        raise SponsorClassificationError(f"Response is missing required field(s): {missing}")

    return SponsorExtractionResult(
        confirmed_sponsors=_expect_str_list(data["confirmed_sponsors"], "confirmed_sponsors"),
    )


def _extract_response_text(response: Any) -> str:
    for block in getattr(response, "content", []):
        if getattr(block, "type", None) == "text":
            return block.text
    raise SponsorClassificationError("Anthropic response contained no text content block")


def _parse_response(response: Any) -> SponsorExtractionResult:
    text = _extract_response_text(response)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SponsorClassificationError(f"Anthropic response was not valid JSON: {exc}") from exc
    return _result_from_dict(data)


# --------------------------------------------------------------------
# The real implementation
# --------------------------------------------------------------------


class AnthropicSponsorLLMClient:
    """The real ``SponsorLLMClient``: a thin wrapper over the
    ``anthropic`` SDK.

    Constructs ``anthropic.Anthropic()`` with **no** explicit
    ``api_key`` argument -- the SDK resolves ``ANTHROPIC_API_KEY`` (or
    another configured credential) itself; a missing/invalid key
    surfaces as an ``anthropic`` SDK exception at
    :meth:`classify_sponsors`'s own call site, caught by ticket 005's
    per-team fail-open guard (SUC-004's Error Flows), never aborting a
    ``teams`` run. No retry/backoff logic here (the ``anthropic`` SDK
    already retries 429/5xx per its own defaults) and no caching
    (that's :class:`~partner_scrape.teams.sponsor_cache.SponsorCache`, a
    different module with a different reason to change).
    """

    def __init__(self) -> None:
        self._client = anthropic.Anthropic()

    def classify_sponsors(self, candidates: list[str], context: dict[str, Any]) -> SponsorExtractionResult:
        response = self._client.messages.create(
            model=MODEL_ID,
            max_tokens=1024,
            system=_build_system_prompt(context),
            messages=[{"role": "user", "content": _build_user_prompt(candidates)}],
            output_config={"format": {"type": "json_schema", "schema": SPONSOR_EXTRACTION_JSON_SCHEMA}},
        )
        return _parse_response(response)


# --------------------------------------------------------------------
# Test double
# --------------------------------------------------------------------


@dataclass
class FixtureSponsorLLMClient:
    """``SponsorLLMClient`` test double: returns canned
    ``SponsorExtractionResult``s.

    Never opens a socket or imports ``anthropic``. ``responses`` is
    looked up by ``key_fn(candidates, context)`` -- default: a
    ``tuple(candidates)``, since the candidate list is this call's
    primary variable input (mirroring ``enrich.llm_client.
    FixtureLLMClient``'s default of keying by the input's own natural
    identity). Pass e.g. ``key_fn=lambda candidates, context:
    context["team_id"]`` to key by team identity instead. Every
    ``(candidates, context)`` pair passed to :meth:`classify_sponsors` is
    recorded in ``calls``, in order, so tests (e.g. ticket 005's
    cache-skip call-counting assertions) can assert on how many times --
    and with what -- this client was invoked.

    Raises:
        KeyError: if ``key_fn(candidates, context)`` is absent from
            ``responses`` -- a loud failure if the code under test asks
            this double to classify a candidate list it wasn't told to
            expect.
    """

    responses: dict[Any, SponsorExtractionResult]
    key_fn: Callable[[list[str], dict[str, Any]], Any] = lambda candidates, context: tuple(candidates)
    calls: list[tuple[list[str], dict[str, Any]]] = field(default_factory=list)

    def classify_sponsors(self, candidates: list[str], context: dict[str, Any]) -> SponsorExtractionResult:
        self.calls.append((candidates, context))
        return self.responses[self.key_fn(candidates, context)]
