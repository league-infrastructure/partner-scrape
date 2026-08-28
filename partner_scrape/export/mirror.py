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

Sprint 009 (ticket 005): `publish.project()` (ticket 004) writes a
second, additive published contract -- a directory tree under
`public/data/` (a partner roster plus per-partner event files), not a
flat file. This module mirrors that tree too, recursively, alongside
the existing flat-file and image copies. `public/data/partners.json`
is *generated output* `publish.project()` writes -- a different file,
at a different path, from the curated `src/data/partners.json` above,
despite the identical basename. Only the generated one is ever
mirrored; `MIRRORED_DATA_FILES` still governs `src/data/` alone, so
this addition cannot touch the curated file.
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
#:
#: Sprint 011 (ticket 002): `"teams.json"` is written by
#: `teams/export.py`, a structurally separate module from this
#: subsystem's own `writer.py`/`ads.py` (see `teams/DESIGN.md`) --
#: mirroring reuses this exact allowlist/copy mechanism unmodified, the
#: same way `teams`'s CLI subcommand reuses `mirror_site_data` itself
#: rather than duplicating it.
MIRRORED_DATA_FILES = ("opportunities.json", "scrape-meta.json", "ads.json", "teams.json")

#: Event images referenced by the mirrored `opportunities.json`. Without
#: these the copied JSON would point at images the target checkout does
#: not have.
IMAGES_SUBPATH = Path("public") / "images" / "opportunities"

#: The published `public/data/` tree `publish.project()` writes (ticket
#: 004): a partner roster (`partners.json`) plus per-partner
#: `events.json`/`past-events.json`. Copied recursively, unlike
#: `MIRRORED_DATA_FILES`'s flat allowlist, because `publish.project()`
#: itself already owns what belongs under this path -- mirror.py only
#: needs the one directory root, not an enumerated list of every file
#: and per-partner subdirectory inside it. This is *not* the same file
#: as the curated `src/data/partners.json` `MIRRORED_DATA_FILES`
#: deliberately excludes -- same basename, different path, different
#: purpose (generated output here, curated input there).
PUBLIC_DATA_SUBPATH = Path("public") / "data"


def mirror_site_data(
    primary_site_dir: str | Path,
    target_site_dirs: list[str | Path],
    *,
    dry_run: bool = False,
) -> list[Path]:
    """Copy the export at ``primary_site_dir`` into each target checkout.

    Copies `MIRRORED_DATA_FILES` and `IMAGES_SUBPATH` as before, plus
    (sprint 009, ticket 005) the entire `PUBLIC_DATA_SUBPATH`
    (`public/data/`) tree `publish.project()` writes -- recursively, and
    with the same additive/byte-identical-skip policy `IMAGES_SUBPATH`
    already uses. A target checkout that has not rebuilt yet may still
    be serving a partner directory this run's projection no longer
    produces (e.g. a partner dropped from the curated roster); nothing
    under `public/data/` is ever deleted from a target, only added to or
    refreshed, for the same reason images are never pruned.

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
        _mirror_directory_tree(primary / PUBLIC_DATA_SUBPATH, target / PUBLIC_DATA_SUBPATH)

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


def _mirror_directory_tree(source_dir: Path, target_dir: Path) -> None:
    """Recursively copy every file under ``source_dir`` into
    ``target_dir``, adding new or changed files and never deleting
    anything already present at the target.

    This is `_mirror_images`'s additive/skip-unchanged policy
    generalized to an arbitrary nested tree (`_mirror_images` itself is
    left unchanged -- its single flat directory needs no recursion).
    Additive for the same reason: a target checkout that has not
    rebuilt yet may still be serving a partner directory this run's
    projection no longer produces, and deleting it would break that
    page for a savings of only disk space. See export/DESIGN.md's
    Design section ("mirror.py's directory copy is additive/
    skip-unchanged").

    A missing ``source_dir`` (the primary has never run
    `publish.project()`) is a no-op, not an error -- a mirror target
    must still receive the flat-file/image copy `mirror_site_data`
    already performs even when the newer `public/data/` tree does not
    exist yet.
    """
    if not source_dir.is_dir():
        return

    for source_path in source_dir.rglob("*"):
        if not source_path.is_file():
            continue
        relative = source_path.relative_to(source_dir)
        destination = target_dir / relative
        # Same byte-identical skip check as `_mirror_images`.
        if destination.is_file() and destination.stat().st_size == source_path.stat().st_size:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
