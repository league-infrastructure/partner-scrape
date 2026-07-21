"""Centralized environment-derived configuration.

This module is the single place in ``partner_scrape`` that reads
``os.environ``. No other module in this package should call
``os.environ`` directly -- import the accessors below instead. Keeping
environment reads in one place means later tickets (Fetch & Cache,
Site Export, ...) can be tested without touching real process
environment: monkeypatch ``os.environ`` and call these functions.

Configuration is assembled by dotconfig (layered ``.env`` files under
``config/``) before the process starts; this module only reads what
lands in ``os.environ`` at call time, it does not know about dotconfig
itself.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Environment variable holding the root directory for the on-disk
#: fetch cache (raw HTML + response metadata). Kept off the repo volume
#: per docs/design/specification.md 3.1 -- there is no sane default,
#: so it must be set explicitly.
SCRAPE_CACHE_DIR_ENV_VAR = "SCRAPE_CACHE_DIR"

#: Environment variable that overrides the default sibling site-repo
#: path used by Site Export (ticket 007).
SITE_DIR_ENV_VAR = "SITE_DIR"

#: Environment variable holding the Bearer token for the League's own
#: sync.jtlapp.net query API (``leaguesync`` adapter). Assembled by
#: dotconfig into ``config/prod/secrets.env`` -- there is no sane
#: default, so it must be set explicitly, matching
#: ``get_scrape_cache_dir``'s convention.
LEAGUESYNC_API_KEY_ENV_VAR = "LEAGUESYNC_API_KEY"

#: Environment variable overriding the ``leaguesync`` adapter's API base
#: URL. Overridable so a future staging/mirror deployment of
#: sync.jtlapp.net doesn't require a code change.
LEAGUESYNC_URL_ENV_VAR = "LEAGUESYNC_URL"

#: Default base URL for the League's sync.jtlapp.net query API --
#: confirmed live (``GET /query?sql=...``) during the leaguesync
#: adapter's build.
DEFAULT_LEAGUESYNC_URL = "https://sync.jtlapp.net"

# This package's own directory, e.g. .../partner-scrape/partner_scrape
_PACKAGE_DIR = Path(__file__).resolve().parent

# The repo root, e.g. .../partner-scrape
_REPO_ROOT = _PACKAGE_DIR.parent

#: Default location of the sibling ``stem-ecosystem`` site repo,
#: matching the layout ``dev/export_site.py`` already assumes: a
#: checkout of ``stem-ecosystem`` next to this repo (``../stem-ecosystem``
#: relative to the repo root). Overridable via ``SITE_DIR``.
DEFAULT_SITE_DIR = _REPO_ROOT.parent / "stem-ecosystem"


def get_scrape_cache_dir() -> Path:
    """Return the configured scrape cache directory.

    Reads ``SCRAPE_CACHE_DIR`` from the environment on every call (no
    caching), so tests can monkeypatch ``os.environ`` freely.

    Raises:
        RuntimeError: if ``SCRAPE_CACHE_DIR`` is not set. There is no
            safe default for a directory that can hold tens of GB of
            cached HTML -- callers must configure it explicitly (see
            ``config/prod/public.env``).
    """
    value = os.environ.get(SCRAPE_CACHE_DIR_ENV_VAR)
    if not value:
        raise RuntimeError(
            f"{SCRAPE_CACHE_DIR_ENV_VAR} is not set. Configure it via the "
            "assembled .env (see config/prod/public.env) before running "
            "the engine."
        )
    return Path(value)


def get_site_dir() -> Path:
    """Return the path to the sibling ``stem-ecosystem`` site repo.

    Reads ``SITE_DIR`` from the environment if set; otherwise returns
    ``DEFAULT_SITE_DIR`` (``../stem-ecosystem`` relative to this repo).
    """
    value = os.environ.get(SITE_DIR_ENV_VAR)
    if value:
        return Path(value)
    return DEFAULT_SITE_DIR


def get_leaguesync_api_key() -> str:
    """Return the Bearer token for sync.jtlapp.net, stripped of quotes.

    Reads ``LEAGUESYNC_API_KEY`` from the environment on every call (no
    caching), matching ``get_scrape_cache_dir``'s pattern so tests can
    monkeypatch ``os.environ`` freely. The value observed in the
    assembled ``.env`` carries surrounding single quotes (dotconfig's
    round-trip of a SOPS-decrypted secret, e.g. ``LEAGUESYNC_API_KEY='abc123'``)
    -- stripped here so callers get the bare token, never the quote
    characters.

    Raises:
        RuntimeError: if ``LEAGUESYNC_API_KEY`` is not set (or is empty
            after stripping) -- there is no safe default for an API
            credential, matching ``get_scrape_cache_dir``'s convention.
    """
    value = os.environ.get(LEAGUESYNC_API_KEY_ENV_VAR)
    if value is not None:
        value = value.strip().strip("'\"").strip()
    if not value:
        raise RuntimeError(
            f"{LEAGUESYNC_API_KEY_ENV_VAR} is not set. Configure it via the "
            "assembled .env (see config/prod/secrets.env) before running "
            "the leaguesync adapter."
        )
    return value


def get_leaguesync_url() -> str:
    """Return the ``leaguesync`` adapter's API base URL.

    Reads ``LEAGUESYNC_URL`` from the environment if set; otherwise
    returns :data:`DEFAULT_LEAGUESYNC_URL`.
    """
    value = os.environ.get(LEAGUESYNC_URL_ENV_VAR)
    if value:
        return value
    return DEFAULT_LEAGUESYNC_URL
