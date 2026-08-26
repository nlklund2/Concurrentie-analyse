"""Multipacks: "3 stuks €12,99" is geen €12,99-artikel.

De pack-grootte komt uit de artikelnaam en bepaalt de prijs-per-stuk-index
(PLAN.md §11.1). Een verzonnen pack is schadelijker dan een gemiste: die
halveert stilletjes de prijs van een concurrent in de index. Deze test legt
daarom vooral vast wat géén multipack is.
"""
from scraper.models import Product
from scraper.normalize import pack_size, to_staging_rows, unit_price


def test_gewone_multipackvormen():
    assert pack_size("kinderboxers katoen - 3 stuks blauw") == 3
    assert pack_size("kinder enkelsokken mesh - 5 paar geel") == 5
    assert pack_size("damesslip 2-pack") == 2
    assert pack_size("3er Pack herensokken") == 3
    assert pack_size("set van 2 pyjama's") == 2
    assert pack_size("voordeelpak 4 boxershorts") == 4
    assert pack_size("onesie 2 st.") == 2


def test_wat_geen_multipack_is():
    # tweedelige pyjamaset = één artikel van twee kledingstukken, geen 2 stuks
    assert pack_size("2-delige pyjamaset meisjes") == 1
    assert pack_size("slaappak 2 jaar") == 1        # leeftijdsmaat
    assert pack_size("sokken maat 39-42") == 1
    assert pack_size("herensokken 24 paar") == 1    # boven PACK_MAX: vrijwel altijd een maat
    assert pack_size("basic bh") == 1
    assert pack_size("") == 1
    assert pack_size(None) == 1


def test_prijs_per_stuk():
    assert unit_price(12.99, 3) == 4.33
    assert unit_price(7.69, 5) == 1.54
    assert unit_price(4.99, 1) == 4.99
    assert unit_price(None, 3) is None
    assert unit_price(4.99, 0) is None              # nooit delen door nul


def test_staging_rij_draagt_de_packgrootte():
    rows = to_staging_rows("hema", [
        Product(key="a1", title="kinderboxers katoen - 3 stuks", price=12.99,
                category_raw="kinderen/ondergoed"),
        Product(key="a2", title="damesslip", price=4.99, category_raw="dames/ondergoed"),
    ])
    packs = {r["product_key"]: r["pack_size"] for r in rows}
    assert packs == {"a1": 3, "a2": 1}
