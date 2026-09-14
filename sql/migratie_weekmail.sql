-- Migratie: weekmail bewaren (docs/weekmail-voorstel.md §2 en §6, 14 september 2026)
-- Draai dit één keer op een bestaande database (SQL Editor of apply_migration).
-- Nieuwe installaties hebben genoeg aan schema.sql.
--
-- Eén rij per week: onderwerp, HTML, platte tekst en de top-3 signalen. Het
-- dashboard toont de laatst verstuurde mail in het paneel "Weekmail"; de
-- weekmail van de week erna leest de top-3 terug voor de terugblik.
-- Alleen ingelogde dashboardgebruikers lezen; alleen de service-rol schrijft.

create table if not exists weekmails (
  week       date primary key,          -- maandag van de weekmailweek
  subject    text not null,
  html       text not null,
  text       text not null,
  top3       jsonb,                      -- de drie signalen (voor de terugblik)
  sent_to    int  not null default 0,    -- aantal ontvangers (0 = niet verstuurd)
  status     text,                       -- uitkomst van het versturen
  created_at timestamptz not null default now()
);

alter table weekmails enable row level security;
drop policy if exists lezen_ingelogd on weekmails;
create policy lezen_ingelogd on weekmails for select to authenticated using (true);
