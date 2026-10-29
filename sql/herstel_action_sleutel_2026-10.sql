-- Herstel Action-artikelsleutel (eenmalig, 19-10-2026)
--
-- Probleem: t/m W40 gebruikte de scraper voor Action een sleutel uit de
-- ingebedde JSON die elke week wisselde (716 verschillende sleutels voor ±220
-- artikelen in 9 weken). Elke week leek daardoor ±40% "nieuw" en ±40%
-- "verdwenen", en prijsbewegingen gingen verloren. Sinds W41 is de sleutel het
-- productnummer uit de URL (/nl-nl/p/<nummer>/); vanaf nu legt de bronconfig
-- dat vast (key_from_url in retailers.yml).
--
-- Dit script zet de historie op dezelfde sleutel en bouwt de Action-events,
-- de Action-artikelstand en new/gone in weekly_stats opnieuw op uit de
-- wekelijkse artikelfoto's (weekly_articles). Prijsniveaus, mediaan, sale-
-- druk en alle andere bronnen blijven onaangeroerd.
--
-- Prijsvergelijkingen met W36 (31-08) en eerder worden overgeslagen: in W36
-- sloeg de scraper bij Action de stukprijs op i.p.v. de verpakkingsprijs
-- (bv. 'Pairz sokken' €0,83 i.p.v. €2,49), en t/m W35 zag hij alleen de
-- eerste categorie. Vergelijken zou 120 schijnverhogingen in W37 geven.
--
-- Veilig: alles in één transactie; vooraf een kopie in bak_action_2026_10_*.
-- Terugdraaien: zie onderaan.

begin;

-- 0. Back-up
create table if not exists bak_action_2026_10_products as
  select * from products where retailer_id = 'action';
create table if not exists bak_action_2026_10_price_events as
  select * from price_events where retailer_id = 'action';
create table if not exists bak_action_2026_10_weekly_articles as
  select * from weekly_articles where retailer_id = 'action';
create table if not exists bak_action_2026_10_weekly_stats as
  select * from weekly_stats where retailer_id = 'action';

-- 1. Artikelfoto's op de URL-sleutel
update weekly_articles
set product_key = substring(url from '/p/(\d+)/')
where retailer_id = 'action'
  and substring(url from '/p/(\d+)/') is not null
  and product_key <> substring(url from '/p/(\d+)/');

-- 2. Events opnieuw opbouwen uit de artikelfoto's
create temp table _wk on commit drop as
  select week, row_number() over (order by week) as i
  from (select distinct week from weekly_articles where retailer_id = 'action') w;

create temp table _a on commit drop as
  select a.product_key, a.week, k.i, a.price, a.was_price,
         (a.was_price is not null and a.price is not null and a.was_price > a.price) as promo
  from weekly_articles a join _wk k using (week)
  where a.retailer_id = 'action';

create temp table _ev on commit drop as
with seq as (
  select a.*,
         lag(a.i)        over w as prev_i,
         lag(a.price)    over w as prev_price,
         lag(a.promo)    over w as prev_promo,
         lag(a.week)     over w as prev_week,
         lead(a.i)       over w as next_i
  from _a a
  window w as (partition by a.product_key order by a.i)
)
select product_key, week, 'new'::text as event, price, was_price, null::numeric as prev_price
  from seq where prev_i is null
union all
select product_key, week, 'back', price, was_price, null
  from seq where prev_i is not null and prev_i < i - 1
union all
select product_key, week, 'price_up', price, was_price, prev_price
  from seq where prev_i = i - 1 and prev_week > date '2026-08-31' and price > prev_price
union all
select product_key, week, 'price_down', price, was_price, prev_price
  from seq where prev_i = i - 1 and prev_week > date '2026-08-31' and price < prev_price
union all
select product_key, week, 'promo_start', price, was_price, prev_price
  from seq where prev_i = i - 1 and prev_week > date '2026-08-31' and promo and not prev_promo
union all
select product_key, week, 'promo_end', price, was_price, prev_price
  from seq where prev_i = i - 1 and prev_week > date '2026-08-31' and not promo and prev_promo
union all
select s.product_key, k.week, 'gone', null, null, s.price
  from seq s join _wk k on k.i = s.i + 1
  where s.next_i is null or s.next_i > s.i + 1;

delete from price_events where retailer_id = 'action';

-- 3. Artikelstand opnieuw opbouwen (laatste waarneming per artikel)
create temp table _p on commit drop as
select distinct on (a.product_key)
  a.product_key, a.url, a.title, a.category_raw, a.audience, a.product_type,
  a.color, a.sizes, a.pack_size, a.promo_text, a.price, a.was_price, a.week as last_seen,
  min(a.week) over (partition by a.product_key) as first_seen
from weekly_articles a
where a.retailer_id = 'action'
order by a.product_key, a.week desc;

delete from products where retailer_id = 'action';

insert into products (retailer_id, product_key, url, title, brand, category_raw,
  audience, product_type, first_seen, last_seen, status, current_price,
  current_was_price, color, sizes, pack_size, promo_text)
select 'action', p.product_key, p.url, p.title,
       (select b.brand from bak_action_2026_10_products b
         where b.url = p.url and b.brand is not null limit 1),
       p.category_raw, p.audience, p.product_type, p.first_seen, p.last_seen,
       case when p.last_seen = (select max(week) from _wk) then 'active' else 'gone' end,
       p.price, p.was_price, p.color, p.sizes, coalesce(p.pack_size, 1), p.promo_text
from _p p;

insert into price_events (retailer_id, product_key, week, event, price, was_price, prev_price)
select 'action', product_key, week, event, price, was_price, prev_price from _ev;

-- 4. new/gone in de weekaggregaten bijwerken (prijsniveaus blijven staan)
create temp table _cnt on commit drop as
select e.week, coalesce(a.audience, p.audience) as audience,
       coalesce(a.product_type, p.product_type) as product_type,
       count(*) filter (where e.event = 'new')::int  as new_count,
       count(*) filter (where e.event = 'gone')::int as gone_count
from _ev e
left join weekly_articles a on a.retailer_id = 'action' and a.week = e.week
                           and a.product_key = e.product_key
left join products p on p.retailer_id = 'action' and p.product_key = e.product_key
where e.event in ('new', 'gone')
group by 1, 2, 3;

update weekly_stats s set new_count = 0, gone_count = 0 where s.retailer_id = 'action';

update weekly_stats s
set new_count = c.new_count, gone_count = c.gone_count
from _cnt c
where s.retailer_id = 'action' and s.week = c.week
  and s.audience = c.audience and s.product_type = c.product_type;

insert into weekly_stats (retailer_id, week, audience, product_type,
  active_count, new_count, gone_count)
select 'action', c.week, c.audience, c.product_type, 0, c.new_count, c.gone_count
from _cnt c
where not exists (select 1 from weekly_stats s
                  where s.retailer_id = 'action' and s.week = c.week
                    and s.audience = c.audience and s.product_type = c.product_type);

commit;

-- Terugdraaien (alleen bij problemen):
-- begin;
-- delete from price_events   where retailer_id = 'action';
-- delete from products       where retailer_id = 'action';
-- delete from weekly_articles where retailer_id = 'action';
-- delete from weekly_stats   where retailer_id = 'action';
-- insert into products        select * from bak_action_2026_10_products;
-- insert into weekly_articles select * from bak_action_2026_10_weekly_articles;
-- insert into weekly_stats    select * from bak_action_2026_10_weekly_stats;
-- insert into price_events    select * from bak_action_2026_10_price_events;
-- commit;
