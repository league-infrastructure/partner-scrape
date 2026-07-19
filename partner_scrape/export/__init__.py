"""Site Export: publish current+upcoming Opportunities into the sibling site repo.

See sprint.md's Architecture > Site Export and writer.py's module
docstring for the single entry point, `export_opportunities()`, that
ticket 008's Pipeline calls.
"""

from __future__ import annotations

from partner_scrape.export.writer import export_opportunities

__all__ = ["export_opportunities"]
