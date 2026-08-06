-- =============================================================
-- DEMO-DATA WISSEN — draai dit één keer vóór de echte eerste
-- meting, zodat de trends schoon beginnen. Maakt alle datatabellen
-- leeg; retailers (stamdata) blijft staan en wordt door de
-- wekelijkse job actueel gehouden.
-- =============================================================

begin;
delete from price_events;
delete from weekly_stats;
delete from scrape_runs;
delete from staging_products;
delete from products;
commit;
