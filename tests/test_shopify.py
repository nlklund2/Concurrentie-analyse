from scraper.strategies.shopify import product_from_item

ITEM = {
    "id": 987654,
    "title": "Dames hipsters 3-pack",
    "handle": "dames-hipsters-3-pack",
    "vendor": "Voorbeeldshop",
    "product_type": "Ondergoed",
    "tags": ["dames", "basics"],
    "options": [
        {"name": "Maat", "values": ["S", "M", "L", "XL"]},
        {"name": "Kleur", "values": ["zwart", "wit"]},
    ],
    "variants": [
        {"price": "7.99", "compare_at_price": None},
        {"price": "6.99", "compare_at_price": "9.99"},
    ],
}


def test_product_from_item_opties_en_laagste_variantprijs():
    p = product_from_item(ITEM, "https://shop.voorbeeld.nl")
    assert p.key == "987654"
    assert p.price == 6.99                 # laagste variantprijs
    assert p.was_price == 9.99             # bijbehorende doorstreepte prijs
    assert p.sizes == "S, M, L, XL"
    assert p.color == "zwart, wit"
    assert p.url == "https://shop.voorbeeld.nl/products/dames-hipsters-3-pack"
    assert "Ondergoed" in p.category_raw and "dames" in p.category_raw
