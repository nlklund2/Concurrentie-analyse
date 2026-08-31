"""Sjabloon-breadcrumbdetectie: W36 zette terstal.nl na een sitevernieuwing
op élke productpagina dezelfde breadcrumb ('kinderen > jongens > nachtmode >
onesies'), waardoor 687 artikelen — beha's incluis — als jongens/nachtmode de
week in gingen. Een breadcrumb die overal identiek is, is geen artikelinfo."""
import scraper.strategies.sitemap_pages as sp
from scraper import discover
from scraper.config import RetailerCfg


def _pagina(naam: str, sku: str, kruimel: str) -> str:
    # Zoals terStal na de sitevernieuwing: het kruimelpad eindigt op het
    # artikel zelf, waardoor elke pagina nét een andere breadcrumb lijkt te
    # hebben terwijl de categorielaag ervóór overal identiek is.
    items = [f'{{"@type":"ListItem","position":{i},"item":{{"@id":"https://voorbeeld.nl/{i}","name":"{n}"}}}}'
             for i, n in enumerate(kruimel.split(" > ") + [naam], 1)]
    return f'''<html><head>
      <script type="application/ld+json">{{"@context":"http://schema.org",
        "@type":"Product","name":"{naam}","sku":"{sku}",
        "url":"https://voorbeeld.nl/{sku}.html",
        "offers":{{"price":"7.99","priceCurrency":"EUR"}}}}</script>
      <script type="application/ld+json">{{"@context":"http://schema.org",
        "@type":"BreadcrumbList","itemListElement":[{",".join(items)}]}}</script>
      </head><body></body></html>'''


class _Resp:
    status_code = 200
    def __init__(self, text): self.text = text


class _Http:
    def __init__(self, paginas): self.paginas = paginas
    def get(self, url): return _Resp(self.paginas[url])


def _cfg():
    return RetailerCfg(id="test", name="Test", base="https://voorbeeld.nl",
                       strategy="sitemap_pages")


def _draai(monkeypatch, paginas):
    urls = list(paginas)
    monkeypatch.setattr(discover, "find_sitemaps", lambda http, base: ["sm"])
    monkeypatch.setattr(discover, "sitemap_urls", lambda http, sm, f: urls)
    monkeypatch.setattr(discover, "split_product_category_urls",
                        lambda us: (us, []))
    return sp.scrape(_cfg(), _Http(paginas), limit=len(urls))


def test_identieke_breadcrumb_wordt_genegeerd(monkeypatch):
    paginas = {f"https://voorbeeld.nl/artikel-{i}.html":
               _pagina(f"Artikel {i}", f"artikel-{i}", "jongens nachtmode")
               for i in range(10)}
    res = _draai(monkeypatch, paginas)
    assert len(res.products) == 10
    assert all("jongens" not in (p.category_raw or "") for p in res.products)
    assert any("breadcrumb genegeerd" in n for n in res.notes)


def test_wisselende_breadcrumbs_blijven_staan(monkeypatch):
    paginas = {f"https://voorbeeld.nl/artikel-{i}.html":
               _pagina(f"Artikel {i}", f"artikel-{i}", f"afdeling-{i}")
               for i in range(10)}
    res = _draai(monkeypatch, paginas)
    assert len(res.products) == 10
    assert all(f"afdeling-{i}" in res.products[i].category_raw for i in range(10))
    assert not any("breadcrumb genegeerd" in n for n in res.notes)
