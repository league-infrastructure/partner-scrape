"""
Parse local XML sitemap files from the mirror directory.
Handles both sitemap indexes and urlsets.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
      "image": "http://www.google.com/schemas/sitemap-image/1.1"}


@dataclass
class SitemapEntry:
    url: str
    lastmod: str = ""
    image_title: str = ""  # From <image:title> (useful for Wix)
    sitemap_file: str = ""


def parse_sitemap_file(xml_path: Path) -> list[SitemapEntry]:
    """Parse a single sitemap XML file and return URL entries."""
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        return []

    root = tree.getroot()
    tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
    entries = []

    if tag == "urlset":
        for url_el in root.findall("sm:url", NS):
            loc = url_el.findtext("sm:loc", "", NS)
            lastmod = url_el.findtext("sm:lastmod", "", NS)
            image_title = url_el.findtext(".//image:title", "", NS)
            if loc:
                entries.append(SitemapEntry(
                    url=loc, lastmod=lastmod, image_title=image_title,
                    sitemap_file=xml_path.name,
                ))
    elif tag == "sitemapindex":
        # Return the child sitemap URLs themselves
        for sm in root.findall("sm:sitemap", NS):
            loc = sm.findtext("sm:loc", "", NS)
            lastmod = sm.findtext("sm:lastmod", "", NS)
            if loc:
                entries.append(SitemapEntry(
                    url=loc, lastmod=lastmod, sitemap_file=xml_path.name,
                ))

    return entries


def get_domain_sitemaps(mirrors_dir: Path, domain: str) -> dict[str, Path]:
    """Find all sitemap XML files for a domain. Returns {filename: path}."""
    domain_dir = mirrors_dir / domain
    sitemaps = {}
    for xml_file in domain_dir.rglob("*.xml"):
        if xml_file.is_file():
            sitemaps[xml_file.name] = xml_file
    return sitemaps


def get_event_urls(mirrors_dir: Path, domain: str,
                   event_sitemap_names: list[str] | None = None) -> list[SitemapEntry]:
    """
    Get event-related URLs from a domain's sitemaps.

    If event_sitemap_names is provided, only parse those specific sitemaps.
    Otherwise, parse all sitemaps and filter by URL path patterns.
    """
    import re
    event_path_re = re.compile(
        r"/(events?|tribe_events|public-events?|science-events?|"
        r"programs?|courses?|camps?|classes|workshops?|training|calendar)(/|$)", re.I
    )

    sitemaps = get_domain_sitemaps(mirrors_dir, domain)
    entries = []

    if event_sitemap_names:
        # Parse only specific event sitemaps
        for name in event_sitemap_names:
            if name in sitemaps:
                entries.extend(parse_sitemap_file(sitemaps[name]))
    else:
        # Parse all sitemaps and filter by URL pattern
        for name, path in sitemaps.items():
            for entry in parse_sitemap_file(path):
                if event_path_re.search(entry.url):
                    entries.append(entry)

    return entries
