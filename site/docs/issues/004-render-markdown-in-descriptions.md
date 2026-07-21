# Event descriptions must render Markdown (and decode HTML entities)

**Reported by stakeholder (Eric), 2026-07-20, from the live beta.**

Opportunity descriptions are rendered as escaped plain text, so any
formatting shows as raw source:

- **Markdown** renders literally. e.g. the LeagueSync class descriptions
  carry `**This Event is tailored to students in grades 7-12**` and
  `\n\n` paragraph breaks — the reader sees the asterisks and run-on text.
- **HTML entities** render literally. ~22 scraped descriptions contain
  `&#8211;` / `&#8217;` etc. (em-dashes, curly apostrophes) that show as
  the raw entity instead of the character.

## Where
- `site/src/pages/opportunities/[slug].astro` (detail page) —
  `<p>{opp.description}</p>` escapes everything.
- `site/src/components/OpportunityCard.astro` — `truncate(opp.description, 120)`
  in the card preview.

## Proposed fix
- Detail page: render `description` as **Markdown → HTML** with a
  lightweight, sanitized renderer (e.g. `marked` + `sanitize-html`, or
  Astro's built-in Markdown), and decode HTML entities first. Wrap in a
  `set:html` on trusted, sanitized output only.
- Card preview: strip Markdown/entities to a clean text snippet for the
  truncated 120-char preview (don't render formatting in the tiny card).
- Applies to **both** the beta (`partner-scrape/site`) and production
  (`stem-ecosystem`) — keep the components in sync when promoting.

## Note (data side, optional)
Most descriptions are already plain text (adapters strip HTML). The
Markdown mainly comes from first-party feeds (LeagueSync/Pike13). Decoding
entities could alternatively be done once at scrape time in
`normalize/`, but rendering-side handling covers all sources uniformly.
