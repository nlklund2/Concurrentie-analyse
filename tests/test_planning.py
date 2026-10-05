"""De planningspoort en de weekbepaling in Nederlandse tijd.

De weekrun heeft meerdere cron-slots omdat GitHub geplande runs uren te laat
start (14-09 en 21-09-2026). Precies één slot mag meten; het eerste slot valt
op zondagavond UTC en moet toch in de nieuwe week boeken.
"""
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

from scraper import planning
from scraper.config import nl_tz, vandaag_nl, week_monday

BRONNEN = ["zeeman", "action", "kik"]
WORKFLOW = Path(__file__).parent.parent / ".github" / "workflows" / "wekelijkse-scrape.yml"


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


def _run(rid, status="ok"):
    return {"retailer_id": rid, "status": status}


# -- weekbepaling ---------------------------------------------------------

def test_zondagavond_utc_is_in_nederland_al_maandag():
    # zomertijd: zo 20-09-2026 23:07 UTC = ma 21-09 01:07 NL → week van 21-09
    assert week_monday(vandaag_nl(utc(2026, 9, 20, 23, 7))) == date(2026, 9, 21)
    # wintertijd: zo 15-11-2026 23:07 UTC = ma 16-11 00:07 NL → week van 16-11
    assert week_monday(vandaag_nl(utc(2026, 11, 15, 23, 7))) == date(2026, 11, 16)


def test_zondagavond_nl_blijft_vorige_week():
    # zo 20-09-2026 21:30 UTC = zo 23:30 NL → nog de week van 14-09
    assert week_monday(vandaag_nl(utc(2026, 9, 20, 21, 30))) == date(2026, 9, 14)


def test_zomertijdgrenzen():
    assert nl_tz(utc(2026, 3, 29, 0, 59)).utcoffset(None) == timedelta(hours=1)
    assert nl_tz(utc(2026, 3, 29, 1, 0)).utcoffset(None) == timedelta(hours=2)
    assert nl_tz(utc(2026, 10, 25, 0, 59)).utcoffset(None) == timedelta(hours=2)
    assert nl_tz(utc(2026, 10, 25, 1, 0)).utcoffset(None) == timedelta(hours=1)


def test_week_monday_met_datum_ongewijzigd():
    assert week_monday(date(2026, 9, 23)) == date(2026, 9, 21)


# -- poort ----------------------------------------------------------------

def test_handmatige_run_meet_altijd():
    meten, _ = planning.besluit("workflow_dispatch", None, 5, None, BRONNEN)
    assert meten


def test_eerste_slot_meet():
    meten, reden = planning.besluit("schedule", [{"id": 5, "status": "in_progress"}], 5, [], BRONNEN)
    assert meten and "nog geen meting" in reden


def test_later_slot_wijkt_voor_lopende_run():
    gh = [{"id": 4, "status": "in_progress", "event": "schedule"},
          {"id": 5, "status": "in_progress", "event": "schedule"}]
    meten, reden = planning.besluit("schedule", gh, 5, [], BRONNEN)
    assert not meten and "4" in reden


def test_gelijktijdige_slots_precies_een_meet():
    gh = [{"id": 4, "status": "queued"}, {"id": 5, "status": "in_progress"}]
    assert planning.besluit("schedule", gh, 4, [], BRONNEN)[0]
    assert not planning.besluit("schedule", gh, 5, [], BRONNEN)[0]


def test_afgeronde_run_telt_niet_als_lopend():
    gh = [{"id": 4, "status": "completed", "conclusion": "failure"}]
    assert planning.besluit("schedule", gh, 5, [], BRONNEN)[0]


def test_gemeten_week_wordt_overgeslagen():
    runs = [_run("zeeman"), _run("action", "afwijkend"), _run("kik", "fout")]
    meten, reden = planning.besluit("schedule", [], 5, runs, BRONNEN)
    assert not meten and "al gemeten" in reden


def test_afgebroken_meting_wordt_herkanst():
    assert planning.besluit("schedule", [], 5, [_run("zeeman")], BRONNEN)[0]


def test_meting_zonder_enkele_ok_wordt_herkanst():
    runs = [_run(b, "fout") for b in BRONNEN]
    assert planning.besluit("schedule", [], 5, runs, BRONNEN)[0]


def test_deelrun_van_een_bron_is_geen_gemeten_week():
    # handmatige run met alleen --retailer zeeman, eerder op de maandag
    assert not planning.week_gemeten([_run("zeeman")], BRONNEN)


def test_bij_storing_in_de_controle_toch_meten():
    meten, reden = planning.besluit("schedule", None, 5, None, BRONNEN)
    assert meten and "onvolledig" in reden
    # GitHub onbereikbaar maar Supabase zegt 'gemeten' → overslaan blijft veilig
    runs = [_run(b) for b in BRONNEN]
    assert not planning.besluit("schedule", None, 5, runs, BRONNEN)[0]


def test_main_schrijft_output(monkeypatch, tmp_path):
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert planning.main() == 0
    assert out.read_text(encoding="utf-8") == "meten=true\n"


# -- de workflow zelf -----------------------------------------------------

def _crons():
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    on = wf.get("on") or wf.get(True)      # YAML 1.1 leest de sleutel 'on' als True
    return [s["cron"] for s in on["schedule"]]


def test_cron_nooit_op_het_hele_uur_en_meerdere_slots():
    crons = _crons()
    assert len(crons) >= 3
    for c in crons:
        minuut = c.split()[0]
        assert re.fullmatch(r"\d+", minuut) and int(minuut) % 30 != 0, c


def test_elk_cron_slot_valt_na_maandag_middernacht_nl():
    """Zomer én winter: geen slot mag nog in de vorige week boeken."""
    for c in _crons():
        minuut, uur, _, _, dag = c.split()
        for zondag in (date(2026, 9, 20), date(2026, 11, 15)):     # CEST, CET
            d = zondag if dag == "0" else zondag + timedelta(days=1)
            assert dag in ("0", "1"), c
            nu = utc(d.year, d.month, d.day, int(uur), int(minuut))
            assert week_monday(vandaag_nl(nu)) == zondag + timedelta(days=1), c
