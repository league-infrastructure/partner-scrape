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
    AnthropicLLMClient,
    EnrichmentResult,
    FixtureLLMClient,
    LLMEnrichmentError,
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
