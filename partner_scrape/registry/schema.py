"""The Source Registry schema: ``SourceConfig`` and its TOML constructor.

A ``SourceConfig`` describes, in data, one organization and how to
reach its events -- the Registry's whole job (sprint.md Architecture >
Source Registry, SUC-001). ``config``, ``taxonomy_defaults``, and
``acquisition_policy`` are kept as plain ``dict``s rather than
further-typed sub-schemas: different ``adapter_type``s need different
shapes in ``config`` (e.g. ``api_base`` for ``tec_rest``, ``feed_url``
for ``ical``), and over-typing it now would need revisiting the moment
a fourth adapter type arrives.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Top-level TOML keys every source file must define. A file missing
#: any of these raises InvalidSourceConfig, which the directory loader
#: (loader.py) catches, logs, and skips -- never fatal to the whole
#: registry load (SUC-001 Acceptance Criteria).
_REQUIRED_FIELDS = ("org_name", "adapter_type", "config")

#: Defaults applied to ``acquisition_policy`` keys a source file omits.
#: Ticket 003 (Fetch & Cache) is the actual consumer of these values;
#: this module only owns supplying sane defaults so hand-authored TOML
#: files aren't required to repeat this boilerplate in every file.
#: ``fetch_strategy`` defaults to ``"static"`` -- ticket 005's Pipeline
#: reads this key (``source.acquisition_policy.get("fetch_strategy",
#: "static")``) to pick between the run's default ``Fetcher`` and a
#: lazily-constructed headless one (``"headless"``, ``fetch/headless.py``
#: ``PlaywrightFetcher``). Purely additive: every source TOML file
#: written before this key existed has no ``fetch_strategy`` line and
#: resolves to ``"static"`` here, identical to its pre-ticket-005 fetch
#: behavior -- see sprint.md's Migration Concerns.
_ACQUISITION_POLICY_DEFAULTS: dict[str, Any] = {
    "rate_limit_seconds": 1.0,
    "respect_robots": True,
    "discovered_via": "manual",
    "fetch_strategy": "static",
}


class InvalidSourceConfig(Exception):
    """Raised when a source TOML file is missing a required field.

    Caught at the directory-loader level (loader.py): a single bad file
    is logged and skipped, never fatal to the whole registry load.
    """


@dataclass
class SourceConfig:
    """One organization's source-of-record for its events.

    ``source_id`` is derived from the TOML file's stem (e.g.
    ``coastalrootsfarm.toml`` -> ``"coastalrootsfarm"``) rather than
    read from a field inside the file -- the filename *is* the
    identifier, so it cannot drift out of sync with the field the way a
    duplicated in-file ``source_id`` could.
    """

    source_id: str
    org_name: str
    adapter_type: str
    config: dict[str, Any]
    taxonomy_defaults: dict[str, Any] = field(default_factory=dict)
    acquisition_policy: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    @classmethod
    def from_toml(cls, path: Path) -> SourceConfig:
        """Parse and validate one source TOML file.

        Raises:
            InvalidSourceConfig: a required field (``org_name``,
                ``adapter_type``, or ``config``) is missing.
            tomllib.TOMLDecodeError: the file is not valid TOML. Left
                unwrapped -- the directory loader treats it the same as
                InvalidSourceConfig (log and skip) but callers reading a
                single file directly may want to tell the two apart.
        """
        with open(path, "rb") as f:
            data = tomllib.load(f)

        missing = [name for name in _REQUIRED_FIELDS if name not in data]
        if missing:
            raise InvalidSourceConfig(
                f"{path}: missing required field(s): {', '.join(missing)}"
            )

        acquisition_policy = {
            **_ACQUISITION_POLICY_DEFAULTS,
            **data.get("acquisition_policy", {}),
        }

        return cls(
            source_id=path.stem,
            org_name=data["org_name"],
            adapter_type=data["adapter_type"],
            config=data["config"],
            taxonomy_defaults=data.get("taxonomy_defaults", {}),
            acquisition_policy=acquisition_policy,
            enabled=data.get("enabled", True),
        )
