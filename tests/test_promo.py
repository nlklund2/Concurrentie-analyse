"""Stap A promotievormen: ruwe promotekst vangen en doorgeven — niets
interpreteren. Zie docs/promotievormen-onderzoek.md."""
from scraper.jsonscan import deep_find_products, products_from_html
from scraper.models import Product
from scraper.normalize import to_staging_rows
from scraper.promo import promo_fragmenten, promo_uit_html
from scraper.strategies.render_listing import cards_from_html


def test_multibuy_en_percentages_worden_herkend():
    assert promo_fragmenten("Boxershorts 2 voor € 7,50") == "2 voor € 7,50"
    assert promo_fragmenten("Sokken 3 voor 10") == "3 voor 10"
    assert promo_fragmenten("1+1 gratis op alle slips") == "1+1 gratis"
    assert promo_fragmenten("2e artikel halve prijs") == "2e artikel halve prijs"
    assert promo_fragmenten("Tweede voor de halve prijs") == "Tweede voor de halve prijs"
    assert promo_fragmenten("2e artikel 50%") == "2e artikel 50%"
    assert promo_fragmenten("Pyjama -30% € 9,99") == "-30%"
    assert promo_fragmenten("tot 50% korting") == "tot 50% korting"
    assert promo_fragmenten("3 halen 2 betalen") == "3 halen 2 betalen"
    assert promo_fragmenten("Opruiming! Nu € 2,00") == "Opruiming"


def test_geen_promo_bij_prijsvormen_maten_en_samenstelling():
    # per-stuk-notatie is een prijsvorm, geen promotie (Action-kaarten)
    assert promo_fragmenten("ZIKI boxershorts € 2,48/st") == ""
    assert promo_fragmenten("Maten 40 - 42 € 0,84/st") == ""
    # samenstelling en 'nieuw' zijn geen acties
    assert promo_fragmenten("95% katoen - 5% elastaan") == ""
    assert promo_fragmenten("100% katoen") == ""
    assert promo_fragmenten("Nieuw! Sale-collectie") == ""
    # was/voor is geen multibuy: '99 voor € 9,99' mag niet uit 14,99 komen
    assert promo_fragmenten("van € 14,99 voor € 9,99") == ""
    assert promo_fragmenten("Van 17,99 € voor 9,99 €") == ""
    assert promo_fragmenten("nu 2 voor € 5") == "2 voor € 5"
    assert promo_fragmenten("") == "" and promo_fragmenten(None) == ""


def test_fragmenten_ontdubbeld_en_afgekapt():
    tekst = "2 voor € 5 · 2 VOOR € 5 · -20% " + "x" * 300 + " 1+1 gratis"
    uit = promo_fragmenten(tekst)
    assert uit.startswith("2 voor € 5 · -20% · 1+1 gratis")
    assert len(promo_fragmenten("-10% " * 100)) <= 120


def test_kaartlezer_vangt_de_badge_naast_de_prijs():
    html = ('<div class="kaart"><span class="badge">2 voor € 7,50</span>'
            '<a href="/p/123/boxer"><img alt="Boxershorts 3-pack"></a>'
            '<span>€ 4,95</span></div>')
    prods = cards_from_html(html, "https://shop.nl/heren")
    assert len(prods) == 1
    assert prods[0].price == 4.95 and prods[0].promo_text == "2 voor € 7,50"
    # de bundelprijs is géén doorstreepprijs: zonder deze regel telde het
    # artikel als afgeprijsd van € 7,50 naar € 4,95
    assert prods[0].was_price is None


def test_json_badgevelden_gaan_door_de_promofilter():
    data = {"items": [
        {"name": "Hipster", "sku": "H1", "price": "3.99", "badges": ["1+1 gratis", "Nieuw"]},
        {"name": "Slip", "sku": "S1", "price": "2.99", "promotion": {"text": "2e halve prijs"}},
        {"name": "Sok", "sku": "K1", "price": "1.99", "labels": ["Nieuw"]},
    ]}
    by_key = {p.key: p for p in deep_find_products(data, "https://x.nl")}
    assert by_key["H1"].promo_text == "1+1 gratis"      # 'Nieuw' valt eerlijk weg
    assert by_key["S1"].promo_text == "2e halve prijs"
    assert by_key["K1"].promo_text == ""


def test_hema_tegel_badge_uit_de_omliggende_html():
    html = ('<div class="product-tile" data-gtm="{&quot;name&quot;:'
            '&quot;hipsters katoen&quot;,&quot;masterSKU&quot;:&quot;HEM1111111&quot;,'
            '&quot;price&quot;:&quot;6.00&quot;}">'
            '<a href="/dames/slips/hipster"></a><span class="sticker">2e artikel 50%</span>'
            '<script>var x = "-99%";</script></div>')
    prods = products_from_html(html, "https://www.hema.nl")
    assert prods[0].promo_text == "2e artikel 50%"      # scriptinhoud telt niet mee
    assert promo_uit_html("<b>1+1</b> gratis &amp; meer") == "1+1 gratis"


def test_promotekst_naar_stagingrij_en_dedupe():
    rows = to_staging_rows("kik", [
        Product(key="a", title="Sokken 5 paar", price=2.99, promo_text=""),
        Product(key="a", title="Sokken 5 paar", price=2.99, promo_text="2 voor € 5"),
        Product(key="b", title="Slip", price=1.99, promo_text="x" * 200),
    ])
    by_key = {r["product_key"]: r for r in rows}
    assert by_key["a"]["promo_text"] == "2 voor € 5"   # lege waarneming aangevuld
    assert len(by_key["b"]["promo_text"]) == 120


def test_omnibusregel_is_geen_promotie():
    """KiK zet onder elke afgeprijsde kaart de wettelijke omnibusregel ('30
    dagen beste prijs: € 3,99 (-25%)'). Dat is prijshistorie, geen actie:
    alleen de echte badge '-67%' telt."""
    kaart = ("-67% Alleen online Super push-up bh + string Janina, 2-delige set "
             "€ 8,99 €299 30 dagen beste prijs1: € 3,99 (-25%)")
    assert promo_fragmenten(kaart) == "-67%"
    assert promo_fragmenten("Hemdje met spaghettibandjes Ergee, Naadloos €499") == ""
    assert promo_fragmenten("€299 30 dagen laagste prijs: € 3,99 (-25%)") == ""
