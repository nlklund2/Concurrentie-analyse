"""De diagnose is het meetinstrument van het hele project — als die crasht,
vaart iedereen blind. Ronde 4 (10-08) viel volledig uit op een ontbrekende
import in het fc-pad; deze tests draaien beide routes offline door."""
import scraper.strategies.firecrawl_api as fc_api
from scraper import diagnose as dg


def _fc(monkeypatch, html):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    monkeypatch.setattr(fc_api, "_firecrawl_html", lambda *a, **kw: html)


def test_fc_diagnose_gewone_pagina(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)      # de HTML-dump belandt in de werkmap
    _fc(monkeypatch, "<html><body><a href='/p/x'>X</a> 4,99</body></html>")
    md = dg.diagnose("fc:https://www.hema.nl/dames/lingerie")
    assert "signalen:" in md and "kaartlezer" in md
    assert (tmp_path / "diagnose-dump-www.hema.nl.html").exists()


def test_fc_diagnose_json_endpoint(monkeypatch):
    _fc(monkeypatch, '[{"id":4227293,"name":"BH met kant",'
                     '"permalink":"https://x.nl/p/1",'
                     '"prices":{"price":"599","currency_minor_unit":2}}]')
    md = dg.diagnose("fc:https://www.wibra.nl/wp-json/wc/store/v1/products?per_page=1")
    assert "geldige JSON" in md and "producten via deep_find: 1" in md


def test_rapport_overleeft_een_kapotte_url(monkeypatch):
    def knal(*a, **kw):
        raise RuntimeError("kapot")
    monkeypatch.setattr(dg, "diagnose", knal)
    md = dg.diagnose_rapport(["https://voorbeeld.nl/a", "https://voorbeeld.nl/b"])
    assert md.count("diagnosefout") == 2
