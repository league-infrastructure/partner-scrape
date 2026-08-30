---
status: pending
---

# Ops: install Playwright, re-enable the weekly cron, add a real-browser fetch path

## Description

Three operational gaps hide content the engine already knows how to get:

1. **Playwright is not installed** in the runtime environment (the
   optional `headless` extra; `import playwright` fails), so the 9 Wix
   partner sites render empty and any source needing JS is blind.
2. **The weekly cron is still commented out** in
   `.github/workflows/scheduled-run.yml` (only `workflow_dispatch`);
   the last runs were manual. Activation prerequisites (SITE_REPO_TOKEN
   PAT etc.) are documented in the sprint 004 runbook.
3. **Plain HTTP gets 403'd by half the interesting web.** Verified
   blockers during the 2026-08-30 research: aquarium.ucsd.edu, Gateway
   Galaxy webstores (Fleet/Zoo/Midway), ActiveNet REST (WAF),
   zoo.sandiegozoo.org kids-programs pages, Chula Vista + National City
   library sites, every North County city rec site, Mathnasium, AoPS.
   The `PoliteFetcher` needs an optional browser-fetch fallback
   (Playwright, honest UA, robots-respecting) for sources marked
   `headless = true`, beyond the existing Wix use case.

## Acceptance sketch

- `uv sync --extra headless` (or equivalent) in dev + CI + scheduled
  runtime; a Wix partner source produces non-empty HTML in a live run.
- Weekly cron enabled and one scheduled run completes end-to-end.
- At least one previously-403 source fetches via the browser path.

## References

Gap analysis 2026-08-30: https://claude.ai/code/artifact/02ba9c3e-61a2-40eb-a987-444463cd3266
