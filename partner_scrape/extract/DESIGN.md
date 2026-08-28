# Extract

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable

---

## 1. Purpose

`extract/` recovers canonical `Event` field values, each with a confidence score, from
one arbitrary HTML page. It is a subsystem because "read fields out of unstructured
HTML" is a self-contained, purely computational problem — no network, no configuration,
no state — that both HTML adapters need and that is worth testing in isolation against a
corpus of real pages. It owns the confidence model for unstructured extraction:
the ordering of which signals are trusted over which. Nothing else makes that judgment.

## 2. Orientation

One public function: `extract_fields(html: str, url: str) -> dict[str, tuple[Any, float]]`.

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

### Consumes
Nothing from any other subsystem. `extract/` imports only the standard library and
`lxml`. It does not import `model`, `fetch`, `registry`, or `config` — which is what
makes it trivially unit-testable against a directory of saved HTML fixtures.

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
