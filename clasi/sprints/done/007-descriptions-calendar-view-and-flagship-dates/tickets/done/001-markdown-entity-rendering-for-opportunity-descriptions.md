---
id: '001'
title: Markdown & entity rendering for opportunity descriptions
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: 15-render-markdown-in-descriptions.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Markdown & entity rendering for opportunity descriptions

## Description

Implements issue `15-render-markdown-in-descriptions.md` and sprint
007's SUC-001. See sprint.md's Architecture (Description Markdown
Renderer, Step 3 module table) and Design Rationale ("Markdown rendering
happens at build time only") for full context — this ticket implements
that design, it does not re-decide it.

**Problem**: `site/src/pages/opportunities/[slug].astro` renders
`<p>{opp.description}</p>` — Astro escapes this, so Markdown syntax
(`**bold**`, `\n\n` paragraph breaks — common in LeagueSync/Pike13 class
copy) and numeric HTML entities (`&#8211;`, `&#8217;` — present in ~22
scraped descriptions) show up as raw literal text.
`site/src/components/OpportunityCard.astro` truncates the same raw
string via `truncate(opp.description, 120)` (`site/src/lib/helpers.ts`),
so cards show the same raw artifacts in their preview.

**Approach**:

1. Create `site/src/lib/markdown.ts` (new module) exporting two pure,
   build-time-only functions operating on one raw description string:
   - `renderDescriptionHtml(text: string): string` — decode HTML
     entities, parse Markdown, **sanitize** the resulting HTML, return
     it as a string safe to emit via `set:html`.
   - `descriptionToPlainText(text: string): string` — decode entities
     and strip Markdown syntax down to clean plain text (no `**`, no
     `\n\n` literal, no raw entity codes), for the card preview.
   - Both must handle `null`/`undefined`/empty input gracefully
     (return `''`), matching `truncate()`'s existing null-safety in
     `helpers.ts`.
2. Pick a dependency-light, **build-time-only** (Node, not
   browser-only) Markdown + sanitizer pairing — e.g. Astro's built-in
   Markdown support, or a small `marked` + a sanitizer (e.g.
   `isomorphic-dompurify` or similar). This choice is deliberately left
   to you (sprint.md Open Question 3) — constraints: no runtime
   external fetch/CDN/script (site has a strict CSP and is a
   self-contained static build), small dependency footprint, must run
   during `astro build`.
3. Wire `site/src/pages/opportunities/[slug].astro`: replace
   `<p>{opp.description}</p>` with a sanitized-HTML render via
   `set:html={renderDescriptionHtml(opp.description)}` (wrap in a
   container element, e.g. `<div class="detail-description" set:html={...} />`).
4. Wire `site/src/components/OpportunityCard.astro`: change
   `truncate(opp.description, 120)` to
   `truncate(descriptionToPlainText(opp.description), 120)`.
5. Do **not** change `helpers.ts`'s `truncate()` itself — it already
   works correctly on plain text; the fix is upstream of it (feeding it
   cleaned text instead of raw Markdown).

**Files**:
- New: `site/src/lib/markdown.ts`
- Modify: `site/src/pages/opportunities/[slug].astro`
- Modify: `site/src/components/OpportunityCard.astro`
- Modify: `site/package.json` (new dependency/dependencies for the
  chosen Markdown/sanitizer pairing)

**Out of scope** (per sprint.md Scope): promoting this to the
production `stem-ecosystem` site; any dependency requiring a runtime
network fetch or external CDN/font.

## Acceptance Criteria

- [x] A LeagueSync/Pike13 class detail page renders real bold text and
      paragraph breaks — not literal `**` or run-on text with no breaks.
- [x] A description containing `&#8211;`/`&#8217;` (or similar numeric
      entities) shows the real em-dash/curly-apostrophe character, on
      both the detail page and the card preview.
- [x] Card previews never show `**`, a literal `\n`, or a raw numeric
      HTML entity — only clean truncated plain text.
- [x] No unescaped third-party HTML reaches the DOM: feed
      `renderDescriptionHtml` a description containing a deliberately
      unsafe fragment (e.g. `<script>alert(1)</script>` or an inline
      `onerror=` handler) and confirm the sanitizer strips it from the
      output.
- [x] A description that is empty, `null`, or has no Markdown/entity
      content renders exactly as it does today (no regression, no
      crash) — both functions handle this input without throwing.
- [x] `npm run build` (in `site/`) succeeds with no errors or warnings
      about the new dependency.

## Testing

- **Existing tests to run**: none exist in `site/` (`package.json` has
  no `test` script) — this project's site has no JS test framework.
  Verification is `npm run build` plus the manual/behavioral checks
  above, run against real scraped data already in
  `site/src/data/opportunities.json` (find a record with `**`/`\n\n`
  or a numeric entity to exercise the fix — or construct one via
  `--dry-run` if none exists in current data).
- **New tests to write**: none required (no framework to add tests
  to) — if you judge it valuable, a small standalone Node script that
  calls both exported functions against a few fixture strings and
  asserts the expected output is acceptable but not mandatory; do not
  introduce a new test-runner dependency just for this.
- **Verification command**: `npm run build` (run from `site/`).
- **Documentation**: none required — this is a self-contained
  presentation fix with no new public interface beyond the two
  functions in `markdown.ts`, which should carry their own docstring
  comments per this project's module-doc convention (see
  `partner_scrape/extract/ladder.py` for the house style, even though
  this ticket is TypeScript).
