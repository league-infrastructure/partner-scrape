---
id: '034'
title: Email-driven partner onboarding
status: roadmap
branch: sprint/034-email-driven-partner-onboarding
use-cases: []
issues:
- 18-email-driven-onboarding-and-ai-event-submission.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 034: Email-driven partner onboarding

## Goals

Add a path for partner onboarding that requires nothing of the partner
except sending an email. Phase 1 (build first): a monitored inbound
email address handles onboarding requests — auto-validated via
site-scrape evidence gathering, then routed to the existing manual
candidate-review queue. Phase 2 (build second): an already-approved
partner emails a URL for a single event, and a competent AI model
(Opus) extracts and auto-publishes it.

## Problem

Structured-HTML/JSON-LD publishing (issue 17) is too high a bar for
small nonprofits with no technical staff. No inbound-email or always-on
infrastructure exists today — the engine is entirely batch/pull (HTTP
GET adapters via `cli.py:main → pipeline.run`, plus a weekly cron that
is currently disabled). This sprint introduces the project's **first
always-on component** (an inbound webhook receiver), which is a
structural departure from every prior sprint's batch-only design and
must be scoped carefully to keep that new surface as small as possible.

## Solution

Mail arrives via an inbound webhook (SendGrid Inbound Parse / Mailgun
Routes / SES) that parses incoming mail and POSTs to a receiver
endpoint. That receiver does only two things: verify the provider
signature, and append the parsed email to an inbound queue — nothing
heavier runs in the always-on path. All expensive work (site-scrape
validation, AI extraction) runs in a new batch subcommand
(`ingest-mail`, mirroring the existing `discover-candidates`
subcommand) that drains the queue on the existing scheduled-workflow
model.

**Phase 1 — Onboarding (build first).** The batch job fetches the
sender org's own site, gathers evidence (does the sender's name/email/
phone/domain appear on the site? is the content STEM-suitable via the
existing LLM relevance gate?), and writes an `OrgCandidate` review stub
via the existing `write_candidate`/`registry/candidates.py` machinery —
reusing the exact "lead → gate → persist a review stub → operator
promotes" model `discovery/candidate_pipeline.py` already implements
for hub-scan leads. A human reviews and promotes, as today.

**Phase 2 — Event submission (build second; depends on issue 15's
per-partner append-only store).** An approved partner emails a URL; the
batch job checks the sender's email domain against the partner's known
website domain (or a recognized address on the partner record), then
points the Opus-tier model at that one page for raw-HTML extraction
into a structured `Event`, attributed to the partner's `source_id`.
Auto-publish, always visible/correctable: the extracted event is
appended to the partner's append-only per-partner store (issue 15),
provenance-tagged as email-submitted, with no human gate but full
auditability after the fact.

## Open Stakeholder Decisions (must resolve before detail planning)

- **Webhook provider/hosting choice** — SendGrid Inbound Parse vs.
  Mailgun Routes vs. SES→Lambda, and where the tiny receiver is hosted.
  Not decided as of this roadmap pass.
- **Phase 2's dependency on issue 15** — issue 15's per-partner
  append-only store is not among the 9 issues this roadmap pass
  planned, so its status is unknown here. If it has not landed by the
  time this sprint reaches detail planning, Phase 2 should be
  descoped from this sprint into its own follow-up rather than
  blocking Phase 1's onboarding work.

This sprint is sequenced last, and largest, precisely because it
depends on resolving these two open items and introduces the project's
first always-on component — the highest-risk structural change of the
whole roadmap.

## Success Criteria

- Phase 1: a fixture email → the webhook receiver → `ingest-mail` batch
  drain produces a correct `OrgCandidate` stub with evidence attached,
  landing in `registry/candidates/`, reviewable exactly like an
  existing hub-scan lead.
- Phase 1: the webhook receiver does nothing beyond signature
  verification and enqueue — no site-scrape or LLM work runs in the
  always-on path.
- Phase 2 (only if issue 15's per-partner store has landed by the time
  this sprint is detail-planned; otherwise Phase 2 is descoped to a
  follow-up sprint, see Open Questions below): a fixture email + saved
  event page → a correct provenance-tagged line appended to a temp
  per-partner store, attributed to the right partner, with sender-domain
  identity verified.
- Full hermetic test suite stays green; an end-to-end dry-run (POST a
  sample webhook payload, then run `ingest-mail`) never writes to the
  real `stem-ecosystem`.

## Scope

### In Scope

- Webhook receiver (signature verify + enqueue only).
- Inbound queue (captured-email store the batch job drains).
- New `ingest-mail` CLI subcommand mirroring `discover-candidates`.
- Sender identity/trust module (domain match for submissions;
  site-scrape contact-evidence gathering for onboarding).
- Phase 1 onboarding: evidence gathering + `OrgCandidate` stub write.
- Phase 2 event submission (contingent — see Open Questions): raw-page
  AI extractor (new method/prompt/result-dataclass in the
  `enrich`-style pattern, Opus model) + wiring into issue 15's
  per-partner store.
- Provider config + new GH Actions schedule for the batch drain.

### Out of Scope

- Issue 17's structured-HTML/JSON-LD publishing path — this sprint is
  the alternative to it, not a dependency of it.
- Any heavier processing inside the webhook receiver itself — the
  "tiny surface" decision is a hard boundary, not a starting point to
  optimize away.
- Building issue 15's per-partner append-only store from scratch, if it
  has not already landed — that is issue 15's own scope; this sprint
  only wires Phase 2 into it once it exists (see Open Questions).

## Test Strategy

Unit tests: parse fixture provider webhook payloads; signature-verify
logic; identity/domain-match logic; raw-HTML extractor against saved
page fixtures via `FixtureLLMClient` (no live API), asserting `Event`
fields. Onboarding: fixture email → assert a correct `OrgCandidate`
stub lands in a temp `registry/candidates/` with evidence attached.
Submission: fixture email + saved event page → assert a correct
provenance-tagged line appended to a temp per-partner store. End-to-end:
POST a sample webhook payload to the receiver, then run `ingest-mail`
against the queue with a dry-run that never writes to the real
`stem-ecosystem`.

## Architecture

(To be sized and written at detail-planning time. Certain to be
**substantial** — this introduces the project's first always-on
component, a new external integration (the webhook provider), and a
new cross-module dependency (Phase 2 writing into issue 15's
per-partner store). Full 7-step methodology with diagrams expected.)

### Architecture Overview

(Deferred to detail planning.)

### Design Rationale

(Deferred to detail planning.)

### Migration Concerns

(Deferred to detail planning.)

## Use Cases

(Deferred to detail planning — roadmap phase does not include full use
cases.)

### SUC-001: (Title)
Parent: UC-XXX

- **Actor**: (Who)
- **Preconditions**: (What must be true before)
- **Main Flow**:
  1. (Step)
- **Postconditions**: (What is true after)
- **Acceptance Criteria**:
  - [ ] (Criterion)

## GitHub Issues

(GitHub issues linked to this sprint's tickets. Format: `owner/repo#N`.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [ ] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|

Tickets execute serially in the order listed.
