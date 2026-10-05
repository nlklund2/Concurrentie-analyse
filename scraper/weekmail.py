"""Weekmail: de maandagsamenvatting van het dashboard, per e-mail.

Zes blokken van oordeel naar detail (docs/weekmail-voorstel.md §3), gebouwd
uit precies de views die het dashboard leest. Elk blok linkt naar zijn
dashboardsectie met de week voorgeselecteerd. HTML en platte tekst komen uit
hetzelfde model; de HTML gebruikt tabellen, inline stijlen en geen enkele
afbeelding, zodat hij in Outlook, Gmail en op een telefoon leesbaar blijft.

  python -m scraper weekmail [--week JJJJ-MM-DD] [--dry-run] [--to adres]
"""
from __future__ import annotations

import html as _html
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from . import signals as S
from .config import env, focus_product_types, nl_tz
from .db import Db, DbError
from .report import REPORTS_DIR, send_email

DASHBOARD_URL = (env("DASHBOARD_URL") or "https://concurrentiemonitor-terstal.netlify.app").rstrip("/")
REPO_URL = "https://github.com/" + (env("GITHUB_REPOSITORY") or "nlklund2/Concurrentie-analyse")
EIGEN = "terstal"
# Volgorde van de concurrentenkaart: kernconcurrenten eerst (PLAN.md §3).
KAART_VOLGORDE = ["zeeman", "wibra", "kik", "primark", "action", "hema", "c-and-a"]
TREND_WEKEN = 6
BESLUITEN = REPORTS_DIR / "besluiten.md"
LAATSTE_JSON = REPORTS_DIR / "weekmail-latest.json"

h = _html.escape


def dash(sectie: str, week: date, **extra) -> str:
    q = [f"week={week.isoformat()}", f"sectie={sectie}"]
    q += [f"{k}={v}" for k, v in extra.items() if v]
    return f"{DASHBOARD_URL}/?{'&'.join(q)}"


# --- model ---------------------------------------------------------------
def build_model(week: date, db) -> dict:
    retailers = db.retailers()
    names = {rid: r.get("name", rid) for rid, r in retailers.items()}
    alle_weken = sorted(w for w in db.weeks() if w <= week)
    weeks = alle_weken[-(TREND_WEKEN + 2):]          # 6 voor de trend, 2 extra voor persistentie
    if week not in weeks:
        weeks.append(week)
    start = weeks[0]
    stats: dict[date, list[dict]] = {}
    for r in db.weekly_stats_range(start):
        stats.setdefault(date.fromisoformat(r["week"]), []).append(r)
    totals = db.week_totals_range(start)

    runs = db.runs(week)
    laatste_run: dict[str, dict] = {}
    for r in runs:
        laatste_run.setdefault(r["retailer_id"], r)     # nieuwste eerst
    bronnen = [rid for rid, r in retailers.items() if r.get("enabled", True)]
    for rid in set(totals.get(week, {})) | set(laatste_run):
        if rid not in bronnen:
            bronnen.append(rid)
    status = {rid: laatste_run.get(rid, {}).get("status", "geen run") for rid in bronnen}
    storing = (env("SCRAPE_OUTCOME") or "").lower() in ("failure", "cancelled")

    sigs = S.signalen(weeks, stats, names, status)
    gekozen = S.top3(sigs, EIGEN)
    for s in gekozen:
        s["kop"] = S.kop_uit_signaal(s)
    nieuwe = [(r["retailer_id"], r.get("title") or "") for r in db.new_titles(week)]
    eerder = [(r["retailer_id"], r.get("title") or "")
              for r in db.recent_titles(week - timedelta(weeks=4), week)]
    woorden = S.trendwoorden(nieuwe, eerder)
    # Seizoenssignaal: nieuw in de instroom bij ≥ 2 bronnen, of bij ≥ 3 bronnen sowieso.
    seizoen = [w for w in woorden if (w["nieuw"] and w["bronnen"] >= 2) or w["bronnen"] >= 3][:2]

    kaart = []
    volgorde = [r for r in KAART_VOLGORDE if r in bronnen] + \
               sorted(r for r in bronnen if r not in KAART_VOLGORDE and r != EIGEN)
    for rid in volgorde:
        kaart.append(S.kaart_regel(rid, weeks, stats, totals, laatste_run.get(rid, {}), sigs, names))

    prijs = S.prijspositie(weeks, stats, status, names, EIGEN,
                           concurrenten=[r for r in volgorde])

    # trendtegels
    laatste6 = weeks[-TREND_WEKEN:]
    verlagingen = [db.count_events(w, "price_down") for w in laatste6]
    beste, beweging = None, 0.0
    for k in kaart:
        s = [v for v in k["sale_reeks"] if v is not None]
        if len(s) >= 3 and abs(s[-1] - s[0]) > beweging:
            beste, beweging = k, abs(s[-1] - s[0])
    eigen_omvang = [S._f((totals.get(w, {}).get(EIGEN) or {}).get("active_count")) for w in weeks[-7:]]
    tegels = [{
        "label": "Prijsverlagingen, alle bronnen", "waarde": str(verlagingen[-1]),
        "spark": S.sparkline(verlagingen),
        "duiding": ("hoogste van de laatste zes weken" if verlagingen[-1] == max(verlagingen)
                    else f"zes weken: {', '.join(str(v) for v in verlagingen)}"),
        "link": dash("movers", week),
    }]
    if beste:
        s = [v for v in beste["sale_reeks"] if v is not None]
        richting = "omlaag" if s[-1] < s[0] else "omhoog"
        tegels.append({"label": f"Sale-druk {beste['naam']}", "waarde": S.pct(s[-1]),
                       "spark": beste["sale_spark"],
                       "duiding": f"{richting} sinds {S.week_label(laatste6[0])}, piek {S.pct(max(s))}",
                       "link": dash("omvang", week, bron=beste["rid"])})
    if any(v is not None for v in eigen_omvang):
        geldig = [v for v in eigen_omvang if v is not None]
        d = (geldig[-1] - geldig[-2]) / geldig[-2] if len(geldig) >= 2 and geldig[-2] else 0
        tegels.append({"label": f"Omvang {names.get(EIGEN, EIGEN)} online",
                       "waarde": f"{int(geldig[-1])}", "spark": S.sparkline(eigen_omvang),
                       "duiding": f"{d:+.0%} t.o.v. vorige week",
                       "link": dash("omvang", week, bron=EIGEN)})

    spiegel = _spiegel(week, weeks, stats, totals, sigs, db, names)

    vorige = weeks[-2] if len(weeks) >= 2 else None
    vorige_top3 = _laad_vorige_top3(db, vorige)
    terug = S.terugblik(vorige_top3, weeks, stats, status)

    agenda = _agenda(gekozen, seizoen, names)
    teller = _actieteller(week)
    rustig = S.is_rustig(gekozen, status) and not storing

    kern = [w["woord"] for w in seizoen[:1]]
    kern = ([f"{'Instroom '+kern[0]} bij {seizoen[0]['bronnen']} bronnen"] if kern else []) + \
           [s["kop"] for s in gekozen]
    if storing:
        kern = ["Storing in de weekrun"] + kern
    onderwerp = S.onderwerp(week, gekozen, status, kern) if not rustig \
        else S.onderwerp(week, [], status)

    ok = sum(1 for v in status.values() if v == "ok")
    rood = [(names.get(r, r), S.korte_reden(laatste_run.get(r, {}).get("note") or status[r]))
            for r, v in status.items() if v != "ok"]
    nu = datetime.now(nl_tz())
    return {
        "week": week, "label": S.week_label(week), "weeks": weeks, "names": names,
        "status": status, "ok": ok, "totaal": len(status), "rood": rood, "storing": storing,
        "focus": focus_product_types(), "sigs": sigs, "top3": gekozen, "rustig": rustig,
        "onderwerp": onderwerp, "kaart": kaart, "prijs": prijs, "tegels": tegels,
        "spiegel": spiegel, "terugblik": terug, "vorige": vorige, "agenda": agenda,
        "trendwoorden": woorden, "actieteller": teller,
        "samengesteld": nu.strftime("%d-%m-%Y %H:%M"),
        "rapport_url": f"{REPO_URL}/blob/main/reports/{week.isocalendar()[0]}-W{week.isocalendar()[1]:02d}.md",
        "dashboard_url": dash("weekmail", week),
    }


def _spiegel(week, weeks, stats, totals, sigs, db, names) -> dict:
    tot = totals.get(week, {}).get(EIGEN) or {}
    prev = totals.get(weeks[-2], {}).get(EIGEN) if len(weeks) >= 2 else None
    regels: list[str] = []
    n = tot.get("active_count")
    if n and prev:
        i, u = int(tot.get("new_count") or 0), int(tot.get("gone_count") or 0)
        regels.append(f"{u} artikelen verdwenen, {i} nieuw (uitstroom {u / n:.0%}, instroom {i / n:.0%}); "
                      f"omvang {int(prev['active_count'])} → {n}.")
    cur = S.by_key(stats.get(week, []))
    prv = S.by_key(stats.get(weeks[-2], [])) if len(weeks) >= 2 else {}
    veranderingen = []
    for (rid, aud, ptype), c in cur.items():
        if rid != EIGEN:
            continue
        p = prv.get((rid, aud, ptype))
        if p:
            veranderingen.append((abs(int(c["active_count"]) - int(p["active_count"])),
                                  S.groep_naam(aud, ptype), int(p["active_count"]), int(c["active_count"])))
    veranderingen.sort(reverse=True)
    if veranderingen and veranderingen[0][0] >= 5:
        regels.append("Grootste verschuivingen: " + "; ".join(
            f"{g} {a} → {b}" for _, g, a, b in veranderingen[:3] if abs(a - b) >= 3) + ".")
    for s in sigs:
        if s["rid"] == EIGEN and s["soort"] in ("instap", "mediaan") and s["betrouwbaar"]:
            naam = "instapniveau" if s["soort"] == "instap" else "mediaanprijs"
            regels.append(f"{naam[0].upper()}{naam[1:]} {S.groep_naam(s['aud'], s['ptype'])} "
                          f"{S.eur(s['van'])} → {S.eur(s['naar'])} ({s['delta']:+.0%}).")
            if len([r for r in regels if "niveau" in r or "prijs " in r]) >= 2:
                break
    downs = [d for d in db.events(week, ["price_down"])
             if d["retailer_id"] == EIGEN and d.get("prev_price") and d.get("price")]
    downs.sort(key=lambda d: (float(d["price"]) - float(d["prev_price"])) / float(d["prev_price"]))
    if downs:
        titels = db.products_by_keys(EIGEN, [d["product_key"] for d in downs[:8]])
        delen, gezien = [], set()
        for d in downs[:8]:
            t = titels.get(d["product_key"], {}).get("title", d["product_key"])[:40]
            regel = f"{t} {S.eur(d['prev_price'])} → {S.eur(d['price'])}"
            if regel in gezien:            # twee kleuren van hetzelfde artikel
                continue
            gezien.add(regel)
            delen.append(regel)
            if len(delen) == 3:
                break
        regels.append(f"Eigen prijsverlagingen ({len(downs)}): " + "; ".join(delen) + ".")
    if not regels:
        regels.append("Geen noemenswaardige verandering in het eigen assortiment.")
    return {"regels": regels, "vraag": "Klopt dit met de planning, of ziet de website iets anders dan inkoop?",
            "link": dash("explorer", week, bron=EIGEN)}


def _agenda(gekozen: list[dict], seizoen: list[dict], names: dict[str, str]) -> list[str]:
    punten: list[str] = []
    if seizoen:
        w = seizoen[0]
        punten.append(f"Instroom: '{w['woord']}' duikt deze week op bij {w['bronnen']} bronnen "
                      f"({w['n']} artikelen). Ligt het bij ons al online en in de winkel?")
    for s in gekozen:
        g = S.groep_naam(s["aud"], s["ptype"])
        b = s["bron"]
        if s["rid"] == EIGEN:
            punten.append(f"Eigen huis: {s['tekst'].replace(b + ' ', '').replace(b + ': ', '')}. "
                          "Bewust, of een websiteprobleem?")
        elif s["soort"] == "omvang" and s["richting"] > 0:
            punten.append(f"{b} bouwt {g} uit ({s['van']} → {s['naar']}): trekt het seizoen eerder aan "
                          "dan onze inkoopkalender aanneemt?")
        elif s["soort"] == "omvang":
            punten.append(f"{b} saneert {g} ({s['van']} → {s['naar']}): einde seizoen bij hen, "
                          "of ruimte voor ons?")
        elif s["soort"] == "sale" and s["richting"] > 0:
            punten.append(f"{b} zit op {S.pct(s['naar'])} afgeprijsd in {g}: vol prijs vasthouden "
                          "en marge pakken, of gericht flankeren?")
        elif s["soort"] == "sale":
            punten.append(f"{b} bouwt de sale-druk in {g} af ({S.pct(s['van'])} → {S.pct(s['naar'])}): "
                          "wat komt er bij hen voor in de plaats?")
        elif s["richting"] < 0:
            naam = "mediaan" if s["soort"] == "mediaan" else "instap"
            punten.append(f"{b} verlaagt de {naam} {g} naar {S.eur(s['naar'])}: volgen, negeren "
                          "of flankeren met één actie-artikel?")
        else:
            naam = "mediaan" if s["soort"] == "mediaan" else "instap"
            punten.append(f"{b} tilt de {naam} {g} naar {S.eur(s['naar'])}: kans om met ons "
                          "prijspunt het prijsimago te pakken?")
        if len(punten) == 3:
            break
    return punten[:3]


def _actieteller(week: date) -> dict:
    """Weken met een vastgelegd besluit in reports/besluiten.md (regels '- W38 …')."""
    weken: set[str] = set()
    if BESLUITEN.exists():
        for regel in BESLUITEN.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^- (W\d{2})\b", regel.strip())
            if m:
                weken.add(m.group(1))
    laatste3 = [S.week_label(week - timedelta(weeks=k)) for k in (1, 2, 3)]
    return {"geteld": sum(1 for w in laatste3 if w in weken), "van": 3}


def _laad_vorige_top3(db, vorige: date | None) -> list[dict]:
    if not vorige:
        return []
    try:
        rij = db.load_weekmail(vorige)
        if rij and rij.get("top3"):
            return rij["top3"]
    except DbError:
        pass
    if LAATSTE_JSON.exists():
        try:
            data = json.loads(LAATSTE_JSON.read_text(encoding="utf-8"))
            if data.get("week") == vorige.isoformat():
                return data.get("top3") or []
        except ValueError:
            pass
    return []


# --- HTML ----------------------------------------------------------------
KLEUR = {"lo": "#fde3d6", "eq": "#f0efec", "hi": "#d9e8fb"}
SPARK_FONT = "font-family:'Segoe UI Symbol','Apple Symbols','DejaVu Sans',monospace;letter-spacing:1px;color:#8a8a8a;font-size:13px"


def _spark(s: str) -> str:
    if not s:
        return ""
    return f"<span style=\"{SPARK_FONT}\">{h(s[:-1])}<span style=\"color:#12202a\">{h(s[-1])}</span></span>"


def _tag(s: dict) -> str:
    stijl = "display:inline-block;font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;padding:1px 7px;border:1px solid #b9b9b9;border-radius:3px;color:#444;margin-left:4px;white-space:nowrap"
    if s["weken"] >= 3:
        stijl = stijl.replace("#b9b9b9", "#12202a").replace("color:#444", "color:#12202a")
    tekst = s["tag"] + (f" · {s['weken']} wk" if s["weken"] >= 2 else "")
    if s["rid"] == EIGEN:
        tekst += " · eigen huis"
    return f'<span style="{stijl}">{h(tekst)}</span>'


def _kop(nr: str, titel: str, link: str | None, linktekst: str = "in het dashboard") -> str:
    a = f'<a href="{h(link)}" style="color:#0e6b70;font-size:12px;letter-spacing:0;text-transform:none">{h(linktekst)}</a>' if link else ""
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#555;padding:0 0 8px">{h(nr)} {h(titel)}</td>'
            f'<td align="right" style="padding:0 0 8px">{a}</td></tr></table>')


def render_html(m: dict) -> str:
    week = m["week"]
    P = "padding:18px 22px 6px"
    delen: list[str] = []

    # kop
    status_kleur = "#0ca30c" if not m["rood"] and not m["storing"] else "#d03b3b"
    if m["storing"]:
        status_tekst = ("<b>Storing in de weekrun.</b> De meting is niet (volledig) geslaagd; "
                        "deze mail toont de laatst verwerkte stand per bron. Kijk in GitHub Actions.")
    elif m["rood"]:
        lijst = "; ".join(f"{h(n)} ({h(str(note))})" for n, note in m["rood"])
        status_tekst = (f"<b>{m['ok']} van {m['totaal']} bronnen ok.</b> Niet gemeten: {lijst}. "
                        "Cijfers van die bron zijn van de laatste goede week en staan zo gemarkeerd.")
    else:
        status_tekst = f"<b>{m['ok']} van {m['totaal']} bronnen ok.</b> Alle cijfers zijn van deze week."
    scope = f" · {', '.join(m['focus'])}" if m["focus"] else ""
    delen.append(f"""
<div style="padding:18px 22px 14px;border-bottom:3px solid #12202a">
  <div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#555">Concurrentiemonitor terStal · ondergoedmode</div>
  <div style="font-size:22px;font-weight:700;margin:2px 0 6px;line-height:1.2">Weekmail {week.isocalendar()[1]}</div>
  <div style="font-size:13px;color:#555">Peildatum maandag {week.strftime('%d-%m-%Y')} · leestijd {'1 minuut' if m['rustig'] else '3 minuten'} · trend over {TREND_WEKEN} weken{h(scope)}</div>
  <div style="margin:12px 0 0;padding:8px 12px;background:#f4f4f2;border-left:4px solid {status_kleur};font-size:13.5px">{status_tekst}</div>
</div>""")

    if m["rustig"]:
        delen.append(f"""
<div style="{P}">{_kop('', 'Rustige week', dash('signalen', week))}
  <p style="font-size:14.5px;margin:0">Geen groep bewoog meer dan {S.COUNT_SIGNAL:.0%} in omvang, {S.MEDIAN_SIGNAL:.0%} in mediaanprijs of {S.SALE_SIGNAL * 100:.0f} punten in sale-druk. Het overleg van 09:15 kan kort: vijf minuten dashboard, geen agendapunt uit de monitor.</p>
</div>""")
    else:
        items = "".join(
            f'<li style="padding-left:14px;border-left:3px solid #12202a;margin:0 0 10px"><b>{h(s["kop"])}.</b> {h(s["tekst"])}. {_tag(s)}</li>'
            for s in m["top3"])
        delen.append(f"""
<div style="{P}">{_kop('1 ·', 'In drie zinnen', dash('signalen', week), 'alle signalen in het dashboard')}
  <ul style="margin:0;padding:0;list-style:none">{items}</ul>
</div>""")

    # concurrentenkaart
    rijen = []
    for k in m["kaart"]:
        sinds = f' <span style="color:#7a7a7a;font-size:12px">{h(k["sinds"])}</span>' if k["sinds"] else ""
        bijzin = f" {h(k['bijzin'])}." if k["bijzin"] else ""
        hoofd = h(k["hoofdlijn"]) if k["status"] == "ok" else f"<b>{h(k['hoofdlijn'])}</b>"
        if k["gemeten_deze_week"]:
            sale = f"{_spark(k['sale_spark'])} {S.pct(k['sale'])}" if k["sale"] is not None else "–"
            omvang = f"{_spark(k['omvang_spark'])} {int(k['omvang']):,}".replace(",", ".") if k["omvang"] else "–"
        else:
            wl = S.week_label(k["laatste_week"]) if k["laatste_week"] else "–"
            sale = f"{S.pct(k['sale'])} · {wl}" if k["sale"] is not None else "–"
            omvang = f"{int(k['omvang']):,} · {wl}".replace(",", ".") if k["omvang"] else "–"
        rijen.append(f"""<tr>
  <td style="padding:9px 6px 9px 0;border-bottom:1px solid #e4e4e4;vertical-align:top;white-space:nowrap;font-weight:700;width:78px">{h(k['naam'])}</td>
  <td style="padding:9px 6px 9px 0;border-bottom:1px solid #e4e4e4;vertical-align:top">{hoofd}{'.' if not k['hoofdlijn'].endswith('.') else ''}{bijzin}{sinds}</td>
  <td style="padding:9px 0 9px 0;border-bottom:1px solid #e4e4e4;vertical-align:top;white-space:nowrap;text-align:right;font-size:12.5px;color:#444;width:118px"><span style="display:block;font-size:10.5px;color:#7a7a7a;letter-spacing:.04em;text-transform:uppercase">sale · omvang</span>{sale}<br>{omvang}</td>
</tr>""")
    delen.append(f"""
<div style="{P}">{_kop('2 ·', 'Concurrentenkaart', dash('health', week), 'bronnen en omvang in het dashboard')}
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:13.5px">{''.join(rijen)}</table>
</div>""")

    # prijspositie
    pr = m["prijs"]
    if pr["groepen"] and pr["kolommen"]:
        koppen = "".join(
            f'<th style="font-weight:600;font-size:11.5px;color:#555;text-align:center;padding:4px 2px">{h(m["names"].get(r, r))}{"*" if pr["stand"].get(r) and pr["stand"][r] != week else ""}</th>'
            for r in pr["kolommen"])
        body = []
        for g in pr["groepen"]:
            cellen = []
            for r in pr["kolommen"]:
                c = pr["cellen"].get((g, r), {})
                if not c.get("index"):
                    cellen.append('<td style="text-align:center;padding:7px 2px;color:#9a9a9a">–</td>')
                else:
                    cellen.append(f'<td style="text-align:center;padding:7px 2px;background:{KLEUR[c["klasse"]]};border-radius:3px">'
                                  f'{c["teken"]} {c["index"]}{" " + c["pijl"] if c["pijl"] else ""}</td>')
            body.append(f'<tr><td style="text-align:left;padding:7px 0;font-size:13px">{h(S.groep_naam(*g))}</td>{"".join(cellen)}</tr>')
        sterren = [f"{h(m['names'].get(r, r))}: stand {S.week_label(w)}" for r, w in pr["stand"].items() if w and w != week]
        ster = (" · * " + "; ".join(sterren)) if sterren else ""
        delen.append(f"""
<div style="{P}">{_kop('3 ·', f'Prijspositie per stuk ({m["names"].get(EIGEN, EIGEN)} = 100)', dash('prijsindex', week, perstuk=1), 'prijsindex in het dashboard')}
  <table role="presentation" width="100%" cellpadding="0" cellspacing="2" style="border-collapse:separate;font-size:13px"><tr><th style="text-align:left;font-size:11.5px;color:#555">Groep</th>{koppen}</tr>{''.join(body)}</table>
  <div style="font-size:12px;color:#555;margin-top:8px">▼ concurrent goedkoper (&lt; 90) · ● gelijk (90–110) · ▲ concurrent duurder (&gt; 110) · ↑↓ meer dan {S.PIJL_PUNTEN} punten verschoven sinds vier weken terug{ster}</div>
</div>""")

    # trendtegels
    tegels = "".join(
        f'<td width="33%" style="vertical-align:top;padding:0 4px"><div style="border:1px solid #e4e4e4;padding:10px 12px">'
        f'<div style="font-size:12px;color:#555">{h(t["label"])}</div>'
        f'<div style="font-size:26px;font-weight:600;line-height:1.1;margin:2px 0">{h(t["waarde"])}</div>'
        f'<div style="font-size:12px;color:#444">{_spark(t["spark"])} {h(t["duiding"])}</div></div></td>'
        for t in m["tegels"])
    delen.append(f"""
<div style="{P}">{_kop('4 ·', f'Trendlijnen, {TREND_WEKEN} weken', dash('movers', week), 'prijsverlagingen in het dashboard')}
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{tegels}</tr></table>
</div>""")

    # trendwoorden
    if m["trendwoorden"]:
        w = ", ".join(f"{h(x['woord'])} ({x['bronnen']} bronnen, {x['n']} art.{', nieuw' if x.get('nieuw') else ''})"
                      for x in m["trendwoorden"][:6])
        delen.append(f"""
<div style="{P}">{_kop('', 'Trendwoorden in de instroom', dash('instroom', week), 'nieuw deze week in het dashboard')}
  <p style="font-size:13.5px;margin:0">Woorden die deze week bij twee of meer bronnen in nieuwe artikelen opduiken; <i>nieuw</i> = kwam de vier weken ervoor niet in de instroom voor: {w}.</p>
</div>""")

    # spiegel
    if not m["rustig"]:
        sp = m["spiegel"]
        li = "".join(f'<li style="margin:0 0 6px">{h(r)}</li>' for r in sp["regels"])
        delen.append(f"""
<div style="{P}">{_kop('5 ·', f'Spiegel: {m["names"].get(EIGEN, EIGEN)} zelf', sp["link"], 'artikel-explorer')}
  <ul style="margin:0;padding-left:18px;font-size:14px">{li}<li style="margin:0 0 6px">{h(sp["vraag"])}</li></ul>
</div>""")

    # terugblik
    if m["terugblik"]:
        li = "".join(
            f'<li style="margin:0 0 6px"><b>{h(t["uitkomst"][0].upper() + t["uitkomst"][1:])}</b> · {h(t["tekst"])}'
            + (f' → nu {h(_waarde(t))}' if t.get("nu") is not None else "") + '</li>'
            for t in m["terugblik"])
        delen.append(f"""
<div style="{P}">{_kop('', f'Terugblik op {S.week_label(m["vorige"])}', None)}
  <ul style="margin:0;padding:0;list-style:none;font-size:13.5px">{li}</ul>
</div>""")

    # agenda
    teller = m["actieteller"]
    if m["rustig"]:
        agenda_html = '<p style="font-size:14px;margin:0">Geen agendapunt uit de monitor deze week.</p>'
    else:
        agenda_html = '<ol style="margin:0;padding-left:22px;font-size:14.5px">' + "".join(
            f'<li style="margin:0 0 8px">{h(p)}</li>' for p in m["agenda"]) + "</ol>"
    delen.append(f"""
<div style="{P}">{_kop('6 ·', 'Voor maandag 09:15', None)}
  {agenda_html}
  <div style="margin-top:12px;padding:10px 12px;background:#f4f4f2;font-size:13.5px">Antwoord op deze mail met <b>1</b>, <b>2</b> of <b>3</b> (of een eigen punt): dat is het besluit van deze week en komt in het besluitenlog. Actieteller: {teller['geteld']} van de laatste {teller['van']} weken vastgelegd.</div>
</div>""")

    # voet
    rood_noot = ""
    if m["rood"]:
        rood_noot = " Niet gemeten deze week: " + ", ".join(h(n) for n, _ in m["rood"]) + "; getoonde cijfers van die bron zijn van de laatste goede week."
    delen.append(f"""
<div style="padding:16px 22px 20px;border-top:1px solid #e4e4e4;font-size:12px;color:#555">
  <div style="margin:0 0 6px"><a href="{h(m['rapport_url'])}" style="color:#0e6b70">Volledig weekrapport {h(m['label'])}</a> · <a href="{h(m['dashboard_url'])}" style="color:#0e6b70">Dashboard (inloglink)</a> · CSV-export via de artikelview in Supabase</div>
  <div style="margin:0 0 6px">Samengesteld op {h(m['samengesteld'])} uit de weekrun. Cijfers betreffen het online assortiment: trendindicatie, geen winkeltelling. Prijs per stuk = prijs ÷ aantal in de verpakking.{rood_noot}</div>
  <div>Vragen of een ander agendapunt? Antwoord op deze mail.</div>
</div>""")

    body = "".join(delen)
    return f"""<!doctype html>
<html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"><title>{h(m['onderwerp'])}</title>
<style>
  body {{ margin:0; background:#e9ebee; }}
  .mail {{ width:100%; max-width:600px; margin:0 auto; background:#ffffff; color:#1a1a1a;
           font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; font-size:15px; line-height:1.5; border:1px solid #d9d9d9; }}
  a {{ color:#0e6b70; }}
  @media (max-width:560px) {{ .mail td[width="33%"] {{ display:block; width:100% !important; padding:0 0 8px !important; }} }}
  @media (prefers-color-scheme: dark) {{ body {{ background:#101416; }} }}
</style></head>
<body><div style="padding:16px 8px"><div class="mail">{body}</div></div></body></html>"""


def _waarde(t: dict) -> str:
    if t["soort"] == "omvang":
        return str(int(t["nu"]))
    if t["soort"] == "sale":
        return S.pct(t["nu"])
    return S.eur(t["nu"])


# --- platte tekst --------------------------------------------------------
def render_text(m: dict) -> str:
    week = m["week"]
    r: list[str] = []
    r.append(f"CONCURRENTIEMONITOR TERSTAL - WEEKMAIL {week.isocalendar()[1]}")
    r.append(f"Peildatum ma {week.strftime('%d-%m-%Y')}. Trend over {TREND_WEKEN} weken.")
    if m["storing"]:
        r.append("STORING in de weekrun: laatst verwerkte stand per bron. Kijk in GitHub Actions.")
    elif m["rood"]:
        r.append(f"Bronnen: {m['ok']} van {m['totaal']} ok. Niet gemeten: "
                 + "; ".join(f"{n} ({note})" for n, note in m["rood"]) + ".")
    else:
        r.append(f"Bronnen: {m['ok']} van {m['totaal']} ok.")
    r.append("")
    if m["rustig"]:
        r.append("RUSTIGE WEEK: geen signalen boven de drempel.")
    else:
        r.append("1. IN DRIE ZINNEN")
        for s in m["top3"]:
            r.append(f"- {s['kop']}. {s['tekst']}. [{s['tag']}{' ' + str(s['weken']) + ' wk' if s['weken'] >= 2 else ''}]")
    r.append("")
    r.append("2. CONCURRENTENKAART (sale-druk / omvang)")
    for k in m["kaart"]:
        wl = "" if k["gemeten_deze_week"] else (f" ({S.week_label(k['laatste_week'])})" if k["laatste_week"] else "")
        cijfers = f"{S.pct(k['sale']) if k['sale'] is not None else '-'} / {int(k['omvang']) if k['omvang'] else '-'}{wl}"
        r.append(f"{k['naam']:<9}{k['hoofdlijn']}{'; ' + k['bijzin'] if k['bijzin'] else ''}  [{cijfers}]")
    r.append("")
    pr = m["prijs"]
    if pr["groepen"] and pr["kolommen"]:
        r.append(f"3. PRIJSPOSITIE PER STUK ({m['names'].get(EIGEN, EIGEN)} = 100; < 90 goedkoper, > 110 duurder)")
        namen = [m["names"].get(c, c)[:8] + ("*" if pr["stand"].get(c) and pr["stand"][c] != week else "") for c in pr["kolommen"]]
        r.append(f"{'':<24}" + "".join(f"{n:>9}" for n in namen))
        for g in pr["groepen"]:
            cellen = []
            for c in pr["kolommen"]:
                x = pr["cellen"].get((g, c), {})
                cellen.append(f"{(str(x['index']) + x['pijl']) if x.get('index') else '-':>9}")
            r.append(f"{S.groep_naam(*g)[:24]:<24}" + "".join(cellen))
        sterren = [f"{m['names'].get(c, c)} stand {S.week_label(w)}" for c, w in pr["stand"].items() if w and w != week]
        if sterren:
            r.append("* " + "; ".join(sterren) + ".")
        r.append("")
    r.append("4. TRENDLIJNEN")
    for t in m["tegels"]:
        r.append(f"{t['label']}: {t['waarde']} ({t['duiding']})")
    if m["trendwoorden"]:
        r.append("Trendwoorden instroom: " + ", ".join(
            f"{w['woord']} ({w['bronnen']} bronnen{', nieuw' if w.get('nieuw') else ''})" for w in m["trendwoorden"][:6]))
    r.append("")
    if not m["rustig"]:
        r.append(f"5. SPIEGEL {m['names'].get(EIGEN, EIGEN).upper()}")
        r.extend(m["spiegel"]["regels"])
        r.append(m["spiegel"]["vraag"])
        r.append("")
    if m["terugblik"]:
        r.append(f"TERUGBLIK {S.week_label(m['vorige'])}")
        for t in m["terugblik"]:
            r.append(f"{t['uitkomst'][0].upper() + t['uitkomst'][1:]}: {t['tekst']}"
                     + (f" -> nu {_waarde(t)}" if t.get("nu") is not None else ""))
        r.append("")
    r.append("6. VOOR MAANDAG 09:15")
    if m["rustig"]:
        r.append("Geen agendapunt uit de monitor deze week.")
    else:
        for i, p in enumerate(m["agenda"], 1):
            r.append(f"{i}) {p}")
    tl = m["actieteller"]
    r.append(f"Antwoord met 1, 2 of 3. Actieteller: {tl['geteld']}/{tl['van']} weken.")
    r.append("")
    r.append(f"Weekrapport: {m['rapport_url']}")
    r.append(f"Dashboard: {m['dashboard_url']}")
    r.append(f"Samengesteld {m['samengesteld']}. Online assortiment, trendindicatie, geen winkeltelling.")
    return "\n".join(r)


# --- schrijven en versturen -----------------------------------------------
def write_weekmail(week: date, send: bool = True, to: str | None = None) -> Path:
    db = Db()
    m = build_model(week, db)
    html_body, text_body = render_html(m), render_text(m)
    REPORTS_DIR.mkdir(exist_ok=True)
    iso_year, iso_week, _ = week.isocalendar()
    path = REPORTS_DIR / f"{iso_year}-W{iso_week:02d}.html"
    path.write_text(html_body, encoding="utf-8")
    (REPORTS_DIR / "weekmail-latest.html").write_text(html_body, encoding="utf-8")
    top3 = [{k: v for k, v in s.items() if k in ("rid", "bron", "aud", "ptype", "soort", "richting",
                                                   "van", "naar", "tekst", "kop", "weken", "tag")}
            for s in m["top3"]]
    LAATSTE_JSON.write_text(json.dumps({"week": week.isoformat(), "onderwerp": m["onderwerp"],
                                        "top3": top3}, ensure_ascii=False, indent=1, default=str),
                            encoding="utf-8")
    uitkomst = "niet verstuurd (--dry-run)"
    if send:
        uitkomst = send_email(m["onderwerp"], html=html_body, text=text_body, to=to,
                              reply_to=env("REPORT_EMAIL_REPLY_TO") or None)
    print(uitkomst)
    try:
        db.save_weekmail({"week": week.isoformat(), "subject": m["onderwerp"], "html": html_body,
                          "text": text_body, "top3": top3,
                          "sent_to": 0 if not send else len([t for t in (to or env("REPORT_EMAIL_TO") or "").split(",") if t.strip()]),
                          "status": uitkomst[:200]})
    except DbError as e:
        print(f"weekmail niet in de database bewaard (draai sql/migratie_weekmail.sql): {e}")
    print(f"Weekmail geschreven: {path}")
    return path
