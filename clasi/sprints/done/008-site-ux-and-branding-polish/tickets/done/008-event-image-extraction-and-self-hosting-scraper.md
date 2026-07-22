---
id: 008
title: Event image extraction and self-hosting (scraper)
status: done
use-cases:
- SUC-008
depends-on: []
github-issue: ''
issue: 19-event-images.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Event image extraction and self-hosting (scraper)

## Description

Issue 19 (scraper half): give each opportunity its own image where the scraper can find one.

**Important codebase-alignment finding from planning**: `Event.image_url` already exists
(`partner_scrape/model.py:101`) and is already populated by the Extraction Ladder's JSON-LD
(`extract/ladder.py`'s `_extract_json_ld`, via `_json_ld_image()`) and OpenGraph
(`_extract_opengraph`, `og:image`) rungs, plus four adapters that set it directly:
`leaguesync.py`, `localist.py`, `bibliocommons.py`, and `tec.py`. This ticket does **not** add new
extraction — it wires the already-extracted `image_url` through to a self-hosted local file and a
new `Opportunity.image_src` field, mirroring exactly how `logo_src` already works (a pre-resolved
local filename, not a URL, by the time the site consumes `opportunities.json`).

**Requires network access** — this ticket downloads each event's image at scrape/export time and
self-hosts it. No runtime hotlinking on the site side afterward (that's ticket 009, which depends
on this one).

See `sprint.md` Architecture > Step 3 ("Event Image Downloader", "Opportunity Model") and Step 4's
diagram for the full data-flow picture.

## Implementation Plan

### Approach

1. **`Opportunity.image_src` field**: add `image_src: str = ""` to the `Opportunity` dataclass in
   `partner_scrape/normalize/run.py`, following the exact same convention as the existing
   `logo_src: str` field (a resolved local filename, empty string when absent). No `writer.py`
   edit is needed for this field to be exported — `export/writer.py`'s `_SITE_SCHEMA_FIELDS` is
   derived from `fields(Opportunity)` automatically (see that file's module docstring).
2. **Event Image Downloader** (new module, e.g. `partner_scrape/export/images.py`, alongside the
   existing `export/writer.py` and `export/ads.py`): given one `Event.image_url`, download it,
   apply a quality gate, and — if it passes — store it locally and return the resulting filename
   (or `None`/empty if rejected/unavailable). Quality gate (exact thresholds left to this ticket,
   per `sprint.md` Open Question 4):
   - Reject empty/missing `image_url`.
   - **Validate the response is actually an image** (`Content-Type` + real image-decode check,
     not just a URL pattern) before writing anything — per `sprint.md`'s downloaded-asset
     validation note.
   - Reject undersized images (tracking pixels / spacers) below a minimum reasonable pixel
     dimension.
   - Dedupe: if an already-downloaded image (e.g. by content hash) is being reused across
     multiple events on the same partner site — a likely case for generic site-banner images —
     store it once and reuse the filename rather than duplicating the file (keeps disk usage
     bounded; also avoid using an image that's obviously just a generic site banner if that's
     detectable, e.g. it's identical across many otherwise-unrelated events on the same source —
     a heuristic, not a hard requirement).
   - Downscale to a reasonable maximum size before storing (mirroring `logo_src`'s existing
     size discipline).
3. **Wire the Downloader into the pipeline**: call it for each surviving `Opportunity`/`Event`
   before/during export, writing files into
   `get_site_dir() / "public" / "images" / "opportunities"` (the same `get_site_dir()` resolution
   `export/writer.py` already uses for `opportunities.json` — this repo's `site/` directory is
   the effective target via the existing `SITE_DIR` override; see `sprint.md` Impact on Existing
   Components for the confirmed repo-topology detail). The exact call site is left to this
   ticket's implementer — most likely alongside the existing partner join in
   `normalize/run.py`'s per-`Instance`-to-`Opportunity` mapping (has access to `Event.image_url`
   via the source `Event`/`Instance`), or as a pass over surviving `Opportunity` records
   immediately before `export_opportunities()` is called.
4. A missing/failed/rejected image must **not** fail the export — `image_src` simply stays `""`
   for that record (SUC-008's Alternate Flow), and the site's fallback chain (ticket 009) handles
   the rest.

### Files to Create / Modify

- `partner_scrape/normalize/run.py` — `Opportunity.image_src` field.
- `partner_scrape/export/images.py` (new) — the Event Image Downloader: fetch, validate, quality
  gate, dedupe, downscale, store, filename derivation.
- The pipeline call site that invokes the Downloader (likely `normalize/run.py` or
  `export/writer.py`'s `export_opportunities()` — implementer's choice, document the choice in
  code comments per this project's existing convention of citing the sprint/ticket that made the
  decision, matching `normalize/run.py`'s existing docstring style).
- `tests/test_normalize_run.py` — new coverage for `Opportunity.image_src`'s presence/default.
- `tests/test_export.py` — new coverage confirming `image_src` is included in
  `_SITE_SCHEMA_FIELDS`/the exported JSON shape.
- New test file (e.g. `tests/test_export_images.py`) — unit tests for the Event Image Downloader:
  URL validation, content-type/decode gating, undersized-image rejection, dedup, filename
  derivation, and the "no image / fetch failure doesn't raise" alternate flow.

### Testing Plan

- `uv run pytest` must pass — all 848 existing tests, plus new coverage listed above.
- **Required evidence beyond unit tests** (per `sprint.md` Test Strategy): a before/after check
  showing `image_src` actually populated in exported `opportunities.json` for at least one real
  source, from a live or recorded-fixture run — unit tests alone don't prove real images reach
  the site. Include this evidence in the ticket's completion notes.
- A deliberately bad input (e.g. a tracking-pixel-sized image, a 404 URL) must not populate
  `image_src` and must not raise/fail the export.

### Documentation Updates

- Update `normalize/run.py`'s `Opportunity` dataclass docstring to mention `image_src` alongside
  the existing "every field through `logo_src` is part of the site's JSON contract" note (the
  contract now extends one field further).
- Add a module docstring to the new `export/images.py`, matching this project's convention (see
  `export/writer.py`'s and `extract/ladder.py`'s module docstrings) — state its responsibility,
  the quality gate, and that it's consumed once per `Opportunity` before export.

## Acceptance Criteria

- [x] `Opportunity` has a new `image_src: str = ""` field, exported automatically via
      `_SITE_SCHEMA_FIELDS`.
- [x] A new Event Image Downloader module fetches, validates, quality-gates, and self-hosts
      images from `Event.image_url` (already populated by the ladder + 4 adapters — no new
      extraction added).
- [x] Rejected/missing/failed images leave `image_src` empty without failing the export.
- [x] Downloaded images are validated as real images (content-type + decode check) before being
      stored.
- [x] `uv run pytest` passes (all 848 existing tests, plus new coverage for the Downloader,
      the new field, and its presence in the exported schema).
- [x] A before/after run on at least one real source shows `image_src` populated in the exported
      `opportunities.json` (documented evidence, not just passing unit tests).

## Testing

- **Existing tests to run**: full suite (`uv run pytest`) — 848 existing tests must stay green.
- **New tests to write**: `tests/test_normalize_run.py` (new field), `tests/test_export.py`
  (schema inclusion), a new `tests/test_export_images.py` (Downloader fetch/validate/gate/dedup
  logic, including failure paths).
- **Verification command**: `uv run pytest`
