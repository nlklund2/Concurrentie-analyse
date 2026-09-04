"""Next.js App Router: producten in de flight-payload (self.__next_f.push).

Zeeman-scenario (04-09-2026): de categoriepagina draagt 30 producten mét
prijs in centen, maar niet in JSON-LD, __NEXT_DATA__ of de tekst. Tot deze
extractor stond Zeeman daardoor vijf weken ten onrechte rood."""
import json

import scraper.strategies.listing_crawl as lc
from scraper.__main__ import _beoordeel
from scraper.config import RetailerCfg
from scraper.jsonscan import flight_meta, flight_payload, products_from_html

BASE = "https://www.zeeman.com/nl-nl/dames/ondergoed"


def _item(naam, variant, centen, *, regulier=None, pak=None, maten=("S", "M"),
          voorraad="IN_STOCK", linten=(), promolinten=(), cat=("Dames", "Ondergoed", "Slips")):
    ouders = [{"name": n, "storyblokName": None} for n in reversed(cat[:-1])]
    attrs = [{"name": "variantId", "value": variant}, {"name": "ean", "value": "8720877000000"}]
    if pak:
        attrs.append({"name": "packSize", "value": str(pak)})
    pv = {"availability": voorraad, "id": "1", "sku": f"{variant}-1", "attributes": attrs,
          "price": {"gross": {"centAmount": centen, "currency": "EUR"}}}
    if regulier:
        pv["regularPrice"] = {"gross": {"centAmount": regulier, "currency": "EUR"}}
    return {"name": naam, "slug": f"{naam.lower().replace(' - ', '-').replace(' ', '-')}-{variant}",
            "packSize": pak, "availability": voorraad, "assortmentType": "OFFLINE_ONLINE",
            "primaryCategory": {"ancestors": ouders, "id": "c1", "name": cat[-1]},
            "primaryVariant": pv,
            "variants": [{"attributes": [{"name": "size", "value": m}], "sku": f"{variant}-{i}"}
                         for i, m in enumerate(maten, 1)],
            "marketingRibbons": [{"color": "blue", "kind": k, "label": l} for k, l in linten],
            "promotionRibbons": [{"kind": "promotion", "label": l} for l in promolinten]}


def _pagina(items, total=None, pages=1, page=1):
    """Zoals Next.js de stroom serialiseert: JS-stringliterals in losse
    push-blokken, met de lijstdata als JSON mét ge-escapete aanhalingstekens."""
    lijst = {"results": items, "total": total if total is not None else len(items),
             "totalPages": pages}
    state = {"filterState": {"pageSize": 30, "page": page, "categoryPageId": "dames > ondergoed"}}
    compact = dict(ensure_ascii=False, separators=(",", ":"))
    stroom = ('0:["$","$L1",null,{"children":["$","div",null,{"data":'
              + json.dumps(lijst, **compact) + "," + json.dumps(state, **compact)[1:] + "}]}]\n")
    # in tweeën knippen: de lijst loopt over de blokgrens heen
    knip = len(stroom) // 2
    blokken = [json.dumps(stroom[:knip], ensure_ascii=False), json.dumps(stroom[knip:], ensure_ascii=False)]
    scripts = "".join(f"<script>self.__next_f.push([1,{b}])</script>" for b in blokken)
    return ('<html><head><script type="application/ld+json">{"@type":"WebPage","name":"x"}</script>'
            '</head><body><div>9<span class="invisible">.</span>99</div>' + scripts + "</body></html>")


ITEMS = [
    _item("Boxer - Blauw", "124200-1", 469, pak=2),
    _item("Cara Hipster - Blauw", "123806-1", 399, pak=3, linten=(("from-folder", "Uit onze folder"),)),
    _item("Demi Padded BH - Beige", "124067-1", 999, regulier=1299, pak=2,
          maten=("80D", "85D"), cat=("Dames", "Ondergoed", "BH's"),
          linten=(("web-only", "Web-Only"),)),
    _item("Pyjama - Grijs", "112282-1", 1299, voorraad="OUT_OF_STOCK",
          cat=("Kind", "Nachtkleding", "Pyjama's"), promolinten=("2 voor € 20",)),
]


def test_flight_payload_plakt_blokken_aaneen():
    html = _pagina(ITEMS)
    stroom = flight_payload(html)
    assert stroom.startswith('0:["$","$L1"')
    assert '"results":[' in stroom
    assert flight_meta(html) == {"total": 4, "totalPages": 1}


def test_producten_uit_de_flightstroom():
    by_key = {p.key: p for p in products_from_html(_pagina(ITEMS), BASE)}
    assert set(by_key) == {"124200-1", "123806-1", "124067-1", "112282-1"}

    boxer = by_key["124200-1"]
    assert boxer.title == "Boxer - Blauw"
    assert boxer.price == 4.69 and boxer.was_price is None
    assert boxer.pack_hint == 2
    assert boxer.category_raw == "Dames > Ondergoed > Slips"
    assert boxer.color == "Blauw"
    assert boxer.sizes == "S, M"
    assert boxer.in_stock is True
    assert boxer.url == "https://www.zeeman.com/nl-nl/product/boxer-blauw-124200-1"

    bh = by_key["124067-1"]
    assert bh.price == 9.99 and bh.was_price == 12.99
    assert bh.sizes == "80D, 85D"
    assert bh.promo_text == ""            # 'Web-Only' is geen promotie

    assert by_key["123806-1"].promo_text == "Uit onze folder"
    pyjama = by_key["112282-1"]
    assert pyjama.in_stock is False
    assert pyjama.promo_text == "2 voor € 20"
    assert pyjama.category_raw == "Kind > Nachtkleding > Pyjama's"


def test_regulier_gelijk_aan_prijs_is_geen_vanprijs():
    item = _item("Slip - Wit", "1-1", 399, regulier=399)
    (p,) = products_from_html(_pagina([item]), BASE)
    assert p.price == 3.99 and p.was_price is None


def test_zonder_flight_verandert_er_niets():
    html = '<html><body><script>self.__x = 1</script></body></html>'
    assert flight_payload(html) == ""
    assert products_from_html(html, BASE) == []
    assert flight_meta(html) == {}


# ---- listing_crawl: teller stuurt de paginering en de dekking -------------

class _Resp:
    status_code = 200
    def __init__(self, text): self.text = text


class _Http:
    def __init__(self, paginas):
        self.paginas, self.opgehaald = paginas, []
    def get(self, url):
        self.opgehaald.append(url)
        return _Resp(self.paginas[url]) if url in self.paginas else None


def _cfg(**kw):
    return RetailerCfg(id="zeeman", name="Zeeman", base="https://www.zeeman.com/nl-nl",
                       strategy="listing", seeds=[BASE], **kw)


def test_listing_stopt_bij_de_laatste_pagina_en_meet_de_dekking():
    p1 = [_item(f"Slip {i} - Wit", f"10-{i}", 399) for i in range(3)]
    p2 = [_item(f"Slip {i} - Zwart", f"20-{i}", 399) for i in range(2)]
    paginas = {BASE: _pagina(p1, total=5, pages=2),
               BASE + "?page=2": _pagina(p2, total=5, pages=2, page=2),
               BASE + "?page=3": _pagina(p2, total=5, pages=2, page=3)}   # mag nooit gevraagd worden
    http = _Http(paginas)
    res = lc.scrape(_cfg(), http)
    assert len(res.products) == 5
    assert BASE + "?page=3" not in http.opgehaald
    assert res.coverage == {"nl-nl > dames > ondergoed": (5, 5)}
    assert any(n.startswith("tellercontrole: 5 van 5") for n in res.notes)
    assert all(p.category_raw.startswith("nl-nl > dames > ondergoed") for p in res.products)


def test_listing_eenpagina_vraagt_geen_tweede_pagina():
    http = _Http({BASE: _pagina(ITEMS, total=4, pages=1)})
    res = lc.scrape(_cfg(), http)
    assert len(res.products) == 4
    assert http.opgehaald == [BASE]


class _Db:
    def last_ok_count(self, rid): return 0


def test_kwaliteitspoort_keurt_tekort_op_de_teller_af():
    cfg = _cfg(min_products_expected=3)
    rows = [{"product_key": str(i)} for i in range(200)]
    assert _beoordeel(_Db(), cfg, rows, "", coverage={"a": (200, 200)})[0] == "ok"
    assert _beoordeel(_Db(), cfg, rows, "", coverage={"a": (190, 200)})[0] == "ok"    # 95%: net goed
    status, note = _beoordeel(_Db(), cfg, rows, "", coverage={"a": (150, 200), "b": (30, 30)})
    assert status == "afwijkend"
    assert "180 van 230" in note and "a 150/200" in note and "b" not in note.split("tekort in:")[1]
    # zonder teller (andere bronnen) verandert er niets aan de poort
    assert _beoordeel(_Db(), cfg, rows, "", coverage=None)[0] == "ok"
