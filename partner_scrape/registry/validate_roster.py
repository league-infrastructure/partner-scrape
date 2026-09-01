"""Roster data-quality and join-integrity validation primitives (issue 48).

Recovers, as pipeline-level validation, the guard coverage sprint 019/020
dropped when `site/`-local roster fixtures were deleted (see this
module's own callers' docstrings and sprint.md's Problem section) --
without recreating a second, committed copy of `partners.json` in this
repo (explicitly rejected, see sprint.md Scope > Out of Scope).

Two shapes of check live here, deliberately kept distinct rather than
unified into one always-raising function -- see sprint.md's Architecture
> Design Rationale for the full reasoning behind each:

- **Content checks** (:func:`validate_roster`): self-contained defects
  in `partners.json` itself -- a bad geocode, an out-of-bounds pin, a
  hijacked domain, a duplicate slug. These always raise, collecting
  every offender across every check into one combined
  :class:`RosterValidationError` before raising once (mirroring
  `export/publish.py`'s and `directory/export.py`'s existing
  `RuntimeError` message convention: state what's wrong, name the
  offending row(s), say what to check) -- never one exception per
  offender, so a real bad-data run surfaces the full picture in one
  failure, not one fix-and-rerun cycle per offender.
- **Join-integrity checks** (:func:`find_unresolved_active_sources`,
  :func:`check_partner_references`): cross-structure references that
  may or may not resolve. `find_unresolved_active_sources` is
  deliberately *non-raising* -- real production data has a live,
  currently-nonzero gap here (9 of 93 active sources), so a raising
  version would be a regression guard that breaks every real run rather
  than one that catches an actual regression; the caller decides what
  to do with the result (ticket 003 logs it as a warning).
  `check_partner_references` *does* raise -- it backs a small,
  fully hand-curated dataset (`places.toml`, ticket 004) with zero known
  gaps, so a hard raise there is safe and matches issue 48's framing of
  that join as a real-incident-shaped regression guard. It is written
  generically (`(referencer_id, partner_id)` pairs, not `Place`-typed)
  per issue 48's own instruction to reuse "the same validation
  primitive" for any future similar hand-copied-id join, not just this
  one.

`validate_roster` operates on the **raw** partner list -- a plain
`json.loads()` of `partners.json` -- never
`normalize.partners.load_partners()`'s name-deduplicated
`partners_by_norm` dict. `load_partners()`'s `setdefault()` means a
colliding second row never enters that dict in the first place, so a
duplicate-slug check built on it would be structurally blind to issue
46's exact failure mode (two exact-duplicate rows under different ids
silently overwriting each other's published directory in
`export/publish.py`'s `project()`). See sprint.md's Design Rationale for
the full "raw list, not deduplicated view" reasoning.

This module does no I/O of its own -- every function here takes
already-loaded Python data structures. Wiring it into `pipeline.run()`
and `directory.pipeline.run_directory()` (where the actual
`json.loads()`/`load_partners()` calls happen) is tickets 003 and 004,
not this one.
"""

from __future__ import annotations

from typing import Any

from partner_scrape.model import slugify
from partner_scrape.normalize.partners import find_partner
from partner_scrape.registry.schema import SourceConfig

#: San Diego County's bounding box -- the site map silently drops any
#: pin outside this box. Mirrors `stem-ecosystem`'s
#: `site/src/pages/partners/index.astro`'s own `SD_BOUNDS` constant
#: (ported here from the deleted `tests/test_roster_housekeeping.py`'s
#: identical constant, sprint 018 ticket 002) -- kept in sync by hand
#: across repos, since the value lives in an Astro page one repo away,
#: not an importable Python module (see sprint.md's Migration Concerns).
SD_BOUNDS: dict[str, float] = {
    "latMin": 32.4,
    "latMax": 33.5,
    "lngMin": -117.7,
    "lngMax": -116.0,
}

#: Google's geocoder centroid for the bare string "California" --
#: sprint 011's known bad-centroid signature, ported from the same
#: deleted test's `BARE_CALIFORNIA_CENTROID` constant.
BARE_CALIFORNIA_CENTROID: tuple[float, float] = (36.778261, -119.417932)

#: Domains known to have been hijacked (a partner's `website` pointing
#: at a domain the organization no longer controls). Seeded with the
#: one real incident this module's deleted-test predecessor guarded
#: against -- a `frozenset` so a future hijacked domain is a one-line
#: addition.
HIJACKED_DOMAINS: frozenset[str] = frozenset({"batiquitosfoundation.org"})


class RosterValidationError(Exception):
    """Raised by this module's content and reference-join checks.

    Every raise here carries every offender the check found, not just
    the first -- see this module's own docstring for why.
    """


def _is_number(value: Any) -> bool:
    """`True` for a real `int`/`float` (never `bool`, never a numeric
    string) -- the "numeric" half of this module's malformed-coordinate
    definition."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _row_ident(partner: dict[str, Any]) -> str:
    """A short, human-readable identifier for `partner`: its `id` and/or
    `name`, whichever are present -- always included in an offender
    message so a raised `RosterValidationError` names the actual
    offending row, never just an index into the list."""
    partner_id = partner.get("id")
    name = partner.get("name")
    if partner_id is not None and name:
        return f"id={partner_id!r} name={name!r}"
    if partner_id is not None:
        return f"id={partner_id!r}"
    if name:
        return f"name={name!r}"
    return "<row with no id or name>"


def _coordinate_offenders(
    partners: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    """Walk `partners` once, returning `(centroid_offenders,
    coordinate_offenders)` -- the bare-California-centroid check and the
    out-of-bounds/malformed check are two distinct content checks (each
    gets its own fires/passes test coverage), but both need the same
    per-row coordinate parsing, so they share this one pass rather than
    walking the list twice.

    A row with both `latitude` and `longitude` absent/`None` is skipped
    entirely by both checks -- the documented "no coordinate yet" state,
    not an offender for either.
    """
    centroid_offenders: list[str] = []
    coordinate_offenders: list[str] = []

    for partner in partners:
        latitude = partner.get("latitude")
        longitude = partner.get("longitude")
        latitude_missing = latitude is None
        longitude_missing = longitude is None

        if latitude_missing and longitude_missing:
            continue

        if (
            latitude_missing != longitude_missing
            or not _is_number(latitude)
            or not _is_number(longitude)
        ):
            coordinate_offenders.append(
                f"{_row_ident(partner)}: malformed coordinate "
                f"(latitude={latitude!r}, longitude={longitude!r})"
            )
            continue

        lat = float(latitude)
        lng = float(longitude)

        if (
            round(lat, 6) == BARE_CALIFORNIA_CENTROID[0]
            and round(lng, 6) == BARE_CALIFORNIA_CENTROID[1]
        ):
            centroid_offenders.append(
                f"{_row_ident(partner)}: coordinate ({lat}, {lng}) matches the "
                "bare-California geocoder centroid"
            )

        if not (
            SD_BOUNDS["latMin"] <= lat <= SD_BOUNDS["latMax"]
            and SD_BOUNDS["lngMin"] <= lng <= SD_BOUNDS["lngMax"]
        ):
            coordinate_offenders.append(
                f"{_row_ident(partner)}: coordinate ({lat}, {lng}) is outside "
                "San Diego County's bounding box"
            )

    return centroid_offenders, coordinate_offenders


def _hijacked_domain_offenders(partners: list[dict[str, Any]]) -> list[str]:
    offenders: list[str] = []
    for partner in partners:
        website = partner.get("website") or ""
        hit = next((domain for domain in HIJACKED_DOMAINS if domain in website), None)
        if hit is not None:
            offenders.append(
                f"{_row_ident(partner)}: website ({website!r}) contains known-hijacked "
                f"domain {hit!r}"
            )
    return offenders


def _duplicate_slug_offenders(partners: list[dict[str, Any]]) -> list[str]:
    """Group `partners` by `model.slugify(name)` over the **raw** list
    passed in -- the caller (`validate_roster`) never passes a
    deduplicated view, which is exactly what makes this check able to
    catch issue 46's failure mode at all (see module docstring).
    Reports every colliding slug group found, each naming every row in
    that group, not just the first pair."""
    rows_by_slug: dict[str, list[dict[str, Any]]] = {}
    for partner in partners:
        slug = slugify(partner.get("name", ""))
        rows_by_slug.setdefault(slug, []).append(partner)

    offenders: list[str] = []
    for slug, rows in rows_by_slug.items():
        if len(rows) > 1:
            row_idents = ", ".join(_row_ident(row) for row in rows)
            offenders.append(
                f"slug {slug!r} shared by {len(rows)} rows: {row_idents}"
            )
    return offenders


def validate_roster(partners: list[dict[str, Any]]) -> None:
    """Run every content check against the **raw** `partners` list,
    raising one combined :class:`RosterValidationError` if any check
    finds an offender.

    Args:
        partners: the raw partner list -- a plain `json.loads()` of
            `partners.json`, never `normalize.partners.load_partners()`'s
            name-deduplicated `partners_by_norm` dict (see module
            docstring for why that distinction matters).

    Raises:
        RosterValidationError: one or more rows fail one or more of:
            bare-California geocoder centroid, out-of-bounds/malformed
            coordinate, hijacked domain, or duplicate `model.slugify()`
            slug. Every offender found across every check is named in
            the single raised message -- this function never raises on
            the first offender found.
    """
    centroid_offenders, coordinate_offenders = _coordinate_offenders(partners)
    hijacked_offenders = _hijacked_domain_offenders(partners)
    slug_offenders = _duplicate_slug_offenders(partners)

    sections: list[str] = []
    if centroid_offenders:
        sections.append(
            "Bare-California geocoder centroid "
            f"{BARE_CALIFORNIA_CENTROID} found -- re-geocode these rows:\n  "
            + "\n  ".join(centroid_offenders)
        )
    if coordinate_offenders:
        sections.append(
            "Out-of-bounds or malformed coordinate found -- fix or clear "
            "latitude/longitude for these rows:\n  " + "\n  ".join(coordinate_offenders)
        )
    if hijacked_offenders:
        sections.append(
            "Hijacked domain found in website field -- replace with the "
            "organization's real site:\n  " + "\n  ".join(hijacked_offenders)
        )
    if slug_offenders:
        sections.append(
            "Duplicate model.slugify() slug found -- these rows will silently "
            "overwrite each other's published directory in export/publish.py's "
            "project() -- rename or merge them:\n  " + "\n  ".join(slug_offenders)
        )

    if sections:
        raise RosterValidationError(
            "Roster validation failed for partners.json:\n\n" + "\n\n".join(sections)
        )


def find_unresolved_active_sources(
    sources: list[SourceConfig], partners_by_norm: dict[str, dict[str, Any]]
) -> list[str]:
    """Return the `org_name`s of every `source` in `sources` whose
    normalized `org_name` has no match in `partners_by_norm`.

    Never raises -- the caller decides what to do with the result
    (ticket 003 logs it as a warning; see module docstring for why a
    raising version here would be a regression guard that breaks every
    real run, not one that catches an actual regression).

    Args:
        sources: registry sources to check (typically
            `registry.loader.load_active_sources()`'s result).
        partners_by_norm: `normalize.partners.load_partners()`'s
            normalized-name-keyed dict.

    Returns:
        The unresolved `org_name`s, in `sources` order. Empty when every
        source resolves.
    """
    return [
        source.org_name
        for source in sources
        if find_partner(source.org_name, partners_by_norm) is None
    ]


def check_partner_references(
    references: list[tuple[str, int]], partners: list[dict[str, Any]]
) -> None:
    """Generic id-reference join-integrity check: raise if any
    `(referencer_id, partner_id)` pair in `references` names a
    `partner_id` that is not among `partners`' real `id` values.

    Written generically -- not `Place`-typed or `directory`-specific --
    per issue 48's own instruction to reuse "the same validation
    primitive" for any hand-copied-id join, not just the `places.toml`
    case (ticket 004) that is its first real caller.

    Args:
        references: `(referencer_id, partner_id)` pairs. Already
            filtered to exclude any `None` `partner_id` by the caller --
            this function does not special-case `None`.
        partners: the raw partner list (see :func:`validate_roster`) to
            join against.

    Raises:
        RosterValidationError: naming every dangling
            `(referencer_id, partner_id)` pair found, all in one
            message -- never one exception per offender. Does not raise
            when every reference resolves.
    """
    valid_ids = {partner["id"] for partner in partners if partner.get("id") is not None}
    dangling = [
        (referencer_id, partner_id)
        for referencer_id, partner_id in references
        if partner_id not in valid_ids
    ]
    if not dangling:
        return

    offenders = "\n  ".join(
        f"{referencer_id} -> partner_id={partner_id!r} (no matching partners.json id)"
        for referencer_id, partner_id in dangling
    )
    raise RosterValidationError(
        "Dangling partner reference(s) found -- these referencer_id -> "
        "partner_id pairs do not resolve against any real partners.json id. "
        f"Check that each referencer's related_partner_id is correct:\n  {offenders}"
    )
