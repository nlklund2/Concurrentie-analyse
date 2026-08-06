-- =============================================================
-- MIGRATIE: wekelijkse artikelfoto (artnr t/m URL) + kleur/maten
-- Voor bestaande installaties die het schema al draaien.
--
-- Stap 1: voer dit bestand uit (voegt kolommen toe).
-- Stap 2: voer daarna sql/schema.sql opnieuw uit — dat bestand is
--         idempotent en maakt de nieuwe tabel weekly_articles, de
--         view v_artikelen_week, het leesbeleid en de bijgewerkte
--         process_staging()-functie aan.
-- Nieuwe installaties hebben deze migratie niet nodig: schema.sql
-- bevat alles al.
-- =============================================================

alter table products         add column if not exists color text;
alter table products         add column if not exists sizes text;
alter table staging_products add column if not exists color text;
alter table staging_products add column if not exists sizes text;
