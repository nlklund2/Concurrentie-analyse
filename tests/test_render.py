"""Render-strategie: alleen uitvoerbaar waar Playwright + Chromium aanwezig zijn
(lokaal en in de scrape-/validatieworkflows); in de kale CI wordt dit overgeslagen."""
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from scraper.jsonscan import products_from_html
from scraper.strategies.render_listing import _ApiSink, _dom_products, _load

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
