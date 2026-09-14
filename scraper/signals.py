"""Signalen voor de weekmail: rangschikken, ruis eruit, trend herkennen.

Alles hier is zuiver: functies op rijen uit `weekly_stats`,
`v_retailer_week_totals`, `scrape_runs` en `products`, zonder database of
netwerk. De weekmail (weekmail.py) haalt de data op en zet de uitkomsten in
HTML en platte tekst; het weekrapport (report.py) blijft ongewijzigd.

Ontwerp: docs/weekmail-voorstel.md §4. De drempels staan hier bovenaan, zodat
ze in de proefweken zonder graven af te stellen zijn.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import date

from .report import COUNT_SIGNAL, ENTRY_SIGNAL, MEDIAN_SIGNAL, SALE_SIGNAL

# --- drempels weekmail ---------------------------------------------------
MIN_GROUP_MAIL = 15      # kleinere groepen halen de top-3 en de onderwerpregel niet
PERSISTENTIE = {1: 1.0, 2: 1.5, 3: 2.0}   # nieuw / houdt aan / trend
VERPAKKING_MEDIAAN = 0.25   # artikelprijs ≥ +25% ...
VERPAKKING_UNIT = 0.05      # ... terwijl de prijs per stuk binnen ±5% blijft ...
VERPAKKING_MULTIPACK = 0.30 # ... en het multipack-aandeel ≥ 30 punten springt
OPRUIMING_SALE = 0.60       # groep met ≥ 60% afgeprijsd = opruiming
UITBOUW = 0.25              # groep ±25% in ≤ 2 weken (en ≥ 20 artikelen)
STILLE_INFLATIE = 0.10      # instapniveau ≥ +10% in ≤ 4 weken, in stappen
KRIMP_WEKEN = 4             # omvang 4+ weken op rij niet gestegen ...
KRIMP_DALING = 0.10         # ... en in totaal ≥ 10% lager
DRAAIDEUR = 0.40            # in- én uitstroom ≥ 40% van de omvang
PIJL_PUNTEN = 10            # prijsindex ≥ 10 punten verschoven sinds 4 weken terug
TREND_MIN_BRONNEN = 2       # een trendwoord telt bij ≥ 2 bronnen
TREND_MIN_LENGTE = 5
OMVANG_MIN_ABS = 10         # een omvangsignaal haalt de top-3 pas vanaf 10 artikelen verschil

BLOKJES = "▁▂▃▄▅▆▇█"

STOPWOORDEN = {
    "dames", "heren", "meisjes", "jongens", "kinder", "kinderen", "baby", "stuks",
    "paar", "katoen", "zwart", "multi", "maat", "sokken", "set", "pack", "stuk",
    "wit", "blauw", "grijs", "roze", "groen", "rood", "beige", "bruin", "lichtblauw",
    "donkerblauw", "print", "effen", "basic", "basics", "online", "alleen", "nieuw",
    "kleur", "kleuren", "voor", "van", "met", "zonder", "extra", "lang", "kort",
    "lange", "korte", "katoenen", "delig", "-delig", "stretch",
    # producttypen die élke week instromen: geen seizoenssignaal
    "pyjama", "pyjamas", "pyjama's", "pyjamaset", "pyjamabroek", "nachthemd", "slip", "slips",
    "boxershort", "boxershorts", "boxer", "boxers", "hipster", "hipsters", "string", "strings",
    "shirt", "shirts", "hemd", "hemden", "panty", "pantys", "panty's", "sokjes", "kousen",
    "beha", "bh's", "onesie", "shortama", "romper", "rompers",
}


# --- hulpjes -------------------------------------------------------------
def week_label(d: date) -> str:
    return f"W{d.isocalendar()[1]:02d}"


def sparkline(values: list[float | None]) -> str:
    """Tekst-sparkline (▁▂▃▅▇): werkt in elke mailclient, ook zonder plaatjes."""
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    out = []
    for v in values:
        if v is None:
            out.append("·")
            continue
        pos = 0 if hi == lo else round((float(v) - lo) / (hi - lo) * (len(BLOKJES) - 1))
        out.append(BLOKJES[pos])
    return "".join(out)


def eur(v) -> str:
    return "–" if v is None else f"€{float(v):.2f}".replace(".", ",")


def pct(v, digits: int = 0) -> str:
    return "–" if v is None else f"{float(v) * 100:.{digits}f}%"


def _f(v) -> float | None:
    return None if v is None else float(v)


def groep_naam(aud: str, ptype: str) -> str:
    return f"{aud} / {ptype}"


def korte_reden(note) -> str:
    """De storingsnotitie van een run in een paar woorden, zonder URL."""
    note = str(note or "")
    if "403" in note:
        return "HTTP 403, bot-bescherming"
    if "teller" in note:
        return "tellercontrole"
    if "<50%" in note or "minimum" in note:
        return "te weinig artikelen"
    kort = re.sub(r"https?://\S+", "", note).split(";")[0].strip(" (:-")
    return (kort[:57] + "…") if len(kort) > 60 else (kort or "geen run")


def by_key(rows: list[dict]) -> dict[tuple[str, str, str], dict]:
    return {(r["retailer_id"], r["audience"], r["product_type"]): r for r in rows}


# --- 4.1 signaalscore met persistentie -----------------------------------
def _richting(cv, pv, drempel, absoluut=False):
    """(+1|-1|0, delta) — delta relatief, of in punten bij absoluut."""
    if cv is None or pv is None:
        return 0, 0.0
    cv, pv = float(cv), float(pv)
    if absoluut:
        d = cv - pv
    else:
        if pv == 0:
            return 0, 0.0
        d = (cv - pv) / pv
    if abs(d) < drempel:
        return 0, d
    return (1 if d > 0 else -1), d


def signalen(weeks: list[date], stats: dict[date, list[dict]], names: dict[str, str],
             status: dict[str, str]) -> list[dict]:
    """Signalen van de laatste week t.o.v. de week ervoor, met persistentie.

    `weeks` oplopend; de laatste is de weekmailweek. Persistentie kijkt terug:
    dezelfde richting ook in de vergelijking ervoor = 'houdt aan', twee keer
    = 'trend'. Elk signaal draagt `betrouwbaar` (groep groot genoeg en bron
    ok) en, bij een prijssprong die alleen in de artikelprijs zit,
    `verpakkingswissel`.
    """
    if len(weeks) < 2:
        return []
    keyed = [by_key(stats.get(w, [])) for w in weeks]
    cur, prv = keyed[-1], keyed[-2]
    soorten = (
        ("omvang", "active_count", COUNT_SIGNAL, False),
        ("mediaan", "price_median", MEDIAN_SIGNAL, False),
        ("instap", "price_p25", ENTRY_SIGNAL, False),
        ("sale", "sale_share", SALE_SIGNAL, True),
    )
    out: list[dict] = []
    for key, c in cur.items():
        p = prv.get(key)
        if not p:
            continue
        rid, aud, ptype = key
        n, pn = int(c["active_count"]), int(p["active_count"])
        for soort, veld, drempel, absoluut in soorten:
            if soort == "omvang":
                if max(n, pn) < 8 or pn == 0:
                    continue
                r, d = _richting(n, pn, drempel)
                if not r or abs(n - pn) < 5:
                    continue
            else:
                if min(n, pn) < 8:
                    continue
                r, d = _richting(c.get(veld), p.get(veld), drempel, absoluut)
                if not r:
                    continue
            # persistentie: dezelfde richting in eerdere vergelijkingen?
            weken = 1
            for i in range(len(keyed) - 2, 0, -1):
                a, b = keyed[i].get(key), keyed[i - 1].get(key)
                if not a or not b:
                    break
                if soort == "omvang":
                    r2, _ = _richting(a["active_count"], b["active_count"], drempel / 2)
                else:
                    r2, _ = _richting(a.get(veld), b.get(veld), drempel / 2, absoluut)
                if r2 != r:
                    break
                weken += 1
            weken = min(weken, 3)
            verpakking = False
            if soort in ("mediaan", "instap") and r > 0 and d >= VERPAKKING_MEDIAAN:
                cu, pu = _f(c.get("unit_price_median")), _f(p.get("unit_price_median"))
                cm, pm = _f(c.get("multipack_share")) or 0.0, _f(p.get("multipack_share")) or 0.0
                if cu and pu and abs(cu - pu) / pu <= VERPAKKING_UNIT \
                        and cm - pm >= VERPAKKING_MULTIPACK:
                    verpakking = True
            betrouwbaar = min(n, pn) >= MIN_GROUP_MAIL and status.get(rid, "ok") == "ok" \
                and (soort != "omvang" or abs(n - pn) >= OMVANG_MIN_ABS)
            score = abs(d) * 100 * math.log(n + 1) * PERSISTENTIE[weken]
            if verpakking:
                score *= 0.3
            van = p.get(veld) if soort != "omvang" else pn
            naar = c.get(veld) if soort != "omvang" else n
            out.append({
                "rid": rid, "bron": names.get(rid, rid), "aud": aud, "ptype": ptype,
                "soort": soort, "richting": r, "delta": d, "van": van, "naar": naar,
                "n": n, "weken": weken, "tag": {1: "nieuw", 2: "houdt aan", 3: "trend"}[weken],
                "betrouwbaar": betrouwbaar, "verpakkingswissel": verpakking,
                "score": score, "tekst": _signaal_tekst(names.get(rid, rid), aud, ptype,
                                                       soort, r, d, van, naar, verpakking),
            })
    out.sort(key=lambda s: s["score"], reverse=True)
    return out


def _signaal_tekst(bron, aud, ptype, soort, r, d, van, naar, verpakking) -> str:
    g = groep_naam(aud, ptype)
    if soort == "omvang":
        if r > 0:
            return f"{bron} breidt {g} uit van {van} naar {naar} artikelen ({d:+.0%})"
        return f"{bron} saneert {g} van {van} naar {naar} artikelen ({d:+.0%})"
    if soort == "sale":
        werk = "stijgt" if r > 0 else "daalt"
        return f"{bron}: sale-druk {g} {werk} van {pct(van)} naar {pct(naar)}"
    naam = "mediaanprijs" if soort == "mediaan" else "instapniveau"
    if verpakking:
        return (f"{bron} toont {g} als verpakkingsprijs: {naam} van {eur(van)} naar "
                f"{eur(naar)}, per stuk ongewijzigd")
    werk = "omhoog" if r > 0 else "omlaag"
    return f"{bron}: {naam} {g} {werk} van {eur(van)} naar {eur(naar)} ({d:+.0%})"


def top3(sigs: list[dict], eigen: str = "terstal") -> list[dict]:
    """Drie zinnen: twee concurrentsignalen plus het sterkste eigen signaal.

    Alleen betrouwbare signalen (groep ≥ MIN_GROUP_MAIL, bron ok) en geen
    verpakkingswissels. Is er geen eigen signaal, dan drie van concurrenten.
    """
    goed = [s for s in sigs if s["betrouwbaar"] and not s["verpakkingswissel"]]
    conc = [s for s in goed if s["rid"] != eigen]
    own = [s for s in goed if s["rid"] == eigen]
    gekozen: list[dict] = []
    gezien: set[tuple] = set()
    plekken = 2 if own else 3
    # Eerst per concurrent het sterkste signaal (twee KiK-zinnen zeggen minder
    # dan één KiK- en één C&A-zin), daarna aanvullen op score.
    for ronde in ("per_bron", "op_score"):
        for s in conc:
            k = (s["rid"], s["aud"], s["ptype"])
            if k in gezien or (ronde == "per_bron" and any(g["rid"] == s["rid"] for g in gekozen)):
                continue
            gezien.add(k)
            gekozen.append(s)
            if len(gekozen) == plekken:
                break
        if len(gekozen) == plekken:
            break
    if own:
        gekozen.append(own[0])
    if len(gekozen) < 3:
        for s in conc:
            if s in gekozen:
                continue
            gekozen.append(s)
            if len(gekozen) == 3:
                break
    return gekozen[:3]


# --- 4.3 trendwoorden op instroom ----------------------------------------
def _woorden(titels: list[tuple[str, str]]) -> dict[str, Counter]:
    per_woord: dict[str, Counter] = defaultdict(Counter)
    for rid, titel in titels:
        for w in re.split(r"\s+", (titel or "").lower()):
            w = re.sub(r"[^a-zà-ÿ-]", "", w).strip("-")
            if len(w) < TREND_MIN_LENGTE or w in STOPWOORDEN:
                continue
            per_woord[w][rid] += 1
    return per_woord


def trendwoorden(nieuwe_titels: list[tuple[str, str]], eerdere_titels: list[tuple[str, str]] | None = None,
                 top: int = 8) -> list[dict]:
    """Woorden die deze week bij ≥ 2 bronnen in nieuwe artikeltitels opduiken.

    `nieuw` = het woord kwam in de instroom van de weken ervoor bij minder dan
    twee bronnen voor: dat is het seizoenssignaal (kerstpyjama, thermo), niet
    het woord dat elke week instroomt.
    """
    per_woord = _woorden(nieuwe_titels)
    eerder = _woorden(eerdere_titels or [])
    rows = [{"woord": w, "bronnen": len(c), "n": sum(c.values()),
             "nieuw": len(eerder.get(w, ())) < TREND_MIN_BRONNEN}
            for w, c in per_woord.items() if len(c) >= TREND_MIN_BRONNEN]
    rows.sort(key=lambda r: (r["nieuw"], r["bronnen"], r["n"]), reverse=True)
    return rows[:top]


# --- 4.5 concurrentenkaart uit sjablonen ---------------------------------
def _reeks(totals_by_week: dict[date, dict[str, dict]], weeks: list[date], rid: str, veld: str):
    return [_f((totals_by_week.get(w, {}).get(rid) or {}).get(veld)) for w in weeks]


def kaart_regel(rid: str, weeks: list[date], stats: dict[date, list[dict]],
                totals: dict[date, dict[str, dict]], run: dict, sigs: list[dict],
                names: dict[str, str]) -> dict:
    """Eén rij voor de concurrentenkaart: hoofdlijn, bijzin, sinds, reeksen."""
    naam = names.get(rid, rid)
    laatste6 = weeks[-6:]
    sale_reeks = _reeks(totals, laatste6, rid, "sale_share")
    omvang_reeks = _reeks(totals, laatste6, rid, "active_count")
    status = run.get("status", "geen run")
    kandidaten: list[tuple[float, str, str]] = []   # (score, tekst, sinds)

    # laatste week mét cijfers voor deze bron
    laatste_w = next((w for w in reversed(weeks) if totals.get(w, {}).get(rid)), None)
    tot = totals.get(laatste_w, {}).get(rid, {}) if laatste_w else {}
    n = tot.get("active_count")
    sale = _f(tot.get("sale_share"))

    if status != "ok":
        kort = korte_reden(run.get("note") or status)
        if laatste_w and n:
            n_txt = f"{int(n):,}".replace(",", ".")
            kandidaten.append((1000.0,
                f"Geen meting deze week ({kort}). Laatste beeld {week_label(laatste_w)}: "
                f"{n_txt} artikelen, {pct(sale)} sale.",
                f"bron rood sinds {week_label(weeks[-1])}"))
        else:
            kandidaten.append((1000.0, f"Geen meting ({kort}) en geen eerdere stand.", ""))

    # sale-trend: drie weken dezelfde kant op
    s3 = [v for v in sale_reeks[-3:] if v is not None]
    if len(s3) == 3 and (s3[0] > s3[1] > s3[2] or s3[0] < s3[1] < s3[2]) \
            and abs(s3[2] - s3[0]) >= 0.03:
        werk = "daalt" if s3[2] < s3[0] else "stijgt"
        kandidaten.append((abs(s3[2] - s3[0]) * 100 * 2,
            f"Sale-druk {werk} voor de derde week ({pct(s3[0])} → {pct(s3[1])} → {pct(s3[2])})",
            f"sinds {week_label(laatste6[-3])}"))

    # per groep: opruiming, uitbouw/sanering, stille inflatie
    keyed = [by_key(stats.get(w, [])) for w in weeks]
    groepen = {k for k in keyed[-1] if k[0] == rid} if keyed else set()
    for key in sorted(groepen):
        _, aud, ptype = key
        c = keyed[-1][key]
        cn = int(c["active_count"])
        if cn < MIN_GROUP_MAIL:
            continue
        g = groep_naam(aud, ptype)
        cs = _f(c.get("sale_share"))
        if cs is not None and cs >= OPRUIMING_SALE:
            kandidaten.append((cs * 100,
                f"{g[0].upper()}{g[1:]} {pct(cs)} afgeprijsd, mediaan {eur(c.get('price_median'))}",
                ""))
        if len(keyed) >= 3:
            b = keyed[-3].get(key)
            if b and int(b["active_count"]) >= 8:
                bn = int(b["active_count"])
                d = (cn - bn) / bn
                if abs(d) >= UITBOUW and abs(cn - bn) >= 20:
                    m = keyed[-2].get(key)
                    tussen = f" → {int(m['active_count'])}" if m else ""
                    werk = "Bouwt" if d > 0 else "Saneert"
                    kandidaten.append((abs(d) * 100,
                        f"{werk} {g} {'uit' if d > 0 else 'af'}: {bn}{tussen} → {cn} in twee weken",
                        f"sinds {week_label(weeks[-3])}"))
        if len(keyed) >= 4:
            p25 = [_f(k.get(key, {}).get("price_p25")) for k in keyed[-4:]]
            # Per stuk moet mee omhoog: anders is het een verpakkingswissel (KiK W36).
            up25 = [_f(k.get(key, {}).get("unit_price_p25")) for k in keyed[-4:]]
            per_stuk_mee = (any(v is None for v in up25) or up25[0] == 0
                            or (up25[-1] - up25[0]) / up25[0] >= STILLE_INFLATIE / 2)
            if all(v is not None for v in p25) and p25[0] > 0 and per_stuk_mee:
                stappen = sum(1 for a, b in zip(p25, p25[1:]) if b > a)
                nooit_omlaag = all(b >= a for a, b in zip(p25, p25[1:]))
                stijging = (p25[-1] - p25[0]) / p25[0]
                if stappen >= 2 and nooit_omlaag and stijging >= STILLE_INFLATIE:
                    per_stuk = ""
                    if all(v is not None for v in up25) and up25[0]:
                        per_stuk = f" (per stuk {(up25[-1] - up25[0]) / up25[0]:+.0%})"
                    kandidaten.append((stijging * 100,
                        f"Instap {g} in vier weken van {eur(p25[0])} naar {eur(p25[-1])}{per_stuk}: stille inflatie",
                        f"sinds {week_label(weeks[-4])}"))

    # krimp over ≥ 4 weken: de omvang komt nooit boven de startstand, eindigt op
    # het laagste punt en ligt ≥ KRIMP_DALING lager. Een kleine opleving
    # onderweg (Wibra W35: 123 → 126) breekt de reeks niet.
    om = [v for v in omvang_reeks if v is not None]
    for k in range(len(om) - 1, KRIMP_WEKEN - 1, -1):
        venster = om[-(k + 1):]
        if all(v <= venster[0] for v in venster[1:]) and venster[-1] == min(venster)                 and venster[-1] < (1 - KRIMP_DALING) * venster[0]:
            kandidaten.append(((venster[0] - venster[-1]) / venster[0] * 100,
                f"Krimpt online al {k} weken ({int(venster[0])} → {int(venster[-1])})",
                f"sinds {week_label(laatste6[-(k + 1)]) if k + 1 <= len(laatste6) else week_label(weeks[-(k + 1)])}"))
            break

    # draaideur
    if n and tot.get("new_count") is not None and tot.get("gone_count") is not None \
            and laatste_w == weeks[-1]:
        i, u = int(tot["new_count"]) / n, int(tot["gone_count"]) / n
        if i >= DRAAIDEUR and u >= DRAAIDEUR:
            kandidaten.append(((i + u) * 50,
                f"Online een draaideur: {i:.0%} in, {u:.0%} uit in één week; {pct(sale)} sale",
                ""))

    # verpakkingswissel uit de signalen
    vp = [s for s in sigs if s["rid"] == rid and s["verpakkingswissel"]]
    if vp:
        kandidaten.append((60.0,
            f"Toont sinds {week_label(weeks[-1])} verpakkingsprijzen ({groep_naam(vp[0]['aud'], vp[0]['ptype'])}): "
            f"artikelprijs omhoog, per stuk ongewijzigd", ""))

    # ruis: alleen kleine groepen en springende medianen
    eigen_groepen = [keyed[-1][k] for k in groepen] if groepen else []
    if eigen_groepen and all(int(g["active_count"]) < 30 for g in eigen_groepen) and len(keyed) >= 4:
        springt = [s for s in sigs if s["rid"] == rid and s["soort"] == "mediaan"]
        if springt:
            ns = [int(g["active_count"]) for g in eigen_groepen]
            kandidaten.append((10.0,
                f"Kleine groepen (grootste {max(ns)} artikelen); mediaan "
                f"{groep_naam(springt[0]['aud'], springt[0]['ptype'])} springt week op week: ruis, geen trend",
                "geen trend"))

    # prijsvast (fallback met inhoud)
    if n and laatste_w == weeks[-1] and len(keyed) >= 6:
        vast = []
        for key in groepen:
            reeks = [_f(k.get(key, {}).get("price_median")) for k in keyed[-6:]]
            if all(v is not None for v in reeks) and len(set(reeks)) == 1 \
                    and int(keyed[-1][key]["active_count"]) >= MIN_GROUP_MAIL:
                vast.append((int(keyed[-1][key]["active_count"]), key, reeks[0]))
        if vast:
            vast.sort(reverse=True)
            _, key, med = vast[0]
            i = int(tot.get("new_count") or 0) / n
            u = int(tot.get("gone_count") or 0) / n
            kandidaten.append((5.0,
                f"Prijsvast ({groep_naam(key[1], key[2])} {eur(med)}, zes weken); doorloop {i:.0%} in, {u:.0%} uit",
                ""))

    if not kandidaten:
        if n:
            i = int(tot.get("new_count") or 0) / n
            u = int(tot.get("gone_count") or 0) / n
            kandidaten.append((0.0,
                f"Geen opvallende beweging: {n} artikelen, {pct(sale)} sale, {i:.0%} in, {u:.0%} uit", ""))
        else:
            kandidaten.append((0.0, "Nog geen meting.", ""))

    kandidaten.sort(key=lambda k: k[0], reverse=True)
    hoofd = kandidaten[0]
    bijzin = kandidaten[1][1] if len(kandidaten) > 1 and kandidaten[1][0] > 0 \
        and kandidaten[0][0] < 1000 else ""
    return {
        "rid": rid, "naam": naam, "status": status,
        "hoofdlijn": hoofd[1], "bijzin": bijzin, "sinds": hoofd[2],
        "sale_reeks": sale_reeks, "omvang_reeks": omvang_reeks,
        "sale_spark": sparkline(sale_reeks), "omvang_spark": sparkline(omvang_reeks),
        "sale": sale, "omvang": n, "laatste_week": laatste_w,
        "gemeten_deze_week": laatste_w == weeks[-1] and status == "ok",
    }


# --- 4.4 / blok 3: prijspositie per stuk ---------------------------------
def prijspositie(weeks: list[date], stats: dict[date, list[dict]], status: dict[str, str],
                 names: dict[str, str], eigen: str = "terstal", max_groepen: int = 5,
                 concurrenten: list[str] | None = None) -> dict:
    """Index per stuk (concurrent ÷ terStal × 100) voor de grootste groepen.

    Per concurrent geldt de laatste week met cijfers én status ok; staat een
    bron deze week rood, dan komt zijn laatste goede week met een asterisk.
    Pijl (↑/↓) als de index sinds vier weken terug ≥ PIJL_PUNTEN verschoof.
    """
    keyed = [by_key(stats.get(w, [])) for w in weeks]
    cur = keyed[-1]
    ref = keyed[-5] if len(keyed) >= 5 else {}
    eigen_cur = {(a, p): r for (rid, a, p), r in cur.items() if rid == eigen}
    if not eigen_cur:
        return {"groepen": [], "kolommen": [], "cellen": {}, "stand": {}}
    rids = concurrenten or sorted({rid for rid, _, _ in cur} | set(status), key=lambda r: names.get(r, r))
    rids = [r for r in rids if r != eigen]

    # stand per bron: index van de week waaruit zijn cijfers komen
    stand: dict[str, int] = {}
    for rid in rids:
        idx = len(weeks) - 1
        if status.get(rid, "ok") != "ok":
            idx = next((i for i in range(len(weeks) - 2, -1, -1)
                        if any(k[0] == rid for k in keyed[i])), -1)
        stand[rid] = idx

    def unit(r):
        return _f(r.get("unit_price_median")) or _f(r.get("price_median"))

    totalen: Counter = Counter()
    for (rid, a, p), r in cur.items():
        totalen[(a, p)] += int(r["active_count"])
    groepen = [g for g, _ in totalen.most_common()
               if g in eigen_cur and int(eigen_cur[g]["active_count"]) >= 8 and unit(eigen_cur[g])]
    groepen = groepen[:max_groepen]

    cellen: dict[tuple, dict] = {}
    for g in groepen:
        t = unit(eigen_cur[g])
        t_ref = unit(ref.get((eigen,) + g, {})) if ref else None
        for rid in rids:
            i = stand.get(rid, -1)
            row = keyed[i].get((rid,) + g) if i >= 0 else None
            if not row or int(row["active_count"]) < 8 or not unit(row):
                cellen[(g, rid)] = {"index": None}
                continue
            index = round(unit(row) / t * 100)
            pijl = ""
            r_ref = ref.get((rid,) + g) if ref else None
            if r_ref and t_ref and unit(r_ref) and int(r_ref["active_count"]) >= 8:
                oud = round(unit(r_ref) / t_ref * 100)
                if index - oud >= PIJL_PUNTEN:
                    pijl = "↑"
                elif oud - index >= PIJL_PUNTEN:
                    pijl = "↓"
            klasse = "lo" if index < 90 else ("hi" if index > 110 else "eq")
            cellen[(g, rid)] = {"index": index, "pijl": pijl, "klasse": klasse,
                                "teken": {"lo": "▼", "eq": "●", "hi": "▲"}[klasse]}
    kolommen = [r for r in rids if any(cellen.get((g, r), {}).get("index") for g in groepen)]
    return {"groepen": groepen, "kolommen": kolommen, "cellen": cellen,
            "stand": {r: weeks[stand[r]] if stand.get(r, -1) >= 0 else None for r in kolommen}}


# --- 4.6 terugblik --------------------------------------------------------
def terugblik(vorige_top3: list[dict], weeks: list[date], stats: dict[date, list[dict]],
              status: dict[str, str]) -> list[dict]:
    """De top-3 van vorige week opnieuw gemeten: houdt aan, teruggedraaid, niet meetbaar."""
    if not vorige_top3 or len(weeks) < 2:
        return []
    cur, prv = by_key(stats.get(weeks[-1], [])), by_key(stats.get(weeks[-2], []))
    veld = {"omvang": "active_count", "mediaan": "price_median",
            "instap": "price_p25", "sale": "sale_share"}
    out = []
    for s in vorige_top3:
        key = (s["rid"], s["aud"], s["ptype"])
        c, p = cur.get(key), prv.get(key)
        if status.get(s["rid"], "ok") != "ok" or not c or not p:
            out.append({**s, "uitkomst": "niet meetbaar", "nu": None})
            continue
        v = veld.get(s["soort"], "price_median")
        nu, toen, van = _f(c.get(v)), _f(p.get(v)), _f(s.get("van"))
        if nu is None or toen is None or van is None:
            out.append({**s, "uitkomst": "niet meetbaar", "nu": None})
            continue
        beweging = (toen - van) * s["richting"]          # wat vorige week bewoog
        terug = (nu - toen) * s["richting"]              # wat er deze week van overblijft
        if beweging > 0 and terug <= -0.5 * beweging:
            uitkomst = "teruggedraaid"
        else:
            uitkomst = "houdt aan"
        out.append({**s, "uitkomst": uitkomst, "nu": nu})
    return out


# --- 4.7 rustige week + onderwerpregel -----------------------------------
def is_rustig(gekozen: list[dict], status: dict[str, str]) -> bool:
    return not gekozen and all(v == "ok" for v in status.values())


def onderwerp(week: date, gekozen: list[dict], status: dict[str, str],
              kernwoorden: list[str] | None = None) -> str:
    ok = sum(1 for v in status.values() if v == "ok")
    tot = len(status)
    if is_rustig(gekozen, status):
        kern = "Rustige week, geen signalen boven de drempel"
    else:
        delen = list((kernwoorden or [s["kop"] for s in gekozen if s.get("kop")])[:3])
        # Mailclients tonen ±70–100 tekens; liever twee koppen leesbaar dan drie afgekapt.
        while len(delen) > 1 and len(" · ".join(delen)) > 80:
            delen.pop()
        kern = " · ".join(delen) or "Signalen van de week"
    return f"{week_label(week)} · {kern} · {ok}/{tot} bronnen ok"


def kop_uit_signaal(s: dict) -> str:
    """Korte kop voor de onderwerpregel, uit een signaal."""
    g = f"{s['aud']} {s['ptype']}"
    if s["soort"] == "omvang":
        return f"{s['bron']} breidt {g} uit" if s["richting"] > 0 else f"{s['bron']} saneert {g}"
    if s["soort"] == "sale":
        return f"{s['bron']} sale-druk {g} {'omhoog' if s['richting'] > 0 else 'omlaag'}"
    naam = "mediaan" if s["soort"] == "mediaan" else "instap"
    return f"{s['bron']} {naam} {g} {'omhoog' if s['richting'] > 0 else 'omlaag'}"
