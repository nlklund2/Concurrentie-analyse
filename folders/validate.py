"""Validatie van folderbronnen: per bron de folderpagina ophalen, de viewer
herkennen en de capture-route adviseren. Rapport in markdown — voor de
workflow "Validatie folders" (plan §4.4). Draait zonder database."""
from __future__ import annotations

from scraper.http import BlockedError, Http

from .config import BronCfg
from .viewer import ViewerInfo, detect, geldigheid, tekst, tel_paginas, titel

STATUS = {"groen": "🟢", "oranje": "🟠", "rood": "🔴", "wit": "⚪"}


def validate_one(cfg: BronCfg, http: Http | None = None) -> dict:
    out: dict = {"cfg": cfg, "http_status": None, "html_len": 0, "titel": "", "viewer": None,
                 "geldig": None, "geblokkeerd": False, "fout": "", "viewer_http": None,
                 "viewer_len": 0, "viewer_pages": 0, "viewer_fout": "", "requests": 0,
                 "gebruikte_url": cfg.folder_url, "kandidaten": []}
    if cfg.mail_only:
        return out
    http = http or Http(min_delay=cfg.min_delay, respect_robots=cfg.respect_robots)
    try:
        resp = http.get(cfg.folder_url)
    except BlockedError as e:
        out["geblokkeerd"] = True
        out["fout"] = str(e)
        out["requests"] = http.requests_done
        return out
    if resp is None and http.robots_skipped:
        out["fout"] = "robots.txt verbiedt de folderpagina"
        out["requests"] = http.requests_done
        return out
    if resp is None:
        # De folder_url is een startaanname; probeer de kandidaten uit bronnen.yml
        # tot er één antwoordt. Het rapport zegt dan welke folder_url moet worden.
        out["kandidaten"].append(f"{cfg.folder_url}: geen antwoord")
        for kand in cfg.folder_url_kandidaten:
            try:
                r = http.get(kand)
            except BlockedError as e:
                out["kandidaten"].append(f"{kand}: {e}")
                continue
            if r is None:
                out["kandidaten"].append(f"{kand}: geen antwoord")
                continue
            resp, out["gebruikte_url"] = r, kand
            out["kandidaten"].append(f"{kand}: antwoordt ({r.status_code})")
            break
    if resp is None:
        out["fout"] = "geen antwoord (404, timeout of verbindingsfout)"
        if cfg.folder_url_kandidaten:
            out["fout"] += f"; {len(cfg.folder_url_kandidaten)} kandidaat-URL(s) ook niet"
        out["requests"] = http.requests_done
        return out
    html = resp.text
    out["http_status"] = resp.status_code
    out["html_len"] = len(html)
    out["titel"] = titel(html)
    info: ViewerInfo = detect(html, resp.url)
    out["viewer"] = info
    out["geldig"] = geldigheid(tekst(html))
    # Tweede stap: de viewer zelf aanraken — dát is het domein waar de
    # capture straks moet werken, en dat kan een ander domein zijn dan de
    # retailer (Wibra/HEMA weren datacenter-IP's op hun eigen domein).
    if info.url and info.kind in ("publitas", "ipaper", "extern", "pdf"):
        try:
            r2 = http.get(info.url)
        except BlockedError as e:
            out["viewer_fout"] = str(e)
        else:
            if r2 is None:
                out["viewer_fout"] = "viewer/pdf niet bereikbaar"
            else:
                out["viewer_http"] = r2.status_code
                out["viewer_len"] = len(r2.content)
                if info.kind != "pdf":
                    out["viewer_pages"] = tel_paginas(r2.text)
                    if out["geldig"] is None:
                        out["geldig"] = geldigheid(tekst(r2.text))
    out["requests"] = http.requests_done
    return out


def route_advies(out: dict) -> str:
    cfg: BronCfg = out["cfg"]
    if cfg.mail_only:
        return "mail-only: de sweep registreert de mailing; er is geen folder te capturen"
    if out["geblokkeerd"]:
        return ("geweerd op het eigen domein — seed de viewer-URL uit de nieuwsbrief "
                "(ander domein), anders Firecrawl (bestaande sleutel) of de upload")
    if out["fout"]:
        return "folderpagina niet bereikbaar — folder_url in bronnen.yml controleren of de link uit de nieuwsbrief seeden"
    info: ViewerInfo = out["viewer"]
    prefix = ""
    if out.get("gebruikte_url") and out["gebruikte_url"] != cfg.folder_url:
        prefix = f"zet folder_url op {out['gebruikte_url']} (kandidaat antwoordde, de folder_url niet); "
    if out["viewer_fout"]:
        return prefix + f"viewer herkend ({info.kind}) maar niet bereikbaar: {out['viewer_fout'][:80]} — upload als vangnet"
    if info.kind == "pdf":
        return prefix + "route pdf — directe download, beste kwaliteit"
    if info.kind in ("publitas", "ipaper") and not info.url:
        return prefix + (f"{info.kind} herkend zonder folderlink — route render (headless browser) "
                         f"die de viewer-URL uit de pagina-JS haalt, of seed uit de nieuwsbrief")
    if info.kind in ("publitas", "ipaper"):
        return prefix + f"route pages via {info.kind} — capture bouwen in fase 1"
    if info.kind == "extern":
        return prefix + f"route pages via {info.platform} — capture bouwen in fase 1 (nog geen eigen route)"
    if info.kind == "pages":
        return prefix + "route pages — paginabeelden staan op de folderpagina zelf"
    return prefix + "route render (headless browser) — of de viewer-URL uit de nieuwsbrief seeden"


def status(out: dict) -> str:
    cfg: BronCfg = out["cfg"]
    if cfg.mail_only:
        return "wit"
    if out["geblokkeerd"] or out["fout"]:
        return "rood"
    info: ViewerInfo = out["viewer"]
    if out["viewer_fout"] or info.kind == "render":
        return "oranje"
    if info.kind in ("publitas", "ipaper", "extern") and not info.url:
        return "oranje"          # platform herkend, maar de folder zelf nog niet gevonden
    return "groen"


def validate_report(results: list[dict]) -> str:
    md = ["# Validatierapport folders", "",
          "*Per bron: is de folderpagina bereikbaar, welke viewer draait er, en welke "
          "capture-route past (plan §4.4)? Dit is een bereikbaarheids- en detectiemeting; "
          "de capture zelf wordt in fase 1 gebouwd op basis van deze uitkomst.*", "",
          "| Bron | Folderpagina | HTTP | Viewer | Viewer bereikbaar | Pagina's (hint) | Geldigheid | Requests | Status |",
          "|---|---|---:|---|---|---:|---|---:|---|"]
    for r in results:
        cfg: BronCfg = r["cfg"]
        info: ViewerInfo | None = r["viewer"]
        icon = STATUS[status(r)]
        viewer = "–" if not info else (info.kind + (f" ({info.platform})" if info.platform else ""))
        bereikbaar = "–"
        if r["viewer_fout"]:
            bereikbaar = "nee"
        elif r["viewer_http"]:
            bereikbaar = f"ja ({r['viewer_len'] // 1024} KB)"
        geldig = "–"
        if r["geldig"]:
            van, tot = r["geldig"]
            geldig = f"{van:%d-%m} t/m {tot:%d-%m-%Y}"
        pagina = r.get("gebruikte_url") or cfg.folder_url or "mail-only"
        if cfg.folder_url and pagina != cfg.folder_url:
            pagina += " (kandidaat)"
        md.append(f"| {cfg.name} | {pagina} | {r['http_status'] or '–'} | {viewer} | {bereikbaar} "
                  f"| {r['viewer_pages'] or '–'} | {geldig} | {r['requests']} | {icon} |")
    md.append("")
    for r in results:
        cfg: BronCfg = r["cfg"]
        md.append(f"## {cfg.name}")
        md.append(f"- **Advies:** {route_advies(r)}")
        if r["fout"]:
            md.append(f"- Fout: {r['fout']}")
        for k in r.get("kandidaten", []):
            md.append(f"- Geprobeerd: {k}")
        if r["titel"]:
            md.append(f"- Paginatitel: {r['titel']}")
        if r["viewer"]:
            for e in r["viewer"].evidence:
                md.append(f"- {e}")
            if r["viewer"].url:
                md.append(f"- Viewer/PDF: {r['viewer'].url}")
        if r["html_len"]:
            md.append(f"- HTML-omvang folderpagina: {r['html_len']:,} tekens".replace(",", "."))
        if cfg.notes:
            md.append(f"- Notities: {' '.join(cfg.notes.split())}")
        md.append("")
    md.append("> 🟢 route bekend en bereikbaar · 🟠 alleen via headless browser of viewer onbereikbaar · "
              "🔴 geweerd of onbereikbaar · ⚪ mail-only bron. Leg het eindoordeel per bron vast in "
              "docs/validaties/ met het run-id.")
    return "\n".join(md)
