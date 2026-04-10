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
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import scrapy
from scrapy.linkextractors import LinkExtractor

# Common .well-known paths worth probing.
_WELL_KNOWN_PATHS: list[str] = [
    "/.well-known/security.txt",
    "/.well-known/humans.txt",
    "/.well-known/change-password",
    "/.well-known/openid-configuration",
    "/.well-known/assetlinks.json",
    "/.well-known/apple-app-site-association",
]


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

#: Patterns to strip inline <script> and <style> blocks from saved HTML.
_STRIP_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)
_STRIP_STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)

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
        recrawl_days: float = 1.0,
        **kwargs,
    ):
        if not url:
            raise ValueError("The 'url' argument is required.")

        # Normalise scheme
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        self.start_url = url
        parsed = urlparse(url)
        self.allowed_domains_set: set[str] = {parsed.netloc}
        self.recrawl_after = timedelta(days=float(recrawl_days))

        # Root directory for this domain's mirror
        self.site_dir = os.path.join(output_dir, parsed.netloc)
        os.makedirs(self.site_dir, exist_ok=True)

        super().__init__(**kwargs)
        self.logger.info("Mirror started: %s  →  %s", url, self.site_dir)

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_www(netloc: str) -> str:
        return netloc[4:] if netloc.startswith("www.") else netloc

    def _is_allowed_domain(self, netloc: str) -> bool:
        """Check if *netloc* matches an allowed domain (ignoring www prefix)."""
        bare = self._strip_www(netloc)
        return any(self._strip_www(d) == bare for d in self.allowed_domains_set)

    # ------------------------------------------------------------------
    # Freshness check
    # ------------------------------------------------------------------

    def _is_recently_crawled(self, url: str) -> bool:
        """Return True if *url* has a meta.json newer than recrawl_after."""
        relpath = _url_to_relpath(url)
        meta_path = os.path.join(self.site_dir, relpath, "meta.json")
        try:
            with open(meta_path, encoding="utf-8") as fh:
                meta = json.load(fh)
            ts = datetime.fromisoformat(meta["timestamp"])
            age = datetime.now(timezone.utc) - ts
            return age < self.recrawl_after
        except (FileNotFoundError, KeyError, ValueError):
            return False

    # ------------------------------------------------------------------
    # Scrapy API
    # ------------------------------------------------------------------

    def _base_url(self) -> str:
        """Return the scheme + authority root of the start URL."""
        parsed = urlparse(self.start_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    async def start(self):
        # 1. Primary entry point
        yield scrapy.Request(
            self.start_url,
            callback=self.parse,
            errback=self.handle_error,
            dont_filter=True,
        )

        base = self._base_url()

        # 2. Try robots.txt to discover sitemap URLs
        yield scrapy.Request(
            f"{base}/robots.txt",
            callback=self._parse_robots,
            errback=self.handle_error,
            dont_filter=True,
        )

        # 3. Try the conventional sitemap location directly
        yield scrapy.Request(
            f"{base}/sitemap.xml",
            callback=self._parse_sitemap,
            errback=self.handle_error,
            dont_filter=True,
        )

        # 4. Probe common .well-known paths
        for wk_path in _WELL_KNOWN_PATHS:
            yield scrapy.Request(
                f"{base}{wk_path}",
                callback=self.parse,
                errback=self.handle_error,
                dont_filter=True,
            )

    # ------------------------------------------------------------------
    # Sitemap helpers
    # ------------------------------------------------------------------

    def _parse_robots(self, response):
        """Extract Sitemap: directives from robots.txt and follow them."""
        if response.status != 200:
            return
        self._save_raw(response)
        text = response.text if hasattr(response, "text") else response.body.decode("utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if line.lower().startswith("sitemap:"):
                sitemap_url = line.split(":", 1)[1].strip()
                if self._is_allowed_domain(urlparse(sitemap_url).netloc):
                    yield scrapy.Request(
                        sitemap_url,
                        callback=self._parse_sitemap,
                        errback=self.handle_error,
                        dont_filter=True,
                    )

    def _parse_sitemap(self, response):
        """Parse a sitemap (index or urlset) and yield requests for each entry."""
        if response.status != 200:
            return
        self._save_raw(response)
        try:
            root = ET.fromstring(response.body)
        except ET.ParseError:
            self.logger.debug("Failed to parse sitemap XML: %s", response.url)
            return

        # Strip XML namespace for easier tag matching
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"

        # Sitemap index → follow child sitemaps
        for sitemap in root.iter(f"{ns}sitemap"):
            loc = sitemap.findtext(f"{ns}loc")
            if loc and self._is_allowed_domain(urlparse(loc.strip()).netloc):
                yield scrapy.Request(
                    loc.strip(),
                    callback=self._parse_sitemap,
                    errback=self.handle_error,
                    dont_filter=True,
                )

        # URL set → crawl each page
        for url_el in root.iter(f"{ns}url"):
            loc = url_el.findtext(f"{ns}loc")
            if loc and self._is_allowed_domain(urlparse(loc.strip()).netloc):
                yield scrapy.Request(
                    loc.strip(),
                    callback=self.parse,
                    errback=self.handle_error,
                )

    # ------------------------------------------------------------------
    # Page handler
    # ------------------------------------------------------------------

    def parse(self, response):  # noqa: D102
        # Detect redirects to a related domain (e.g. www.x.org → x.org)
        # and add the new domain to the allowed set, but only if it's a
        # www/non-www variant of an already-allowed domain.
        resp_netloc = urlparse(response.url).netloc
        if resp_netloc not in self.allowed_domains_set:
            if self._is_allowed_domain(resp_netloc):
                self.allowed_domains_set.add(resp_netloc)
                self.logger.info(
                    "Redirect detected – added %s to allowed domains", resp_netloc
                )
            else:
                self.logger.debug("Ignoring off-site redirect: %s", response.url)
                return

        content_type = (
            response.headers.get("Content-Type", b"")
            .decode("utf-8", errors="replace")
        )
        ct_base = content_type.split(";")[0].strip().lower()

        # Only process HTML / XHTML pages
        is_html = "html" in ct_base or "xhtml" in ct_base
        if not is_html:
            return

        # Skip if this page was recently crawled
        if self._is_recently_crawled(response.url):
            self.logger.debug("Skipping (fresh): %s", response.url)
            return

        self._save_page(response)

        link_extractor = LinkExtractor(
            allow_domains=list(self.allowed_domains_set),
            deny_extensions=list(SKIP_EXTENSIONS),
        )

        for link in link_extractor.extract_links(response):
            parsed = urlparse(link.url)

            # Stay within the same domain(s)
            if parsed.netloc not in self.allowed_domains_set:
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

    def _save_raw(self, response) -> None:
        """Save a non-HTML response (robots.txt, sitemap XML, etc.) as-is."""
        relpath = _url_to_relpath(response.url)
        save_dir = os.path.join(self.site_dir, relpath)
        os.makedirs(save_dir, exist_ok=True)

        # Guess a sensible filename from the URL
        parsed_path = urlparse(response.url).path
        filename = os.path.basename(parsed_path) or "content"
        filepath = os.path.join(save_dir, filename)
        with open(filepath, "wb") as fh:
            fh.write(response.body)

        self.logger.debug("Saved raw  %s  →  %s", response.url, filepath)

    def _save_page(self, response) -> None:
        """Write content.html and meta.json for *response* to disk."""
        relpath = _url_to_relpath(response.url)
        save_dir = os.path.join(self.site_dir, relpath)
        os.makedirs(save_dir, exist_ok=True)

        # --- content (strip inline <script> and <style> tags) ----------------
        body = response.body
        encoding = response.encoding or "utf-8"
        try:
            html = body.decode(encoding, errors="replace")
        except (LookupError, UnicodeDecodeError):
            html = body.decode("utf-8", errors="replace")
        html = _STRIP_SCRIPT_RE.sub("", html)
        html = _STRIP_STYLE_RE.sub("", html)

        content_path = os.path.join(save_dir, "content.html")
        with open(content_path, "w", encoding="utf-8") as fh:
            fh.write(html)

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
