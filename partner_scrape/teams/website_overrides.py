"""Website/social overlay ingestion and cleanup (``teams.website_overrides``).

Sprint 013 was originally planned assuming only the 53 team websites
FTC's/TBA's structured sources already carry. Two things came up after
planning:

1. A web-search discovery pass over the 225 teams whose upstream source
   carried no website found **31 new websites and 21 social-only
   teams** (every candidate required two independent on-page signals
   plus a successful fetch, then independent re-verification). That
   result is committed as this sprint's research artifact,
   `clasi/sprints/013-team-website-surfacing-and-sponsor-extraction/
   research/discovered-websites.json` -- transcribed **verbatim**, no
   re-derivation, into `teams/data/discovered-websites.toml`, the file
   this module actually reads at runtime.
2. Measuring the *existing* 53 TBA-sourced websites against the live
   export found two data-quality defects already shipping: 4 teams
   carry `http://www.firstinspires.org/` -- TBA's own program homepage,
   copied into the per-team field by mistake, never that team's real
   site -- and 7 carry a malformed triple-slash URL
   (`http:///host...` instead of `http://host...`).

This module owns exactly one responsibility, no "and": populate and
clean `Team.website`/`Team.social` from committed, curated data. It
is deliberately **not** folded into `teams.scrape.verify_team_websites()`
(ticket 001, already planned and approved before this ticket existed)
-- see `design/teams-DESIGN.md`'s Design Rationale for why conflating
curated-data ingestion with live-fetch verification in one function was
rejected. Most importantly: **this module never sets
`Team.website_status`**, for any team, regardless of an overlay entry's
original research `confidence` (`strong`/`weak` -- not even carried
into the runtime TOML, see below) or the research file's own same-day
`reverified_status: 200`. `teams.scrape.verify_team_websites()` remains
the sole, uniform authority for `confirmed`/`unverified`, run
immediately after this stage so it verifies the corrected, enlarged
`website` set -- this is the mechanism, not a special case, by which a
`weak`-confidence discovered entry lands as `unverified` rather than
being pre-confirmed by construction.

**First edge from `teams/` into `partner_scrape.model`.** This module
imports `partner_scrape.model.slugify` to build a (host, path) dedup
key -- reused, not reimplemented, matching `teams/merge.py`'s existing
precedent of reusing `normalize.partners.normalize_org_name` read-only.
`partner_scrape.model` is not one of the four boundaries this
subsystem's zero-edges invariant actually guards (`enrich/`,
`adapters/`, `normalize.run()`, `pipeline.run()`, see
`tests/teams/test_sources_base.py`); it is a leaf, dependency-free
string utility with no path back into any of those four, so this edge
does not weaken that invariant.

**The data-file loader mirrors, but never imports, `teams/geo.py`'s
`_load_overrides`/`_require_file` shape** (`tomllib`, raises loudly at
load time on a missing or malformed file -- a build-time defect to fix
before the next run, never a per-record failure to isolate, matching
`geo.py`'s `SchoolIndex` rationale). It additionally guards against a
data-authoring collision while loading: two different `team_id`s
claiming the identical `(host, path)` pair raise `RuntimeError` at load
time. This must compare host **and** path, never host alone -- the
research file's own caveats note `carlsbaded.org` and
`sites.google.com` each legitimately host more than one team, each at a
distinct path; a host-only check would wrongly flag those as
collisions.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from partner_scrape.model import slugify
from partner_scrape.teams.model import Team

#: This module's own data file location -- `teams/data/discovered-
#: websites.toml`, alongside `geo.py`'s data files. Never overridden in
#: production; tests always pass an explicit `data_dir` pointing at a
#: small fixture directory instead of the real, 52-entry file.
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"

#: Matches TBA's malformed `http:///host...`/`https:///host...` triple-
#: slash defect (an extra `/` before the host) -- repaired generically
#: to `http://host...`/`https://host...` for any host, not a per-team
#: hardcoded fix. TBA's own field is the source of this defect, so a
#: future TBA refresh may surface more of these; this repair applies to
#: every team's existing `website`, not just the 7 measured live at
#: ticket-write time.
_TRIPLE_SLASH_RE = re.compile(r"^(https?):///")

#: Hosts that are TBA's own program homepage, not a real team site --
#: measured live: `frc-3486`/`frc-4139`/`frc-4919`/`frc-5884` all carry
#: `http://www.firstinspires.org/` as `website`. Compared via
#: `urllib.parse.urlsplit`'s parsed `netloc`, never a substring match,
#: so a real team domain that merely contains "firstinspires" as a
#: substring is never misfired on.
_FIRSTINSPIRES_HOSTS = frozenset({"firstinspires.org", "www.firstinspires.org"})


class _DataFileError(RuntimeError):
    """`teams/data/discovered-websites.toml` is missing, malformed, or
    carries a data-authoring `(host, path)` collision between two
    different `team_id`s."""


@dataclass(frozen=True)
class _OverlayEntry:
    website: str  # "" for a social-only entry
    social: list[str] = field(default_factory=list)


def _require_file(path: Path) -> Path:
    if not path.is_file():
        raise _DataFileError(
            f"Missing offline website-overlay data file: {path}. See "
            "teams/data/discovered-websites.toml's own header comment "
            "for how it is derived."
        )
    return path


def _host_path_key(url: str) -> str:
    """`(host, path)` dedup key for `url`, via `slugify()` of the
    parsed netloc+path -- reused from `partner_scrape.model`, never a
    second slugifier. Deliberately host **and** path, never host alone
    (see this module's docstring)."""
    parsed = urlsplit(url)
    return slugify(f"{parsed.netloc}{parsed.path}")


def _load_overlay(path: Path) -> dict[str, _OverlayEntry]:
    """Load and validate `path` (`discovered-websites.toml`) into a
    `team_id -> _OverlayEntry` map.

    Raises:
        _DataFileError: the file is unreadable/malformed, an entry has
            a non-string `website`/`social` value, or two different
            `team_id`s claim the identical `(host, path)` pair.
    """
    try:
        with path.open("rb") as f:
            raw_data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise _DataFileError(f"Cannot read {path}: {exc}") from exc

    entries: dict[str, _OverlayEntry] = {}
    claimed_by: dict[str, str] = {}  # (host, path) key -> the team_id that claimed it

    for team_id, raw_entry in raw_data.items():
        try:
            website = str(raw_entry.get("website", ""))
            social = [str(item) for item in raw_entry.get("social", [])]
        except (AttributeError, TypeError) as exc:
            raise _DataFileError(f"Malformed entry {team_id!r} in {path}: {exc}") from exc

        if website:
            key = _host_path_key(website)
            existing_team_id = claimed_by.get(key)
            if existing_team_id is not None and existing_team_id != team_id:
                raise _DataFileError(
                    f"Duplicate (host, path) in {path}: {existing_team_id!r} "
                    f"and {team_id!r} both claim {key!r} (from {website!r})"
                )
            claimed_by[key] = team_id

        entries[team_id] = _OverlayEntry(website=website, social=social)

    return entries


def _clean_existing_website(website: str) -> str:
    """Generic cleanup applied to every team's *existing* `website`,
    regardless of source or whether it appears in the overlay: clear a
    `firstinspires.org` junk value, repair a triple-slash malformed URL.
    """
    if not website:
        return website
    if urlsplit(website).netloc in _FIRSTINSPIRES_HOSTS:
        return ""
    return _TRIPLE_SLASH_RE.sub(r"\1://", website)


def apply_website_overrides(teams: list[Team], data_dir: str | Path | None = None) -> list[Team]:
    """Clean and enrich `Team.website`/`Team.social` on `teams`, in
    place; return `teams` (matching `merge_teams()`/`geocode_teams()`'s
    "operate on the full list once" shape).

    In order, for every team:

    1. **Generic cleanup** of the *existing* `website`: cleared to
       `""` if its host is `firstinspires.org`/`www.firstinspires.org`;
       a malformed `http:///`/`https:///` URL is repaired to
       `http://`/`https://`, generically, for any host.
    2. **Overlay application**: if `website` is still empty after (1)
       and the overlay has a `website` for this `team_id`, set it. A
       team whose (post-cleanup) `website` is already non-empty is
       never overwritten, even if the overlay also has an entry for it.
    3. **Social ingestion**: for any `team_id` present in the overlay
       (website or social-only entry alike), set `Team.social` from its
       `social` list. A team absent from the overlay keeps the
       dataclass default (`[]`).
    4. **`Team.website_status` is never set or touched here** -- see
       this module's own docstring for why.

    Idempotent: calling this twice on the same `teams` list produces
    the same result the second time.

    Args:
        teams: already-geocoded `Team[]` (order irrelevant).
        data_dir: the directory containing `discovered-websites.toml`.
            Defaults to :data:`DEFAULT_DATA_DIR` (the real committed
            `teams/data/`) when omitted -- tests should always pass an
            explicit fixture directory instead.

    Raises:
        RuntimeError: `discovered-websites.toml` is missing, malformed,
            or carries a data-authoring `(host, path)` collision (see
            `_load_overlay`) -- a build-time defect to fix before the
            next run, matching `teams/geo.py`'s `SchoolIndex` loudly-
            fail-at-construction convention.
    """
    resolved_dir = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    overlay = _load_overlay(_require_file(resolved_dir / "discovered-websites.toml"))

    for team in teams:
        team.website = _clean_existing_website(team.website)

        entry = overlay.get(team.team_id)
        if entry is None:
            continue

        if not team.website and entry.website:
            team.website = entry.website

        team.social = list(entry.social)

    return teams
