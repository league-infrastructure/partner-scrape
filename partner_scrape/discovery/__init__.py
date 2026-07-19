"""Discovery: strategies for resolving a source into fetchable event URLs.

See ``sprint.md``'s Architecture > Sitemap Discovery (SUC-009) and
Listing-Page Discovery (SUC-014) -- two independent, sibling discovery
strategies. ``discover_changed_urls`` (sitemap-diff, ticket 001 of
sprint 002) and ``discover_via_listing`` (listing-page crawl, no
diffing, ticket 003 of sprint 003) are this package's public entry
points -- the ``generic_html`` and ``listing_html`` adapters call into
them directly, never the other way around.
"""

from __future__ import annotations

from partner_scrape.discovery.listing import discover_via_listing
from partner_scrape.discovery.sitemap import discover_changed_urls

__all__ = ["discover_changed_urls", "discover_via_listing"]
