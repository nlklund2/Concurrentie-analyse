# Concurrentiemonitor terStal — strategisch plan

*Wekelijkse monitoring van assortiment en prijsvorming bij de concurrenten van terStal familiemode (±200 winkels, waardesegment gezinsmode).*

**Scope: ondergoedmode** — ondergoed, nachtmode en sokken & panty's, over alle doelgroepen (dames, heren, kinderen, baby). Bewust smal gestart: bodywear is de frequentie- en vertrouwenscategorie van de familiewinkel, prijzen zijn er goed vergelijkbaar en de klant kent ze uit het hoofd. De tool is gebouwd om de scope met één configuratieregel te verbreden (badmode erbij, of het volledige assortiment) zodra het maandagritueel staat.

---

## 1. Waarom dit instrument — en de eerste kritische vraag

De verleiding van elk monitoring-project is: "we willen alles kunnen zien." De realiteit van elke retailer die wint: **je wint niet door te kijken, je wint door sneller te beslissen dan de concurrent.**

Daarom begint dit plan niet bij techniek maar bij het **beslisritme**:

> **Elke maandag om 09:00 ligt er een weekrapport klaar. Om 09:15 is er een overleg van maximaal 15 minuten. Daaruit komen maximaal 3 acties.**

Voorbeelden van zulke acties:
- "Zeeman heeft de instapprijs van kinderboxers verlaagd van €3,99 naar €2,99 — beslissen we deze week of we volgen, en zo nee, wat vertellen we de winkels?"
- "Wibra bouwt in 3 weken tijd 40 artikelen nachtmode dames op — trekt het seizoen eerder aan dan onze inkoopkalender aanneemt?"
- "Takko zit op 34% afgeprijsd assortiment (vorige maand 19%) — zij zitten op voorraad. Wij houden vol prijs vast en pakken marge."

Als het rapport drie weken achter elkaar alleen "bekeken" wordt zonder actie, is de tool een speeltje geworden. Dan is niet de techniek kapot, maar het ritueel.

## 2. Wat we meten (de KPI-set)

Alles per **concurrent × productgroep × week**. Bewust een kleine, scherpe set — geen dashboard-kerstboom.

### Assortiment (omvang & beweging)
| KPI | Definitie | Waarom het telt |
|---|---|---|
| **Omvang** | Aantal actieve artikelen online | Waar zet de concurrent zijn geld op in? |
| **Instroom** | Nieuwe artikelen deze week | Seizoenstiming, trendadoptie, nieuwheid |
| **Uitstroom** | Verdwenen artikelen deze week | Sanering, uitverkoop-einde, doorloopsnelheid |

### Prijsvorming
| KPI | Definitie | Waarom het telt |
|---|---|---|
| **Instapniveau** | Laagste prijs + 25e percentiel | Het prijsbeeld dat de klant "voelt" bij binnenkomst |
| **Mediaanprijs** | Middelste prijs van de groep | Robuuste kern van de prijsstelling (geen gemiddelde: dat vervuilt door uitschieters) |
| **Prijspuntenverdeling** | Histogram op €-prijspunten | Waardesegment draait op prijspunten (€3,99/€4,99/€7,99). Verschuiving = stille inflatie of agressie |
| **Sale-druk** | % artikelen met doorstreepte prijs + gem. kortingsdiepte | Marge-indicator: hoge sale-druk = voorraadprobleem bij de concurrent = kans voor ons |
| **Prijsindex vs. terStal** | Mediaan concurrent ÷ mediaan terStal × 100 | Objectivering van "zijn wij te duur/te goedkoop?" per groep |

Cruciaal detail: **terStal.nl wordt zélf ook wekelijks gescraped**, met exact dezelfde methode. Zonder eigen cijfers in hetzelfde formaat is elke vergelijking handwerk; mét eigen cijfers rekent de prijsindex zichzelf uit.

### Productgroepen (uniforme taxonomie)
Elke concurrent hanteert zijn eigen indeling; wij mappen alles naar twee assen:
- **Doelgroep**: dames · heren · meisjes · jongens · baby · kinderen (ongesplitst) · huis · onbekend
- **Producttype**: shirts & tops · truien & vesten · broeken & jeans · jurken & rokken · jassen · ondergoed · nachtmode · sokken & panty's · badmode · schoenen · sport · accessoires · huistextiel · overig

Binnen de huidige focus vullen alleen **ondergoed, nachtmode en sokken & panty's** zich; de taxonomie is compleet gehouden zodat verbreden later geen verbouwing is (`focus_*` in `scraper/retailers.yml`).

Wat niet mapt, valt zichtbaar in "onbekend/overig" — dat is een werklijst om de mappingregels aan te scherpen, geen vuilnisbak om te negeren. Streefwaarde: ≥85% gemapt per bron.

### Vastlegging op artikelniveau
Naast de aggregaten wordt **per artikel per week** een regel bewaard: artnr · artnaam · hoofdcategorie (doelgroep) · categorie (producttype) · bron-categoriepad · kleur · maten · van-prijs · voor-prijs · URL. Opvragen en exporteren (CSV) kan direct via de view `v_artikelen_week` in Supabase. Kleur en maten zijn per bron *best effort*: lijstpagina's tonen ze zelden, dus een gecapte verrijkingsstap haalt ze van de productpagina's van vooral nieuwe artikelen; het validatierapport toont de dekking per bron. Let op: "maten" betekent *aangeboden* maten, geen voorraad per maat.

## 3. Het concurrentieveld — het gekozen speelveld ondergoedmode

**Kern (wekelijks gevolgd):**

| Bron | Waarom in het ondergoed-speelveld |
|---|---|
| *terStal (zelf)* | Referentielijn voor alle indexen — zonder eigen cijfers geen vergelijking |
| **Zeeman** | Dé maatstaf in waarde-bodywear; prijspuntendiscipline om van te leren |
| **Wibra** | Zelfde klant, zelfde straat; ondergoed/nachtmode is er kerncategorie |
| **Primark** | Volume-speler bodywear; geen webshop-verkoop, wel prijzen op primark.com — prijsreferentie met beperktere online-dekking |
| **Action** | Prijszetter in multipacks (sokken, boxers); smal maar prijsbepalend |
| **HEMA** | Sterk merk in ondergoed/bh's; markeert de bovengrens van het prijsveld |
| **C&A** | Breed gezinsondergoed; het middensegment waar klanten naartoe kunnen weglekken |

Het veld dekt zo bewust de hele prijsladder: Action/KiK-niveau onderin, Zeeman/Wibra/Primark als directe vechters, C&A/HEMA als bovenkant. Zo zie je niet alleen wie er onder je zit, maar ook hoeveel ruimte er boven je is.

**Fase 2 (uitgeschakeld klaargezet in de configuratie):** Takko, KiK, Scapino, Shoeby, MS Mode, Bonprix — aanzetten is één regel (`enabled: true`) plus een validatierun.

**Bewust (nog) niet:** H&M/Zara (ander segment), Lidl/Aldi (bodywear zit in folder-acties, niet in doorlopend online assortiment — zie folder-suggestie in §7), bol/Amazon (marktplaats-ruis).

> **Kritische vraag hierbij:** zeven bronnen goed gevolgd verslaat dertien half gevolgd. Uitbreiden (meer bronnen óf bredere scope) mag pas als de maandag-actie-teller drie weken op rij ≥1 staat.

## 4. Methode — en waarom deze zo gekozen is

### Online is een steekproef, geen volkstelling
De webshop van Zeeman of Wibra toont niet 1-op-1 het winkelschap; actie-artikelen en winkel-exclusives ontbreken deels. Dat is acceptabel omdat we **trends** meten (richting en tempo), geen absolute waarheid. De bias is per concurrent redelijk constant, dus week-op-week-vergelijkingen blijven valide. We zeggen dus nooit "Zeeman heeft 412 damesartikelen" maar "Zeeman's damesassortiment online groeide 12% in 4 weken".

### Artikelniveau mét kleur en maten — voorraaddiepte niet
Per artikel leggen we wekelijks ook kleur en aangeboden maten vast. Omdat lijstpagina's die zelden tonen, worden ontbrekende kleur/maten via de productpagina aangevuld met een cap per bron (`enrich_limit`, standaard 150/week) — minuten extra, geen uren, en de bron blijft te vriend. Wat we bewust níet doen: **voorraad per maat** volgen (uitverkochte maten = harde loper). Dat is een prachtig dieptesignaal maar vertienvoudigt de datalast; het blijft een fase-3-kandidaat voor een handjevol vechtartikelen.

### Wekelijks, niet dagelijks
Mode in het waardesegment beweegt in weken, niet in uren. Dagelijks scrapen kost 7× zoveel, irriteert de bron en produceert vooral ruis. Eén nachtelijke run in de nacht van zondag op maandag is het juiste ritme bij het maandagritueel.

### Kostenefficiënt scrapen: lijstpagina's, geen productpagina's
De naïeve aanpak (elke productpagina apart ophalen) kost bij een assortiment van 10.000 artikelen ~3 uur per site per week — dat past niet in gratis rekenminuten en is onbeleefd richting de bron. Daarom werkt de scraper met een **watervalstrategie per bron**, van goedkoop naar duur:
1. **Shopify-JSON** (`/products.json`): 250 artikelen per request — vrijwel gratis;
2. **Categorielijstpagina's**: 24–48 artikelen per pagina, producten worden uit de ingebedde JSON van de pagina gelezen (JSON-LD, `__NEXT_DATA__` e.d.) — ~10 min per site;
3. **Sitemap + productpagina's**: alleen voor kleine assortimenten (cap ingebouwd).

De `auto`-modus detecteert per bron wat werkt en rapporteert dat. Verandert een concurrent zijn platform, dan zie je dat maandag in de bron-gezondheidstabel — niet drie maanden later.

De **ondergoedfocus versterkt dit nog eens**: de crawler beperkt zich tot ondergoed-/nachtmode-/sokkencategorieën (een categoriefilter op de URL) en filtert daarna nogmaals op productgroep. Dat scheelt ~80–90% van de requests, houdt de bronnen te vriend en maakt de wekelijkse run in minuten klaar in plaats van uren.

### Beleefd en verdedigbaar
Max ~1 request/seconde, robots.txt wordt gerespecteerd, één run per week, alleen publieke productdata, geen persoonsgegevens (AVG niet geraakt), geen inlog- of betaalmuren. Zie §8.

## 5. Architectuur & kosten

```
GitHub Actions (cron, ma 06:07)          Supabase (Postgres, gratis tier)
┌─────────────────────────────┐          ┌──────────────────────────────┐
│ 1. scrape alle bronnen      │─ upsert ►│ products   (actueel + histor.)│
│ 2. verwerk in database ─────┼─ RPC ───►│ price_events (alleen mutaties)│
│ 3. genereer weekrapport     │          │ weekly_stats (aggregaten)     │
│ 4. commit rapport + e-mail  │          │ scrape_runs  (gezondheid)     │
└─────────────────────────────┘          └───────────┬──────────────────┘
        ruwe dumps als artifact                      │ leesrechten (RLS,
        (60 dagen bewaard)                           │ alleen ingelogd)
                                                     ▼
                                         Netlify (statisch dashboard)
                                         trends · prijsindex · movers
                                         magic-link-login (Supabase Auth)
```

**Waarom deze verdeling zuinig is:**
- **Compact opslaan.** Voor de trends: actuele stand per artikel + een event bij elke wijziging (nieuw/prijs op/prijs af/promo/weg) + kant-en-klare weekaggregaten. Daarnaast — binnen de ondergoedfocus goed betaalbaar — een **wekelijkse artikelfoto** (`weekly_articles`): per artikel per week artnr, naam, hoofdcategorie, categorie, kleur, maten, van-/voor-prijs en URL, opvraagbaar via de Nederlandstalige view `v_artikelen_week` (±35 MB/jaar; bij verbreding naar het volledige assortiment hoort een bewaartermijn — zie het commentaar in `sql/schema.sql`). De database blijft jaren binnen de gratis 500 MB.
- **Zware verwerking in één SQL-functie** in Supabase (set-based), niet in Python-lusjes — sneller én minder rekenminuten.
- **Dashboard leest alleen aggregaten** — laadt in milliseconden, geen serverkosten.
- **Ruwe dumps** (jsonl.gz) als Actions-artifact met 60 dagen retentie: gratis herberekenbaarheid zonder database-vervuiling.

**Kostenraming:**

| Post | Tier | Verwacht verbruik | Kosten |
|---|---|---|---|
| GitHub Actions | 2.000 min/mnd gratis (private repo) | ±15–30 min/week dankzij de categoriefocus | €0 |
| Supabase | Free (500 MB db, 50k MAU auth) | < 100 MB na jaar 1 | €0 |
| Netlify | Free (100 GB bandbreedte) | verwaarloosbaar (intern gebruik) | €0 |
| E-mail (Resend, optioneel) | 3.000 mails/mnd gratis | ±10/mnd | €0 |
| **Totaal** | | | **€0/maand** |

Het reële kostenrisico is niet geld maar **stilte**: een scraper die stuk gaat en waar niemand naar omkijkt. Daarom staat de bron-gezondheidstabel bovenáán het weekrapport, met harde afwijkingsdrempels (zie §9).

## 6. Kritische vragen aan de business (beantwoorden vóór week 1)

1. **Wie is de eigenaar?** ✅ **Besloten: de inkoopmanager.** De inkoopmanager agendeert het maandagoverleg, bewaakt de actieteller en onderhoudt maandelijks de categoriemapping (§6.7).
2. **Wat is ons prijsbeleid per groep?** Volgen we Zeeman op basics? Willen we ±5% rond Wibra zitten op nachtmode? Zonder doelpositie is elk prijssignaal vrijblijvend. Advies: leg per productgroep één regel vast ("index 95–105 t.o.v. Zeeman op kinderbasics"). ⏳ **Status: bewust nog open** — de doelpositie wordt bepaald op basis van de eerste 4–6 weken data in het dashboard. Agendeer het besluit zodra er vier meetweken zijn; tot die tijd zijn prijssignalen informatief, niet normatief.
3. **Welke 30 artikelen bepalen ons ondergoed-prijsimago?** De klant kent geen honderden prijzen, maar wel de boxers 3-pack, dameshipsters multipack, kindersokken 5-pack, basis-bh en de flanellen pyjama. Maak die **KVI-lijst** en koppel per KVI handmatig het vergelijkbare artikel per concurrent. *KVI = key value item, in gewoon Nederlands een bekende-prijs-artikel: een artikel waarvan de klant de prijs uit het hoofd kent en waarop ze het prijsimago van de hele winkel beoordeelt. Retailwet: op KVI's moet de prijs kloppen — desnoods ten koste van marge — en op de rest van het assortiment haal je die marge terug. De monitor vergelijkt automatisch groepsmedianen (het kompas); de KVI-koppellijst maakt het artikel-op-artikel scherp.* Dit is de enige plek waar handwerk loont — één middag werk voor de inkoopmanager, blijvend rendement. (De datastructuur ondersteunt dit; zie roadmap fase 2.)
4. **Accepteren we de online-bias?** Ja, mits we trends lezen en geen absolute aantallen citeren. Wie winkelwaarheid wil: combineer met de folder-check (§7) en twee fysieke concurrentiebezoeken per maand — de tool vertelt wáár je moet kijken.
5. **Prijs zegt niets over kwaliteit.** Een €4,99-shirt bij KiK kan 120 grams zijn waar het onze 160 grams is. De index is een kompas, geen rechter. Grote afwijkingen eerst fysiek checken, dan pas reageren.
6. **Wat doen we bewust níet?** Geen omzet- of voorraadschattingen (drijfzand), geen dagelijkse frequentie, geen 13 bronnen in week 1, geen automatische prijsaanpassingen. Elke "zou ook kunnen"-uitbreiding komt pas na drie weken bewezen ritueel.
7. **Wie onderhoudt de mapping?** Categorieregels verslijten (concurrenten hernoemen categorieën). Afspraak: de eigenaar kijkt maandelijks 15 min naar de "onbekend/overig"-bak.
8. **Is juridisch akkoord?** Zie §8 — laat de afweging één keer formeel aftikken, niet impliciet.
9. **Wanneer is dit geslaagd?** Voorstel: na 8 weken zijn er ≥6 acties uit het maandagoverleg gekomen waarvan ≥2 aantoonbaar marge of omzet hebben opgeleverd. Zo niet: stoppen of herontwerpen — ook dat is winst.
10. **Wie mag erbij?** Dashboard staat achter een login (magic link). Hoe breder de toegang, hoe groter de kans dat "wij monitoren de concurrent" op straat ligt — en concurrenten lezen ook. Advies: klein houden (inkoop, pricing, directie).

## 7. Suggesties om te wínnen (niet alleen te kijken)

- **Prijspuntenradar.** Het waardesegment communiceert in prijspunten. Als Zeeman massaal artikelen van €3,99 naar €4,49 tilt, is dat verkapte inflatie — en jouw kans om met €3,99 het prijsimago te pakken terwijl je marge elders haalt. Het histogram in het dashboard laat dit in één oogopslag zien.
- **Nieuwheid als trendradar.** De instroomlijst per week is een gratis trendbureau: als drie concurrenten tegelijk "seamless", "bralette" of "thermo" instromen, weet inkoop wat het volgende seizoen doet. Suggestie voor fase 2: automatische woordfrequentie-analyse op titels van nieuwe artikelen.
- **Sale-druk als margesignaal.** Stijgende sale-druk bij een concurrent betekent voorraadpijn. Dat is hét moment om juist níet mee te zakken maar vol prijs vast te houden — of gericht de artikelen te verlagen waar de concurrent al doorheen is.
- **Seizoensklok.** Na 52 weken data ontstaat het echte goud: week-op-week-vergelijking met vorig jaar. "Wibra start nachtmode-opbouw dit jaar in week 33, vorig jaar week 35" — dat soort signalen stuurt de inkoopkalender. Begin dáárom nu: de waarde van dit instrument groeit met elke week historie en is met geen geld achteraf te koop.
- **Folder-flankering.** Zeeman en Wibra vechten via de weekfolder. De online monitor vangt dat deels; wie het compleet wil, laat de eigenaar wekelijks 10 minuten de digitale folders doorbladeren met het weekrapport ernaast. Fase-3-kandidaat: folder-PDF's automatisch archiveren.
- **Winkelbezoek met richting.** De tool vervangt het winkelbezoek niet — hij maakt het scherp. Ga niet "rondkijken bij Zeeman", maar "check of de nieuwe €2,99-kinderlijn in de winkel ligt en hoe de kwaliteit voelt".

## 8. Juridisch & fair use

- We verzamelen uitsluitend **publiek zichtbare productinformatie** (titel, categorie, prijs) — geen persoonsgegevens (AVG niet van toepassing), niets achter een login.
- **Beleefdheid ingebouwd:** ~1 request/sec, één run per week, robots.txt wordt gerespecteerd (overtredingen worden gelogd en overgeslagen).
- Prijsmonitoring van concurrenten is **staande praktijk in retail** (er bestaat een hele industrie omheen); het Europese databankenrecht en site-voorwaarden vormen in theorie een restrisico. De volumes hier zijn minimaal en de data wordt niet herpubliceerd — intern beslisgebruik. **Advies: laat dit één keer formeel toetsen door de huisjurist en leg het besluit vast.**
- De scraper gebruikt een standaard browser-identificatie. Alternatief is een herkenbare eigen user-agent met contactgegevens — netter, maar het maakt zichtbaar dát en wát je monitort. Dat is een beleidskeuze voor de eigenaar; technisch is het één regel in de configuratie.

### Bronnen die het datacenter-IP weren (Wibra, HEMA) — de proxy-afweging
Sommige retailers blokkeren niet de scraper-*techniek* maar het *IP-adres*: verkeer vanaf de datacenter-IP's van GitHub Actions (Azure) wordt categorisch geweigerd, óók van een volwaardige headless browser. Zelf een betere scraper bouwen lost dit principieel niet op — het probleem zit in het herkenbare server-IP, niet in de browser. De enige technische route is het verkeer via **residentiële/roterende proxies** laten lopen, en dat levert een externe dienst (Firecrawl, ScrapingBee, ScraperAPI, Zyte) kant-en-klaar. De monitor heeft hiervoor een `firecrawl`-strategie klaarstaan, die **alleen activeert met een `FIRECRAWL_API_KEY`**. Afweging voor de eigenaar:
- **Kosten:** gratis start (~500 pagina's eenmalig), daarna ±€16/mnd (hobby-tier). Dit is de eerste post die de €0-opzet doorbreekt.
- **Privacy/juridisch:** de te scrapen product-URL's gaan naar een derde partij; de proxy-aanpak omzeilt bewust een IP-blokkade, wat het "publiek toegankelijk"-argument iets minder sterk maakt. Neem dit mee in de juridische toetsing hierboven.
- **Waarde:** Wibra is een directe kernconcurrent (zelfde klant, zelfde straat); die missen doet pijn. HEMA markeert de bovenkant. Voor die twee kan ±€16/mnd verdedigbaar zijn — maar het is een **business**beslissing, geen technische.
- **Alternatief zonder kosten:** Wibra/HEMA afdekken via de weekfolder-check en het gerichte winkelbezoek (§7), en leunen op de wél-werkende bronnen die hetzelfde prijssegment beslaan (KiK, Action, C&A).

**Stand 09-08 na zes validatierondes:** de IP-blokkade ís doorbroken — Firecrawl komt bij beide sites binnen. Maar daarachter geven ze hun assortiment niet prijs: Wibra's productpagina's dragen geen enkele machineleesbare productdata (0 van 38), HEMA's productraster rendert niet binnen de snapshot, ook niet na scroll-acties. Betalen voor de hobby-tier lost dat dus **niet** op; het probleem is niet meer het IP.

**DOORBRAAK 10-08 (meetronde 2-3): Wibra loopt volledig mee.** De sitemap-index verried dat wibra.nl op WordPress/WooCommerce draait, en de publieke Store-API (`/wp-json/wc/store/v1/products`) staat open. De nieuwe `firecrawl_mode: wp_store` haalt de complete catalogus op in ±8 opvragingen per week — gevalideerd op GitHub Actions: 800 artikelen, 100% prijsdekking, 64% kleur, 33% maten, alle doelgroepen, prijzen correct omgerekend uit minor units. Dat is rijkere data dan de meeste lijstpagina-bronnen leveren, voor minder credits dan één vergeefse pages-run kostte. De les voor volgende bronnen: kijk éérst welk platform een site draait — het platform verraadt de goedkoopste route.

**DOORBRAAK 10-08 (meetronde 5-6): HEMA loopt mee.** Het raster verschijnt wél in de snapshot met 8 s extra rendertijd; zes rondes lang bleef het onleesbaar omdat elke tegel zijn naam, masterSKU en prijs draagt als **HTML-ge-escapete JSON in een attribuut** (`&quot;price&quot;:&quot;8.69&quot;`) — onzichtbaar voor tekst-, script- en dataLayer-lezers. De nieuwe escaped-attrs-extractie ontcijfert dat. Bewijsprobe: **181 artikelen uit 20 categorieën, 159 binnen focus, 100% prijs- en kleurdekking**, ±24 credits per run. De promo-drempel van 60 blijft als slot op de deur staan.

**Creditprognose per week (stand 10-08):** Wibra ±9 (Store-API) + HEMA ±24 (20 categorieën met rendertijd) ≈ **±33 credits per week**. Het resterende gratis tegoed (±175 na het onderzoek van dit weekend) dekt zo'n **vijf weken**; daarna is de afweging voor de eigenaar: het betaalde Firecrawl-tier (±€16/mnd) voor twee volwaardig meelopende kernconcurrenten, of HEMA terugschroeven naar minder categorieën. Die keuze hoeft pas rond half september.

**Zeeman (eindoordeel 10-08):** langs alle wegen gemeten en uitgeput. Categoriepagina's hydrateren niet — óók niet in een echte browser met consent en scrollen — `/api/*` is per robots.txt verboden (dat respecteren we), en de productpagina's uit de sitemap (9.672 binnen focus) dragen geen eigen productdata: in de slotprobe gaven 19 van 25 pagina's hetzelfde gedeelde aanraderblok terug, ook aan de nieuwe extractieroutes. Zeeman blijft wekelijks meelopen als goedkope hertest (render, gratis) met de kwaliteitspoort dicht; de weekfolder en het winkelbezoek (§7) zijn het alternatief voor prijspeiling. Dit is de enige bron van de acht zonder machineleesbare route.

**Besluit van de eigenaar (09-08): beide bronnen blijven wekelijks meelopen als hertest.** Sites veranderen, en de dag dat het raster wél rendert wil je het diezelfde maandag zien. Om te voorkomen dat die hertest het gratis tegoed opmaakt, kent de firecrawl-strategie een **kanarie** (`firecrawl_canary` in `retailers.yml`): levert de eerste handvol opvragingen niets leesbaars op, dan stopt de run daar. Dat drukt het weekverbruik van ±66 naar ±14 credits — genoeg voor maanden hertesten in plaats van vier weken. Geeft de kanarie wél data, dan loopt dezelfde run gewoon door tot de volle cap; er gaat dus geen week verloren. Bij HEMA kijkt de kanarie bewust naar de JSON-route en niet naar de kaartoogst: die leest bij een niet-renderend raster alleen de promoblokken (koffie, koekjes) en zou de bron ten onrechte groen praten.

### Zeeman: laadt wel, toont geen prijzen (stand 09-08)
Zeeman is een ander geval dan Wibra/HEMA — er is géén blokkade. De pagina's laden
volledig, ook zonder browser, maar bevatten geen prijzen. Drie gemeten voorbeelden:

| Pagina | Links | €-tekens in de tekst |
|---|---:|---:|
| `/nl-nl/dames/ondergoed` | 120 | **0** |
| `/nl-nl/heren/sokken` | 120 | **0** |
| `/nl-nl/collecties/sokken` | 116 | **0** |

De paginatitel van de tweede luidt letterlijk *"Herensokken, enkelsokken, en meer.
Vanaf €1,99 | Zeeman"* — de prijzen bestáán dus, maar komen pas in beeld na een
stap die de scraper niet zet. Meest waarschijnlijke oorzaak: een cookie- of
regiokeuze die het productraster vrijgeeft en die de consent-routine niet herkent.
Via de productpagina's lukt het evenmin: die dragen in de HTML alleen een
aanraderblok, waardoor 60 verschillende pagina's steeds dezelfde zes artikelen
opleverden.

**Besluit: Zeeman blijft rood tot dit gericht is uitgezocht.** Zes aanrader-
artikelen als "het Zeeman-assortiment" presenteren is schadelijker dan een lege
regel — juist omdat Zeeman de maatstaf van het waardesegment is. Dit is de
belangrijkste openstaande technische taak; begin bij de consent-/regiostap.

## 9. Beperkingen & risico's — eerlijk benoemd

| Risico | Impact | Beheersing |
|---|---|---|
| Bot-bescherming (m.n. Action, Wibra, HEMA) | Bron valt uit | Waterval-strategie; bron-gezondheid in rapport; render-strategie (headless browser) actief voor de geblokkeerde bronnen — zware challenge-muren kunnen ook die tegenhouden, dan folder-/winkelflankering |
| Site-redesign bij concurrent | Bron valt uit of telt raar | Autodetectie + harde afwijkingsdrempel: bij <50% van vorige week wordt de week **niet** verwerkt (geen vervuilde trends) en kleurt de bron rood |
| Mapping-ruis | Verkeerde groepstoedeling | "Onbekend"-bak zichtbaar; maandelijks 15 min onderhoud; mappingregels in één YAML-bestand |
| Prijs ontbreekt op de productpagina (terStal: 43% dekking) | Mediaan en prijsindex berusten op een deel van het assortiment | Rapport noemt voorbeeld-URL's van artikelen zonder prijs, zodat het ontbrekende veld op te zoeken en toe te voegen is; liever een smallere basis dan een prijs van een ánder artikel |
| Online ≠ winkel | Verkeerde absolute conclusies | Alleen trends communiceren; folder- en winkelflankering |
| Stille dood (niemand kijkt) | Tool wordt speeltje | Maandagritueel met eigenaar en actieteller (§1, §6.9) |
| Gratis tiers wijzigen | Kosten ontstaan | Alles is standaard Postgres/statische site — verhuisbaar in een dag |

## 10. Roadmap

| Fase | Wanneer | Wat |
|---|---|---|
| **0. Setup** | Week 1 | Supabase + Netlify aansluiten (zie README), Validatie-workflow draaien, bronnen kalibreren |
| **1. Ritueel** | Week 2–5 | Wekelijkse run + maandagoverleg; mapping aanscherpen; drempels afstellen |
| **2. Verdieping** | Week 6–12 | KVI-koppeltabel (§6.3), fase-2-bronnen aanzetten waar gevalideerd, trendwoorden op instroom |
| **3. Volwassen** | Kwartaal 2+ | Jaar-op-jaar-seizoensklok, folder-archief, evt. maatdiepte op vechtartikelen |

---

*Technische installatie en beheer: zie [README.md](README.md). Bronconfiguratie: `scraper/retailers.yml`. Categoriemapping: `scraper/mapping.yml`.*
