"""The shared, fully offline geocoding ladder (``geo_ladder``).

Extracted from ``teams/geo.py`` in ticket 018-006 so both ``teams/``
and the new ``directory/`` module (Places, Clubs -- ticket 018-007/
008) can resolve an organization/place name to a location through the
same "never guess" precision ladder, without either module depending
on the other and without duplicating logic that has real, hard-won
bug-fix history (the fuzzy school-name matching thresholds, the
"prefer Active over Closed" school dedup, the rung-7 honesty rule).
Clubs in particular need this: a Hack Club chapter (ticket 018-008) is
hosted by a real school, so the CDE/NCES school-matching rungs are
exactly as relevant to a school-based club as to a robotics team, not
robotics-specific at all.

This module owns **no** knowledge of any caller's own record type
(``Team``, the future ``Place``/``Club``) -- every public function and
method here takes plain strings (``organization``, ``city``,
``postal_code``) and returns a :class:`LocationMatch`, never mutating
a caller-owned object. Stamping a match onto a specific dataclass's
fields is each caller's own job (see ``teams/geo.py``'s
``SchoolIndex.resolve(team)`` for the ``Team``-specific example).

Deliberately, structurally offline: **zero network calls, ever** (see
``teams/geo.py``'s own docstring for the live-geocoder failure rates
that originally motivated this). This module reads only whatever data
files a caller's ``data_dir`` points at and never imports
``partner_scrape.fetch`` or any of Python's own networking modules.

## The ladder

Highest precision first. Every rung returns a :class:`LocationMatch`
carrying ``location_precision`` and ``matched_name`` (so "why is this
location here?" always has a string answer), and, for the two fuzzy
school rungs, ``needs_review``:

1. ``school-overrides.toml`` -- hand corrections for the residue a
   human has actually verified. -> ``"school"``
2. CDE **and** NCES exact normalized-name match, city-filtered when the
   normalized name is ambiguous across sources/cities. -> ``"school"``
3. Token-set match, Jaccard >= 0.60, restricted to schools in the same
   (normalized) city as the caller's reported city. -> ``"school"``
4. Token-set match, Jaccard >= 0.80, county-wide (no city restriction).
   -> ``"school"``
5. ZIP centroid, from a postal code. -> ``"zip"``
6. City centroid, from a city name. -> ``"city"``
7. No match anywhere above -> ``"none"``, coordinates left ``None``.
   **Deliberate, not a bug**: a caller that exhausts every rung gets no
   pin at all rather than a fabricated one -- the "never guess" honesty
   rule this whole module exists to enforce.

Rungs 3 and 4 are two different *candidate pools* (same-city vs.
county-wide) at two different acceptance thresholds, but
``needs_review`` is set from the actual computed Jaccard score, not
from which rung accepted the match.

## Caching

:class:`GeoLadder` caches rungs 1-4's outcome (a hit *or* a confirmed
miss) keyed by :func:`normalize_school_name` of the ``organization``
argument alone -- not by ``(organization, city)``. This is deliberate:
per ``teams/geo.py``'s own measurement, many organizations collapse
onto a much smaller number of distinct real-world schools, so a
per-call cache would repeat a large fraction of the matching work for
no benefit -- two lookups for the *same* normalized organization name
are, by construction, the same real-world school, so city is only ever
needed to disambiguate the *first* lookup for that name. Negative
outcomes (rungs 1-4 all miss) are cached too. This cache is in-memory
and scoped to one :class:`GeoLadder` instance -- there is no cross-run/
disk persistence (see ``teams/geo.py``'s own docstring for the fuller
comparison against ``enrich/cache.py``'s disk-persisted cache; nothing
here costs money or meaningfully more wall-clock time on a second run).

## Malformed data fails loudly

A missing or unparseable data file raises ``RuntimeError`` out of
:meth:`GeoLadder.__init__` -- a bad geocoding table is a build-time
defect to fix before the next run, not a per-record failure to log and
skip.
"""

from __future__ import annotations

import csv
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

_PARENTHETICAL_RE = re.compile(r"\([^)]*\)")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9 ]")
_WHITESPACE_RE = re.compile(r"\s+")

#: Generic institution-type tokens with no identifying signal, dropped
#: from every normalized name -- *not* type words like "high"/
#: "middle"/"elementary"/"senior" (those genuinely distinguish two real
#: schools at the same place, e.g. "Poway High" vs. a hypothetical
#: "Poway Middle", and must never be discarded). Measured live running
#: this ladder against the real 211-team FTC+FRC corpus: without this,
#: a team-reported "X High School" against CDE's own official "X High"
#: (CDE almost never carries the word "School" itself) collapses two
#: identical real-world schools to a 0.67-0.75 Jaccard score --
#: genuinely correct matches, flooding `needs_review` with noise rather
#: than reserving it for actually-uncertain cases like "Classical
#: Academy Online" fuzzy-matching its sponsoring district's building.
#: "sch" catches CDE's own abbreviated form (e.g. "High Tech Middle Sch
#: Mesa"); "the" matches `normalize.partners.normalize_org_name`'s own
#: precedent of dropping a leading "the" (not reused directly -- see
#: this module's docstring -- but the same reasoning applies to place
#: names too).
_STOPWORD_TOKENS = frozenset({"school", "schools", "sch", "the"})

#: CDE `StatusType` preference order for de-duplicating rows that share
#: a normalized school name -- lower wins. Only ever relevant to a
#: fixture/future refresh that carries more than one status for the
#: same name; the real committed `sd-schools-public.tsv` ships
#: `StatusType == "Active"` rows only, so this is defense in depth.
_STATUS_RANK = {"Active": 0, "Closed": 1, "Merged": 2}

#: CDE `Virtual` codes meaning "no real campus" -- rejected on load, the
#: same criterion `dev/refresh_school_directories.py` already applies
#: when writing `sd-schools-public.tsv`. Duplicated here, not just
#: there, for the same defense-in-depth reason as `_STATUS_RANK`: an
#: online school fuzzy-matching its sponsoring district's building (the
#: "Classical Academy Online" case) is exactly the failure this guards
#: against.
_VIRTUAL_REJECT = {"F", "V"}


def normalize_school_name(name: str) -> str:
    """Normalize a school/organization name for exact and token-set
    matching.

    Strips parenthetical asides (CDE writes some names as ``"Surname
    (Given Name)"``, e.g. ``"Feaster (Mae L.) Charter"`` -- dropping the
    parenthetical recovers the class of matches that pattern otherwise
    breaks), lowercases, strips punctuation, and collapses whitespace.
    A small, separately-named normalizer -- deliberately *not*
    `normalize.partners.normalize_org_name`, which is scoped to
    partner-directory organization names, not place names.
    """
    no_parens = _PARENTHETICAL_RE.sub(" ", name)
    lowered = no_parens.lower()
    no_punct = _NON_ALNUM_RE.sub(" ", lowered)
    collapsed = _WHITESPACE_RE.sub(" ", no_punct).strip()
    tokens = [t for t in collapsed.split(" ") if t and t not in _STOPWORD_TOKENS]
    return " ".join(tokens)


def normalize_city_name(city: str) -> str:
    """Normalize a city string for matching/lookup.

    Strips and lowercases -- e.g. ``"La Jolla "``, ``"carlsbad"``, and
    ``"San Diego"`` all normalize to a single canonical form.
    """
    return _WHITESPACE_RE.sub(" ", (city or "").strip().lower())


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass(frozen=True)
class _SchoolRecord:
    name: str
    normalized_name: str
    tokens: frozenset[str]
    normalized_city: str
    latitude: float
    longitude: float
    website: str = ""


@dataclass(frozen=True)
class _Override:
    matched_name: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class LocationMatch:
    """The result of resolving one ``(organization, city, postal_code)``
    through the ladder -- generic, caller-independent.

    ``website`` is only ever non-empty on a school-precision match
    against a school record that itself carries a website (public
    schools only -- NCES's private-school data has no website column);
    ``""`` otherwise, never fabricated. ``location_precision`` is one
    of ``"school"``, ``"zip"``, ``"city"``, or ``"none"``.
    """

    latitude: float | None
    longitude: float | None
    location_precision: str
    matched_name: str
    needs_review: bool = False
    website: str = ""


class _DataFileError(RuntimeError):
    """A geocoding data file under `data_dir` is missing or malformed."""


def _require_file(path: Path) -> Path:
    if not path.is_file():
        raise _DataFileError(
            f"Missing offline geocoding data file: {path}. Run "
            "dev/refresh_school_directories.py (CDE/NCES/centroid files) "
            "or check the data directory's school-overrides.toml (hand-maintained)."
        )
    return path


def _load_school_tsv(path: Path, *, dedup_by_status: bool) -> list[_SchoolRecord]:
    """Load one school-directory TSV (`sd-schools-public.tsv` or
    `sd-schools-private.tsv`) into `_SchoolRecord`s.

    ``dedup_by_status=True`` (public schools only) keeps, per
    normalized name, only the row with the best `_STATUS_RANK` --
    "prefer StatusType == Active over Closed".
    """
    try:
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise _DataFileError(f"Cannot read {path}: {exc}") from exc

    best: dict[str, tuple[int, _SchoolRecord]] = {}
    for row in rows:
        name = (row.get("School") or "").strip()
        lat_raw, lon_raw = row.get("Latitude"), row.get("Longitude")
        if not name or not lat_raw or not lon_raw:
            continue
        # "Virtual" is only present on the public-schools TSV (NCES's
        # private-school file has no such column); .get() returning
        # None for a private-school row never matches _VIRTUAL_REJECT.
        if (row.get("Virtual") or "").strip() in _VIRTUAL_REJECT:
            continue
        try:
            lat, lon = float(lat_raw), float(lon_raw)
        except ValueError as exc:
            raise _DataFileError(f"Non-numeric coordinate in {path} for {name!r}: {exc}") from exc

        norm = normalize_school_name(name)
        if not norm:
            continue

        record = _SchoolRecord(
            name=name,
            normalized_name=norm,
            tokens=frozenset(norm.split()),
            normalized_city=normalize_city_name(row.get("City") or ""),
            latitude=lat,
            longitude=lon,
            website=(row.get("WebSite") or "").strip(),
        )

        if not dedup_by_status:
            # Private schools: no status concept, keep every row as its
            # own candidate (a genuine name collision across two real
            # schools is handled by rung 2's city-filter, not by
            # dropping one here).
            best[f"{norm}\0{id(record)}"] = (0, record)
            continue

        status = (row.get("StatusType") or "").strip()
        rank = _STATUS_RANK.get(status, len(_STATUS_RANK))
        existing = best.get(norm)
        if existing is None or rank < existing[0]:
            best[norm] = (rank, record)

    return [record for _, record in best.values()]


def _load_overrides(path: Path) -> dict[str, _Override]:
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise _DataFileError(f"Cannot read {path}: {exc}") from exc

    overrides: dict[str, _Override] = {}
    for raw_key, entry in data.items():
        try:
            overrides[raw_key] = _Override(
                matched_name=str(entry["matched_name"]),
                latitude=float(entry["latitude"]),
                longitude=float(entry["longitude"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise _DataFileError(f"Malformed entry {raw_key!r} in {path}: {exc}") from exc
    return overrides


def _load_centroids(path: Path) -> dict[str, tuple[float, float]]:
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise _DataFileError(f"Cannot read {path}: {exc}") from exc

    centroids: dict[str, tuple[float, float]] = {}
    for raw_key, entry in data.items():
        try:
            centroids[raw_key] = (float(entry["latitude"]), float(entry["longitude"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise _DataFileError(f"Malformed entry {raw_key!r} in {path}: {exc}") from exc
    return centroids


class GeoLadder:
    """Loaded-once view of every offline geocoding data file under
    ``data_dir``, plus the rungs 1-4 school matcher (with its
    per-organization cache) and the rungs 5-6 centroid lookups --
    the complete seven-rung ladder, generic and caller-independent.

    Construct one per pipeline run (matching `teams.merge.
    merge_teams()`'s "operate on the combined list, once" shape) --
    never shared across runs.

    Raises:
        RuntimeError: any data file under `data_dir` is missing or
            malformed (`_DataFileError`, a `RuntimeError` subclass) --
            fails loudly at construction, before any caller record is
            touched.
    """

    def __init__(self, data_dir: Path) -> None:
        public = _load_school_tsv(_require_file(data_dir / "sd-schools-public.tsv"), dedup_by_status=True)
        private = _load_school_tsv(_require_file(data_dir / "sd-schools-private.tsv"), dedup_by_status=False)
        self._all_records: list[_SchoolRecord] = sorted(
            [*public, *private], key=lambda r: (r.normalized_name, r.name)
        )

        self._by_exact_name: dict[str, list[_SchoolRecord]] = {}
        for record in self._all_records:
            self._by_exact_name.setdefault(record.normalized_name, []).append(record)

        self._overrides = _load_overrides(_require_file(data_dir / "school-overrides.toml"))
        self._zip_centroids = _load_centroids(_require_file(data_dir / "zip-centroids.toml"))
        self._city_centroids = _load_centroids(_require_file(data_dir / "city-centroids.toml"))

        self._school_cache: dict[str, LocationMatch | None] = {}
        #: Number of times the rungs 1-4 matcher actually ran (cache
        #: misses only) -- tests assert this stays low for many
        #: callers sharing an organization, proving the cache is keyed
        #: per resolved school, not per call.
        self.match_calls = 0

    # -- rung 2 helper -----------------------------------------------

    @staticmethod
    def _disambiguate_by_city(
        candidates: list[_SchoolRecord], city_norm: str
    ) -> _SchoolRecord:
        if len(candidates) == 1:
            return candidates[0]
        same_city = [c for c in candidates if c.normalized_city == city_norm]
        pool = same_city if same_city else candidates
        return sorted(pool, key=lambda c: c.name)[0]

    # -- rungs 3/4 helper ----------------------------------------------

    def _best_token_match(
        self, org_tokens: frozenset[str], *, city_norm: str | None
    ) -> tuple[_SchoolRecord, float] | None:
        pool = self._all_records if city_norm is None else [
            r for r in self._all_records if r.normalized_city == city_norm
        ]
        best_record: _SchoolRecord | None = None
        best_score = 0.0
        for record in pool:
            score = _jaccard(org_tokens, record.tokens)
            if score > best_score:
                best_score = score
                best_record = record
        if best_record is None:
            return None
        return best_record, best_score

    # -- rungs 1-4, uncached -------------------------------------------

    def _run_ladder(self, organization: str, city: str) -> LocationMatch | None:
        org_norm = normalize_school_name(organization)
        if not org_norm:
            return None

        # Rung 1: hand overrides.
        override = self._overrides.get(org_norm)
        if override is not None:
            return LocationMatch(
                latitude=override.latitude,
                longitude=override.longitude,
                location_precision="school",
                matched_name=override.matched_name,
                website="",
                needs_review=False,
            )

        # Rung 2: exact normalized match (CDE + NCES), city-filtered
        # when ambiguous.
        exact_candidates = self._by_exact_name.get(org_norm)
        if exact_candidates:
            city_norm = normalize_city_name(city)
            chosen = self._disambiguate_by_city(exact_candidates, city_norm)
            return LocationMatch(
                latitude=chosen.latitude,
                longitude=chosen.longitude,
                location_precision="school",
                matched_name=chosen.name,
                website=chosen.website,
                needs_review=False,
            )

        org_tokens = frozenset(org_norm.split())
        city_norm = normalize_city_name(city)

        # Rung 3: token-set >= 0.60 within the same city.
        if city_norm:
            within_city = self._best_token_match(org_tokens, city_norm=city_norm)
            if within_city is not None and within_city[1] >= 0.60:
                record, score = within_city
                return LocationMatch(
                    latitude=record.latitude,
                    longitude=record.longitude,
                    location_precision="school",
                    matched_name=record.name,
                    website=record.website,
                    needs_review=score < 0.85,
                )

        # Rung 4: token-set >= 0.80 county-wide.
        county_wide = self._best_token_match(org_tokens, city_norm=None)
        if county_wide is not None and county_wide[1] >= 0.80:
            record, score = county_wide
            return LocationMatch(
                latitude=record.latitude,
                longitude=record.longitude,
                location_precision="school",
                matched_name=record.name,
                website=record.website,
                needs_review=score < 0.85,
            )

        return None

    # -- rungs 1-4, cached -----------------------------------------------

    def resolve_school(self, organization: str, city: str) -> LocationMatch | None:
        """Rungs 1-4, cached per :func:`normalize_school_name` of
        ``organization`` alone (see this module's docstring's Caching
        section). Returns ``None`` on a cached or fresh miss -- callers
        fall through to rungs 5-6."""
        key = normalize_school_name(organization)
        if not key:
            return None
        if key in self._school_cache:
            return self._school_cache[key]
        self.match_calls += 1
        result = self._run_ladder(organization, city)
        self._school_cache[key] = result
        return result

    # -- rungs 5/6 -------------------------------------------------------

    def resolve_zip(self, postal_code: str) -> tuple[float, float] | None:
        zip5 = (postal_code or "").strip()[:5]
        if not zip5:
            return None
        return self._zip_centroids.get(zip5)

    def resolve_city(self, city: str) -> tuple[float, float] | None:
        key = normalize_city_name(city)
        if not key:
            return None
        return self._city_centroids.get(key)

    # -- full ladder, generic and caller-independent ---------------------

    def locate(self, organization: str, city: str, postal_code: str = "") -> LocationMatch:
        """Run the full seven-rung ladder for one
        ``(organization, city, postal_code)`` and return the result --
        never mutates anything, never fabricates a coordinate.

        This is the one generic entry point both `teams/geo.py`'s
        `SchoolIndex.resolve(team)` and any future `directory/` caller
        (Places, Clubs) build on: school match (rungs 1-4) when
        ``organization`` is non-empty, else ZIP centroid (rung 5), else
        city centroid (rung 6), else the honest rung-7 ``"none"`` --
        never a guess.
        """
        school_match = self.resolve_school(organization, city) if organization else None
        if school_match is not None:
            return school_match

        zip_coords = self.resolve_zip(postal_code) if postal_code else None
        if zip_coords is not None:
            lat, lon = zip_coords
            return LocationMatch(
                latitude=lat,
                longitude=lon,
                location_precision="zip",
                matched_name=f"ZIP {postal_code.strip()[:5]} centroid",
                needs_review=False,
            )

        city_coords = self.resolve_city(city) if city else None
        if city_coords is not None:
            lat, lon = city_coords
            return LocationMatch(
                latitude=lat,
                longitude=lon,
                location_precision="city",
                matched_name=f"{city.strip()} (city centroid)",
                needs_review=False,
            )

        # Rung 7: deliberate non-match. Never guess.
        return LocationMatch(
            latitude=None,
            longitude=None,
            location_precision="none",
            matched_name="",
            needs_review=False,
        )
