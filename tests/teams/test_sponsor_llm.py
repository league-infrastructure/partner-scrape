"""Tests for partner_scrape.teams.sponsor_llm: the SponsorLLMClient
protocol, SponsorExtractionResult, AnthropicSponsorLLMClient, and
FixtureSponsorLLMClient.

Every test in this file either exercises FixtureSponsorLLMClient
directly (no ``anthropic`` import involved at all) or monkeypatches
``anthropic.Anthropic`` -- the SDK's client *class* -- with a fake, per
``enrich/`` project's convention (mirrored, not imported): no test opens
a real socket, and no test requires ``ANTHROPIC_API_KEY`` to be set.
"""

from __future__ import annotations

import ast
import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from partner_scrape.teams.sponsor_llm import (
    MODEL_ID,
    SPONSOR_EXTRACTION_JSON_SCHEMA,
    AnthropicSponsorLLMClient,
    FixtureSponsorLLMClient,
    SponsorClassificationError,
    SponsorExtractionResult,
)

SPONSOR_LLM_MODULE_PATH = Path(__file__).resolve().parents[2] / "partner_scrape" / "teams" / "sponsor_llm.py"


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

    monkeypatch.setattr("partner_scrape.teams.sponsor_llm.anthropic.Anthropic", FakeAnthropic)
    return fake_messages


# ---------------------------------------------------------------------
# SponsorExtractionResult / SponsorLLMClient protocol shape
# ---------------------------------------------------------------------


class TestSponsorExtractionResult:
    def test_defaults_to_empty_list(self):
        result = SponsorExtractionResult()
        assert result.confirmed_sponsors == []

    def test_default_list_field_is_not_shared_between_instances(self):
        a = SponsorExtractionResult()
        b = SponsorExtractionResult()
        a.confirmed_sponsors.append("Qualcomm")
        assert b.confirmed_sponsors == []


class TestSponsorExtractionJsonSchema:
    def test_schema_properties_and_required_match_dataclass_fields(self):
        field_names = {f.name for f in dataclasses.fields(SponsorExtractionResult)}
        assert set(SPONSOR_EXTRACTION_JSON_SCHEMA["properties"].keys()) == field_names
        assert set(SPONSOR_EXTRACTION_JSON_SCHEMA["required"]) == field_names

    def test_schema_forbids_additional_properties(self):
        assert SPONSOR_EXTRACTION_JSON_SCHEMA["additionalProperties"] is False

    def test_confirmed_sponsors_is_an_array_of_strings(self):
        prop = SPONSOR_EXTRACTION_JSON_SCHEMA["properties"]["confirmed_sponsors"]
        assert prop == {"type": "array", "items": {"type": "string"}}


# ---------------------------------------------------------------------
# Zero imports from partner_scrape.enrich (AC)
# ---------------------------------------------------------------------


class TestNoForbiddenImports:
    def test_sponsor_llm_module_imports_nothing_from_partner_scrape_enrich(self):
        tree = ast.parse(SPONSOR_LLM_MODULE_PATH.read_text(), filename=str(SPONSOR_LLM_MODULE_PATH))
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


# ---------------------------------------------------------------------
# AnthropicSponsorLLMClient construction (AC: no explicit api_key argument)
# ---------------------------------------------------------------------


class TestAnthropicSponsorLLMClientConstruction:
    def test_constructs_anthropic_client_with_no_api_key_argument(self, monkeypatch):
        captured: dict[str, Any] = {}

        class RecordingAnthropic:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                captured["args"] = args
                captured["kwargs"] = kwargs
                self.messages = _FakeMessagesResource(response_text="{}")

        monkeypatch.setattr("partner_scrape.teams.sponsor_llm.anthropic.Anthropic", RecordingAnthropic)

        AnthropicSponsorLLMClient()

        assert captured["args"] == ()
        assert captured["kwargs"] == {}
        assert "api_key" not in captured["kwargs"]

    def test_construction_does_not_require_anthropic_api_key_env_var(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        _install_fake_anthropic(monkeypatch, response_text="{}")

        # Must not raise, even with no ANTHROPIC_API_KEY set.
        AnthropicSponsorLLMClient()


# ---------------------------------------------------------------------
# AnthropicSponsorLLMClient.classify_sponsors -- request shape
# ---------------------------------------------------------------------


class TestAnthropicSponsorLLMClientRequestShape:
    def test_request_uses_model_id_constant_and_structured_output_schema(self, monkeypatch):
        fake_messages = _install_fake_anthropic(
            monkeypatch, response_text=json.dumps({"confirmed_sponsors": ["Qualcomm"]})
        )
        client = AnthropicSponsorLLMClient()

        client.classify_sponsors(["Qualcomm", "Wix"], {"organization": "Team Spyder", "hostname": "teamspyder.org"})

        assert len(fake_messages.calls) == 1
        call_kwargs = fake_messages.calls[0]
        assert call_kwargs["model"] == MODEL_ID
        assert call_kwargs["output_config"]["format"]["type"] == "json_schema"
        assert call_kwargs["output_config"]["format"]["schema"] == SPONSOR_EXTRACTION_JSON_SCHEMA

    def test_user_message_carries_the_candidate_list_verbatim(self, monkeypatch):
        fake_messages = _install_fake_anthropic(
            monkeypatch, response_text=json.dumps({"confirmed_sponsors": []})
        )
        client = AnthropicSponsorLLMClient()

        client.classify_sponsors(["Qualcomm", "Nordson"], {"organization": "", "hostname": ""})

        user_message = fake_messages.calls[0]["messages"][0]["content"]
        assert "Qualcomm" in user_message
        assert "Nordson" in user_message

    def test_system_prompt_excludes_organization_hostname_program_and_cms_names(self, monkeypatch):
        """AC: the system prompt explicitly instructs the model to select
        only from the given candidates and to exclude the team's own
        organization name, program names, and named CMS/hosting
        vendors."""
        fake_messages = _install_fake_anthropic(
            monkeypatch, response_text=json.dumps({"confirmed_sponsors": []})
        )
        client = AnthropicSponsorLLMClient()

        client.classify_sponsors(
            ["Qualcomm"], {"organization": "Poway High School", "hostname": "gearup12499.com"}
        )

        system_prompt = fake_messages.calls[0]["system"]
        assert "select" in system_prompt.lower()
        assert "Poway High School" in system_prompt
        assert "gearup12499.com" in system_prompt
        assert "FTC" in system_prompt and "FRC" in system_prompt
        assert "Wix" in system_prompt and "Squarespace" in system_prompt and "GoDaddy" in system_prompt

    def test_system_prompt_omits_organization_and_hostname_lines_when_absent_from_context(self, monkeypatch):
        fake_messages = _install_fake_anthropic(
            monkeypatch, response_text=json.dumps({"confirmed_sponsors": []})
        )
        client = AnthropicSponsorLLMClient()

        client.classify_sponsors(["Qualcomm"], {})

        system_prompt = fake_messages.calls[0]["system"]
        # Still names program/CMS exclusions even with no team context.
        assert "Wix" in system_prompt


# ---------------------------------------------------------------------
# AnthropicSponsorLLMClient.classify_sponsors -- successful parsing (AC)
# ---------------------------------------------------------------------


class TestAnthropicSponsorLLMClientParsesResponses:
    def test_parses_confirmed_sponsors_list(self, monkeypatch):
        _install_fake_anthropic(
            monkeypatch, response_text=json.dumps({"confirmed_sponsors": ["Qualcomm", "Nordson"]})
        )
        client = AnthropicSponsorLLMClient()

        result = client.classify_sponsors(["Qualcomm", "Nordson", "Wix"], {"organization": "", "hostname": ""})

        assert isinstance(result, SponsorExtractionResult)
        assert result.confirmed_sponsors == ["Qualcomm", "Nordson"]

    def test_parses_empty_confirmed_sponsors_list(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text=json.dumps({"confirmed_sponsors": []}))
        client = AnthropicSponsorLLMClient()

        result = client.classify_sponsors(["Wix", "Facebook"], {"organization": "", "hostname": ""})

        assert result.confirmed_sponsors == []


# ---------------------------------------------------------------------
# AnthropicSponsorLLMClient.classify_sponsors -- malformed responses (AC)
# ---------------------------------------------------------------------


class TestAnthropicSponsorLLMClientRejectsMalformedResponses:
    def test_malformed_json_raises_sponsor_classification_error(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text="{not valid json")
        client = AnthropicSponsorLLMClient()

        with pytest.raises(SponsorClassificationError):
            client.classify_sponsors(["Qualcomm"], {})

    def test_wrong_type_field_raises_sponsor_classification_error(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text=json.dumps({"confirmed_sponsors": "Qualcomm"}))
        client = AnthropicSponsorLLMClient()

        with pytest.raises(SponsorClassificationError):
            client.classify_sponsors(["Qualcomm"], {})

    def test_missing_required_field_raises_sponsor_classification_error(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text=json.dumps({}))
        client = AnthropicSponsorLLMClient()

        with pytest.raises(SponsorClassificationError):
            client.classify_sponsors(["Qualcomm"], {})

    def test_non_object_json_raises_sponsor_classification_error(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, response_text=json.dumps(["Qualcomm"]))
        client = AnthropicSponsorLLMClient()

        with pytest.raises(SponsorClassificationError):
            client.classify_sponsors(["Qualcomm"], {})

    def test_no_text_content_block_raises_sponsor_classification_error(self, monkeypatch):
        class FakeMessagesNoText:
            def create(self, **kwargs: Any) -> _FakeMessage:
                return _FakeMessage(content=[])

        class FakeAnthropic:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.messages = FakeMessagesNoText()

        monkeypatch.setattr("partner_scrape.teams.sponsor_llm.anthropic.Anthropic", FakeAnthropic)
        client = AnthropicSponsorLLMClient()

        with pytest.raises(SponsorClassificationError):
            client.classify_sponsors(["Qualcomm"], {})


# ---------------------------------------------------------------------
# FixtureSponsorLLMClient (AC)
# ---------------------------------------------------------------------


class TestFixtureSponsorLLMClient:
    def test_returns_canned_result_looked_up_by_candidate_tuple(self):
        canned = SponsorExtractionResult(confirmed_sponsors=["Qualcomm"])
        client = FixtureSponsorLLMClient(responses={("Qualcomm", "Wix"): canned})

        result = client.classify_sponsors(["Qualcomm", "Wix"], {"organization": "Team Spyder"})

        assert result is canned

    def test_records_every_call_in_order(self):
        canned = SponsorExtractionResult()
        client = FixtureSponsorLLMClient(responses={("Qualcomm",): canned, ("Nordson",): canned})
        context_a = {"organization": "Team A"}
        context_b = {"organization": "Team B"}

        client.classify_sponsors(["Qualcomm"], context_a)
        client.classify_sponsors(["Nordson"], context_b)

        assert client.calls == [(["Qualcomm"], context_a), (["Nordson"], context_b)]

    def test_unknown_key_raises_key_error(self):
        client = FixtureSponsorLLMClient(responses={})

        with pytest.raises(KeyError):
            client.classify_sponsors(["Unregistered"], {})

    def test_custom_key_fn_looks_up_by_team_id_in_context(self):
        canned = SponsorExtractionResult(confirmed_sponsors=["Qualcomm"])
        client = FixtureSponsorLLMClient(
            responses={"ftc-12499": canned},
            key_fn=lambda candidates, context: context["team_id"],
        )

        result = client.classify_sponsors(["Qualcomm"], {"team_id": "ftc-12499"})

        assert result is canned

    def test_works_even_if_the_anthropic_sdk_client_would_explode(self, monkeypatch):
        """Sanity check that FixtureSponsorLLMClient never constructs or
        calls the real anthropic SDK client -- break it and confirm
        FixtureSponsorLLMClient is unaffected."""

        class ExplodingAnthropic:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                raise AssertionError("FixtureSponsorLLMClient must never construct anthropic.Anthropic()")

        monkeypatch.setattr("partner_scrape.teams.sponsor_llm.anthropic.Anthropic", ExplodingAnthropic)

        canned = SponsorExtractionResult(confirmed_sponsors=["Qualcomm"])
        client = FixtureSponsorLLMClient(responses={("Qualcomm",): canned})

        assert client.classify_sponsors(["Qualcomm"], {}) is canned
