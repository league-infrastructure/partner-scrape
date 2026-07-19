"""The Hub Registry schema: ``HubConfig`` and its TOML directory loader.

Structurally parallel to ``registry/schema.py`` + ``registry/loader.py``
(``SourceConfig``/``load_sources``), but deliberately kept in one module
rather than split across two -- a hub definition is a much smaller shape
than a ``SourceConfig`` (no ``adapter_type``, no ``acquisition_policy``),
so a schema/loader split adds no real separation of concerns here.

A ``HubConfig`` describes one curated external hub -- a regional
calendar, a library system's event listing, a university calendar --
purely as a *lead-generation* source: where to look
(``page_urls``), never how to acquire events from it directly. See
sprint.md's Architecture > Hub Registry and the Design Rationale
("Hub scanning is structurally separate from the Event/Opportunity
pipeline"): hub definitions live under a new ``registry/hubs/``
directory, physically separate from ``registry/sources/``, so
``registry/loader.py``'s ``DEFAULT_SOURCES_DIR`` scan never sees them
and can never accidentally treat a hub as a live source.
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

#: Top-level TOML keys every hub file must define. A file missing
#: either raises InvalidHubConfig, which :func:`load_hubs` catches,
#: logs, and skips -- never fatal to the rest of the directory, mirroring
#: ``registry/schema.py``'s ``_REQUIRED_FIELDS`` contract.
_REQUIRED_FIELDS = ("hub_name", "page_urls")

#: Default location of the Hub Registry's per-hub TOML files:
#: ``partner_scrape/registry/hubs/`` -- physically separate from
#: ``registry/sources/`` (see this module's docstring).
DEFAULT_HUBS_DIR = Path(__file__).resolve().parent / "hubs"


class InvalidHubConfig(Exception):
    """Raised when a hub TOML file is missing a required field.

    Caught at the directory-loader level (:func:`load_hubs`): a single
    bad file is logged and skipped, never fatal to the whole registry
    load.
    """


@dataclass
class HubConfig:
    """One curated external hub Hub Scan can scan for lead candidates.

    ``hub_id`` is derived from the TOML file's stem (e.g.
    ``example-regional-calendar.toml`` ->
    ``"example-regional-calendar"``), the same filename-is-the-identifier
    convention ``SourceConfig.source_id`` uses.

    ``page_urls`` are absolute page URLs on the hub's own site to scan --
    a hub has no ``site_url`` field of its own; every entry in
    ``page_urls`` must already be absolute (unlike
    ``discovery/listing.py``'s ``source.config["listing_urls"]``, which
    resolves bare paths against a source's ``site_url``).

    ``config`` is a free-form dict for hub-specific scan hints (e.g. a
    CSS selector narrowing which part of the page to scan) -- Hub Scan
    (ticket 003's other module) does not read anything from it yet; it
    exists so a future hub with unusual page structure has somewhere to
    put a hint without a schema change.
    """

    hub_id: str
    hub_name: str
    page_urls: list[str]
    config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_toml(cls, path: Path) -> HubConfig:
        """Parse and validate one hub TOML file.

        Raises:
            InvalidHubConfig: a required field (``hub_name`` or
                ``page_urls``) is missing.
            tomllib.TOMLDecodeError: the file is not valid TOML. Left
                unwrapped -- :func:`load_hubs` treats it the same as
                InvalidHubConfig (log and skip) but callers reading a
                single file directly may want to tell the two apart.
        """
        with open(path, "rb") as f:
            data = tomllib.load(f)

        missing = [name for name in _REQUIRED_FIELDS if name not in data]
        if missing:
            raise InvalidHubConfig(
                f"{path}: missing required field(s): {', '.join(missing)}"
            )

        return cls(
            hub_id=path.stem,
            hub_name=data["hub_name"],
            page_urls=data["page_urls"],
            config=data.get("config", {}),
        )


def load_hubs(directory: Path | None = None) -> list[HubConfig]:
    """Load and validate every ``*.toml`` file in ``directory``.

    A file that fails to parse as TOML, or is missing a required field,
    is logged as a warning and skipped; it never aborts the rest of the
    directory's load -- the same contract ``registry.loader.load_sources``
    gives the Source Registry.

    Args:
        directory: defaults to :data:`DEFAULT_HUBS_DIR` (the real seed
            hub registry) when omitted.
    """
    directory = directory or DEFAULT_HUBS_DIR
    hubs: list[HubConfig] = []
    for path in sorted(directory.glob("*.toml")):
        try:
            hubs.append(HubConfig.from_toml(path))
        except InvalidHubConfig as exc:
            logger.warning("Skipping invalid hub file: %s", exc)
        except tomllib.TOMLDecodeError as exc:
            logger.warning("Skipping malformed TOML file %s: %s", path, exc)
    return hubs
