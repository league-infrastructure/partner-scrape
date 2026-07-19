"""Sitemap Discovery: resolves a source's sitemap into new/changed event URLs.

See ``sprint.md``'s Architecture > Sitemap Discovery, SUC-009: the first
real implementation of ``Adapter.discover()``'s deferred seam (sprint
001). ``discover_changed_urls`` is this package's one public entry
point -- ticket 002's ``generic_html`` adapter calls into it directly,
never the other way around.
"""

from __future__ import annotations

from partner_scrape.discovery.sitemap import discover_changed_urls

__all__ = ["discover_changed_urls"]
