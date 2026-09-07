"""Viewerdetectie en geldigheid: waar staat de folder, in welke vorm, en
voor welke periode?

Folders komen zelden als PDF. Retailers publiceren ze in een bladerviewer
(Publitas, iPaper, een eigen viewer) die per pagina een afbeelding serveert.
Deze module kijkt naar de HTML van een folderpagina en zegt welke
capture-route (plan §4.4) in aanmerking komt. Zonder netwerk testbaar.
"""
from __future__ import annotations

import html as html_mod
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from urllib.parse import urljoin, urlsplit

# Bekende viewerplatformen → herkenbare hostfragmenten. Publitas en iPaper
# krijgen een eigen route (plan §4.4); de rest is 'extern' tot een capture
# ervoor bestaat.
VIEWER_HOSTS: dict[str, tuple[str, ...]] = {
    "publitas": ("publitas.com",),
    "ipaper": ("ipaper.io", "ipaper.dk", "ipapercms"),
    "flipsnack": ("flipsnack.com",),
    "issuu": ("issuu.com",),
    "yumpu": ("yumpu.com",),
    "calameo": ("calameo.com",),
    "paperturn": ("paperturn",),
    "flippingbook": ("flippingbook",),
}
EIGEN_ROUTE = ("publitas", "ipaper")

ATTR_URL_RE = re.compile(
    r"""(?:href|src|data-src|data-href|data-url|data-pdf|content)\s*=\s*["']([^"'\s>]+)["']""", re.I)
PDF_RE = re.compile(r"\.pdf(?:[?#][^\s\"']*)?$", re.I)
# Kale URL's in script-/JSON-blokken (Next.js-flight, embed-configs). Alleen
# viewer- en pdf-URL's worden daaruit meegenomen; de rest is ruis.
BARE_URL_RE = re.compile(r"https?://[^\s\"'<>\\)]+")
SCRIPT_URL_RE = re.compile(r"\.(?:m?js|css)(?:[?#].*)?$", re.I)
# Een pdf op een folderpagina is niet per se de folder (Zeeman: een
# kwaliteitsrapport). Alleen pdf's met een folderkenmerk in het pad tellen.
FOLDER_PDF_RE = re.compile(r"folder|brochure|magazine|krant|week|aanbieding|actie|deal|catalog", re.I)
ANCHOR_RE = re.compile(r"""<a\b[^>]*?href\s*=\s*["']([^"'#\s>]+)["'][^>]*>(.*?)</a>""", re.I | re.S)
PAGE_IMG_RE = re.compile(r"(?:page|pagina|folder|spread)[-_/]?\d{1,3}\b[^\"'\s]*\.(?:jpe?g|png|webp)", re.I)
PAGE_NR_RE = re.compile(r"(?:page|pagina)(?:[-_ ]|\s*=\s*[\"']?)?(\d{1,3})\b", re.I)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


@dataclass
class ViewerInfo:
    kind: str                       # pdf | publitas | ipaper | extern | pages | render
    url: str = ""                   # de PDF, de viewer-URL of het eerste paginabeeld
    platform: str = ""              # naam van het platform bij 'extern'
    evidence: list[str] = field(default_factory=list)
    page_hints: int = 0             # aantal paginabeelden/-verwijzingen gezien


def _viewer_of_pdf(u: str) -> bool:
    low = u.lower()
    return bool(PDF_RE.search(u)) or any(h in low for hosts in VIEWER_HOSTS.values() for h in hosts)


def urls_in(html: str, base_url: str) -> list[str]:
    """Alle absolute URL's uit href/src/data-*-attributen, in documentvolgorde,
    ontdubbeld. Daarna de viewer- en pdf-URL's die kaal in script-/JSON-blokken
    staan (JSON-escaped `https:\\/\\/…` wordt eerst hersteld) — Action en KiK
    zetten hun Publitas-link in de pagina-JS, niet in een href."""
    html = (html or "").replace("\\/", "/")
    seen: list[str] = []
    for raw in ATTR_URL_RE.findall(html):
        u = html_mod.unescape(raw).strip()
        if not u or u.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            continue
        absu = urljoin(base_url, u)
        if absu not in seen:
            seen.append(absu)
    for raw in BARE_URL_RE.findall(html):
        u = html_mod.unescape(raw).rstrip(".,;")
        if _viewer_of_pdf(u) and u not in seen:
            seen.append(u)
    return seen


def _host(u: str) -> str:
    return urlsplit(u).netloc.lower()


def folder_links(html: str, base_url: str, limit: int = 3) -> list[str]:
    """Interne links die naar een folderpagina wijzen: 'folder' in het pad of in de
    linktekst, zelfde host, niet de pagina zelf. Eén stap diep is genoeg: een
    aanbiedingenpagina linkt naar de folder, een folderpagina naar de viewer."""
    html = (html or "").replace("\\/", "/")
    host, eigen = _host(base_url), base_url.rstrip("/")
    out: list[str] = []
    for href, tekst in ANCHOR_RE.findall(html):
        u = urljoin(base_url, html_mod.unescape(href).strip())
        if _host(u) != host or u.rstrip("/") == eigen or u in out:
            continue
        if "folder" in urlsplit(u).path.lower() or "folder" in re.sub(r"<[^>]+>", " ", tekst).lower():
            out.append(u)
            if len(out) >= limit:
                break
    return out


def detect(html: str, base_url: str) -> ViewerInfo:
    """Welke capture-route past bij deze folderpagina?"""
    urls = urls_in(html, base_url)
    pdfs = [u for u in urls if PDF_RE.search(u)]
    folder_pdfs = [u for u in pdfs if FOLDER_PDF_RE.search(urlsplit(u).path)]
    if folder_pdfs:
        return ViewerInfo("pdf", folder_pdfs[0], evidence=[f"{len(folder_pdfs)} folder-pdf-link(s)"], page_hints=0)
    extra = [f"{len(pdfs)} pdf-link(s) zonder folderkenmerk genegeerd"] if pdfs else []
    for platform, hosts in VIEWER_HOSTS.items():
        hits = [u for u in urls if any(h in _host(u) or h in u.lower() for h in hosts)]
        if hits:
            kind = platform if platform in EIGEN_ROUTE else "extern"
            # embed.js e.d. is het script van het platform, niet de folder zelf.
            folders = [u for u in hits if not SCRIPT_URL_RE.search(urlsplit(u).path)]
            if folders:
                return ViewerInfo(kind, folders[0], platform=platform,
                                  evidence=[f"{platform}: {len(hits)} verwijzing(en)"])
            return ViewerInfo(kind, "", platform=platform,
                              evidence=[f"{platform}: alleen het embed-script gevonden; de folder-URL "
                                        f"wordt door de pagina-JS opgebouwd (render-route of seed uit de nieuwsbrief)"])
    page_imgs = [u for u in urls if PAGE_IMG_RE.search(u)]
    if len(page_imgs) >= 3:
        return ViewerInfo("pages", page_imgs[0], evidence=[f"{len(page_imgs)} paginabeelden op de pagina"],
                          page_hints=len(page_imgs))
    low = (html or "").lower()
    for platform, hosts in VIEWER_HOSTS.items():
        if platform in low or any(h in low for h in hosts):
            kind = platform if platform in EIGEN_ROUTE else "extern"
            return ViewerInfo(kind, "", platform=platform,
                              evidence=[f"{platform} genoemd in de pagina, maar geen link gevonden"] + extra)
    return ViewerInfo("render", "", evidence=["geen pdf, viewer of paginabeelden herkend"] + extra)


def tel_paginas(html: str) -> int:
    """Hoogste paginanummer dat een viewerpagina verraadt (hint, geen telling)."""
    nrs = [int(n) for n in PAGE_NR_RE.findall(html or "") if 0 < int(n) <= 200]
    return max(nrs) if nrs else 0


def titel(html: str) -> str:
    m = TITLE_RE.search(html or "")
    return re.sub(r"\s+", " ", html_mod.unescape(m.group(1))).strip()[:120] if m else ""


def tekst(html: str) -> str:
    """Kale tekst van een pagina (voor de geldigheidsdatums)."""
    t = re.sub(r"<script\b.*?</script>|<style\b.*?</style>", " ", html or "", flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html_mod.unescape(t)).strip()


# ---- geldigheid ---------------------------------------------------------

MAANDEN = {
    "januari": 1, "jan": 1, "februari": 2, "feb": 2, "maart": 3, "mrt": 3, "april": 4, "apr": 4,
    "mei": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7, "augustus": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9, "oktober": 10, "okt": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
_SCHEIDER = r"\s*(?:t/m|t\.e\.m\.|tot en met|tot|-|–|—)\s*"
# '9 t/m 15 september', '31 augustus t/m 13 september 2026', 'van 2 september tot 8 september'
TEKST_RE = re.compile(
    r"\b(\d{1,2})(?:\s+([a-z]{3,9})\.?)?" + _SCHEIDER + r"(\d{1,2})\s+([a-z]{3,9})\.?(?:\s+(\d{4}))?", re.I)
# '02-09 t/m 08-09', '02-09-2026 t/m 08-09-2026', '2/9 - 8/9'
NUM_RE = re.compile(
    r"\b(\d{1,2})[-/.](\d{1,2})(?:[-/.](\d{4}))?" + _SCHEIDER + r"(\d{1,2})[-/.](\d{1,2})(?:[-/.](\d{4}))?\b")
MAX_LOOPTIJD = 60  # dagen; langer is geen folder maar een seizoen


def _datum(d: int, m: int, y: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def geldigheid(text: str, vandaag: date | None = None) -> tuple[date, date] | None:
    """Geldigheidsperiode uit vrije tekst — de eerste plausibele match wint.

    Jaar ontbreekt meestal: dan het huidige jaar, met een jaarwissel als
    'tot' vóór 'van' zou vallen (december → januari). Periodes langer dan
    MAX_LOOPTIJD dagen worden verworpen (seizoens- of contentpagina's)."""
    vandaag = vandaag or date.today()
    if not text:
        return None
    low = text.lower()
    for m in TEKST_RE.finditer(low):
        d1, m1, d2, m2, jaar = m.groups()
        if m2 not in MAANDEN or (m1 and m1 not in MAANDEN):
            continue
        y = int(jaar) if jaar else vandaag.year
        van = _datum(int(d1), MAANDEN[m1] if m1 else MAANDEN[m2], y)
        tot = _datum(int(d2), MAANDEN[m2], y)
        periode = _plausibel(van, tot, vandaag, jaar_bekend=bool(jaar))
        if periode:
            return periode
    for m in NUM_RE.finditer(low):
        d1, m1, y1, d2, m2, y2 = m.groups()
        if not (1 <= int(m1) <= 12 and 1 <= int(m2) <= 12):
            continue
        y_van = int(y1) if y1 else (int(y2) if y2 else vandaag.year)
        y_tot = int(y2) if y2 else y_van
        van = _datum(int(d1), int(m1), y_van)
        tot = _datum(int(d2), int(m2), y_tot)
        periode = _plausibel(van, tot, vandaag, jaar_bekend=bool(y1 or y2))
        if periode:
            return periode
    return None


def _plausibel(van: date | None, tot: date | None, vandaag: date,
               jaar_bekend: bool) -> tuple[date, date] | None:
    if not van or not tot:
        return None
    if tot < van:
        if jaar_bekend:
            return None
        tot = _datum(tot.day, tot.month, tot.year + 1)
        if not tot:
            return None
    if not jaar_bekend and tot < vandaag - timedelta(days=300):
        # 'januari' gelezen in december: de folder is van volgend jaar
        van = _datum(van.day, van.month, van.year + 1) or van
        tot = _datum(tot.day, tot.month, tot.year + 1) or tot
    if (tot - van).days > MAX_LOOPTIJD:
        return None
    return van, tot
