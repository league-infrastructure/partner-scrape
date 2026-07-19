"""Partner join: normalized-org-name lookup against the site's `partners.json`.

Reads (never writes) the site's `partners.json` -- see sprint.md's
Architecture > Normalize & Dedup boundary ("Inside: ... partner join
(reads the site's `partners.json` read-only)") and Impact on Existing
Components ("the partner join in Normalize & Dedup reads the site's
`../stem-ecosystem/src/data/partners.json` directly, matching
`dev/export_site.py`'s existing behavior").

No match -> the caller keeps the org name and leaves `partner_id`
unset (SUC-005's documented error flow). This module never raises for
an unmatched org -- :func:`find_partner` just returns `None`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_NON_ALNUM_RE = re.compile(r"[^a-z0-9 ]")
_LEADING_THE_RE = re.compile(r"^the ")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_org_name(name: str) -> str:
    """Normalize an organization name for partner-join matching.

    Lowercases, strips punctuation (keeping spaces), drops a leading
    "the ", and collapses whitespace -- e.g. "The Living Coast
    Discovery Center" and "Living Coast Discovery Center" normalize
    identically. Ported from `dev/export_site.py`'s `norm_name`.
    """
    lowered = name.lower()
    no_punctuation = _NON_ALNUM_RE.sub("", lowered)
    no_leading_the = _LEADING_THE_RE.sub("", no_punctuation.strip())
    return _WHITESPACE_RE.sub(" ", no_leading_the).strip()


def load_partners(partners_path: str | Path) -> dict[str, dict[str, Any]]:
    """Load `partners.json` into a dict keyed by :func:`normalize_org_name`.

    The first partner record wins a normalized-name collision, matching
    `dev/export_site.py`'s `load_site_partners`'s `setdefault` behavior.
    """
    data = json.loads(Path(partners_path).read_text())
    by_norm: dict[str, dict[str, Any]] = {}
    for partner in data:
        by_norm.setdefault(normalize_org_name(partner.get("name", "")), partner)
    return by_norm


def find_partner(org_name: str, partners_by_norm: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Look up ``org_name`` in ``partners_by_norm``; `None` on no match."""
    return partners_by_norm.get(normalize_org_name(org_name))
