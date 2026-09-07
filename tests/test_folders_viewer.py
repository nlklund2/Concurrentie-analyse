"""Viewerdetectie en geldigheidsdatums — zonder netwerk, op HTML-fragmenten."""
from datetime import date

from folders.viewer import detect, geldigheid, tekst, tel_paginas, titel, urls_in

BASE = "https://www.voorbeeld.nl/folder"


def test_pdf_link_wint():
    html = '<a href="/media/folder-week-37.pdf?x=1">Download</a><iframe src="https://view.publitas.com/x/y"></iframe>'
    info = detect(html, BASE)
    assert info.kind == "pdf"
    assert info.url == "https://www.voorbeeld.nl/media/folder-week-37.pdf?x=1"


def test_publitas_iframe():
    html = '<iframe src="https://view.publitas.com/zeeman/folder-37/"></iframe>'
    info = detect(html, BASE)
    assert info.kind == "publitas" and info.url.startswith("https://view.publitas.com/")


def test_ipaper_link_relatief_en_absoluut():
    html = '<a data-href="https://viewer.ipaper.io/wibra/folder-36/">Bekijk</a>'
    assert detect(html, BASE).kind == "ipaper"


def test_extern_platform():
    html = '<a href="https://www.flipsnack.com/kik/folder">folder</a>'
    info = detect(html, BASE)
    assert info.kind == "extern" and info.platform == "flipsnack"


def test_paginabeelden_op_eigen_pagina():
    html = "".join(f'<img src="/cdn/folder/page-{n}.jpg">' for n in range(1, 6))
    info = detect(html, BASE)
    assert info.kind == "pages" and info.page_hints == 5


def test_render_als_niets_herkend():
    html = "<html><body><div id='app'></div><script src='/app.js'></script></body></html>"
    assert detect(html, BASE).kind == "render"


def test_platform_alleen_genoemd():
    html = "<script>window.viewer='publitas';</script>"
    info = detect(html, BASE)
    assert info.kind == "publitas" and info.url == ""


def test_urls_in_ontdubbelt_en_negeert_rommel():
    html = '<a href="#top"></a><a href="mailto:x@y"></a><a href="/a"></a><a href="/a"></a>'
    assert urls_in(html, BASE) == ["https://www.voorbeeld.nl/a"]


def test_tel_paginas_en_titel():
    html = "<title> Folder &amp; acties </title><div data-page='12'></div><span>pagina 24</span>"
    assert tel_paginas(html) == 24
    assert titel(html) == "Folder & acties"
    assert "Folder" in tekst(html)


# ---- geldigheid ----
VANDAAG = date(2026, 9, 5)


def test_geldigheid_tekstueel_zelfde_maand():
    assert geldigheid("Geldig van 9 t/m 15 september", VANDAAG) == (date(2026, 9, 9), date(2026, 9, 15))


def test_geldigheid_tekstueel_maandgrens():
    assert geldigheid("31 augustus t/m 13 september 2026", VANDAAG) == (date(2026, 8, 31), date(2026, 9, 13))


def test_geldigheid_numeriek():
    assert geldigheid("Folder 02-09 t/m 08-09", VANDAAG) == (date(2026, 9, 2), date(2026, 9, 8))
    assert geldigheid("02-09-2026 t/m 08-09-2026", VANDAAG) == (date(2026, 9, 2), date(2026, 9, 8))


def test_geldigheid_jaarwissel():
    assert geldigheid("29 december t/m 4 januari", date(2026, 12, 20)) == (date(2026, 12, 29), date(2027, 1, 4))


def test_geldigheid_verwerpt_seizoen_en_ruis():
    assert geldigheid("1 maart t/m 31 augustus", VANDAAG) is None
    assert geldigheid("maten 92 t/m 164", VANDAAG) is None
    assert geldigheid("", VANDAAG) is None
