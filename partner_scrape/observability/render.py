"""Report Rendering: `render_text(report) -> str` (sprint.md's
Architecture > Report Rendering, issue 08).

Formats a `YieldReport` as plain, human-readable text: any zero-yield/
cliff alerts listed *before* the per-source detail lines, so an
operator scanning a CI job log sees the alerts without reading every
line. Computing the report's data is `yield_report.py`'s job, not this
module's; where the text goes (stdout, a GitHub Actions step summary)
is ticket 003/004's job, not this module's either.
"""

from __future__ import annotations

from partner_scrape.observability.yield_report import SourceYield, YieldReport


def _alert_label(source: SourceYield) -> str:
    if source.zero_yield:
        return "ZERO-YIELD"
    if source.cliff:
        return "CLIFF"
    return ""


def _alert_line(source: SourceYield) -> str:
    previous = source.previous_found if source.previous_found is not None else "n/a"
    return (
        f"  [{_alert_label(source)}] {source.source_id} ({source.org_name}): "
        f"found={source.found} (previous={previous})"
    )


def _detail_line(source: SourceYield) -> str:
    delta = f"{source.delta:+d}" if source.delta is not None else "n/a"
    markers = ""
    if source.has_alert:
        markers += f" [{_alert_label(source)}]"
    if source.error is not None:
        markers += " [ERROR]"
    return (
        f"  {source.source_id}: found={source.found} (delta {delta}) "
        f"dated={source.dated} new={source.new} dropped={source.dropped}{markers}"
    )


def render_text(report: YieldReport) -> str:
    """Render ``report`` as plain text.

    Any zero-yield/cliff alerts are listed first (under an ``ALERTS``
    heading), ahead of the ``Per-source detail`` section -- an operator
    scanning a GitHub Actions job log sees the alerts without reading
    every line (sprint.md's Report Rendering responsibility).
    """
    lines: list[str] = [f"Yield report ({report.generated_at.isoformat()})", ""]

    alerts = report.alerts
    if alerts:
        lines.append(f"ALERTS ({len(alerts)}):")
        lines.extend(_alert_line(source) for source in alerts)
    else:
        lines.append("ALERTS: none")
    lines.append("")

    lines.append("Per-source detail:")
    lines.extend(_detail_line(source) for source in report.sources)

    return "\n".join(lines)
