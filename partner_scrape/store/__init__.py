"""Event Store: a durable, cross-run table of canonical Events.

See `event_store.py`'s module docstring for the full design. This is the
foundation for incremental/self-updating scraping -- pipeline
integration (deciding when a run reads from / writes to the store) is a
separate, later step, not part of this module.
"""

from __future__ import annotations

from partner_scrape.store.event_store import EventStore

__all__ = [
    "EventStore",
]
