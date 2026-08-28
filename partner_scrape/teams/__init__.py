"""teams: a second, independent pipeline (sprint 011).

Acquires, locates, and publishes San Diego County's FIRST robotics
teams (FTC via FTCScout, FRC via The Blue Alliance) as a standalone
``teams.json`` data contract -- deliberately not routed through the
existing ``Event``/``Opportunity`` pipeline (``partner_scrape.model``,
``partner_scrape.pipeline``), since a ``Team`` is a standing entity
with no date and no relevance-gating need. See ``teams/DESIGN.md`` for
the full subsystem writeup.

This ticket (011-001) lays the foundation only: ``model.Team`` and the
``sources.TeamSource`` protocol plus its first implementation
(``sources.ftcscout``). Nothing here is imported by ``pipeline.py``,
``cli.py``, or any other existing module -- that wiring is ticket
011-002 (``teams.pipeline``, the ``teams`` CLI subcommand, and
``teams.export``).
"""

from __future__ import annotations
