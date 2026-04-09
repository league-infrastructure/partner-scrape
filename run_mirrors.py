#!/usr/bin/env python3
"""
run_mirrors.py – Mirror all partner websites listed in the partners CSV.

Usage
-----
# Mirror all partners (reads data/partners_viable.csv by default):
    python run_mirrors.py

# Mirror only the first 3 partners (useful for testing):
    python run_mirrors.py --limit 3

# Skip domains that already have mirrored content:
    python run_mirrors.py --resume

# Mirror a single URL (bypasses the CSV entirely):
    python run_mirrors.py --url https://www.example.com

# Show help:
    python run_mirrors.py --help

Output
------
Each partner's pages are saved under::

    data/mirrors/{domain}/{url_path}/content.html
    data/mirrors/{domain}/{url_path}/meta.json

where {domain} is the partner's hostname (e.g. ``www.example.com``) and
{url_path} mirrors the URL path structure of each crawled page.
"""

import argparse
import csv
import logging
import os
import sys
from urllib.parse import urlparse

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from scraper.spiders.mirror_spider import MirrorSpider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("run_mirrors")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def read_partners(csv_file: str) -> list[dict]:
    """Return a list of ``{name, url}`` dicts from the partners CSV."""
    partners = []
    with open(csv_file, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            url = row.get("website", "").strip()
            name = row.get("name", "").strip()
            if url and url.startswith(("http://", "https://")):
                partners.append({"name": name, "url": url})
    return partners


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mirror partner websites for offline data extraction.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--csv",
        default="data/partners_viable.csv",
        metavar="PATH",
        help="Path to the partners CSV file (default: data/partners_viable.csv)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/mirrors",
        metavar="DIR",
        help="Root directory for mirrored sites (default: data/mirrors)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Mirror only the first N partners (useful for testing)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip partners whose mirror directory already contains files",
    )
    parser.add_argument(
        "--url",
        metavar="URL",
        help="Mirror a single URL instead of reading the partners CSV",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Build list of sites to mirror
    # ------------------------------------------------------------------
    if args.url:
        partners = [{"name": "cli", "url": args.url}]
    else:
        if not os.path.exists(args.csv):
            logger.error("CSV file not found: %s", args.csv)
            sys.exit(1)
        partners = read_partners(args.csv)
        logger.info("Loaded %d partners from %s", len(partners), args.csv)

    if args.limit:
        partners = partners[: args.limit]

    if args.resume:
        remaining = []
        for p in partners:
            domain = urlparse(p["url"]).netloc
            site_dir = os.path.join(args.output_dir, domain)
            if os.path.isdir(site_dir) and os.listdir(site_dir):
                logger.info("Skipping (already mirrored): %s", p["url"])
            else:
                remaining.append(p)
        partners = remaining
        logger.info("%d sites remaining after --resume filter", len(partners))

    if not partners:
        logger.info("Nothing to mirror.")
        return

    # ------------------------------------------------------------------
    # Schedule all crawls in one Scrapy CrawlerProcess
    # ------------------------------------------------------------------
    settings = get_project_settings()
    process = CrawlerProcess(settings)

    for partner in partners:
        logger.info("Scheduling mirror: %s  (%s)", partner["name"], partner["url"])
        process.crawl(
            MirrorSpider,
            url=partner["url"],
            output_dir=args.output_dir,
        )

    logger.info("Starting %d crawl(s) …", len(partners))
    process.start()
    logger.info("All mirrors complete.")


if __name__ == "__main__":
    main()
