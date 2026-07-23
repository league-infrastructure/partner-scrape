---
status: pending
---

# Email-driven partner onboarding + AI event submission

Structured-HTML / JSON-LD publishing (issue 17) is too high a bar for
many partners — small nonprofits with no technical staff won't add
schema.org markup or maintain a feed. This issue adds a path that
requires **nothing of the partner except sending an email**.

A monitored, automation-driven **email account** handles two things:

1. **Onboarding** — an org emails asking to become a partner
   (auto-validated, then human-reviewed). **Build first.**
2. **Event submission** — an already-approved partner emails a URL for a
   single event; a competent AI model extracts it. **Build second;
   depends on issue 15's per-partner store.**

Related: extends the partner-publishing options in **issue 17**; Phase 2
writes into the append-only per-partner store from **issue 15**; reuses
the LLM enrichment path touched by **issue 13**.

## How it harmonizes with the real system (from exploration)

- **No email/inbound infra and no always-on process exist today.** The
  engine is batch/pull (HTTP GET adapters) via `partner-scrape`
  (`cli.py:main → pipeline.run`) + the `discover-candidates` subcommand;
  the only automation is `.github/workflows/scheduled-run.yml` (weekly
  cron, currently disabled). **Decision: mail arrives via an inbound
  webhook** (SendGrid Inbound Parse / Mailgun Routes / SES) that parses
  incoming mail and POSTs it to our endpoint.
  → This adds the project's *first* always-on component. Keep that
  surface **tiny**: the webhook receiver only (a) verifies the provider
  signature and (b) captures the parsed email into an **inbound queue**.
  All expensive work — site-scrape validation, AI extraction — stays in
  a **batch subcommand** that drains the queue, reusing the existing
  batch model and scheduled workflow.

- **Reuse the existing candidate review queue for onboarding.**
  `discovery/` + `registry/candidates.py` already implement
  "lead → LLM relevance gate → persist a review stub → operator lists &
  manually promotes": `OrgCandidate` (`hub_scan.py`), `write_candidate` /
  `list_candidates` / `CandidateStub` (`candidates.py`), stubs under
  `registry/candidates/`. Promotion candidate→source is **deliberately
  manual** — exactly the "list we review to add partners" model.

- **Reuse the AI machinery for validation + extraction.**
  `enrich/llm_client.py` `AnthropicLLMClient` owns the Anthropic SDK, key
  resolution (`ANTHROPIC_API_KEY` via SOPS/dotconfig `.env`), structured
  JSON-schema output auto-generated from a dataclass, and strict parsing.
  Model is one constant — `MODEL_ID` (`llm_client.py:49`, Haiku) → swap
  to **`claude-opus-4-8`** for extraction ("a really competent model").
  `LLMClient` Protocol + `FixtureLLMClient` = clean test seam.
  `candidate_pipeline.py` already builds a synthetic `Event` and runs the
  **relevance gate** ("content suitable?").

- **Reuse the fetcher + Event pipeline.** `fetch/` (`PoliteFetcher`,
  `PlaywrightFetcher` for JS) fetches the org site / submitted URL; the
  extracted `Event` (`model.py`, full field set + `Event.set()`
  provenance) flows through `enrich → normalize → export`.

- **Net-new pieces:** (1) the webhook receiver + inbound queue;
  (2) **sender identity/trust** — no contact/name/phone/email matching
  exists today (`contact_*` fields are always empty); (3) **raw-page AI
  extraction** — nothing feeds raw HTML to the LLM today (the enricher
  sends only pre-extracted fields).

## Phase 1 — Onboarding (build first)

1. **Webhook receiver** verifies the provider signature, parses the
   email (sender address, domain, body), appends it to the inbound
   queue. Nothing heavy.
2. **Batch subcommand** (new, e.g. `ingest-mail`, mirroring
   `discover-candidates`) drains the queue. For an onboarding email it
   fetches the org's own site (`fetch/`) and gathers **evidence**: does
   the sender's name / email / phone / domain appear on the site? Is the
   content STEM-suitable (LLM relevance gate)?
3. Writes an `OrgCandidate` review stub (reuse `write_candidate`) into
   `registry/candidates/`, annotated with the evidence + a confidence
   signal.
4. **A human reviews the queue** and promotes (manual, as today).

## Phase 2 — Event submission (build second; depends on issue 15)

1. Partner emails a **URL** + a few details; webhook queues it as above.
2. **Identity check** (batch): the sender's email domain must match the
   partner's website domain (or a recognized address on the partner
   record). Otherwise route to the review queue.
3. Because the URL is a partner-vouched single event page, **point the
   competent AI model (Opus) at that one page**: fetch → new raw-HTML
   extraction → structured fields → `Event` attributed to the partner's
   `source_id`.
4. **Auto-publish, always visible/correctable** (decision): append the
   extracted event to the partner's **append-only per-partner store
   (issue 15)** — provenance-tagged as email-submitted — where it is
   visible and correctable after the fact. No human gate; full
   auditability.

## Components to build

- **Webhook receiver** — minimal always-on endpoint (serverless is
  enough); signature verify + enqueue only.
- **Inbound queue** — a captured-email store the batch job drains.
- **New CLI subcommand** `ingest-mail` mirroring `discover-candidates`.
- **Sender identity/trust module** — domain match for submissions;
  site-scrape contact-evidence gathering for onboarding.
- **Raw-page AI extractor** — new method/prompt/result-dataclass in the
  `enrich`-style pattern (reuse `_build_*_json_schema`,
  `AnthropicLLMClient`), Opus model.
- **Wiring** — onboarding → candidate queue; submissions → issue-15
  per-partner store.
- **Provider config + new GH Actions schedule** for the batch drain.

## Key reused files

`partner_scrape/cli.py`, `pipeline.py`, `config.py`,
`enrich/llm_client.py` (+ `enricher.py`, `cache.py`),
`discovery/candidate_pipeline.py`, `registry/candidates.py`,
`registry/schema.py`/`loader.py`, `fetch/`, `model.py`,
`normalize/run.py`, `.github/workflows/scheduled-run.yml`.

## Open questions

- Webhook provider choice (SendGrid Inbound Parse vs. Mailgun Routes vs.
  SES→Lambda) and where the tiny receiver is hosted.
- The dedicated inbound address, and how "recognized addresses" beyond
  the sender's domain are maintained on the partner record.
- Phase 2 depends on issue 15's per-partner append-only store landing
  first.

## Verification

- Unit: parse fixture provider webhook payloads; signature-verify;
  identity/domain-match logic; raw-HTML extractor against saved page
  fixtures via `FixtureLLMClient` (no live API), asserting `Event`
  fields.
- Onboarding: fixture email → assert a correct `OrgCandidate` stub lands
  in a temp `registry/candidates/` with evidence attached.
- Submission: fixture email + saved event page → assert a correct
  provenance-tagged line appended to a temp per-partner store, attributed
  to the right partner.
- End-to-end: POST a sample webhook payload to the receiver, then run
  `ingest-mail` against the queue with a dry-run that never writes to the
  real `stem-ecosystem`.
</content>
