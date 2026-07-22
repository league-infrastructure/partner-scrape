# Justfile for the STEM Ecosystem beta site (partner-scrape/site).
#   just dev   → run the local Astro dev server (hot reload)
#   just pub   → publish master to GitHub Pages and watch the deploy
# Requires: just, node/npm, gh (GitHub CLI, authenticated).

# The Astro site lives in this subdirectory.
site := "site"
# GitHub Pages deploy workflow + public URL (see .github/workflows/pages.yml).
pages_url := "https://league-infrastructure.github.io/partner-scrape/"

# Show the available recipes.
default:
    @just --list

# Run the Astro dev server locally (http://localhost:4321, hot reload).
dev:
    cd {{site}} && npm run dev

# Build the static site into site/dist (base path = /partner-scrape, as in CI).
build:
    cd {{site}} && npm run build -- --base /partner-scrape

# Preview the production build locally.
preview: build
    cd {{site}} && npm run preview -- --base /partner-scrape

# Publish to GitHub Pages: push master and watch the deploy (dispatches manually if nothing new).
pub:
    #!/usr/bin/env bash
    set -euo pipefail
    before="$(git rev-parse origin/master 2>/dev/null || echo none)"
    git push origin master
    after="$(git rev-parse origin/master)"
    if [ "$before" = "$after" ]; then
      echo "→ No new commits to push; dispatching a manual Pages deploy…"
      gh workflow run pages.yml --ref master
    else
      echo "→ Pushed ${before:0:7}..${after:0:7}; the push triggered the Pages deploy."
    fi
    sleep 8
    run_id="$(gh run list --workflow=pages.yml --branch master --limit 1 --json databaseId --jq '.[0].databaseId')"
    echo "→ Watching Pages deploy run ${run_id}…"
    gh run watch "${run_id}" --exit-status
    echo "✓ Published: {{pages_url}}"
