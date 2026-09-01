"""`export_ads()`: the Ad Content Export module's single entry point.

Publishes hand-authored League ad-slot content (sprint 005 ticket 005,
issue 12: "give the League the ad placement it's owed in exchange" for
funding this project) into partner-scrape's own `own_data_dir` -- the
same write target `export/writer.py` already uses for
`opportunities.json` (sprint.md Architecture > Ad Content Export). This
module does not implement any UI/placement/rotation decision -- that is
the downstream consuming site's own, separately-scheduled work (see
sprint.md's Design Rationale, "League's ad slot is delivered as a data
contract...").

## The `ads.json` data contract

`export_ads()` writes `{own_data_dir}/ads.json` as a JSON array of
objects, one per configured ad, each shaped:

```json
{
  "headline": "string -- short, punchy ad title",
  "body": "string -- 1-2 sentence pitch/description",
  "link": "string -- absolute URL the ad should link to",
  "logo_src": "string -- logo image filename, matching the same
      logo_src convention stem-ecosystem's partners.json already uses"
}
```

The array is intentionally flat and advertiser-agnostic: today it holds
exactly one entry (the League's), but a second advertiser is just a
second array element, with no schema change (sprint.md's Open Question
2: exact placement/rotation/format is deliberately left to the
`stem-ecosystem` site's own follow-up design work). A recommended
integration for that follow-up: render each entry as a card in the
site's sidebar (the opportunities/partners listing pages' existing
filter sidebar is filter-only today; a dedicated ad slot is new
site-side UI work) -- `headline` as the card title, `body` as its
copy, `logo_src` resolved the same way `Opportunity.logo_src` already
resolves an image, and the whole card wrapped in an anchor to `link`.

A missing `own_data_dir` is created automatically
(`Path.mkdir(parents=True, exist_ok=True)`); an unwritable one fails
loudly -- mirrors `export_opportunities`'s existing contract: "fail
loudly, do not silently skip the export."

Sprint 020 ticket 004 (issue 60) added this write, into
partner-scrape's own `data/` directory (`config.get_own_data_dir()`),
alongside an original write into a sibling `stem-ecosystem` checkout's
`src/data/ads.json` -- the same "one export, three files, two
directories" contract `export/writer.py`'s `export_opportunities()`
already gave `opportunities.json`/`scrape-meta.json` (sprint 020 ticket
003). Sprint 025 ticket 003 (issue 21, "stop writing to the
stem-ecosystem checkout") removed the `stem-ecosystem` write entirely:
this function no longer accepts a `site_dir` parameter, and
`own_data_dir` is now the sole write target.
"""

from __future__ import annotations

import json
import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from partner_scrape.config import REPO_ROOT, get_own_data_dir

logger = logging.getLogger(__name__)

#: Top-level TOML keys every ad file must define. A file missing any of
#: these raises InvalidAdConfig, which :func:`load_ad_configs` catches,
#: logs, and skips -- never fatal to the rest of the directory, mirroring
#: `registry/hub_schema.py`'s `_REQUIRED_FIELDS` contract.
_REQUIRED_FIELDS = ("headline", "body", "link", "logo_src")

#: Default location of the hand-authored Ad Registry's per-advertiser
#: TOML files: `registry/ads/` at the repo root (see sprint 025 ticket
#: 001 for the move out of `partner_scrape/registry/`).
DEFAULT_ADS_DIR = REPO_ROOT / "registry" / "ads"


class InvalidAdConfig(Exception):
    """Raised when an ad TOML file is missing a required field.

    Caught at the directory-loader level (:func:`load_ad_configs`): a
    single bad file is logged and skipped, never fatal to the whole
    load.
    """


@dataclass
class AdConfig:
    """One hand-authored advertiser's ad-slot content.

    Standalone, hand-authored marketing copy -- not scraped from the
    advertiser's own site -- since ad copy an advertiser wants to run
    (e.g. a seasonal enrollment pitch) is a different concern from
    what's literally published on their site (sprint.md ticket 005's
    Description).
    """

    headline: str
    body: str
    link: str
    logo_src: str

    @classmethod
    def from_toml(cls, path: Path) -> AdConfig:
        """Parse and validate one ad TOML file.

        Raises:
            InvalidAdConfig: a required field (`headline`, `body`,
                `link`, or `logo_src`) is missing.
            tomllib.TOMLDecodeError: the file is not valid TOML. Left
                unwrapped -- :func:`load_ad_configs` treats it the same
                as InvalidAdConfig (log and skip) but callers reading a
                single file directly may want to tell the two apart.
        """
        with open(path, "rb") as f:
            data = tomllib.load(f)

        missing = [name for name in _REQUIRED_FIELDS if name not in data]
        if missing:
            raise InvalidAdConfig(f"{path}: missing required field(s): {', '.join(missing)}")

        return cls(
            headline=data["headline"],
            body=data["body"],
            link=data["link"],
            logo_src=data["logo_src"],
        )


def load_ad_configs(directory: Path | None = None) -> list[AdConfig]:
    """Load and validate every `*.toml` file in `directory`.

    A file that fails to parse as TOML, or is missing a required field,
    is logged as a warning and skipped; it never aborts the rest of the
    directory's load -- the same contract `registry.hub_schema.load_hubs`
    and `registry.loader.load_sources` give their own registries.

    Args:
        directory: defaults to :data:`DEFAULT_ADS_DIR` (the real seed ad
            registry) when omitted.
    """
    directory = directory or DEFAULT_ADS_DIR
    ad_configs: list[AdConfig] = []
    for path in sorted(directory.glob("*.toml")):
        try:
            ad_configs.append(AdConfig.from_toml(path))
        except InvalidAdConfig as exc:
            logger.warning("Skipping invalid ad file: %s", exc)
        except tomllib.TOMLDecodeError as exc:
            logger.warning("Skipping malformed TOML file %s: %s", path, exc)
    return ad_configs


def _to_json_dict(ad: AdConfig) -> dict[str, Any]:
    return {
        "headline": ad.headline,
        "body": ad.body,
        "link": ad.link,
        "logo_src": ad.logo_src,
    }


def export_ads(
    ad_configs: Iterable[AdConfig],
    *,
    dry_run: bool = False,
    own_data_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Write `ad_configs` into `own_data_dir`'s `ads.json` data contract.

    Args:
        ad_configs: already-loaded `AdConfig` records (typically
            `load_ad_configs()`'s output).
        dry_run: when `True`, compute and return the would-be-written
            payload without touching disk -- `own_data_dir` is not
            written.
        own_data_dir: path to partner-scrape's own pipeline-output
            directory. Defaults to `Config.get_own_data_dir()`
            (`<repo_root>/data`) when `None`. Created automatically if
            missing. Tests should always pass an explicit `tmp_path`
            here, never rely on the default.

    Returns:
        The list of ad dicts that were (or, for `dry_run`, would have
        been) written, in this module's documented `ads.json` schema.

    Raises:
        RuntimeError: `own_data_dir` is occupied by something
            unwritable (e.g. a non-directory file). Never silently
            skips the write.
    """
    resolved_own_data_dir = Path(own_data_dir) if own_data_dir is not None else get_own_data_dir()

    payload = [_to_json_dict(ad) for ad in ad_configs]

    if dry_run:
        return payload

    serialized_ads = json.dumps(payload, indent=1, ensure_ascii=False)

    # Sprint 020 ticket 004 (issue 60) added this write, into
    # partner-scrape's own data/ directory, alongside a since-removed
    # write into a sibling stem-ecosystem checkout (sprint 025 ticket
    # 003 removed that second target -- see module docstring).
    # own_data_dir is created if missing (see module docstring).
    own_ads_path = resolved_own_data_dir / "ads.json"

    try:
        resolved_own_data_dir.mkdir(parents=True, exist_ok=True)
        own_ads_path.write_text(serialized_ads, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"Cannot write own-data ads export to {resolved_own_data_dir}: {exc}. "
            "Check that own_data_dir is writable."
        ) from exc

    return payload
