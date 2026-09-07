"""Validatie van folderbronnen: per bron de folderpagina ophalen, de viewer
herkennen en de capture-route adviseren. Rapport in markdown — voor de
workflow "Validatie folders" (plan §4.4). Draait zonder database."""
from __future__ import annotations

from scraper.http import BlockedError, Http

from .config import BronCfg
from .viewer import ViewerInfo, detect, folder_links, geldigheid, tekst, tel_paginas, titel

STATUS = {"groen": "🟢", "oranje": "🟠", "rood": "🔴", "wit": "⚪"}


def _score(info: ViewerInfo) -> int:
    """Hoe bruikbaar is deze pagina als startpunt voor de capture? 4 = klaar
    voor fase 1, 1 = alleen een headless browser kan er iets mee."""
    if info.kind == "pdf":
        return 4
    if info.kind in ("publitas", "ipaper"):
        return 4 if info.url else 2
    if info.kind == "extern":
        return 3 if info.url else 2
    if info.kind == "pages":
        return 3
    return 1


def validate_one(cfg: BronCfg, http: Http | None = None, max_ontdekt: int = 3) -> dict:
    out: dict = {"cfg": cfg, "http_status": None, "html_len": 0, "titel": "", "viewer": None,
                 "geldig": None, "geblokkeerd": False, "fout": "", "viewer_http": None,
                 "viewer_len": 0, "viewer_pages": 0, "viewer_fout": "", "requests": 0,
                 "gebruikte_url": cfg.folder_url, "kandidaten": []}
    if cfg.mail_only:
        return out
    http = http or Http(min_delay=cfg.min_delay, respect_robots=cfg.respect_robots)

    # De folder_url is een startaanname. Probeer daarna de kandidaten uit
    # bronnen.yml én de folderlinks die de pagina's zelf noemen (één stap
    # diep), en kies de pagina met de beste capture-route. Stop zodra een
    # pagina 'klaar voor fase 1' is (score 4) — geen verzoek te veel.
    wachtrij = [cfg.folder_url] + [k for k in cfg.folder_url_kandidaten if k != cfg.folder_url]
    geprobeerd: set[str] = set()
    ontdekt = 0
    beste: tuple[int, str, object, ViewerInfo] | None = None   # (score, url, resp, info)
    primair_geblokkeerd = ""
    while wachtrij:
        url = wachtrij.pop(0)
        if url in geprobeerd:
            continue
        geprobeerd.add(url)
        try:
            resp = http.get(url)
        except BlockedError as e:
            out["kandidaten"].append(f"{url}: {e}")
            if url == cfg.folder_url:
                primair_geblokkeerd = str(e)
            continue
        if resp is None:
            out["kandidaten"].append(f"{url}: " + ("robots.txt verbiedt de pagina" if http.robots_skipped
                                                   else "geen antwoord"))
            continue
        info = detect(resp.text, resp.url)
        score = _score(info)
        out["kandidaten"].append(f"{url}: antwoordt ({resp.status_code}) → {info.kind}"
                                 + (f" ({info.platform})" if info.platform and info.kind == "extern" else ""))
        if beste is None or score > beste[0]:
            beste = (score, url, resp, info)
        if score >= 4:
            break
        for link in folder_links(resp.text, resp.url):
            if link not in geprobeerd and link not in wachtrij and ontdekt < max_ontdekt:
                wachtrij.append(link)
                ontdekt += 1
                out["kandidaten"].append(f"{link}: ontdekt via de pagina, wordt geprobeerd")

    if beste is None:
        if primair_geblokkeerd:
            out["geblokkeerd"] = True
            out["fout"] = primair_geblokkeerd
        else:
            out["fout"] = "geen antwoord (404, timeout of verbindingsfout)"
        if len(geprobeerd) > 1:
            out["fout"] += f"; {len(geprobeerd) - 1} kandidaat-URL(s) ook niet"
        out["requests"] = http.requests_done
        return out

    _, url, resp, info = beste
    html = resp.text
    out["gebruikte_url"] = url
    out["http_status"] = resp.status_code
    out["html_len"] = len(html)
    out["titel"] = titel(html)
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
