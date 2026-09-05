"""Bronconfiguratie van de foldermonitor: gespiegeld aan retailers.yml."""
import yaml

from folders.config import BRONNEN_FILE, load_bronnen
from scraper.config import RETAILERS_FILE


def test_ids_bestaan_in_retailers_yml():
    monitor_ids = set(yaml.safe_load(RETAILERS_FILE.read_text(encoding="utf-8"))["retailers"])
    for b in load_bronnen(include_disabled=True):
        if b.id in ("lidl", "aldi"):        # folder-only bronnen, bewust niet in de monitor
            continue
        assert b.id in monitor_ids, b.id


def test_defaults_en_uitgeschakeld():
    aan = load_bronnen()
    alle = load_bronnen(include_disabled=True)
    assert {b.id for b in alle} - {b.id for b in aan} == {"lidl", "aldi"}
    wibra = next(b for b in aan if b.id == "wibra")
    assert wibra.cadence_days == 14 and wibra.min_delay == 1.0 and wibra.alias == "wibra"
    assert all(b.mail_from for b in alle)


def test_mail_only_bronnen():
    alle = {b.id: b for b in load_bronnen(include_disabled=True)}
    assert alle["primark"].mail_only and alle["c-and-a"].mail_only
    assert not alle["zeeman"].mail_only


def test_onbekende_bron_faalt():
    import pytest
    with pytest.raises(SystemExit):
        load_bronnen(["bestaatniet"])


def test_bestand_is_geldige_yaml_met_defaults():
    raw = yaml.safe_load(BRONNEN_FILE.read_text(encoding="utf-8"))
    assert raw["defaults"]["viewer"] == "auto"
