"""`EventImageDownloader`: the Event Image Downloader module.

Sprint 008 ticket 008 (issue 19, scraper half; see sprint.md Architecture
> Step 3 "Event Image Downloader" and Step 4's diagram). Given one
`Event`'s already-extracted `image_url` -- populated by the Extraction
Ladder's JSON-LD/OpenGraph rungs (`extract/ladder.py`) or by one of four
adapters (`leaguesync`, `localist`, `bibliocommons`, `tec`) -- this
module fetches it, validates it is really an image, quality-gates it
(rejects tracking pixels/spacers/undersized/non-image responses), dedupes
identical images across events, and self-hosts a local copy. No new
extraction is added here (sprint.md's Out of Scope); this module only
turns an already-populated remote URL into a self-hosted local file.

`pipeline.run()` wires one `EventImageDownloader` instance per export run
into `normalize.run()` via the `image_resolver` callable parameter (a
plain `Callable[[str], str]`, not an import of this class) -- keeping
`normalize` free of any dependency on `export`, matching sprint.md's
documented one-way module-dependency direction ("Export ... depends
one-way on Normalize"; the new edge is Export -> this module, not
Normalize -> this module). `normalize.run.Opportunity.image_src` ends up
holding this call's return value, exported automatically by
`export/writer.py`'s `SITE_SCHEMA_FIELDS` (no writer.py edit needed).

## Quality gate

A call to `.download(image_url)` rejects (returns `""`) at the first of:

1. `image_url` is empty, blank, or not `http(s)://` -- never even
   attempts a fetch (`file://`/`data:`/other schemes are refused before
   any I/O, matching sprint.md's Migration Concern that a downloaded
   asset "must not execute or interpret the downloaded bytes as anything
   other than a static image asset").
2. The HTTP response is not 2xx, or its body is empty.
3. Its `Content-Type` header, when present, does not start with
   `image/`.
4. The body exceeds `MAX_IMAGE_BYTES` -- a size-safety cap.
5. The body does not structurally decode as a real PNG, JPEG, GIF, or
   WebP (see `_sniff_dimensions`) -- this is this module's "real
   image-decode check" (sprint.md's Migration Concern: "verify the
   fetched response is actually an image ... not just a URL pattern"),
   catching non-image content masquerading with an image Content-Type,
   truncated downloads, and HTML error pages.
6. The decoded width or height is below `MIN_DIMENSION` pixels --
   rejects 1x1 tracking pixels and small spacer graphics.

Survivors are deduped by SHA-256 of their raw bytes: an image already
stored earlier in the same `EventImageDownloader`'s lifetime (the common
case of a generic partner-site banner reused across many unrelated
events, sprint.md Approach step 2) reuses its existing filename rather
than writing a duplicate file.

**Resize-on-fetch (sprint 025 ticket 002).** Pixel-dimension downscaling
was intentionally *not* implemented as of ticket 008 -- this docstring's
own earlier text named the exact trigger for revisiting that call ("if
genuine pixel downscaling becomes a real operational need, revisit
adding an image-processing dependency in a follow-up ticket"). Sprint
025's own measurement of stem-ecosystem's 631 already-self-hosted images
was that trigger: ~405MB total, mean 655KB/median 303KB, 147 files over
1MB accounting for 67% of total bytes (including a 5.2MB
raw-camera-original JPEG served as a card thumbnail). `MAX_IMAGE_BYTES`
bounds the *fetched* payload but was never a substitute for true
resampling of what gets *stored*.

A newly-downloaded image (only -- the 631 legacy images already
self-hosted before this ticket are explicitly out of scope; this module
never re-processes an already-stored file) whose long edge exceeds
`RESIZE_LONG_EDGE` is downscaled, aspect ratio preserved, via Pillow's
`Image.thumbnail`, and re-encoded: JPEG at `RESIZE_JPEG_QUALITY` for an
opaque image, PNG for one with an alpha channel (so transparency isn't
silently lost). GIF is passed through unresized regardless of size --
`Image.thumbnail` only touches a GIF's first frame, which would silently
drop animation. An image already within the cap on both dimensions is
written through unchanged, byte-for-byte -- no unnecessary re-encode.
See `_resize_if_needed`.

This is the one exception to `fetch/fetcher.py`'s "zero new
dependencies" rationale (echoed in this module's own `UrllibImageFetcher`
docstring, which still holds for *fetching*): this module now takes a
hard dependency on Pillow (`pyproject.toml`'s `dependencies`, not an
optional extra like `playwright` -- no external browser/binary is
needed).

A missing, unreachable, or rejected image never raises -- `.download()`
returns `""`, and the caller leaves `Opportunity.image_src` empty,
exactly SUC-008's documented Alternate Flow ("the record exports
normally otherwise").
"""

from __future__ import annotations

import hashlib
import io
import logging
import struct
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PIL import Image

logger = logging.getLogger(__name__)

#: Polite default User-Agent, matching `fetch/fetcher.py`'s own default.
DEFAULT_USER_AGENT = "STEM-Calendar-Bot/1.0 (educational research)"

DEFAULT_TIMEOUT = 15.0

#: Reject any response body larger than this many bytes -- see the
#: module docstring's "Pixel-dimension downscaling is intentionally not
#: implemented" note for why this stands in for true resampling.
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB

#: Minimum width AND height, in pixels, an image must have to survive the
#: quality gate -- rejects 1x1 tracking pixels and small spacer graphics
#: while still accepting a small-but-legitimate square photo used as an
#: event's image.
MIN_DIMENSION = 80

#: Resize-on-fetch long-edge cap, in pixels (sprint 025 ticket 002). A
#: newly-downloaded image with either dimension above this is downscaled
#: (aspect ratio preserved) before being written -- see
#: `_resize_if_needed` and the module docstring's "Resize-on-fetch"
#: section for the stem-ecosystem measurement that motivated this value.
RESIZE_LONG_EDGE = 1600

#: JPEG re-encode quality used by `_resize_if_needed` for an opaque
#: resized image -- 80 is a conventional "visually lossless enough for a
#: web card thumbnail" quality/size tradeoff point, well above JPEG's
#: perceptible-artifact range (roughly <60) and well below the
#: diminishing-returns range near 100.
RESIZE_JPEG_QUALITY = 80


@dataclass
class ImageFetchResponse:
    """One raw binary HTTP response.

    Deliberately separate from `fetch.fetcher.FetchResponse`: that
    dataclass's `body` is UTF-8-decoded `str` (fine for HTML), which
    would corrupt binary image bytes -- this module needs its own,
    parallel, binary-safe response shape.
    """

    url: str
    status: int
    headers: dict[str, str]
    body: bytes


class ImageFetcher(Protocol):
    """Injectable seam for retrieving one image URL's raw bytes.

    The same DI pattern `fetch.fetcher.Fetcher` already establishes for
    text responses (sprint.md Design Rationale precedent). Implementations
    must not raise: a network failure, timeout, or non-2xx status is
    reported via `status`/`body`, mirroring `Fetcher`'s own "must not
    raise" contract, so `EventImageDownloader` never needs a try/except
    around a well-behaved implementation's call (it wraps the call in one
    anyway, as defense in depth -- see `.download()`).
    """

    def get(self, url: str) -> ImageFetchResponse:
        """Issue a GET request to ``url``, returning its raw bytes."""
        ...


class UrllibImageFetcher:
    """The real `ImageFetcher`: stdlib `urllib.request`, no new
    dependency -- mirrors `fetch.fetcher.UrllibFetcher`'s "zero new
    dependencies" rationale exactly, just binary-safe."""

    def __init__(
        self, user_agent: str = DEFAULT_USER_AGENT, timeout: float = DEFAULT_TIMEOUT
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout

    def get(self, url: str) -> ImageFetchResponse:
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read()
                return ImageFetchResponse(
                    url=url,
                    status=response.status,
                    headers=dict(response.headers.items()),
                    body=body,
                )
        except urllib.error.HTTPError as exc:
            return ImageFetchResponse(url=url, status=exc.code, headers={}, body=b"")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            # Covers DNS failures, connection resets, timeouts, and
            # malformed URLs -- none of these are fatal to the run
            # (SUC-008's Alternate Flow: "image_url is ... unreachable
            # ... image_src stays empty").
            logger.info("Event image fetch failed for %s: %s", url, exc)
            return ImageFetchResponse(url=url, status=0, headers={}, body=b"")


def _content_type(headers: dict[str, str]) -> str:
    """Case-insensitive `Content-Type` lookup, stripped of any
    `; charset=...` parameter. HTTP header names are case-insensitive,
    but `dict(response.headers.items())` preserves whatever case the
    server actually sent."""
    for name, value in headers.items():
        if name.lower() == "content-type":
            return value.split(";")[0].strip().lower()
    return ""


def _png_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _gif_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 10 or data[:6] not in (b"GIF87a", b"GIF89a"):
        return None
    width, height = struct.unpack("<HH", data[6:10])
    return width, height


#: JPEG Start-Of-Frame marker bytes that carry frame dimensions
#: (baseline, extended/progressive, and their arithmetic-coded/lossless
#: variants). Deliberately excludes 0xC4 (DHT, Huffman table -- not a
#: frame header) and 0xC8/0xCC (JPG extension / DAC -- not dimension
#: bearing), matching the JPEG spec's own SOFn marker set.
_JPEG_SOF_MARKERS = frozenset(
    {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
)


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    length = len(data)
    i = 2
    while i < length - 1:
        if data[i] != 0xFF:
            i += 1
            continue
        # A marker may be preceded by any number of 0xFF fill bytes.
        while i < length and data[i] == 0xFF:
            i += 1
        if i >= length:
            return None
        marker = data[i]
        i += 1
        if marker == 0x01 or 0xD0 <= marker <= 0xD9:
            # TEM, RSTn, SOI, EOI: standalone, no length field follows.
            continue
        if i + 2 > length:
            return None
        seg_len = struct.unpack(">H", data[i : i + 2])[0]
        if marker in _JPEG_SOF_MARKERS:
            if i + 7 > length:
                return None
            height, width = struct.unpack(">HH", data[i + 3 : i + 7])
            return width, height
        i += seg_len
    return None


def _webp_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    if chunk == b"VP8X":
        width = 1 + (data[24] | (data[25] << 8) | (data[26] << 16))
        height = 1 + (data[27] | (data[28] << 8) | (data[29] << 16))
        return width, height
    if chunk == b"VP8 " and data[23:26] == b"\x9d\x01\x2a":
        width = struct.unpack("<H", data[26:28])[0] & 0x3FFF
        height = struct.unpack("<H", data[28:30])[0] & 0x3FFF
        return width, height
    # VP8L (lossless WebP) dimensions require bit-level unpacking this
    # module deliberately doesn't implement -- rare for scraped event
    # photos in practice (almost always JPEG/PNG, occasionally GIF/VP8X).
    # Treated as "can't decode", i.e. rejected by the quality gate, not
    # crashed.
    return None


_DIMENSION_PARSERS = (_png_dimensions, _jpeg_dimensions, _gif_dimensions, _webp_dimensions)

#: Maps each parser above to the filename extension its format uses,
#: applied in the same order `_sniff_dimensions` tries them.
_EXTENSIONS = (".png", ".jpg", ".gif", ".webp")


def _sniff(data: bytes) -> tuple[int, tuple[int, int]] | None:
    """Try each known format's parser in turn; return `(parser_index,
    (width, height))` for the first that recognizes `data`, or `None` if
    none do. See `_sniff_dimensions` for the public-facing wrapper."""
    for index, parser in enumerate(_DIMENSION_PARSERS):
        dimensions = parser(data)
        if dimensions is not None:
            return index, dimensions
    return None


def _sniff_dimensions(data: bytes) -> tuple[int, int] | None:
    """Parse `data`'s real pixel width/height by reading its image
    container format directly (PNG/JPEG/GIF/WebP magic bytes + embedded
    header fields) -- this *is* this module's "real image-decode check"
    (see module docstring, Quality gate step 5). Returns `None` for
    anything that isn't a structurally valid image in one of these four
    formats.

    This validates container structure, not full pixel-level integrity
    (e.g. a PNG with a correct `IHDR` chunk but corrupted `IDAT` data
    would still parse here) -- a deliberate scope decision: this is a
    fetch-time quality gate meant to reject non-images and tracking
    pixels, not a general-purpose image repair/validation tool.
    """
    found = _sniff(data)
    return found[1] if found is not None else None


def _extension_for(data: bytes) -> str:
    """The filename extension for whichever format `_sniff_dimensions`
    actually recognized in `data`. Only ever called after `_sniff`
    already succeeded, so a `None` result here would indicate a caller
    bug -- falls back to `.jpg` rather than raising, since a wrong
    extension on an already-validated image is cosmetic, not a
    correctness problem."""
    found = _sniff(data)
    if found is None:
        return ".jpg"
    return _EXTENSIONS[found[0]]


def _resize_if_needed(data: bytes, dimensions: tuple[int, int], extension: str) -> bytes:
    """Return `data`, downscaled and re-encoded if it exceeds
    `RESIZE_LONG_EDGE` on either dimension; otherwise `data` unchanged,
    byte-for-byte (see module docstring's "Resize-on-fetch" section).

    `extension` (the format `_extension_for` sniffed from `data`) gates
    two passthrough cases before any Pillow decode is attempted:
    `".gif"` is always passed through -- `Image.thumbnail` only touches
    a GIF's first frame, which would silently drop animation -- and an
    image already within the cap on both `dimensions` needs no
    re-encode at all. Only PNG/JPEG/WebP inputs above the cap actually
    reach Pillow.

    An image with an alpha channel (`RGBA`/`LA` mode, or `P`-mode with a
    `transparency` entry) is re-encoded as PNG so transparency survives;
    every other (opaque) image is re-encoded as JPEG at
    `RESIZE_JPEG_QUALITY`, regardless of its original format -- matching
    this ticket's acceptance criteria, not a format-preserving resize.
    """
    width, height = dimensions
    if extension == ".gif":
        return data
    if width <= RESIZE_LONG_EDGE and height <= RESIZE_LONG_EDGE:
        return data

    with Image.open(io.BytesIO(data)) as opened:
        opened.load()
        image = opened.copy()
    image.thumbnail((RESIZE_LONG_EDGE, RESIZE_LONG_EDGE), Image.Resampling.LANCZOS)

    has_alpha = image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    )
    buffer = io.BytesIO()
    if has_alpha:
        image.convert("RGBA").save(buffer, format="PNG")
    else:
        image.convert("RGB").save(buffer, format="JPEG", quality=RESIZE_JPEG_QUALITY)
    return buffer.getvalue()


class EventImageDownloader:
    """Fetches, validates, quality-gates, dedupes, and self-hosts one
    Event's `image_url` per `.download()` call.

    Construct **one instance per export run** and reuse it for every
    surviving `Opportunity` -- the dedup cache (`_hash_to_filename`) is
    per-instance state, so reusing one instance across a whole run is
    what makes the dedup requirement work (see module docstring).
    `pipeline.run()` constructs the real instance and wires its
    `.download` method through as `normalize.run()`'s `image_resolver`
    parameter; tests inject a fixture `ImageFetcher` here so no test
    touches a real socket.
    """

    def __init__(
        self,
        dest_dir: str | Path,
        *,
        fetcher: ImageFetcher | None = None,
        min_dimension: int = MIN_DIMENSION,
        max_bytes: int = MAX_IMAGE_BYTES,
    ) -> None:
        self.dest_dir = Path(dest_dir)
        self.fetcher = fetcher or UrllibImageFetcher()
        self.min_dimension = min_dimension
        self.max_bytes = max_bytes
        self._hash_to_filename: dict[str, str] = {}

    def download(self, image_url: str) -> str:
        """Return the self-hosted filename for `image_url`'s image, or
        `""` if `image_url` is missing, unreachable, or fails the
        quality gate (SUC-008's Alternate Flow). Never raises."""
        if not image_url or not image_url.strip():
            return ""
        if not image_url.startswith(("http://", "https://")):
            # Refuses non-http(s) schemes (file:, data:, javascript:, ...)
            # before any I/O -- see module docstring's Quality gate step 1.
            return ""

        try:
            response = self.fetcher.get(image_url)
        except Exception:
            # Defense in depth: the real UrllibImageFetcher never raises
            # (see its own docstring), but a test double or a future
            # ImageFetcher implementation might -- must still degrade
            # gracefully (SUC-008's Alternate Flow).
            logger.info("Event image fetch raised for %s", image_url, exc_info=True)
            return ""

        if response.status < 200 or response.status >= 300 or not response.body:
            return ""

        content_type = _content_type(response.headers)
        if content_type and not content_type.startswith("image/"):
            return ""

        if len(response.body) > self.max_bytes:
            return ""

        dimensions = _sniff_dimensions(response.body)
        if dimensions is None:
            return ""
        width, height = dimensions
        if width < self.min_dimension or height < self.min_dimension:
            return ""

        # Resize-on-fetch (sprint 025 ticket 002): applies only to this
        # newly-fetched image, never to anything already written by an
        # earlier `.download()` call. The dedup hash/filename below is
        # computed from these *final* bytes, not `response.body` --
        # two images that resize to identical final bytes dedupe to one
        # written file, matching the acceptance criteria.
        final_bytes = _resize_if_needed(response.body, dimensions, _extension_for(response.body))

        digest = hashlib.sha256(final_bytes).hexdigest()
        cached = self._hash_to_filename.get(digest)
        if cached is not None:
            return cached

        filename = f"{digest[:16]}{_extension_for(final_bytes)}"
        self.dest_dir.mkdir(parents=True, exist_ok=True)
        (self.dest_dir / filename).write_bytes(final_bytes)
        self._hash_to_filename[digest] = filename
        return filename
