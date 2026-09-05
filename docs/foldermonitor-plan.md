# Foldermonitor — add-on op de concurrentiemonitor (plan ter review)

*Status: 5 september 2026 — plan goedgekeurd (de drie besluiten uit §14 zijn genomen, zie [foldermonitor-fase0.md](foldermonitor-fase0.md)); fase 0 is gestart. Reviewer: de eigenaar (inkoopmanager) en de opdrachtgever.*

**In één zin:** de concurrentiemonitor ziet wat concurrenten *online* voeren; de foldermonitor legt vast wat zij *pushen* — de weekfolder — en bewaart die als bewijsstuk én als data, zodat samen de complete **retailkalender** van het concurrentieveld ontstaat. Scope start, net als de monitor, bij **ondergoedmode** (ondergoed, nachtmode, sokken & panty's).

---

## 0. Samenvatting voor de reviewer (1-pager)

**Besluit dat voorligt:** de foldermonitor bouwen als add-on ín de bestaande repo, het bestaande Supabase-project en de bestaande Netlify-site — geen aparte repo, geen tweede database (onderbouwing in §9). **Eis van de eigenaar (05-09):** eerst apart draaien en zichtbaar zijn náást productie, niet erin — ingevuld met een preview-omgeving (integratiebranch, tweede gratis Supabase-project, branch deploy op Netlify, feature-vlag) en een expliciete go-live (§9.5).

**Wat het oplevert, elke maandag naast het weekrapport:**
- per concurrent de folder van die week als PDF in het archief, doorbladerbaar in het dashboard;
- de bodywear-aanbiedingen uit die folder als data: artikel, prijs, van-prijs, actiemechanisme ("2 voor", "1+1"), pakgrootte, doelgroep, productgroep, pagina;
- een **retailkalender**: retailer × week — wie pusht wanneer welke bodywear, op welk prijspunt, met welk mechanisme;
- signalen en adviesregels in het weekrapport (§8): "Zeeman zet kinderboxers 3-pack in de folder op €5,99 — 25% onder terStal-instap; besluit: volgen, negeren of flankeren?"

**Waarom nu:** twee van de acht bronnen (Zeeman, Action) prijzen online niets af — hun hele promotiebeleid loopt via de folder. Zonder folder ziet de monitor bij precies de twee scherpste prijsvechters géén actie. Dat gat staat in PLAN.md §7 en §11.11 als fase-3-kandidaat; dit plan haalt het naar voren.

**Scenario's:**

| Scenario | Wat je krijgt | Bouw | Kosten/maand |
|---|---|---|---|
| **A. Archief** (fase 1) | folders binnenhalen, opslaan, bekijken; "folder aanwezig"-kalender | 2 dagdelen | €0 |
| **B. Archief + extractie** (fase 1–2, *aanbevolen*) | A + bodywear-aanbiedingen als data, folder-KPI's, signalen in het weekrapport | +3 dagdelen | ≈ €3–8 (vision-model) |
| **C. B + koppeling online** (fase 3) | B + folderprijs vs onlineprijs per artikel, folder-only-aandeel, adviesregels, retailkalender op aanbiedingen | +2 dagdelen | idem; opslag na ±5 maanden: €0 (R2) of €25 (Supabase Pro) |

**Quick wins (deze week, zonder code):** één neutraal mailadres aanmaken en inschrijven op de nieuwsbrieven van alle acht bronnen (30 min, eigenaar) — vanaf dan komt de folderkalender vanzelf binnen, ook als de bouw nog loopt. Plus: de eigenaar bewaart vanaf nu elke folder-PDF die hij toch al doorbladert in één map; dat wordt de eerste testset.

**Next step:** de drie besluiten uit §14 nemen → fase 0 (mailbox + validatieworkflow) start dezelfde week.

**Aannames:** (1) nieuwsbrieven kondigen elke folder aan (te bewijzen in fase 0; anders web-fallback §4.2); (2) folder-viewers (Publitas/iPaper/eigen) zijn vanaf GitHub Actions bereikbaar (Wibra/HEMA weren datacenter-IP's op hun eigen domein — de viewer draait meestal op een ander domein); (3) ±6 folders per week, ±24 pagina's per folder, ±20% bodywear-pagina's.

**Risico's, kort:** folders die niet via mail komen (→ web-fallback + handmatige upload), extractiefouten bij prijzen (→ kwaliteitspoort + controlelijst + eval op handgelabelde folders), opslaggroei voorbij de gratis 1 GB (→ retentie + keuze R2/Pro rond maand 3), en het bekende risico van elke monitor: stilte (→ §8 van het weekrapport met een eigen gezondheidstabel).

---

## 1. Doel — wat de folder toevoegt aan wat we al zien

De monitor meet het online assortiment: omvang, instroom, prijsniveau, sale-druk. Drie dingen mist die meting structureel, en alle drie zitten in de folder:

| Blinde vlek online | Wat de folder laat zien | Voorbeeld |
|---|---|---|
| Actieprijzen die niet online staan (Zeeman prijst online niets af; Action nauwelijks) | de werkelijke actieprijs en het mechanisme | "3 boxershorts €5,99" alleen in de folder |
| Timing en prioriteit: wat de concurrent *deze week* naar voren duwt | coverpositie, paginavolgorde, themapagina's | bodywear op de cover = seizoenstart |
| De promotiekalender over het jaar | folderfrequentie per groep, herhaalacties, seizoensritme | "Zeeman voert kindersokken in W36, W40, W44" |

Samen met de online meting ontstaat per concurrent per week één beeld: **wat voert hij, wat kost het, en wat pusht hij**. Dat is de retailkalender waar de inkoop- en actiekalender van terStal tegenaan gelegd kan worden.

**Wat het niet is:** geen omzet- of voorraadschatting, geen automatische prijsaanpassing, geen dagelijkse alerts. Het maandagritueel uit PLAN.md §1 blijft het ritme; de folder is een extra sectie in hetzelfde rapport, geen tweede kanaal.

## 2. Wat we vastleggen — twee lagen

### Laag 1: het origineel (bewijsstuk)
Advies over de vorm, want de vraag stond open:

| Vorm | Rol | Waarom |
|---|---|---|
| **PDF** (canoniek) | archiefstuk en bewijs | leesbaar over 5 jaar, één bestand per folder, deelbaar, te printen; als de bron een PDF aanbiedt bewaren we die, anders bouwen we hem uit de paginabeelden |
| **WebP per pagina** (werkformaat) | dashboardviewer + invoer voor de extractie | snel laden per pagina, ±120 KB per pagina op 1.200 px breed |
| **Mail-metadata** (herkomst) | provenance | afzender, datum, onderwerp, message-id, link naar de viewer; de HTML-mail zelf bewaren we niet (links verlopen, geen bewijswaarde) |

Niet als canoniek formaat: de HTML-nieuwsbrief (verlopen links), screenshots van folder-aggregators (rechten, kwaliteit), alleen de viewer-URL (verdwijnt na de looptijd).

### Laag 2: de data
Per folder: retailer, geldigheid (van/tot), ontvangst, aantal pagina's, thema per pagina, bodywear-pagina's. Per bodywear-aanbieding: artikelnaam, merk, prijs, van-prijs, actietekst en -type, pakgrootte, prijs per stuk, doelgroep, productgroep (via de bestaande `mapping.yml`), pagina, heropositie, betrouwbaarheid, en waar mogelijk de koppeling naar het online artikel in `products`. Details in §6.

## 3. Bronnen en folderritme

Zelfde acht bronnen als de monitor (`scraper/retailers.yml`), zodat online en folder per retailer naast elkaar staan. Ritme en route zijn de startaannames; fase 0 valideert ze per bron met een eigen workflow (§4.4).

| Bron | Folderritme (aanname) | Verwachte route | Bodywear in folder |
|---|---|---|---|
| terStal (referentie) | ±2-wekelijks, aankondiging per nieuwsbrief (komt al binnen: "De nieuwe folder is uit!", link naar de online folder, geen PDF-bijlage) | mail-link → viewer | eigen folder = referentie voor de folderindex |
| Zeeman | wekelijks; promotie loopt volledig via de folder ('Uit onze folder'-label online) | nieuwsbrief + folderpagina zeeman.com | hoog, kerncategorie |
| Wibra | tweewekelijks (bv. 31-08 t/m 13-09), nieuwe folder in het weekend | nieuwsbrief + wibra.nl/folder (let op: wibra.nl weert datacenter-IP's; de viewer zelf mogelijk niet) | hoog |
| Action | wekelijks, elke **woensdag**, geldig wo–di; ook een "folder volgende week"-pagina | nieuwsbrief + action.com/nl-nl/folder | wisselend, multipacks sokken/boxers |
| HEMA | wekelijks, aanbiedingen wisselen op maandag | nieuwsbrief + hema.nl (weert datacenter-IP's) | middel, bh's/ondergoed |
| KiK | wekelijks, "Online folder" op kik.nl | nieuwsbrief + kik.nl/Online-folder | hoog |
| C&A | geen klassieke weekfolder; wel "aanbiedingen"-mailings en online-lookbooks | nieuwsbrief | laag; mail-only |
| Primark | geen folder, geen webshop; nieuwsbrief met collecties | nieuwsbrief | laag; alleen kalendersignaal |

**Fase 2-kandidaten (folder-only bronnen):** Lidl en Aldi — bodywear zit daar uitsluitend in folderacties (PLAN.md §3 sluit ze daarom online uit). De foldermonitor is precies het instrument waarmee ze wél meetbaar worden. Ook Kruidvat/Trekpleister (sokken, panty's) passen in dit stramien. Uitbreiden pas na drie weken bewezen ritueel, conform PLAN.md §3.

Bronnen komen in `folders/bronnen.yml`, gespiegeld aan `retailers.yml`: per bron `mail_from` (afzenderdomeinen), `folder_url` (web-fallback), `viewer` (`auto | publitas | ipaper | pages | render`), `cadence_days`, `enabled`.

## 4. Hoe folders binnenkomen

Kern van het ontwerp: **de mail is de trigger, de viewer is de bron, de upload is het vangnet.** De terStal-mail bewijst waarom: hij bevat geen PDF, alleen "onze folder is uit!" met een link. De folder zelf moet dus altijd nog worden opgehaald.

### 4.1 Mailbox (primaire trigger) — PLAN.md §11.11
- **Eén neutraal, nieuw mailadres** (Gmail), uitsluitend voor dit doel. Aanbevolen boven een terStal-adres: inschrijven met een @terstal-adres maakt zichtbaar dát en wát er gemonitord wordt (PLAN.md §8). Besluit §14.1.
- **Plus-aliassen per bron**: `<adres>+zeeman@gmail.com`, `<adres>+wibra@gmail.com`, … De retailer stuurt vaak via een derde partij (terStal via Bloomreach); het alias maakt de koppeling afzender → bron deterministisch, ongeacht het verzenddomein.
- **Ophalen vanuit GitHub Actions via IMAP** (`imaplib`, standaardbibliotheek, geen extra afhankelijkheid) met een Google app-wachtwoord (2-staps-verificatie verplicht). Secrets: `FOLDER_IMAP_USER`, `FOLDER_IMAP_PASSWORD` — alleen in GitHub Secrets, nooit in repo of dashboard. Alternatief bij bezwaar tegen IMAP: Gmail API met OAuth-refreshtoken (meer inrichting, zelfde resultaat).
- **Wat de sweep doet:** ongelezen mails lezen → bron bepalen (alias, anders afzenderdomein) → folderlinks en PDF-bijlagen herkennen → registreren in `folders` (status `nieuw`) → mail markeren als verwerkt. Geen mail wordt verwijderd; de mailbox is het tweede archief.
- **Privacy/AVG:** de mailbox ontvangt alleen marketingmail van bedrijven; geen persoonsgegevens van derden. Trackingpixels en -links in die mails melden de afzender dat er geopend/geklikt wordt — accepteren, of de sweep laat links onaangeroerd en haalt de folder via de folderpagina (§4.2).

### 4.2 Web-fallback (secundaire trigger)
Eén lichte opvraging per bron per dag van de folderpagina (`folder_url`): verschijnt er een nieuwe publicatie-ID of geldigheidsdatum, dan wordt de folder geregistreerd alsof hij per mail kwam (`source = 'web'`). Dekt bronnen die niet elke folder per mail aankondigen. Voor Wibra/HEMA geldt de bekende IP-wering op het eigen domein; de route loopt dan via de viewer op zijn eigen domein of, als laatste, via Firecrawl (±1 credit per opvraging, bestaande secret).

### 4.3 Handmatige upload (vangnet)
In het dashboard (achter de login) een upload van een PDF naar bucket `folders-inbox/<retailer>/`. De eerstvolgende run verwerkt hem als `source = 'upload'`. Dit garandeert 100% dekking vanaf week 1, ongeacht hoe de techniek per bron uitpakt, en is de route voor folders die iemand fysiek in handen heeft (scan).

### 4.4 Capture: van viewer naar PDF en pagina's
Per `viewer`-type een capture-strategie, in dezelfde watervalgedachte als de scraper:

| Strategie | Hoe | Wanneer |
|---|---|---|
| `pdf` | directe PDF-download (bijlage, downloadknop, of viewer-endpoint) | als de bron het aanbiedt — beste kwaliteit |
| `pages` | paginabeelden van de viewer opvragen (Publitas/iPaper/eigen viewer serveren per pagina een afbeelding) | de meest voorkomende route |
| `render` | headless browser (Playwright, staat al in de workflows): folder doorbladeren, per pagina een screenshot | als de viewer geen losse beelden prijsgeeft |

Uitkomst is altijd gelijk: pagina-WebP's + één PDF (samengesteld uit de beelden met `img2pdf`, of de originele PDF gecomprimeerd met Ghostscript tot ≤ 8 MB). Dedupe op SHA-256 van de pagina's: dezelfde folder via mail én web wordt één record.

**Workflow "Validatie folders"** (spiegel van "Validatie bronnen"): per bron folderpagina ophalen, viewer detecteren, aantal pagina's tellen, capture proberen, rapport in de job-samenvatting. Bevindingen per bron in `docs/validaties/`, met run-id's — dezelfde bewijsdiscipline als bij de scraper. Livevalidatie kan alleen op GitHub Actions (netwerk naar de retailers is vanuit de ontwikkelomgeving dicht).

## 5. Verwerking — van pagina naar data

```
sweep (mail/web/upload)      capture               classificatie          extractie              poort            verwerking
folders(status=nieuw)  ──►  PDF + WebP/pagina  ──►  thema per pagina  ──►  bodywear-pagina's  ──►  plausibel?  ──►  folder_offers
                             naar Storage           (alle pagina's)         → aanbiedingen         ja: verwerkt     folder_weekly_stats
                                                                                                    nee: controle    weekrapport §8
```

### 5.1 Classificatie (alle pagina's, goedkoop)
Per pagina: thema (`bodywear | kleding | huis | speelgoed | food | overig`), bevat-bodywear ja/nee, hero (cover/pagina 2–3). Dit levert de **retailkalender voor álle categorieën** bijna gratis op, terwijl de dure extractie beperkt blijft tot bodywear-pagina's (±20%).

### 5.2 Extractie (alleen bodywear-pagina's)
Drie lagen, goedkoop vóór duur:
1. **Tekstlaag** van de PDF (`pymupdf`), als de bron een echte PDF levert: gratis, exact. Folders uit viewers zijn beeld — dan is er geen tekstlaag.
2. **Vision-model** op het paginabeeld met een vast JSON-schema (structured outputs): per aanbieding artikelnaam, merk, prijs, van-prijs, actietekst, pakgrootte, maten, doelgroep, productgroep, positie op de pagina, `confidence`. Advies: Claude Opus 5 (`claude-opus-5`) voor de extractie — prijzen, superscript-centen ("5⁹⁹"), "vanaf"-prijzen en pakgroottes zijn precies waar goedkope modellen misgaan; Claude Haiku 4.5 (`claude-haiku-4-5`) voor de paginaclassificatie. Via de Batch API (nachtelijke job, 50% korting). Kosten in §10. OCR met Tesseract is bewust geen laag: folderlay-outs (prijsvlakken, gesplitste centen) leveren daar te veel ruis.
3. **Mens** voor de restcategorie: aanbiedingen met `confidence < 0,7` of onwaarschijnlijke prijzen komen op een **controlelijst** in het dashboard (10 minuten per week voor de eigenaar, zoals het mapping-onderhoud in PLAN.md §6.7).

Na de extractie draait dezelfde normalisatie als bij de scraper: `mapping.yml` voor doelgroep/productgroep, `normalize.pack_size()` voor pakgrootte, `promo.py`-patronen voor het actietype → prijs per stuk en effectieve actieprijs. Eén taxonomie voor online en folder, anders is de vergelijking later handwerk.

### 5.3 Kwaliteitspoort (heilig, zoals bij de scraper)
Een folder wordt pas `verwerkt` als: ≥ 1 bodywear-pagina herkend óf expliciet "geen bodywear" (ook een geldige uitkomst), ≥ 90% van de aanbiedingen een prijs draagt, prijzen binnen €0,50–€60, geldigheidsdatums geparset. Anders status `controle` en een oranje regel in het weekrapport — nooit halve data in de kalender.

### 5.4 Bewijs eerst: de eval
Vóór fase 2 live gaat: drie folders handmatig labelen (eigenaar, ±1 uur) → extractie erlangs → precisie/recall per veld in `docs/validaties/`. Drempel om live te gaan: ≥ 90% correcte prijzen, ≥ 85% correcte productgroepen. Zonder dit cijfer is de folderindex een belofte, geen meting.

### 5.5 Koppeling aan online artikelen (fase 3)
Folderaanbieding → online artikel binnen dezelfde bron: `pg_trgm`-gelijkenis op titel binnen doelgroep × productgroep × pakgrootte; EAN als de folder hem noemt (zelden). `match_confidence` wordt opgeslagen; alleen matches ≥ 0,8 voeden de vergelijking folderprijs vs onlineprijs. Wat niet matcht is het **folder-only-aandeel** — op zichzelf al een signaal (winkel-exclusieve acties).

## 6. Datamodel (Supabase, zelfde project)

Sluit aan op het bestaande schema: `retailers` blijft de sleutel, weekdefinitie blijft de maandag, aggregaten krijgen dezelfde sleutel als `weekly_stats` zodat het dashboard online en folder in één query naast elkaar zet.

**Weekregel:** een folder telt mee in elke week waarin hij op de **maandag** (peildatum) geldig is. Action wo 02-09 t/m di 08-09 → week 37 (maandag 07-09). Wibra 31-08 t/m 13-09 → week 36 én 37.

### Tabellen (schets; definitieve DDL in `sql/migratie_folders.sql`)
```sql
create table folders (
  id            bigint generated by default as identity primary key,
  retailer_id   text not null references retailers(id),
  source        text not null check (source in ('mail','web','upload')),
  title         text,
  valid_from    date,
  valid_to      date,
  received_at   timestamptz not null default now(),
  mail_message_id text,                 -- herkomst
  mail_subject  text,
  viewer_url    text,
  pdf_path      text,                   -- storage: folders/<retailer>/<jaar>/<id>.pdf
  page_count    int,
  sha256        text unique,            -- dedupe mail/web/upload
  status        text not null default 'nieuw'
                check (status in ('nieuw','gearchiveerd','verwerkt','controle','fout')),
  note          text
);

create table folder_pages (
  folder_id     bigint references folders(id) on delete cascade,
  page_no       int not null,
  image_path    text,                   -- storage: folders/<retailer>/<jaar>/<id>/p<nn>.webp
  theme         text,                   -- bodywear | kleding | huis | speelgoed | food | overig
  has_bodywear  boolean,
  is_hero       boolean default false,  -- cover / pagina 2-3
  text_layer    text,                   -- tekst uit de PDF, indien aanwezig
  primary key (folder_id, page_no)
);

create table folder_offers (
  id            bigint generated by default as identity primary key,
  folder_id     bigint references folders(id) on delete cascade,
  retailer_id   text not null,
  page_no       int,
  title         text not null,
  brand         text,
  audience      text not null default 'onbekend',
  product_type  text not null default 'overig',
  pack_size     int not null default 1,
  sizes         text,
  price         numeric(10,2),
  was_price     numeric(10,2),
  promo_text    text,                   -- ruwe actietekst ('2 voor € 7,50')
  promo_type    text,                   -- bundel | gratis_erbij | tweede_halve_prijs | percentage | afprijzing | geen
  effective_price numeric(10,2),        -- effectieve prijs per stuk bij minimale afname
  is_hero       boolean default false,
  confidence    numeric(4,3),
  extraction    text,                   -- textlayer | vision | manual
  product_key   text,                   -- koppeling naar products (fase 3)
  match_confidence numeric(4,3),
  reviewed      boolean default false   -- controlelijst afgevinkt
);

create table folder_weekly_stats (      -- zelfde sleutel als weekly_stats
  retailer_id   text not null,
  week          date not null,
  audience      text not null,
  product_type  text not null,
  offer_count   int not null default 0,
  hero_count    int not null default 0,
  price_min     numeric(10,2),
  price_median  numeric(10,2),
  unit_price_median numeric(10,2),
  multibuy_share numeric(6,4),
  discount_share numeric(6,4),
  primary key (retailer_id, week, audience, product_type)
);

create table folder_runs (              -- gezondheid, zoals scrape_runs
  id bigint generated by default as identity primary key,
  retailer_id text, week date, run_at timestamptz default now(),
  step text, status text, note text     -- sweep | capture | extract
);
```

**Views (Nederlandstalig, exporteerbaar):** `v_folders` (folder per bron per week, met status), `v_folder_aanbiedingen` (artnaam t/m prijs per stuk, per folder en pagina), `v_retailkalender` (retailer × week: folder ja/nee, bodywear-pagina's, aantal aanbiedingen, instapprijs, mechanismen, thema's).

**Verwerkingsfunctie:** `process_folder_week(p_retailer, p_week)` berekent `folder_weekly_stats` set-based, idempotent per (bron, week) — zelfde patroon als `process_staging`, alleen uitvoerbaar door de service-rol.

**Storage:** bucket `folders` (privé) voor PDF's en pagina's, bucket `folders-inbox` (privé, upload door ingelogde gebruikers). Padconventie `folders/<retailer>/<jaar>/<folder_id>.pdf` en `/<folder_id>/p01.webp`. Lezen via signed URLs vanuit het dashboard (alleen ingelogd), schrijven alleen door de service-rol. Storage-policies in dezelfde migratie.

**RLS:** alle nieuwe tabellen `lezen_ingelogd` (select voor `authenticated`), schrijven uitsluitend service-rol; `folder_offers.reviewed` mag door ingelogde gebruikers worden bijgewerkt (controlelijst) — de enige schrijfpolicy voor clients.

**Omvang:** ±300 folders/jaar × ±20 bodywear-aanbiedingen ≈ 6.000 rijen/jaar — verwaarloosbaar voor de database. De opslag (bestanden) is het aandachtspunt, zie §9.4.

## 7. KPI's — de folderset en de retailkalender

Klein en scherp, per **concurrent × productgroep × week**, naast de bestaande set uit PLAN.md §2:

| KPI | Definitie | Waarom het telt |
|---|---|---|
| **Folderaanwezigheid** | folder geldig op de maandag (ja/nee) en aantal bodywear-pagina's | wie voert deze week een bodywear-actie? |
| **Aanbiedingen** | aantal bodywear-aanbiedingen, waarvan hero (cover/p2–3) | intensiteit en prioriteit |
| **Folder-instap en -mediaan** | min, p25, mediaan van de folderprijs; ook per stuk | het prijsbeeld dat de klant deze week in de bus krijgt |
| **Mechanismen-mix** | aandeel afprijzing / multibuy ("2 voor", "1+1") / percentage | discounters vechten met multibuy; de mix verraadt de tactiek |
| **Folderindex t.o.v. terStal** | folder-mediaan concurrent ÷ terStal-mediaan (online én folder) × 100 | objectiveert "zijn wij in de folderweek te duur?" |
| **Folder vs online** (fase 3) | folderprijs ÷ onlineprijs van hetzelfde artikel; folder-only-aandeel | is de folderkorting echt? wat blijft winkel-exclusief? |
| **Herhaalcadans** | weken tussen twee folderacties op hetzelfde artikel/groep | voorspelt wanneer de volgende actie komt |
| **Seizoensklok** | retailer × weeknummer, na 52 weken jaar-op-jaar | "Zeeman start nachtmode-acties in W38" — stuurt de inkoopkalender |

**Signaalregels (weekrapport §8, deterministisch, geen black box):**
- folderaanbieding in een groep ≥ 15% onder de terStal-instap (online) → *prijssignaal*;
- bodywear op de cover of ≥ 3 bodywear-pagina's → *seizoen-/prioriteitssignaal*;
- ≥ 3 bronnen met multibuy in dezelfde groep in dezelfde week → *multibuy-golf*;
- folderprijs = onlineprijs (geen echte korting) → *prijsimago-signaal*;
- eerste folder van een bron in ≥ 6 weken met bodywear → *herstart*.

**Adviesregels:** elk signaal krijgt een vaste adviesvorm — *volgen / negeren / flankeren / timing verschuiven* — met de cijfers erbij, zodat het maandagoverleg een besluit kan nemen in plaats van een analyse. Tot het besluit over de doelpositie per groep (PLAN.md §6.2) zijn adviezen informatief, niet normatief. Optioneel later: een gegenereerde weeksamenvatting op basis van de signaalregels, expliciet gelabeld als concept.

## 8. Weekrapport en dashboard

**Weekrapport (`scraper/report.py`) — nieuwe sectie §8 "Folders van de week":**
1. gezondheid: per bron folder ontvangen (mail/web/upload), status, pagina's, extractie-dekking — dezelfde 🟢🟠🔴-logica als §1;
2. retailkalender-regel: per bron "folder W37: 24 p., 5 p. bodywear, 18 aanbiedingen, instap €1,99, 40% multibuy";
3. signalen + advies (§7);
4. top-10 scherpste folderaanbiedingen in bodywear t.o.v. terStal.
Loopt de folderrun stuk, dan zegt §8 dat expliciet; de rest van het rapport blijft intact.

**Dashboard (Netlify, zelfde site, zelfde login) — nieuwe pagina `dashboard/folders.html`:**
- **Retailkalender**: heatmap retailer × week (intensiteit = bodywear-aanbiedingen), klik → folder;
- **Folderviewer**: pagina's uit Storage via signed URLs, bodywear-pagina's gemarkeerd, aanbiedingen als overlay/lijst per pagina;
- **Aanbiedingen-tabel**: filters op bron/groep/mechanisme/week, CSV-export (zoals `v_artikelen_week`);
- **Folder vs online** (fase 3): per artikel folderprijs, onlineprijs, verschil;
- **Controlelijst**: aanbiedingen met lage betrouwbaarheid, afvinken (`reviewed`);
- **Upload**: PDF naar `folders-inbox`.
Aparte pagina in plaats van een tab in `index.html` (1.047 regels): houdt beide onderhoudbaar; `config.js` en het login-fragment worden gedeeld.

## 9. Architectuur-advies: GitHub, Supabase, Netlify, opslag

### 9.1 GitHub: zelfde repo (aanbevolen), geen aparte repo

| | Zelfde repo (add-on) | Aparte repo |
|---|---|---|
| Taxonomie & normalisatie (`mapping.yml`, `normalize.py`, `promo.py`) | hergebruik, één waarheid | kopie → drift, twee keer onderhoud |
| Secrets, CI, workflows, validatiedossier | bestaand, één plek | tweede set, tweede ritueel |
| Weekrapport | één document met §8 | cross-repo orkestratie nodig |
| Dashboard | zelfde site, zelfde login | tweede site of cross-repo deploy |
| Ownership | zelfde eigenaar (inkoopmanager) | alleen zinvol bij een ander team |
| Risico | repo groeit; CI duurt langer (marginaal) | het geheel valt uiteen in twee half gevolgde tools |

**Verdict:** add-on in deze repo. De waarde zit in de combinatie; splitsen maakt precies dat duurder. Structuur:

```
folders/                    nieuw Python-pakket (naast scraper/)
  bronnen.yml               bronnen, aliassen, folder-URL's, viewer-type
  __main__.py               python -m folders sweep | capture | extract | process | validate
  mail.py                   IMAP-sweep
  capture/                  pdf.py · pages.py · render.py (Playwright)
  classify.py, extract.py   Claude API (Batch), JSON-schema's
  storage.py                Supabase Storage-client (S3-compatibel; later R2 zonder codewijziging elders)
scraper/report.py           §8 erbij (leest folder-tabellen)
dashboard/folders.html      retailkalender, viewer, controlelijst, upload
sql/migratie_folders.sql    tabellen, views, functie, storage-policies, RLS
.github/workflows/
  dagelijkse-foldersweep.yml   cron ma–za, sweep + capture + extract (±2 min/dag)
  validatie-folders.yml        workflow_dispatch, routes per bron testen
  wekelijkse-scrape.yml        ongewijzigd, behalve: rapport leest nu ook folders
tests/test_folders_*.py     mailparser, viewerdetectie, poort, weekregel, promo-normalisatie
docs/validaties/            folderroutes per bron met run-id's
```

Ritme: een **dagelijkse sweep** (ma–za, cron buiten het hele uur, bv. `23 3 * * 1-6` = 05:23 NL-zomertijd / 04:23 wintertijd) omdat folders op wisselende dagen verschijnen (Action woensdag, Wibra weekend, HEMA maandag) en maillinks kunnen verlopen; het maandagrapport leest de database. Kosten: ±2 minuten Actions per dag, ruim binnen de gratis 2.000 minuten. Best-effort-cron blijft gelden: de folderrun meldt zichzelf in §8, en `folder_runs` maakt een gemiste dag zichtbaar.

### 9.2 Supabase: zelfde project `concurrentiemonitor-terstal`
- Folder-data verwijst naar `retailers` en (fase 3) naar `products`; dat kan alleen binnen één database.
- Eén auth, één RLS-beleid, één anon-key in het dashboard.
- Free-tier telt maximaal 2 actieve projecten; een tweede project zou het enige reserve-slot opmaken zonder iets op te leveren.
- Storage-buckets zitten in hetzelfde project; policies in dezelfde migratie.

### 9.3 Netlify: zelfde site, extra pagina
Geen tweede site: dezelfde `netlify.toml`, dezelfde omgevingsvariabelen, dezelfde magic-link-login en dezelfde `noindex`-headers. Alternatieven (GitHub Pages, Vercel, Cloudflare Pages) voegen niets toe en kosten een tweede inrichting. Mocht de opslag later naar R2 gaan, dan levert een Netlify Function (gratis tier: 125.000 aanroepen/mnd) de signed URLs.

### 9.4 Bestandsopslag: de enige echte keuze

Rekensom (aannames §0): ±8 MB per folder (PDF ≤ 5 MB + 24 WebP's ≈ 3 MB) × ±300 folders/jaar ≈ **2,4 GB/jaar**. Supabase Free geeft 1 GB opslag, 50 MB per bestand, 5 GB egress/maand. Het archief loopt dus na **±5 maanden** uit de gratis tier.

| Optie | Kosten | Integratie | Oordeel |
|---|---|---|---|
| **Supabase Storage** (zelfde project) | €0 tot 1 GB; daarna Pro €25/mnd (100 GB, 8 GB db, geen pauzering, backups) | beste: RLS, signed URLs, één client | **start hier** |
| **Cloudflare R2** | €0 tot 10 GB, geen egresskosten; S3-API | apart account + secret; signed URLs via Netlify Function | **beste vervolg** als €0 leidend blijft (±4 jaar archief) |
| SharePoint/OneDrive (M365 van terStal) | €0 (bestaande licentie) | Graph-API-app via IT; geen koppeling met dashboard-login | alleen als extra kopie van de PDF's (bewijsarchief), niet als werkopslag |
| Google Drive | €0 tot 15 GB | apart account; zwakke koppeling met RLS | niet aanbevolen |
| GitHub (repo/LFS/Releases) | LFS betaald boven 1 GB; Releases oneigenlijk | geen viewer | niet aanbevolen |

**Advies:** start op Supabase Storage (nul nieuwe accounts, beste integratie), met `folders/storage.py` als enige laag die weet wáár bestanden staan. Retentie vanaf dag 1: pagina-WebP's 52 weken, PDF's 5 jaar. Rond **maand 3** het besluit: R2 (€0) of Supabase Pro (€25/mnd, en dan is meteen de Firecrawl-vraag uit PLAN.md §11E in hetzelfde budgetgesprek). De verhuizing is dan één configuratiewijziging plus één kopieerscript.

### 9.5 Parallel draaien: preview naast productie (eis eigenaar, 05-09)

**Eis:** de foldermonitor draait en is zichtbaar vóórdat hij in productie komt. Weekrapport, dashboard en database van de monitor blijven ongewijzigd tot een expliciete go-live.

| Laag | Productie (blijft zoals nu) | Preview (nieuw, ernaast) | Hoe gescheiden |
|---|---|---|---|
| **Code** | `main` | integratiebranch `foldermonitor`; feature-PR's gaan dáárheen; één go-live-PR naar `main` | CI draait al op elke branch; `main` ziet niets tot de go-live-PR |
| **Database + opslag** | project `concurrentiemonitor-terstal` | tweede gratis Supabase-project `concurrentiemonitor-preview` (eigen 500 MB db, eigen 1 GB storage, eigen auth) | de foldercode leest alleen `FOLDERS_SUPABASE_URL` / `FOLDERS_SUPABASE_SERVICE_ROLE_KEY`; productiesleutels bereiken hem niet |
| **Dashboard** | `concurrentiemonitor-terstal.netlify.app` | branch deploy `foldermonitor--concurrentiemonitor-terstal.netlify.app` en deploy previews: `dashboard/build.sh` kiest buiten de productiecontext het preview-project (`PREVIEW_SUPABASE_URL`/`_ANON_KEY`) | zelfde Netlify-site, eigen URL, eigen config; productievariabelen onaangeraakt |
| **Planning (cron)** | `wekelijkse-scrape.yml` | `foldermonitor-preview.yml` op `main`: cron + `actions/checkout` van `ref: vars.FOLDERS_REF` (= `foldermonitor`), draait tegen GitHub Environment `preview` | GitHub voert cron alleen uit op de default branch; dit ene workflowbestand is het enige dat `main` raakt en wijzigt niets aan de scraper of het rapport |

**Waarom een tweede project en geen apart schema of tabelprefix in het productieproject:** de service-rolsleutel omzeilt RLS; dev-code mét die sleutel kán productietabellen raken. Geen sleutel = geen risico. Bijvangst: 1 GB extra opslag tijdens de bouw en een schone meting van de opslaggroei. Supabase Branching is de officiële variant, maar vereist het Pro-plan (€25/mnd) — nu niet nodig. Free tier staat 2 actieve projecten toe; de monitor is er één, de overige projecten in de organisatie zijn gepauzeerd.

**Wat de preview uit productie nodig heeft:** alleen `retailers` (upsert uit `folders/bronnen.yml`, zoals `ensure_retailers` dat nu doet). De koppeling aan `products` (fase 3) volgt na de go-live, of tijdens de preview met een wekelijkse read-only kopie uit de ruwe dumps van de scraper.

**Zichtbaar voor de eigenaar tijdens de bouw:** het preview-dashboard (magic-link-login via het preview-project, dezelfde genodigden), de job-samenvatting van elke preview-run met het folderrapport, en de PR's naar `foldermonitor`.

**Secrets en variabelen:**
- GitHub Environment `preview`: `FOLDERS_SUPABASE_URL`, `FOLDERS_SUPABASE_SERVICE_ROLE_KEY`, `FOLDER_IMAP_USER`, `FOLDER_IMAP_PASSWORD`, `ANTHROPIC_API_KEY`; repository-variabele `FOLDERS_REF=foldermonitor`.
- Netlify: `PREVIEW_SUPABASE_URL` en `PREVIEW_SUPABASE_ANON_KEY`; `build.sh` schakelt erop zodra Netlify's `CONTEXT` ≠ `production`. De productiewaarden blijven staan en worden niet aangeraakt (gebouwd 05-09, zie `foldermonitor-fase0.md`).
- Supabase preview-project: Auth → Site URL en redirect op de branch-URL; gebruikers uitnodigen.

**Feature-vlag `FOLDERS_ENABLED`:** rapport §8 en de folderpagina in het dashboard bestaan alleen mét de vlag. Ook ná de merge naar `main` blijft productie dus ongewijzigd tot de vlag aan staat — de go-live is een bewuste handeling, geen bijeffect van een merge.

**Go-live (na review, één middag):**
1. go-live-PR `foldermonitor` → `main` (code-review; validatiedossier per bron compleet; eval §5.4 gehaald);
2. `sql/migratie_folders.sql` op het productieproject;
3. data: de mailbox is de bron van waarheid — de sweep opnieuw draaien tegen productie haalt alle folders terug (alleen de extractie kost opnieuw, ±€1 per week historie); alternatief `python -m folders promote` dat rijen en bestanden kopieert;
4. Environment `production` met de productiewaarden van `FOLDERS_SUPABASE_*`; `FOLDERS_REF=main`; `FOLDERS_ENABLED=true` in Actions én Netlify;
5. preview-project pauzeren; het blijft staging voor volgende wijzigingen.

**Kosten:** €0 extra. **Tijd:** +0,5 dagdeel inrichting in fase 0.

## 10. Kosten

| Post | Verbruik | Kosten/maand |
|---|---|---|
| GitHub Actions | +±60 min (dagelijkse sweep) | €0 |
| Supabase database | +±10 MB/jaar | €0 |
| Supabase Storage | ±200 MB/maand groei | €0 tot maand ±5; daarna R2 €0 of Pro €25 |
| Claude API — classificatie (Haiku 4.5, $1/$5 per 1M tokens) | ±150 pagina's/week × ±1.700 tokens in, ±60 uit | ≈ $0,30/week |
| Claude API — extractie (Opus 5, $5/$25 per 1M tokens) | ±30 bodywear-pagina's/week × ±2.500 in, ±800 uit | ≈ $1,00/week; via Batch API de helft |
| Firecrawl (alleen als viewer-domeinen weren) | ±5 credits/week | binnen bestaand tegoed |
| **Totaal** | | **≈ €3–6/maand**; opslag is de enige post die groeit |

De €0-opzet van de monitor breekt hier dus voor het eerst structureel, met een paar euro per maand. Sonnet 5 ($2/$10) als extractiemodel scheelt ±60% als de eval (§5.4) laat zien dat de precisie gelijk blijft — meten, niet aannemen.

## 11. Juridisch & fair use
- Folders zijn **publiek marketingmateriaal**, bedoeld voor verspreiding; archiveren en intern analyseren is staande praktijk (folder-aggregators doen het commercieel).
- Inschrijven op nieuwsbrieven is de door de retailer zelf aangeboden route; opzeggen kan altijd. Het "neutrale adres" is een beleidskeuze (PLAN.md §8), geen verhulling van iets onrechtmatigs.
- Geen herpublicatie: PDF's en pagina's blijven achter de login; het dashboard is `noindex`.
- Aggregators (Folderz, AlleFolders, Reclamefolder) **niet** scrapen: eigen voorwaarden, en de retailer zelf is de primaire bron. Alleen als bewuste laatste fallback na een eigenaarsbesluit.
- Laat deze uitbreiding meelopen in de eenmalige juridische toetsing uit PLAN.md §6.8.

## 12. Risico's & mitigaties

| Risico | Impact | Beheersing |
|---|---|---|
| Nieuwsbrief kondigt niet elke folder aan | gat in de kalender | web-fallback (§4.2) + handmatige upload; dekking per bron in §8 zichtbaar |
| Viewer-platform wijzigt of weert | capture valt uit | validatieworkflow + `render`-fallback; oranje in §8 |
| Wibra/HEMA weren ook de viewer | bron rood | viewer-domein testen; Firecrawl als laatste; upload-vangnet |
| Extractiefouten (centen, "vanaf", pakgrootte) | verkeerde index | kwaliteitspoort, controlelijst, eval op handgelabelde folders vóór livegang |
| Opslag groeit voorbij gratis tier | kosten of stilstand | retentie; besluit R2/Pro in maand 3; storage-laag is verwisselbaar |
| Mailbox-credentials | toegang tot marketingmail | app-wachtwoord alleen in GitHub Secrets; mailbox zonder ander gebruik; 2FA |
| Cron best effort (gemiste dag) | folder een dag later | dagelijkse cadans vangt het op; `folder_runs` toont gaten |
| Stille dood | niemand kijkt | §8 in hetzelfde rapport; controlelijst met eigenaar; actieteller (PLAN.md §11E) telt foldersignalen mee |

## 13. Roadmap

| Fase | Wanneer | Wat | Klaar als |
|---|---|---|---|
| **0. Besluiten & instap** | deze week | §14 beslissen; mailbox + aliassen; inschrijven bij 8 bronnen (eigenaar, 30 min); preview-omgeving inrichten (§9.5: branch, preview-project, Netlify-context, Environment `preview`, scheduler); workflow "Validatie folders"; eerste 3 folder-PDF's handmatig verzamelen | per bron staat de route (mail/web/upload) met run-id in `docs/validaties/`; preview-dashboard bereikbaar |
| **1. Archief** | week 1–2 | migratie + buckets (preview-project); sweep + capture; upload; folderrapport in de job-samenvatting; dashboardpagina met viewer en aanwezigheidskalender (branch deploy) | maandag ligt van elke kernbron de folder van die week in het preview-archief |
| **2. Extractie** | week 3–4 | classificatie + bodywear-extractie; poort; `folder_offers`/weekstats; controlelijst; eval op 3 folders; signalen in §8 | eval ≥ 90% prijzen correct; §8 toont aanbiedingen en signalen |
| **3. Go-live, kalender & advies** | week 5–6 | go-live volgens §9.5 (merge, migratie productie, vlag aan); koppeling folder ↔ online; folder-only-aandeel; adviesregels; retailkalender op aanbiedingen; Lidl/Aldi als folder-only bronnen | §8 staat in het productie-weekrapport; maandagoverleg neemt ≥ 1 besluit per 2 weken op een foldersignaal |
| **4. Volwassen** | kwartaal 2+ | seizoensklok jaar-op-jaar; opslagbesluit uitgevoerd; eventueel historie uit folderarchieven (gelabeld *gereconstrueerd*) | kalender voorspelt de eerstvolgende actieweek per bron |

Bouwinspanning totaal ±4–5 dagen, verspreid over 6 weken; eigenaarstijd ±1 uur per week (controlelijst + maandagoverleg).

## 14. Besluiten aan de eigenaar (max. 3)

1. **Mailbox:** nieuw neutraal Gmail-adres (aanbevolen) of een terStal-/M365-mailbox (IT-inrichting, zichtbaar meekijken)?
2. **Opslagpad:** starten op Supabase Storage met het besluit R2/Pro in maand 3 (aanbevolen), of R2 vanaf dag 1?
3. **Extractie:** akkoord met een vision-model (Claude API, ≈ €3–6/maand) voor folderpagina's zonder tekstlaag, of eerst alleen scenario A (archief) draaien?

Bij akkoord op 1–3 start fase 0 dezelfde week. Bij twijfel over 3: fase 1 heeft het antwoord niet nodig; het besluit kan tot week 3 wachten zonder vertraging.

---

## Bijlage A — extractieschema (JSON, structured outputs)
```json
{
  "page_no": 7,
  "theme": "bodywear",
  "is_hero": false,
  "offers": [
    {
      "title": "Kinderboxers katoen 3-pack",
      "brand": null,
      "audience": "jongens",
      "product_type": "ondergoed",
      "pack_size": 3,
      "sizes": "92-164",
      "price": 5.99,
      "was_price": null,
      "promo_text": "3 stuks",
      "promo_type": "geen",
      "confidence": 0.93
    }
  ]
}
```
`audience`/`product_type` worden ná de extractie opnieuw door `mapping.yml` gehaald; het model levert de ruwe termen, de mapping beslist.

## Bijlage B — voorbeeld weekrapport §8
```
## 8. Folders van de week

| Bron | Folder | Geldig | Pagina's | Bodywear | Aanbiedingen | Status |
|---|---|---|---|---:|---:|---|
| Zeeman | mail | 07-09 – 13-09 | 20 | 4 p. | 17 | 🟢 verwerkt |
| Action | web | 02-09 – 08-09 | 28 | 1 p. | 4 | 🟢 verwerkt |
| Wibra | mail | 31-08 – 13-09 | 24 | 6 p. | 22 | 🟠 controle (3 prijzen onzeker) |
| HEMA | – | – | – | – | – | ⚪ geen folder ontvangen |

Signalen
- Zeeman · jongens/ondergoed: 3-pack boxers €5,99 (folder) = €2,00/stuk, 25% onder terStal-instap €2,66/stuk → advies: besluit volgen/negeren; check kwaliteit fysiek (PLAN.md §6.5).
- Wibra · dames/nachtmode op cover, 6 bodywear-pagina's → seizoenstart nachtmode ligt bij Wibra in W36; terStal-inkoopkalender rekent op W39.
- Multibuy-golf sokken: Zeeman, Wibra, Action alle drie "2 voor" in W37 → eigen sokkenactie nu plannen = middenin de golf; overweeg W39.
```

## Bijlage C — bronnen bij de aannames
- Action: folderpagina en ritme (elke woensdag, geldig wo–di): https://www.action.com/nl-nl/folder/ · https://www.action.com/nl-nl/app/folder-volgende-week/
- Wibra: tweewekelijkse folder, nieuwe folder in het weekend: https://www.allefolders.nl/wibra/folder-aanbiedingen · https://www.folderz.nl/winkels/wibra/folders-aanbiedingen
- KiK: online folder: https://www.kik.nl/Online-folder
- HEMA: wekelijkse wissel op maandag: https://folders.nl/winkels/hema
- Publitas als folderplatform met distributie naar Folderz.nl: https://www.publitas.com/integrations/folderz-nl/
- Supabase Free-limieten (1 GB storage, 50 MB per bestand, 5 GB egress, 2 actieve projecten): https://costbench.com/software/database-as-service/supabase/free-plan/ · https://uibakery.io/blog/supabase-pricing
- terStal-nieuwsbrief "De nieuwe folder is uit!" (05-09-2026, afzender newsletter@m.terstal.nl via Bloomreach): link naar de online folder, geen PDF-bijlage — de reden dat mail hier trigger is en niet drager.
