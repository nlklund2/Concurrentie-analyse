"""De weekmail zonder database en zonder Resend: model, HTML, platte tekst, bestanden.

FakeDb levert drie meetweken; de mail moet dan een onderwerpregel, zes
blokken, dashboardlinks met de week erin en een platte-tekstversie opleveren,
en in een week zonder signalen de korte vorm kiezen.
"""
import json
from datetime import date, timedelta

import pytest

from scraper import weekmail
from scraper.db import DbError

W = [date(2026, 8, 31) + timedelta(weeks=i) for i in range(3)]   # W36 … W38
WEEK = W[-1]


def _stat(rid, aud, ptype, week, n=40, med=5.0, p25=4.0, sale=0.0, unit=None, mp=0.0):
    return {"retailer_id": rid, "week": week.isoformat(), "audience": aud, "product_type": ptype,
            "active_count": n, "new_count": 2, "gone_count": 3,
            "price_median": med, "price_p25": p25, "sale_share": sale,
            "unit_price_median": med if unit is None else unit, "multipack_share": mp}


def _basis(week, beweging=False):
    """Eén groep per bron; met `beweging` verandert KiK en terStal in de laatste week."""
    laatste = beweging and week == WEEK
    kik_med = 4.59 if laatste else 3.0
    ter_n, ter_p25 = (110, 6.99) if laatste else (140, 5.0)
    wibra_med = 2.99 if laatste else 3.49
    return [
        _stat("terstal", "dames", "ondergoed", week, n=ter_n, med=7.99, p25=ter_p25, unit=7.99, mp=0.2),
        _stat("kik", "dames", "ondergoed", week, n=240, med=kik_med, p25=2.99, sale=0.46, unit=3.0, mp=0.4),
        _stat("wibra", "dames", "ondergoed", week, n=35, med=wibra_med, p25=3.49, sale=0.05),
        _stat("zeeman", "dames", "ondergoed", week, n=290, med=4.69, p25=3.99, unit=2.5, mp=0.58)
        if week != WEEK else None,
    ]


class FakeDb:
    def __init__(self, beweging=True, zeeman_status="fout", weekmail_tabel=True):
        self.stats = [s for w in W for s in _basis(w, beweging) if s]
        self.zeeman_status = zeeman_status
        self.weekmail_tabel = weekmail_tabel
        self.bewaard = None

    def retailers(self):
        return {"terstal": {"name": "terStal familiemode", "enabled": True},
                "kik": {"name": "KiK", "enabled": True}, "wibra": {"name": "Wibra", "enabled": True},
                "zeeman": {"name": "Zeeman", "enabled": True}, "takko": {"name": "Takko", "enabled": False}}

    def weeks(self):
        return sorted(W, reverse=True)

    def weekly_stats_range(self, start):
        return [s for s in self.stats if date.fromisoformat(s["week"]) >= start]

    def week_totals_range(self, start):
        out = {}
        for s in self.weekly_stats_range(start):
            w = date.fromisoformat(s["week"])
            t = out.setdefault(w, {}).setdefault(s["retailer_id"], {
                "retailer_id": s["retailer_id"], "week": s["week"], "active_count": 0,
                "new_count": 0, "gone_count": 0, "sale_share": 0.0})
            t["active_count"] += s["active_count"]
            t["new_count"] += s["new_count"]
            t["gone_count"] += s["gone_count"]
            t["sale_share"] = s["sale_share"]
        return out

    def runs(self, week):
        rows = [{"retailer_id": r, "status": "ok", "note": "", "strategy": "x"} for r in ("terstal", "kik", "wibra")]
        rows.append({"retailer_id": "zeeman", "status": self.zeeman_status,
                     "note": "HTTP 403 op https://www.zeeman.com/nl-nl/dames/ondergoed (bot-bescherming?)"})
        return rows

    def new_titles(self, week):
        return [{"retailer_id": "kik", "title": "Kerstpyjama dames"},
                {"retailer_id": "wibra", "title": "kerstpyjama heren geruit"},
                {"retailer_id": "kik", "title": "Thermoshirt heren"},
                {"retailer_id": "terstal", "title": "thermoshirt dames"},
                {"retailer_id": "wibra", "title": "thermoshirt kids"}]

    def recent_titles(self, start, before):
        return [{"retailer_id": "kik", "title": "Thermoshirt dames"},
                {"retailer_id": "wibra", "title": "thermoshirt heren"}]   # thermo stroomde al eerder in

    def count_events(self, week, kind):
        return {W[0]: 28, W[1]: 7, W[2]: 37}[week]

    def events(self, week, kinds):
        return [{"retailer_id": "terstal", "product_key": "a1", "event": "price_down",
                 "price": 1.00, "was_price": None, "prev_price": 3.99}]

    def products_by_keys(self, rid, keys):
        return {"a1": {"title": "rib slip naadloos"}}

    def load_weekmail(self, week):
        if not self.weekmail_tabel:
            raise DbError("relation weekmails does not exist")
        return {"week": week.isoformat(), "top3": [
            {"rid": "kik", "bron": "KiK", "aud": "dames", "ptype": "ondergoed", "soort": "mediaan",
             "richting": -1, "van": 3.3, "naar": 3.0, "tekst": "KiK: mediaanprijs dames / ondergoed omlaag"}]}

    def save_weekmail(self, row):
        if not self.weekmail_tabel:
            raise DbError("relation weekmails does not exist")
        self.bewaard = row


@pytest.fixture
def model(monkeypatch):
    monkeypatch.delenv("SCRAPE_OUTCOME", raising=False)

    def _model(**kw):
        return weekmail.build_model(WEEK, FakeDb(**kw))
    return _model


def test_model_kiest_signalen_en_markeert_rode_bron(model):
    m = model()
    assert m["label"] == "W38" and m["ok"] == 3 and m["totaal"] == 4
    assert m["rood"] and m["rood"][0][0] == "Zeeman"
    assert not m["rustig"]
    ridden = [s["rid"] for s in m["top3"]]
    assert "kik" in ridden and "terstal" in ridden
    # kerstpyjama is nieuw in de instroom (2 bronnen) en wint van thermoshirt (3 bronnen, al eerder gezien)
    assert m["onderwerp"].startswith("W38 · Instroom kerstpyjama bij 2 bronnen · ")
    assert len(m["onderwerp"]) <= 110
    assert m["onderwerp"].endswith("· 3/4 bronnen ok")
    # Zeeman staat in de kaart met zijn laatste goede week
    zeeman = next(k for k in m["kaart"] if k["rid"] == "zeeman")
    assert zeeman["hoofdlijn"].startswith("Geen meting deze week (HTTP 403, bot-bescherming)")
    assert "W37" in zeeman["hoofdlijn"]
    # kernconcurrenten eerst, terStal niet in de kaart, uitgeschakelde bron ook niet
    assert [k["rid"] for k in m["kaart"]] == ["zeeman", "wibra", "kik"]
    assert m["terugblik"][0]["uitkomst"] in ("houdt aan", "teruggedraaid")
    assert m["trendwoorden"][0]["woord"] == "kerstpyjama" and m["trendwoorden"][0]["nieuw"] is True
    assert next(w for w in m["trendwoorden"] if w["woord"] == "thermoshirt")["nieuw"] is False
    assert 1 <= len(m["agenda"]) <= 3


def test_html_bevat_zes_blokken_en_dashboardlinks(model):
    m = model()
    html = weekmail.render_html(m)
    for kop in ("1 · In drie zinnen", "2 · Concurrentenkaart", "3 · Prijspositie per stuk",
                "4 · Trendlijnen", "5 · Spiegel", "6 · Voor maandag 09:15", "Terugblik op W37"):
        assert kop in html, kop
    assert "?week=2026-09-14&amp;sectie=signalen" in html
    assert "sectie=prijsindex&amp;perstuk=1" in html
    assert "<img" not in html                       # nooit afbeeldingen
    assert "Zeeman*" in html and "Zeeman: stand W37" in html
    assert "▼ 38" in html                           # KiK per stuk 3,00 / 7,99
    assert "Antwoord op deze mail met <b>1</b>" in html
    assert "€4,59" in html                          # prijzen met komma, nooit met punt


def test_platte_tekst_volgt_dezelfde_opbouw(model):
    tekst = weekmail.render_text(model())
    assert tekst.startswith("CONCURRENTIEMONITOR TERSTAL - WEEKMAIL 38")
    assert "1. IN DRIE ZINNEN" in tekst and "6. VOOR MAANDAG 09:15" in tekst
    assert "Niet gemeten: Zeeman" in tekst
    assert "3. PRIJSPOSITIE PER STUK" in tekst
    assert "https://concurrentiemonitor-terstal.netlify.app/?week=2026-09-14" in tekst


def test_rustige_week_wordt_kort(model):
    m = model(beweging=False, zeeman_status="ok")
    assert m["rustig"] is True
    assert m["onderwerp"] == "W38 · Rustige week, geen signalen boven de drempel · 4/4 bronnen ok"
    html = weekmail.render_html(m)
    assert "Rustige week" in html and "1 · In drie zinnen" not in html
    assert "Geen agendapunt uit de monitor" in html


def test_storing_in_de_weekrun_staat_in_kop_en_onderwerp(model, monkeypatch):
    monkeypatch.setenv("SCRAPE_OUTCOME", "failure")
    m = model()
    assert m["storing"] is True and not m["rustig"]
    assert m["onderwerp"].startswith("W38 · Storing in de weekrun · ")
    assert "Storing in de weekrun" in weekmail.render_html(m)


def test_write_weekmail_schrijft_bestanden_en_bewaart_top3(tmp_path, monkeypatch):
    monkeypatch.delenv("SCRAPE_OUTCOME", raising=False)
    db = FakeDb()
    monkeypatch.setattr(weekmail, "Db", lambda: db)
    monkeypatch.setattr(weekmail, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(weekmail, "LAATSTE_JSON", tmp_path / "weekmail-latest.json")
    monkeypatch.setattr(weekmail, "BESLUITEN", tmp_path / "besluiten.md")
    verstuurd = {}

    def nep_send(subject, markdown_body=None, *, html=None, text=None, to=None, reply_to=None):
        verstuurd.update(subject=subject, html=html, text=text, to=to, reply_to=reply_to)
        return "e-mail verstuurd naar 1 adres(sen)"
    monkeypatch.setattr(weekmail, "send_email", nep_send)
    monkeypatch.setenv("REPORT_EMAIL_REPLY_TO", "opsteller@example.org")

    pad = weekmail.write_weekmail(WEEK, send=True, to="proef@example.org")
    assert pad.name == "2026-W38.html" and pad.exists()
    assert (tmp_path / "weekmail-latest.html").exists()
    laatste = json.loads((tmp_path / "weekmail-latest.json").read_text(encoding="utf-8"))
    assert laatste["week"] == "2026-09-14" and len(laatste["top3"]) == 3
    assert verstuurd["to"] == "proef@example.org" and verstuurd["reply_to"] == "opsteller@example.org"
    assert verstuurd["text"].startswith("CONCURRENTIEMONITOR")
    assert db.bewaard["week"] == "2026-09-14" and db.bewaard["sent_to"] == 1


def test_zonder_weekmailtabel_gaat_de_mail_gewoon_door(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("SCRAPE_OUTCOME", raising=False)
    monkeypatch.setattr(weekmail, "Db", lambda: FakeDb(weekmail_tabel=False))
    monkeypatch.setattr(weekmail, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(weekmail, "LAATSTE_JSON", tmp_path / "weekmail-latest.json")
    monkeypatch.setattr(weekmail, "BESLUITEN", tmp_path / "besluiten.md")
    weekmail.write_weekmail(WEEK, send=False)
    uit = capsys.readouterr().out
    assert "niet verstuurd (--dry-run)" in uit
    assert "migratie_weekmail.sql" in uit


def test_actieteller_leest_besluitenlog(tmp_path, monkeypatch):
    log = tmp_path / "besluiten.md"
    log.write_text("# Besluiten\n\n- W37 · 2 · KiK nachtmode: vol prijs vasthouden\n- W35 · 1 · x\n",
                   encoding="utf-8")
    monkeypatch.setattr(weekmail, "BESLUITEN", log)
    assert weekmail._actieteller(WEEK) == {"geteld": 2, "van": 3}
