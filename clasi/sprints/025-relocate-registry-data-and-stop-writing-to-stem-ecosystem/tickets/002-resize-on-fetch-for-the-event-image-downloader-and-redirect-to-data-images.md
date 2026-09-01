---
id: '002'
title: Resize-on-fetch for the Event Image Downloader and redirect to data/images/
status: in-progress
use-cases:
- SUC-030
depends-on: []
github-issue: ''
issue: stop-writing-to-stem-ecosystem-checkout.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Resize-on-fetch for the Event Image Downloader and redirect to data/images/

## Description

`pipeline.py`'s `run()` constructs a real `export.images.
EventImageDownloader` (whenever `image_resolver` is omitted) that
writes into `{site_dir}/public/images/opportunities/` — a write path
sprint 020 never gave an `own_data_dir` equivalent, and not part of
Eric's original enumeration (found during this sprint's own
investigation). `EventImageDownloader` fetches and quality-gates images
today but never resizes them; stem-ecosystem's own measurement of the
631 images currently there: ~405MB total, mean 655KB/median 303KB, 147
files over 1MB accounting for 67% of total bytes (including a 5.2MB
raw-camera-original JPEG served as a card thumbnail).

Add a resize-on-fetch step to `EventImageDownloader` for *newly*
downloaded images (the existing 631 legacy images are explicitly out of
scope — see sprint.md's Scope and Design Rationale), and redirect its
write target from `{site_dir}/public/images/opportunities/` to
`data/images/opportunities/` (`config.get_own_data_dir()`-relative).
See sprint.md's Design Rationale ("fold resize-on-fetch into
`EventImageDownloader`...") for the full reasoning, including why this
is not an infrastructure/hosting decision requiring stakeholder input.

## Acceptance Criteria

- [x] `Pillow` is declared in `pyproject.toml`'s `dependencies` (not an
      optional extra — unlike `playwright`, no external browser binary
      is needed).
- [x] A newly-downloaded image whose width or height exceeds 1600px
      (long edge) is resized (aspect ratio preserved) and re-encoded as
      JPEG at quality 80.
- [x] An image already within the 1600px cap is written through with
      its original bytes and format unchanged — no unnecessary
      re-encode.
- [x] Only PNG/JPEG/WebP are eligible for resize; GIF is passed through
      unresized (animation-safety — see sprint.md's Design Rationale).
- [x] The dedup-by-hash filename is computed from the *final* (possibly
      resized) bytes, not the original fetch — two images that resize to
      identical final bytes dedupe to one written file.
- [x] `pipeline.run()`'s default `image_resolver` construction (used
      when the caller omits one) targets `data/images/opportunities/`
      via `config.get_own_data_dir()`, never
      `{site_dir}/public/images/opportunities/`.
- [x] `data/images/opportunities/` is created automatically if missing
      (`mkdir(parents=True, exist_ok=True)`), matching every other
      `own_data_dir` write's convention.
- [x] Existing `EventImageDownloader` quality-gate tests (scheme check,
      status, `Content-Type`, size cap, structural decode check, minimum
      dimensions) pass unmodified — this ticket adds a new step after
      the existing gate, it doesn't change the gate itself.
- [x] `uv run pytest -q` is green.

## Implementation Plan

**Approach**: read `export/images.py` in full before starting — it
already anticipated this exact moment in its sprint-008 docstring
("If genuine pixel downscaling becomes a real operational need, revisit
adding an image-processing dependency in a follow-up ticket"). Insert
the resize step between the existing quality gate (ends at
`_sniff_dimensions`'s minimum-dimension check) and the existing
dedup-by-hash step, inside `EventImageDownloader.download()`.

1. Add `Pillow` to `pyproject.toml`'s `dependencies` list; `uv sync`.
2. Add two named constants (with a short rationale docstring each,
   matching this module's existing style): `RESIZE_LONG_EDGE = 1600`,
   `RESIZE_JPEG_QUALITY = 80`.
3. Add a `_resize_if_needed(data: bytes, dimensions: tuple[int, int],
   extension: str) -> bytes` (or similarly-scoped helper): if
   `extension` is `.gif`, or both dimensions are already `<=
   RESIZE_LONG_EDGE`, return `data` unchanged. Otherwise, open with
   Pillow, resize (`Image.thumbnail` or equivalent, preserving aspect
   ratio), and re-encode: JPEG at `RESIZE_JPEG_QUALITY` for an opaque
   image; preserve PNG for an image with an alpha channel (so
   transparency isn't silently lost) rather than forcing JPEG.
4. In `download()`, call this helper after the existing
   `_sniff_dimensions` gate passes, before computing `digest =
   hashlib.sha256(...)`. Compute `digest`/`filename`/the dedup cache key
   from the *resized* bytes, and write those bytes
   (`self.dest_dir / filename).write_bytes(resized_bytes)`), not the
   original `response.body`.
5. In `pipeline.py`'s `run()`, change the default `image_resolver`
   construction's `dest_dir` argument from
   `resolved_site_dir / "public" / "images" / "opportunities"` to
   `get_own_data_dir() / "images" / "opportunities"` (import
   `get_own_data_dir` from `config.py`, already imported elsewhere in
   this file for `get_site_dir`).

**Files to modify**: `pyproject.toml`; `export/images.py`;
`pipeline.py`.

**Testing plan**: new fixture-based unit tests in
`tests/test_export_images.py` (or wherever `EventImageDownloader`'s
existing tests live): (a) a synthetic in-memory PNG/JPEG larger than
1600px on its long edge is fetched (fixture `ImageFetcher`) and the
written bytes are smaller than the original and structurally valid at
<=1600px; (b) a synthetic image already <=1600px is written
byte-identical to the fetch; (c) two events whose fetched images
produce identical bytes after resize dedupe to one written file (extend
the existing dedup test's shape); (d) a synthetic animated-shaped GIF
fixture is written unresized. Update `tests/test_pipeline_e2e*.py`'s
assertions about the image downloader's `dest_dir` construction to
expect `own_data_dir`-relative, not `site_dir`-relative. No network
calls in any of this — all fixture-based, matching this project's
existing hermetic convention for `EventImageDownloader`.

**Documentation updates**: `export/images.py`'s module docstring (the
"zero new dependencies" framing needs a note that this decision was
revisited, per its own anticipated trigger) and its "Pixel-dimension
downscaling is intentionally not implemented" section (now implemented,
for new downloads).
