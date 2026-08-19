"""Het weekrapport zonder database: bouwt het de nieuwe secties correct op?

Twee toevoegingen worden hier vastgelegd (PLAN.md §11.1 en §11.2):
de prijsindex per stuk en het vernieuwingstempo. Beide rekenen met deelsommen
waar een lege of eerste meetweek stilletjes onzin kan opleveren.
"""
from datetime import date

import pytest

from scraper import report

WEEK = date(2026, 8, 17)
VORIGE = date(2026, 8, 10)


def _stat(rid, aud, ptype, **kw):
    rij = {"retailer_id": rid, "audience": aud, "product_type": ptype,
           "active_count": 20, "new_count": 0, "gone_count": 0,
           "price_median": 10.0, "price_p25": 8.0, "sale_share": 0.0,
           "unit_price_median": 10.0, "multipack_share": 0.0}
    rij.update(kw)
    return rij


class FakeDb:
    """Minimale dubbelganger van Db — het rapport leest, schrijft nooit."""

    def __init__(self, stats, totals, prev_totals=None, prev_stats=None):
        self._stats = {WEEK: stats, VORIGE: prev_stats or []}
        self._totals = {WEEK: totals, VORIGE: prev_totals if prev_totals is not None else totals}

    def retailers(self):
        return {"terstal": {"name": "terStal familiemode"}, "hema": {"name": "HEMA"}}

    def weeks(self):
        return [WEEK, VORIGE]

    def weekly_stats(self, week):
        return self._stats.get(week, [])

    def week_totals(self, week):
        return self._totals.get(week, {})

    def runs(self, week):
        return []

    def events(self, week, kinds):
        return []

    def products_by_keys(self, rid, keys):
        return {}


@pytest.fixture
def bouw(monkeypatch):
    def _bouw(**kw):
        monkeypatch.setattr(report, "Db", lambda: FakeDb(**kw))
        return report.build(WEEK)
    return _bouw


def test_index_per_stuk_rekent_met_de_packprijs(bouw):
    """HEMA voert 5-paar sokken van €7,69: duurder per artikel, goedkoper per
    stuk. Precies het verschil dat §5 niet ziet en §5b wél."""
    stats = [
        _stat("terstal", "meisjes", "sokken & panty's", price_median=4.99,
              unit_price_median=4.99, multipack_share=0.0),
        _stat("hema", "meisjes", "sokken & panty's", price_median=7.69,
              unit_price_median=1.54, multipack_share=0.6),
    ]
    totals = {"terstal": {"active_count": 20, "new_count": 1, "gone_count": 2},
              "hema": {"active_count": 20, "new_count": 4, "gone_count": 0}}
    md = bouw(stats=stats, totals=totals)

    assert "### 5b. Prijsindex per stuk" in md
    kop, per_stuk = md.split("### 5b. Prijsindex per stuk", 1)
    assert "| meisjes / sokken & panty's | 154 |" in kop        # §5: op artikelprijs
    assert "| meisjes / sokken & panty's | 31 |" in per_stuk    # §5b: per stuk
    assert "HEMA 60%" in per_stuk                               # aandeel multipacks


def test_groep_zonder_multipacks_blijft_uit_de_per_stuk_tabel(bouw):
    stats = [_stat("terstal", "dames", "ondergoed"), _stat("hema", "dames", "ondergoed")]
    totals = {"terstal": {"active_count": 20, "new_count": 0, "gone_count": 0}}
    md = bouw(stats=stats, totals=totals)
    assert "Geen groep met noemenswaardig aandeel multipacks" in md


def test_zonder_migratie_geen_verzonnen_per_stuk_cijfers(bouw):
    stats = [_stat("terstal", "dames", "ondergoed", unit_price_median=None,
                   multipack_share=None),
             _stat("hema", "dames", "ondergoed", unit_price_median=None,
                   multipack_share=None)]
    totals = {"terstal": {"active_count": 20, "new_count": 0, "gone_count": 0}}
    md = bouw(stats=stats, totals=totals)
    assert "migratie_prijs_per_stuk.sql" in md


def test_vernieuwingstempo_in_procenten(bouw):
    stats = [_stat("terstal", "dames", "ondergoed"), _stat("hema", "dames", "ondergoed")]
    totals = {"terstal": {"active_count": 600, "new_count": 99, "gone_count": 150},
              "hema": {"active_count": 100, "new_count": 6, "gone_count": 0}}
    md = bouw(stats=stats, totals=totals)
    assert "## 7. Vernieuwingstempo per bron" in md
    assert "| terStal familiemode | 600 | 99 (16%) | 150 (25%) |" in md
    assert "| HEMA | 100 | 6 (6%) | 0 (0%) |" in md


def test_zonder_vergelijkweek_geen_vernieuwingspercentage(bouw):
    """In de eerste week van een bron (of na een week die de kwaliteitspoort
    tegenhield) is alles 'nieuw'; 100% instroom melden zou die bron ten onrechte
    als de snelste van het veld neerzetten."""
    stats = [_stat("terstal", "dames", "ondergoed"), _stat("hema", "dames", "ondergoed")]
    totals = {"terstal": {"active_count": 600, "new_count": 99, "gone_count": 150},
              "hema": {"active_count": 100, "new_count": 100, "gone_count": 0}}
    prev_totals = {"terstal": {"active_count": 590, "new_count": 10, "gone_count": 5}}
    md = bouw(stats=stats, totals=totals, prev_totals=prev_totals)
    assert "| HEMA | 100 | geen vergelijkweek | geen vergelijkweek |" in md
