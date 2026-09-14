"""Beleefde HTTP-client: throttling, retries, robots.txt.

Twee smaken van dezelfde client:
  * requests (standaard) — de gewone Python-client;
  * impersonate='chrome' — curl_cffi: dezelfde aanroepen, maar het TLS- en
    HTTP/2-handschrift (JA3/JA4, header-volgorde, ALPN) van een echte
    Chrome. Bronnen die op dat handschrift filteren (Zeeman sinds 14-09-2026)
    zien dan een browser in plaats van een script. Wat de client doet blijft
    identiek: ±1 request/sec, robots.txt gerespecteerd, alleen publieke
    pagina's — zie PLAN.md §8.
"""
from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import blokkade

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Wat een echte Chrome méér meestuurt dan requests. Zonder deze regels
# is 'Mozilla/5.0 … Chrome/126' een kale bewering; mét is de headerset
# consistent met de user-agent. Voor curl_cffi-impersonatie zet de
# bibliotheek zelf de bijpassende set en laten we deze weg.
BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
              "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.6",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


class BlockedError(RuntimeError):
    """403/429: de bron weert ons — direct stoppen, niet doordrammen.

    Draagt status, headers en het begin van de body mee, zodat de
    toegangsladder en de diagnose kunnen zien wíe er nee zegt."""

    def __init__(self, msg: str, *, status: int = 0, headers=None, body: str = "",
                 url: str = ""):
        super().__init__(msg)
        self.status = status
        self.headers = dict(headers or {})
        self.body = (body or "")[:20000]
        self.url = url

    @property
    def signatuur(self) -> str:
        return blokkade.signatuur(self.status, self.headers, self.body)


class Http:
    def __init__(self, min_delay: float = 0.7, timeout: int = 25,
                 user_agent: str = DEFAULT_UA, respect_robots: bool = True,
                 impersonate: str | None = None, browser_headers: bool = False):
        self.min_delay = min_delay
        self.timeout = timeout
        self.user_agent = user_agent
        self.respect_robots = respect_robots
        self.impersonate = impersonate
        self.requests_done = 0
        self.robots_skipped = 0
        self._last_request = 0.0
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

        if impersonate:
            # ImportError laten doorlopen: de ladder slaat de trede dan over
            # met een leesbare notitie, in plaats van stil op requests terug
            # te vallen en een 'chrome'-meting te rapporteren die er geen was.
            from curl_cffi import requests as cffi_requests
            self.session = cffi_requests.Session(impersonate=impersonate)
            self.session.headers.update({"Accept-Language": BROWSER_HEADERS["Accept-Language"]})
            # curl_cffi zet de user-agent van de nagebootste browser zelf; die
            # gebruiken we ook voor robots.txt.
            self.user_agent = self.session.headers.get("User-Agent") or user_agent
            return

        self.session = requests.Session()
        if browser_headers:
            self.session.headers.update({"User-Agent": user_agent, **BROWSER_HEADERS})
        else:
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
                resp = self._raw_get(f"https://{host}/robots.txt")
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    rp = None  # geen robots.txt → alles toegestaan
            except Exception:
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
    def _raw_get(self, url: str):
        """Eén GET zonder throttling/robots. Bij curl_cffi zelf herkansen
        op 502/503/504 (urllib3's Retry geldt daar niet)."""
        if not self.impersonate:
            return self.session.get(url, timeout=self.timeout)
        resp = None
        for poging in range(3):
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code not in (502, 503, 504):
                break
            time.sleep(1.5 * (poging + 1))
        return resp

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
            resp = self._raw_get(url)
        except Exception:
            # requests.RequestException én curl_cffi's eigen fouten: één
            # mislukte pagina is 'geen antwoord', geen einde van de run.
            return None
        if resp.status_code in (403, 429):
            body = resp.text if isinstance(getattr(resp, "text", None), str) else ""
            sig = blokkade.signatuur(resp.status_code, resp.headers, body)
            raise BlockedError(f"HTTP {resp.status_code} op {url} — {blokkade.kort(sig)}",
                               status=resp.status_code, headers=resp.headers,
                               body=body, url=url)
        if resp.status_code != 200:
            return None
        if as_json:
            try:
                return resp.json()
            except ValueError:
                return None
        return resp
