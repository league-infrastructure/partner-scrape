---
status: pending
---

# Localist adapter cannot filter by event type (blocks UCSD volunteer events)

## Description

Found during sprint 030 ticket 006 while verifying issue 14's dated
volunteer-event sources.

UCSD's Localist instance exposes a Volunteer event type — issue 14
names Wander the Wetlands and Weed Warriors as examples, and
`type=Volunteer` was confirmed working live (it returns Weed Warriors).
But `LocalistAdapter.discover()` in `partner_scrape/adapters/localist.py`
only supports a `group_id` parameter; there is no `type` filter, so
these events cannot be registered at all.

This is the one piece of issue 14's post-research plan that sprint 030
could not deliver. Issue 14 itself is otherwise resolved: Strategy A is
dead by its own research, Strategy B shipped as `offerings.json`
volunteer profiles (sprint 030 ticket 002), and Coastkeeper + Surfrider
already surface volunteer events through the normal pipeline.

## Proposed fix

Add a `type` (event-type) filter to `LocalistAdapter.discover()`'s
supported config alongside `group_id`, then register UCSD's Volunteer
type as a source and live-verify that the resulting records classify as
`opportunity_type = "Volunteering"`.

Check whether Birch Aquarium's existing Localist registration would
also benefit, and whether a source can carry both filters at once.

## Verification

- Unit: a source configured with an event type produces the expected
  request against a fixture.
- Live: the registered source yields Weed Warriors / Wander the
  Wetlands, typed `Volunteering`.
