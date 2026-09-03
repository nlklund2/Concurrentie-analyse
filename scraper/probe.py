"""Validatie van bronnen: kleine proefscrape per bron, rapport in markdown.

Draait zonder database — bedoeld voor de "Validatie bronnen"-workflow en voor
lokaal gebruik bij het toevoegen of repareren van een bron.
"""
from __future__ import annotations

from collections import Counter

from . import strategies
from .config import RetailerCfg
from .normalize import apply_focus, mapping_coverage, to_staging_rows

VERDACHTE_PRIJS = 0.50   # euro; daaronder is het in ondermode geen echte prijs


def probe_one(cfg: RetailerCfg, limit: int = 40) -> dict:
    res = strategies.run(cfg, limit=limit)
    all_rows = to_staging_rows(cfg.id, res.products)
    rows = apply_focus(all_rows, cfg.focus_product_types)
    n = len(all_rows) or 1
    return {
        "cfg": cfg,
        "limit": limit,
        "result": res,
        "all_rows": all_rows,
        "rows": rows,
        "price_coverage": round(sum(1 for r in all_rows if r["price"] is not None) / n, 2),
        # Prijzen onder de VERDACHTE_PRIJS zijn in bodywear vrijwel altijd een
        # leesfout (stukprijs van een multipack, of centen zonder komma), geen
        # koopje. KiK stond week 35 vol met sokken van "€0,28"; zonder dit
        # signaal zag het validatierapport er kerngezond uit.
        "verdacht_laag": round(sum(1 for r in all_rows
                                   if r["price"] is not None and r["price"] < VERDACHTE_PRIJS) / n, 2),
        "color_coverage": round(sum(1 for r in all_rows if r["color"]) / n, 2),
        "sizes_coverage": round(sum(1 for r in all_rows if r["sizes"]) / n, 2),
        # Stap A promotievormen: aandeel artikelen met een gevangen promotekst.
        # Geen normwaarde — een bron zonder online acties scoort eerlijk 0%.
        "promo_coverage": round(sum(1 for r in all_rows if r.get("promo_text")) / n, 2),
        "mapping": mapping_coverage(all_rows),
    }


def advies(p: dict) -> str:
    res, cfg = p["result"], p["cfg"]
    if res.error:
        if "blokkeert" in res.error.lower() or "403" in res.error or "429" in res.error:
            return "geblokkeerd — kandidaat voor fase-2 (headless browser) of accepteer uitval"
        return "configuratie nalopen (base-URL, url_filter, evt. seeds toevoegen)"
    if p["all_rows"] and not p["rows"]:
        return ("artikelen gevonden maar geen enkele binnen de focus — mappingregels "
                "of focus_product_types nalopen")
    if len(p["rows"]) < cfg.min_products_expected <= p.get("limit", 0):
        # Zonder deze regel adviseerde de probe 'klaar voor de wekelijkse run' bij
        # 6 artikelen (Zeeman) — terwijl de weekrun zo'n oogst per definitie afkeurt.
        return (f"slechts {len(p['rows'])} artikelen binnen focus — onder de "
                f"weekdrempel van {cfg.min_products_expected}, dus de weekrun keurt "
                "dit af; controleer de notities en voorbeeldtitels hierboven")
    if p.get("verdacht_laag", 0) >= 0.05:
        return (f"{p['verdacht_laag']:.0%} van de prijzen ligt onder €{VERDACHTE_PRIJS:.2f} "
                "— vrijwel zeker een leesfout (stukprijs van een multipack of centen "
                "zonder komma); prijsextractie van deze bron nalopen vóór de cijfers "
                "gebruikt worden")
    if p["price_coverage"] < 0.6:
        return "prijsextractie mager — bron-JSON bekijken en veldnamen aan jsonscan toevoegen"
    if p["mapping"] < 0.6:
        return "mappingregels aanscherpen op de categorienamen van deze bron"
    if not cfg.enabled:
        return "werkt — kan aangezet worden (enabled: true) zodra fase 2 start"
    return "klaar voor de wekelijkse run"


def probe_report(probes: list[dict], limit: int) -> str:
    md = ["# Validatierapport bronnen", "",
          f"*Proefscrape met maximaal {limit} artikelen per bron — een steekproef, "
          "geen volledige telling. Kleur-/matendekking is gemeten op lijstniveau, "
          "dus vóór de verrijking via productpagina's die in de weekrun draait.*", "",
          "| Bron | Strategie | Categorieën | Artikelen | Binnen focus | Prijs­dekking | Verdacht laag | Kleur | Maten | Promo | Mapping | Requests | Status |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for p in probes:
        cfg, res = p["cfg"], p["result"]
        status = f"🔴 {res.error[:90]}" if res.error else "🟢 ok"
        md.append(f"| {cfg.name} | {res.strategy or '–'} | {res.categories_found or '–'} "
                  f"| {len(p['all_rows'])} | {len(p['rows'])} | {p['price_coverage']:.0%} "
                  f"| {p.get('verdacht_laag', 0):.0%} "
                  f"| {p['color_coverage']:.0%} | {p['sizes_coverage']:.0%} "
                  f"| {p.get('promo_coverage', 0):.0%} "
                  f"| {p['mapping']:.0%} | {res.requests_done} | {status} |")
    md.append("")
    for p in probes:
        cfg, res = p["cfg"], p["result"]
        md.append(f"## {cfg.name}")
        md.append(f"- **Advies:** {advies(p)}")
        for n in res.notes:
            md.append(f"- {n}")
        if p["rows"]:
            aud = Counter(r["audience"] for r in p["rows"])
            md.append(f"- Doelgroepverdeling (steekproef): "
                      + ", ".join(f"{k} {v}" for k, v in aud.most_common(6)))
            # De gevangen promoteksten zelf zijn het bewijs dat de patronen
            # raak zijn (of ruis oppikken) — zonder voorbeelden is een
            # dekkingspercentage niet te beoordelen.
            promos = Counter(r["promo_text"] for r in p["all_rows"] if r.get("promo_text"))
            if promos:
                md.append("- Promoteksten gevangen (ruw, stap A): "
                          + " | ".join(f"'{t[:40]}' ×{n}" for t, n in promos.most_common(6)))
            md.append("- Voorbeelden:")
            md.append("")
            md.append("  | Artikel | Prijs | Was | Promo | Kleur | Maten | Groep |")
            md.append("  |---|---:|---:|---|---|---|---|")
            for r in p["rows"][:5]:
                prijs = f"€{r['price']:.2f}" if r["price"] is not None else "–"
                was = f"€{r['was_price']:.2f}" if r["was_price"] is not None else ""
                md.append(f"  | {r['title'][:50]} | {prijs} | {was} "
                          f"| {(r.get('promo_text') or '')[:30]} "
                          f"| {r['color'][:20]} | {r['sizes'][:25]} "
                          f"| {r['audience']} / {r['product_type']} |")
        md.append("")
    return "\n".join(md)
