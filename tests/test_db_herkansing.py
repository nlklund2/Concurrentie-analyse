"""Een netwerkhapering mag een bron geen hele week kosten.

In week 32 verloor C&A 28 al gescrapete artikelen aan één read-timeout van
60 s richting Supabase; de bron viel daardoor terug op data van een week eerder.
"""
import pytest
import requests

from scraper.db import Db, DbError


class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self.text = "" if status < 400 else f"fout {status}"
        self._payload = payload if payload is not None else []
        self.headers = {}

    def json(self):
        return self._payload


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-sleutel")
    monkeypatch.setattr("scraper.db.time.sleep", lambda _s: None)  # geen wachttijd
    return Db()


def _neproeper(uitkomsten):
    """Elke aanroep levert de volgende uitkomst; exceptions worden opgeworpen."""
    pogingen = []

    def roep(method, url, **kw):
        pogingen.append((method, url))
        uit = uitkomsten[len(pogingen) - 1]
        if isinstance(uit, Exception):
            raise uit
        return uit

    roep.pogingen = pogingen
    return roep


def test_timeout_wordt_herkanst(db, monkeypatch):
    roep = _neproeper([requests.Timeout("read timed out"), _Resp(200, [{"a": 1}])])
    monkeypatch.setattr(db.session, "request", roep)
    assert db.process_week("c-and-a", __import__("datetime").date(2026, 8, 3)) == [{"a": 1}]
    assert len(roep.pogingen) == 2


def test_5xx_wordt_herkanst_4xx_niet(db, monkeypatch):
    roep = _neproeper([_Resp(503), _Resp(200, [])])
    monkeypatch.setattr(db.session, "request", roep)
    db._req("GET", "products", timeout=1)
    assert len(roep.pogingen) == 2

    roep = _neproeper([_Resp(404)])
    monkeypatch.setattr(db.session, "request", roep)
    with pytest.raises(DbError):
        db._req("GET", "products", timeout=1)
    assert len(roep.pogingen) == 1      # een echte fout meteen naar boven


def test_opgeven_na_alle_pogingen(db, monkeypatch):
    roep = _neproeper([requests.ConnectionError("weg")] * Db.POGINGEN)
    monkeypatch.setattr(db.session, "request", roep)
    with pytest.raises(DbError, match="pogingen"):
        db._req("GET", "products", timeout=1)
    assert len(roep.pogingen) == Db.POGINGEN


def test_staging_herkanst_vanaf_de_delete(db, monkeypatch):
    """Een half geslaagde insert opnieuw proberen zou dubbele sleutels in
    staging achterlaten; de herkansing moet dus weer bij de delete beginnen."""
    roep = _neproeper([_Resp(200),                       # delete
                       requests.Timeout("weg"),          # insert mislukt
                       _Resp(200), _Resp(200)])          # delete + insert opnieuw
    monkeypatch.setattr(db.session, "request", roep)
    db.replace_staging("c-and-a", [{"product_key": "x"}])
    assert [m for m, _ in roep.pogingen] == ["DELETE", "POST", "DELETE", "POST"]
