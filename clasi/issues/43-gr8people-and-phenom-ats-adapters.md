---
status: pending
---

# ATS adapters: GR8 People (Teradata) and Phenom (BAE Systems)

## Description

Sprint 031 ticket 007 probed the six employers issue 31 listed as
"unconfirmed ATS — probe before building anything bespoke." The probe
was the deliverable; this issue is what it found worth building.

Two are viable and unsupported:

- **Teradata — GR8 People.** Permissive robots.txt, reachable,
  GraphQL/Next.js, and 13 live San Diego postings visible in the
  aggregation counts at probe time. The strongest candidate.
- **BAE Systems — Phenom People.** Permissive robots.txt (blocks only
  tracking and apply paths), reachable, with a real 805-URL sitemap.
  Secondary.

Four are not worth building, and should not be re-probed without new
information:

- **Qualcomm — Eightfold.** Public search reachable (200); the earlier
  403 was the login-gated candidate portal, not the search API. Worth a
  second look only if someone wants Eightfold support generally.
- **Solar Turbines** — Akamai Bot Manager 403; parent Caterpillar is
  Cloudflare-blocked too.
- **General Atomics — BrassRing.** Reachable but a ~1MB legacy SPA with
  no discoverable JSON API.
- **Intuit — Radancy.** robots.txt disallows the exact `/search-jobs/`
  path.

## Proposed fix

Build the GR8 People adapter first, register Teradata, live-verify.
Then decide on Phenom based on what BAE's sitemap actually yields.

Follow the established ATS path (sprint 006's `greenhouse.py`/`lever.py`,
sprint 031's `workday.py`/`smartrecruiters.py`/`workable.py`/`neogov.py`):
reuse `ats_filters`, `kind='internship'`, `Work-based Learning`,
Apply-by/Rolling availability, routed around dedup.

## Verification

Zero matching postings is a PASS for an ATS adapter — issue 31's
standing rule. Verify the adapter reaches the API and filters
correctly against the raw live response, not that it returns records.
