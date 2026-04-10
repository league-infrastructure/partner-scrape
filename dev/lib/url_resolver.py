"""
Map URLs from sitemaps to local mirror filesystem paths.
Reuses the same _url_to_relpath logic from scraper/spiders/mirror_spider.py.
"""

import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

_UNSAFE_CHARS_RE = re.compile(r'[<>:"|\\*\x00-\x1f]')


def url_to_relpath(url: str) -> str:
    """Convert a URL to a relative file-system path used inside the mirror."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        path = "_index"
    if parsed.query:
        qhash = hashlib.sha256(parsed.query.encode()).hexdigest()[:8]
        path = f"{path}__q_{qhash}"
    segments = [
        _UNSAFE_CHARS_RE.sub("_", seg)[:200]
        for seg in path.split("/")
        if seg
    ]
    return "/".join(segments) if segments else "_index"


def resolve(mirrors_dir: Path, domain: str, url: str) -> Path | None:
    """Resolve a URL to its local content.html path. Returns None if not found."""
    relpath = url_to_relpath(url)
    content_path = mirrors_dir / domain / relpath / "content.html"
    if content_path.exists():
        return content_path
    return None


def domain_from_url(url: str) -> str:
    """Extract domain from a URL."""
    return urlparse(url).netloc
