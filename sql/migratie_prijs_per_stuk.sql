-- =====================================================================
-- MIGRATIE: prijs per stuk (multipacks eerlijk vergelijken) — PLAN.md §11.1
--
-- Waarom: in het waardesegment vecht iedereen met multipacks. "Kinderboxers
-- 3 stuks €12,99" naast een losse boxer leggen is appels met peren, en juist
-- op sokken en boxers zit het grootste deel van het prijsimago. De scraper
-- leest voortaan de pack-grootte uit de artikelnaam (scraper/normalize.py,
-- functie pack_size) en de weekverwerking rekent daar een tweede prijsindex
-- mee uit: mediaan en instapniveau per stuk.
--
-- Draaien:
--   Stap 1: dit bestand één keer plakken in de Supabase SQL Editor.
--   Stap 2: daarna sql/schema.sql opnieuw uitvoeren — dat bestand is
--           idempotent en zet de bijgewerkte process_staging()-functie en de
--           exportview v_artikelen_week klaar.
-- Nieuwe installaties hebben deze migratie niet nodig: schema.sql bevat alles.
--
-- Volgorde is niet kritiek: draait de wekelijkse scrape vóór deze migratie,
-- dan merkt hij dat de kolom pack_size ontbreekt, laat hem weg en noteert dat
-- in de run-notitie. De week gaat dus niet verloren; alleen de per-stuk-cijfers
-- blijven leeg tot de migratie er is.
--
-- Historie: bestaande rijen krijgen pack_size 1. De actuele stand (products)
-- en daarmee weekly_stats zijn vanaf de eerstvolgende verwerkte week correct,
-- omdat elke week alle actieve artikelen opnieuw worden weggeschreven. De
-- artikelfoto's van eerdere weken (weekly_articles) blijven op 1 staan — die
-- worden niet met terugwerkende kracht herbeoordeeld. Lees de per-stuk-index
-- dus pas vanaf de eerste week ná deze migratie.
-- =====================================================================

alter table products         add column if not exists pack_size int not null default 1;
alter table staging_products add column if not exists pack_size int not null default 1;
alter table weekly_articles  add column if not exists pack_size int default 1;

alter table weekly_stats add column if not exists unit_price_median numeric(10,2);
alter table weekly_stats add column if not exists unit_price_p25    numeric(10,2);
alter table weekly_stats add column if not exists multipack_share   numeric(6,4);
