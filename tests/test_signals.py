"""De regels achter de weekmail (docs/weekmail-voorstel.md §4), zonder database.

Elke regel heeft een positieve en een negatieve casus: een signaal dat de
top-3 haalt en een dat er terecht buiten blijft. De cijfers zijn ontleend
aan echte weken (KiK W36, Wibra W34–W38, HEMA dames ondergoed).
"""
from datetime import date, timedelta

from scraper import signals as S

W = [date(2026, 8, 3) + timedelta(weeks=i) for i in range(7)]   # W32 … W38
NAMEN = {"terstal": "terStal familiemode", "kik": "KiK", "wibra": "Wibra",
         "hema": "HEMA", "primark": "Primark"}
OK = {rid: "ok" for rid in NAMEN}


def _stat(rid, aud, ptype, n=40, med=5.0, p25=4.0, sale=0.0, unit=None, mp=0.0):
    return {"retailer_id": rid, "audience": aud, "product_type": ptype,
            "active_count": n, "new_count": 0, "gone_count": 0,
            "price_median": med, "price_p25": p25, "sale_share": sale,
            "unit_price_median": med if unit is None else unit, "multipack_share": mp}


def _weken(reeks):
    """reeks: per week een lijst stat-rijen → dict week → rijen."""
    return {w: rows for w, rows in zip(W, reeks)}


# --- sparkline ---------------------------------------------------------------
def test_sparkline_tekst():
    assert S.sparkline([1, 2, 3]) == "▁▅█"
    assert S.sparkline([5, 5, 5]) == "▁▁▁"
    assert S.sparkline([1, None, 3]) == "▁·█"
    assert S.sparkline([]) == ""


# --- 4.1 signaalscore met persistentie ---------------------------------------
def test_trend_krijgt_hogere_score_dan_eenmalige_sprong():
    reeks = [[_stat("kik", "heren", "ondergoed", med=4.00, p25=3.0)],
             [_stat("kik", "heren", "ondergoed", med=4.40, p25=3.0)],
             [_stat("kik", "heren", "ondergoed", med=4.84, p25=3.0)],
             [_stat("kik", "heren", "ondergoed", med=5.32, p25=3.0),
              _stat("hema", "dames", "ondergoed", med=10.0, p25=8.0)],
             ]
    reeks[2].append(_stat("hema", "dames", "ondergoed", med=10.0, p25=8.0))
    # HEMA: eenmalig +10%, even groot als KiK's laatste stap
    reeks[3][1]["price_median"] = 11.0
    stats = {w: rows for w, rows in zip(W[:4], reeks)}
    sigs = S.signalen(W[:4], stats, NAMEN, OK)
    kik = next(s for s in sigs if s["rid"] == "kik" and s["soort"] == "mediaan")
    hema = next(s for s in sigs if s["rid"] == "hema" and s["soort"] == "mediaan")
    assert kik["weken"] == 3 and kik["tag"] == "trend"
    assert hema["weken"] == 1 and hema["tag"] == "nieuw"
    assert kik["score"] > hema["score"]
    assert "mediaanprijs heren / ondergoed omhoog van €4,84 naar €5,32" in kik["tekst"]
    assert S.korte_reden("HTTP 403 op https://www.zeeman.com/nl-nl/dames (bot-bescherming?)") == "HTTP 403, bot-bescherming"
    assert S.korte_reden("slechts 11 artikelen (minimum 25); bron gewijzigd?") == "te weinig artikelen"


def test_kleine_groep_en_rode_bron_zijn_niet_betrouwbaar():
    stats = _weken([
        [_stat("hema", "dames", "ondergoed", n=12, med=10.0), _stat("kik", "dames", "ondergoed", med=3.0)],
        [_stat("hema", "dames", "ondergoed", n=12, med=16.0), _stat("kik", "dames", "ondergoed", med=3.6)],
    ])
    sigs = S.signalen(W[:2], stats, NAMEN, {"hema": "ok", "kik": "fout"})
    assert {s["rid"]: s["betrouwbaar"] for s in sigs} == {"hema": False, "kik": False}
    assert S.top3(sigs) == []


def test_verpakkingswissel_wordt_herkend_en_niet_als_prijsverhoging_verkocht():
    """KiK W36: herensokken €0,80 → €2,99 per artikel, per stuk €0,80, multipacks 0 → 100%."""
    stats = _weken([
        [_stat("kik", "heren", "sokken & panty's", med=0.80, p25=0.66, unit=0.80, mp=0.0)],
        [_stat("kik", "heren", "sokken & panty's", med=2.99, p25=1.99, unit=0.80, mp=1.0)],
    ])
    sigs = S.signalen(W[:2], stats, NAMEN, OK)
    med = next(s for s in sigs if s["soort"] == "mediaan")
    assert med["verpakkingswissel"] is True
    assert "verpakkingsprijs" in med["tekst"] and "per stuk ongewijzigd" in med["tekst"]
    assert S.top3(sigs) == []          # haalt de drie zinnen niet

    # Een echte verhoging (per stuk mee omhoog) blijft een verhoging.
    stats2 = _weken([
        [_stat("kik", "heren", "sokken & panty's", med=0.80, unit=0.80, mp=0.0)],
        [_stat("kik", "heren", "sokken & panty's", med=2.99, unit=2.99, mp=0.0)],
    ])
    sigs2 = S.signalen(W[:2], stats2, NAMEN, OK)
    assert all(not s["verpakkingswissel"] for s in sigs2)
    assert S.top3(sigs2)


def test_top3_is_twee_concurrenten_plus_eigen_huis():
    stats = _weken([
        [_stat("kik", "dames", "ondergoed", med=3.0), _stat("wibra", "dames", "ondergoed", med=3.49),
         _stat("primark", "dames", "ondergoed", med=8.0), _stat("terstal", "dames", "ondergoed", n=140, p25=5.0)],
        [_stat("kik", "dames", "ondergoed", med=4.59), _stat("wibra", "dames", "ondergoed", med=2.99),
         _stat("primark", "dames", "ondergoed", med=8.8), _stat("terstal", "dames", "ondergoed", n=120, p25=6.99)],
    ])
    top = S.top3(S.signalen(W[:2], stats, NAMEN, OK))
    assert len(top) == 3
    assert [s["rid"] for s in top][:2] != ["terstal", "terstal"]
    assert top[-1]["rid"] == "terstal"
    assert top[0]["score"] >= top[1]["score"]


# --- 4.3 trendwoorden --------------------------------------------------------
def test_trendwoorden_tellen_per_bron_en_slaan_stopwoorden_over():
    titels = [("kik", "Kerstpyjama dames rood"), ("kik", "Kerstpyjama heren"),
              ("hema", "kinder kerstpyjama beren"), ("primark", "Thermoshirt dames"),
              ("wibra", "thermoshirt heren zwart"), ("hema", "thermoshirt kids"),
              ("kik", "Dames sokken 5 paar"), ("hema", "dames sokken katoen")]
    woorden = S.trendwoorden(titels)
    assert woorden[0] == {"woord": "thermoshirt", "bronnen": 3, "n": 3, "nieuw": True}
    assert woorden[1] == {"woord": "kerstpyjama", "bronnen": 2, "n": 3, "nieuw": True}
    assert all(w["woord"] not in ("dames", "sokken", "heren") for w in woorden)
    # 'pyjama' stroomt elke week in en is een stopwoord; wat eerder al instroomde is niet nieuw
    eerder = [("hema", "thermoshirt kids"), ("primark", "thermoshirt dames"), ("kik", "pyjama heren")]
    woorden2 = S.trendwoorden(titels + [("kik", "Pyjama dames"), ("hema", "pyjama kind")], eerder)
    assert woorden2[0]["woord"] == "kerstpyjama" and woorden2[0]["nieuw"] is True
    assert next(w for w in woorden2 if w["woord"] == "thermoshirt")["nieuw"] is False
    assert all(w["woord"] != "pyjama" for w in woorden2)


# --- 4.5 concurrentenkaart ---------------------------------------------------
def _totals(reeks_per_rid):
    """{rid: [(n, new, gone, sale), …]} → week → rid → rij."""
    out = {}
    for rid, reeks in reeks_per_rid.items():
        for w, (n, nieuw, weg, sale) in zip(W, reeks):
            out.setdefault(w, {})[rid] = {"retailer_id": rid, "week": w.isoformat(),
                                          "active_count": n, "new_count": nieuw,
                                          "gone_count": weg, "sale_share": sale}
    return out


def test_kaart_geen_meting_toont_laatste_goede_stand():
    totals = _totals({"zeeman": [(1067, 1067, 0, 0.0), (1042, 22, 60, 0.0)]})
    stats = {W[0]: [], W[1]: [], W[2]: []}
    regel = S.kaart_regel("zeeman", W[:3], stats, totals,
                          {"status": "fout", "note": "HTTP 403 op https://www.zeeman.com"},
                          [], {"zeeman": "Zeeman"})
    assert regel["hoofdlijn"].startswith("Geen meting deze week (HTTP 403, bot-bescherming)")
    assert "Laatste beeld W33: 1.042 artikelen" in regel["hoofdlijn"]
    assert regel["gemeten_deze_week"] is False and regel["bijzin"] == ""


def test_kaart_krimp_en_sale_trend():
    """Wibra W33–W38: 129 → 110 in vijf weken, sale-druk 9% → 5%."""
    totals = _totals({"wibra": [(129, 0, 0, 0.093), (123, 4, 10, 0.089), (126, 5, 9, 0.071),
                                (125, 9, 10, 0.080), (112, 0, 14, 0.054), (110, 6, 9, 0.055)]})
    stats = {w: [_stat("wibra", "dames", "ondergoed", med=3.49)] for w in W[:6]}
    regel = S.kaart_regel("wibra", W[:6], stats, totals, {"status": "ok"}, [], NAMEN)
    assert regel["hoofdlijn"].startswith("Krimpt online al")
    assert "→ 110" in regel["hoofdlijn"]
    assert regel["omvang_spark"] == S.sparkline([129, 123, 126, 125, 112, 110])
    assert regel["gemeten_deze_week"] is True


def test_kaart_draaideur_en_sale_trend():
    totals = _totals({"action": [(200, 20, 20, 0.0)] * 3 + [(211, 93, 147, 0.0)],
                      "kik": [(600, 5, 5, 0.507), (600, 5, 5, 0.488), (600, 5, 5, 0.458), (600, 5, 5, 0.430)]})
    stats = {w: [] for w in W[:4]}
    action = S.kaart_regel("action", W[:4], stats, totals, {"status": "ok"}, [], {"action": "Action"})
    assert action["hoofdlijn"].startswith("Online een draaideur: 44% in, 70% uit")
    kik = S.kaart_regel("kik", W[:4], stats, totals, {"status": "ok"}, [], NAMEN)
    assert kik["hoofdlijn"].startswith("Sale-druk daalt voor de derde week (49% → 46% → 43%)")


# --- blok 3: prijspositie per stuk -------------------------------------------
def test_prijspositie_index_pijl_en_stand_van_rode_bron():
    def week(t_unit, kik_unit, zeeman=True):
        rows = [_stat("terstal", "dames", "ondergoed", n=120, unit=t_unit),
                _stat("kik", "dames", "ondergoed", unit=kik_unit)]
        if zeeman:
            rows.append(_stat("zeeman", "dames", "ondergoed", unit=2.50))
        return rows
    stats = {W[0]: week(7.74, 3.00), W[1]: week(7.74, 3.00), W[2]: week(7.5, 3.0),
             W[3]: week(7.5, 3.0), W[4]: week(7.99, 3.0, zeeman=False)}
    status = {"terstal": "ok", "kik": "ok", "zeeman": "fout"}
    pr = S.prijspositie(W[:5], stats, status, {**NAMEN, "zeeman": "Zeeman"})
    g = ("dames", "ondergoed")
    assert pr["groepen"] == [g]
    assert pr["cellen"][(g, "kik")]["index"] == 38 and pr["cellen"][(g, "kik")]["klasse"] == "lo"
    assert pr["cellen"][(g, "kik")]["pijl"] == ""          # 39 → 38: geen pijl
    assert pr["cellen"][(g, "zeeman")]["index"] == 31       # uit W35, de laatste goede week
    assert pr["stand"]["zeeman"] == W[3] and pr["stand"]["kik"] == W[4]

    # C&A: 168 → 125 in vier weken → pijl omlaag
    stats2 = {w: rows + [_stat("c-and-a", "dames", "ondergoed", unit=12.99 if w == W[0] else 9.99)]
              for w, rows in stats.items()}
    pr2 = S.prijspositie(W[:5], stats2, {**status, "c-and-a": "ok"}, {**NAMEN, "c-and-a": "C&A"})
    assert pr2["cellen"][(g, "c-and-a")]["index"] == 125
    assert pr2["cellen"][(g, "c-and-a")]["pijl"] == "↓"


# --- 4.6 terugblik -----------------------------------------------------------
def test_terugblik_houdt_aan_teruggedraaid_niet_meetbaar():
    vorige = [
        {"rid": "c-and-a", "aud": "dames", "ptype": "ondergoed", "soort": "omvang",
         "richting": 1, "van": 110, "naar": 251, "tekst": "C&A breidt uit"},
        {"rid": "hema", "aud": "dames", "ptype": "ondergoed", "soort": "mediaan",
         "richting": 1, "van": 10.64, "naar": 12.29, "tekst": "HEMA mediaan omhoog"},
        {"rid": "zeeman", "aud": "dames", "ptype": "ondergoed", "soort": "mediaan",
         "richting": 1, "van": 4.5, "naar": 4.69, "tekst": "Zeeman mediaan omhoog"},
    ]
    stats = {
        W[0]: [_stat("c-and-a", "dames", "ondergoed", n=251), _stat("hema", "dames", "ondergoed", med=12.29),
               _stat("zeeman", "dames", "ondergoed", med=4.69)],
        W[1]: [_stat("c-and-a", "dames", "ondergoed", n=255), _stat("hema", "dames", "ondergoed", med=8.99)],
    }
    uit = S.terugblik(vorige, W[:2], stats, {"c-and-a": "ok", "hema": "ok", "zeeman": "fout"})
    assert [u["uitkomst"] for u in uit] == ["houdt aan", "teruggedraaid", "niet meetbaar"]
    assert uit[0]["nu"] == 255


# --- 4.7 onderwerp / rustige week -------------------------------------------
def test_onderwerpregel_en_rustige_week():
    status = {"kik": "ok", "wibra": "ok", "zeeman": "fout"}
    assert S.onderwerp(W[6], [], {"kik": "ok", "wibra": "ok"}) == \
        "W38 · Rustige week, geen signalen boven de drempel · 2/2 bronnen ok"
    sig = {"bron": "KiK", "aud": "dames", "ptype": "nachtmode", "soort": "sale", "richting": 1,
           "kop": S.kop_uit_signaal({"bron": "KiK", "aud": "dames", "ptype": "nachtmode",
                                     "soort": "sale", "richting": 1})}
    assert S.onderwerp(W[6], [sig], status) == \
        "W38 · KiK sale-druk dames nachtmode omhoog · 2/3 bronnen ok"
    assert not S.is_rustig([], status)          # een rode bron is nooit rustig
