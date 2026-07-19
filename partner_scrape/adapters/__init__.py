"""Adapter Framework: converts a registered source into canonical Events.

See ``sprint.md``'s Architecture > Adapter Framework for the design: the
``Adapter`` contract (``discover -> fetch -> extract``, chained by
:func:`run`), dispatched by ``SourceConfig.adapter_type`` via
:data:`ADAPTERS`. Adding a new adapter type is a one-line addition
below -- never a change to ``base.py``'s dispatch mechanism, as ticket
005's ``wp_rest``/``ical`` registration below demonstrates.
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
from partner_scrape.adapters.generic_html import GenericHtmlAdapter
from partner_scrape.adapters.ical import ICalAdapter
from partner_scrape.adapters.tec import TecRestAdapter
from partner_scrape.adapters.wordpress import WordPressRestAdapter

ADAPTERS["tec_rest"] = TecRestAdapter
ADAPTERS["wp_rest"] = WordPressRestAdapter
ADAPTERS["ical"] = ICalAdapter
ADAPTERS["generic_html"] = GenericHtmlAdapter

__all__ = [
    "Adapter",
    "EventRef",
    "RawResponse",
    "ADAPTERS",
    "UnknownAdapterType",
    "get_adapter",
    "run",
    "TecRestAdapter",
    "WordPressRestAdapter",
    "ICalAdapter",
    "GenericHtmlAdapter",
]
