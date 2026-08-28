"""teams.sources: per-league team-roster acquisition strategies.

Every concrete source (``ftcscout.py`` here; ``tba.py`` in ticket
011-003) implements the ``TeamSource`` protocol defined in
``base.py``. This package is structurally disjoint from
``partner_scrape.adapters.base`` -- no module here imports it, and no
``TeamSource`` is registered with ``adapters.base.ADAPTERS``. See
``base.py``'s module docstring for why that boundary matters.
"""

from __future__ import annotations
