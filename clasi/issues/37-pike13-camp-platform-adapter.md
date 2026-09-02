---
status: pending
sprint: null
split_from: 29-camp-session-extraction.md
---

# Pike13 camp-platform adapter

Split from `29-camp-session-extraction.md` during sprint 028 detail planning
(2026-09-01): issue 29 named three camp-registration platform adapters in
priority order — `campscui.active.com` (ActiveNet), CampBrain, then Pike13.
Sprint 028 builds the first two (`activenet_camps`, `campbrain` adapter
types) but explicitly defers Pike13.

## Description

Pike13 (developer.pike13.com) is the platform behind the League's own camps
— "the cleanest API of any provider" per issue 29's original text. Two
things need resolving before it can be built:

1. **Credential provisioning.** Unlike ActiveNet/CampBrain (treated as
   public browse surfaces for sprint 028's purposes), Pike13's API needs its
   own key/OAuth credential, following the `config.py` accessor precedent
   (`get_leaguesync_api_key()`, `get_robotevents_api_key()`).
2. **Overlap with `leaguesync`.** Issue 29's own original text asked
   whether Pike13 "supersedes gaps in leaguesync" — the already-shipped
   adapter that pulls the League's own booking data. This needs an answer
   before registering Pike13-sourced camps, to avoid the same
   dual-registration risk sprint 028's `adapters/DESIGN.md` documents for
   Air & Space Museum/Helen Woodward (two adapters covering the same
   underlying camps, each bypassing cross-source dedup by design since both
   would carry `kind in PROGRAM_EXTRACTION_KINDS`).

## Suggested approach

Reuse sprint 028's `activenet_camps`/`campbrain` adapter shape: `discover()`/
`fetch()` mirror `ProgramPageAdapter`'s single-configured-endpoint shape;
`extract()` parses Pike13's JSON response deterministically into
`ProgramExtractionResult` (Pike13's API is described as clean/structured,
so the LLM-fallback path `activenet_camps`/`campbrain` also support should
rarely be needed here), mapped onto `Event` via the existing
`_map_result_to_event` — zero new mapping code, per
`adapters/DESIGN.md`'s sprint 028 "Reuse surface for future platforms" note.

## References

Originally issue 29 (`29-camp-session-extraction.md`), sprint 028's own
Design Rationale (`clasi/sprints/028-camp-session-extraction/design/
adapters-DESIGN.md`, "defer Pike13" entry).