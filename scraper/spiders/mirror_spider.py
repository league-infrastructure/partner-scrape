"""
MirrorSpider – crawls a single partner website and saves every text-based
page as two files inside data/mirrors/{domain}/{url_path}/:

  content.html  – the raw response body
  meta.json     – URL, HTTP status, response headers, crawl timestamp

Binary resources (images, video, audio, fonts, archives, …) are
intentionally skipped; only HTML / plain-text pages are saved.
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import scrapy
from scrapy.linkextractors import LinkExtractor


# ---------------------------------------------------------------------------
# File-extension filter
# ---------------------------------------------------------------------------

#: Extensions whose URLs we never follow or save.
SKIP_EXTENSIONS: frozenset = frozenset(
    {
        # Images
        "jpg", "jpeg", "png", "gif", "webp", "svg", "ico",
        "bmp", "tiff", "tif", "avif", "heic", "heif",
        # Video
        "mp4", "avi", "mov", "wmv", "flv", "mkv", "webm", "m4v", "3gp", "ogv",
        # Audio
        "mp3", "wav", "ogg", "aac", "flac", "m4a", "wma", "opus",
        # Archives / executables
        "zip", "tar", "gz", "bz2", "7z", "rar", "xz", "zst",
        "exe", "dmg", "pkg", "msi", "deb", "rpm", "sh",
        # Fonts
        "woff", "woff2", "ttf", "eot", "otf",
        # Binary documents
        "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
        # Misc binary
        "bin", "dat", "db", "sqlite", "pyc",
    }
)

#: Content-type prefixes that indicate a non-text response we should skip.
_SKIP_CT_RE = re.compile(
    r"^(image/|video/|audio/|application/octet-stream"
    r"|application/zip|application/x-|application/vnd\.)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# URL → filesystem path helpers
# ---------------------------------------------------------------------------

_UNSAFE_CHARS_RE = re.compile(r'[<>:"|\\*\x00-\x1f]')


def _url_to_relpath(url: str) -> str:
    """
    Convert a URL to a relative file-system path used inside the mirror
    directory for a domain.

    Examples
    --------
    ``https://example.com/``          → ``_index``
    ``https://example.com/about``     → ``about``
    ``https://example.com/a/b/``      → ``a/b``
    ``https://example.com/?foo=bar``  → ``_index__q_<hash>``
    ``https://example.com/page?x=1``  → ``page__q_<hash>``
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")

    if not path:
        path = "_index"

    # Append a short hash of the query string to distinguish paginated URLs.
    # SHA-256 is used; we truncate to 8 hex chars for a compact filename.
    if parsed.query:
        qhash = hashlib.sha256(parsed.query.encode()).hexdigest()[:8]
        path = f"{path}__q_{qhash}"

    # Sanitise per-segment (replace unsafe chars, cap length)
    segments = [
        _UNSAFE_CHARS_RE.sub("_", seg)[:200]
        for seg in path.split("/")
        if seg
    ]
    return "/".join(segments) if segments else "_index"


# ---------------------------------------------------------------------------
# Spider
# ---------------------------------------------------------------------------


class MirrorSpider(scrapy.Spider):
    """Crawl a single domain and save a full mirror of all text pages."""

    name = "mirror"

    def __init__(
        self,
        url: str | None = None,
        output_dir: str = "data/mirrors",
        **kwargs,
    ):
        if not url:
            raise ValueError("The 'url' argument is required.")

        # Normalise scheme
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        self.start_url = url
        parsed = urlparse(url)
        self.allowed_domain: str = parsed.netloc

        # Root directory for this domain's mirror
        self.site_dir = os.path.join(output_dir, self.allowed_domain)
        os.makedirs(self.site_dir, exist_ok=True)

        super().__init__(**kwargs)
        self.logger.info("Mirror started: %s  →  %s", url, self.site_dir)

    # ------------------------------------------------------------------
    # Scrapy API
    # ------------------------------------------------------------------

    async def start(self):
        yield scrapy.Request(
            self.start_url,
            callback=self.parse,
            errback=self.handle_error,
            dont_filter=True,
        )

    def parse(self, response):  # noqa: D102
        content_type = (
            response.headers.get("Content-Type", b"")
            .decode("utf-8", errors="replace")
        )
        ct_base = content_type.split(";")[0].strip().lower()

        # Save text-based pages; skip images, video, fonts, etc.
        if not _SKIP_CT_RE.match(ct_base):
            self._save_page(response)

        # Only extract links from HTML/XHTML responses
        if "html" not in ct_base and "xhtml" not in ct_base:
            return

        link_extractor = LinkExtractor(
            allow_domains=[self.allowed_domain],
            deny_extensions=list(SKIP_EXTENSIONS),
        )

        for link in link_extractor.extract_links(response):
            parsed = urlparse(link.url)

            # Stay within the same domain
            if parsed.netloc != self.allowed_domain:
                continue

            # Double-check the path extension
            path_lower = parsed.path.lower()
            ext = (
                path_lower.rsplit(".", 1)[-1]
                if "." in path_lower.split("/")[-1]
                else ""
            )
            if ext in SKIP_EXTENSIONS:
                continue

            yield scrapy.Request(
                link.url,
                callback=self.parse,
                errback=self.handle_error,
            )

    def handle_error(self, failure):
        self.logger.warning(
            "Request failed: %s  —  %s",
            failure.request.url,
            failure.value,
        )

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def _save_page(self, response) -> None:
        """Write content.html and meta.json for *response* to disk."""
        relpath = _url_to_relpath(response.url)
        save_dir = os.path.join(self.site_dir, relpath)
        os.makedirs(save_dir, exist_ok=True)

        # --- content ---------------------------------------------------------
        content_path = os.path.join(save_dir, "content.html")
        with open(content_path, "wb") as fh:
            fh.write(response.body)

        # --- metadata (URL + HTTP headers) -----------------------------------
        headers: dict[str, list[str]] = {}
        for raw_key, raw_values in response.headers.items():
            key = (
                raw_key.decode("utf-8", errors="replace")
                if isinstance(raw_key, bytes)
                else raw_key
            )
            headers[key] = [
                v.decode("utf-8", errors="replace") if isinstance(v, bytes) else v
                for v in raw_values
            ]

        meta = {
            "url": response.url,
            "status": response.status,
            "headers": headers,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        meta_path = os.path.join(save_dir, "meta.json")
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2, ensure_ascii=False)

        self.logger.debug("Saved  %s  →  %s", response.url, save_dir)
