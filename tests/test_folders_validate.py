"""Validatierapport folders — zonder netwerk: een nep-HTTP levert de HTML."""
from folders.config import BronCfg
from folders.validate import route_advies, status, validate_one, validate_report
from folders.viewer import ViewerInfo
from scraper.http import BlockedError


class _Resp:
    def __init__(self, text, url):
        self.text, self.url, self.status_code = text, url, 200
        self.content = text.encode()


class _Http:
    def __init__(self, pages: dict, blocked=()):
        self.pages, self.blocked, self.requests_done, self.robots_skipped = pages, blocked, 0, 0

    def get(self, url, **kw):
        self.requests_done += 1
        if url in self.blocked:
            raise BlockedError(f"HTTP 403 op {url}")
        html = self.pages.get(url)
        return _Resp(html, url) if html is not None else None


def _cfg(**kw):
    base = dict(id="zeeman", name="Zeeman", folder_url="https://z.nl/folder")
    base.update(kw)
    return BronCfg(**base)


def test_publitas_route_groen():
    http = _Http({"https://z.nl/folder": '<title>Folder</title>Geldig 9 t/m 15 september'
                                         '<iframe src="https://view.publitas.com/z/f/"></iframe>',
                  "https://view.publitas.com/z/f/": "<div data-page='20'></div>"})
    r = validate_one(_cfg(), http)
    assert status(r) == "groen" and r["viewer"].kind == "publitas"
    assert r["viewer_pages"] == 20 and r["geldig"] is not None
    assert "publitas" in route_advies(r)


def test_geblokkeerd_rood():
    http = _Http({}, blocked={"https://z.nl/folder"})
    r = validate_one(_cfg(), http)
    assert status(r) == "rood" and r["geblokkeerd"] and "geweerd" in route_advies(r)


def test_niet_bereikbaar_rood():
    r = validate_one(_cfg(), _Http({}))
    assert status(r) == "rood" and "niet bereikbaar" in route_advies(r)


def test_render_oranje_en_mail_only_wit():
    r = validate_one(_cfg(), _Http({"https://z.nl/folder": "<div id=app></div>"}))
    assert status(r) == "oranje" and "render" in route_advies(r)
    m = validate_one(_cfg(id="primark", name="Primark", folder_url=""), _Http({}))
    assert status(m) == "wit" and "mail-only" in route_advies(m) and m["requests"] == 0


def test_rapport_bevat_tabel_en_secties():
    http = _Http({"https://z.nl/folder": '<a href="/f.pdf">pdf</a>', "https://z.nl/f.pdf": "%PDF-1.4"})
    md = validate_report([validate_one(_cfg(), http),
                          validate_one(_cfg(id="primark", name="Primark", folder_url=""), _Http({}))])
    assert "| Zeeman | https://z.nl/folder | 200 | pdf | ja" in md
    assert "| Primark | mail-only |" in md and "## Primark" in md
    assert "route pdf" in md


def test_viewerinfo_defaults():
    v = ViewerInfo("render")
    assert v.url == "" and v.evidence == [] and v.page_hints == 0
