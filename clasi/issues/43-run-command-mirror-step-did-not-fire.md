---
status: pending
---

# Triage: the run command's mirror step didn't update the beta site/ checkout

## Description

After the 2026-08-31 post-016 production run (plain `uv run
partner-scrape`, exit 0, wrote 350 opportunities to ../stem-ecosystem),
this repo's beta `site/src/data/opportunities.json` was still the prior
312-record snapshot — the exact "beta silently serves an old snapshot"
failure `config.get_mirror_site_dirs()`'s docstring exists to prevent.
The mirror block at `partner_scrape/cli.py:477-485` should have fired
(no --dry-run, no --no-mirror, MIRROR_SITE_DIRS unset → default
`site/`). A manual `mirror_site_data('../stem-ecosystem', ['site'])`
immediately afterward worked and wrote the file, so the copy machinery
itself is fine.

Hypotheses to check: default-path resolution relative to CWD in a
wrapped/background shell; an exception in the mirror step swallowed
before the final "wrote N opportunities" line (check ordering — the
run's stdout tail showed no mirror log lines at all); or the block not
reached on the default (no-subcommand) code path despite the parser
wiring. Reproduce with `-v` and add a regression test asserting the
default run path invokes mirror_site_data when MIRror config is unset.

## References

Run log: scratchpad run-post-016.log (session 2026-08-31);
partner_scrape/cli.py:477; partner_scrape/export/mirror.py;
partner_scrape/config.get_mirror_site_dirs.
