from pathlib import Path

from scraper.jsonscan import deep_find_products, products_from_html, url_key

FIXTURE = (Path(__file__).parent / "fixtures" / "listing.html").read_text(encoding="utf-8")
BASE = "https://www.voorbeeldshop.nl/dames"


def test_products_from_html_combineert_jsonld_en_nextdata():
    products = products_from_html(FIXTURE, BASE)
    by_key = {p.key: p for p in products}
    assert set(by_key) == {"123", "456", "789"}

    pyjama = by_key["123"]
    assert pyjama.title == "Dames pyjama flanel"
    assert pyjama.price == 12.99
    assert pyjama.url == "https://www.voorbeeldshop.nl/p/dames-pyjama-123"

    assert pyjama.color == "roze"

    sokken = by_key["789"]
    assert sokken.price == 3.99
    assert sokken.was_price == 5.99
    assert sokken.category_raw == "Kinderen > Sokken"
    assert sokken.color == "blauw"
    assert sokken.sizes == "23-26, 27-30, 31-34"

    # dubbel aanwezig (JSON-LD én __NEXT_DATA__) → één product met prijs
    assert by_key["456"].price == 7.99


def test_deep_find_products_geneste_prijsvelden():
    data = {"resultaten": [{"productId": "x1", "title": "Legging",
                            "prices": {"sellingPrice": "6,99"},
                            "oldPrice": "9,99"}]}
    found = deep_find_products(data, "https://x.nl")
    assert len(found) == 1
    assert found[0].price == 6.99
    assert found[0].was_price == 9.99


def test_url_key_negeert_querystring():
    assert url_key("https://x.nl/p/abc?kleur=rood") == url_key("https://x.nl/p/abc")
    assert url_key("https://x.nl/p/abc/") == url_key("https://x.nl/p/abc")


def test_products_from_js_state_datalayer():
    """Wibra-hypothese: naam en prijs staan alleen in dataLayer.push(...) —
    gewone JS, geen JSON-script. Moet toch gevonden worden."""
    from scraper.jsonscan import products_from_html
    html = """<html><head><script>
      window.x = 1; dataLayer.push({"event":"productDetail","ecommerce":{
        "detail":{"products":[{"name":"Dames hipster 2-pack","id":"W-77",
                               "price":"3.99"}]}}});
    </script></head><body><div id="app"></div></body></html>"""
    prods = products_from_html(html, "https://www.wibra.nl/assortiment/x")
    assert len(prods) == 1
    assert prods[0].title == "Dames hipster 2-pack"
    assert prods[0].price == 3.99


def test_products_from_js_state_initial_state():
    from scraper.jsonscan import products_from_html
    html = """<script>window.__INITIAL_STATE__ = {"product":
      {"name":"Herensok 5-pack","sku":"H1","price":4.49}};</script>"""
    prods = products_from_html(html, "https://voorbeeld.nl/p/h1")
    assert [p.title for p in prods] == ["Herensok 5-pack"]


def test_js_state_slikt_geen_js_expressies():
    """Blokken met echte JS (functies, variabelen) zijn geen JSON en moeten
    stil afvallen, niet crashen of halve producten opleveren."""
    from scraper.jsonscan import products_from_html
    html = """<script>dataLayer.push({event: getEvent(), fn: function(){
      return {name: 'nep', price: 1.00};}});</script>"""
    assert products_from_html(html, "https://voorbeeld.nl") == []


def test_products_from_escaped_attrs_hema_tegel():
    """HEMA-meting 10-08: de tegel draagt zijn productdata als HTML-ge-escapete
    JSON in een attribuut — &quot;price&quot;:&quot;8.69&quot;. Geen script,
    geen dataLayer, geen tekstprijs."""
    from scraper.jsonscan import products_from_html
    html = ('<div class="product-tile" data-gtm="{&quot;name&quot;:'
            '&quot;niet-voorgevormde top zonder beugel&quot;,'
            '&quot;masterSKU&quot;:&quot;HEM2228294&quot;,'
            '&quot;price&quot;:&quot;8.69&quot;,'
            '&quot;stockStatus&quot;:&quot;IN_STOCK&quot;}">'
            '<a href="/dames/lingerie/bh/top"></a></div>')
    prods = products_from_html(html, "https://www.hema.nl/dames/lingerie")
    assert len(prods) == 1
    assert prods[0].title == "niet-voorgevormde top zonder beugel"
    assert prods[0].price == 8.69


def test_escaped_attrs_slikt_kapotte_json_stil():
    from scraper.jsonscan import products_from_html
    html = '<div data-x="{&quot;price&quot;:&quot;8.69&quot;">'   # niet afgesloten
    assert products_from_html(html, "https://www.hema.nl") == []
