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

A missing local data directory is created automatically; an unwritable
one fails loudly -- mirrors `export_opportunities`'s existing contract: "fail
loudly, do not silently skip the export."

Sprint 020 ticket 004 (issue 60) added this write, into
partner-scrape's own data location (since sprint 038 the data Store,
`config.get_data_store()`), alongside an original write into a sibling `stem-ecosystem` checkout's
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

from partner_scrape.config import BUNDLED_REGISTRY_DIR, get_ads_dir, resolve_data_store
from partner_scrape.storage import Store

logger = logging.getLogger(__name__)

#: Top-level TOML keys every ad file must define. A file missing any of
#: these raises InvalidAdConfig, which :func:`load_ad_configs` catches,
#: logs, and skips -- never fatal to the rest of the directory, mirroring
#: `registry/hub_schema.py`'s `_REQUIRED_FIELDS` contract.
_REQUIRED_FIELDS = ("headline", "body", "link", "logo_src")

#: The *bundled* Ad Registry directory
#: (`partner_scrape/registry_data/ads`). Callers omitting `directory`
#: get `config.get_ads_dir()`, which honours `PARTNER_SCRAPE_REGISTRY_DIR`.
DEFAULT_ADS_DIR = BUNDLED_REGISTRY_DIR / "ads"


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
        directory: defaults to `config.get_ads_dir()` (the bundled seed ad
            registry) when omitted.
    """
    directory = directory or get_ads_dir()
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
    own_data_dir: str | Path | Store | None = None,
) -> list[dict[str, Any]]:
    """Write `ad_configs` into `own_data_dir`'s `ads.json` data contract.

    Args:
        ad_configs: already-loaded `AdConfig` records (typically
            `load_ad_configs()`'s output).
        dry_run: when `True`, compute and return the would-be-written
            payload without touching disk -- `own_data_dir` is not
            written.
        own_data_dir: where to write -- a local path, an `s3://` location,
            or a `Store`. Defaults to `config.get_data_store()` when
            `None`. A local directory is created automatically if
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
    payload = [_to_json_dict(ad) for ad in ad_configs]

    if dry_run:
        return payload

    serialized_ads = json.dumps(payload, indent=1, ensure_ascii=False)

    # Sprint 020 ticket 004 (issue 60) added this write; since sprint
    # 038 it goes through the data Store (key unchanged).
    store = resolve_data_store(own_data_dir)
    try:
        store.write_text("ads.json", serialized_ads, "application/json")
    except RuntimeError as exc:
        raise RuntimeError(
            f"Cannot write own-data ads export: {exc}. "
            "Check that the data location is writable."
        ) from exc

    return payload
