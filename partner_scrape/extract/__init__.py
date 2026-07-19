"""Generic HTML Extractor: field values + confidence from one HTML page.

See ``sprint.md``'s Architecture > Generic HTML Extractor, SUC-010. The
public surface is :mod:`partner_scrape.extract.ladder`'s
:func:`~partner_scrape.extract.ladder.extract_fields` -- everything else
in this package is ladder-internal.
"""

from __future__ import annotations

from partner_scrape.extract.ladder import (
    CONFIDENCE_BODY_REGEX,
    CONFIDENCE_JSON_LD,
    CONFIDENCE_OPENGRAPH,
    CONFIDENCE_TIME_TAG,
    CONFIDENCE_TITLE_FALLBACK,
    CONFIDENCE_URL_DATE,
    extract_fields,
)

__all__ = [
    "extract_fields",
    "CONFIDENCE_JSON_LD",
    "CONFIDENCE_TIME_TAG",
    "CONFIDENCE_OPENGRAPH",
    "CONFIDENCE_TITLE_FALLBACK",
    "CONFIDENCE_URL_DATE",
    "CONFIDENCE_BODY_REGEX",
]
