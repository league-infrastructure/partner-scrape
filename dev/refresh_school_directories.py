#!/usr/bin/env python3
"""Yearly manual refresh of ``partner_scrape/teams/geo.py``'s offline
geocoding data files.

RUN THIS BY HAND, ROUGHLY ONCE A YEAR (school directories are annual
publications), or whenever a live ``teams`` run's exported
``meta.by_location_precision`` shows a sudden jump in ``"none"``
counts -- that is the signal a source has drifted and this script's
output is stale.

    uv run python dev/refresh_school_directories.py

This is a **standalone provisioning script**. It is never imported by
``partner_scrape.teams.pipeline`` or any other runtime code, and it is
the *only* thing in the ``teams/`` subsystem that touches the network
-- ``partner_scrape/teams/geo.py`` reads only the committed files this
script writes and makes zero network calls at runtime (see that
module's own docstring and ``tests/teams/test_geo.py``'s
``TestZeroNetworkCalls``). Re-run it, diff the four files it writes,
and review the diff like any other code change before committing.

Writes, under ``partner_scrape/teams/data/``:

``sd-schools-public.tsv``
    California Department of Education's public-school directory
    (``https://www.cde.ca.gov/schooldirectory/report?rid=dl1&tp=txt``,
    an 18k-row statewide TSV), filtered to:

    - ``County == "San Diego"``
    - ``StatusType == "Active"`` (a school that has closed is not
      somewhere a current team plays out of; ``geo.py``'s loader
      *also* independently prefers ``"Active"`` over ``"Closed"`` when
      deduplicating by normalized name, in case a future CDE refresh
      or a hand-edited fixture ever carries both for the same school --
      see its own docstring)
    - ``Virtual not in {"F", "V"}`` (schools CDE's own field dictionary
      documents as "Exclusively Virtual" or "Primarily Virtual" have no
      real campus a team could physically be at -- this is what makes
      an online school's team fuzzy-match its sponsoring district's
      administrative building and land a pin nobody actually attends;
      ``"C"``/"Primarily Classroom" and ``"N"``/"Not Virtual" schools
      are kept)
    - ``Latitude``/``Longitude`` both present

``sd-schools-private.tsv``
    NCES EDGE's geocoded private-school locations (ArcGIS REST,
    ``.../EDGE_GEOCODE_PRIVATESCH_2324`` and ``_2122``
    ``/MapServer/0/query``), filtered to ``STFIP='06' AND
    NMCNTY='San Diego County'`` and **unioned across the 2021-22 and
    2023-24 survey vintages** by NCES's stable school identifier
    (``PPIN``). The Private School Survey is voluntary, so a
    non-responding school drops out of one vintage but not the other
    -- confirmed live building this ticket: Pacific Ridge School is
    present in the 2021-22 vintage and absent from 2023-24. Where a
    ``PPIN`` appears in both vintages, the newer (2023-24) vintage's
    attributes win; the ``Vintages`` column on every row records which
    vintage(s) actually contributed it.

``zip-centroids.toml``
    ZIP Code Tabulation Area centroids for every distinct ZIP appearing
    in the freshly-filtered ``sd-schools-public.tsv`` above, from the
    Census Bureau's own Gazetteer file
    (``https://www2.census.gov/geo/docs/maps-data/data/gazetteer/``,
    the ``*_Gaz_zcta_national.zip`` national ZCTA file) -- authoritative
    geographic centroids, not derived from this project's own data.

``city-centroids.toml``
    One entry per distinct CDE ``City`` value seen in
    ``sd-schools-public.tsv``, computed as the mean coordinate of that
    file's own rows sharing the city -- self-consistent with the school
    data teams actually resolve against, and reproducible by re-running
    this script rather than hand-typed. A handful of San Diego
    neighborhoods (:data:`_NEIGHBORHOOD_ZIP_FALLBACK`) that
    ``sources.tba.SD_COUNTY_CITIES`` treats as distinct places but CDE's
    own ``City`` field folds into plain "San Diego" (Rancho Bernardo,
    Rancho Penasquitos, Carmel Valley, ...) are instead pointed at a
    specific, real ZIP's centroid from the table above -- each one
    cross-checked against an actual CDE school address at that name
    during this script's initial authoring (e.g. "Rancho Bernardo
    High" -> City=San Diego, Zip=92128; see that constant's own
    comments for the rest). Two real, unambiguous cities just outside
    San Diego County that FTCScout's region search has been observed to
    return (Agoura Hills, San Clemente -- see
    ``sources.ftcscout.OUT_OF_REGION_CITIES``) are added from the
    Census Gazetteer's California Places file so an out-of-region team
    at one of them still gets a real pin, not just the ``in_region =
    False`` flag. Deliberately **not** added: "Ensenada" (Mexico, no US
    Census coverage), "Louisville", "San Antonio" (ambiguous which
    real-world place FTCScout means -- guessing one would violate this
    whole subsystem's "never guess" rule; these fall through to
    ``location_precision: "none"`` at runtime instead, which is the
    honest outcome for a genuinely unidentifiable place name).

This script does not touch ``school-overrides.toml`` -- that file is
hand-maintained residue (the ~14 org-named teams and any hard fuzzy-
match misses a human has actually verified), not something to
regenerate from a live source.
"""

from __future__ import annotations

import csv
import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "partner_scrape" / "teams" / "data"

USER_AGENT = "STEM-Ecosystem-Robot-Teams-Bot/1.0 (educational research; offline geocoding data refresh)"

CDE_URL = "https://www.cde.ca.gov/schooldirectory/report?rid=dl1&tp=txt"

NCES_BASE = "https://nces.ed.gov/opengis/rest/services/K12_School_Locations"
NCES_VINTAGES = [
    ("2021-22", f"{NCES_BASE}/EDGE_GEOCODE_PRIVATESCH_2122/MapServer/0/query"),
    ("2023-24", f"{NCES_BASE}/EDGE_GEOCODE_PRIVATESCH_2324/MapServer/0/query"),
]
NCES_FIELDS = "PPIN,NAME,CITY,ZIP,LAT,LON,SCHOOLYEAR"
NCES_WHERE = "STFIP='06' AND NMCNTY='San Diego County'"

ZCTA_GAZETTEER_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2024_Gazetteer/2024_Gaz_zcta_national.zip"
)
PLACES_CA_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2024_Gazetteer/2024_gaz_place_06.txt"
)

#: Virtual-status codes (CDE's own field dictionary) meaning "no real
#: campus" -- see this module's docstring.
_VIRTUAL_REJECT = {"F", "V"}

#: San Diego neighborhoods `sources.tba.SD_COUNTY_CITIES` names as
#: distinct places that CDE's own `City` column does not distinguish
#: from plain "San Diego" -- each mapped to the ZIP of a real CDE school
#: address confirmed at that name (or, where noted, the immediately
#: adjacent well-evidenced ZIP) during this script's initial authoring
#: (2026-08-28). Not a guess: every ZIP below is grounded in an actual
#: CDE row, listed in the comment.
_NEIGHBORHOOD_ZIP_FALLBACK: dict[str, str] = {
    "rancho bernardo": "92128",  # "Rancho Bernardo High" -> San Diego 92128
    "rancho penasquitos": "92129",  # "Los Penasquitos Elementary" -> San Diego 92129
    "torrey hills": "92130",  # "Torrey Hills" (school) -> San Diego 92130
    "carmel valley": "92130",  # "Torrey Pines High"/"Solana Ranch Elementary" -> San Diego 92130
    "pacific highlands ranch": "92130",  # adjacent to/within the Carmel Valley 92130 area
    "santaluz": "92127",  # "Del Norte High"/"Poway to Palomar Middle College High" -> San Diego 92127
    "palomar mountain": "92060",  # "Palomar Mountain Elementary" -> Palomar Mountain 92060
    "jacumba": "91934",  # "Jacumba Elementary" -> Jacumba 91934
}

#: Real, unambiguous cities just outside San Diego County that
#: `sources.ftcscout.OUT_OF_REGION_CITIES` flags -- looked up in the
#: Census Places gazetteer by exact name below, not guessed.
_OUT_OF_REGION_PLACES = {"Agoura Hills", "San Clemente"}


def _fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _fetch_json(url: str) -> dict[str, Any]:
    body = _fetch_bytes(url)
    return json.loads(body.decode("utf-8"))


def refresh_public_schools() -> list[dict[str, str]]:
    """Download, filter, and write ``sd-schools-public.tsv``.

    Returns the written rows (each a plain dict) so :func:`refresh_centroids`
    can derive ZIP/city centroids from exactly what was just shipped.
    """
    print(f"Fetching CDE public-school directory from {CDE_URL} ...")
    raw = _fetch_bytes(CDE_URL).decode("utf-8")
    lines = raw.splitlines()
    header = lines[0].split("\t")
    idx = {name: i for i, name in enumerate(header)}

    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        cols = line.split("\t")
        if len(cols) <= max(idx.values()):
            continue
        if cols[idx["County"]] != "San Diego":
            continue
        if cols[idx["StatusType"]] != "Active":
            continue
        if cols[idx["Virtual"]] in _VIRTUAL_REJECT:
            continue
        lat_raw, lon_raw = cols[idx["Latitude"]].strip(), cols[idx["Longitude"]].strip()
        if not lat_raw or not lon_raw:
            continue
        try:
            lat, lon = float(lat_raw), float(lon_raw)
        except ValueError:
            continue

        zip5 = cols[idx["Zip"]].strip().split("-")[0]
        rows.append(
            {
                "School": cols[idx["School"]].strip(),
                "District": cols[idx["District"]].strip(),
                "City": cols[idx["City"]].strip(),
                "Zip": zip5,
                "WebSite": cols[idx["WebSite"]].strip(),
                "Latitude": f"{lat:.6f}",
                "Longitude": f"{lon:.6f}",
                "StatusType": cols[idx["StatusType"]].strip(),
                "Virtual": cols[idx["Virtual"]].strip(),
            }
        )

    rows.sort(key=lambda r: r["School"])
    out_path = DATA_DIR / "sd-schools-public.tsv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out_path}")
    return rows


def refresh_private_schools() -> None:
    """Download, union, and write ``sd-schools-private.tsv``."""
    by_ppin: dict[str, dict[str, Any]] = {}
    vintages_by_ppin: dict[str, list[str]] = {}

    for vintage, base_url in NCES_VINTAGES:
        params = {"where": NCES_WHERE, "outFields": NCES_FIELDS, "f": "json"}
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        print(f"Fetching NCES EDGE private-school vintage {vintage} ...")
        data = _fetch_json(url)
        features = data.get("features", [])
        for feature in features:
            attrs = feature["attributes"]
            ppin = attrs["PPIN"]
            by_ppin[ppin] = attrs  # later vintage in NCES_VINTAGES wins on conflict
            vintages_by_ppin.setdefault(ppin, []).append(vintage)

    rows: list[dict[str, str]] = []
    for ppin, attrs in by_ppin.items():
        lat, lon = attrs.get("LAT"), attrs.get("LON")
        if lat is None or lon is None:
            continue
        rows.append(
            {
                "School": str(attrs.get("NAME") or "").strip().title(),
                "City": str(attrs.get("CITY") or "").strip().title(),
                "Zip": str(attrs.get("ZIP") or "").strip().split("-")[0],
                "Latitude": f"{float(lat):.6f}",
                "Longitude": f"{float(lon):.6f}",
                "Vintages": ",".join(sorted(vintages_by_ppin[ppin])),
            }
        )

    rows.sort(key=lambda r: r["School"])
    out_path = DATA_DIR / "sd-schools-private.tsv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows (union of {len(NCES_VINTAGES)} vintages) to {out_path}")


def _load_zcta_centroids(needed_zips: set[str]) -> dict[str, tuple[float, float]]:
    print(f"Fetching Census Gazetteer ZCTA centroids from {ZCTA_GAZETTEER_URL} ...")
    archive_bytes = _fetch_bytes(ZCTA_GAZETTEER_URL)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        (member_name,) = [n for n in archive.namelist() if n.lower().endswith(".txt")]
        text = archive.read(member_name).decode("latin-1")

    lines = text.splitlines()
    header = [h.strip() for h in lines[0].split("\t")]
    idx = {name: i for i, name in enumerate(header)}

    found: dict[str, tuple[float, float]] = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        cols = line.split("\t")
        zcta = cols[idx["GEOID"]].strip()
        if zcta not in needed_zips:
            continue
        lat = float(cols[idx["INTPTLAT"]].strip())
        lon = float(cols[idx["INTPTLONG"]].strip())
        found[zcta] = (lat, lon)

    missing = needed_zips - found.keys()
    if missing:
        print(f"  WARNING: {len(missing)} ZIP(s) not found in the ZCTA gazetteer: {sorted(missing)}")
    return found


def _load_out_of_region_place_centroids() -> dict[str, tuple[float, float]]:
    print(f"Fetching Census Gazetteer CA Places from {PLACES_CA_URL} ...")
    text = _fetch_bytes(PLACES_CA_URL).decode("latin-1")
    lines = text.splitlines()
    header = [h.strip() for h in lines[0].split("\t")]
    idx = {name: i for i, name in enumerate(header)}

    found: dict[str, tuple[float, float]] = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        cols = line.split("\t")
        name = cols[idx["NAME"]].strip()
        for wanted in _OUT_OF_REGION_PLACES:
            if name == f"{wanted} city":
                found[wanted] = (float(cols[idx["INTPTLAT"]]), float(cols[idx["INTPTLONG"]]))
    return found


def refresh_centroids(public_school_rows: list[dict[str, str]]) -> None:
    """Write ``zip-centroids.toml`` and ``city-centroids.toml`` from
    this run's own ``sd-schools-public.tsv`` rows plus the Census
    Gazetteer -- see this module's docstring for the exact derivation.
    """
    needed_zips = {row["Zip"] for row in public_school_rows if row["Zip"]}
    needed_zips |= set(_NEIGHBORHOOD_ZIP_FALLBACK.values())
    zip_centroids = _load_zcta_centroids(needed_zips)

    zip_path = DATA_DIR / "zip-centroids.toml"
    with zip_path.open("w", encoding="utf-8") as f:
        f.write(
            "# ZIP Code Tabulation Area centroids, Census Bureau 2024 Gazetteer\n"
            "# (https://www2.census.gov/geo/docs/maps-data/data/gazetteer/).\n"
            "# Regenerated by dev/refresh_school_directories.py -- do not hand-edit.\n\n"
        )
        for zip5 in sorted(zip_centroids):
            lat, lon = zip_centroids[zip5]
            f.write(f'["{zip5}"]\n')
            f.write(f"latitude = {lat:.6f}\n")
            f.write(f"longitude = {lon:.6f}\n\n")
    print(f"Wrote {len(zip_centroids)} ZIP centroids to {zip_path}")

    # City centroid = mean of this run's own public-school coordinates
    # sharing a City value -- self-consistent with the data teams
    # actually resolve against.
    sums: dict[str, list[float]] = {}
    counts: dict[str, int] = {}
    for row in public_school_rows:
        city = row["City"].strip()
        if not city:
            continue
        key = city.lower()
        lat, lon = float(row["Latitude"]), float(row["Longitude"])
        if key not in sums:
            sums[key] = [0.0, 0.0]
            counts[key] = 0
        sums[key][0] += lat
        sums[key][1] += lon
        counts[key] += 1

    city_centroids: dict[str, tuple[float, float, str]] = {
        key: (sums[key][0] / counts[key], sums[key][1] / counts[key], counts[key])
        for key in sums
    }

    for neighborhood, zip5 in _NEIGHBORHOOD_ZIP_FALLBACK.items():
        if zip5 in zip_centroids:
            lat, lon = zip_centroids[zip5]
            city_centroids[neighborhood] = (lat, lon, 0)  # count=0 marks "via ZIP fallback"

    out_of_region = _load_out_of_region_place_centroids()
    for place, (lat, lon) in out_of_region.items():
        city_centroids[place.lower()] = (lat, lon, 0)

    city_path = DATA_DIR / "city-centroids.toml"
    with city_path.open("w", encoding="utf-8") as f:
        f.write(
            "# City centroids for teams/geo.py's rung 6 (city precision).\n"
            "# Mean of sd-schools-public.tsv's own coordinates per CDE `City`\n"
            "# value, except entries with a comment below -- those are a\n"
            "# specific ZIP centroid or an out-of-region place, not a school\n"
            "# mean (see dev/refresh_school_directories.py's docstring).\n"
            "# Regenerated by dev/refresh_school_directories.py -- do not hand-edit.\n\n"
        )
        for key in sorted(city_centroids):
            lat, lon, count = city_centroids[key]
            f.write(f'["{key}"]\n')
            f.write(f"latitude = {lat:.6f}\n")
            f.write(f"longitude = {lon:.6f}\n")
            if count:
                f.write(f"# mean of {count} CDE public school(s)\n")
            elif key in _NEIGHBORHOOD_ZIP_FALLBACK:
                f.write(f"# via ZIP {_NEIGHBORHOOD_ZIP_FALLBACK[key]} centroid, not a school mean\n")
            else:
                f.write("# out-of-region place, Census Gazetteer CA Places centroid\n")
            f.write("\n")
    print(f"Wrote {len(city_centroids)} city centroids to {city_path}")


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        public_rows = refresh_public_schools()
        refresh_private_schools()
        refresh_centroids(public_rows)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError) as exc:
        print(f"ERROR: refresh failed: {exc}", file=sys.stderr)
        return 1
    print("\nDone. Review the diff (git diff partner_scrape/teams/data/) before committing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
