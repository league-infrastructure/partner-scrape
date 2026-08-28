"""Copy a finished site export into additional site checkouts.

`export_opportunities()` and `export_ads()` each write into exactly one
`site_dir`, and the pipeline resolves exactly one -- the sibling
`stem-ecosystem` checkout that the scheduled workflow publishes from
(`docs/deploy/scheduled-run.md`). This repo's own `site/` is a second,
independent checkout of the same site, and nothing kept it in step: a
scrape refreshed production while the beta site the team develops
against kept serving whatever snapshot it was last handed. That is how
`site/src/data/opportunities.json` came to sit at a 2026-07-21 export
for five weeks.

This module closes that gap by copying the export's *output* files into
each extra checkout after the primary export completes. It deliberately
copies rather than re-running the pipeline per target: a second run
would re-fetch, re-enrich (paying Anthropic again), and -- because the
`today` filter and every source's live content move between runs --
could produce a *different* set of opportunities for each checkout. One
export copied N times is the only way the checkouts are guaranteed to
agree.

Only generated artifacts are mirrored. `partners.json` is an *input*
the pipeline reads (`normalize_run`'s partner roster) and is curated per
checkout, so overwriting it would clobber one site's roster with
another's. `yield-history.json` is per-run operational state belonging
to the run that produced it.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

#: Generated `src/data` files a mirror target should receive. Kept
#: explicit rather than globbing the directory so an unrelated file
#: living beside them (notably the curated `partners.json`) is never
#: copied over the target's own copy.
MIRRORED_DATA_FILES = ("opportunities.json", "scrape-meta.json", "ads.json")

#: Event images referenced by the mirrored `opportunities.json`. Without
#: these the copied JSON would point at images the target checkout does
#: not have.
IMAGES_SUBPATH = Path("public") / "images" / "opportunities"


def mirror_site_data(
    primary_site_dir: str | Path,
    target_site_dirs: list[str | Path],
    *,
    dry_run: bool = False,
) -> list[Path]:
    """Copy the export at ``primary_site_dir`` into each target checkout.

    Args:
        primary_site_dir: the checkout the pipeline just exported into.
        target_site_dirs: additional checkouts to bring into step. A
            target that resolves to ``primary_site_dir`` is skipped, so
            passing the primary explicitly is harmless.
        dry_run: log what would be copied, write nothing -- matching the
            `dry_run` contract `export_opportunities()` already honors.

    Returns:
        The site directories actually mirrored into, in the order given.
        A target that does not exist, or that has no ``src/data``, is
        logged and skipped rather than raising: a missing sibling
        checkout is a normal local condition (not every machine has both
        repos) and must never fail a scrape that already succeeded.
    """
    primary = Path(primary_site_dir).resolve()
    mirrored: list[Path] = []

    for raw_target in target_site_dirs:
        target = Path(raw_target).resolve()

        if target == primary:
            continue
        if not (target / "src" / "data").is_dir():
            logger.warning(
                "Mirror target %s has no src/data directory; skipping it "
                "(the scrape itself is unaffected)",
                target,
            )
            continue

        if dry_run:
            logger.info("Would mirror the export into %s (dry run)", target)
            mirrored.append(target)
            continue

        for filename in MIRRORED_DATA_FILES:
            source_file = primary / "src" / "data" / filename
            if not source_file.is_file():
                # ads.json is only written when ad configs exist; a
                # missing source file is not an error.
                continue
            shutil.copy2(source_file, target / "src" / "data" / filename)

        _mirror_images(primary / IMAGES_SUBPATH, target / IMAGES_SUBPATH)

        logger.info("Mirrored the export into %s", target)
        mirrored.append(target)

    return mirrored


def _mirror_images(source_dir: Path, target_dir: Path) -> None:
    """Copy event images across, adding new files without deleting any.

    Images are additive on purpose: an opportunity dropped from *this*
    export may still be referenced by a page the target checkout has not
    rebuilt yet, so deleting its image would break that page for no
    gain. Stale images cost only disk.
    """
    if not source_dir.is_dir():
        return

    target_dir.mkdir(parents=True, exist_ok=True)
    for image in source_dir.iterdir():
        if not image.is_file():
            continue
        destination = target_dir / image.name
        # Skip a byte-identical file already present -- these are
        # content-addressed downloads, so equal size and mtime means
        # equal content, and most runs re-download very few of them.
        if destination.is_file() and destination.stat().st_size == image.stat().st_size:
            continue
        shutil.copy2(image, destination)
