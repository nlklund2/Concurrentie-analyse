from scraper.models import Product
from scraper.normalize import apply_focus, map_category, parse_price, to_staging_rows


def test_parse_price_formats():
    assert parse_price("€ 4,99") == 4.99
    assert parse_price("4.99") == 4.99
    assert parse_price("1.299,95") == 1299.95
    assert parse_price("5,-") == 5.0
    assert parse_price("vanaf € 3,99") == 3.99
    assert parse_price(12.99) == 12.99
    assert parse_price(1299) == 12.99            # centen-integer
    assert parse_price(250) == 250.0             # gewone euro-integer
    assert parse_price(250, key_hint="priceInCents") == 2.5
    assert parse_price(None) is None
    assert parse_price("") is None
    assert parse_price(0) is None
    assert parse_price("gratis") is None


def test_map_category_bronpad_wint():
    assert map_category("Dames > Nachtmode > Pyjama's") == ("dames", "nachtmode")
    assert map_category("meisjes/sokken-maillots") == ("meisjes", "sokken & panty's")
    assert map_category("Huishoudtextiel", title="Handdoek 50x100") == ("huis", "huistextiel")


def test_map_category_titel_als_vangnet():
    assert map_category("", title="Jongens boxershorts 3-pack") == ("jongens", "ondergoed")
    assert map_category("", title="Baby romper 2-pack") == ("baby", "overig")
    assert map_category("volstrekt-onduidelijk") == ("onbekend", "overig")


def test_boxershort_is_ondergoed_geen_broek():
    _, ptype = map_category("heren/boxershorts")
    assert ptype == "ondergoed"


def test_pyjama_in_ondergoedpad_is_nachtmode():
    # gevalideerd op Primark: pyjama's hangen onder "lingerie & ondergoed"
    _, ptype = map_category("dames/lingerie-en-ondergoed",
                            title="Korte pyjama met print")
    assert ptype == "nachtmode"
    # maar een gewone slip in datzelfde pad blijft ondergoed
    _, ptype = map_category("dames/lingerie-en-ondergoed", title="Slips 5-pack")
    assert ptype == "ondergoed"


def test_apply_focus_ondergoedmode():
    rows = to_staging_rows("test", [
        Product(key="1", title="Dames hipsters 2-pack", category_raw="dames/ondergoed", price=4.99),
        Product(key="2", title="Meisjes pyjama", category_raw="meisjes/nachtmode", price=7.99),
        Product(key="3", title="Herensokken 5-pack", category_raw="heren/sokken", price=3.99),
        Product(key="4", title="Dames spijkerbroek", category_raw="dames/broeken", price=19.99),
    ])
    focus = ["ondergoed", "nachtmode", "sokken & panty's"]
    binnen = apply_focus(rows, focus)
    assert {r["product_key"] for r in binnen} == {"1", "2", "3"}
    assert apply_focus(rows, []) == rows  # lege focus = alles


def test_to_staging_rows_dedupe_en_schoonmaak():
    ps = [
        Product(key="a", title="Shirt", price=None),
        Product(key="a", title="Shirt", price=4.99),
        Product(key="b", title="Broek", price=9.99, was_price=5.0),   # was < prijs → ongeldig
        Product(key="", title="Zonder sleutel", price=1.0),           # valt af
    ]
    rows = to_staging_rows("test", ps)
    by_key = {r["product_key"]: r for r in rows}
    assert set(by_key) == {"a", "b"}
    assert by_key["a"]["price"] == 4.99
    assert by_key["b"]["was_price"] is None


def test_to_staging_rows_kleur_maten_en_samenvoegen():
    ps = [
        Product(key="a", title="Boxers", price=4.99, color="zwart"),
        Product(key="a", title="Boxers", price=4.99, sizes="S, M, L"),  # maten winnen
        Product(key="b", title="Sokken", price=2.99, color="wit", sizes="39-42"),
    ]
    rows = to_staging_rows("test", ps)
    by_key = {r["product_key"]: r for r in rows}
    assert by_key["a"]["sizes"] == "S, M, L"
    assert by_key["a"]["color"] == "zwart"      # aangevuld vanuit de andere rij
    assert by_key["b"]["color"] == "wit"
    assert by_key["b"]["sizes"] == "39-42"
