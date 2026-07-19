---
id: '003'
title: Event model classification fields and Normalize taxonomy fallback
status: done
use-cases:
- SUC-011
- SUC-012
depends-on: []
github-issue: ''
issue: 04-llm-enrichment-relevance-gate.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Event model classification fields and Normalize taxonomy fallback

## Description

Foundational data-model ticket for issue 04, with no LLM dependency of its
own — pure plumbing that tickets 004/005 build on. Extend the canonical
`Event` (sprint.md Architecture > Event Model, extended) with the fields
LLM enrichment will populate, and teach Normalize to prefer them when
present.

Scope:
- Add six fields to `partner_scrape/model.py`'s `Event` dataclass:
  `relevant: bool | None = None`, `relevance_reason: str = ""`,
  `areas_of_interest: list[str] = field(default_factory=list)`,
  `age_grade_level: list[str] = field(default_factory=list)`,
  `cost_range: str = ""`, `time_of_day: list[str] =
  field(default_factory=list)`. No change to `Event.set(...)` itself —
  these fields are populated the same way every other field is (sprint
  001's Design Rationale already anticipated exactly this extension).
- `partner_scrape/normalize/run.py`'s `_to_opportunity`: for each of
  `areas_of_interest`/`age_grade_level`/`cost_range`/`time_of_day`,
  prefer the Event's own value when `field_provenance` shows it was set
  (i.e. some upstream step, currently only a future Enricher, called
  `Event.set()` for that field); otherwise fall back to
  `taxonomy.py`'s keyword derivation exactly as sprint 001 built it. Each
  of the four fields is checked independently — an Event with an
  LLM-set `cost_range` but no LLM-set `areas_of_interest` gets the LLM
  value for one and the keyword-derived value for the other.
  `taxonomy.py` itself needs no code changes.

## Acceptance Criteria

- [x] `Event` gains the six fields listed above; each is settable via the
      existing `Event.set(field, value, source=..., confidence=...)`
      helper with provenance recorded exactly like any other field.
- [x] An Event with none of the six fields set behaves identically to
      sprint 001: `_to_opportunity` calls `taxonomy.py`'s keyword
      derivation for `areas_of_interest`/`age_grade_level`/`cost_range`/
      `time_of_day`, and every existing sprint 001 test still passes
      unmodified.
- [x] An Event with `areas_of_interest` set via `Event.set(...)` produces
      an `Opportunity.areas_of_interest` equal to that set value, not the
      keyword-derived one.
- [x] The same holds independently for `age_grade_level`, `cost_range`,
      and `time_of_day` — each field's presence/absence in
      `field_provenance` is checked on its own, not all four together.
- [x] `relevant`/`relevance_reason` round-trip through `Event.set()`
      (this ticket only stores them on the Event; SUC-012's actual gating
      behavior is ticket 005's job).

## Implementation Plan

### Approach

Purely additive dataclass fields plus one small conditional per field in
`_to_opportunity` — resist the temptation to generalize this into a
loop-driven "prefer-set-else-fallback" helper for four fields with two
different fallback shapes (`list[str]` vs `str`); four explicit
if/else branches read more clearly than an abstraction built for exactly
four call sites (see sprint.md's anti-pattern guidance on speculative
generality).

### Files to Create/Modify

- `partner_scrape/model.py`
- `partner_scrape/normalize/run.py`
- `tests/test_model.py`
- `tests/test_normalize_run.py`

### Documentation Updates

None required this ticket.

## Testing

- **Existing tests to run**: `uv run pytest` (full sprint 001 suite —
  this ticket's whole point is that nothing existing regresses; the
  additive fields and the fallback-preserving conditional must leave
  every sprint 001 assertion unchanged).
- **New tests to write**: `tests/test_model.py` cases for the six new
  fields via `Event.set()`; `tests/test_normalize_run.py` cases for each
  of the four classification fields independently, both LLM-set and
  unset, plus a case mixing some set and some unset on the same Event.
- **Verification command**: `uv run pytest`
