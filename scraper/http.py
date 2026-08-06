"""Beleefde HTTP-client: throttling, retries, robots.txt."""
from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class BlockedError(RuntimeError):
    """403/429: de bron weert ons — direct stoppen, niet doordrammen."""


class Http:
    def __init__(self, min_delay: float = 0.7, timeout: int = 25,
                 user_agent: str = DEFAULT_UA, respect_robots: bool = True):
        self.min_delay = min_delay
        self.timeout = timeout
        self.user_agent = user_agent
        self.respect_robots = respect_robots
        self.requests_done = 0
        self.robots_skipped = 0
        self._last_request = 0.0
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.6",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        })
        retry = Retry(total=2, backoff_factor=1.5,
                      status_forcelist=[502, 503, 504],
                      allowed_methods=["GET"])
        adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    # -- robots ---------------------------------------------------------
    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        host = urlsplit(url).netloc
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                resp = self.session.get(f"https://{host}/robots.txt", timeout=self.timeout)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    rp = None  # geen robots.txt → alles toegestaan
            except requests.RequestException:
                rp = None
            self._robots[host] = rp
        return self._robots[host]

    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        rp = self._robots_for(url)
        if rp is None:
            return True
        return rp.can_fetch(self.user_agent, url)

    # -- ophalen --------------------------------------------------------
    def get(self, url: str, *, as_json: bool = False):
        """GET met throttling en robots-check. Geeft None bij 404/parsefout,
        gooit BlockedError bij 403/429."""
        if not self.allowed(url):
            self.robots_skipped += 1
            return None
        wait = self.min_delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()
        self.requests_done += 1
        try:
            resp = self.session.get(url, timeout=self.timeout)
        except requests.RequestException:
            return None
        if resp.status_code in (403, 429):
            raise BlockedError(f"HTTP {resp.status_code} op {url} (bot-bescherming?)")
        if resp.status_code != 200:
            return None
        if as_json:
            try:
                return resp.json()
            except ValueError:
                return None
        return resp
