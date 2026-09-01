"""The ``DescriptionLLMClient`` protocol, ``DescriptionExtractionResult``,
and its real and fixture implementations.

Sprint 021 ticket 003: the injectable LLM-summarization infrastructure
ticket 004's orchestration (``description_extract.py``) calls -- no
orchestration logic here, only the client protocol and its two
implementations. **This client's contract is summarization of given
text, never open-ended generation.**
:func:`~partner_scrape.teams.description_candidates.gather_description_content`
(ticket 002) is the only source of the ``content`` this call ever sees --
a short, bounded string already reduced from one team's fetched
homepage (meta description, title, heading/body text), never the raw
page or its HTML. See ``sprint.md``'s Design Rationale ("the LLM's role
is constrained summarization of deterministically-gathered, bounded
text, never open-ended generation from raw HTML or open context") for
the full reasoning -- the same shape ``sponsor_llm.py`` already
established for sponsor *classification*, applied here to
*summarization* instead.

Deliberately mirrors, but never imports, ``teams/sponsor_llm.py``'s
``SponsorLLMClient``/``SponsorExtractionResult``/
``AnthropicSponsorLLMClient``/``FixtureSponsorLLMClient`` shape (same
JSON-schema-from-dataclass generation pattern, same "no explicit
api_key" SDK construction, same strict response-parsing helpers) --
which itself mirrors, and never imports, ``enrich/llm_client.py`` for
the identical reason. This is now the second mirror-of-a-mirror in this
subsystem: ``teams/`` has a standing, explicitly documented invariant of
zero edges into ``enrich/``, ``adapters/``, ``normalize.run()``, or
``pipeline.run()`` (``teams/DESIGN.md``'s Purpose/Constraints sections)
-- importing ``sponsor_llm.py``, even for one small helper, would be the
first crack in that boundary for this concern. Duplicating a ~15-line
schema-builder helper is the accepted cost (``sprint.md``'s Design
Rationale), matching ``sponsor_llm.py``'s own stated tradeoff against
``enrich/`` almost verbatim.

Unlike ``sponsor_llm.py``'s ``_build_system_prompt()``, this module's
system prompt is a static module-level constant, not rebuilt per call:
sponsor classification must name each team's own organization/hostname
as per-call exclusions, but description summarization has no
per-team-varying instruction to inject -- "summarize only the given
text" holds identically for every call. This matches
``enrich/llm_client.py``'s own static ``_SYSTEM_PROMPT`` convention
(mirrored, not imported, same reasoning as above).

``AnthropicDescriptionLLMClient`` constructs ``anthropic.Anthropic()``
with **no** explicit ``api_key`` -- the SDK resolves
``ANTHROPIC_API_KEY`` itself. This is deliberately not a ``config.py``
accessor, exactly matching ``sponsor_llm.AnthropicSponsorLLMClient``'s
(and, before it, ``enrich.llm_client.AnthropicLLMClient``'s) own
documented reason for the same choice.
"""

from __future__ import annotations

import dataclasses
import json
import typing
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

import anthropic

#: Single named model-ID constant, redefined locally (same value as
#: ``sponsor_llm.MODEL_ID``, not imported -- see module docstring).
#: Haiku is the default: description summarization is a high-volume,
#: per-team-page task over a short, already-bounded content string, run
#: across the whole team corpus -- the identical cost/quality tradeoff
#: ``sponsor_llm.MODEL_ID``'s own comment documents, applied here to
#: summarization instead of classification.
MODEL_ID = "claude-haiku-4-5-20251001"


@dataclass
class DescriptionExtractionResult:
    """One LLM summarization call's structured output.

    ``description`` is the model's short (1-2 sentence) summary of the
    given ``content`` -- or ``""`` when the given text carried nothing
    substantive to summarize. An empty ``description`` is a valid,
    expected result, not an error: mirrors ``SponsorExtractionResult``'s
    own "an empty result is correct and expected" framing, adapted from
    an empty *list* (no confirmed sponsors) to an empty *string* (no
    summarizable content). Ticket 004's orchestration is the layer that
    actually enforces the no-email guard's third layer and any length
    cap in code (never trusting the model's compliance with its own
    prompt instructions alone); this dataclass is just the call's raw
    structured result.
    """

    description: str = ""


class DescriptionLLMClient(Protocol):
    """Injectable seam for one LLM description-summarization call.

    Mirrors ``sponsor_llm.py``'s ``SponsorLLMClient`` protocol pattern,
    parallel in shape but with no import relationship to it (module
    docstring). Implementations receive a bounded content string (see
    :func:`~partner_scrape.teams.description_candidates.gather_description_content`)
    and a ``context`` dict carrying call-identifying information (e.g.
    ``"team_id"``) that ticket 004's orchestration and tests may use for
    logging or fixture lookup -- unlike ``sponsor_llm.py``'s
    ``context``, no key here drives the real client's prompt content
    (module docstring: no per-team exclusion list applies to
    summarization) -- and return a structured
    :class:`DescriptionExtractionResult`, never a raw string, never a
    partially-parsed dict.
    """

    def summarize_description(self, content: str, context: dict[str, Any]) -> DescriptionExtractionResult:
        """Return a short summary of ``content``, or an empty-description
        result if ``content`` has nothing substantive to summarize.

        ``content`` is expected to already be ticket 002's bounded,
        gathered content string -- never raw HTML, never a live page.
        ``context`` may carry call-identifying keys (e.g. ``"team_id"``),
        any of which may be absent.
        """
        ...


class DescriptionClassificationError(Exception):
    """Raised when an LLM response cannot be parsed into a
    DescriptionExtractionResult.

    Covers malformed JSON, a missing text content block, and a missing
    or wrongly-typed ``description`` field -- every case where returning
    a partially-populated ``DescriptionExtractionResult`` would be a
    silently wrong result rather than a caught failure. Mirrors
    ``SponsorClassificationError``'s role exactly: ticket 004's
    ``extract_descriptions()`` fail-open path (SUC-023's Error Flows)
    catches this specifically, not a bare ``Exception``, so it can
    distinguish "the model/API misbehaved" from an unrelated programming
    error.
    """


# --------------------------------------------------------------------
# Structured-output JSON schema, built directly from
# DescriptionExtractionResult's shape (via dataclass field
# introspection) so the schema and the dataclass cannot drift silently
# -- duplicating, not importing, sponsor_llm.py's
# _build_sponsor_extraction_json_schema pattern (module docstring).
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

    raise TypeError(f"Unsupported field type for DescriptionExtractionResult schema: {annotation!r}")


def _build_description_extraction_json_schema() -> dict[str, Any]:
    hints = typing.get_type_hints(DescriptionExtractionResult)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for f in dataclasses.fields(DescriptionExtractionResult):
        properties[f.name] = _field_json_schema(hints[f.name])
        required.append(f.name)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


#: The structured-output schema sent on every real request -- see
#: :func:`_build_description_extraction_json_schema`.
DESCRIPTION_EXTRACTION_JSON_SCHEMA = _build_description_extraction_json_schema()


#: This call's system prompt (SUC-023's Main Flow; this ticket's
#: acceptance criteria). Static, not rebuilt per call -- see the module
#: docstring for why this differs from ``sponsor_llm._build_system_prompt()``.
#:
#: Explicitly instructs, per the acceptance criteria: summarize only the
#: given text; never state a fact not present in it; never include
#: contact information (**no-email guard, layer 2 of 3** -- layer 1 is
#: ticket 002's regex strip on the gathered content itself, layer 3 is
#: ticket 004's code-level rejection of this call's raw output); return
#: an empty string if nothing substantive is present -- mirroring
#: ``sponsor_llm.py``'s own "an empty result is correct and expected ...
#: do not select a candidate you are unsure about" instruction, adapted
#: from selection to summarization.
_SYSTEM_PROMPT = """You are helping write short, factual descriptions for a directory of San Diego \
County FIRST robotics teams (FTC/FRC/FLL). You are given a single bounded block of text gathered \
deterministically from one team's own website -- its meta description, page title, and heading/body \
text, already assembled by a separate process. You never see the raw page or its HTML, and you \
never see anything beyond the text given to you in the next message.

Your only job is to SUMMARIZE the given text into a short, one-to-two sentence description of the \
team. Never state a fact about the team that is not present in the given text -- do not infer, \
guess, or add outside knowledge, even general knowledge you may have about FIRST robotics or about \
this team specifically. Every claim in your description must be traceable to the given text.

Never include any contact information in your response -- no email address, no phone number, and no \
physical or mailing address -- even if the given text itself contains one.

If the given text contains nothing substantive to summarize (for example, only boilerplate, \
navigation labels, or a single unhelpful phrase), return an empty string -- an empty result is \
correct and expected for many pages; do not invent a plausible-sounding description just to avoid \
an empty answer. Respond only with the structured JSON the response format requires."""


def _build_user_prompt(content: str) -> str:
    return (
        "Here is the bounded content gathered from this team's website. Summarize it into a short, "
        "one-to-two sentence description, following the rules in your system prompt:\n\n"
        + json.dumps({"content": content}, indent=2)
    )


# --------------------------------------------------------------------
# Response parsing/validation
# --------------------------------------------------------------------


def _expect_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise DescriptionClassificationError(f"Expected {field_name!r} to be a string, got {value!r}")
    return value


def _result_from_dict(data: Any) -> DescriptionExtractionResult:
    if not isinstance(data, dict):
        raise DescriptionClassificationError(f"Expected the response to be a JSON object, got {type(data).__name__}")

    missing = [name for name in DESCRIPTION_EXTRACTION_JSON_SCHEMA["required"] if name not in data]
    if missing:
        raise DescriptionClassificationError(f"Response is missing required field(s): {missing}")

    return DescriptionExtractionResult(
        description=_expect_str(data["description"], "description"),
    )


def _extract_response_text(response: Any) -> str:
    for block in getattr(response, "content", []):
        if getattr(block, "type", None) == "text":
            return block.text
    raise DescriptionClassificationError("Anthropic response contained no text content block")


def _parse_response(response: Any) -> DescriptionExtractionResult:
    text = _extract_response_text(response)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DescriptionClassificationError(f"Anthropic response was not valid JSON: {exc}") from exc
    return _result_from_dict(data)


# --------------------------------------------------------------------
# The real implementation
# --------------------------------------------------------------------


class AnthropicDescriptionLLMClient:
    """The real ``DescriptionLLMClient``: a thin wrapper over the
    ``anthropic`` SDK.

    Constructs ``anthropic.Anthropic()`` with **no** explicit
    ``api_key`` argument -- the SDK resolves ``ANTHROPIC_API_KEY`` (or
    another configured credential) itself; a missing/invalid key
    surfaces as an ``anthropic`` SDK exception at
    :meth:`summarize_description`'s own call site, caught by ticket
    004's per-team fail-open guard (SUC-023's Error Flows), never
    aborting a ``teams`` run. No retry/backoff logic here (the
    ``anthropic`` SDK already retries 429/5xx per its own defaults) and
    no caching (that's
    :class:`~partner_scrape.teams.description_cache.DescriptionCache`, a
    different module with a different reason to change).
    """

    def __init__(self) -> None:
        self._client = anthropic.Anthropic()

    def summarize_description(self, content: str, context: dict[str, Any]) -> DescriptionExtractionResult:
        response = self._client.messages.create(
            model=MODEL_ID,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_prompt(content)}],
            output_config={"format": {"type": "json_schema", "schema": DESCRIPTION_EXTRACTION_JSON_SCHEMA}},
        )
        return _parse_response(response)


# --------------------------------------------------------------------
# Test double
# --------------------------------------------------------------------


@dataclass
class FixtureDescriptionLLMClient:
    """``DescriptionLLMClient`` test double: returns canned
    ``DescriptionExtractionResult``s.

    Never opens a socket or imports ``anthropic``. ``responses`` is
    looked up by ``key_fn(content, context)`` -- default: ``content``
    itself, since the content string is this call's primary variable
    input (mirroring ``sponsor_llm.FixtureSponsorLLMClient``'s default
    of keying by the input's own natural identity, adapted from a
    candidate-list tuple to a plain string). Pass e.g.
    ``key_fn=lambda content, context: context["team_id"]`` to key by
    team identity instead. Every ``(content, context)`` pair passed to
    :meth:`summarize_description` is recorded in ``calls``, in order, so
    tests (e.g. ticket 004's cache-skip call-counting assertions) can
    assert on how many times -- and with what -- this client was
    invoked.

    Raises:
        KeyError: if ``key_fn(content, context)`` is absent from
            ``responses`` -- a loud failure if the code under test asks
            this double to summarize content it wasn't told to expect.
    """

    responses: dict[Any, DescriptionExtractionResult]
    key_fn: Callable[[str, dict[str, Any]], Any] = lambda content, context: content
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def summarize_description(self, content: str, context: dict[str, Any]) -> DescriptionExtractionResult:
        self.calls.append((content, context))
        return self.responses[self.key_fn(content, context)]
