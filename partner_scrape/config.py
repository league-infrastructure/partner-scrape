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

Sprint 023 ticket 001 adds :class:`CredentialError`, a dedicated
``RuntimeError`` subclass raised specifically by
:func:`get_tba_api_key`/:func:`get_robotevents_api_key` when their env
var is unset -- and, in ``teams/sources/tba.py``/``teams/sources/
robotevents.py``, specifically by each source's ``discover()`` 401
branch. Every other config accessor here, and every other raise branch
in those two ``discover()`` methods, keeps raising plain
``RuntimeError`` unchanged. The point is letting
``teams.pipeline.run_teams()`` tell a structural, recurring credential
failure (issue 62) apart from a one-off scrape hiccup by exception type
rather than by message-substring matching -- see sprint.md's Design
Rationale ("a dedicated ``CredentialError`` type, not message-substring
matching") for the full reasoning.
"""

from __future__ import annotations

import os
from pathlib import Path

class CredentialError(RuntimeError):
    """A structural, recurring credential failure -- a missing/invalid
    API key or a 401 response -- as distinct from a transient/one-off
    scrape failure (a bad page, a flaky network blip).

    A plain marker subclass, no new behavior: it exists so
    ``teams.pipeline.run_teams()`` can catch this specifically (before
    its existing broader ``except Exception``) and raise exactly one
    aggregate alert naming every affected league/source, rather than
    treating a credential outage the same as any other per-source
    hiccup (issue 62). Since it subclasses ``RuntimeError``, every
    existing ``except RuntimeError``/``except Exception`` call site
    continues to catch it unchanged -- this ticket narrows *which*
    exception type specific raise sites use, it does not change what
    catches them.
    """


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

#: Environment variable holding the ``X-TBA-Auth-Key`` header value for
#: The Blue Alliance's v3 API (``teams.sources.tba``). Assembled by
#: dotconfig into ``config/prod/secrets.env`` -- there is no sane
#: default, so it must be set explicitly, matching
#: ``get_leaguesync_api_key()``'s convention exactly. Provisioned and
#: verified working in ``.env``/``config/prod/secrets.env`` as of
#: ticket 011-003, but **not yet** in the scheduled workflow's GitHub
#: Actions repo secrets (sprint.md's Migration Concerns) -- a scheduled
#: run will hit this unset until an operator pushes it, which is why
#: ``teams.pipeline.run_teams()`` must isolate a TBA source failure the
#: same way it isolates any other source's.
TBA_API_KEY_ENV_VAR = "TBA_KEY"

#: Environment variable overriding The Blue Alliance API's base URL.
#: Overridable so a future staging mirror doesn't require a code
#: change, matching ``LEAGUESYNC_URL_ENV_VAR``'s convention.
TBA_URL_ENV_VAR = "TBA_URL"

#: Default base URL for The Blue Alliance's v3 API -- confirmed live
#: (``GET /api/v3/status``, ``GET /api/v3/teams/{page}``) during the
#: TBA source's build.
DEFAULT_TBA_URL = "https://www.thebluealliance.com"

#: Environment variable holding the Bearer token for RobotEvents API v2
#: (``adapters.robotevents``, sprint 016 ticket 004; ``teams.sources.
#: robotevents``, ticket 005). Assembled by dotconfig into
#: ``config/prod/secrets.env`` -- there is no sane default, so it must
#: be set explicitly, matching ``get_tba_api_key()``'s convention
#: exactly. **Not yet provisioned** in ``config/prod/secrets.env`` as of
#: this ticket (sprint.md's Migration Concerns) -- getting a real value
#: requires a RobotEvents account (robotevents.com), the same
#: operator-provisioning gap ``TBA_KEY`` had before ticket 011-003.
#: Both ``pipeline.run()`` and ``teams.pipeline.run_teams()`` isolate
#: this source's failure the same way they isolate any other source's
#: (a missing/invalid key degrades that one source, never aborts the
#: run) -- see ``registry/sources/robotevents-vex-sd.toml``'s own
#: comment for the provisioning steps (account -> API key -> SOPS
#: ``secrets.env`` entry).
ROBOTEVENTS_API_KEY_ENV_VAR = "ROBOTEVENTS_KEY"

#: Environment variable overriding the RobotEvents API's base URL.
#: Overridable so a future staging/mirror deployment doesn't require a
#: code change, matching ``TBA_URL_ENV_VAR``'s convention.
ROBOTEVENTS_URL_ENV_VAR = "ROBOTEVENTS_URL"

#: Default base URL for RobotEvents API v2. Unlike ``DEFAULT_TBA_URL``,
#: this was **not** confirmed via a live authenticated probe during
#: this ticket -- no ``ROBOTEVENTS_KEY`` was available (Migration
#: Concerns), and every documented RobotEvents v2 endpoint requires the
#: Bearer token, so there is no unauthenticated live call this ticket
#: could run instead. Confirmed instead against RobotEvents' own
#: published OpenAPI schema, via the ``baseUrl`` the actively-maintained
#: open-source ``robotevents`` npm client
#: (https://github.com/brenapp/robotevents) is generated against and
#: constructs its client with (``createClient()`` in
#: ``src/utils/client.ts``: ``baseUrl: "https://www.robotevents.com/api/v2"``).
#: Re-verify live (``GET /events`` with a real token) the first time one
#: is provisioned.
DEFAULT_ROBOTEVENTS_URL = "https://www.robotevents.com/api/v2"

# This package's own directory, e.g. .../partner-scrape/partner_scrape
_PACKAGE_DIR = Path(__file__).resolve().parent

# The repo root, e.g. .../partner-scrape
_REPO_ROOT = _PACKAGE_DIR.parent

#: The repo root, e.g. ``.../partner-scrape`` -- a public alias for
#: :data:`_REPO_ROOT`. Exists so other modules needing a root-relative
#: default (e.g. the root-level ``registry/`` data directory) can import
#: one shared constant instead of each recomputing their own
#: ``Path(__file__).resolve()`` parent-chain (sprint 025 ticket 001).
REPO_ROOT = _REPO_ROOT

#: Default location of the sibling ``stem-ecosystem`` site repo -- the
#: real production site codebase, checked out next to this repo
#: (``../stem-ecosystem`` relative to the repo root) for local
#: interactive runs, and used by default in CI. Overridable via
#: ``SITE_DIR``.
DEFAULT_SITE_DIR = _REPO_ROOT.parent / "stem-ecosystem"

#: Default location of this repo's own pipeline-output publish target
#: (``data/`` at the repo root). Not overridable via environment
#: variable -- the location is fixed by design (see sprint 020's
#: Design Rationale and Open Questions).
DEFAULT_OWN_DATA_DIR = _REPO_ROOT / "data"


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


def get_own_data_dir() -> Path:
    """Return the path to this repo's own pipeline-output publish target.

    Always returns ``DEFAULT_OWN_DATA_DIR`` (``<repo_root>/data``) --
    unlike ``get_site_dir()``, this has no environment variable override;
    the location is fixed by design.
    """
    return DEFAULT_OWN_DATA_DIR


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


def get_tba_api_key() -> str:
    """Return the ``X-TBA-Auth-Key`` header value, stripped of quotes.

    Reads ``TBA_KEY`` from the environment on every call (no caching),
    mirroring ``get_leaguesync_api_key()`` exactly -- including the
    quote-stripping the assembled ``.env`` needs (dotconfig's
    round-trip of a SOPS-decrypted secret carries surrounding single
    quotes, e.g. ``TBA_KEY='abc123'``) -- so callers get the bare
    token, never the quote characters.

    Raises:
        CredentialError: if ``TBA_KEY`` is not set (or is empty after
            stripping) -- there is no safe default for an API
            credential, matching ``get_leaguesync_api_key()``'s
            convention, except that this specific missing-credential
            case raises the dedicated ``CredentialError`` subclass
            (sprint 023 ticket 001), not a bare ``RuntimeError``. This
            is the failure mode ``teams.pipeline.run_teams()`` must
            isolate (Migration Concerns): a missing ``TBA_KEY``
            degrades the ``teams`` export to FTC-only, it must never
            raise out of the whole run -- and, since ``CredentialError``
            is-a ``RuntimeError``, every existing catch site keeps
            working unchanged; only ``run_teams()``'s new aggregate
            credential-failure alert additionally distinguishes it.
    """
    value = os.environ.get(TBA_API_KEY_ENV_VAR)
    if value is not None:
        value = value.strip().strip("'\"").strip()
    if not value:
        raise CredentialError(
            f"{TBA_API_KEY_ENV_VAR} is not set. Configure it via the "
            "assembled .env (see config/prod/secrets.env) before running "
            "the tba team source."
        )
    return value


def get_tba_url() -> str:
    """Return The Blue Alliance API's base URL.

    Reads ``TBA_URL`` from the environment if set; otherwise returns
    :data:`DEFAULT_TBA_URL`.
    """
    value = os.environ.get(TBA_URL_ENV_VAR)
    if value:
        return value
    return DEFAULT_TBA_URL


def get_robotevents_api_key() -> str:
    """Return the RobotEvents API v2 Bearer token, stripped of quotes.

    Reads ``ROBOTEVENTS_KEY`` from the environment on every call (no
    caching), mirroring ``get_tba_api_key()`` exactly -- including the
    quote-stripping the assembled ``.env`` needs (dotconfig's
    round-trip of a SOPS-decrypted secret carries surrounding single
    quotes, e.g. ``ROBOTEVENTS_KEY='abc123'``) -- so callers get the
    bare token, never the quote characters.

    Raises:
        CredentialError: if ``ROBOTEVENTS_KEY`` is not set (or is empty
            after stripping) -- there is no safe default for an API
            credential, matching ``get_tba_api_key()``'s convention,
            including that convention's sprint 023 ticket 001 update:
            this specific missing-credential case raises the dedicated
            ``CredentialError`` subclass, not a bare ``RuntimeError``.
            This is the failure mode both ``pipeline.run()`` and
            ``teams.pipeline.run_teams()`` must isolate (see
            :data:`ROBOTEVENTS_API_KEY_ENV_VAR`'s own docstring): a
            missing ``ROBOTEVENTS_KEY`` degrades to that one source
            being skipped, it must never raise out of the whole run --
            and, since ``CredentialError`` is-a ``RuntimeError``, every
            existing catch site keeps working unchanged; only
            ``run_teams()``'s new aggregate credential-failure alert
            additionally distinguishes it.
    """
    value = os.environ.get(ROBOTEVENTS_API_KEY_ENV_VAR)
    if value is not None:
        value = value.strip().strip("'\"").strip()
    if not value:
        raise CredentialError(
            f"{ROBOTEVENTS_API_KEY_ENV_VAR} is not set. Configure it via the "
            "assembled .env (see config/prod/secrets.env) before running "
            "the robotevents adapter/team source."
        )
    return value


def get_robotevents_url() -> str:
    """Return RobotEvents API v2's base URL.

    Reads ``ROBOTEVENTS_URL`` from the environment if set; otherwise
    returns :data:`DEFAULT_ROBOTEVENTS_URL`.
    """
    value = os.environ.get(ROBOTEVENTS_URL_ENV_VAR)
    if value:
        return value
    return DEFAULT_ROBOTEVENTS_URL
