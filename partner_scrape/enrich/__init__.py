"""LLM-based enrichment: injectable client, cache, and Enricher (issue 04).

See sprint.md's Architecture > LLM Client / Enrichment Cache / LLM
Enricher. This ticket (004) defines only the LLM Client: the injectable
``LLMClient`` protocol, its structured request/response shape
(``EnrichmentResult``), the one real implementation
(``AnthropicLLMClient``), and a ``FixtureLLMClient`` test double that
ticket 005's ``LLMEnricher`` reuses.
"""

from __future__ import annotations

from partner_scrape.enrich.llm_client import (
    ENRICHMENT_JSON_SCHEMA,
    MODEL_ID,
    AnthropicLLMClient,
    EnrichmentResult,
    FixtureLLMClient,
    LLMClient,
    LLMEnrichmentError,
)

__all__ = [
    "ENRICHMENT_JSON_SCHEMA",
    "MODEL_ID",
    "AnthropicLLMClient",
    "EnrichmentResult",
    "FixtureLLMClient",
    "LLMClient",
    "LLMEnrichmentError",
]
