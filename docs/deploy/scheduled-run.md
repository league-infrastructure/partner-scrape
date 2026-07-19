# Activating the scheduled scrape-and-publish workflow

This document is a runbook for the **operator activation steps** that put
`.github/workflows/scheduled-run.yml` (sprint 004 / issue 07 / SUC-017)
into production. None of these steps are performed by the ticket that
produced the workflow file — the sprint's own Test Strategy and Migration
Concerns are explicit that activation (provisioning the cross-repo
secret, merging the workflow, and firing the first real run) is a
separate, deliberate, post-sprint action, not something any ticket
executes automatically. No step below is run by an agent implementing a
ticket; it is for a human operator to perform once, then again whenever
the PAT rotates.

No secret value is written anywhere in this repo, this document, or the
workflow file itself — every secret is referenced only by name
(`${{ secrets.ANTHROPIC_API_KEY }}` / `${{ secrets.SITE_REPO_TOKEN }}`)
inside the workflow, and lives encrypted at rest under
`config/prod/secrets.env` (SOPS) until pushed to GitHub.

## Prerequisites

- `dotconfig` installed and this repo's `config/` already initialized
  (`ANTHROPIC_API_KEY` is already provisioned this same way — see
  `config/prod/secrets.env` and `config/dotconfig.yaml`).
- Write access to both `league-infrastructure/partner-scrape` (to push
  Actions secrets) and `league-infrastructure/stem-ecosystem` (to create
  the fine-grained PAT scoped to it).
- `gh` CLI authenticated, if you want to verify secrets/branch state via
  `gh api` as part of step 4.

## 1. Merge the workflow to `master`

GitHub Actions only evaluates `on: schedule` triggers for workflow files
that exist on the repository's **default branch**. Until
`.github/workflows/scheduled-run.yml` is merged into `partner-scrape`'s
`master`, the weekly cron never fires (`workflow_dispatch` also requires
the file to be present on a branch GitHub can see it push/PR against, but
practically speaking: merge first). Merge this sprint's branch (or at
least this file) to `master` before proceeding.

## 2. Create the fine-grained GitHub PAT

Create a **fine-grained personal access token**, scoped as narrowly as
possible:

- **Resource owner**: `league-infrastructure`
- **Repository access**: only `stem-ecosystem` (not "all repositories")
- **Permissions**: Repository → **Contents: Read and write**. Nothing
  else — no Actions, no Administration, no Metadata beyond the
  read-access GitHub requires implicitly.
- **Expiration**: GitHub enforces a maximum for fine-grained PATs
  (commonly ≤1 year); pick the longest allowed and note the expiry
  somewhere you'll see it (see Rotation below).

Copy the token value — it is shown once.

## 3. Add the token to this repo's encrypted secrets, then push it

```bash
# Add SITE_REPO_TOKEN=<the PAT value> to config/prod/secrets.env,
# then re-encrypt in place:
dotconfig save -d prod

# Dry-run first -- confirms which keys/repo would be affected without
# actually writing anything to GitHub:
dotconfig gh-push -d prod --actions --repo league-infrastructure/partner-scrape --dry-run

# Then for real -- pushes both ANTHROPIC_API_KEY and SITE_REPO_TOKEN to
# this repo's Actions secrets:
dotconfig gh-push -d prod --actions --repo league-infrastructure/partner-scrape
```

`dotconfig save` re-encrypts `config/prod/secrets.env` at rest (SOPS);
the plaintext token only ever exists locally in your shell/editor while
you add it, never committed. `dotconfig gh-push` is the only step that
transmits the value, and it goes straight to GitHub's Actions secrets
store, not into any file in this repo.

## 4. Verify both secrets are present

In the GitHub UI: `partner-scrape` repo → **Settings → Secrets and
variables → Actions** → confirm `ANTHROPIC_API_KEY` and
`SITE_REPO_TOKEN` both appear (values are never shown, only names and
last-updated timestamps — that's expected).

Equivalently, via `gh`:

```bash
gh api repos/league-infrastructure/partner-scrape/actions/secrets --jq '.secrets[].name'
```

should list both names.

## 5. Trigger one manual run before trusting the cron

From the GitHub UI: `partner-scrape` repo → **Actions** →
**Scheduled scrape and publish** → **Run workflow** (this is the
`workflow_dispatch` trigger). Or via `gh`:

```bash
gh workflow run scheduled-run.yml --repo league-infrastructure/partner-scrape
```

Confirm, for that run:

- The job summary shows a per-source yield report.
- `stem-ecosystem`'s `master` branch received a new commit (check its
  commit history) — or, if the run happened to produce no data changes,
  confirm the job log shows "No data changes this run -- nothing to
  publish." instead.
- If a commit landed, `stem-ecosystem`'s existing `deploy.yml` fired on
  that push (check its own Actions tab) and the live site's "last
  updated" stamp reflects the new run.

Only after a real end-to-end run like this succeeds should the weekly
cron be trusted to run unattended.

## PAT rotation

Fine-grained PATs expire on GitHub's enforced schedule. When
`SITE_REPO_TOKEN` is about to expire (or has expired — the scheduled
workflow's `Checkout stem-ecosystem` step will simply start failing
authentication), repeat steps 2–4 above: create a new PAT, `dotconfig
save` the new value into `config/prod/secrets.env`, then re-run
`dotconfig gh-push -d prod --actions --repo
league-infrastructure/partner-scrape`. No code or workflow change is
needed for rotation — the workflow always reads whatever value currently
sits behind the `SITE_REPO_TOKEN` secret name.

## What this runbook deliberately does not do

Per this sprint's Test Strategy and Migration Concerns, ticket
004-004's own implementation work did not run any step in this document:
no `dotconfig gh-push` was executed, no PAT was created, no commit was
pushed to `stem-ecosystem`, and the workflow was not triggered. This
document exists so an operator can perform those steps deliberately,
once the sprint is otherwise ready to ship.
