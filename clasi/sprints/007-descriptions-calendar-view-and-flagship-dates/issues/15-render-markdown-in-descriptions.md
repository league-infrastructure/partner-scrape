---
status: in-progress
sprint: '007'
tickets:
- 007-001
---

# Event descriptions must render Markdown (and decode HTML entities)

Opportunity descriptions render as escaped plain text, so any formatting
shows as raw source. Reported by the stakeholder from the live beta.

- **Markdown** renders literally: LeagueSync/Pike13 class descriptions carry
  `**This Event is tailored to students in grades 7-12**` and `\n\n`
  paragraph breaks — the reader sees the asterisks and run-on text.
- **HTML entities** render literally: ~22 scraped descriptions contain
  `&#8211;` / `&#8217;` etc. (em-dashes, curly apostrophes) shown raw.

## Where (in `site/`)
- `site/src/pages/opportunities/[slug].astro` (detail page) —
  `<p>{opp.description}</p>` escapes everything.
- `site/src/components/OpportunityCard.astro` — `truncate(opp.description, 120)`
  in the card preview.

## Fix
- Detail page: render `description` as **Markdown → HTML** with a
  lightweight, sanitized renderer, decoding HTML entities first. Emit via
  `set:html` on trusted, **sanitized** output only (no raw injection).
- Card preview: strip Markdown/entities to a clean text snippet for the
  truncated 120-char preview (don't render formatting in the tiny card).
- Prefer a dependency-light approach (Astro built-in Markdown or a small
  vetted `marked`+sanitizer); the site is a static build with a strict CSP.

## Acceptance
- A LeagueSync class detail page renders bold/paragraphs, not asterisks.
- A scraped description with `&#8211;`/`&#8217;` shows the real characters.
- Card previews show clean text (no `**`, no raw entities).
- Output is sanitized — no unescaped third-party HTML reaches the DOM.

## Note
Applies to both the beta (`partner-scrape/site`) and production
(`stem-ecosystem`) — this sprint delivers the beta; keep the components in
sync when promoting. Source: `site/docs/issues/004-render-markdown-in-descriptions.md`.
