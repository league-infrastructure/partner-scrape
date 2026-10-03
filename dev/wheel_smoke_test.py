#!/usr/bin/env python3
"""Build the wheel, install it into a fresh venv outside the repo, and smoke-test it.

Proves that a pip-installed ``partner-scrape`` works with no repo checkout
and no bucket credentials:

1. ``partner-scrape --help`` runs with every DO_SPACES_* / AWS_* variable
   stripped from the environment.
2. The bundled registry (``registry_data/``), the in-package data files and
   ``data-schema.md`` are present in the installed package.
3. One dry run (``--dry-run``, offline: empty registry, empty fake site
   checkout) succeeds with ``SCRAPE_CACHE_DIR`` and ``PARTNER_SCRAPE_DATA_DIR``
   pointing at local temp dirs -- never the real bucket -- and writes nothing.
   (The real bundled registry is only parsed, not fetched, so CI stays offline.)

Usage::

    python dev/wheel_smoke_test.py            # builds the wheel with `uv build`
    python dev/wheel_smoke_test.py --wheel dist/partner_scrape-*.whl

Requires ``uv`` on PATH. Used by ``.github/workflows/wheel-smoke.yml``.
"""

from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Probe run inside the installed venv (cwd is a temp dir, not the repo).
_PROBE = """
import importlib.util, pathlib, sys
spec = importlib.util.find_spec("partner_scrape")
pkg = pathlib.Path(spec.origin).parent
assert "site-packages" in str(pkg), f"not an installed copy: {pkg}"
from partner_scrape.config import get_sources_dir, get_hubs_dir
from partner_scrape.registry.loader import load_sources
n = len(load_sources())  # parses + validates every bundled source TOML
assert n > 0, f"bundled registry has no sources: {get_sources_dir()}"
assert get_hubs_dir().is_dir(), get_hubs_dir()
for rel in ("data-schema.md", "directory/data/places.toml",
            "teams/data/tarc-sd.tsv", "registry_data/ads"):
    assert (pkg / rel).exists(), f"missing from wheel: {rel}"
print(f"installed at {pkg}; {n} bundled sources")
"""


def _clean_env(**extra: str) -> dict[str, str]:
    """Environment with every bucket/LLM credential removed."""
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("DO_SPACES_", "AWS_", "ANTHROPIC_"))
        and k not in {"SCRAPE_CACHE_DIR", "PARTNER_SCRAPE_DATA_DIR", "SITE_DIR",
                      "PARTNER_SCRAPE_REGISTRY_DIR", "PARTNER_SCRAPE_EVENT_DB"}
    }
    env.update(extra)
    return env


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if result.returncode != 0:
        sys.stderr.write(result.stdout + result.stderr)
        raise SystemExit(f"FAILED (exit {result.returncode}): {' '.join(map(str, cmd))}")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--wheel", help="Wheel to test (default: build one with uv)")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory(prefix="ps-smoke-") as tmp_s:
        tmp = Path(tmp_s)
        if args.wheel:
            wheels = glob.glob(args.wheel)
        else:
            _run(["uv", "build", "--wheel", "-o", str(tmp / "dist")], cwd=REPO)
            wheels = glob.glob(str(tmp / "dist" / "*.whl"))
        if len(wheels) != 1:
            raise SystemExit(f"expected exactly one wheel, found {wheels}")
        wheel = str(Path(wheels[0]).resolve())

        venv = tmp / "venv"
        _run(["uv", "venv", "-q", str(venv)], cwd=tmp)
        bindir = venv / ("Scripts" if os.name == "nt" else "bin")
        py = str(bindir / ("python.exe" if os.name == "nt" else "python"))
        _run(["uv", "pip", "install", "-q", "--python", py, wheel], cwd=tmp)
        exe = str(bindir / ("partner-scrape.exe" if os.name == "nt" else "partner-scrape"))

        # 1. --help with no credentials at all.
        out = _run([exe, "--help"], cwd=tmp, env=_clean_env()).stdout
        assert "usage: partner-scrape" in out, out
        print("OK  --help")

        # 2. Bundled data present in the installed copy.
        print("OK ", _run([py, "-c", _PROBE], cwd=tmp, env=_clean_env()).stdout.strip())

        # 3. Dry run with explicit LOCAL cache/data dirs.
        cache, data = tmp / "cache", tmp / "data"
        site, empty_registry = tmp / "site", tmp / "empty-registry"
        (site / "src" / "data").mkdir(parents=True)
        (site / "src" / "data" / "partners.json").write_text("[]")
        empty_registry.mkdir()
        env = _clean_env(SCRAPE_CACHE_DIR=str(cache), PARTNER_SCRAPE_DATA_DIR=str(data))

        run = _run([exe, "--dry-run", "--site-dir", str(site),
                    "--registry-dir", str(empty_registry)], cwd=tmp, env=env)
        print("OK  main --dry-run:", run.stdout.strip().splitlines()[0])

        written = [p for d in (data,) if d.exists() for p in d.rglob("*") if p.is_file()]
        assert not written, f"dry run wrote files: {written}"
        print("smoke test passed")


if __name__ == "__main__":
    main()
