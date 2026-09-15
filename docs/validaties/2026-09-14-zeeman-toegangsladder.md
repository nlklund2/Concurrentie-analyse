# Zeeman — dicht sinds W38: CloudFront weert elk datacenter-IP; toegangsladder als antwoord

**Datum:** 14-09-2026 · **Runs:** [34822128207](https://github.com/nlklund2/Concurrentie-analyse/actions/runs/34822128207) (weekrun 26, 10:19 NL, eerste 403), [34829744444](https://github.com/nlklund2/Concurrentie-analyse/actions/runs/34829744444) (weekrun 27, 11:46 NL, zelfde 403), [34850113902](https://github.com/nlklund2/Concurrentie-analyse/actions/runs/34850113902) (probe via de ladder, 15:34 NL), [34850110853](https://github.com/nlklund2/Concurrentie-analyse/actions/runs/34850110853) (toegangsmatrix, 15:34 NL), [34850724709](https://github.com/nlklund2/Concurrentie-analyse/actions/runs/34850724709) (toegangsmatrix mét Firecrawl enhanced en `?pageSize=`, 15:41 NL), [34851163036](https://github.com/nlklund2/Concurrentie-analyse/actions/runs/34851163036) (probe via de ladder tot en met de enhanced-trede, 15:45 NL)
**Besluit:** Zeeman blijft op de listing-route met flight-extractor, maar haalt zijn pagina's via de toegangsladder; sinds 14-09 is de trede `firecrawl` met `firecrawl_proxy: enhanced` (residentieel IP) de enige die binnenkomt. De gratis treden blijven als wekelijkse hertest in de ladder staan. Weekrun voor W38 en het structurele alternatief (thuis-runner) zijn een eigenaarsbesluit — zie onderaan.

## Aanleiding

W37 (maandag 07-09, run 24) was groen: 1.058 artikelen via de listing-route met flight-extractor,
tellercontrole 100%. W38 (maandag 14-09) begon met `HTTP 403 op https://www.zeeman.com/nl-nl/dames/ondergoed`
— op de allereerste seed, in beide runs van die ochtend (10:19 en 11:46 NL), zonder dat er aan
onze kant iets was veranderd (de weekworkflow en de Zeeman-configuratie waren sinds 04-09 gelijk).
De foutregel zei niet wíe er nee zei; de diagnose crashte op de 403 (`BlockedError` ongevangen).

## Meting 1 — wie zegt nee, en tegen wie? (toegangsmatrix, run 34850110853)

Dezelfde twee URL's (`/robots.txt` en `/nl-nl/dames/ondergoed`) via elke client die de monitor
in huis heeft, vanaf GitHub Actions (Azure, VS):

| Client | Antwoord |
|---|---|
| requests, kaal (de scraper tot 14-09) | **403** — `server: CloudFront`, titel "ERROR: The request could not be satisfied", tekst "Request blocked. We can't connect to the server for this app or website at this time" (919 tekens) |
| requests + volledige Chrome-headerset (sec-ch-ua, sec-fetch-*) | **403**, identiek |
| curl_cffi met het TLS-/HTTP2-handschrift van Chrome | **403**, identiek |
| echte Chromium (Playwright, stealth-script, 20 s gewacht op een challenge) | **403**, identiek — er is geen challenge, alleen een blokkade |
| Firecrawl, standaardproxy (datacenter), rawHtml | **403 van de bron**, dezelfde CloudFront-pagina (838 tekens), door Firecrawl als geslaagde scrape (HTTP 200) teruggegeven |

Ook `/robots.txt` is dicht. Geen `cf-ray`, geen Akamai-referentie, geen challenge-script: dit is
de blokkadepagina van **AWS WAF/CloudFront** ("Request blocked"). Dat de headerset, het
TLS-handschrift én een echte browser allemaal hetzelfde antwoord krijgen, en de standaardproxy
van Firecrawl ook, betekent dat de regel niet naar de *client* kijkt maar naar het **IP**: een
regel van het type "hosting-/cloudprovider-IP's weren" (AWS' managed rule group
*AnonymousIpList/HostingProviderIPList* of een eigen IP-set). Een geo-regel zou "block access
from your country" melden; die tekst ontbreekt.

De probe via de ladder (run 34850113902) bevestigt het van de andere kant: `http` → `chrome`
→ `browser` → `firecrawl` klommen keurig, allemaal geweigerd, in 24 s en 4 verzoeken.

## Meting 2 — komt een residentieel IP wél binnen? (run 34850724709)

Zelfde matrix, nu met Firecrawl's residentiële proxy (`proxy: enhanced`) als zesde rij, op drie
URL's:

| URL | requests / headers / curl_cffi / Chromium / Firecrawl basic | Firecrawl **enhanced** |
|---|---|---|
| `/robots.txt` | 5× **403** (CloudFront) | **200**, 858 tekens — de echte robots.txt |
| `/nl-nl/dames/ondergoed` | 5× **403** | **200**, 639.984 tekens, flight-payload met 30 producten, teller 298 artikelen op 10 pagina's (11,1 s) |
| `/nl-nl/dames/ondergoed?pageSize=100` | 5× **403** | **200**, 640.762 tekens, 30 producten, teller 298/10 — `pageSize` wordt genegeerd, dus geen kortere route dan ±49 pagina's per week |

De pagina die via het residentiële IP binnenkomt is dezelfde als op 04-09 (toen 710.037 tekens;
het verschil is content, de teller staat op 298 tegen 296): de flight-extractor leest hem
ongewijzigd. Het probleem zit dus uitsluitend in het IP waarvandaan gevraagd wordt.

robots.txt (via enhanced gelezen; de ladder leest hem voortaan via dezelfde trede als de
pagina's): `Disallow: /api/*`, zoeken, `?q=`, `?color`, `?sort`, `?variants.size`, afrekenen,
winkelwagen, account, reparatie. Onze categorie-URL's en `?page=N` staan er niet in.

## Meting 3 — de ladder van onder tot boven in één probe (run 34851163036)

`python -m scraper probe --retailer zeeman --limit 100` op de nieuwe configuratie
(`fetch_ladder: [http, chrome, browser, firecrawl]`, `firecrawl_proxy: enhanced`), 15:45 NL:

| Strategie | Categorieën | Artikelen | Binnen focus | Prijs | Kleur | Maten | Promo | Mapping | Requests | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **listing+firecrawl** | 14 | 100 | 100 | 100% | 100% | 100% | 5% | 100% | 8 | 🟢 ok — "klaar voor de wekelijkse run" |

- Verloop in de notities: `http` geweigerd op de eerste seed → `chrome` geweigerd op
  robots.txt → `browser` geweigerd op robots.txt → `firecrawl` (enhanced) leest robots.txt en
  daarna vier pagina's van `dames/ondergoed` (`?page=2` t/m `?page=4` — de paginering komt dus
  ook langs de poortwachter én robots.txt). Acht verzoeken in 84 s, waarvan 5 via Firecrawl.
- Tellercontrole 120 van 298 voor die ene categorie: de probe stopt bewust bij de limiet van
  100; in de weekrun loopt hij door tot de teller van de bron en keurt `_beoordeel` een
  tekort >5% af.
- Voorbeelden identiek aan de meting van 04-09 (Katy String €3,69, Cara Hipster €3,99, Plunge
  Padded BH €9,99 met maten 80D–95E), 'Uit onze folder' als promotekst — de extractie is
  ongewijzigd; alleen de toegangsroute is anders.
- Kosten: 5 Firecrawl-opvragingen met `proxy: enhanced`. De weekrun heeft er ±50 nodig
  (14 seeds, ±49 pagina's, plus robots.txt), gecapt op 60. Wat een enhanced-opvraging op het
  huidige plan kost, staat in het Firecrawl-dashboard; de docs noemen geen toeslag, oudere
  plannen rekenden 5 credits voor de residentiële proxy. **Controleer het verbruik na de
  eerste weekrun.**

## Wat er is veranderd

- `scraper/fetch.py` — **toegangsladder**: per bron een volgorde van clients (`fetch_ladder`),
  van goedkoop naar zwaar: `http` (requests) → `chrome` (curl_cffi, Chrome-handschrift) →
  `browser` (Playwright) → `firecrawl` (residentieel IP met `firecrawl_proxy: enhanced`;
  betaald, gecapt door `firecrawl_page_cap`). Klimt alleen bij een aantoonbare weigering
  (403/429 of challenge-pagina), leest robots.txt via dezelfde trede en meldt de trede in het
  weekrapport als `listing+chrome` e.d.
- `scraper/blokkade.py` — handtekening van de poortwachter (Cloudflare, Akamai, Vercel, AWS WAF,
  Imperva, DataDome, PerimeterX, of "onbekend, server: …") in de foutregel van het rapport.
- `scraper/http.py` — `BlockedError` draagt status, headers en body; optionele
  curl_cffi-impersonatie; volledige Chrome-headerset als variant.
- `scraper/diagnose.py` — bij een 403 geen crash maar een toegangsmatrix met conclusie.
- `scraper/strategies/firecrawl_api.py` — `_firecrawl_fetch` geeft de status van de bron terug
  (`metadata.statusCode`; een 403-pagina telde tot nu als geslaagde scrape) en kent de
  proxy-keuze (`basic`/`enhanced`/`auto`, met alias `stealth` voor oudere API-versies).
- `.github/workflows/toegangscheck.yml` — donderdagse kanarie: proefscrape zonder database,
  rood = job faalt = mail aan de eigenaar, vier dagen vóór de maandagrun.
- `scraper/retailers.yml` — Zeeman: `fetch_ladder: [http, chrome, browser, firecrawl]`,
  `firecrawl_proxy: enhanced`, `firecrawl_page_cap: 60`.
- Tests: `tests/test_blokkade.py`, `tests/test_fetch.py`, uitbreidingen in `test_diagnose.py`
  en `test_firecrawl.py` (177 groen).

## Wat níet is gedaan

- W38 is voor Zeeman niet opnieuw gemeten; de weekrun voor Zeeman start de eigenaar
  (`Wekelijkse scrape` → `retailers: zeeman`), want die kost credits en schrijft weekcijfers.
- De gratis treden blijven in de ladder staan als wekelijkse hertest: de dag dat CloudFront
  het IP van GitHub Actions weer toelaat, zakt de bron vanzelf terug naar `listing` — zonder
  configwijziging, zichtbaar in de strategiekolom.
- Structureel alternatief zónder credits: een **self-hosted runner op een thuisaansluiting**
  (NL, residentieel IP) die de Zeeman-job draait — zie het besluitvoorstel hieronder.

## Besluitvoorstel voor de eigenaar

Drie routes, oplopend in structurele waarde:

| Route | Wat het kost | Wat het oplevert | Wanneer |
|---|---|---|---|
| **A. Firecrawl enhanced** (staat klaar in de config) | credits per pagina volgens je Firecrawl-plan; ±49 pagina's per week voor Zeeman, gecapt op 60 | Zeeman deze week nog groen, geen handwerk | nu — start `Wekelijkse scrape` met `retailers: zeeman` |
| **B. Thuis-runner** (self-hosted GitHub-runner op een NL-thuisaansluiting: oude laptop, NAS of Raspberry Pi) | eenmalig ±30 min inrichten (`Settings → Actions → Runners → New self-hosted runner`), apparaat aan op maandagochtend | residentieel IP voor álle bronnen die datacenter-IP's weren — Zeeman zonder credits, en op termijn ook Wibra/HEMA zonder Firecrawl (±36 credits/week) | volgende sprint; de workflow krijgt dan een job `runs-on: [self-hosted, thuis]` voor die bronnen |
| **C. Officiële feed** (TradeTracker-productfeed van Zeeman, zie dossier 19-08) | aanvraag + schriftelijke toestemming voor concurrentieonderzoek | juridisch de schoonste route, geen scraper nodig | eigenaarsactie, doorlooptijd onbekend |

Aanbeveling: **A nu, B inplannen**. A houdt de weekreeks heel (W38 is nog te meten); B haalt de
kosten er structureel uit en maakt de monitor onafhankelijk van wat CloudFront volgende week
besluit. De ladder blijft in beide gevallen staan: zakt de blokkade, dan zakt Zeeman vanzelf
terug naar de gratis trede.
