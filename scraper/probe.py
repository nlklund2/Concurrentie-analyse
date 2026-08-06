"""Validatie van bronnen: kleine proefscrape per bron, rapport in markdown.

Draait zonder database — bedoeld voor de "Validatie bronnen"-workflow en voor
lokaal gebruik bij het toevoegen of repareren van een bron.
"""
from __future__ import annotations

from collections import Counter

from . import strategies
from .config import RetailerCfg
from .normalize import apply_focus, mapping_coverage, to_staging_rows


def probe_one(cfg: RetailerCfg, limit: int = 40) -> dict:
    res = strategies.run(cfg, limit=limit)
    all_rows = to_staging_rows(cfg.id, res.products)
    rows = apply_focus(all_rows, cfg.focus_product_types)
    priced = sum(1 for r in all_rows if r["price"] is not None)
    return {
        "cfg": cfg,
        "result": res,
        "all_rows": all_rows,
        "rows": rows,
        "price_coverage": round(priced / len(all_rows), 2) if all_rows else 0.0,
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
          "geen volledige telling.*", "",
          "| Bron | Strategie | Categorieën | Artikelen | Binnen focus | Prijs­dekking | Mapping | Requests | Status |",
          "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for p in probes:
        cfg, res = p["cfg"], p["result"]
        status = f"🔴 {res.error[:90]}" if res.error else "🟢 ok"
        md.append(f"| {cfg.name} | {res.strategy or '–'} | {res.categories_found or '–'} "
                  f"| {len(p['all_rows'])} | {len(p['rows'])} | {p['price_coverage']:.0%} "
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
            md.append("- Voorbeelden:")
            md.append("")
            md.append("  | Artikel | Prijs | Was | Groep |")
            md.append("  |---|---:|---:|---|")
            for r in p["rows"][:5]:
                prijs = f"€{r['price']:.2f}" if r["price"] is not None else "–"
                was = f"€{r['was_price']:.2f}" if r["was_price"] is not None else ""
                md.append(f"  | {r['title'][:60]} | {prijs} | {was} "
                          f"| {r['audience']} / {r['product_type']} |")
        md.append("")
    return "\n".join(md)
