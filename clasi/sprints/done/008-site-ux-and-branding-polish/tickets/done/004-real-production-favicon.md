---
id: '004'
title: Real production favicon
status: done
use-cases:
- SUC-004
depends-on: []
github-issue: ''
issue: 21-site-favicon.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Real production favicon

## Description

Issue 21: the site still ships Astro's default `site/public/favicon.svg`, referenced by
`site/src/layouts/BaseLayout.astro`'s `<link rel="icon">`. Replace it with the real STEM
Ecosystem favicon sourced from production (https://www.sdstemecosystem.org).

**Requires network access** — this ticket fetches an external asset once, then self-hosts it.
The site's static, strict-CSP build never fetches it at runtime afterward (see `sprint.md`
Architecture > Design Rationale, "every new external asset ... is downloaded once and
self-hosted, never hotlinked").

## Implementation Plan

### Approach

- Fetch the favicon asset(s) from production: check `https://www.sdstemecosystem.org/favicon.ico`,
  the `<link rel="icon">` / `apple-touch-icon` href(s) in its HTML `<head>`, and any
  `site.webmanifest` icon entries. Prefer whichever format production actually serves (.ico /
  .png / .svg) — do not assume SVG.
- Download and store the asset(s) under `site/public/` (e.g. `site/public/favicon.ico` and/or
  `site/public/apple-touch-icon.png`, matching production's actual filenames/formats).
- **Validate the downloaded response is actually an image** (`Content-Type` check plus a real
  image-decode/dimension check, not just a URL pattern) before writing it into `site/public/` —
  per `sprint.md`'s downloaded-asset validation note in Migration Concerns.
- Update `BaseLayout.astro`'s `<link rel="icon">` to point at the new file, using the
  base-path-safe pattern already in use elsewhere in that file (`import.meta.env.BASE_URL`,
  stripped of trailing slash). Add `apple-touch-icon`/manifest icon `<link>` tags if production
  provides them and it's a small addition.
- Handle the format correctly: if the new favicon is `.ico`/`.png` rather than `.svg`, update the
  `type` attribute on the `<link rel="icon">` tag accordingly (don't leave `type="image/svg+xml"`
  pointing at a `.ico`/`.png` file).

### Files to Modify / Create

- `site/src/layouts/BaseLayout.astro` — `<link rel="icon">` (and optional `apple-touch-icon`/
  manifest tags).
- `site/public/` — new favicon asset file(s), replacing or alongside the existing
  `favicon.svg` (remove `favicon.svg` if it's no longer referenced, to avoid a stale unused
  asset; keep it if still referenced from elsewhere, e.g. `og:image` defaults in
  `BaseLayout.astro`'s `ogImage` prop default — check before deleting).

### Testing Plan

- No JS test framework in `site/`; verify manually: the browser tab shows the real STEM
  Ecosystem icon on a local build; confirm on the deployed beta
  (`league-infrastructure.github.io/partner-scrape/`) once merged/deployed (not required for this
  ticket's own acceptance, but noted for post-merge verification).
- Confirm no runtime network request to sdstemecosystem.org appears in the built page's network
  requests (asset is fully self-hosted).
- `uv run pytest` unaffected (no Python files touched).

### Documentation Updates

None required.

## Acceptance Criteria

- [x] The real STEM Ecosystem favicon renders in the browser tab on a local build.
- [x] `apple-touch-icon`/manifest icons added if production provides them and doing so is a small
      addition (not required if production offers none, or if the addition is nontrivial —
      use judgment, favicon is the hard requirement). (Production offers neither — verified by
      inspecting the full `<head>` of https://www.sdstemecosystem.org/: only a single
      `<link rel="icon">`, no `apple-touch-icon`, no `manifest` link. Nothing to add.)
- [x] The favicon path is base-path-safe (`import.meta.env.BASE_URL`), matching the convention
      already used elsewhere in `BaseLayout.astro`.
- [x] No runtime fetch to sdstemecosystem.org — the asset is fully self-hosted under
      `site/public/`.
- [x] The downloaded asset was validated as a real image (content-type + decode check) before
      being committed.
- [x] `npm run build` succeeds.

## Testing

- **Existing tests to run**: none (no JS test framework); `uv run pytest` unaffected.
- **New tests to write**: none applicable; verified by manual visual check plus a successful
  build, per the sprint's Test Strategy.
- **Verification command**: `npm run build`
