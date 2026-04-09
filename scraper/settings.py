"""
Scrapy settings for the partner-scrape project.

All Scrapy settings reference:
  https://docs.scrapy.org/en/latest/topics/settings.html
"""

BOT_NAME = "partner-scrape"

SPIDER_MODULES = ["scraper.spiders"]
NEWSPIDER_MODULE = "scraper.spiders"

# Identify the bot in the User-Agent header
USER_AGENT = (
    "partner-scrape/1.0 "
    "(+https://github.com/league-infrastructure/partner-scrape)"
)

# Respect robots.txt rules
ROBOTSTXT_OBEY = True

# Politeness: add a small delay between requests to the same domain
DOWNLOAD_DELAY = 1
RANDOMIZE_DOWNLOAD_DELAY = True

# Concurrency
CONCURRENT_REQUESTS = 32
CONCURRENT_REQUESTS_PER_DOMAIN = 4

# AutoThrottle: automatically adjusts request rate based on server load
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 30
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
AUTOTHROTTLE_DEBUG = False

# Network timeouts
DOWNLOAD_TIMEOUT = 30

# Skip responses larger than 10 MB (avoids downloading huge binary blobs
# that slipped past the extension filter)
DOWNLOAD_MAXSIZE = 10 * 1024 * 1024  # 10 MB

# Maximum crawl depth per domain
DEPTH_LIMIT = 20

# Retry settings
RETRY_ENABLED = True
RETRY_TIMES = 2
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Cookies are not needed for mirroring
COOKIES_ENABLED = False

# Disable the Telnet console (not needed in production)
TELNETCONSOLE_ENABLED = False

# Default request headers (supplement the User-Agent set above)
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en",
}

# No custom item pipelines – the spider writes files directly
ITEM_PIPELINES = {}

# Keep only essential extensions
EXTENSIONS = {
    "scrapy.extensions.corestats.CoreStats": 500,
    "scrapy.extensions.memusage.MemoryUsage": 560,
    "scrapy.extensions.logstats.LogStats": 540,
}

LOG_LEVEL = "INFO"

# DNS cache
DNSCACHE_ENABLED = True
