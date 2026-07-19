"""Candidate Review Queue: persists discovered ``OrgCandidate``s as
review-marked TOML stubs for a human operator to promote.

See sprint.md's Architecture > Candidate Review Queue, SUC-001, and the
Design Rationale ("Hub scanning is structurally separate from the
Event/Opportunity pipeline"). A stub deliberately contains only
``org_name``, ``candidate_url``, ``discovered_via``, and
``evidence_text`` -- **no** ``adapter_type``/``config`` -- so that even a
misdirected attempt to load it via ``registry.loader.load_sources()``
fails ``SourceConfig.from_toml``'s required-field check
(``InvalidSourceConfig``) rather than silently succeeding. This is a
belt-and-suspenders defense: the primary safety property is that
``registry/candidates/`` is physically separate from
``registry/sources/`` and never in ``registry/loader.py``'s scan path
(that module is unmodified by this ticket) -- this stub shape is what
happens if a future caller ever points the loader at the wrong
directory anyway.
"""

from __future__ import annotations

import logging
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from partner_scrape.discovery.hub_scan import OrgCandidate
from partner_scrape.normalize.partners import normalize_org_name

logger = logging.getLogger(__name__)

#: Default location of the Candidate Review Queue's stub TOML files:
#: ``partner_scrape/registry/candidates/`` -- physically separate from
#: ``registry/sources/`` and ``registry/hubs/``, and never scanned by
#: ``registry.loader.load_sources``/``load_active_sources`` (that
#: module's ``DEFAULT_SOURCES_DIR`` is a different, unrelated directory).
DEFAULT_CANDIDATES_DIR = Path(__file__).resolve().parent / "candidates"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(org_name: str) -> str:
    """A filesystem-safe, human-legible file stem derived from
    ``org_name`` (e.g. ``"Brand New STEM Org!"`` -> ``"brand-new-stem-org"``).

    Falls back to ``"candidate"`` for a name with no alphanumeric
    characters at all, so a pathological org name never yields an empty
    filename.
    """
    slug = _SLUG_RE.sub("-", org_name.lower()).strip("-")
    return slug or "candidate"


def _toml_escape(value: str) -> str:
    """Escape ``value`` for a TOML basic (double-quoted) string literal.

    Hub-observed evidence text is free-form HTML block text and may
    contain newlines or other control characters a raw basic string
    cannot hold literally -- escaped here so every written stub is valid
    TOML round-trippable by ``tomllib``, not just well-formed for the
    common case.
    """
    out: list[str] = []
    for ch in value:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return "".join(out)


def _toml_string(value: str) -> str:
    return f'"{_toml_escape(value)}"'


@dataclass
class CandidateStub:
    """One persisted Candidate Review Queue entry, as read back by
    :func:`list_candidates` -- an operator-facing view of a queued
    ``OrgCandidate``, plus the file it lives at."""

    org_name: str
    candidate_url: str
    discovered_via: str
    evidence_text: str
    path: Path


def _is_duplicate(candidate: OrgCandidate, existing: list[CandidateStub]) -> bool:
    """Whether ``candidate`` is already represented in ``existing`` --
    either the same ``candidate_url`` exactly, or the same normalized org
    name (mirrors ``discovery.hub_scan``'s own dedup-by-URL-or-name
    convention against the Source Registry, applied here against the
    Candidate Review Queue itself)."""
    normalized_name = normalize_org_name(candidate.org_name)
    for stub in existing:
        if stub.candidate_url == candidate.candidate_url:
            return True
        if normalize_org_name(stub.org_name) == normalized_name:
            return True
    return False


def write_candidate(candidate: OrgCandidate, directory: Path | None = None) -> Path | None:
    """Persist ``candidate`` as a review-marked stub TOML file under
    ``directory`` (defaults to :data:`DEFAULT_CANDIDATES_DIR`).

    The written file contains exactly ``org_name``, ``candidate_url``,
    ``discovered_via`` (``candidate.hub_id``), and ``evidence_text`` --
    deliberately omitting ``adapter_type``/``config`` (see this module's
    docstring). The filename is derived from a slugified ``org_name``,
    disambiguated with a numeric suffix on a literal collision.

    A candidate already present in the queue -- matched by exact
    ``candidate_url`` or normalized org name against every existing stub
    in ``directory`` -- is not written again: this call is a no-op and
    returns ``None``. Re-running discovery repeatedly (e.g. a scheduled
    hub scan) must not clutter the review queue with duplicate stubs for
    an org still awaiting review.

    Returns:
        The path written to, or ``None`` if ``candidate`` was already
        queued and this call was skipped.
    """
    directory = directory or DEFAULT_CANDIDATES_DIR
    directory.mkdir(parents=True, exist_ok=True)

    if _is_duplicate(candidate, list_candidates(directory)):
        logger.info(
            "Candidate %r (%s) already queued for review; skipping duplicate write",
            candidate.org_name,
            candidate.candidate_url,
        )
        return None

    stem = _slugify(candidate.org_name)
    path = directory / f"{stem}.toml"
    suffix = 2
    while path.exists():
        path = directory / f"{stem}-{suffix}.toml"
        suffix += 1

    lines = [
        "# Candidate review stub -- NOT a live source.",
        "#",
        "# This file is deliberately missing adapter_type/config: it is",
        "# never loaded by registry.loader.load_sources(). To promote this",
        "# candidate, investigate its own site, add adapter_type/config,",
        "# and move the completed file into registry/sources/.",
        f"org_name = {_toml_string(candidate.org_name)}",
        f"candidate_url = {_toml_string(candidate.candidate_url)}",
        f"discovered_via = {_toml_string(candidate.hub_id)}",
        f"evidence_text = {_toml_string(candidate.evidence_text)}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def list_candidates(directory: Path | None = None) -> list[CandidateStub]:
    """List every candidate stub currently queued under ``directory``
    (defaults to :data:`DEFAULT_CANDIDATES_DIR`) for an operator to
    review.

    A directory that does not yet exist (no discovery run has ever
    written to it) yields an empty list rather than raising. A stub file
    that fails to parse as TOML is logged and skipped -- mirrors
    ``registry.loader.load_sources``'s "malformed file is never fatal to
    the rest of the directory" contract.
    """
    directory = directory or DEFAULT_CANDIDATES_DIR
    if not directory.exists():
        return []

    stubs: list[CandidateStub] = []
    for path in sorted(directory.glob("*.toml")):
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as exc:
            logger.warning("Skipping malformed candidate stub %s: %s", path, exc)
            continue
        stubs.append(
            CandidateStub(
                org_name=data.get("org_name", ""),
                candidate_url=data.get("candidate_url", ""),
                discovered_via=data.get("discovered_via", ""),
                evidence_text=data.get("evidence_text", ""),
                path=path,
            )
        )
    return stubs
