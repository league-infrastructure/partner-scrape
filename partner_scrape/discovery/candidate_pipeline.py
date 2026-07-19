"""Candidate Pipeline: sequences Hub Scan through an optional Relevance
Gate into the Candidate Review Queue.

See sprint.md's Architecture > Candidate Pipeline, SUC-001, and the
Design Rationale:

- **"Hub scanning is structurally separate from the Event/Opportunity
  pipeline"** -- this module never imports anything from
  ``partner_scrape.normalize`` or ``partner_scrape.export``. A hub's
  candidates can structurally never reach ``normalize.run()``/
  ``export_opportunities()`` through this call chain, so
  ``opportunities.json`` can never be written by a discovery run no
  matter what a future caller does.
- **"Candidate relevance filtering reuses the existing ``LLMEnricher``
  relevance gate via a synthetic Event"** -- each surviving
  (Source-Registry-deduped) candidate's hub-observed evidence is packaged
  into a throwaway ``Event`` (never persisted, never returned) purely so
  the existing relevance classifier can be reused unmodified.
- **"``discovery/candidate_pipeline.py`` depends on
  ``enrich.enricher.LLMEnricher`` ... never on ``pipeline.Enricher``"**
  -- this module defines its own small, structurally-typed
  :class:`RelevanceGate` Protocol below rather than importing
  ``pipeline.Enricher``. Importing from ``pipeline.py`` would create a
  ``discovery -> pipeline`` edge running backwards against this
  codebase's established dependency direction (``pipeline`` depends on
  ``discovery``/``adapters``/``enrich``, never the reverse). Python
  Protocols are structurally typed, so a real ``LLMEnricher`` instance
  satisfies :class:`RelevanceGate` with zero adaptation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from partner_scrape.discovery.hub_scan import OrgCandidate, scan_hub
from partner_scrape.fetch import Fetcher
from partner_scrape.model import Event
from partner_scrape.registry.candidates import write_candidate
from partner_scrape.registry.hub_schema import HubConfig

logger = logging.getLogger(__name__)


class RelevanceGate(Protocol):
    """Structurally matches ``enrich.enricher.LLMEnricher``'s
    ``.enrich(events) -> events`` shape -- see module docstring's
    dependency-direction note. Any object with this one method (a real
    ``LLMEnricher``, or a test double) satisfies this Protocol with no
    inheritance required."""

    def enrich(self, events: list[Event]) -> list[Event]:
        """Return the subset of ``events`` that survive relevance
        gating (``relevant is not False``), in the same relative order."""
        ...


def _synthetic_event(candidate: OrgCandidate) -> Event:
    """Build the throwaway ``Event`` the Relevance Gate classifies.

    Never persisted, never returned by :func:`discover_candidates` --
    exists only so ``RelevanceGate.enrich`` has something Event-shaped to
    classify. ``title=org_name``, ``description=evidence_text``,
    ``source_id=f"hub:{hub_id}"`` per sprint.md's Candidate Pipeline row.
    """
    return Event(
        title=candidate.org_name,
        description=candidate.evidence_text,
        source_id=f"hub:{candidate.hub_id}",
    )


def discover_candidates(
    hubs: list[HubConfig],
    fetcher: Fetcher,
    enricher: RelevanceGate | None = None,
    *,
    sources_dir: Path | None = None,
    candidates_dir: Path | None = None,
) -> list[OrgCandidate]:
    """Scan every hub in ``hubs``, optionally relevance-gate the
    resulting candidates, and persist survivors to the Candidate Review
    Queue.

    Main flow (SUC-001):

    1. For each hub, :func:`~partner_scrape.discovery.hub_scan.scan_hub`
       produces candidates already deduped against the Source Registry
       (``sources_dir`` overrides the directory checked; defaults to the
       real ``registry/sources/`` when omitted -- see ``scan_hub``'s own
       docstring).
    2. When ``enricher`` is given, every remaining candidate's evidence
       is packaged into a synthetic ``Event`` (:func:`_synthetic_event`)
       and run through ``enricher.enrich(...)``; only candidates whose
       synthetic Event survives (matched back by
       ``Event.identity_key()``, which stays stable whether or not the
       gate mutates/copies the Event) are kept. ``enricher`` omitted
       (``None``) skips relevance filtering entirely -- every
       Source-Registry-deduped candidate is queued, matching sprint.md's
       "(optional) relevance gate" framing.
    3. Every surviving candidate is written via
       ``registry.candidates.write_candidate`` (``candidates_dir``
       overrides the real ``registry/candidates/`` directory). A
       candidate already present in the queue is silently skipped there,
       not duplicated.

    This function never imports or calls ``normalize.run()``/
    ``export_opportunities()`` -- see this module's docstring -- and
    never constructs anything Event-shaped other than the throwaway
    synthetic Event above, which is never returned or persisted.

    Returns:
        The candidates actually written to the queue this call (a
        subset of the relevance-gated survivors: one already queued from
        a prior run is gated out at the write step, not returned here).
        The CLI reports ``len(hubs)`` and ``len(...)`` of this return
        value as its summary.
    """
    all_candidates: list[OrgCandidate] = []
    for hub in hubs:
        all_candidates.extend(scan_hub(hub, fetcher, sources_dir=sources_dir))

    if enricher is None or not all_candidates:
        survivors = all_candidates
    else:
        synthetic_events = [_synthetic_event(candidate) for candidate in all_candidates]
        gated_events = enricher.enrich(synthetic_events)
        gated_keys = {event.identity_key() for event in gated_events}
        survivors = [
            candidate
            for candidate, event in zip(all_candidates, synthetic_events)
            if event.identity_key() in gated_keys
        ]

    written: list[OrgCandidate] = []
    for candidate in survivors:
        path = write_candidate(candidate, directory=candidates_dir)
        if path is not None:
            written.append(candidate)

    logger.info(
        "Scanned %d hub(s): %d candidate(s) survived relevance gating, %d written to the review queue",
        len(hubs),
        len(survivors),
        len(written),
    )
    return written
