"""Adapter Framework: converts a registered source into canonical Events.

See ``sprint.md``'s Architecture > Adapter Framework for the design: the
``Adapter`` contract (``discover -> fetch -> extract``, chained by
:func:`run`), dispatched by ``SourceConfig.adapter_type`` via
:data:`ADAPTERS`. Adding a new adapter type (ticket 005's
``wp_rest``/``ical``) is a one-line addition below -- never a change to
``base.py``'s dispatch mechanism.
"""

from __future__ import annotations

from partner_scrape.adapters.base import (
    ADAPTERS,
    Adapter,
    EventRef,
    RawResponse,
    UnknownAdapterType,
    get_adapter,
    run,
)
from partner_scrape.adapters.tec import TecRestAdapter

ADAPTERS["tec_rest"] = TecRestAdapter

__all__ = [
    "Adapter",
    "EventRef",
    "RawResponse",
    "ADAPTERS",
    "UnknownAdapterType",
    "get_adapter",
    "run",
    "TecRestAdapter",
]
