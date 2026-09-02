# Extract

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable

---

## Revision (2026-09-01 — sprint 028)

Sprint 027's `program_page`/`program_listing`/`program_page_multi` adapter family
(`adapters/DESIGN.md`) sends a fetched page's raw HTML body to the LLM verbatim, with no
reduction step. Two verified failures came out of that (issue 36): the SD Foundation
Community Scholarship's raw page HTML (840KB-965KB site-wide) raised
`anthropic.BadRequestError: prompt is too long: 600199 tokens > 200000 maximum`, and a
UCSD Summer Program Finder card (`www.rmtlacademy.org`, 612KB) hit the same limit. Sprint
028 fixes this by adding one new public function here, `reduce_html_to_text()` (§2, §5),
rather than adding a second HTML-reduction path inside `adapters/` — per this doc's own
"read fields out of unstructured HTML... worth testing in isolation" purpose statement
(§1), text reduction is the same kind of self-contained, purely computational, no-network/
no-config/no-state problem `extract_fields()` already solves, just for a different
consumer (an LLM prompt budget, not the confidence ladder). It reuses this module's
existing visible-text-walking machinery (`_visible_text_parts`/`_visible_body_text`,
already used by the body-regex rung) rather than duplicating an HTML-to-text pass — see
§4's Revision note for why a shared helper, not two independent implementations, was the
right call once a second caller needed "get me the visible text" with a different bound
than the ladder's own 20,000-character rung limit.

## 1. Purpose

`extract/` recovers canonical `Event` field values, each with a confidence score, from
one arbitrary HTML page. It is a subsystem because "read fields out of unstructured
HTML" is a self-contained, purely computational problem — no network, no configuration,
no state — that both HTML adapters need and that is worth testing in isolation against a
corpus of real pages. It owns the confidence model for unstructured extraction:
the ordering of which signals are trusted over which. Nothing else makes that judgment.

**(Sprint 028)** It also now owns one more self-contained, purely computational problem
of the same shape: reducing an arbitrary HTML page down to bounded, readable plain text,
for a caller (the LLM-extraction adapter family) that needs the page's prose content but
not its markup, script, or boilerplate, and cannot safely hand an LLM an unbounded page.
This is a distinct output from `extract_fields()` — plain text, not
`{field: (value, confidence)}` — but the same "parse once, walk the tree, return
something total and pure" shape, so it lives here rather than becoming a second
tree-walking implementation inside `adapters/`.

## 2. Orientation

Two public functions.

`extract_fields(html: str, url: str) -> dict[str, tuple[Any, float]]`.

It parses the page once with `lxml.html` and then runs a fixed sequence of extraction
strategies ("rungs") in descending order of trust. Each rung contributes only fields that
no higher rung already supplied:

| Rung | Signal | Confidence |
|---|---|---|
| 1 | JSON-LD `Event` schema | 1.0 |
| 2 | `<time datetime>` elements | 0.8 |
| 3 | OpenGraph meta tags | 0.6 |
| 4 | `<h1>` / `<title>` fallback | 0.5 |
| 5 | Date embedded in the URL/slug | 0.4 |
| 6 | Body-text date regex | 0.2 |

The return value is a flat `{field_name: (value, confidence)}` map. A field no rung could
recover — most often `start`/`end` on a page with no date signal at all — is simply
*absent* from the map, not present with a placeholder.

**(Sprint 028)** `reduce_html_to_text(html: str, max_chars: int = 100_000) -> str`. Parses
the page once with `lxml.html` (same parser, same `fromstring`-then-tolerate-bad-markup
behavior as `extract_fields`), strips `<script>`, `<style>`, `<nav>`, `<header>`, and
`<footer>` elements before walking the remaining tree for visible text (reusing
`_visible_text_parts`, the same helper the body-regex rung already calls), collapses
whitespace, and truncates to the first `max_chars` characters. Returns `""` for
unparseable/empty HTML, with a logged warning — never raises, matching
`extract_fields()`'s own error-handling contract exactly.

## 3. Constraints and Invariants

- **The ladder is ordered by trust, and each rung only fills gaps.** A lower rung must
  never overwrite a value a higher rung produced. Reordering the rungs, or letting a
  later one clobber an earlier one, silently degrades every page that has both signals —
  a page with correct JSON-LD dates would start reporting a date scraped out of its body
  text.
- **This module returns field values, never an `Event`.** Constructing the canonical
  record is the calling adapter's job. Returning an `Event` here would put record
  assembly in two places and force this module to know about `Provenance`, `source_id`,
  and the rest of the acquisition context it deliberately has no access to.
- **The confidence constants are a public contract.** `CONFIDENCE_JSON_LD` … 
  `CONFIDENCE_BODY_REGEX` are exported and flow into `Event.field_provenance`, where
  `normalize/`'s collapse and dedup stages use them to pick between competing records.
  Changing a tier's number changes which record wins a merge, project-wide.
- **Unparseable or empty HTML returns `{}` with a logged warning — it never raises.** One
  bad page must not abort a source's whole run. `lxml.html.fromstring` already tolerates
  most real-world markup, so this path is rare by construction.
- **No network, no configuration, no state.** The function takes HTML and a URL and
  returns a dict. Anything that would require fetching a linked resource, reading config,
  or remembering a previous call belongs elsewhere.
- **Deliberate non-goal — no per-site special cases.** The point of the ladder was
  replacing a pile of bespoke per-site scrapers with one site-agnostic mechanism. A rung
  must generalize; "if the domain is X, look at div.foo" belongs in a dedicated adapter,
  not here.
- **Body-text scanning is bounded** (`_BODY_SCAN_LIMIT`, 20 000 chars) and skips
  `<script>`/`<style>` content. Removing the bound makes the lowest-value, highest-noise
  rung the most expensive one on large pages.
- **(Sprint 028) `reduce_html_to_text()`'s bound is deliberately separate from
  `_BODY_SCAN_LIMIT`.** The two exist for different reasons and must not be unified: the
  body-regex rung's 20,000-character cap bounds the cost of a low-value, high-noise date
  regex scan; `reduce_html_to_text()`'s 100,000-character cap bounds an LLM's context
  budget for a page it needs to read in full. Changing one must not silently change the
  other.
- **(Sprint 028) Truncation keeps the leading `max_chars` characters of reduced text,
  never the whole page.** A program/camp page states its key facts (program name, dates,
  price, eligibility) in prose near the top, not buried at the end — the same
  publisher-authoring assumption the body-regex rung's own bound already accepts (see
  that rung's docstring). This is a documented, deliberate strategy, not an arbitrary cut:
  a page whose material facts live past the 100,000-character mark would need a different
  strategy (e.g. a summary pass), which is not built here because no page examined during
  sprint 027/028 exhibited that shape.
- **(Sprint 028) `reduce_html_to_text()` strips `<script>`/`<style>`/`<nav>`/`<header>`/
  `<footer>` before truncating, not after.** Stripping first is what makes the
  100,000-character budget mostly page *content* rather than boilerplate — the SD
  Foundation pages' own site-wide template bloat (a large repeated mega-menu/inline
  script payload on every page, per this module's own live-measured finding) is exactly
  the shape this ordering is designed to discard before the cap ever applies.

## 4. Design

**Why a ladder rather than a scorer.** The obvious alternative — collect every candidate
value from every strategy and pick by score — was rejected: it needs a comparison rule
per field type, and the strategies are already cleanly rank-ordered by how deliberately
the publisher authored the signal. JSON-LD is markup someone wrote *to be machine-read*;
a date matched in body text is a guess. A strict priority ladder encodes that ranking
once, in one place, and makes "why did this field get this value?" answerable by
inspecting a single number.

**Why the title fallback is a rung.** It is not one of the signal families the original
design named, but every rung below JSON-LD and OpenGraph needs *some* source for `title`
or the resulting record would be dropped downstream for having none. This rung ports the
equivalent step from the pre-existing `dev/extract_events.py` rather than inventing new
behavior.

**Per-rung structure.** Each `_extract_*(tree, url)` helper returns its own
`{field: value}` map; `extract_fields` merges them in order with `setdefault`-style gap
filling and stamps the rung's confidence on each field it contributed. Adding a rung is
adding one helper plus one entry in the merge sequence at the right rank.

**JSON-LD handling.** `_find_json_ld_event` walks `<script type="application/ld+json">`
blocks, tolerating both bare objects and `@graph` arrays, and picks the first
`Event`-typed node. Nested value shapes (`location` as string or `Place`, `offers` as
object or list, `image` as string or list) each get a dedicated coercion helper —
schema.org permits all of these and real sites use all of them.

**Date parsing.** ISO parsing is the primary path; the body-regex rung uses a
month-name pattern built from `_MONTHS`, tolerating optional weekday prefixes and
ordinal suffixes ("Tuesday, March 3rd, 2026"). Everything resolves to `datetime`, never a
string — downstream comparison logic in `normalize/` depends on real datetimes.

**Dependency.** `lxml`, already a base dependency of the package since the first sprint.
No parser was added for this module.

**(Sprint 028) Why a shared helper, not a second implementation.** `adapters/
program_page.py` could have grown its own `lxml`-based strip-and-walk function instead.
That was rejected the same way `extract/DESIGN.md`'s own non-goal already rejects
per-site special cases living outside this module: "get the visible text out of an HTML
page" is exactly the problem `_visible_text_parts`/`_visible_body_text` already solve for
the body-regex rung, and a second implementation would drift from this one's tolerance
for malformed markup (a bug fixed in one would not fix the other). Exporting
`reduce_html_to_text()` from here, reusing the existing private helpers internally,
keeps there being exactly one "how do we get readable text out of arbitrary HTML" answer
in the codebase.

## 5. Interfaces

### Exposes
- **`extract_fields(html: str, url: str) -> dict[str, tuple[Any, float]]`** — the whole
  subsystem. Pure; total (returns `{}` rather than raising on bad input); deterministic
  for a given input pair. Keys are canonical `Event` field names; values are
  `(value, confidence)`. Absent key means "no rung recovered this field".
- **`CONFIDENCE_JSON_LD`, `CONFIDENCE_TIME_TAG`, `CONFIDENCE_OPENGRAPH`,
  `CONFIDENCE_TITLE_FALLBACK`, `CONFIDENCE_URL_DATE`, `CONFIDENCE_BODY_REGEX`** — the
  tier constants, exported so callers stamp provenance with the same numbers the ladder
  used rather than re-deriving them.
- **(Sprint 028) `reduce_html_to_text(html: str, max_chars: int = 100_000) -> str`** —
  script/style/nav/header/footer-stripped, whitespace-collapsed, leading-`max_chars`-
  truncated visible text. Pure; total (returns `""` rather than raising on bad input).
  Consumed by `adapters/program_page.py`'s `_extract_one_program`/
  `_extract_many_programs` before every cache lookup and LLM call — see
  `adapters/DESIGN.md`'s sprint 028 section.

### Consumes
Nothing from any other subsystem. `extract/` imports only the standard library and
`lxml`. It does not import `model`, `fetch`, `registry`, or `config` — which is what
makes it trivially unit-testable against a directory of saved HTML fixtures. **(Sprint
028)** `reduce_html_to_text()` preserves this exactly — same zero-dependency shape as
`extract_fields()`.

## 6. Open Questions / Known Limitations

- The ladder recovers dates, title, description, location, cost, registration URL, and
  image URL. It does not attempt structured audience, age range, or price *tier* — those
  are left to `enrich/`'s LLM pass and `normalize/`'s keyword taxonomy.
- Timezone handling is inherited from whatever the page states. Pages with an implicit
  local timezone produce naive datetimes; `normalize.run()` coerces any tz-aware datetime
  to naive in one place precisely because this layer cannot guarantee consistency.
- The body-regex rung (0.2) is low-precision by design and frequently matches an
  unrelated date elsewhere on the page. It survives because a wrong date is still
  filterable downstream while a missing date drops the record entirely — but that
  tradeoff has never been measured against real export quality.
- There is no microdata/RDFa rung. Some older event sites use those instead of JSON-LD
  and currently fall through to the weaker rungs.
- **(Sprint 028)** `reduce_html_to_text()`'s 100,000-character truncation is a fixed
  constant, not derived from the model's actual token budget (`adapters/program_llm.py`'s
  `MODEL_ID` and its 200K-token context window). 100,000 characters is comfortably below
  200K tokens for ordinary English prose (~4 chars/token), but a page whose reduced text
  is unusually token-dense (e.g. heavy non-Latin script or numeric tables) is not
  measured against the model's real tokenizer. Not built speculatively — revisit if a
  reduced page is ever observed to still exceed the context window.
- **(Sprint 028)** No page examined during sprint 027/028 needed anything past the
  leading 100,000 characters to recover its program/session fields, so the "keep the
  leading text" truncation strategy is unverified against a page whose material facts
  are genuinely deep in the document. Revisit if one is found.
