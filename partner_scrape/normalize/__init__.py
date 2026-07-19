"""Normalize & Dedup: canonical Events -> deduplicated `Opportunity` records.

See sprint.md's Architecture > Normalize & Dedup and `run.py`'s module
docstring for the single entry point, `run()`, that ticket 008's
Pipeline calls.
"""

from __future__ import annotations

from partner_scrape.normalize.run import Opportunity, run

__all__ = ["Opportunity", "run"]
