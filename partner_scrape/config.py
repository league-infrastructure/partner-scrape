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
from typing import Any
from urllib.parse import urlparse

from partner_scrape.storage import Store, store_from_location


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

#: Environment variable holding the root *location* for the data output
#: (``sites.json``, images, ...): a local directory or ``s3://bucket/
#: prefix``. Defaults to :data:`DEFAULT_DATA_LOCATION` (the bucket); a
#: local directory only when set explicitly.
PARTNER_SCRAPE_DATA_DIR_ENV_VAR = "PARTNER_SCRAPE_DATA_DIR"

#: Default cache location -- the DigitalOcean Spaces bucket. A local
#: ``SCRAPE_CACHE_DIR`` is used only when set explicitly.
DEFAULT_CACHE_LOCATION = "s3://jtl-stem-ecosystem-scrape/cache"

#: Default data-output location -- the DigitalOcean Spaces bucket.
DEFAULT_DATA_LOCATION = "s3://jtl-stem-ecosystem-scrape/data"

#: DigitalOcean Spaces settings, used only when an ``s3://`` location is
#: in effect. The endpoint is the *region* endpoint, e.g.
#: ``https://sfo3.digitaloceanspaces.com`` -- never bucket-qualified.
DO_SPACES_ENDPOINT_ENV_VAR = "DO_SPACES_ENDPOINT"
DO_SPACES_ACCESS_KEY_ENV_VAR = "DO_SPACES_ACCESS_KEY"
DO_SPACES_SECRET_KEY_ENV_VAR = "DO_SPACES_SECRET_KEY"

#: Environment variable naming the site checkout used by Site Export
#: (defaults to the current working directory when unset).
SITE_DIR_ENV_VAR = "SITE_DIR"

#: Environment variable holding the Bearer token for the League's own
#: sync.jtlapp.net query API (``leaguesync`` adapter). Assembled by
#: dotconfig into ``config/prod/secrets.env`` -- there is no sane
#: default, so it must be set explicitly, matching
#: the other getters' convention.
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
#: run) -- see ``registry_data/sources/robotevents-vex-sd.toml``'s own
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

# This package's own directory, e.g. .../site-packages/partner_scrape
_PACKAGE_DIR = Path(__file__).resolve().parent

#: Environment variable overriding the registry location (sources/,
#: hubs/, candidates/, ads/ subdirectories). A *location string*: a
#: local directory today. Loaders resolve it only through
#: :func:`get_registry_dir`, so a later phase can accept an ``s3://``
#: location without touching callers; no bucket loading exists yet.
PARTNER_SCRAPE_REGISTRY_DIR_ENV_VAR = "PARTNER_SCRAPE_REGISTRY_DIR"

#: The registry bundled in the package (and the wheel) -- the default
#: when :data:`PARTNER_SCRAPE_REGISTRY_DIR_ENV_VAR` is unset. Read-only
#: by convention: when installed this lives in site-packages.
BUNDLED_REGISTRY_DIR = _PACKAGE_DIR / "registry_data"

#: Environment variable overriding where the local SQLite event store
#: (``store/event_store.py``) lives.
EVENT_STORE_PATH_ENV_VAR = "PARTNER_SCRAPE_EVENT_DB"


def get_registry_dir() -> Path:
    """Return the registry root: ``PARTNER_SCRAPE_REGISTRY_DIR`` if set,
    else the bundled :data:`BUNDLED_REGISTRY_DIR`.

    Reads the environment on every call. Only local paths are supported;
    an ``s3://`` (or other URL) value raises ``RuntimeError`` rather than
    being silently treated as a relative path.
    """
    value = os.environ.get(PARTNER_SCRAPE_REGISTRY_DIR_ENV_VAR)
    if not value:
        return BUNDLED_REGISTRY_DIR
    if "://" in value:
        raise RuntimeError(
            f"{PARTNER_SCRAPE_REGISTRY_DIR_ENV_VAR}={value!r}: remote registry "
            "locations are not supported yet; use a local directory."
        )
    return Path(value)


def get_sources_dir() -> Path:
    """Source Registry directory (``<registry>/sources``)."""
    return get_registry_dir() / "sources"


def get_hubs_dir() -> Path:
    """Hub Registry directory (``<registry>/hubs``)."""
    return get_registry_dir() / "hubs"


def get_ads_dir() -> Path:
    """Ad Registry directory (``<registry>/ads``)."""
    return get_registry_dir() / "ads"


def get_candidates_dir() -> Path:
    """Candidate Review Queue directory to *read* (``<registry>/candidates``)."""
    return get_registry_dir() / "candidates"


def get_candidates_write_dir() -> Path:
    """Directory ``discover-candidates`` *writes* new stubs into.

    The bundled registry is read-only when installed (site-packages), so
    the writer never targets it by default: with a registry override set
    it is ``<override>/candidates``; otherwise ``./candidates`` under the
    current working directory.
    """
    if os.environ.get(PARTNER_SCRAPE_REGISTRY_DIR_ENV_VAR):
        return get_candidates_dir()
    return Path.cwd() / "candidates"


def get_event_store_path() -> Path:
    """Local path of the SQLite event store (always local, never a bucket).

    ``PARTNER_SCRAPE_EVENT_DB`` if set; otherwise
    ``~/.partner-scrape/events.db`` -- deliberately independent of
    ``SCRAPE_CACHE_DIR``, which may be an ``s3://`` location.
    """
    value = os.environ.get(EVENT_STORE_PATH_ENV_VAR)
    if value:
        return Path(value)
    return Path.home() / ".partner-scrape" / "events.db"


def get_site_dir() -> Path:
    """Return the site checkout directory.

    ``SITE_DIR`` from the environment if set; otherwise the current
    working directory (there is no sibling-checkout default).
    """
    value = os.environ.get(SITE_DIR_ENV_VAR)
    if value:
        return Path(value)
    return Path.cwd()


def get_leaguesync_api_key() -> str:
    """Return the Bearer token for sync.jtlapp.net, stripped of quotes.

    Reads ``LEAGUESYNC_API_KEY`` from the environment on every call (no
    caching), matching the other getters' pattern so tests can
    monkeypatch ``os.environ`` freely. The value observed in the
    assembled ``.env`` carries surrounding single quotes (dotconfig's
    round-trip of a SOPS-decrypted secret, e.g. ``LEAGUESYNC_API_KEY='abc123'``)
    -- stripped here so callers get the bare token, never the quote
    characters.

    Raises:
        RuntimeError: if ``LEAGUESYNC_API_KEY`` is not set (or is empty
            after stripping) -- there is no safe default for an API
            credential, matching ``get_tba_api_key``'s convention.
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


# -- Bucket-backed storage (sprint 038 ticket 002) --------------------------

#: The shared boto3 client and the settings it was built from. Rebuilt
#: when the settings change so tests can monkeypatch the environment.
_s3_client: tuple[tuple[str, str, str], Any] | None = None


def _clean(value: str | None) -> str:
    """Strip whitespace and the quotes dotconfig leaves on secrets."""
    return (value or "").strip().strip("'\"").strip()


def _validate_endpoint(endpoint: str) -> str:
    """Return ``endpoint`` if it is a region endpoint, else raise.

    A DigitalOcean Spaces endpoint must be ``https://<region>.
    digitaloceanspaces.com``; a bucket-qualified one
    (``https://<bucket>.<region>.digitaloceanspaces.com``) makes boto
    address the bucket twice, so it is rejected with the fix spelled out.
    """
    parsed = urlparse(endpoint)
    host = parsed.hostname or ""
    labels = host.split(".")
    if parsed.scheme not in ("http", "https") or not host:
        raise RuntimeError(
            f"{DO_SPACES_ENDPOINT_ENV_VAR}={endpoint!r} is not a URL. Set it "
            "to the region endpoint, e.g. https://sfo3.digitaloceanspaces.com."
        )
    qualified = host.endswith(".digitaloceanspaces.com") and len(labels) != 3
    if qualified or parsed.path.strip("/"):
        region = labels[-3] if len(labels) >= 3 else "<region>"
        raise RuntimeError(
            f"{DO_SPACES_ENDPOINT_ENV_VAR}={endpoint!r} must be the region "
            "endpoint, not bucket-qualified or carrying a path. Use "
            f"https://{region}.digitaloceanspaces.com (the bucket name belongs "
            "in the s3:// location, not the endpoint)."
        )
    return endpoint


def _get_s3_client() -> Any:
    """Return the shared boto3 S3 client, building it on first use.

    Raises:
        RuntimeError: if any ``DO_SPACES_*`` variable is missing (all
            missing names are listed) or the endpoint is bucket-qualified.
    """
    global _s3_client
    values = {
        name: _clean(os.environ.get(name))
        for name in (
            DO_SPACES_ENDPOINT_ENV_VAR,
            DO_SPACES_ACCESS_KEY_ENV_VAR,
            DO_SPACES_SECRET_KEY_ENV_VAR,
        )
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(
            f"{', '.join(missing)} not set, but an s3:// location is in "
            "effect. Set them in the assembled .env (see "
            "config/prod/public.env and secrets.env), or point "
            f"{SCRAPE_CACHE_DIR_ENV_VAR}/{PARTNER_SCRAPE_DATA_DIR_ENV_VAR} at "
            "a local directory to run without the bucket."
        )
    endpoint = _validate_endpoint(values[DO_SPACES_ENDPOINT_ENV_VAR])
    settings = (
        endpoint,
        values[DO_SPACES_ACCESS_KEY_ENV_VAR],
        values[DO_SPACES_SECRET_KEY_ENV_VAR],
    )
    if _s3_client is None or _s3_client[0] != settings:
        import boto3  # deferred: --help and local-only runs never need it

        host = urlparse(endpoint).hostname or ""
        region = host.split(".")[0] if host.endswith(".digitaloceanspaces.com") else "us-east-1"
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=settings[1],
            aws_secret_access_key=settings[2],
            region_name=region,
        )
        _s3_client = (settings, client)
    return _s3_client[1]


def _store_for(env_var: str, default: str) -> Store:
    """Build the Store for ``env_var``'s location (default: the bucket)."""
    location = os.environ.get(env_var) or default
    client = _get_s3_client() if location.startswith("s3://") else None
    return store_from_location(location, client)


def get_scrape_cache_store() -> Store:
    """Return the Store holding the fetch/LLM caches.

    ``SCRAPE_CACHE_DIR`` is a local path or ``s3://bucket/prefix``;
    unset, it defaults to :data:`DEFAULT_CACHE_LOCATION`. Credentials
    are required only when the effective location is ``s3://``.
    """
    return _store_for(SCRAPE_CACHE_DIR_ENV_VAR, DEFAULT_CACHE_LOCATION)


def get_data_store() -> Store:
    """Return the Store receiving pipeline output (``sites.json``, ...).

    ``PARTNER_SCRAPE_DATA_DIR`` is a local path or ``s3://bucket/prefix``;
    unset, it defaults to :data:`DEFAULT_DATA_LOCATION`.
    """
    return _store_for(PARTNER_SCRAPE_DATA_DIR_ENV_VAR, DEFAULT_DATA_LOCATION)


def resolve_data_store(location: str | Path | Store | None = None) -> Store:
    """Return the data Store for an export function's ``own_data_dir``
    argument.

    ``None`` -> :func:`get_data_store`; an existing :class:`Store` is
    used as-is; a path or ``s3://`` string builds the matching Store
    (tests pass ``tmp_path``).
    """
    if location is None:
        return get_data_store()
    if isinstance(location, (str, Path)):
        text = str(location)
        client = _get_s3_client() if text.startswith("s3://") else None
        return store_from_location(location, client)
    return location
