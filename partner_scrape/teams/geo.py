"""The seven-rung, fully offline location resolver (``teams.geo``).

This is the module that actually delivers the sprint's stated goal --
*knowing where the teams are* -- and it is deliberately, structurally
offline: **zero network calls, ever.** ``clasi/sprints/011-robot-teams/
issues/robot-teams-scrape-locate-and-publish-san-diego-first-teams.md``
measured live geocoding unreliable before this module was written
(Nominatim/OSM: 62 distinct FTC school names, 25 resolved / 36 did not
-- 41% failure -- plus an HTTP 429 on a second machine's very first
request; the US Census geocoder: 0 matches for a bare school name, it
parses street addresses this project does not have). ``geo.py`` reads
only the committed data files under ``teams/data/`` -- refreshed
yearly, offline-safe, by the standalone ``dev/
refresh_school_directories.py`` (never imported here) -- and never asks
an LLM for a coordinate either: an LLM would emit a *plausible* wrong
value nothing downstream can catch, and a wrong pin is worse than no
pin.

## The ladder

Highest precision first. Every rung stamps ``Team.location_precision``,
``Team.matched_name`` (so "why is this team here?" always has a string
answer), and, for the two fuzzy rungs, ``Team.needs_review``:

1. ``school-overrides.toml`` -- hand corrections for the residue a
   human has actually verified. -> ``"school"``
2. CDE **and** NCES exact normalized-name match, city-filtered when the
   normalized name is ambiguous across sources/cities. -> ``"school"``
3. Token-set match, Jaccard >= 0.60, restricted to schools in the same
   (normalized) city as the team. -> ``"school"``
4. Token-set match, Jaccard >= 0.80, county-wide (no city restriction).
   -> ``"school"``
5. ZIP centroid, from ``Team.postal_code``. -> ``"zip"``
6. City centroid, from ``Team.city``. -> ``"city"``
7. No match anywhere above -> ``"none"``, coordinates left ``None``.
   **Deliberate, not a bug**: a team that exhausts every rung gets no
   pin at all rather than a fabricated one.

Rungs 3 and 4 are two different *candidate pools* (same-city vs.
county-wide) at two different acceptance thresholds, but
``Team.needs_review`` is set from the actual computed Jaccard score,
not from which rung accepted the match -- a rung-3 match that happens
to score 0.90 is not flagged, and a rung-4 match at exactly 0.80 is.
Below 0.85, ``needs_review = True`` and the match still publishes (per
the issue: a silent guess is worse than a flagged one) -- this is
exactly what would catch a case like "Classical Academy Online"
fuzzy-matching its sponsoring district's building at a 0.70 score
without a human ever ratifying it.

## Caching

A ``SchoolIndex`` is constructed once per ``geocode_teams()``/
``run_teams()`` call and caches rungs 1-4's outcome (a hit *or* a
confirmed miss) keyed by :func:`normalize_school_name` of
``Team.organization`` alone -- not by (organization, city) and not
per-``Team``. This is deliberate: per the issue's own measurement, 94
school-named FTC/FRC teams collapse onto ~58 distinct campuses, so a
per-team cache would repeat ~40% of the matching work for no benefit --
two ``Team`` records with the *same* normalized organization name are,
by construction, teams at the *same* real-world school, so city is only
ever needed to disambiguate the *first* lookup for that name. Negative
outcomes (rungs 1-4 all miss) are cached too, so the ~14 unresolvable
org-named teams (``"D Robotics Education"``, ...) never rescan the full
candidate pool more than once per run. This cache is in-memory and
scoped to one ``SchoolIndex`` instance -- there is no cross-run/disk
persistence (unlike ``enrich/cache.py``'s ``EnrichmentCache``, which
exists to avoid *paying for* a repeated LLM call; nothing here costs
money or meaningfully more wall-clock time on a second run, so a disk
cache would add real complexity -- schema versioning, invalidation --
for no measurable benefit. See ``teams/DESIGN.md``'s Design section for
the fuller comparison).

## Malformed data fails loudly

A missing or unparseable data file raises ``RuntimeError`` out of
``SchoolIndex.__init__``/``geocode_teams()`` -- per SUC-003's Error
Flows, a bad geocoding table is a build-time defect to fix before the
next run, not a per-record failure to log and skip.
"""

from __future__ import annotations

import csv
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from partner_scrape.teams.model import Team

#: This module's own data directory -- `teams/data/`, populated by
#: `dev/refresh_school_directories.py` (CDE/NCES/centroids) and by hand
#: (`school-overrides.toml`). Never overridden in production; tests
#: always pass an explicit `data_dir` pointing at a small fixture
#: directory instead of touching these real, ~800+213-row files.
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"

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
#: `StatusType == "Active"` rows only (see
#: `dev/refresh_school_directories.py`), so this is defense in depth,
#: directly exercised by `tests/teams/test_geo.py`'s own fixture.
_STATUS_RANK = {"Active": 0, "Closed": 1, "Merged": 2}

#: CDE `Virtual` codes meaning "no real campus" -- rejected on load, the
#: same criterion `dev/refresh_school_directories.py` already applies
#: when writing `sd-schools-public.tsv`. Duplicated here, not just
#: there, for the same defense-in-depth reason as `_STATUS_RANK`: an
#: online school fuzzy-matching its sponsoring district's building (the
#: "Classical Academy Online" case) is exactly the failure this guards
#: against, and this module's own tests exercise it directly rather
#: than trusting the refresh script was run correctly.
_VIRTUAL_REJECT = {"F", "V"}


def normalize_school_name(name: str) -> str:
    """Normalize a school/organization name for exact and token-set
    matching.

    Strips parenthetical asides (CDE writes some names as ``"Surname
    (Given Name)"``, e.g. ``"Feaster (Mae L.) Charter"`` -- dropping the
    parenthetical recovers the class of matches that pattern otherwise
    breaks), lowercases, strips punctuation, and collapses whitespace.
    A small, separately-named normalizer local to this module --
    deliberately *not* `normalize.partners.normalize_org_name`, which
    is scoped to partner-directory organization names, not place names
    (see `teams/DESIGN.md`'s Design section).
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
    ``"San Diego"`` all normalize to a single canonical form, per this
    ticket's explicit acceptance criterion. Deliberately independent of
    (not a caller of) `sources.ftcscout._clean_city`/`sources.tba.
    _clean_city` -- those strip+title-case at *extraction* time for
    display; this is this module's own defensive normalization at
    *match* time, so `geo.py`'s ladder is correct even if a future
    source ever sends a dirtier `Team.city` than today's two sources do.
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
class _SchoolMatch:
    latitude: float
    longitude: float
    matched_name: str
    website: str
    needs_review: bool


class _DataFileError(RuntimeError):
    """A geocoding data file under `data_dir` is missing or malformed."""


def _require_file(path: Path) -> Path:
    if not path.is_file():
        raise _DataFileError(
            f"Missing offline geocoding data file: {path}. Run "
            "dev/refresh_school_directories.py (CDE/NCES/centroid files) "
            "or check teams/data/school-overrides.toml (hand-maintained)."
        )
    return path


def _load_school_tsv(path: Path, *, dedup_by_status: bool) -> list[_SchoolRecord]:
    """Load one school-directory TSV (`sd-schools-public.tsv` or
    `sd-schools-private.tsv`) into `_SchoolRecord`s.

    ``dedup_by_status=True`` (public schools only) keeps, per
    normalized name, only the row with the best `_STATUS_RANK` --
    "prefer StatusType == Active over Closed" -- see this module's own
    docstring and `_STATUS_RANK`.
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


class SchoolIndex:
    """Loaded-once view of every offline geocoding data file, plus the
    rungs 1-4 school matcher and its per-organization cache.

    Construct one per `geocode_teams()` call (matching
    `teams.merge.merge_teams()`'s "operate on the combined list, once"
    shape) -- never shared across runs.

    Raises:
        RuntimeError: any data file under `data_dir` is missing or
            malformed (`_DataFileError`, a `RuntimeError` subclass) --
            fails loudly at construction, before any `Team` is touched.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        resolved = data_dir if data_dir is not None else DEFAULT_DATA_DIR

        public = _load_school_tsv(_require_file(resolved / "sd-schools-public.tsv"), dedup_by_status=True)
        private = _load_school_tsv(_require_file(resolved / "sd-schools-private.tsv"), dedup_by_status=False)
        self._all_records: list[_SchoolRecord] = sorted(
            [*public, *private], key=lambda r: (r.normalized_name, r.name)
        )

        self._by_exact_name: dict[str, list[_SchoolRecord]] = {}
        for record in self._all_records:
            self._by_exact_name.setdefault(record.normalized_name, []).append(record)

        self._overrides = _load_overrides(_require_file(resolved / "school-overrides.toml"))
        self._zip_centroids = _load_centroids(_require_file(resolved / "zip-centroids.toml"))
        self._city_centroids = _load_centroids(_require_file(resolved / "city-centroids.toml"))

        self._school_cache: dict[str, _SchoolMatch | None] = {}
        #: Number of times the rungs 1-4 matcher actually ran (cache
        #: misses only) -- tests assert this stays at 1 for N teams
        #: sharing an organization, proving the cache is keyed per
        #: resolved school, not per team.
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

    def _run_ladder(self, organization: str, city: str) -> _SchoolMatch | None:
        org_norm = normalize_school_name(organization)
        if not org_norm:
            return None

        # Rung 1: hand overrides.
        override = self._overrides.get(org_norm)
        if override is not None:
            return _SchoolMatch(
                latitude=override.latitude,
                longitude=override.longitude,
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
            return _SchoolMatch(
                latitude=chosen.latitude,
                longitude=chosen.longitude,
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
                return _SchoolMatch(
                    latitude=record.latitude,
                    longitude=record.longitude,
                    matched_name=record.name,
                    website=record.website,
                    needs_review=score < 0.85,
                )

        # Rung 4: token-set >= 0.80 county-wide.
        county_wide = self._best_token_match(org_tokens, city_norm=None)
        if county_wide is not None and county_wide[1] >= 0.80:
            record, score = county_wide
            return _SchoolMatch(
                latitude=record.latitude,
                longitude=record.longitude,
                matched_name=record.name,
                website=record.website,
                needs_review=score < 0.85,
            )

        return None

    # -- rungs 1-4, cached -----------------------------------------------

    def resolve_school(self, organization: str, city: str) -> _SchoolMatch | None:
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

    # -- full ladder, one Team --------------------------------------------

    def resolve(self, team: Team) -> None:
        """Run the full seven-rung ladder for ``team``, stamping
        ``latitude``/``longitude``/``location_precision``/
        ``matched_name``/``needs_review``/(on a school match)
        ``organization_website`` in place. Runs uniformly regardless of
        ``team.in_region`` -- an out-of-county team gets the same
        ladder, flagged separately by `sources/*`'s own `in_region`
        field, never special-cased here (see `teams/DESIGN.md`).
        """
        school_match = self.resolve_school(team.organization, team.city) if team.organization else None
        if school_match is not None:
            team.latitude = school_match.latitude
            team.longitude = school_match.longitude
            team.location_precision = "school"
            team.matched_name = school_match.matched_name
            team.needs_review = school_match.needs_review
            if school_match.website:
                team.organization_website = school_match.website
            return

        zip_coords = self.resolve_zip(team.postal_code) if team.postal_code else None
        if zip_coords is not None:
            team.latitude, team.longitude = zip_coords
            team.location_precision = "zip"
            team.matched_name = f"ZIP {team.postal_code.strip()[:5]} centroid"
            team.needs_review = False
            return

        city_coords = self.resolve_city(team.city) if team.city else None
        if city_coords is not None:
            team.latitude, team.longitude = city_coords
            team.location_precision = "city"
            team.matched_name = f"{team.city.strip()} (city centroid)"
            team.needs_review = False
            return

        # Rung 7: deliberate non-match. Never guess.
        team.latitude = None
        team.longitude = None
        team.location_precision = "none"
        team.matched_name = ""
        team.needs_review = False


def geocode_teams(teams: list[Team], *, data_dir: Path | str | None = None) -> list[Team]:
    """Resolve every `Team` in `teams` through the offline ladder, in
    place; return the same list.

    Structurally parallel to `teams.merge.merge_teams()`: mutates and
    returns its input, called once by `teams.pipeline.run_teams()`
    after `merge_teams()` and before `export_teams()`.

    Args:
        teams: already-merged `Team[]` (order irrelevant to this
            function).
        data_dir: the geocoding data directory. Defaults to
            :data:`DEFAULT_DATA_DIR` (the real committed `teams/data/`)
            when omitted -- tests should always pass an explicit
            fixture directory.

    Raises:
        RuntimeError: a data file under `data_dir` is missing or
            malformed (see `SchoolIndex`).
    """
    index = SchoolIndex(Path(data_dir) if data_dir is not None else None)
    for team in teams:
        index.resolve(team)
    return teams
