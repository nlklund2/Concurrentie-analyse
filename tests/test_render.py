"""Render-strategie: alleen uitvoerbaar waar Playwright + Chromium aanwezig zijn
(lokaal en in de scrape-/validatieworkflows); in de kale CI wordt dit overgeslagen."""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from scraper.jsonscan import products_from_html
from scraper.strategies.render_listing import (_ApiSink, _dom_products, _load,
                                               _load_of_verse_sessie,
                                               _verse_pagina)

FIXTURE = (Path(__file__).parent / "fixtures" / "render-listing.html").resolve()
CONSENT_FIXTURE = (Path(__file__).parent / "fixtures" / "consent-listing.html").resolve()


def _browser(pw):
    try:
        return pw.chromium.launch()
    except Exception:
        alt = Path("/opt/pw-browsers/chromium")
        if not alt.exists():
            pytest.skip("chromium niet beschikbaar")
        return pw.chromium.launch(executable_path=str(alt))


def test_render_pijplijn_op_js_pagina():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception:
            # omgevingen met een systeem-Chromium (bv. de ontwikkelcontainer)
            alt = Path("/opt/pw-browsers/chromium")
            if not alt.exists():
                pytest.skip("chromium niet beschikbaar")
            browser = pw.chromium.launch(executable_path=str(alt))
        page = browser.new_page()

        html = _load(page, FIXTURE.as_uri())
        assert html is not None

        # JS-geïnjecteerde JSON-LD wordt na rendering gewoon gevonden
        prods = products_from_html(html, FIXTURE.as_uri())
        assert any(p.title == "Dames hipster 3-pack" and p.price == 6.99
                   for p in prods)

        # DOM-vangnet: kaarten met €-prijs, incl. was-prijs
        dom = {p.title: p for p in _dom_products(page)}
        assert dom["Jongens boxers 2-pack"].price == 4.99
        pyjama = dom["Meisjes pyjama sterren"]
        assert pyjama.price == 9.99
        assert pyjama.was_price == 14.99

        browser.close()


def test_cookiemuur_wordt_weggeklikt_en_producten_verschijnen():
    """Zonder consent blijft de lijst leeg; mét consent komen de producten."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = _browser(pw)
        page = browser.new_page()

        # zonder consent: muur staat er, geen producten
        _load(page, CONSENT_FIXTURE.as_uri(), consent=False)
        assert _dom_products(page) == []

        # mét consent: muur weg, producten zichtbaar incl. was-prijs
        _load(page, CONSENT_FIXTURE.as_uri(), consent=True)
        found = {p.title: p for p in _dom_products(page)}
        assert found["Dames slip 5-pack"].price == 5.99
        boxers = found["Heren boxers 3-pack"]
        assert boxers.price == 8.99 and boxers.was_price == 11.99

        browser.close()


def test_dom_kaart_met_prijs_buiten_de_link():
    """C&A/KiK-patroon: prijs in een apart kaart-element, titel uit aria-label."""
    from playwright.sync_api import sync_playwright
    fixture = (Path(__file__).parent / "fixtures" / "card-listing.html").resolve()
    with sync_playwright() as pw:
        browser = _browser(pw)
        page = browser.new_page()
        _load(page, fixture.as_uri(), consent=False)
        found = {p.title: p for p in _dom_products(page)}

        assert found["Dames hipster 3-pack"].price == 9.99
        boxers = found["Heren boxers 2-pack"]
        assert boxers.price == 8.99 and boxers.was_price == 12.99
        # het losse getal 599 mag geen prijs of titel worden
        sokken = found["Kindersokken 5-pack"]
        assert sokken.price == 3.99
        assert all("599" not in t for t in found)
        browser.close()


def test_dom_negeert_banners_en_navigatietegels():
    """Week 32: zonder eis dat de link naar een product wijst, kwamen bij Action
    'Veiligheidswaarschuwing: Big Jeff barbecuehandschoen' en bij C&A 'Voor
    meisjes' als artikel in de cijfers — inclusief de prijs van de banner."""
    from playwright.sync_api import sync_playwright
    fixture = (Path(__file__).parent / "fixtures" / "navigatie-listing.html").resolve()
    with sync_playwright() as pw:
        browser = _browser(pw)
        page = browser.new_page()
        _load(page, fixture.as_uri(), consent=False)
        found = {p.title: p for p in _dom_products(page)}

        assert set(found) == {"Dames slips 5-pack", "Baby pyjama met sterren"}
        assert found["Dames slips 5-pack"].price == 6.99
        pyjama = found["Baby pyjama met sterren"]
        assert pyjama.price == 9.99 and pyjama.was_price == 14.99
        browser.close()


def test_titel_uit_kaarttekst_zonder_maten_en_varianten():
    """Action-patroon: geen aria-label of heading, en de maatvermelding plakt
    aan de productnaam vast ('CompressiesokkenMaten 35 - 46 | 2 paar | …')."""
    from playwright.sync_api import sync_playwright
    fixture = (Path(__file__).parent / "fixtures" / "kaarttekst-listing.html").resolve()
    with sync_playwright() as pw:
        browser = _browser(pw)
        page = browser.new_page()
        _load(page, fixture.as_uri(), consent=False)
        found = {p.title: p for p in _dom_products(page)}

        assert set(found) == {"Compressiesokken", "Pairz sportsokken", "Dames hemd"}
        assert found["Compressiesokken"].price == 2.48
        assert found["Dames hemd"].price == 3.99
        browser.close()


def test_lui_ladend_raster_wordt_volgescrold_en_toon_meer_geklikt():
    """Action-patroon (03-09): het raster vult zich per scrollbatch en de rest
    zit achter een 'Toon meer'-knop. Met twee vaste scrolls bleef de teller op
    de eerste batches steken (±24 van veel meer tegels); de scroll-lus moet
    doorgaan tot de telling stilstaat én de knop aanklikken."""
    from playwright.sync_api import sync_playwright
    fixture = (Path(__file__).parent / "fixtures" / "lazy-listing.html").resolve()
    with sync_playwright() as pw:
        browser = _browser(pw)
        page = browser.new_page()
        _load(page, fixture.as_uri(), consent=False)
        found = _dom_products(page)
        assert len(found) == 30
        # '€ 3,48/st' is bij een los artikel de verkoopprijs, nooit een was-prijs
        assert all(p.was_price is None for p in found)
        assert {p.price for p in found} == {2.48, 3.48, 4.48, 5.48, 6.48}
        browser.close()


def test_prijzen_zonder_euroteken_in_de_tekst():
    """Shops die het €-teken via CSS neerzetten maken een €-gebaseerde scan
    blind. De losse prijsronde springt bij, maar alleen als er nérgens op de
    pagina een €-teken staat — en maten ('Maten 35 - 46') blijven eraf."""
    from playwright.sync_api import sync_playwright
    fixture = (Path(__file__).parent / "fixtures" / "prijs-zonder-euroteken.html").resolve()
    with sync_playwright() as pw:
        browser = _browser(pw)
        page = browser.new_page()
        _load(page, fixture.as_uri(), consent=False)
        found = {p.title: p for p in _dom_products(page)}

        assert set(found) == {"Dames slip 3-pack", "Heren boxer 2-pack"}
        assert found["Dames slip 3-pack"].price == 5.99
        boxer = found["Heren boxer 2-pack"]
        assert boxer.price == 7.99
        assert boxer.was_price is None      # 35 en 46 zijn maten, geen prijzen
        browser.close()


def test_prijs_achter_het_getal_zoals_c_and_a():
    """C&A schrijft '24,99 €' — getal eerst. De €-eerst-regex las daardoor maar
    een fractie van de kaarten (16 van ~39 prijzen op de pagina)."""
    from playwright.sync_api import sync_playwright
    fixture = (Path(__file__).parent / "fixtures" / "euro-achter-listing.html").resolve()
    with sync_playwright() as pw:
        browser = _browser(pw)
        page = browser.new_page()
        _load(page, fixture.as_uri(), consent=False)
        found = {p.title: p for p in _dom_products(page)}

        assert found["Baby pyjama dino"].price == 24.99
        romper = found["Baby romper sterren"]
        assert romper.price == 9.99 and romper.was_price == 17.99
        browser.close()


def test_late_cookiemuur_wordt_alsnog_weggeklikt():
    """Zeeman-patroon: Cookiebot rendert asynchroon, ná de eerste klikpoging.
    De herkansing in _load moet 'Alles toestaan' alsnog vinden."""
    from playwright.sync_api import sync_playwright
    fixture = (Path(__file__).parent / "fixtures" / "consent-laat.html").resolve()
    with sync_playwright() as pw:
        browser = _browser(pw)
        page = browser.new_page()
        html = _load(page, fixture.as_uri())
        assert html is not None
        assert page.evaluate("() => window.__consent") is True
        assert page.evaluate("() => !document.getElementById('laatdialoog')")
        browser.close()


class _SessieWeringHandler(BaseHTTPRequestHandler):
    """Bootst het Action-patroon na (diagnose 03-09): het éérste bezoek van een
    sessie krijgt HTTP 200 en een sessiecookie; elk vervolgbezoek mét die
    cookie wordt met 403 geweerd. Een verse context (schone cookies) is dus de
    enige doorgang — precies wat de herkansing moet doen."""

    def do_GET(self):
        if "sessie=1" in (self.headers.get("Cookie") or ""):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Access denied")
            return
        naam = self.path.strip("/").replace("?", "-").replace("=", "-") or "start"
        body = (f'<html><body><div><a href="/nl-nl/p/9{len(naam)}001/{naam}/">'
                f'<img alt="Artikel {naam}"><span>€ 4,95/st</span></a>'
                f"</div></body></html>").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Set-Cookie", "sessie=1; Path=/")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def test_blokkade_na_eerste_pagina_wordt_met_verse_sessie_omzeild():
    """Action weert de opgebouwde sessie, niet de URL: goto twee van dezelfde
    context krijgt 403 waar een verse sessie 200 krijgt. De herkansing moet de
    tweede pagina dus alsnog binnenhalen, in een nieuwe context."""
    from playwright.sync_api import sync_playwright
    server = HTTPServer(("127.0.0.1", 0), _SessieWeringHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{server.server_port}"
    try:
        with sync_playwright() as pw:
            browser = _browser(pw)
            sink = _ApiSink()
            context, page = _verse_pagina(browser, sink)

            context, page, html, vers = _load_of_verse_sessie(
                browser, sink, context, page, f"{basis}/categorie-a/")
            assert html is not None and not vers        # eerste bezoek: gewoon open

            context, page, html, vers = _load_of_verse_sessie(
                browser, sink, context, page, f"{basis}/categorie-a/?page=2")
            assert vers                                  # zelfde sessie: geweerd
            assert html is not None                      # verse context: alsnog open
            assert "Artikel" in html
            browser.close()
    finally:
        server.shutdown()


def test_firecrawl_zonder_sleutel_faalt_netjes(monkeypatch):
    """Zonder FIRECRAWL_API_KEY blijft de bron rood met een duidelijke uitleg,
    zonder de weekrun te breken."""
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    from scraper.config import RetailerCfg
    from scraper.http import Http
    from scraper.strategies import firecrawl_api

    cfg = RetailerCfg(id="wibra", name="Wibra", base="https://www.wibra.nl")
    res = firecrawl_api.scrape(cfg, Http(min_delay=0), limit=5)
    assert res.products == []
    assert "FIRECRAWL_API_KEY" in res.error


def test_api_sink_vangt_json_response():
    """De sink haalt producten uit een onderschepte JSON-API-response."""
    sink = _ApiSink()

    class FakeResponse:
        url = "https://shop.nl/api/search?q=ondergoed"
        headers = {"content-type": "application/json; charset=utf-8"}

        def json(self):
            return {"results": [
                {"productId": "X1", "name": "Dames slip 5-pack",
                 "price": {"value": 5.99}, "oldPrice": {"value": 7.99}},
                {"productId": "X2", "name": "Herensokken 7-pack", "price": 6.49},
            ]}

    sink.handle(FakeResponse())
    got = {p.key: p for p in sink.products}
    assert got["X1"].price == 5.99 and got["X1"].was_price == 7.99
    assert got["X2"].price == 6.49

    # niet-JSON of niet-relevante URL's worden genegeerd
    sink.reset()

    class Irrelevant:
        url = "https://shop.nl/static/theme.css"
        headers = {"content-type": "text/css"}

        def json(self):
            raise AssertionError("mag niet worden aangeroepen")

    sink.handle(Irrelevant())
    assert sink.products == []
