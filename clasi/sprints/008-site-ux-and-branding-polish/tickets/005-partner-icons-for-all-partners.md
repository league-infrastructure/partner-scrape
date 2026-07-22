---
id: '005'
title: Partner icons for all partners
status: open
use-cases: [SUC-005]
depends-on: []
github-issue: ''
issue: 18-partner-icons-images.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Partner icons for all partners

## Description

Issue 18: 28 of 153 partners have no `logo_src` in `site/src/data/partners.json`, falling back to
the generic placeholder (`getLogoPath()` in `site/src/lib/helpers.ts`). Source and self-host a
real icon for each of the 28.

Per `sprint.md` Architecture > Design Rationale ("partner icon sourcing is automated ... with a
generated monogram as the final fallback"): this is a standalone, one-off sourcing effort against
curated partner metadata — **not** part of the recurring `partner_scrape` pipeline. `logo_src` is
already a read-only join field the pipeline consumes (`partner_scrape/normalize/partners.py`
reads `partners.json`, never writes it); this ticket follows that same convention by editing
`partners.json` directly, not by adding scraper logic.

**Requires network access** — this ticket fetches each logo-less partner's website favicon/icon
and self-hosts it. No runtime hotlinking afterward.

## Implementation Plan

### Approach

- For each of the 28 partners with an empty `logo_src`, attempt automated sourcing from that
  partner's `website` field: favicon, `apple-touch-icon`, or `og:image`, in whatever priority
  order yields a usable result (left to this ticket's implementer — not pinned in `sprint.md`,
  see Open Question 1).
- **Validate each downloaded asset is actually a usable image** (`Content-Type` + real
  image-decode + a minimum reasonable size — reject 1×1 tracking-pixel-style favicons) before
  storing it, matching the same downloaded-asset validation principle used by ticket 008's Event
  Image Downloader.
- Download, resize/normalize (square-ish, reasonable dimensions matching the existing 125
  partners' logos under `site/public/images/logos/`), and store each successfully-sourced icon
  under `site/public/images/logos/`, then set that partner's `logo_src` in `partners.json` to the
  new filename — matching the existing convention exactly (`logo_src` is a bare filename, not a
  URL or path; see `getLogoPath()`).
- For any partner where automated sourcing genuinely fails (no fetchable favicon/icon of any
  kind), generate a monogram/initials tile (e.g. the partner's initials on a brand-colored
  background) as a locally-generated fallback image, store it the same way, and set `logo_src`
  accordingly — so every partner ends up better than the flat default placeholder even in the
  worst case.
- Consider (optional, not required) wiring the monogram generator into `getLogoPath()`'s default
  case too, as a general improvement to what a still-logo-less partner shows — but the primary
  acceptance bar is that none of the 28 remain logo-less after this ticket; a per-partner
  pre-generated monogram file satisfies that without touching `helpers.ts` at all if simpler.
- The 125 partners that already have a `logo_src` are untouched — do not re-fetch or "improve"
  existing logos (out of scope per `sprint.md`).

### Files to Create / Modify

- `site/src/data/partners.json` — `logo_src` filled in for the 28 currently-empty records.
- `site/public/images/logos/` — new logo/monogram image files for those 28 partners.
- (Optional) `site/src/lib/helpers.ts` — `getLogoPath()`'s default-placeholder case, only if a
  general monogram-generation fallback is wired in rather than pre-generated static files.

### Testing Plan

- No JS test framework in `site/`; verify by re-checking the 28 previously-empty `logo_src`
  values are now populated and each referenced file exists under
  `site/public/images/logos/` and is a valid, non-trivial image (spot-check a sample visually).
- Confirm the 125 already-populated partners are unchanged (diff `partners.json` to confirm only
  the 28 target records' `logo_src` values changed).
- `uv run pytest` unaffected (no Python files touched).

### Documentation Updates

None required.

## Acceptance Criteria

- [ ] All 28 currently logo-less partners have a non-empty `logo_src` pointing at a self-hosted
      image under `site/public/images/logos/`.
- [ ] Each new image was validated as a real, usable image (not a tracking pixel or broken
      fetch) before being committed.
- [ ] Any partner where automated sourcing genuinely failed shows a generated monogram/initials
      tile instead of the generic default placeholder.
- [ ] The 125 partners that already had a `logo_src` are unchanged.
- [ ] Images are self-hosted (no runtime hotlinking) and reasonably sized.
- [ ] `npm run build` succeeds.

## Testing

- **Existing tests to run**: none (no JS test framework); `uv run pytest` unaffected.
- **New tests to write**: none applicable; verified by diffing `partners.json` and spot-checking
  images, plus a successful build, per the sprint's Test Strategy.
- **Verification command**: `npm run build`
