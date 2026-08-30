"""Tests for partner_scrape.enrich.llm_client: the LLMClient protocol,
EnrichmentResult, AnthropicLLMClient, and FixtureLLMClient.

Every test in this file either exercises FixtureLLMClient directly (no
``anthropic`` import involved at all) or monkeypatches
``anthropic.Anthropic`` -- the SDK's client *class* -- with a fake, per
sprint.md's testing policy: no test opens a real socket, and no test
requires ``ANTHROPIC_API_KEY`` to be set.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from partner_scrape.enrich.llm_client import (
    ENRICHMENT_JSON_SCHEMA,
    MODEL_ID,
    PROMPT_VERSION,
    AnthropicLLMClient,
    EnrichmentResult,
    FixtureLLMClient,
    LLMEnrichmentError,
    _SYSTEM_PROMPT,
)
from partner_scrape.model import Event

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "llm"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _sample_event(**overrides: Any) -> Event:
    defaults: dict[str, Any] = dict(
        source_id="fixture_org",
        title="Robotics Night",
        description="Hands-on robotics for kids.",
    )
    defaults.update(overrides)
    return Event(**defaults)


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

    monkeypatch.setattr("partner_scrape.enrich.llm_client.anthropic.Anthropic", FakeAnthropic)
    return fake_messages


# ---------------------------------------------------------------------
# EnrichmentResult / LLMClient protocol shape
# ---------------------------------------------------------------------


class TestEnrichmentResult:
    def test_defaults_are_unset(self):
        result = EnrichmentResult()
        assert result.start is None
        assert result.end is None
        assert result.all_day is None
        assert result.location is None
        assert result.cost is None
        assert result.registration_url is None
        assert result.areas_of_interest == []
        assert result.age_grade_level == []
        assert result.cost_range == ""
        assert result.time_of_day == []
        assert result.opportunity_type == ""
        assert result.relevant is True
        assert result.relevance_reason == ""

    def test_default_list_fields_are_not_shared_between_instances(self):
        a = EnrichmentResult()
        b = EnrichmentResult()
        a.areas_of_interest.append("Engineering")
        assert b.areas_of_interest == []


class TestEnrichmentJsonSchema:
    def test_schema_properties_and_required_match_dataclass_fields(self):
        field_names = {f.name for f in dataclasses.fields(EnrichmentResult)}
        assert set(ENRICHMENT_JSON_SCHEMA["properties"].keys()) == field_names
        assert set(ENRICHMENT_JSON_SCHEMA["required"]) == field_names

    def test_schema_forbids_additional_properties(self):
        assert ENRICHMENT_JSON_SCHEMA["additionalProperties"] is False

    def test_list_fields_are_arrays_of_strings(self):
        for name in ("areas_of_interest", "age_grade_level", "time_of_day"):
            prop = ENRICHMENT_JSON_SCHEMA["properties"][name]
            assert prop == {"type": "array", "items": {"type": "string"}}

    def test_opportunity_type_is_a_required_string_field(self):
        """Sprint 009 (issue 13): opportunity_type is picked up by the
        dataclass-introspection schema generator automatically -- no
        hand-maintained schema literal is touched to add it."""
        assert "opportunity_type" in ENRICHMENT_JSON_SCHEMA["properties"]
        assert ENRICHMENT_JSON_SCHEMA["properties"]["opportunity_type"] == {"type": "string"}
        assert "opportunity_type" in ENRICHMENT_JSON_SCHEMA["required"]


# ---------------------------------------------------------------------
# All-ages relevance gate (sprint 014, issue 22): _SYSTEM_PROMPT's
# audience scope and the new PROMPT_VERSION cache-key signal.
# ---------------------------------------------------------------------


class TestSystemPromptAllAgesScope:
    def test_relevant_criterion_states_any_audience(self):
        assert "STEM learning opportunity for any audience" in _SYSTEM_PROMPT

    def test_relevant_criterion_lists_the_widened_audience_examples(self):
        for audience in (
            "children",
            "teens",
            "families",
            "adults",
            "educators",
            "college-bound",
        ):
            assert audience in _SYSTEM_PROMPT

    def test_no_longer_restricts_relevance_to_youth_or_excludes_adult_only(self):
        """The old K-12-only framing explicitly said 'for youth' and
        '(not an adult-only program...)' -- both must be gone from the
        rewritten relevant criterion; an adult/professional audience is
        no longer, by itself, a reason to reject."""
        assert "for youth" not in _SYSTEM_PROMPT
        assert "adult-only program" not in _SYSTEM_PROMPT

    def test_noise_rejection_categories_are_still_named(self):
        """The gate widens audience scope; it does not loosen noise
        rejection. Non-STEM recreation, galas, closure notices, press
        releases, and navigation pages with no program content are all
        still named as reasons to say relevant=false."""
        for noise_term in (
            "non-STEM recreation",
            "gala",
            "closure notice",
            "press release",
            "navigation",
        ):
            assert noise_term in _SYSTEM_PROMPT


class TestPromptVersion:
    def test_prompt_version_is_a_positive_integer_constant(self):
        assert isinstance(PROMPT_VERSION, int)
        assert PROMPT_VERSION >= 1


# ---------------------------------------------------------------------
# AnthropicLLMClient construction (AC: no explicit api_key argument)
# ---------------------------------------------------------------------


class TestAnthropicLLMClientConstruction:
    def test_constructs_anthropic_client_with_no_api_key_argument(self, monkeypatch):
        captured: dict[str, Any] = {}

        class RecordingAnthropic:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                captured["args"] = args
                captured["kwargs"] = kwargs
                self.messages = _FakeMessagesResource(response_text="{}")

        monkeypatch.setattr("partner_scrape.enrich.llm_client.anthropic.Anthropic", RecordingAnthropic)

        AnthropicLLMClient()

        assert captured["args"] == ()
        assert captured["kwargs"] == {}
        assert "api_key" not in captured["kwargs"]

    def test_construction_does_not_require_anthropic_api_key_env_var(self, monkeypatch):
        """No test in this suite should require ANTHROPIC_API_KEY -- the
        SDK client class itself is replaced, so whatever credential
        resolution the real SDK would do never runs."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        _install_fake_anthropic(monkeypatch, response_text="{}")

        # Must not raise, even with no ANTHROPIC_API_KEY set.
        AnthropicLLMClient()


# ---------------------------------------------------------------------
# AnthropicLLMClient.enrich_event -- request shape
# ---------------------------------------------------------------------


class TestAnthropicLLMClientRequestShape:
    def test_request_uses_model_id_constant_and_structured_output_schema(self, monkeypatch):
        fake_messages = _install_fake_anthropic(
            monkeypatch, response_text=_read_fixture("full_classification.json")
        )
        client = AnthropicLLMClient()

        client.enrich_event(_sample_event())

        assert len(fake_messages.calls) == 1
        call_kwargs = fake_messages.calls[0]
        assert call_kwargs["model"] == MODEL_ID
        assert call_kwargs["output_config"]["format"]["type"] == "json_schema"
        assert call_kwargs["output_config"]["format"]["schema"] == ENRICHMENT_JSON_SCHEMA

    def test_request_includes_event_known_fields_in_the_prompt(self, monkeypatch):
        fake_messages = _install_fake_anthropic(
            monkeypatch, response_text=_read_fixture("full_classification.json")
        )
        client = AnthropicLLMClient()
        event = _sample_event(title="Robotics Night", description="Hands-on robotics for kids.")

        client.enrich_event(event)

        call_kwargs = fake_messages.calls[0]
        user_message = call_kwargs["messages"][0]["content"]
        assert "Robotics Night" in user_message
        assert "Hands-on robotics for kids." in user_message


# ---------------------------------------------------------------------
# AnthropicLLMClient.enrich_event -- successful parsing (AC)
# ---------------------------------------------------------------------


class TestAnthropicLLMClientParsesResponses:
    def test_parses_full_classification_response(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text=_read_fixture("full_classification.json"))
        client = AnthropicLLMClient()

        result = client.enrich_event(_sample_event())

        assert isinstance(result, EnrichmentResult)
        assert result.start == datetime(2026, 8, 15, 18, 0, 0)
        assert result.end == datetime(2026, 8, 15, 20, 0, 0)
        assert result.all_day is False
        assert result.location == "Fixture Library, San Diego, CA"
        assert result.cost == "Free"
        assert result.registration_url == "https://example.org/register"
        assert result.areas_of_interest == [
            "Coding/Computer Science/Cyber Security",
            "Engineering",
        ]
        assert result.age_grade_level == ["Grades 6-8"]
        assert result.cost_range == "Free"
        assert result.time_of_day == ["Evening"]
        assert result.opportunity_type == "Out-of-school Programs"
        assert result.relevant is True
        assert result.relevance_reason == "Hands-on youth robotics program at a public library."

    def test_parses_not_relevant_response(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text=_read_fixture("not_relevant.json"))
        client = AnthropicLLMClient()

        result = client.enrich_event(_sample_event(title="Adult Wine Tasting"))

        assert result.start is None
        assert result.location is None
        assert result.age_grade_level == ["Adult"]
        assert result.relevant is False
        assert result.relevance_reason == (
            "Adult-only wine tasting event, not a STEM learning opportunity for youth."
        )

    def test_parses_adult_audience_relevant_response(self, monkeypatch):
        """Sprint 014 (issue 22), SUC-001: an adult-audience-worded event
        (a professional development workshop for working engineers)
        enriches relevant=True with 'Adult' in age_grade_level -- the
        gate widens audience, an adult-only program is no longer, by
        itself, a reason to reject."""
        _install_fake_anthropic(
            monkeypatch, response_text=_read_fixture("adult_professional_relevant.json")
        )
        client = AnthropicLLMClient()
        event = _sample_event(
            title="Engineering Leadership Workshop for Working Professionals",
            description="A professional development workshop for working engineers.",
        )

        result = client.enrich_event(event)

        assert result.relevant is True
        assert "Adult" in result.age_grade_level
        assert result.opportunity_type == "Professional Development / Conferences"

    def test_parses_closure_notice_not_relevant_response(self, monkeypatch):
        """Sprint 014 (issue 22), SUC-001: a noise fixture (a facility
        closure notice) still enriches relevant=False -- the audience
        widening does not loosen noise rejection."""
        _install_fake_anthropic(
            monkeypatch, response_text=_read_fixture("closure_notice_not_relevant.json")
        )
        client = AnthropicLLMClient()
        event = _sample_event(
            title="Library Closed for Independence Day",
            description="The library will be closed on July 4th for the holiday.",
        )

        result = client.enrich_event(event)

        assert result.relevant is False
        assert "closure" in result.relevance_reason.lower()


# ---------------------------------------------------------------------
# AnthropicLLMClient.enrich_event -- malformed/wrong-shaped responses (AC)
# ---------------------------------------------------------------------


class TestAnthropicLLMClientRejectsMalformedResponses:
    def test_malformed_json_raises_llm_enrichment_error(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text=_read_fixture("malformed.json"))
        client = AnthropicLLMClient()

        with pytest.raises(LLMEnrichmentError):
            client.enrich_event(_sample_event())

    def test_wrong_type_field_raises_llm_enrichment_error(self, monkeypatch):
        bad_payload = json.loads(_read_fixture("full_classification.json"))
        bad_payload["relevant"] = "yes"  # should be a bool, not a string
        _install_fake_anthropic(monkeypatch, response_text=json.dumps(bad_payload))
        client = AnthropicLLMClient()

        with pytest.raises(LLMEnrichmentError):
            client.enrich_event(_sample_event())

    def test_wrong_type_list_field_raises_llm_enrichment_error(self, monkeypatch):
        bad_payload = json.loads(_read_fixture("full_classification.json"))
        bad_payload["areas_of_interest"] = "Engineering"  # should be a list
        _install_fake_anthropic(monkeypatch, response_text=json.dumps(bad_payload))
        client = AnthropicLLMClient()

        with pytest.raises(LLMEnrichmentError):
            client.enrich_event(_sample_event())

    def test_unparseable_date_raises_llm_enrichment_error(self, monkeypatch):
        bad_payload = json.loads(_read_fixture("full_classification.json"))
        bad_payload["start"] = "not-a-date"
        _install_fake_anthropic(monkeypatch, response_text=json.dumps(bad_payload))
        client = AnthropicLLMClient()

        with pytest.raises(LLMEnrichmentError):
            client.enrich_event(_sample_event())

    def test_missing_required_field_raises_llm_enrichment_error(self, monkeypatch):
        bad_payload = json.loads(_read_fixture("full_classification.json"))
        del bad_payload["relevant"]
        _install_fake_anthropic(monkeypatch, response_text=json.dumps(bad_payload))
        client = AnthropicLLMClient()

        with pytest.raises(LLMEnrichmentError):
            client.enrich_event(_sample_event())

    def test_missing_opportunity_type_raises_llm_enrichment_error(self, monkeypatch):
        bad_payload = json.loads(_read_fixture("full_classification.json"))
        del bad_payload["opportunity_type"]
        _install_fake_anthropic(monkeypatch, response_text=json.dumps(bad_payload))
        client = AnthropicLLMClient()

        with pytest.raises(LLMEnrichmentError):
            client.enrich_event(_sample_event())

    def test_wrong_type_opportunity_type_raises_llm_enrichment_error(self, monkeypatch):
        bad_payload = json.loads(_read_fixture("full_classification.json"))
        bad_payload["opportunity_type"] = ["Online"]  # should be a string
        _install_fake_anthropic(monkeypatch, response_text=json.dumps(bad_payload))
        client = AnthropicLLMClient()

        with pytest.raises(LLMEnrichmentError):
            client.enrich_event(_sample_event())

    def test_non_object_json_raises_llm_enrichment_error(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text=json.dumps(["not", "an", "object"]))
        client = AnthropicLLMClient()

        with pytest.raises(LLMEnrichmentError):
            client.enrich_event(_sample_event())

    def test_no_text_content_block_raises_llm_enrichment_error(self, monkeypatch):
        class FakeMessagesNoText:
            def create(self, **kwargs: Any) -> _FakeMessage:
                return _FakeMessage(content=[])

        class FakeAnthropic:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.messages = FakeMessagesNoText()

        monkeypatch.setattr("partner_scrape.enrich.llm_client.anthropic.Anthropic", FakeAnthropic)
        client = AnthropicLLMClient()

        with pytest.raises(LLMEnrichmentError):
            client.enrich_event(_sample_event())


# ---------------------------------------------------------------------
# FixtureLLMClient (AC)
# ---------------------------------------------------------------------


class TestFixtureLLMClient:
    def test_returns_canned_result_looked_up_by_title(self):
        canned = EnrichmentResult(relevant=True, relevance_reason="stub")
        client = FixtureLLMClient(responses={"Robotics Night": canned})
        event = _sample_event(title="Robotics Night")

        result = client.enrich_event(event)

        assert result is canned

    def test_canned_result_can_set_opportunity_type(self):
        canned = EnrichmentResult(relevant=True, opportunity_type="Volunteering")
        client = FixtureLLMClient(responses={"Beach Cleanup": canned})
        event = _sample_event(title="Beach Cleanup")

        result = client.enrich_event(event)

        assert result.opportunity_type == "Volunteering"

    def test_records_every_call_in_order(self):
        canned = EnrichmentResult()
        client = FixtureLLMClient(responses={"Robotics Night": canned})
        event_a = _sample_event(title="Robotics Night")
        event_b = _sample_event(title="Robotics Night", description="second call")

        client.enrich_event(event_a)
        client.enrich_event(event_b)

        assert client.calls == [event_a, event_b]

    def test_unknown_key_raises_key_error(self):
        client = FixtureLLMClient(responses={})

        with pytest.raises(KeyError):
            client.enrich_event(_sample_event(title="Unregistered Event"))

    def test_custom_key_fn_looks_up_by_identity_key(self):
        canned = EnrichmentResult(relevant=False)
        event = _sample_event(source_id="fixture_org", external_id="ext-1")
        client = FixtureLLMClient(
            responses={event.identity_key(): canned},
            key_fn=lambda e: e.identity_key(),
        )

        assert client.enrich_event(event) is canned

    def test_works_even_if_the_anthropic_sdk_client_would_explode(self, monkeypatch):
        """Sanity check that FixtureLLMClient never constructs or calls
        the real anthropic SDK client -- break it and confirm
        FixtureLLMClient is unaffected."""

        class ExplodingAnthropic:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                raise AssertionError("FixtureLLMClient must never construct anthropic.Anthropic()")

        monkeypatch.setattr("partner_scrape.enrich.llm_client.anthropic.Anthropic", ExplodingAnthropic)

        canned = EnrichmentResult(relevant=True)
        client = FixtureLLMClient(responses={"Robotics Night": canned})

        assert client.enrich_event(_sample_event(title="Robotics Night")) is canned
