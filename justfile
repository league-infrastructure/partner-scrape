# Justfile for the STEM Ecosystem beta preview (league-infrastructure/pages.yml
# checks out league-infrastructure/stem-ecosystem into site/ at build time —
# it is not tracked in this repo).
#   just dev   → run the local Astro dev server (hot reload)
#   just pub   → publish master to GitHub Pages and watch the deploy
# Requires: just, node/npm, gh (GitHub CLI, authenticated).
#
# `dev`/`build`/`preview` below expect a `site/` directory to exist locally.
# CI gets one via pages.yml's build-time checkout; for local use, clone
# stem-ecosystem yourself into site/ (gitignored, not managed by this repo),
# or point `site :=` below at wherever your own clone lives.

# The Astro site lives in this subdirectory (a local, gitignored clone of
# stem-ecosystem -- see note above).
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

# Publish to GitHub Pages: push master, then dispatch the deploy and watch it.
# (pages.yml's push trigger only fires on changes to the workflow file itself
# -- site/ is a build-time checkout, not tracked here -- so an ordinary push
# no longer reliably triggers a build; this recipe dispatches explicitly
# every time rather than assuming the push did.)
pub:
    #!/usr/bin/env bash
    set -euo pipefail
    git push origin master
    echo "→ Dispatching a Pages deploy…"
    gh workflow run pages.yml --ref master
    sleep 8
    run_id="$(gh run list --workflow=pages.yml --branch master --limit 1 --json databaseId --jq '.[0].databaseId')"
    echo "→ Watching Pages deploy run ${run_id}…"
    gh run watch "${run_id}" --exit-status
    echo "✓ Published: {{pages_url}}"
