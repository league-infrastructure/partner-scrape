"""Tests for partner_scrape.adapters.program_llm: the ProgramLLMClient
protocol, ProgramExtractionResult, AnthropicProgramLLMClient, and
FixtureProgramLLMClient.

Every test in this file either exercises FixtureProgramLLMClient directly
(no ``anthropic`` import involved at all) or monkeypatches
``anthropic.Anthropic`` -- the SDK's client *class* -- with a fake, so no
test opens a real socket or requires ``ANTHROPIC_API_KEY`` to be set.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from partner_scrape.adapters.program_llm import (
    PROGRAM_EXTRACTION_JSON_SCHEMA,
    PROGRAM_LIST_EXTRACTION_JSON_SCHEMA,
    MODEL_ID,
    _FIELD_EXTRACTION_RULES,
    _FIELD_EXTRACTION_RULES_COMPETITION,
    _SYSTEM_PROMPT,
    _SYSTEM_PROMPT_COMPETITION,
    _SYSTEM_PROMPT_COMPETITION_MULTI,
    _SYSTEM_PROMPT_MULTI,
    AnthropicProgramLLMClient,
    FixtureProgramLLMClient,
    ProgramExtractionResult,
    ProgramLLMExtractionError,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "program_pages"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


# ---------------------------------------------------------------------
# Fake anthropic SDK client -- stands in for anthropic.Anthropic()
# ---------------------------------------------------------------------


@dataclass
class _FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class _FakeMessage:
    content: list[Any]


@dataclass
class _FakeMessagesResource:
    """Stands in for ``anthropic.Anthropic().messages`` -- records every
    call's kwargs so tests can assert on the request shape."""

    response_text: str
    calls: list[dict[str, Any]] = field(default_factory=list)

    def create(self, **kwargs: Any) -> _FakeMessage:
        self.calls.append(kwargs)
        return _FakeMessage(content=[_FakeTextBlock(text=self.response_text)])


def _install_fake_anthropic(monkeypatch: pytest.MonkeyPatch, response_text: str) -> _FakeMessagesResource:
    """Monkeypatch anthropic.Anthropic (the class itself) with a fake that
    never opens a socket, and return its `.messages` double so the test
    can inspect recorded calls."""

    fake_messages = _FakeMessagesResource(response_text=response_text)

    class FakeAnthropic:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.init_args = args
            self.init_kwargs = kwargs
            self.messages = fake_messages

    monkeypatch.setattr("partner_scrape.adapters.program_llm.anthropic.Anthropic", FakeAnthropic)
    return fake_messages


_FULL_RESULT_PAYLOAD = {
    "program_name": "Fixture Research Experience for High School Students",
    "audience_grades": ["10th grade", "11th grade", "12th grade"],
    "date_start": "2026-12-01",
    "date_end": "2027-02-15",
    "cost": "$2,500 stipend",
    "eligibility": "San Diego County residents in grades 10-12.",
    "is_open": True,
    "opportunity_type": "Work-based Learning",
    "registration_deadline": "",
}


# ---------------------------------------------------------------------
# ProgramExtractionResult / schema shape (AC: schema generated from the
# dataclass's own annotations, no hand-maintained schema literal)
# ---------------------------------------------------------------------


class TestProgramExtractionResult:
    def test_defaults(self):
        result = ProgramExtractionResult()
        assert result.program_name == ""
        assert result.audience_grades == []
        assert result.date_start == ""
        assert result.date_end == ""
        assert result.cost == ""
        assert result.eligibility == ""
        assert result.is_open is True
        assert result.opportunity_type == ""
        assert result.registration_deadline == ""

    def test_default_list_fields_are_not_shared_between_instances(self):
        a = ProgramExtractionResult()
        b = ProgramExtractionResult()
        a.audience_grades.append("Grades 9-12")
        assert b.audience_grades == []


class TestProgramExtractionJsonSchema:
    def test_schema_properties_and_required_match_dataclass_fields(self):
        field_names = {f.name for f in dataclasses.fields(ProgramExtractionResult)}
        assert set(PROGRAM_EXTRACTION_JSON_SCHEMA["properties"].keys()) == field_names
        assert set(PROGRAM_EXTRACTION_JSON_SCHEMA["required"]) == field_names

    def test_schema_forbids_additional_properties(self):
        assert PROGRAM_EXTRACTION_JSON_SCHEMA["additionalProperties"] is False

    def test_audience_grades_is_an_array_of_strings(self):
        prop = PROGRAM_EXTRACTION_JSON_SCHEMA["properties"]["audience_grades"]
        assert prop == {"type": "array", "items": {"type": "string"}}

    def test_is_open_is_a_boolean_field(self):
        assert PROGRAM_EXTRACTION_JSON_SCHEMA["properties"]["is_open"] == {"type": "boolean"}

    def test_opportunity_type_is_a_required_string_field(self):
        assert PROGRAM_EXTRACTION_JSON_SCHEMA["properties"]["opportunity_type"] == {"type": "string"}
        assert "opportunity_type" in PROGRAM_EXTRACTION_JSON_SCHEMA["required"]


# ---------------------------------------------------------------------
# AnthropicProgramLLMClient construction
# ---------------------------------------------------------------------


class TestAnthropicProgramLLMClientConstruction:
    def test_constructs_anthropic_client_with_no_api_key_argument(self, monkeypatch):
        captured: dict[str, Any] = {}

        class RecordingAnthropic:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                captured["args"] = args
                captured["kwargs"] = kwargs
                self.messages = _FakeMessagesResource(response_text="{}")

        monkeypatch.setattr("partner_scrape.adapters.program_llm.anthropic.Anthropic", RecordingAnthropic)

        AnthropicProgramLLMClient()

        assert captured["args"] == ()
        assert captured["kwargs"] == {}
        assert "api_key" not in captured["kwargs"]

    def test_construction_does_not_require_anthropic_api_key_env_var(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        _install_fake_anthropic(monkeypatch, response_text="{}")

        # Must not raise, even with no ANTHROPIC_API_KEY set.
        AnthropicProgramLLMClient()


# ---------------------------------------------------------------------
# AnthropicProgramLLMClient.extract_program -- request shape
# ---------------------------------------------------------------------


class TestAnthropicProgramLLMClientRequestShape:
    def test_request_uses_model_id_constant_and_structured_output_schema(self, monkeypatch):
        fake_messages = _install_fake_anthropic(monkeypatch, response_text=json.dumps(_FULL_RESULT_PAYLOAD))
        client = AnthropicProgramLLMClient()

        client.extract_program("https://example.org/fre-hs", _read_fixture("prose_program_page.html"))

        assert len(fake_messages.calls) == 1
        call_kwargs = fake_messages.calls[0]
        assert call_kwargs["model"] == MODEL_ID
        assert call_kwargs["output_config"]["format"]["type"] == "json_schema"
        assert call_kwargs["output_config"]["format"]["schema"] == PROGRAM_EXTRACTION_JSON_SCHEMA

    def test_request_includes_url_and_body_in_the_prompt(self, monkeypatch):
        fake_messages = _install_fake_anthropic(monkeypatch, response_text=json.dumps(_FULL_RESULT_PAYLOAD))
        client = AnthropicProgramLLMClient()
        body = _read_fixture("prose_program_page.html")

        client.extract_program("https://example.org/fre-hs", body)

        call_kwargs = fake_messages.calls[0]
        user_message = call_kwargs["messages"][0]["content"]
        assert "https://example.org/fre-hs" in user_message
        assert "Fixture Research Experience" in user_message


# ---------------------------------------------------------------------
# AnthropicProgramLLMClient.extract_program -- successful parsing (AC)
# ---------------------------------------------------------------------


class TestAnthropicProgramLLMClientParsesResponses:
    def test_parses_full_result_response(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text=json.dumps(_FULL_RESULT_PAYLOAD))
        client = AnthropicProgramLLMClient()

        result = client.extract_program(
            "https://example.org/fre-hs", _read_fixture("prose_program_page.html")
        )

        assert isinstance(result, ProgramExtractionResult)
        assert result.program_name == "Fixture Research Experience for High School Students"
        assert result.audience_grades == ["10th grade", "11th grade", "12th grade"]
        assert result.date_start == "2026-12-01"
        assert result.date_end == "2027-02-15"
        assert result.cost == "$2,500 stipend"
        assert result.eligibility == "San Diego County residents in grades 10-12."
        assert result.is_open is True
        assert result.opportunity_type == "Work-based Learning"

    def test_parses_closed_program_response(self, monkeypatch):
        closed_payload = dict(_FULL_RESULT_PAYLOAD, is_open=False, date_end="2026-01-01")
        _install_fake_anthropic(monkeypatch, response_text=json.dumps(closed_payload))
        client = AnthropicProgramLLMClient()

        result = client.extract_program("https://example.org/closed-program", "closed")

        assert result.is_open is False
        assert result.date_end == "2026-01-01"


# ---------------------------------------------------------------------
# AnthropicProgramLLMClient.extract_program -- malformed/wrong-shaped
# responses (AC)
# ---------------------------------------------------------------------


class TestAnthropicProgramLLMClientRejectsMalformedResponses:
    def test_malformed_json_raises_program_llm_extraction_error(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text="{not json")
        client = AnthropicProgramLLMClient()

        with pytest.raises(ProgramLLMExtractionError):
            client.extract_program("https://example.org/x", "body")

    def test_wrong_type_field_raises_program_llm_extraction_error(self, monkeypatch):
        bad_payload = dict(_FULL_RESULT_PAYLOAD, is_open="yes")  # should be a bool
        _install_fake_anthropic(monkeypatch, response_text=json.dumps(bad_payload))
        client = AnthropicProgramLLMClient()

        with pytest.raises(ProgramLLMExtractionError):
            client.extract_program("https://example.org/x", "body")

    def test_wrong_type_list_field_raises_program_llm_extraction_error(self, monkeypatch):
        bad_payload = dict(_FULL_RESULT_PAYLOAD, audience_grades="Grades 9-12")  # should be a list
        _install_fake_anthropic(monkeypatch, response_text=json.dumps(bad_payload))
        client = AnthropicProgramLLMClient()

        with pytest.raises(ProgramLLMExtractionError):
            client.extract_program("https://example.org/x", "body")

    def test_missing_required_field_raises_program_llm_extraction_error(self, monkeypatch):
        bad_payload = dict(_FULL_RESULT_PAYLOAD)
        del bad_payload["opportunity_type"]
        _install_fake_anthropic(monkeypatch, response_text=json.dumps(bad_payload))
        client = AnthropicProgramLLMClient()

        with pytest.raises(ProgramLLMExtractionError):
            client.extract_program("https://example.org/x", "body")

    def test_non_object_json_raises_program_llm_extraction_error(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text=json.dumps(["not", "an", "object"]))
        client = AnthropicProgramLLMClient()

        with pytest.raises(ProgramLLMExtractionError):
            client.extract_program("https://example.org/x", "body")

    def test_no_text_content_block_raises_program_llm_extraction_error(self, monkeypatch):
        class FakeMessagesNoText:
            def create(self, **kwargs: Any) -> _FakeMessage:
                return _FakeMessage(content=[])

        class FakeAnthropic:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.messages = FakeMessagesNoText()

        monkeypatch.setattr("partner_scrape.adapters.program_llm.anthropic.Anthropic", FakeAnthropic)
        client = AnthropicProgramLLMClient()

        with pytest.raises(ProgramLLMExtractionError):
            client.extract_program("https://example.org/x", "body")


# ---------------------------------------------------------------------
# FixtureProgramLLMClient (AC)
# ---------------------------------------------------------------------


# ---------------------------------------------------------------------
# extract_programs()'s list-valued schema and request shape (ticket 006
# exception revision, AC: schema built via the same dataclass-
# introspection mechanism as the existing schema, no hand-maintained
# duplicate)
# ---------------------------------------------------------------------


class TestProgramListExtractionJsonSchema:
    def test_wraps_the_per_record_schema_in_a_programs_array(self):
        assert PROGRAM_LIST_EXTRACTION_JSON_SCHEMA == {
            "type": "object",
            "properties": {"programs": {"type": "array", "items": PROGRAM_EXTRACTION_JSON_SCHEMA}},
            "required": ["programs"],
            "additionalProperties": False,
        }

    def test_items_schema_is_the_exact_dataclass_introspected_object_not_a_hand_written_copy(self):
        # Identity, not just equality -- proves this is the same object
        # _build_program_extraction_json_schema() already produced, never
        # a second hand-maintained literal that happens to match today.
        assert PROGRAM_LIST_EXTRACTION_JSON_SCHEMA["properties"]["programs"]["items"] is (
            PROGRAM_EXTRACTION_JSON_SCHEMA
        )


_MULTI_RESULT_PAYLOAD = {
    "programs": [
        _FULL_RESULT_PAYLOAD,
        dict(_FULL_RESULT_PAYLOAD, program_name="Fixture Second Program", date_end="2027-03-01"),
    ]
}


class TestAnthropicProgramLLMClientExtractPrograms:
    def test_request_uses_model_id_constant_and_list_schema(self, monkeypatch):
        fake_messages = _install_fake_anthropic(monkeypatch, response_text=json.dumps(_MULTI_RESULT_PAYLOAD))
        client = AnthropicProgramLLMClient()

        client.extract_programs("https://example.org/sio-internships", _read_fixture("prose_program_page.html"))

        assert len(fake_messages.calls) == 1
        call_kwargs = fake_messages.calls[0]
        assert call_kwargs["model"] == MODEL_ID
        assert call_kwargs["output_config"]["format"]["type"] == "json_schema"
        assert call_kwargs["output_config"]["format"]["schema"] == PROGRAM_LIST_EXTRACTION_JSON_SCHEMA

    def test_parses_a_list_of_results(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text=json.dumps(_MULTI_RESULT_PAYLOAD))
        client = AnthropicProgramLLMClient()

        results = client.extract_programs("https://example.org/sio-internships", "body")

        assert len(results) == 2
        assert all(isinstance(r, ProgramExtractionResult) for r in results)
        assert results[0].program_name == "Fixture Research Experience for High School Students"
        assert results[1].program_name == "Fixture Second Program"
        assert results[1].date_end == "2027-03-01"

    def test_empty_programs_list_is_valid(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text=json.dumps({"programs": []}))
        client = AnthropicProgramLLMClient()

        assert client.extract_programs("https://example.org/x", "body") == []

    def test_missing_programs_key_raises_program_llm_extraction_error(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text=json.dumps({}))
        client = AnthropicProgramLLMClient()

        with pytest.raises(ProgramLLMExtractionError):
            client.extract_programs("https://example.org/x", "body")

    def test_non_list_programs_value_raises_program_llm_extraction_error(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text=json.dumps({"programs": "not a list"}))
        client = AnthropicProgramLLMClient()

        with pytest.raises(ProgramLLMExtractionError):
            client.extract_programs("https://example.org/x", "body")

    def test_a_malformed_record_within_the_list_raises_program_llm_extraction_error(self, monkeypatch):
        bad_payload = {"programs": [dict(_FULL_RESULT_PAYLOAD, is_open="yes")]}
        _install_fake_anthropic(monkeypatch, response_text=json.dumps(bad_payload))
        client = AnthropicProgramLLMClient()

        with pytest.raises(ProgramLLMExtractionError):
            client.extract_programs("https://example.org/x", "body")


class TestIsOpenPromptGeneralization:
    """AC (028-003): ``is_open``'s field description generalizes from
    "applications are open" to also cover a sold-out camp session,
    identically in both the single- and multi-record system prompts
    (they already share ``_FIELD_EXTRACTION_RULES`` verbatim).
    """

    def test_field_rules_describe_is_open_generically_covering_sold_out(self):
        assert "sold out" in _FIELD_EXTRACTION_RULES
        assert "is_open: true if open for enrollment/application" in _FIELD_EXTRACTION_RULES

    def test_field_rules_no_longer_scope_is_open_to_applications_only(self):
        # The old, narrower wording ("applications are currently open")
        # is gone -- this is a broadening, not an addition alongside it.
        assert "applications are currently open" not in _FIELD_EXTRACTION_RULES

    def test_single_and_multi_prompts_share_the_identical_is_open_wording(self):
        assert _FIELD_EXTRACTION_RULES in _SYSTEM_PROMPT
        assert _FIELD_EXTRACTION_RULES in _SYSTEM_PROMPT_MULTI


class TestEmptyProgramsListIsExplicitlyValid:
    """AC (028-003): ``_SYSTEM_PROMPT_MULTI`` explicitly instructs the
    model that an empty ``programs`` list is a valid response for a page
    with no distinct programs/sessions -- closing the gap that would
    otherwise let an off-season page (e.g. Fleet's) hallucinate a
    session or raise a parse error instead of legitimately returning
    nothing.
    """

    def test_multi_prompt_tells_the_model_an_empty_list_is_valid(self):
        assert "If no distinct programs are described on the page, return an empty list." in (
            _SYSTEM_PROMPT_MULTI
        )

    def test_single_prompt_carries_no_such_instruction(self):
        # The single-record prompt has no list-valued response to be
        # empty -- this instruction is multi-prompt-only.
        assert "return an empty list" not in _SYSTEM_PROMPT


# ---------------------------------------------------------------------
# Sprint 029 ticket 006: competition-genre extraction profile fix --
# date-vs-deadline framing, "Event Date"-style phrasing, and the
# reference-date-based year-inference rule.
# ---------------------------------------------------------------------


class TestBaseFieldRulesSpecifyRegistrationDeadline:
    """AC: the base (unchanged) ``_FIELD_EXTRACTION_RULES`` explicitly
    says ``registration_deadline`` is always ``""`` for that profile,
    rather than leaving the new required field to unstated
    structured-output defaulting.
    """

    def test_base_field_rules_say_registration_deadline_is_always_empty(self):
        assert 'registration_deadline: always ""' in _FIELD_EXTRACTION_RULES


class TestCompetitionFieldRulesSeparateDateFromDeadline:
    """AC: ``_FIELD_EXTRACTION_RULES_COMPETITION`` redefines
    date_start/date_end as the event's own date (never a registration
    deadline), names the "Event Date"-style phrasing patterns tickets
    001/002 found the model missing, and specifies the reference-date
    year-inference rule.
    """

    def test_date_end_is_explicitly_not_a_registration_deadline(self):
        assert "NOT a registration, sign-up, or paperwork deadline" in (
            _FIELD_EXTRACTION_RULES_COMPETITION
        )

    def test_registration_deadline_field_is_defined_as_a_separate_deadline(self):
        assert "registration_deadline: a registration, team-signup, or paperwork deadline" in (
            _FIELD_EXTRACTION_RULES_COMPETITION
        )

    def test_names_event_date_style_phrasing_patterns(self):
        for phrase in ('"Event Date,"', '"Competition Date,"', '"Tournament Date,"', '"Save the Date,"'):
            assert phrase in _FIELD_EXTRACTION_RULES_COMPETITION

    def test_year_inference_rule_references_the_reference_date(self):
        assert "Page fetched on" in _FIELD_EXTRACTION_RULES_COMPETITION
        assert "infer the soonest year" in _FIELD_EXTRACTION_RULES_COMPETITION

    def test_shared_by_both_competition_prompts(self):
        assert _FIELD_EXTRACTION_RULES_COMPETITION in _SYSTEM_PROMPT_COMPETITION
        assert _FIELD_EXTRACTION_RULES_COMPETITION in _SYSTEM_PROMPT_COMPETITION_MULTI

    def test_competition_prompts_are_distinct_from_the_base_prompts(self):
        assert _SYSTEM_PROMPT_COMPETITION != _SYSTEM_PROMPT
        assert _SYSTEM_PROMPT_COMPETITION_MULTI != _SYSTEM_PROMPT_MULTI


class TestProfileSelectsSystemPrompt:
    """AC: ``profile="competition"`` selects
    ``_SYSTEM_PROMPT_COMPETITION``/``_SYSTEM_PROMPT_COMPETITION_MULTI``;
    every call that omits ``profile`` (or passes the default
    ``"program"``) is byte-for-byte unaffected -- proving sprint 027/028
    call sites' backward compatibility.
    """

    def test_default_profile_uses_the_unchanged_single_record_prompt(self, monkeypatch):
        fake_messages = _install_fake_anthropic(monkeypatch, response_text=json.dumps(_FULL_RESULT_PAYLOAD))
        client = AnthropicProgramLLMClient()

        client.extract_program("https://example.org/x", "body")

        assert fake_messages.calls[0]["system"] == _SYSTEM_PROMPT

    def test_omitted_profile_and_reference_date_produce_the_pre_revision_prompt_byte_for_byte(
        self, monkeypatch
    ):
        fake_messages = _install_fake_anthropic(monkeypatch, response_text=json.dumps(_FULL_RESULT_PAYLOAD))
        client = AnthropicProgramLLMClient()

        client.extract_program("https://example.org/x", "body text")

        user_message = fake_messages.calls[0]["messages"][0]["content"]
        assert user_message == (
            "Program page URL: https://example.org/x\n\n"
            "Here is the page's raw text. Extract the fields the response "
            "format requires.\n\nbody text"
        )
        assert "Page fetched on" not in user_message

    def test_competition_profile_uses_the_competition_single_record_prompt(self, monkeypatch):
        fake_messages = _install_fake_anthropic(monkeypatch, response_text=json.dumps(_FULL_RESULT_PAYLOAD))
        client = AnthropicProgramLLMClient()

        client.extract_program("https://example.org/x", "body", profile="competition")

        assert fake_messages.calls[0]["system"] == _SYSTEM_PROMPT_COMPETITION

    def test_competition_profile_uses_the_competition_multi_record_prompt(self, monkeypatch):
        fake_messages = _install_fake_anthropic(
            monkeypatch, response_text=json.dumps({"programs": [_FULL_RESULT_PAYLOAD]})
        )
        client = AnthropicProgramLLMClient()

        client.extract_programs("https://example.org/x", "body", profile="competition")

        assert fake_messages.calls[0]["system"] == _SYSTEM_PROMPT_COMPETITION_MULTI


class TestReferenceDateInjectedIntoUserPromptOnly:
    """AC: ``reference_date`` is injected into the *user* prompt as
    "Page fetched on: ``<ISO date>``", never the system prompt.
    """

    def test_reference_date_appears_in_the_user_prompt(self, monkeypatch):
        fake_messages = _install_fake_anthropic(monkeypatch, response_text=json.dumps(_FULL_RESULT_PAYLOAD))
        client = AnthropicProgramLLMClient()

        client.extract_program(
            "https://example.org/x", "body", profile="competition", reference_date=date(2026, 3, 1)
        )

        user_message = fake_messages.calls[0]["messages"][0]["content"]
        assert "Page fetched on: 2026-03-01" in user_message
        # The literal reference date value is user-prompt-only -- the
        # system prompt's own year-inference rule refers to "Page fetched
        # on" generically (static text), never embeds a per-call date.
        assert "2026-03-01" not in fake_messages.calls[0]["system"]

    def test_no_reference_date_line_when_reference_date_is_none(self, monkeypatch):
        fake_messages = _install_fake_anthropic(monkeypatch, response_text=json.dumps(_FULL_RESULT_PAYLOAD))
        client = AnthropicProgramLLMClient()

        client.extract_program("https://example.org/x", "body", profile="competition")

        user_message = fake_messages.calls[0]["messages"][0]["content"]
        assert "Page fetched on" not in user_message


class TestYearInferenceMechanismWiring:
    """AC: a fixture test proving the year-inference mechanism -- a
    synthetic page stating a month/day with no adjacent year, extracted
    with a fixed ``reference_date``, yields the expected inferred year.

    Since every test in this file drives a fake (never real) Anthropic
    client, this proves the *mechanism* is correctly wired -- the
    competition prompt is selected, the reference date reaches the user
    prompt, and a response already reflecting the year-inference rule
    (what the corrected prompt directs the real model to produce, per
    ``adapters/DESIGN.md``'s Revision section) round-trips through
    unchanged -- not that the real model reasons correctly, which is
    outside this hermetic suite's reach (no live network/API, per this
    project's testing convention).
    """

    def test_tritonhacks_shaped_page_with_a_fixed_reference_date_yields_the_inferred_year(
        self, monkeypatch
    ):
        # TritonHacks' live-measured failure: "May 16 & 17" with no
        # adjacent year anywhere near the dates; the pre-revision prompt
        # guessed an already-past year (2025-05-08). A reference date of
        # 2026-03-01 makes 2026-05-16 the correctly-inferred soonest year.
        inferred_payload = dict(_FULL_RESULT_PAYLOAD, date_start="2026-05-16", date_end="2026-05-17")
        fake_messages = _install_fake_anthropic(monkeypatch, response_text=json.dumps(inferred_payload))
        client = AnthropicProgramLLMClient()

        result = client.extract_program(
            "https://example.org/tritonhacks",
            "TritonHacks -- May 16 & 17. Save the Date!",
            profile="competition",
            reference_date=date(2026, 3, 1),
        )

        assert result.date_start == "2026-05-16"
        assert result.date_end == "2026-05-17"
        call_kwargs = fake_messages.calls[0]
        assert call_kwargs["system"] == _SYSTEM_PROMPT_COMPETITION
        assert "Page fetched on: 2026-03-01" in call_kwargs["messages"][0]["content"]
        assert "May 16 & 17" in call_kwargs["messages"][0]["content"]


class TestFixtureProgramLLMClientAcceptsAndIgnoresNewParameters:
    """AC: ``FixtureProgramLLMClient`` accepts the same ``profile``/
    ``reference_date`` keyword-only parameters, ignoring them -- no
    existing fixture-test call site needs to change.
    """

    def test_extract_program_accepts_profile_and_reference_date(self):
        canned = ProgramExtractionResult(program_name="Fixture Program")
        client = FixtureProgramLLMClient(responses={"https://example.org/p": canned})

        result = client.extract_program(
            "https://example.org/p", "body", profile="competition", reference_date=date(2026, 3, 1)
        )

        assert result is canned
        # calls still records only (url, body) -- unchanged shape.
        assert client.calls == [("https://example.org/p", "body")]

    def test_extract_programs_accepts_profile_and_reference_date(self):
        canned = [ProgramExtractionResult(program_name="A")]
        client = FixtureProgramLLMClient(list_responses={"https://example.org/p": canned})

        result = client.extract_programs(
            "https://example.org/p", "body", profile="competition", reference_date=date(2026, 3, 1)
        )

        assert result is canned
        assert client.list_calls == [("https://example.org/p", "body")]


class TestFixtureProgramLLMClient:
    def test_returns_canned_result_looked_up_by_url(self):
        canned = ProgramExtractionResult(program_name="Fixture Program")
        client = FixtureProgramLLMClient(responses={"https://example.org/p": canned})

        result = client.extract_program("https://example.org/p", "body text")

        assert result is canned

    def test_records_every_call_in_order(self):
        canned = ProgramExtractionResult()
        client = FixtureProgramLLMClient(responses={"https://example.org/p": canned})

        client.extract_program("https://example.org/p", "body one")
        client.extract_program("https://example.org/p", "body two")

        assert client.calls == [
            ("https://example.org/p", "body one"),
            ("https://example.org/p", "body two"),
        ]

    def test_unknown_key_raises_key_error(self):
        client = FixtureProgramLLMClient(responses={})

        with pytest.raises(KeyError):
            client.extract_program("https://example.org/unregistered", "body")

    def test_custom_key_fn_looks_up_by_url_and_body(self):
        canned = ProgramExtractionResult(is_open=False)
        client = FixtureProgramLLMClient(
            responses={("https://example.org/p", "closed body"): canned},
            key_fn=lambda url, body: (url, body),
        )

        assert client.extract_program("https://example.org/p", "closed body") is canned

    def test_works_even_if_the_anthropic_sdk_client_would_explode(self, monkeypatch):
        """Sanity check that FixtureProgramLLMClient never constructs or
        calls the real anthropic SDK client -- break it and confirm
        FixtureProgramLLMClient is unaffected."""

        class ExplodingAnthropic:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                raise AssertionError("FixtureProgramLLMClient must never construct anthropic.Anthropic()")

        monkeypatch.setattr("partner_scrape.adapters.program_llm.anthropic.Anthropic", ExplodingAnthropic)

        canned = ProgramExtractionResult(program_name="Fixture Program")
        client = FixtureProgramLLMClient(responses={"https://example.org/p": canned})

        assert client.extract_program("https://example.org/p", "body") is canned


class TestFixtureProgramLLMClientExtractPrograms:
    """Ticket 006 exception revision: ``FixtureProgramLLMClient`` extended
    to also return a canned list, via a second ``list_responses`` dict
    keyed the same way (``key_fn``) as the existing ``responses`` dict --
    not a second test-double class.
    """

    def test_returns_canned_list_looked_up_by_url(self):
        canned = [ProgramExtractionResult(program_name="A"), ProgramExtractionResult(program_name="B")]
        client = FixtureProgramLLMClient(list_responses={"https://example.org/p": canned})

        result = client.extract_programs("https://example.org/p", "body text")

        assert result is canned

    def test_records_every_call_in_order_separately_from_singular_calls(self):
        client = FixtureProgramLLMClient(
            responses={"https://example.org/p": ProgramExtractionResult()},
            list_responses={"https://example.org/p": []},
        )

        client.extract_program("https://example.org/p", "body")
        client.extract_programs("https://example.org/p", "body")

        assert client.calls == [("https://example.org/p", "body")]
        assert client.list_calls == [("https://example.org/p", "body")]

    def test_unknown_key_raises_key_error(self):
        client = FixtureProgramLLMClient()

        with pytest.raises(KeyError):
            client.extract_programs("https://example.org/unregistered", "body")

    def test_custom_key_fn_looks_up_by_url_and_body(self):
        canned = [ProgramExtractionResult(program_name="A")]
        client = FixtureProgramLLMClient(
            list_responses={("https://example.org/p", "body one"): canned},
            key_fn=lambda url, body: (url, body),
        )

        assert client.extract_programs("https://example.org/p", "body one") is canned
