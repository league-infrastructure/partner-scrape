"""Tests for partner_scrape.export.images: the Event Image Downloader.

Every test injects a fixture `ImageFetcher` (never `UrllibImageFetcher`)
so no test touches a real socket -- mirrors `test_export.py`'s own "no
live HTTP ... ever" convention. Fixture image bytes are built by hand
from each format's real container structure (PNG `IHDR`, JPEG `SOF0`,
GIF header, WebP `VP8X`) rather than loaded from binary files, so these
tests exercise `_sniff_dimensions`'s actual byte-level parsing against
spec-compliant layouts, not a stand-in.
"""

from __future__ import annotations

import struct

from partner_scrape.export.images import (
    EventImageDownloader,
    ImageFetchResponse,
    _extension_for,
    _sniff_dimensions,
)


def _png_bytes(width: int, height: int) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr + b"\x00\x00\x00\x00"


def _jpeg_bytes(width: int, height: int) -> bytes:
    # SOF0 (baseline): length(2) + precision(1) + height(2) + width(2) +
    # num_components(1) + one 3-byte component descriptor.
    component = bytes([1, 0x11, 0])
    payload = struct.pack(">BHHB", 8, height, width, 1) + component
    seg_len = len(payload) + 2
    return b"\xff\xd8" + b"\xff\xc0" + struct.pack(">H", seg_len) + payload + b"\xff\xd9"


def _gif_bytes(width: int, height: int) -> bytes:
    return b"GIF89a" + struct.pack("<HH", width, height) + b"\x00" * 3


def _webp_vp8x_bytes(width: int, height: int) -> bytes:
    w_minus1 = width - 1
    h_minus1 = height - 1
    dims = bytes(
        [
            w_minus1 & 0xFF, (w_minus1 >> 8) & 0xFF, (w_minus1 >> 16) & 0xFF,
            h_minus1 & 0xFF, (h_minus1 >> 8) & 0xFF, (h_minus1 >> 16) & 0xFF,
        ]
    )
    chunk_data = b"\x00\x00\x00\x00" + dims
    riff_body = b"WEBP" + b"VP8X" + struct.pack("<I", len(chunk_data)) + chunk_data
    return b"RIFF" + struct.pack("<I", len(riff_body)) + riff_body


LARGE_JPEG = _jpeg_bytes(800, 600)
LARGE_PNG = _png_bytes(1024, 768)
TINY_JPEG = _jpeg_bytes(2, 2)


class _FakeFetcher:
    """A scripted `ImageFetcher`: one canned response per URL, and a call
    log so tests can assert whether/how many times `.get()` was invoked
    (e.g. dedup should only fetch each distinct URL once)."""

    def __init__(self, responses: dict[str, ImageFetchResponse]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str) -> ImageFetchResponse:
        self.calls.append(url)
        if url not in self.responses:
            raise AssertionError(f"unexpected URL fetched: {url!r}")
        return self.responses[url]


class _RaisingFetcher:
    """An `ImageFetcher` that raises -- proves `.download()`'s defense-in-
    depth try/except (see that method's docstring)."""

    def get(self, url: str) -> ImageFetchResponse:
        raise RuntimeError("boom")


def _ok(body: bytes, content_type: str = "image/jpeg") -> ImageFetchResponse:
    return ImageFetchResponse(
        url="https://example.org/x", status=200, headers={"Content-Type": content_type}, body=body
    )


class TestDimensionSniffing:
    def test_png_dimensions_parsed_from_ihdr(self):
        assert _sniff_dimensions(_png_bytes(400, 300)) == (400, 300)

    def test_jpeg_dimensions_parsed_from_sof0(self):
        assert _sniff_dimensions(_jpeg_bytes(640, 480)) == (640, 480)

    def test_gif_dimensions_parsed_from_header(self):
        assert _sniff_dimensions(_gif_bytes(200, 100)) == (200, 100)

    def test_webp_vp8x_dimensions_parsed(self):
        assert _sniff_dimensions(_webp_vp8x_bytes(500, 250)) == (500, 250)

    def test_garbage_bytes_do_not_parse_as_any_format(self):
        assert _sniff_dimensions(b"not an image, just some html<html>") is None

    def test_truncated_png_does_not_parse(self):
        assert _sniff_dimensions(b"\x89PNG\r\n\x1a\n\x00\x00") is None

    def test_extension_matches_sniffed_format(self):
        assert _extension_for(_png_bytes(10, 10)) == ".png"
        assert _extension_for(_jpeg_bytes(10, 10)) == ".jpg"
        assert _extension_for(_gif_bytes(10, 10)) == ".gif"
        assert _extension_for(_webp_vp8x_bytes(10, 10)) == ".webp"


class TestQualityGate:
    def test_missing_image_url_is_rejected_without_any_fetch(self, tmp_path):
        fetcher = _FakeFetcher({})
        downloader = EventImageDownloader(tmp_path, fetcher=fetcher)

        assert downloader.download("") == ""
        assert downloader.download("   ") == ""
        assert fetcher.calls == []

    def test_non_http_scheme_is_rejected_without_any_fetch(self, tmp_path):
        fetcher = _FakeFetcher({})
        downloader = EventImageDownloader(tmp_path, fetcher=fetcher)

        assert downloader.download("file:///etc/passwd") == ""
        assert downloader.download("data:image/png;base64,AAAA") == ""
        assert fetcher.calls == []

    def test_404_status_is_rejected(self, tmp_path):
        url = "https://example.org/missing.jpg"
        fetcher = _FakeFetcher(
            {url: ImageFetchResponse(url=url, status=404, headers={}, body=b"")}
        )
        downloader = EventImageDownloader(tmp_path, fetcher=fetcher)

        assert downloader.download(url) == ""

    def test_non_image_content_type_is_rejected(self, tmp_path):
        url = "https://example.org/page.html"
        fetcher = _FakeFetcher({url: _ok(b"<html>not an image</html>", content_type="text/html")})
        downloader = EventImageDownloader(tmp_path, fetcher=fetcher)

        assert downloader.download(url) == ""

    def test_image_content_type_but_undecodable_body_is_rejected(self, tmp_path):
        """The core "real decode check, not just a URL pattern" case:
        a server that lies about Content-Type doesn't fool the gate."""
        url = "https://example.org/fake.jpg"
        fetcher = _FakeFetcher({url: _ok(b"this is not really a jpeg", content_type="image/jpeg")})
        downloader = EventImageDownloader(tmp_path, fetcher=fetcher)

        assert downloader.download(url) == ""
        assert list(tmp_path.iterdir()) == []

    def test_tracking_pixel_sized_image_is_rejected(self, tmp_path):
        url = "https://example.org/pixel.jpg"
        fetcher = _FakeFetcher({url: _ok(TINY_JPEG)})
        downloader = EventImageDownloader(tmp_path, fetcher=fetcher)

        assert downloader.download(url) == ""
        assert list(tmp_path.iterdir()) == []

    def test_image_just_above_the_minimum_dimension_survives(self, tmp_path):
        just_big_enough = _jpeg_bytes(80, 80)
        url = "https://example.org/small.jpg"
        fetcher = _FakeFetcher({url: _ok(just_big_enough)})
        downloader = EventImageDownloader(tmp_path, fetcher=fetcher)

        filename = downloader.download(url)

        assert filename != ""
        assert (tmp_path / filename).exists()

    def test_oversized_body_is_rejected(self, tmp_path):
        url = "https://example.org/huge.jpg"
        fetcher = _FakeFetcher({url: _ok(LARGE_JPEG)})
        downloader = EventImageDownloader(tmp_path, fetcher=fetcher, max_bytes=len(LARGE_JPEG) - 1)

        assert downloader.download(url) == ""

    def test_empty_body_is_rejected(self, tmp_path):
        url = "https://example.org/empty.jpg"
        fetcher = _FakeFetcher({url: _ok(b"")})
        downloader = EventImageDownloader(tmp_path, fetcher=fetcher)

        assert downloader.download(url) == ""

    def test_fetcher_raising_does_not_raise_and_returns_empty(self, tmp_path):
        downloader = EventImageDownloader(tmp_path, fetcher=_RaisingFetcher())

        assert downloader.download("https://example.org/whatever.jpg") == ""


class TestSuccessfulDownload:
    def test_valid_jpeg_is_stored_and_filename_returned(self, tmp_path):
        url = "https://example.org/event.jpg"
        fetcher = _FakeFetcher({url: _ok(LARGE_JPEG)})
        downloader = EventImageDownloader(tmp_path, fetcher=fetcher)

        filename = downloader.download(url)

        assert filename.endswith(".jpg")
        stored = tmp_path / filename
        assert stored.exists()
        assert stored.read_bytes() == LARGE_JPEG

    def test_valid_png_is_stored_with_png_extension(self, tmp_path):
        url = "https://example.org/event.png"
        fetcher = _FakeFetcher({url: _ok(LARGE_PNG, content_type="image/png")})
        downloader = EventImageDownloader(tmp_path, fetcher=fetcher)

        filename = downloader.download(url)

        assert filename.endswith(".png")
        assert (tmp_path / filename).read_bytes() == LARGE_PNG

    def test_dest_dir_is_created_if_missing(self, tmp_path):
        dest_dir = tmp_path / "images" / "opportunities"
        url = "https://example.org/event.jpg"
        fetcher = _FakeFetcher({url: _ok(LARGE_JPEG)})
        downloader = EventImageDownloader(dest_dir, fetcher=fetcher)

        filename = downloader.download(url)

        assert (dest_dir / filename).exists()

    def test_missing_content_type_header_still_succeeds_on_a_real_decode(self, tmp_path):
        """Content-Type is a first-pass filter, not the sole gate -- an
        absent header doesn't block a body that genuinely decodes."""
        url = "https://example.org/event.jpg"
        response = ImageFetchResponse(url=url, status=200, headers={}, body=LARGE_JPEG)
        fetcher = _FakeFetcher({url: response})
        downloader = EventImageDownloader(tmp_path, fetcher=fetcher)

        assert downloader.download(url) != ""


class TestDedup:
    def test_identical_bytes_from_two_urls_reuse_the_same_filename(self, tmp_path):
        url_a = "https://example.org/banner-a.jpg"
        url_b = "https://example.org/banner-b.jpg"
        fetcher = _FakeFetcher({url_a: _ok(LARGE_JPEG), url_b: _ok(LARGE_JPEG)})
        downloader = EventImageDownloader(tmp_path, fetcher=fetcher)

        filename_a = downloader.download(url_a)
        filename_b = downloader.download(url_b)

        assert filename_a == filename_b
        assert filename_a != ""
        # Only one file is ever written for the shared content.
        assert len(list(tmp_path.iterdir())) == 1
        # Both URLs were genuinely fetched (dedup is by content, not by
        # skipping the second URL's request).
        assert fetcher.calls == [url_a, url_b]

    def test_repeated_downloads_of_the_same_url_do_not_duplicate_or_refetch_unnecessarily(
        self, tmp_path
    ):
        url = "https://example.org/event.jpg"
        fetcher = _FakeFetcher({url: _ok(LARGE_JPEG)})
        downloader = EventImageDownloader(tmp_path, fetcher=fetcher)

        first = downloader.download(url)
        second = downloader.download(url)

        assert first == second
        assert len(list(tmp_path.iterdir())) == 1

    def test_different_images_get_different_filenames(self, tmp_path):
        url_a = "https://example.org/a.jpg"
        url_b = "https://example.org/b.png"
        fetcher = _FakeFetcher({url_a: _ok(LARGE_JPEG), url_b: _ok(LARGE_PNG, content_type="image/png")})
        downloader = EventImageDownloader(tmp_path, fetcher=fetcher)

        filename_a = downloader.download(url_a)
        filename_b = downloader.download(url_b)

        assert filename_a != filename_b
        assert len(list(tmp_path.iterdir())) == 2
