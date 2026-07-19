"""LLM-based enrichment: injectable client, cache, and Enricher (issue 04).

See sprint.md's Architecture > LLM Client / Enrichment Cache / LLM
Enricher. Ticket 004 defined the LLM Client: the injectable
``LLMClient`` protocol, its structured request/response shape
(``EnrichmentResult``), the one real implementation
(``AnthropicLLMClient``), and a ``FixtureLLMClient`` test double. Ticket
005 adds the ``EnrichmentCache`` (cost-control skip-cache) and
``LLMEnricher`` (``pipeline.Enricher``'s first real implementation,
including the relevance gate) built on top of it.
"""

from __future__ import annotations

from partner_scrape.enrich.cache import EnrichmentCache, content_hash
from partner_scrape.enrich.enricher import (
    FALLBACK_CONFIDENCE,
    FALLBACK_SOURCE,
    LLM_CONFIDENCE,
    LLM_SOURCE,
    LLMEnricher,
)
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
    "EnrichmentCache",
    "content_hash",
    "LLMEnricher",
    "LLM_SOURCE",
    "LLM_CONFIDENCE",
    "FALLBACK_SOURCE",
    "FALLBACK_CONFIDENCE",
]
