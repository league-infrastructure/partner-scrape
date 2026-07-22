"""Site Export: publish current+upcoming Opportunities into the sibling site repo.

See sprint.md's Architecture > Site Export and writer.py's module
docstring for the single entry point, `export_opportunities()`, that
ticket 008's Pipeline calls.

Also re-exports sprint 005 ticket 005's Ad Content Export entry points
(`export_ads`, `load_ad_configs`) -- a separate, small data contract
(`ads.json`) publishing hand-authored League ad-slot content, structurally
parallel to `export_opportunities` but with no shared code (see
`export/ads.py`'s module docstring) -- and sprint 008 ticket 008's Event
Image Downloader (`EventImageDownloader`, see `export/images.py`'s
module docstring), which `pipeline.run()` constructs and wires into
`normalize.run()` via a plain callable, not an import from `normalize`.
"""

from __future__ import annotations

from partner_scrape.export.ads import AdConfig, export_ads, load_ad_configs
from partner_scrape.export.images import EventImageDownloader
from partner_scrape.export.writer import export_opportunities

__all__ = [
    "export_opportunities",
    "export_ads",
    "load_ad_configs",
    "AdConfig",
    "EventImageDownloader",
]
