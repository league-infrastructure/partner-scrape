---
status: done
sprint: 019
tickets:
- 019-001
- 019-002
- 019-003
---

# Consolidate partner-scrape's beta site into stem-ecosystem (production)

## Description

`partner-scrape/site/` (the "beta" Astro checkout inside this repo) and
`stem-ecosystem` (the real production repo, deploys to
`www.sdstemecosystem.org`) have been maintained as two independent copies of
almost the same site for months. Beta pulled ahead — Teams, Places, Clubs,
markdown rendering, image fallbacks, data-access/for-agents/publish-events
pages, Umami analytics — and nothing ported it back. stem-ecosystem's site
code is a strict subset of beta's; several shared files are byte-identical
(`contact.astro`, `PartnerFilters.astro`, `SocialIcon.astro`,
`partners/index.astro`).

Consolidate: stem-ecosystem becomes the one canonical site codebase.
partner-scrape references it (a build-time checkout, not a second tracked
copy) so its own beta/demo deploy always builds from the same source, for
previewing changes ahead of promoting to production. Stop maintaining two
copies of `partners.json`, two copies of every page, two copies of
everything.

**Decided** (stakeholder, 2026-08-31): partner-scrape's beta stays on GitHub
Pages via a build-time-only checkout of stem-ecosystem — no submodule, no
directory deletion. Longer-term the beta story moves to a Docker deploy of
the site (stem-ecosystem owns the Dockerfile; tracked separately, see
Related) — the GH Pages direct-checkout beta is the interim state.

## Cause

Two proximate triggers surfaced the drift:

1. Sprint 018 (2026-08-31) expanded the partner roster (153→211 orgs,
   geocoded, logo-backfilled, join-verified) — but only in
   `partner-scrape/site/src/data/partners.json`. The pipeline's actual join
   target defaults to `../stem-ecosystem`, whose copy was still the stale
   153-row file, so that production run silently missed ~60 partner
   geocodes/logos.
2. `pages.yml` (beta's deploy workflow) already documented the intended
   relationship in a comment — *"partner-scrape is the beta... stem-ecosystem
   is production... promoted to when ready"* — but that promotion never
   happened, so the two codebases diverged unchecked.

## Proposed fix

Executed as a two-repo effort; this repo (partner-scrape) owns the phases
below. The stem-ecosystem-side promotion (content port, `partners.json`
reconciliation, legacy cleanup) **landed** 2026-08-31 (stem-ecosystem
`master` at `e772cba`, live and green at
`https://league-infrastructure.github.io/stem-ecosystem/`, all 12 routes
200, 350 opportunities) — a separate effort in that repo, not duplicated
here.

1. ~~Provision the scheduled-run workflow~~ **Deferred** (stakeholder,
   2026-08-31 — open-ended "deal with that later," alongside the
   `www.sdstemecosystem.org` DNS/custom-domain fix; see Related). The
   runbook remains complete and unchanged at `docs/deploy/scheduled-run.md`
   for whenever this is picked back up: create a fine-grained PAT
   (`stem-ecosystem` only, Contents: Read/write), `dotconfig save -d prod`
   + `dotconfig gh-push -d prod --actions --repo
   league-infrastructure/partner-scrape`, verify, then one manual
   `gh workflow run scheduled-run.yml`. Not part of this sprint's ticket
   work — a credential-touching operator action the runbook itself already
   documents as outside any ticket's scope.

2. **Convert `site/`**: remove it as a tracked directory entirely (not a
   submodule); add a second `actions/checkout` step to `pages.yml`'s build
   job (`repository: league-infrastructure/stem-ecosystem, ref: master,
   path: site`) ahead of the existing `npm ci`/build steps, which already
   assume `working-directory: site` — no other build-step change needed.
   Considered and rejected: a true `git submodule` (pulls stem-ecosystem's
   ~405MB `public/images` tree into every clone that recurses submodules;
   pin-bumping is a manual step, not automatic) and deleting `site/`
   entirely (drops the partner-scrape-hosted beta deploy the stakeholder
   explicitly wants kept).

   The trigger needs rethinking once `site/` is gone from git — `pages.yml`'s
   `paths: ['site/**']` filter will match nothing. Options: `workflow_dispatch`
   only, a hook off the weekly scheduled-run's data push, or
   `repository_dispatch` fired from stem-ecosystem on its own pushes. Decide
   at implementation time.

   **Accepted tradeoff, stated plainly**: with item 1 deferred,
   `scheduled-run.yml` is not running. Retiring `site/` as a tracked
   directory does not stop the beta from building or deploying — it's a
   checkout of stem-ecosystem's already-live, already-current content —
   but neither repo's data will refresh again until the token is
   provisioned later. This sprint does not solve that; it only needs to
   not hide it.

3. **Follow-up cleanup** (separate commits from the Phase 2 build-step
   change):
   - Repoint `partner_scrape/config.py`'s `DEFAULT_SITE_DIR` to the local
     checkout path used by local interactive runs, if one is kept (e.g. a
     gitignored manual clone for local dev preview). `scheduled-run.yml`
     needs no change — it already uses its own explicit `--site-dir`
     against a fresh CI checkout, fully decoupled from this default.
   - Remove the now-pointless `MIRROR_SITE_DIRS` mechanism in full:
     `config.py`'s `MIRROR_SITE_DIRS_ENV_VAR`/`DEFAULT_MIRROR_SITE_DIR`/
     `get_mirror_site_dirs()`, `partner_scrape/export/mirror.py` entirely,
     its 3 call sites in `cli.py` (`run`, teams export, directory export),
     and `tests/test_export_mirror.py` (28 tests) + the related
     `test_config.py` assertions. It exists solely to sync two independent
     directories — moot once there's one.
   - Review partner-scrape's own root-level dead weight (`dev/`,
     `scraper/`, `run_mirrors.py`, `scrapy.cfg` — already called superseded
     in this repo's own README) for archival; grep for any remaining
     `scrapy.cfg`/settings references before removing anything.
   - Update `README.md` and the `justfile`'s site-related recipes.

4. ~~Parameterize the shared data-origin constant~~ **Done** (2026-08-31,
   landed on the stem-ecosystem side ahead of the promotion so it was fixed
   once, not twice): `for-agents.astro`'s `DATA_ORIGIN` now derives from
   `import.meta.env.SITE` + `BASE_URL` instead of a hardcoded literal.
   `stem-ecosystem-8d` additionally generalized `llms.txt` the same way
   (`public/llms.txt` → `src/pages/llms.txt.ts`, since a static file can't
   derive anything at request time) — both now correctly emit whichever
   origin actually built them, verified live post-deploy.

## Verification

- `pages.yml`'s beta build succeeds end-to-end via the direct checkout;
  `github.io/partner-scrape` renders correctly with real, current data
  (currently the Aug 31 stem-ecosystem snapshot — see item 1's deferral).
- Full `uv run pytest -q` green with `mirror.py` and its tests removed; a
  real pipeline run confirms `DEFAULT_SITE_DIR` resolves correctly with no
  mirror step attempted.
- No copy of `partners.json` (or any site data) remains tracked in
  partner-scrape once `site/` is removed — confirming the duplicate-copy
  problem this issue exists to fix cannot recur structurally, not just
  that it happens to be reconciled right now.
- Deferred until item 1 is picked back up: a real `gh workflow run
  scheduled-run.yml` completing, stem-ecosystem's `master` receiving a
  fresh commit, and `public/data/partners.json` regenerating from 153 to
  match the live roster.

## Related

- **stem-ecosystem-side promotion** (content port, `partners.json`
  reconciliation, legacy cleanup incl. removing `rundbat` entirely and
  fixing the still-unrenamed `astro-template` naming in `docker/`) — a
  parallel, separately-tracked effort in the stem-ecosystem repo. This
  issue's phases 1–2 are gated on it landing.
- **Long-term beta strategy**: stakeholder direction is to eventually
  deploy the beta via Docker rather than GitHub Pages direct-checkout
  ("set up a Docker page for beta test — that's how we're going to do
  betas"). Tracked as follow-on work in stem-ecosystem (owns the
  Dockerfile); the direct-checkout GH Pages beta in this issue is the
  interim state, not the end state.
- **`www.sdstemecosystem.org` frame-forwards to the beta site** (frameset
  HTML pointing at `github.io/partner-scrape`, no GitHub Pages custom
  domain configured on either repo) — a DNS/registrar-level
  misconfiguration, orthogonal to this migration, tracked as a stakeholder
  action item on the stem-ecosystem side.
