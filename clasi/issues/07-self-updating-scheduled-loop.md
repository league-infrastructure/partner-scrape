---
status: pending
---

# Self-updating scheduled loop + deploy

Make the whole thing run unattended. This is the core of the pitch: a
directory that stays fresh every week with zero per-event human effort.

## Why

The business case (near-$0 hosting vs. the Fleet's $3k/yr, and the League's
goodwill/advertising model) only works if nobody has to babysit it. It also
needs to run clean for a week or two before we re-engage the Fleet.

## Proposed scope

- **Orchestrator** — run adapters on per-source cadence (frequent API pulls,
  weekly sitemap diffs, monthly full mirror for API-less sites).
- **Failure isolation** — one broken source never empties the site or aborts
  the run; it's reported and skipped.
- **Scheduled loop** — scrape → enrich → normalize → export → site rebuild →
  deploy, with a visible "last updated" stamp and automatic pruning of past
  events.
- **Decide the automation home** — GitHub Actions in this repo committing to
  the site repo, vs. the League's Docker host — and how cross-repo publish is
  authenticated.

## Sequence

Depends on: 05 (export). Needs at least 02 + 06 producing data to be
meaningful. Enables the "run unattended, then contact Meyer" plan.

_Proposal / mock-up — rewrite freely._
