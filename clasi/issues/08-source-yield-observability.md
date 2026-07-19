---
status: pending
sprint: '004'
---

# Source-yield observability + zero-yield alerts

Cheap insurance for an unattended aggregator: know immediately when a scraper
silently breaks.

## Why

The whole reason Fleet and Birch went unnoticed at zero events is that
nothing watched per-source yield. With hundreds of sources, adapters *will*
break as sites change; without monitoring, the site quietly rots — the exact
failure this project exists to reverse.

## Proposed scope

- **Per-run, per-source yield report** — counts of events found / dated /
  new / dropped, with deltas vs. the previous run.
- **Zero-yield / cliff alerts** — flag any source that was productive and
  suddenly returns nothing (or drops sharply).
- Lightweight, human-readable output the operator can scan after each
  scheduled run (and later, a surface on the site's admin/meta).

## Sequence

Depends on: 07 (orchestrator) for the run loop to report against. Small but
high-value.

_Proposal / mock-up — rewrite freely._
