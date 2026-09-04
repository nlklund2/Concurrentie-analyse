"""Verpakkingsgrootte uit de stukprijs op de kaart (KiK, Action).

KiK zet de pack-grootte niet in de artikelnaam ("Slips met haaien") maar
wél als "(0,66 € / Stuk)" op de kaart; sinds de herstelde prijslezer (4-09)
draagt zo'n kaart de pakprijs, en zonder deze afleiding stond een 3-pack
voor €1,99 als één stuk in de per-stuk-index.
"""
from scraper.models import Product
from scraper.normalize import to_staging_rows
from scraper.strategies.render_listing import _pak_uit_stukprijs, cards_from_html


def test_pakgrootte_uit_stukprijs():
    assert _pak_uit_stukprijs(8.99, "Nieuw BH push-up + string Janina, Set van 2 stuks €899 (4,50 € / Stuk)") == 2
    assert _pak_uit_stukprijs(5.99, "Hipsters luipaardprint 2 stuks, Janina €599 (3 € / Stuk)") == 2
    assert _pak_uit_stukprijs(1.99, "Slips met haaien 3 stuks €199 (0,66 € / Stuk)") == 3
    assert _pak_uit_stukprijs(4.99, "Sneakersokken 6 paar €499 (0,83 € / Stuk)") == 6
    # Action: stukprijs direct achter het bedrag
    assert _pak_uit_stukprijs(4.95, "Sokken € 4,95 € 2,48/st") == 2
    # afgeprijsde kaart: de stukprijs hoort bij de actieprijs, niet bij de was-prijs
    assert _pak_uit_stukprijs(2.99, "-67% Super push-up bh + string, 2-delige set € 8,99 €299 "
                                    "30 dagen beste prijs: € 3,99 (-25%) (1,50 € / Stuk)") == 2


def test_geen_pakgrootte_zonder_passende_stukprijs():
    assert _pak_uit_stukprijs(4.99, "Hemdje met spaghettibandjes €499") == 0
    # los artikel: stukprijs = prijs
    assert _pak_uit_stukprijs(2.48, "€ 2,48/st") == 0
    # geen geheel aantal → geen verzonnen pack
    assert _pak_uit_stukprijs(4.95, "€ 4,95 € 1,90/st") == 0
    # boven de 12 is het geen verpakking
    assert _pak_uit_stukprijs(9.99, "€ 9,99 € 0,50/st") == 0
    assert _pak_uit_stukprijs(None, "€ 4,95 € 2,48/st") == 0


def test_staging_neemt_kaarthint_als_de_titel_zwijgt():
    rows = to_staging_rows("kik", [
        Product(key="a", title="Slips met haaien", price=1.99, pack_hint=3),
        Product(key="b", title="Sokken 5 paar", price=4.99, pack_hint=2),   # titel gaat voor
        Product(key="c", title="Hemdje", price=4.99),
    ])
    per_key = {r["product_key"]: r["pack_size"] for r in rows}
    assert per_key == {"a": 3, "b": 5, "c": 1}
    # bij dubbele waarnemingen wint de rij mét pack-grootte
    rows = to_staging_rows("kik", [
        Product(key="a", title="Slips met haaien", price=1.99),
        Product(key="a", title="Slips met haaien", price=1.99, pack_hint=3),
    ])
    assert rows[0]["pack_size"] == 3


def test_kaartlezer_geeft_de_hint_mee():
    html = """<html><body>
      <a href="/p/slips-met-haaien/12345"><img alt="Slips met haaien">
        <p>Slips met haaien 3 stuks, Ergee</p><p>€ 1,99</p><p>(0,66 € / Stuk)</p></a>
    </body></html>"""
    kaarten = cards_from_html(html, "https://www.kik.nl/c/dames")
    assert len(kaarten) == 1
    assert kaarten[0].price == 1.99 and kaarten[0].pack_hint == 3
