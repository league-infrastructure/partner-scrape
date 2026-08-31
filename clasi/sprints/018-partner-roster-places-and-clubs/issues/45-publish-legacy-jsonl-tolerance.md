---
status: in-progress
sprint: 018
tickets:
- 018-010
---

# publish.project() must tolerate legacy partner-log lines missing newer Opportunity fields

## Description

Root-caused in sprint 018 ticket 001 (see its Notes for the full
writeup): `export/publish.py`'s `_to_opportunity()` raises
`KeyError('eligibility')` on any partner-log `.jsonl` line recorded
before sprint 015 added the `eligibility` field to `Opportunity`
(b0570aa). Consequence: `publish.project()` has failed on EVERY run
since sprint 015 merged — the published `public/data/` tree (partner
roster + per-partner events, the contract llms.txt advertises) is
silently stale, and will stay stale until this is fixed. Ticket 018-001
made the failure loud (logged + exit code 1) and decoupled the mirror
step, but deliberately did not fix the underlying defect (out of its
file scope).

## Proposed fix

`_to_opportunity()` (and any sibling reconstruction path) defaults
missing fields from the `Opportunity` dataclass's own field defaults —
the append-only log's whole design assumes old lines stay readable as
the schema grows, so this is restoring an intended property, not a
behavior change. Regression tests: a fixture `.jsonl` line lacking
`eligibility` (and one lacking several newer fields) reconstructs with
defaults; a full `publish.project()` over mixed-era lines succeeds;
future-proof by iterating dataclass fields rather than special-casing
`eligibility`. Then verify live: `publish.project()` completes and
`public/data/` regenerates with current data.

## References

Sprint 018 ticket 001 Notes (root cause + reproduction);
export/publish.py `_to_opportunity()`; sprint 015 ticket 008
(eligibility field).
