---
status: pending
---

# llms.txt + agent discovery pages (make the data easy for LLMs to find)

Add a well-known discovery layer so an LLM/agent landing on the site can
find our published JSON data (from issue 15) without guessing. Three
connected pieces:

## 1. `llms.txt` (well-known referencing)

Publish an `llms.txt` at the site root (Astro serves `site/public/` at
`/`, so `site/public/llms.txt` → `/llms.txt`), following the llms.txt
convention. It is the entry point that:

- Points agents straight at the machine-readable data files — the
  `partners.json` and per-partner `events.json` / past-events files
  defined in **issue 15**.
- Links to the human/agent-readable pages below.

## 2. A "how to consume our data" page (human + agent readable)

A normal web page on the site documenting how to consume/scrape our
data easily: where the JSON lives, its shape, and the "given
`partners.json` + a partner's event files you can fully reconstruct the
site" contract from issue 15. This is the page an agent is sent to when
it wants to use our data.

## 3. An "LLM page" referenced from `llms.txt`

A page authored specifically for LLM consumption. The `llms.txt` entry
references this page; the intended flow is: agent reads `/llms.txt` →
follows to the LLM page → learns where the data is and how to use it. An
agent that wants to consume/republish our data goes here to get what it
needs.

## Connections (the point of this issue)

- **Depends on / advertises issue 15** — this discovery layer exists to
  expose the `partners.json` + per-partner event files that issue 15
  publishes. The two must agree on file locations/URLs.
- **A separate future issue** will cover *how the publication workflow
  itself works* (the mechanism an agent follows to publish/consume).
  This issue must **link to that page** from `llms.txt` / the LLM page
  once it exists — wiring the discovery entry points to the publication
  docs is explicitly part of this issue's scope.

## Open questions

- Do we also mirror `llms.txt` under `/.well-known/`, or root only?
- One combined page vs. two (a human "how to scrape us" page + a
  separate LLM-only page) — the request names both; confirm whether
  they're distinct or the same page served two ways.
- What exact URLs does `llms.txt` list (ties to issue 15's layout
  decision)?
</content>
