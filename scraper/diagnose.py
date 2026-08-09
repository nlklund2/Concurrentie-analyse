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

from .http import Http
from .jsonscan import deep_find_products, products_from_html

# Prijsachtig zonder valutateken: 3,99 of 3.99, niet 35 - 46 (maten) en niet
# jaartallen. Bewust smal — dit is een signaal, geen extractieregel.
PRIJS_LOS_RE = re.compile(r"(?<![\d.,])\d{1,4}[.,]\d{2}(?![\d])")

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
      if (/(?:^|[^\d.,])\d{1,4}[.,]\d{2}(?!\d)/.test(n.nodeValue || '')) {
        const delen = [];
        let el = n.parentElement;
        while (el && delen.length < 5) {
          const cls = (typeof el.className === 'string' && el.className.trim())
            ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '';
          delen.unshift(el.tagName.toLowerCase() + cls);
          el = el.parentElement;
        }
        pad = delen.join(' > ') + '  «' + (n.nodeValue || '').trim().slice(0, 40) + '»';
        break;
      }
    }
  }
  return {
    titel: (document.title || '').slice(0, 90),
    tekst: tekst.length,
    links: document.querySelectorAll('a[href]').length,
    euro: (tekst.match(/€/g) || []).length,
    eur: (tekst.match(/\bEUR\b/g) || []).length,
    prijsachtig: (tekst.match(/(?:^|[^\d.,])\d{1,4}[.,]\d{2}(?!\d)/g) || []).length,
    attr, micro, scripts, pad,
  };
}
"""


def diagnose(url: str, render: bool = True) -> str:
    regels: list[str] = [f"## {url}", ""]
    http = Http(min_delay=0.5, respect_robots=True)
    resp = http.get(url)
    if resp is None:
        regels.append("- **HTTP: geen antwoord** — geblokkeerd, robots.txt of netwerkfout.")
    else:
        html = resp.text
        prods = products_from_html(html, url)
        regels += [
            f"- HTTP {resp.status_code}, {len(html)} tekens HTML",
            f"- in de kále HTML: {html.count('€')} €-tekens, "
            f"{len(PRIJS_LOS_RE.findall(html))} prijsachtige getallen, "
            f"{len(prods)} producten via de gewone extractie",
        ]
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
            f"- browser: HTTP {status}, cookiemuur {'weggeklikt' if geklikt else 'niet gevonden'}",
            f"- titel: {info['titel']!r}",
            f"- {info['tekst']} tekens tekst, {info['links']} links",
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

        na_render = products_from_html(html, url)
        regels.append(f"- producten uit de gerenderde HTML: {len(na_render)}")
        if api_treffers:
            regels.append("- **JSON-API's met producten** (betrouwbaarste route):")
            regels += [f"    - {t}" for t in api_treffers]
        else:
            regels.append("- JSON-API's met producten: geen onderschept")

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
    delen = [diagnose(u, render=render) for u in urls]
    return "\n".join(kop + delen)


def _dump(obj) -> str:  # handig bij handmatig debuggen
    return json.dumps(obj, ensure_ascii=False, indent=2)[:4000]
