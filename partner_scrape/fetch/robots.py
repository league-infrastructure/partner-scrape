"""robots.txt permission checking.

Wraps the stdlib ``urllib.robotparser.RobotFileParser`` but retrieves
robots.txt through the same injected ``Fetcher`` used for real requests,
rather than ``RobotFileParser.read()`` (which opens its own socket).
That keeps this check exercisable in tests with zero network, matching
the rest of this package.
"""

from __future__ import annotations

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from partner_scrape.fetch.fetcher import Fetcher


class RobotsDisallowed(Exception):
    """Raised when a target URL is disallowed by its site's robots.txt."""


def robots_txt_url(url: str) -> str:
    """Derive the robots.txt URL for the same scheme+host as ``url``."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/robots.txt"


def is_allowed(url: str, fetcher: Fetcher, user_agent: str) -> bool:
    """Return whether ``user_agent`` may fetch ``url`` per its robots.txt.

    A missing or unreadable robots.txt (any non-200 response) is
    treated as "everything allowed" -- the conventional interpretation
    of "no robots.txt present" on the web, and also what
    ``RobotFileParser`` does when fed an empty ruleset.
    """
    response = fetcher.get(robots_txt_url(url))

    parser = RobotFileParser()
    if response.status == 200:
        parser.parse(response.body.splitlines())
    else:
        parser.parse([])

    return parser.can_fetch(user_agent, url)
