"""Render-strategie: alleen uitvoerbaar waar Playwright + Chromium aanwezig zijn
(lokaal en in de scrape-/validatieworkflows); in de kale CI wordt dit overgeslagen."""
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from scraper.jsonscan import products_from_html
from scraper.strategies.render_listing import _dom_products, _load

FIXTURE = (Path(__file__).parent / "fixtures" / "render-listing.html").resolve()


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
