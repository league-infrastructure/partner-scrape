"""Tests for partner_scrape.teams.description_llm: the
DescriptionLLMClient protocol, DescriptionExtractionResult,
AnthropicDescriptionLLMClient, and FixtureDescriptionLLMClient.

Every test in this file either exercises FixtureDescriptionLLMClient
directly (no ``anthropic`` import involved at all) or monkeypatches
``anthropic.Anthropic`` -- the SDK's client *class* -- with a fake,
mirroring ``tests/teams/test_sponsor_llm.py``'s convention exactly: no
test opens a real socket, and no test requires ``ANTHROPIC_API_KEY`` to
be set.
"""

from __future__ import annotations

import ast
import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from partner_scrape.teams.description_llm import (
    DESCRIPTION_EXTRACTION_JSON_SCHEMA,
    MODEL_ID,
    AnthropicDescriptionLLMClient,
    DescriptionClassificationError,
    DescriptionExtractionResult,
    FixtureDescriptionLLMClient,
)

DESCRIPTION_LLM_MODULE_PATH = Path(__file__).resolve().parents[2] / "partner_scrape" / "teams" / "description_llm.py"


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

    monkeypatch.setattr("partner_scrape.teams.description_llm.anthropic.Anthropic", FakeAnthropic)
    return fake_messages


# ---------------------------------------------------------------------
# DescriptionExtractionResult / DescriptionLLMClient protocol shape
# ---------------------------------------------------------------------


class TestDescriptionExtractionResult:
    def test_defaults_to_empty_string(self):
        result = DescriptionExtractionResult()
        assert result.description == ""

    def test_empty_description_is_a_valid_value_not_an_error(self):
        # AC: empty string is a valid, expected value, not an error.
        result = DescriptionExtractionResult(description="")
        assert result.description == ""


class TestDescriptionExtractionJsonSchema:
    def test_schema_properties_and_required_match_dataclass_fields(self):
        field_names = {f.name for f in dataclasses.fields(DescriptionExtractionResult)}
        assert set(DESCRIPTION_EXTRACTION_JSON_SCHEMA["properties"].keys()) == field_names
        assert set(DESCRIPTION_EXTRACTION_JSON_SCHEMA["required"]) == field_names

    def test_schema_forbids_additional_properties(self):
        assert DESCRIPTION_EXTRACTION_JSON_SCHEMA["additionalProperties"] is False

    def test_description_is_a_string(self):
        prop = DESCRIPTION_EXTRACTION_JSON_SCHEMA["properties"]["description"]
        assert prop == {"type": "string"}


# ---------------------------------------------------------------------
# Zero imports from partner_scrape.enrich (mirrors sponsor_llm's own
# forbidden-import precedent -- teams/ has a standing invariant of zero
# edges into enrich/).
# ---------------------------------------------------------------------


class TestNoForbiddenImports:
    def test_description_llm_module_imports_nothing_from_partner_scrape_enrich(self):
        tree = ast.parse(DESCRIPTION_LLM_MODULE_PATH.read_text(), filename=str(DESCRIPTION_LLM_MODULE_PATH))
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders.extend(
                    alias.name for alias in node.names if alias.name.startswith("partner_scrape.enrich")
                )
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("partner_scrape.enrich"):
                    offenders.append(node.module)
        assert offenders == []

    def test_description_llm_module_imports_nothing_from_sponsor_llm(self):
        """AC: mirrors sponsor_llm.py in shape, never by import."""
        tree = ast.parse(DESCRIPTION_LLM_MODULE_PATH.read_text(), filename=str(DESCRIPTION_LLM_MODULE_PATH))
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "sponsor_llm" in node.module:
                    offenders.append(node.module)
        assert offenders == []


# ---------------------------------------------------------------------
# AnthropicDescriptionLLMClient construction (AC: no explicit api_key argument)
# ---------------------------------------------------------------------


class TestAnthropicDescriptionLLMClientConstruction:
    def test_constructs_anthropic_client_with_no_api_key_argument(self, monkeypatch):
        captured: dict[str, Any] = {}

        class RecordingAnthropic:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                captured["args"] = args
                captured["kwargs"] = kwargs
                self.messages = _FakeMessagesResource(response_text="{}")

        monkeypatch.setattr("partner_scrape.teams.description_llm.anthropic.Anthropic", RecordingAnthropic)

        AnthropicDescriptionLLMClient()

        assert captured["args"] == ()
        assert captured["kwargs"] == {}
        assert "api_key" not in captured["kwargs"]

    def test_construction_does_not_require_anthropic_api_key_env_var(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        _install_fake_anthropic(monkeypatch, response_text="{}")

        # Must not raise, even with no ANTHROPIC_API_KEY set.
        AnthropicDescriptionLLMClient()

    def test_real_client_construction_never_calls_the_network(self, monkeypatch):
        """AC: the real client is constructed in at most one test proving
        it builds without raising -- and never actually calls the
        network. Guard against anthropic.Anthropic() itself performing an
        HTTP call at construction time by asserting no messages call was
        made."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        fake_messages = _install_fake_anthropic(monkeypatch, response_text="{}")

        AnthropicDescriptionLLMClient()

        assert fake_messages.calls == []


# ---------------------------------------------------------------------
# AnthropicDescriptionLLMClient.summarize_description -- request shape
# ---------------------------------------------------------------------


class TestAnthropicDescriptionLLMClientRequestShape:
    def test_request_uses_model_id_constant_and_structured_output_schema(self, monkeypatch):
        fake_messages = _install_fake_anthropic(
            monkeypatch, response_text=json.dumps({"description": "A robotics team from Poway."})
        )
        client = AnthropicDescriptionLLMClient()

        client.summarize_description("Poway High School's FTC robotics team.", {"team_id": "ftc-12499"})

        assert len(fake_messages.calls) == 1
        call_kwargs = fake_messages.calls[0]
        assert call_kwargs["model"] == MODEL_ID
        assert call_kwargs["output_config"]["format"]["type"] == "json_schema"
        assert call_kwargs["output_config"]["format"]["schema"] == DESCRIPTION_EXTRACTION_JSON_SCHEMA

    def test_user_message_carries_the_content_verbatim(self, monkeypatch):
        fake_messages = _install_fake_anthropic(monkeypatch, response_text=json.dumps({"description": ""}))
        client = AnthropicDescriptionLLMClient()

        client.summarize_description("Gear Up! is Team 12499's motto.", {})

        user_message = fake_messages.calls[0]["messages"][0]["content"]
        assert "Gear Up! is Team 12499's motto." in user_message

    def test_system_prompt_instructs_summarize_only_no_facts_no_contact_info_empty_if_nothing(self, monkeypatch):
        """AC: the system prompt explicitly instructs: summarize only the
        given text; never state a fact not present in it; never include
        contact information; return an empty string if nothing
        substantive is present."""
        fake_messages = _install_fake_anthropic(monkeypatch, response_text=json.dumps({"description": ""}))
        client = AnthropicDescriptionLLMClient()

        client.summarize_description("Some team content.", {})

        system_prompt = fake_messages.calls[0]["system"]
        assert "summarize" in system_prompt.lower()
        assert "not present in the given text" in system_prompt or "not present in the text" in system_prompt
        assert "email" in system_prompt.lower()
        assert "phone" in system_prompt.lower()
        assert "address" in system_prompt.lower()
        assert "empty string" in system_prompt.lower()

    def test_system_prompt_is_stable_across_calls_with_different_content(self, monkeypatch):
        """Unlike sponsor_llm.py's per-call-rebuilt system prompt, this
        one carries no per-team-varying instruction -- confirm it's
        identical across two different content inputs."""
        fake_messages = _install_fake_anthropic(monkeypatch, response_text=json.dumps({"description": ""}))
        client = AnthropicDescriptionLLMClient()

        client.summarize_description("First team's content.", {"team_id": "ftc-1"})
        client.summarize_description("Second team's content.", {"team_id": "ftc-2"})

        assert fake_messages.calls[0]["system"] == fake_messages.calls[1]["system"]


# ---------------------------------------------------------------------
# AnthropicDescriptionLLMClient.summarize_description -- successful parsing (AC)
# ---------------------------------------------------------------------


class TestAnthropicDescriptionLLMClientParsesResponses:
    def test_parses_non_empty_description(self, monkeypatch):
        _install_fake_anthropic(
            monkeypatch, response_text=json.dumps({"description": "A San Diego FTC robotics team."})
        )
        client = AnthropicDescriptionLLMClient()

        result = client.summarize_description("Team content goes here.", {})

        assert isinstance(result, DescriptionExtractionResult)
        assert result.description == "A San Diego FTC robotics team."

    def test_parses_empty_description(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text=json.dumps({"description": ""}))
        client = AnthropicDescriptionLLMClient()

        result = client.summarize_description("Boilerplate nav labels only.", {})

        assert result.description == ""


# ---------------------------------------------------------------------
# AnthropicDescriptionLLMClient.summarize_description -- malformed responses (AC)
# ---------------------------------------------------------------------


class TestAnthropicDescriptionLLMClientRejectsMalformedResponses:
    def test_malformed_json_raises_description_classification_error(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text="{not valid json")
        client = AnthropicDescriptionLLMClient()

        with pytest.raises(DescriptionClassificationError):
            client.summarize_description("Some content.", {})

    def test_wrong_type_field_raises_description_classification_error(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text=json.dumps({"description": ["not", "a", "string"]}))
        client = AnthropicDescriptionLLMClient()

        with pytest.raises(DescriptionClassificationError):
            client.summarize_description("Some content.", {})

    def test_missing_required_field_raises_description_classification_error(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text=json.dumps({}))
        client = AnthropicDescriptionLLMClient()

        with pytest.raises(DescriptionClassificationError):
            client.summarize_description("Some content.", {})

    def test_non_object_json_raises_description_classification_error(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text=json.dumps(["not", "an", "object"]))
        client = AnthropicDescriptionLLMClient()

        with pytest.raises(DescriptionClassificationError):
            client.summarize_description("Some content.", {})

    def test_no_text_content_block_raises_description_classification_error(self, monkeypatch):
        class FakeMessagesNoText:
            def create(self, **kwargs: Any) -> _FakeMessage:
                return _FakeMessage(content=[])

        class FakeAnthropic:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.messages = FakeMessagesNoText()

        monkeypatch.setattr("partner_scrape.teams.description_llm.anthropic.Anthropic", FakeAnthropic)
        client = AnthropicDescriptionLLMClient()

        with pytest.raises(DescriptionClassificationError):
            client.summarize_description("Some content.", {})


# ---------------------------------------------------------------------
# FixtureDescriptionLLMClient (AC)
# ---------------------------------------------------------------------


class TestFixtureDescriptionLLMClient:
    def test_returns_canned_result_looked_up_by_content(self):
        canned = DescriptionExtractionResult(description="A robotics team.")
        client = FixtureDescriptionLLMClient(responses={"Team content.": canned})

        result = client.summarize_description("Team content.", {"team_id": "ftc-12499"})

        assert result is canned

    def test_records_every_call_in_order(self):
        canned = DescriptionExtractionResult()
        client = FixtureDescriptionLLMClient(responses={"Content A": canned, "Content B": canned})
        context_a = {"team_id": "ftc-1"}
        context_b = {"team_id": "ftc-2"}

        client.summarize_description("Content A", context_a)
        client.summarize_description("Content B", context_b)

        assert client.calls == [("Content A", context_a), ("Content B", context_b)]

    def test_unknown_key_raises_key_error(self):
        client = FixtureDescriptionLLMClient(responses={})

        with pytest.raises(KeyError):
            client.summarize_description("Unregistered content", {})

    def test_custom_key_fn_looks_up_by_team_id_in_context(self):
        canned = DescriptionExtractionResult(description="A robotics team.")
        client = FixtureDescriptionLLMClient(
            responses={"ftc-12499": canned},
            key_fn=lambda content, context: context["team_id"],
        )

        result = client.summarize_description("Any content", {"team_id": "ftc-12499"})

        assert result is canned

    def test_works_even_if_the_anthropic_sdk_client_would_explode(self, monkeypatch):
        """Sanity check that FixtureDescriptionLLMClient never constructs
        or calls the real anthropic SDK client -- break it and confirm
        FixtureDescriptionLLMClient is unaffected."""

        class ExplodingAnthropic:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                raise AssertionError("FixtureDescriptionLLMClient must never construct anthropic.Anthropic()")

        monkeypatch.setattr("partner_scrape.teams.description_llm.anthropic.Anthropic", ExplodingAnthropic)

        canned = DescriptionExtractionResult(description="A robotics team.")
        client = FixtureDescriptionLLMClient(responses={"Team content.": canned})

        assert client.summarize_description("Team content.", {}) is canned
