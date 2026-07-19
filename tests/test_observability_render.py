"""Unit tests for `partner_scrape.observability.render.render_text`
(ticket 004-002): alert-before-detail ordering, and a no-alert run's
plain per-source output.
"""

from __future__ import annotations

from datetime import datetime, timezone

from partner_scrape.observability.render import render_text
from partner_scrape.observability.yield_report import SourceYield, YieldReport

NOW = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)


def _source(**overrides: object) -> SourceYield:
    defaults: dict[str, object] = dict(
        source_id="acme",
        org_name="Acme Org",
        found=3,
        dated=2,
        new=1,
        dropped=0,
        slugs=frozenset({"a"}),
        previous_found=3,
        delta=0,
        error=None,
        zero_yield=False,
        cliff=False,
    )
    defaults.update(overrides)
    return SourceYield(**defaults)  # type: ignore[arg-type]


class TestAlertOrdering:
    def test_alert_lines_appear_before_the_per_source_detail_section(self):
        healthy = _source(source_id="healthy")
        zero_yield = _source(
            source_id="fleet",
            org_name="Fleet Science Center",
            found=0,
            previous_found=12,
            delta=-12,
            zero_yield=True,
        )
        report = YieldReport(sources=[healthy, zero_yield], generated_at=NOW)

        text = render_text(report)

        alert_index = text.index("ALERTS")
        detail_index = text.index("Per-source detail:")
        assert alert_index < detail_index
        # And the alerted source is actually named inside the alert
        # block, before the detail section starts.
        alert_mention_index = text.index("fleet")
        assert alert_mention_index < detail_index

    def test_zero_yield_alert_line_names_the_source_and_its_kind(self):
        zero_yield = _source(
            source_id="fleet", found=0, previous_found=12, delta=-12, zero_yield=True
        )
        report = YieldReport(sources=[zero_yield], generated_at=NOW)

        text = render_text(report)

        assert "ZERO-YIELD" in text
        assert "fleet" in text

    def test_cliff_alert_is_labeled_distinctly_from_zero_yield(self):
        cliff = _source(source_id="acme", found=4, previous_found=10, delta=-6, cliff=True)
        report = YieldReport(sources=[cliff], generated_at=NOW)

        text = render_text(report)

        assert "CLIFF" in text
        assert "ZERO-YIELD" not in text

    def test_multiple_alerts_are_all_listed_ahead_of_the_detail_section(self):
        zero_yield = _source(
            source_id="fleet", found=0, previous_found=12, delta=-12, zero_yield=True
        )
        cliff = _source(source_id="birch", found=3, previous_found=10, delta=-7, cliff=True)
        healthy = _source(source_id="coastal")
        report = YieldReport(sources=[healthy, zero_yield, cliff], generated_at=NOW)

        text = render_text(report)

        detail_index = text.index("Per-source detail:")
        assert text.index("fleet") < detail_index
        assert text.index("birch") < detail_index
        assert "ALERTS (2):" in text


class TestNoAlertRun:
    def test_plain_per_source_output_with_no_alerts(self):
        healthy = _source()
        report = YieldReport(sources=[healthy], generated_at=NOW)

        text = render_text(report)

        assert "ALERTS: none" in text
        assert "acme" in text
        assert "found=3" in text
        assert "dated=2" in text
        assert "new=1" in text
        assert "dropped=0" in text

    def test_first_ever_run_shows_no_alerts_and_an_na_delta(self):
        first_run_source = _source(previous_found=None, delta=None)
        report = YieldReport(sources=[first_run_source], generated_at=NOW)

        text = render_text(report)

        assert "ALERTS: none" in text
        assert "delta n/a" in text
