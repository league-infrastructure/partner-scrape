"""Source Registry: the data-driven catalog of organizations and how to
reach their events.

See ``sprint.md``'s Architecture > Source Registry for the design: one
TOML file per organization under ``registry/sources/``, parsed by the
stdlib ``tomllib`` and validated by :func:`load_sources` /
:func:`load_active_sources`. Adding a source is a data edit (one new
TOML file), never a code change.
"""

from __future__ import annotations

from partner_scrape.registry.loader import (
    DEFAULT_SOURCES_DIR,
    load_active_sources,
    load_sources,
)
from partner_scrape.registry.schema import InvalidSourceConfig, SourceConfig

__all__ = [
    "SourceConfig",
    "InvalidSourceConfig",
    "load_sources",
    "load_active_sources",
    "DEFAULT_SOURCES_DIR",
]
