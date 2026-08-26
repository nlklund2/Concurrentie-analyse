"""Weekrapport: het maandagochtend-document (markdown, optioneel per e-mail)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import requests

from .config import env, focus_product_types
from .db import Db

REPORTS_DIR = Path("reports")

MIN_GROUP = 8          # minimaal aantal artikelen voordat een groep 'meetelt'
COUNT_SIGNAL = 0.15    # ±15% omvangsverandering is een signaal
MEDIAN_SIGNAL = 0.05   # ±5% mediaanverschuiving is een signaal
ENTRY_SIGNAL = 0.08    # ±8% instapniveau (p25)
SALE_SIGNAL = 0.10     # +10 procentpunt sale-druk
MULTIPACK_MIN = 0.10   # vanaf 10% multipacks in een groep loont de per-stuk-index


def eur(v) -> str:
    return "–" if v is None else f"€{float(v):.2f}".replace(".", ",")


def pct(v) -> str:
    return "–" if v is None else f"{float(v) * 100:.0f}%"


def build(week: date) -> str:
    db = Db()
    retailers = db.retailers()
    stats = db.weekly_stats(week)
    all_weeks = db.weeks()
    prev_week = next((w for w in all_weeks if w < week), None)
    prev_stats = db.weekly_stats(prev_week) if prev_week else []
    totals = db.week_totals(week)
    prev_totals = db.week_totals(prev_week) if prev_week else {}
    runs = db.runs(week)

    def name(rid: str) -> str:
        return retailers.get(rid, {}).get("name", rid)

    def grp(rows) -> dict:
        return {(r["retailer_id"], r["audience"], r["product_type"]): r for r in rows}

    cur, prv = grp(stats), grp(prev_stats)
    iso_year, iso_week, _ = week.isocalendar()

    md: list[str] = []
    md.append(f"# Weekrapport concurrentiemonitor — week {iso_week}, {iso_year}")
    md.append(f"\n*Peildatum: maandag {week.strftime('%d-%m-%Y')}."
              f" Cijfers betreffen het online assortiment (trend-indicatie, geen winkeltelling).*\n")
    focus = focus_product_types()
    if focus:
        md.append(f"*Scope: ondergoedmode — {', '.join(focus)}.*\n")

    # ---- 1. Grondgezondheid ----
    md.append("## 1. Gezondheid van de bronnen\n")
    md.append("| Bron | Strategie | Deze run | In database | t.o.v. vorige week | Status |")
    md.append("|---|---|---:|---:|---:|---|")
    latest_run: dict[str, dict] = {}
    for r in runs:
        latest_run.setdefault(r["retailer_id"], r)  # runs staan al nieuwste-eerst
    for rid in sorted(set(list(totals) + list(latest_run))):
        run = latest_run.get(rid, {})
        tot = totals.get(rid, {})
        cur_n = tot.get("active_count")
        prev_n = (prev_totals.get(rid) or {}).get("active_count")
        delta = "–"
        if cur_n is not None and prev_n:
            d = (cur_n - prev_n) / prev_n
            delta = f"{d:+.0%}"
        status = run.get("status", "geen run")
        icon = {"ok": "🟢", "afwijkend": "🟠", "fout": "🔴"}.get(status, "⚪")
        note = f" — {run['note']}" if run.get("note") else ""
        run_n = run.get("products_found")
        md.append(f"| {name(rid)} | {run.get('strategy', '–')} "
                  f"| {run_n if run_n is not None else '–'} "
                  f"| {cur_n if cur_n is not None else '–'} "
                  f"| {delta} | {icon} {status}{note} |")
    md.append("\n> 🟠/🔴: cijfers van die bron deze week niet gebruiken voor besluiten.\n"
              "> *Deze run* is wat de scraper deze week ophaalde, *in database* de laatst "
              "verwerkte stand. Lopen die uiteen, dan heeft de kwaliteitspoort deze week "
              "tegengehouden en staat er nog oudere data.\n")

    # ---- 2. Signalen ----
    md.append("## 2. Signalen van de week\n")
    signals: list[tuple[float, str]] = []
    if prev_week:
        for key, c in cur.items():
            rid, aud, ptype = key
            p = prv.get(key)
            if not p:
                continue
            label = f"**{name(rid)}** · {aud} / {ptype}"
            c_n, p_n = c["active_count"], p["active_count"]
            if max(c_n, p_n) >= MIN_GROUP and p_n > 0:
                d = (c_n - p_n) / p_n
                if abs(d) >= COUNT_SIGNAL and abs(c_n - p_n) >= 5:
                    verb = "breidt uit" if d > 0 else "saneert"
                    signals.append((abs(d) * 100 + min(abs(c_n - p_n), 50),
                                    f"{label}: {verb} van {p_n} naar {c_n} artikelen ({d:+.0%})"))
            for field, drempel, naam in (("price_median", MEDIAN_SIGNAL, "mediaanprijs"),
                                         ("price_p25", ENTRY_SIGNAL, "instapniveau")):
                cv, pv = c.get(field), p.get(field)
                if cv and pv and min(c_n, p_n) >= MIN_GROUP:
                    d = (float(cv) - float(pv)) / float(pv)
                    if abs(d) >= drempel:
                        richting = "omhoog" if d > 0 else "omlaag"
                        signals.append((abs(d) * 200,
                                        f"{label}: {naam} {richting} van {eur(pv)} naar {eur(cv)} ({d:+.0%})"))
            cs, ps = c.get("sale_share"), p.get("sale_share")
            if cs is not None and ps is not None and c_n >= MIN_GROUP:
                d = float(cs) - float(ps)
                if abs(d) >= SALE_SIGNAL:
                    richting = "stijgt" if d > 0 else "daalt"
                    signals.append((abs(d) * 150,
                                    f"{label}: sale-druk {richting} van {pct(ps)} naar {pct(cs)}"))
    if signals:
        for _, text in sorted(signals, reverse=True)[:15]:
            md.append(f"- {text}")
    elif prev_week:
        md.append("- Geen opvallende verschuivingen boven de drempelwaarden.")
    else:
        md.append("- Eerste meting: signalen verschijnen vanaf volgende week "
                  "(er is nog geen vergelijkingsweek).")
    md.append("")

    # ---- 3. Grootste prijsverlagingen ----
    md.append("## 3. Grootste prijsverlagingen deze week\n")
    downs = db.events(week, ["price_down"])
    downs = [d for d in downs if d.get("prev_price") and d.get("price")]
    downs.sort(key=lambda d: (float(d["price"]) - float(d["prev_price"])) / float(d["prev_price"]))
    if downs:
        md.append("| Bron | Artikel | Van | Naar | Verschil |")
        md.append("|---|---|---:|---:|---:|")
        by_retailer: dict[str, list[dict]] = {}
        for d in downs[:60]:
            by_retailer.setdefault(d["retailer_id"], []).append(d)
        shown = 0
        for rid, items in by_retailer.items():
            titles = db.products_by_keys(rid, [i["product_key"] for i in items[:5]])
            for i in items[:5]:
                t = titles.get(i["product_key"], {})
                d_pct = (float(i["price"]) - float(i["prev_price"])) / float(i["prev_price"])
                md.append(f"| {name(rid)} | {t.get('title', i['product_key'])[:60]} "
                          f"| {eur(i['prev_price'])} | {eur(i['price'])} | {d_pct:+.0%} |")
                shown += 1
                if shown >= 15:
                    break
            if shown >= 15:
                break
    else:
        md.append("Geen prijsverlagingen geregistreerd.")
    md.append("")

    # ---- 4. Assortimentsomvang per productgroep ----
    md.append("## 4. Assortimentsomvang per groep (verschil t.o.v. vorige week)\n")
    group_totals: dict[tuple[str, str], int] = {}
    for (rid, aud, ptype), r in cur.items():
        group_totals[(aud, ptype)] = group_totals.get((aud, ptype), 0) + r["active_count"]
    top_groups = sorted(group_totals, key=group_totals.get, reverse=True)[:14]
    rids = sorted({rid for rid, _, _ in cur}, key=lambda r: (r != "terstal", r))
    md.append("| Groep | " + " | ".join(name(r) for r in rids) + " |")
    md.append("|---" * (len(rids) + 1) + "|")
    for aud, ptype in top_groups:
        cells = []
        for rid in rids:
            c = cur.get((rid, aud, ptype))
            p = prv.get((rid, aud, ptype))
            if not c:
                cells.append("–")
                continue
            cell = str(c["active_count"])
            if p:
                d = c["active_count"] - p["active_count"]
                if d:
                    cell += f" ({d:+d})"
            cells.append(cell)
        md.append(f"| {aud} / {ptype} | " + " | ".join(cells) + " |")
    md.append("")

    # ---- 5. Prijsindex t.o.v. terStal ----
    md.append("## 5. Prijsindex t.o.v. terStal (mediaan; terStal = 100)\n")
    ter = {(aud, ptype): r for (rid, aud, ptype), r in cur.items() if rid == "terstal"}
    if ter:
        md.append("| Groep | " + " | ".join(name(r) for r in rids if r != "terstal") + " |")
        md.append("|---" * len(rids) + "|")
        for aud, ptype in top_groups:
            t = ter.get((aud, ptype))
            if not t or not t.get("price_median") or t["active_count"] < MIN_GROUP:
                continue
            cells = []
            for rid in rids:
                if rid == "terstal":
                    continue
                c = cur.get((rid, aud, ptype))
                if c and c.get("price_median") and c["active_count"] >= MIN_GROUP:
                    idx = float(c["price_median"]) / float(t["price_median"]) * 100
                    cells.append(f"{idx:.0f}")
                else:
                    cells.append("–")
            md.append(f"| {aud} / {ptype} | " + " | ".join(cells) + " |")
        md.append("\n> Index < 100: concurrent is goedkoper dan terStal. Kompas, geen rechter "
                  "— kwaliteitsverschil is online onzichtbaar (PLAN.md §6.5).\n")
    else:
        md.append("Geen terStal-cijfers deze week — index niet te berekenen.\n")

    # ---- 5b. Prijsindex per stuk (multipacks eerlijk vergelijken) ----
    md.append("### 5b. Prijsindex per stuk (multipacks omgerekend; terStal = 100)\n")
    heeft_unit = any(r.get("unit_price_median") is not None for r in cur.values())
    if not heeft_unit:
        md.append("Nog geen per-stuk-cijfers. Die verschijnen vanaf de eerste week ná "
                  "`sql/migratie_prijs_per_stuk.sql` (PLAN.md §11.1).\n")
    elif not ter:
        md.append("Geen terStal-cijfers deze week — index niet te berekenen.\n")
    else:
        pack_groups = [g for g in top_groups
                       if any(float(r.get("multipack_share") or 0) >= MULTIPACK_MIN
                              for (rid, aud, ptype), r in cur.items() if (aud, ptype) == g)]
        if not pack_groups:
            md.append("Geen groep met noemenswaardig aandeel multipacks deze week.\n")
        else:
            md.append("| Groep | " + " | ".join(name(r) for r in rids if r != "terstal") + " |")
            md.append("|---" * len(rids) + "|")
            for aud, ptype in pack_groups:
                t_row = ter.get((aud, ptype))
                if not t_row or not t_row.get("unit_price_median") or t_row["active_count"] < MIN_GROUP:
                    continue
                cells = []
                for rid in rids:
                    if rid == "terstal":
                        continue
                    c = cur.get((rid, aud, ptype))
                    if c and c.get("unit_price_median") and c["active_count"] >= MIN_GROUP:
                        idx = float(c["unit_price_median"]) / float(t_row["unit_price_median"]) * 100
                        cells.append(f"{idx:.0f}")
                    else:
                        cells.append("–")
                md.append(f"| {aud} / {ptype} | " + " | ".join(cells) + " |")
            aandelen = []
            for rid in rids:
                waarden = [float(r["multipack_share"]) for (r_id, aud, ptype), r in cur.items()
                           if r_id == rid and r.get("multipack_share") is not None
                           and (aud, ptype) in pack_groups]
                if waarden:
                    aandelen.append(f"{name(rid)} {sum(waarden) / len(waarden) * 100:.0f}%")
            md.append("\n> Prijs per stuk = prijs ÷ aantal in de verpakking, afgeleid uit de "
                      "artikelnaam (3-pack, 5 paar). Alleen groepen waarin minstens één bron "
                      f"≥{MULTIPACK_MIN:.0%} multipacks voert. Aandeel multipacks in die groepen: "
                      + ", ".join(aandelen) + ".\n"
                      "> Wijkt deze index sterk af van §5, dan zit het prijsverschil in de "
                      "verpakkingsgrootte en niet in de prijs per stuk.\n")

    # ---- 6. Sale-druk ----
    md.append("## 6. Sale-druk per bron\n")
    md.append("| Bron | % afgeprijsd | t.o.v. vorige week |")
    md.append("|---|---:|---:|")
    for rid in rids:
        t = totals.get(rid, {})
        p = prev_totals.get(rid, {})
        cur_s, prev_s = t.get("sale_share"), p.get("sale_share")
        d = "–"
        if cur_s is not None and prev_s is not None:
            d = f"{(float(cur_s) - float(prev_s)) * 100:+.0f} pt"
        md.append(f"| {name(rid)} | {pct(cur_s)} | {d} |")
    md.append("")

    # ---- 7. Vernieuwingstempo (instroom/uitstroom als % van de omvang) ----
    md.append("## 7. Vernieuwingstempo per bron\n")
    md.append("| Bron | Omvang | Instroom deze week | Uitstroom deze week |")
    md.append("|---|---:|---:|---:|")
    for rid in rids:
        tot = totals.get(rid, {})
        n = tot.get("active_count")
        if not n:
            md.append(f"| {name(rid)} | – | – | – |")
            continue
        if rid not in prev_totals:
            # Eerste meetweek van een bron, of een week die de kwaliteitspoort
            # tegenhield: dan is 'nieuw' geen tempo maar een startstand.
            md.append(f"| {name(rid)} | {n} | geen vergelijkweek | geen vergelijkweek |")
            continue
        in_n, uit_n = tot.get("new_count") or 0, tot.get("gone_count") or 0
        md.append(f"| {name(rid)} | {n} | {in_n} ({in_n / n:.0%}) | {uit_n} ({uit_n / n:.0%}) |")
    md.append("\n> Instroom en uitstroom als aandeel van het eigen assortiment: wie hoog zit "
              "speelt op snelheid en nieuwheid, wie laag zit zit op voorraad. Ontbreekt de "
              "vorige week (eerste meting of tegengehouden door de kwaliteitspoort), dan "
              "zegt het percentage niets en blijft het leeg.\n")

    md.append("\n---\n*Automatisch gegenereerd. Dashboard: zie Netlify-site. "
              "Ruwe data: Actions-artifact van deze run.*")
    return "\n".join(md)


def send_email(subject: str, markdown_body: str) -> str:
    """Optioneel: via Resend (gratis tier). Stil overslaan zonder API-sleutel."""
    api_key = env("RESEND_API_KEY")
    to = env("REPORT_EMAIL_TO")
    if not api_key or not to:
        return "e-mail overgeslagen (RESEND_API_KEY/REPORT_EMAIL_TO niet gezet)"
    sender = env("REPORT_EMAIL_FROM") or "concurrentiemonitor <onboarding@resend.dev>"
    html = ("<pre style=\"font: 13px/1.5 ui-monospace, monospace; white-space: pre-wrap;\">"
            + markdown_body.replace("&", "&amp;").replace("<", "&lt;") + "</pre>")
    resp = requests.post(
        "https://api.resend.com/emails", timeout=60,
        headers={"Authorization": f"Bearer {api_key}"},
        json={"from": sender, "to": [t.strip() for t in to.split(",")],
              "subject": subject, "html": html})
    if resp.status_code >= 400:
        return f"e-mail mislukt: {resp.status_code} {resp.text[:200]}"
    return f"e-mail verstuurd naar {to}"


def write_report(week: date, send: bool = True) -> Path:
    body = build(week)
    REPORTS_DIR.mkdir(exist_ok=True)
    iso_year, iso_week, _ = week.isocalendar()
    path = REPORTS_DIR / f"{iso_year}-W{iso_week:02d}.md"
    path.write_text(body, encoding="utf-8")
    (REPORTS_DIR / "latest.md").write_text(body, encoding="utf-8")
    if send:
        print(send_email(f"Concurrentiemonitor week {iso_week}", body))
    print(f"Rapport geschreven: {path}")
    return path
