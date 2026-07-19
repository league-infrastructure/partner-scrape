"""Directory loader for the Source Registry.

Globs ``*.toml`` files under a directory, parses each via
:meth:`SourceConfig.from_toml`, and returns the list of valid configs.
A malformed or missing-required-field file is logged and skipped --
never fatal to the whole load (SUC-001 Acceptance Criteria: "A
malformed or missing-required-field source file is reported and
skipped, not fatal to the whole load").
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path

from partner_scrape.registry.schema import InvalidSourceConfig, SourceConfig

logger = logging.getLogger(__name__)

#: Default location of the Source Registry's per-organization TOML
#: files: ``partner_scrape/registry/sources/``.
DEFAULT_SOURCES_DIR = Path(__file__).resolve().parent / "sources"


def load_sources(directory: Path | None = None) -> list[SourceConfig]:
    """Load and validate every ``*.toml`` file in ``directory``.

    Returns all parseable sources, including ``enabled: false`` ones --
    disabling a source is a one-line edit, not a file deletion, so a
    disabled entry must still round-trip through the loader. Use
    :func:`load_active_sources` for the enabled-only subset most
    callers (e.g. the Pipeline) actually want.

    A file that fails to parse as TOML, or is missing a required field,
    is logged as a warning and skipped; it never aborts the rest of the
    directory's load.

    Args:
        directory: defaults to :data:`DEFAULT_SOURCES_DIR` (the real
            seed registry) when omitted.
    """
    directory = directory or DEFAULT_SOURCES_DIR
    sources: list[SourceConfig] = []
    for path in sorted(directory.glob("*.toml")):
        try:
            sources.append(SourceConfig.from_toml(path))
        except InvalidSourceConfig as exc:
            logger.warning("Skipping invalid source file: %s", exc)
        except tomllib.TOMLDecodeError as exc:
            logger.warning("Skipping malformed TOML file %s: %s", path, exc)
    return sources


def load_active_sources(directory: Path | None = None) -> list[SourceConfig]:
    """Load sources, excluding ``enabled: false`` entries.

    This is the result most callers (the Pipeline, ticket 008) want --
    the full parseable set from :func:`load_sources` minus anything an
    operator has disabled.
    """
    return [source for source in load_sources(directory) if source.enabled]
