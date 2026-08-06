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
