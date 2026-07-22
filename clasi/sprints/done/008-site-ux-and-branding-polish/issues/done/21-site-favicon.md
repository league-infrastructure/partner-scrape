---
status: done
sprint: 008
tickets:
- 008-004
---

# Set a real favicon for the site (from sdstemecosystem.org)

The site still ships the default Astro favicon
(`site/public/favicon.svg`, referenced in
`site/src/layouts/BaseLayout.astro:26` via `<link rel="icon">`). Replace it
with the real STEM Ecosystem favicon.

## Source
Pull the favicon from the production site: **https://www.sdstemecosystem.org**
— check `/favicon.ico`, the `<link rel="icon">` / `apple-touch-icon` in its
HTML `<head>`, and any `site.webmanifest` icons.

## Do
- Download the favicon asset(s) and store them in `site/public/`
  (self-hosted — the site is a static build with a strict CSP, no runtime
  remote fetch).
- Update `BaseLayout.astro`'s `<link rel="icon">` (and add
  `apple-touch-icon` / manifest icons if available) to point at the new
  file(s). Handle the format (.ico / .png / .svg) accordingly.
- Confirm the tab icon renders on the beta
  (https://league-infrastructure.github.io/partner-scrape/).

## Notes
- Applies to both beta (`partner-scrape/site`) and production
  (`stem-ecosystem`) — though production IS sdstemecosystem.org, so this is
  mainly about the beta matching the real brand.
- Keep it base-path-safe (`import.meta.env.BASE_URL`) if referenced as an
  absolute path.
