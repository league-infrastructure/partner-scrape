---
status: in-progress
sprint: '022'
tickets:
- 022-001
---

# Restore test coverage for exit code 1 when publish.project() raises

## Description

Sprint 019 ticket 001 (removing the MIRROR_SITE_DIRS mechanism) deleted
`tests/test_cli.py::test_mirror_still_runs_when_publish_project_raises`
per its explicit deletion list — correctly, since the mirror-continues
framing it tested no longer applies. But that test also incidentally
covered a distinct, still-live correctness property from sprint 018
ticket 010: `main()` returns exit code 1 (not 0) when `publish.project()`
raises. That coverage isn't preserved anywhere else.

This is exactly the class of silent regression that motivated tonight's
whole site-consolidation effort (a `publish.project()` failure went
unnoticed for months because nothing surfaced it loudly). Cheap to add
back with the mirror framing removed.

## Proposed fix

A small, focused test in `tests/test_cli.py` (or wherever exit-code
behavior is otherwise tested) asserting: `main()` returns 1 when
`publish.project()` raises, and that the error is logged (per ticket
018-010's `logger.exception(...)` addition) — no mirror-related
assertions, since that mechanism is gone.

## References

Sprint 019 ticket 001 (deletion, flagged as a deviation); sprint 018
ticket 010 (the exit-code-1 behavior this covers).
