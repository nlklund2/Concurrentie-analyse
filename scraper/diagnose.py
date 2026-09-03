"""Waarom levert deze pagina niets op? Eén commando dat het antwoord toont.

De afgelopen week ging er meer tijd in het ráden waarom een bron leeg bleef dan
in het repareren. Zeeman leek geblokkeerd, bleek redactioneel, bleek uiteindelijk
een pagina zonder leesbare prijzen. Dit bestand maakt van dat raden een meting:
render de pagina zoals de scraper dat doet en rapporteer álle signalen waar de
extractie op kan aanhaken — inclusief de signalen die we (nog) niet gebruiken.

    python -m scraper diagnose --url https://www.zeeman.com/nl-nl/dames/ondergoed/

Lees het rapport van boven naar beneden:
  * geen tekst / blokkadehint  → bron weert ons (proxy nodig, zie PLAN.md §8)
  * tekst maar 0 prijssignalen → raster laadt niet (consent, regio, interactie)
  * prijzen zonder €           → valutateken komt uit CSS; los-prijs-ronde helpt
  * prijzen alleen in attributen of microdata → extractie uitbreiden
  * JSON-API met producten     → de betrouwbaarste route; endpoint overnemen
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from .http import Http
from .jsonscan import deep_find_products, products_from_html

_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
    re.I | re.S)

# Prijsachtig zonder valutateken: 3,99 of 3.99, niet 35 - 46 (maten), geen
# jaartallen en geen versienummers (5.51.0 — telde op Zeeman als prijs terwijl
# het een scriptnaam in de cookiedialoog was). Signaal, geen extractieregel.
PRIJS_LOS_RE = re.compile(r"(?<![\d.,])\d{1,4}[.,]\d{2}(?![.,]?\d)")


def _sitemap_regels(xml: str) -> list[str]:
    """Sitemap samenvatten: omvang, padsegmenten en voorbeeld-URL's — de
    grondstof om een productpagina voor een vervolgdiagnose te kiezen."""
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)
    per_seg: dict[str, int] = {}
    for u in locs:
        seg = (re.sub(r"^https?://[^/]+", "", u).strip("/").split("/") or [""])[0]
        per_seg[seg] = per_seg.get(seg, 0) + 1
    top = sorted(per_seg.items(), key=lambda kv: -kv[1])[:5]
    return [f"- sitemap: {len(locs)} URL's",
            f"- grootste padsegmenten: {top}",
            "- voorbeelden: " + ", ".join(locs[:6])]


def _json_of_none(text: str):
    """JSON parsen uit een Firecrawl-rawHtml-antwoord; endpoints geven soms
    HTML-omlijsting mee, dus ook het eerste {...}/[...]-blok proberen."""
    for kandidaat in (text, text[text.find("{"):], text[text.find("["):]):
        if not kandidaat:
            continue
        try:
            return json.loads(kandidaat)
        except (ValueError, TypeError):
            continue
    return None

PAGINA_JS = r"""
() => {
  const tekst = document.body ? (document.body.innerText || '') : '';
  const attr = [];
  const els = document.querySelectorAll('*');
  for (let i = 0; i < els.length && attr.length < 6; i++) {
    for (const a of els[i].attributes || []) {
      if (/price|prijs|amount/i.test(a.name) && a.value && attr.length < 6) {
        attr.push(a.name + '="' + String(a.value).slice(0, 30) + '"');
      }
    }
  }
  const micro = [...document.querySelectorAll(
      '[itemprop="price"],[itemprop="lowPrice"],[itemprop="offers"]')]
    .slice(0, 5)
    .map(e => (e.getAttribute('content') || e.textContent || '').trim().slice(0, 30));
  const scripts = [...document.querySelectorAll(
      'script[type="application/json"],script[type="application/ld+json"],script#__NEXT_DATA__')]
    .map(s => (s.id || s.type) + ' (' + (s.textContent || '').length + ' tekens)')
    .slice(0, 6);
  // Waar staat het eerste prijsachtige getal? Het DOM-pad verraadt of het in
  // een productkaart zit of in een banner/voettekst.
  let pad = '';
  if (document.body) {
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = w.nextNode())) {
      if (/(?:^|[^\d.,])\d{1,4}[.,]\d{2}(?![.,]?\d)/.test(n.nodeValue || '')) {
        const delen = [];
        let el = n.parentElement;
        while (el && delen.length < 5) {
          const cls = (typeof el.className === 'string' && el.className.trim())
            ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '';
          delen.unshift(el.tagName.toLowerCase() + cls);
          el = el.parentElement;
        }
        // de omsluitende link (of het ontbreken ervan) beslist of de
        // DOM-kaartscan dit prijsgetal ooit aan een product kan koppelen
        const link = n.parentElement && n.parentElement.closest
          ? n.parentElement.closest('a') : null;
        const linkinfo = link
          ? ' | link: ' + (link.getAttribute('href') || 'zonder href').slice(0, 70)
          : ' | geen omsluitende link';
        pad = delen.join(' > ') + linkinfo
          + '  «' + (n.nodeValue || '').trim().slice(0, 40) + '»';
        break;
      }
    }
  }
  // Artikelteller en paginering: onmisbaar om een deels geladen raster te
  // duiden — Action toonde 24 tegels terwijl de categorie er (veel) meer
  // heeft, en zonder deze signalen is niet te zien of de rest achter
  // scrollen, een knop of een volgende pagina zit.
  const teller = (tekst.match(/\d+\s*(?:producten|artikelen|resultaten|items)|\b\d+\s*van\s+\d+\b/i) || [''])[0];
  const pagLinks = [...document.querySelectorAll('a[href*="page="], a[href*="/page/"]')]
    .map(a => (a.getAttribute('href') || '').slice(0, 60)).slice(0, 5);
  const pagKnoppen = [...document.querySelectorAll('button, [role="button"], a')]
    .map(e => ((e.getAttribute('aria-label') || '') + ' ' + (e.innerText || '')).trim().toLowerCase())
    .filter(t => t && t.length < 40 &&
                 /volgende|vorige|next|prev|pagina \d|page \d|toon meer|laad meer|load more|show more/.test(t))
    .slice(0, 6);
  // Kaarttekst van de eerste drie productkaarten, precies zoals de DOM-scan
  // hem leest (link + klim naar de eerste voorouder met een prijs). Beslist
  // of een gevangen promotekst bij het artikel hoort of een paginabreed
  // element is dat in de klim meekomt — KiK gaf '-43% · -20%' op 37 kaarten.
  const kaarten = [];
  const padRe = /\/p\/|\/p-|\/product|\/artikel|\/dp\//i;
  const prijsRe = /€\s*\d|\d[.,]\d{2}\s*€/;
  for (const streng of [true, false]) {
    const gezien = new Set();
    for (const a of document.querySelectorAll('a[href]')) {
      if (kaarten.length >= 3) break;
      const href = a.href || '';
      const laatste = (href.split(/[?#]/)[0].replace(/\/$/, '').split('/').pop() || '');
      if (streng && !padRe.test(href) && !/\d{4,}/.test(laatste)) continue;
      if (!href || gezien.has(href)) continue;
      let card = a, hops = 0;
      while (card && hops < 5 && !prijsRe.test(card.innerText || '')) { card = card.parentElement; hops++; }
      if (!card || !prijsRe.test(card.innerText || '')) continue;
      gezien.add(href);
      kaarten.push(hops + '↑ ' + (card.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 220));
    }
    if (kaarten.length) break;
  }
  return {
    titel: (document.title || '').slice(0, 90),
    tekst: tekst.length,
    links: document.querySelectorAll('a[href]').length,
    euro: (tekst.match(/€/g) || []).length,
    eur: (tekst.match(/\bEUR\b/g) || []).length,
    prijsachtig: (tekst.match(/(?:^|[^\d.,])\d{1,4}[.,]\d{2}(?![.,]?\d)/g) || []).length,
    attr, micro, scripts, pad, teller, pagLinks, pagKnoppen, kaarten,
  };
}
"""


def _firecrawl_diagnose(url: str) -> str:
    """Zelfde meting, maar opgehaald via Firecrawl — voor bronnen die het
    datacenter-IP weren (Wibra, HEMA). Gebruik: `fc:` vóór de URL in
    diagnose_urls. Een .xml-URL wordt als sitemap gelezen en toont
    voorbeelis-URL's, zodat een vervolgdiagnose een echte productpagina heeft."""
    import os

    import requests as _rq

    from .models import ScrapeResult
    from .strategies.firecrawl_api import _firecrawl_html, _signalen

    regels: list[str] = [f"## {url} *(via Firecrawl)*", ""]
    if not os.environ.get("FIRECRAWL_API_KEY"):
        return "\n".join(regels + ["- **FIRECRAWL_API_KEY niet gezet** — deze meting "
                                   "kan alleen op GitHub Actions draaien."])
    session = _rq.Session()
    session.headers.update({"Authorization": f"Bearer {os.environ['FIRECRAWL_API_KEY']}",
                            "Content-Type": "application/json"})
    res = ScrapeResult(retailer_id="diagnose")
    laag = url.lower()
    # JSON-endpoints (wp-json, .json) rauw ophalen: geen rendering, en de
    # inhoud meteen op producten toetsen — de goedkoopste route die er is.
    raw = laag.endswith(".xml") or "/wp-json/" in laag or ".json" in laag
    html = _firecrawl_html(session, url, res, raw=raw, wait_ms=0 if raw else 8000)
    for n in res.notes:
        regels.append(f"- {n}")
    if res.error:
        regels.append(f"- **{res.error}**")
    if html is None:
        return "\n".join(regels + ["- geen HTML terug — zie de notities hierboven."])

    if raw and not laag.endswith(".xml"):
        regels.append(f"- {len(html)} tekens; begin: `{' '.join(html[:200].split())}`")
        data = _json_of_none(html)
        if data is None:
            regels.append("- **geen geldige JSON** — endpoint bestaat niet of "
                          "geeft een foutpagina")
        else:
            keys = list(data)[:8] if isinstance(data, dict) else f"lijst[{len(data)}]"
            prods = deep_find_products(data, url)
            regels.append(f"- geldige JSON, sleutels: {keys}")
            regels.append(f"- **producten via deep_find: {len(prods)}**"
                          + (f", bv. {prods[0].title[:40]!r} à {prods[0].price}"
                             if prods else ""))
        return "\n".join(regels)

    if raw:
        return "\n".join(regels + _sitemap_regels(html))

    from .strategies.render_listing import cards_from_html

    # De ruwe snapshot bewaren als werkbestand: raden op signalen bleef bij
    # HEMA twee rondes lang steken; met de echte bytes is de kaartstructuur
    # in één keer te ontleden. De workflow neemt diagnose-dump-*.html mee
    # als artifact.
    host = re.sub(r"[^a-z0-9.-]", "-", urlsplit(url).netloc.lower())
    with open(f"diagnose-dump-{host}.html", "w", encoding="utf-8") as f:
        f.write(html[:2_000_000])

    prods = products_from_html(html, url)
    kaarten = cards_from_html(html, url)
    regels += [
        f"- signalen: {_signalen(html)}",
        f"- producten via de gewone extractie: {len(prods)}"
        + (f", bv. {prods[0].title[:40]!r} à {prods[0].price}" if prods else ""),
        f"- producten via de kaartlezer: {len(kaarten)}"
        + (f", bv. {kaarten[0].title[:40]!r} à {kaarten[0].price}" if kaarten else ""),
    ]
    # productachtige links: de grondstof voor een vervolgdiagnose per artikel
    hrefs: list[str] = []
    for m in re.finditer(r'href\s*=\s*["\']([^"\']+)["\']', html, re.I):
        h = m.group(1)
        if re.search(r"product|assortiment|artikel|/p/|/a/|\d{5,}", h) and h not in hrefs:
            hrefs.append(h)
        if len(hrefs) >= 8:
            break
    if hrefs:
        regels.append("- productachtige links: " + ", ".join(h[:80] for h in hrefs))
    # De tegel zelf uitknippen: het artifact met de volledige dump is vanuit
    # de ontwikkelomgeving niet te downloaden (proxy), dus het fragment moet
    # het rapport in — dáár wordt de kaartstructuur leesbaar.
    eerste = next((m for m in re.finditer(
        r'href\s*=\s*["\'][^"\']*(?:lingerie|ondergoed|product)[^"\']*["\']',
        html, re.I)), None)
    if eerste is not None:
        frag = html[max(0, eerste.start() - 400):eerste.start() + 2400]
        frag = re.sub(r'(srcset|src|style|class)\s*=\s*"[^"]{60,}"', r'\1="…"', frag)
        frag = re.sub(r"\s+", " ", frag)
        regels += ["- fragment rond de eerste producttegel:",
                   "", "```html", frag, "```"]
        prijs = PRIJS_LOS_RE.search(html, eerste.start())
        if prijs is not None:
            ctx = html[max(0, prijs.start() - 250):prijs.end() + 120]
            ctx = re.sub(r"\s+", " ", ctx)
            regels += [f"- eerste prijsachtige treffer ná de tegel "
                       f"(afstand {prijs.start() - eerste.start()} tekens):",
                       "", "```html", ctx, "```"]
    return "\n".join(regels)


def diagnose(url: str, render: bool = True) -> str:
    if url.startswith("fc:"):
        return _firecrawl_diagnose(url[3:])
    regels: list[str] = [f"## {url}", ""]
    http = Http(min_delay=0.5, respect_robots=True)
    resp = http.get(url)
    if resp is None:
        regels.append("- **HTTP: geen antwoord** — geblokkeerd, robots.txt of netwerkfout.")
    elif url.lower().endswith(".xml"):
        uit = regels + [f"- HTTP {resp.status_code}"] + _sitemap_regels(resp.text)
        if "<loc>" not in resp.text:
            # 200 zonder locs = soft-404 of een heel ander formaat; het begin
            # van het antwoord vertelt welke van de twee.
            uit.append("- begin van het antwoord: `"
                       + " ".join(resp.text[:300].split()) + "`")
        return "\n".join(uit)
    elif url.lower().endswith(".txt"):
        # robots.txt: verklapt de echte sitemap-locatie (Zeeman's
        # /sitemap.xml gaf HTTP 200 met nul URL's — verkeerd pad).
        sitemaps = [r for r in resp.text.splitlines()
                    if r.lower().startswith("sitemap")]
        kop = " | ".join(resp.text[:1500].splitlines())
        return "\n".join(regels + [f"- HTTP {resp.status_code}",
                                   f"- sitemap-regels: {sitemaps or 'geen'}",
                                   f"- inhoud: `{kop}`"])
    else:
        html = resp.text
        prods = products_from_html(html, url)
        regels += [
            f"- HTTP {resp.status_code}, {len(html)} tekens HTML",
            f"- in de kále HTML: {html.count('€')} €-tekens, "
            f"{len(PRIJS_LOS_RE.findall(html))} prijsachtige getallen, "
            f"{len(prods)} producten via de gewone extractie",
        ]
        # Waar stáán die prijsachtige getallen dan? Zeeman: 40 treffers in
        # 686k tekens kale HTML terwijl de gerenderde pagina er 2 toont —
        # de context beslist of het productdata in een JS-blob is of ruis.
        for m in list(PRIJS_LOS_RE.finditer(html))[:3]:
            ctx = html[max(0, m.start() - 60):m.end() + 40]
            regels.append("- context: `…" + " ".join(ctx.split()) + "…`")
        # De ld+json-blokken voluit: bij bronnen als terStal beslist de
        # breadcrumb hierin de doelgroep — vernieuwt de site het sjabloon,
        # dan is hier direct te zien wát er dan in staat (W36: het hele
        # assortiment werd 'jongens/nachtmode' zonder dat de code wijzigde).
        for i, blok in enumerate(_LDJSON_RE.findall(html)[:3], 1):
            regels.append(f"- ld+json {i}: `" + " ".join(blok.split())[:1400] + "`")
        eerste = next((p for p in prods if p.title), None)
        if eerste is not None:
            regels.append(f"- eerste extractieproduct: {eerste.title[:60]!r} à "
                          f"{eerste.price} · category_raw: {(eerste.category_raw or '')[:200]!r}")
        if not render:
            return "\n".join(regels)

    if not render:
        return "\n".join(regels)
    regels.append("")
    regels += _render_diagnose(url)
    return "\n".join(regels)


def _render_diagnose(url: str) -> list[str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return ["- playwright niet geïnstalleerd; alleen de HTTP-diagnose hierboven."]

    from .strategies.render_listing import accept_consent

    regels: list[str] = []
    api_treffers: list[str] = []
    api_alle: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            locale="nl-NL", timezone_id="Europe/Amsterdam",
            viewport={"width": 1366, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"))
        page = context.new_page()

        def op_response(response):
            # Álle JSON meenemen, niet alleen URL's die op een product-API lijken:
            # juist de endpoints die we níet herkennen zijn hier interessant.
            try:
                if "json" not in (response.headers or {}).get("content-type", "").lower():
                    return
                data = response.json()
            except Exception:
                return
            # élk JSON-antwoord vastleggen — Zeeman bleek een raster te hebben
            # dat nooit hydrateert, en dan is juist de vraag welke API's er
            # wél of níet langskomen (en met welke sleutels).
            if len(api_alle) < 8:
                keys = list(data)[:5] if isinstance(data, dict) else f"lijst[{len(data)}]"
                api_alle.append(f"{response.url[:100]} ({keys})")
            try:
                gevonden = deep_find_products(data, response.url)
            except Exception:
                return
            if gevonden and len(api_treffers) < 8:
                api_treffers.append(f"{response.url[:110]} → {len(gevonden)} producten, "
                                    f"bv. {gevonden[0].title[:40]!r} à {gevonden[0].price}")

        page.on("response", op_response)
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            status = resp.status if resp is not None else "?"
            geklikt = accept_consent(page)
            try:
                page.wait_for_load_state("networkidle", timeout=12000)
            except Exception:
                pass
            if not geklikt:
                # Cookiemuren laden asynchroon; bij Zeeman stond de muur er pas
                # ná de eerste klikpoging en bleef het raster daardoor leeg.
                geklikt = accept_consent(page)
                if geklikt:
                    page.wait_for_timeout(1000)
            try:
                links_voor = page.evaluate(
                    "() => document.querySelectorAll('a[href]').length")
            except Exception:
                links_voor = None
            # Trager en verder scrollen dan de scraper: zo blijkt of het raster
            # alleen maar méér geduld nodig had.
            for deel in (0.3, 0.6, 1.0):
                page.evaluate(f"() => window.scrollTo(0, document.body.scrollHeight * {deel})")
                page.wait_for_timeout(1200)
            info = page.evaluate(PAGINA_JS)
            html = page.content()
        except Exception as e:
            browser.close()
            return [f"- **browserfout:** {type(e).__name__}: {str(e)[:200]}"]

        regels += [
            f"- browser: HTTP {status}, cookiemuur "
            f"{'weggeklikt' if geklikt else 'niet gevonden (ook niet bij de tweede poging)'}",
            f"- titel: {info['titel']!r}",
            f"- {info['tekst']} tekens tekst, {info['links']} links"
            + (f" (vóór het scrollen: {links_voor})" if links_voor is not None else ""),
            f"- prijssignalen: {info['euro']}× €, {info['eur']}× 'EUR', "
            f"{info['prijsachtig']}× prijsachtig getal (3,99-patroon)",
        ]
        if info["pad"]:
            regels.append(f"- eerste prijsachtige getal staat in: `{info['pad']}`")
        if info["micro"]:
            regels.append(f"- microdata itemprop=price: {info['micro']}")
        if info["attr"]:
            regels.append(f"- prijs-attributen: {info['attr']}")
        regels.append(f"- JSON-scripts in de pagina: {info['scripts'] or 'geen'}")
        if info.get("teller"):
            regels.append(f"- artikelteller op de pagina: «{info['teller']}»")
        if info.get("pagLinks") or info.get("pagKnoppen"):
            regels.append(f"- paginering: links {info.get('pagLinks') or 'geen'}, "
                          f"knoppen/teksten {info.get('pagKnoppen') or 'geen'}")
        for i, kaart in enumerate(info.get("kaarten") or [], 1):
            regels.append(f"- kaarttekst {i} (klim↑ + tekst zoals de DOM-scan leest): «{kaart}»")

        na_render = products_from_html(html, url)
        regels.append(f"- producten uit de gerenderde HTML: {len(na_render)}")
        if api_treffers:
            regels.append("- **JSON-API's met producten** (betrouwbaarste route):")
            regels += [f"    - {t}" for t in api_treffers]
        else:
            regels.append("- JSON-API's met producten: geen onderschept")
        if api_alle:
            regels.append("- alle JSON-antwoorden tijdens het laden:")
            regels += [f"    - {t}" for t in api_alle]
        else:
            regels.append("- geen enkel JSON-antwoord tijdens het laden — de "
                          "pagina haalt zijn data dus niet via een API op")

        regels.append("")
        regels.append(f"**Conclusie:** {_conclusie(info, na_render, api_treffers)}")
        browser.close()
    return regels


def _conclusie(info: dict, na_render: list, api_treffers: list) -> str:
    if info["tekst"] < 500:
        return ("de pagina laadt vrijwel geen tekst — blokkade of challenge. "
                "Zonder residentiële proxy is deze bron niet te scrapen (PLAN.md §8).")
    if api_treffers:
        return ("er is een JSON-API met producten. Dat is de betrouwbaarste route: "
                "neem het endpoint over als vaste bron i.p.v. de HTML te lezen.")
    if na_render:
        return f"de gerenderde HTML bevat {len(na_render)} producten — de render-strategie werkt hier."
    if info["prijsachtig"] == 0:
        return ("de pagina toont géén enkel prijsachtig getal. Het productraster laadt niet: "
                "denk aan een regio-/winkelkeuze, een tweede consent-stap of inhoud die pas "
                "na interactie verschijnt. Extractie aanpassen heeft hier geen zin.")
    if info["euro"] == 0 and info["prijsachtig"] > 0:
        return ("er staan wél prijzen, maar zonder €-teken in de tekst (valutateken komt "
                "waarschijnlijk uit CSS). De los-prijs-ronde van de DOM-scan vangt dit.")
    if info["micro"] or info["attr"]:
        return ("prijzen staan in microdata of attributen in plaats van in de tekst — "
                "daar leest de extractie nu ook op.")
    return ("prijzen staan in de tekst maar worden niet aan een productkaart gekoppeld; "
            "kijk naar het DOM-pad hierboven om de kaartstructuur te vinden.")


def diagnose_rapport(urls: list[str], render: bool = True) -> str:
    kop = ["# Paginadiagnose", "",
           "*Waarom levert een pagina niets op? Deze meting toont álle signalen waar de "
           "extractie op kan aanhaken, inclusief de signalen die we nog niet gebruiken.*", ""]
    delen = []
    for u in urls:
        try:
            delen.append(diagnose(u, render=render))
        except Exception as e:  # één kapotte URL mag de rest niet meenemen
            delen.append(f"## {u}\n\n- **diagnosefout:** {type(e).__name__}: "
                         f"{str(e)[:200]}")
    return "\n".join(kop + delen)


def _dump(obj) -> str:  # handig bij handmatig debuggen
    return json.dumps(obj, ensure_ascii=False, indent=2)[:4000]
