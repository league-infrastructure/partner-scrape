---
status: in-progress
sprint: '016'
tickets:
- 016-003
---

# Venue canonicalization so cross-source dedup actually collapses duplicates

## Description

Sprint 015 ticket 004 proved the remaining gap with a live measurement:
after Fleet's `default_location` fix, the same event ("Educator Open
House", 2026-09-24) from Balboa Park's calendar and Fleet's own listing
matches on title+date but still does NOT collapse, because
`dedup.cross_source_identity()` compares venue strings via
`normalize_title()` (lowercase + strip punctuation only):

- Balboa Park TEC venue: "Fleet Science Center, 1875 El Prado, San Diego, CA"
- Fleet default_location:  "1875 El Prado, San Diego, CA 92101"

**User-visible consequence:** with the Balboa Park hub source live
(sprint 014), shared events publish TWICE on the site today.

Fix shape (design discussion in `partner_scrape/normalize/DESIGN.md`
Open Questions, sprint 015 addendum): an address-aware venue
canonicalization for the dedup identity's venue component — e.g. street
-number+street-name token match, ZIP-stripping, org-name prefix
stripping — conservative enough not to collapse genuinely different
venues. Re-run ticket 004's measurement script as the acceptance test
fixture basis.

## References

Sprint 015 tickets 004 (measurement + root cause), 014-004 notes;
gap analysis: https://claude.ai/code/artifact/02ba9c3e-61a2-40eb-a987-444463cd3266
