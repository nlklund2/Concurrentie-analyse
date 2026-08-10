-- =====================================================================
-- Migratie: weekwissel-opruiming op de snapshot toetsen (10-08-2026)
--
-- Wat dit oplost: een herdraai binnen dezelfde week liet de rijen van de
-- eerdere poging actief staan ('gone' keek naar last_seen < week, en die was
-- gelijk). Zo bleven bij Action 27 banner-rijen naast de 24 echte artikelen
-- staan. Vanaf nu geldt: actief maar niet in de aangeleverde weeksnapshot
-- = verdwenen — ongeacht wanneer het artikel voor het laatst gezien is.
--
-- Draaien: één keer plakken in de Supabase SQL Editor. Idempotent.
-- De achtergebleven Action-rijen ruimen zichzelf op bij de eerstvolgende
-- goedgekeurde weekverwerking; daar is geen aparte opruimquery voor nodig.
-- =====================================================================

create or replace function process_staging(p_retailer text, p_week date)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_total int; v_new int; v_back int; v_up int; v_down int;
  v_promo_start int; v_promo_end int; v_gone int;
begin
  create temp table _snap on commit drop as
    select distinct on (product_key) *
    from staging_products
    where retailer_id = p_retailer;

  select count(*) into v_total from _snap;
  if v_total = 0 then
    raise exception 'staging is leeg voor % — verwerking afgebroken', p_retailer;
  end if;

  -- Nieuw: nooit eerder gezien.
  insert into price_events (retailer_id, product_key, week, event, price, was_price)
  select s.retailer_id, s.product_key, p_week, 'new', s.price, s.was_price
  from _snap s
  left join products p on p.retailer_id = s.retailer_id and p.product_key = s.product_key
  where p.product_key is null;
  get diagnostics v_new = row_count;

  -- Terug: was verdwenen, duikt weer op.
  insert into price_events (retailer_id, product_key, week, event, price, was_price)
  select s.retailer_id, s.product_key, p_week, 'back', s.price, s.was_price
  from _snap s
  join products p on p.retailer_id = s.retailer_id and p.product_key = s.product_key
  where p.status = 'gone';
  get diagnostics v_back = row_count;

  -- Prijsverhoging / -verlaging op bestaande actieve artikelen.
  insert into price_events (retailer_id, product_key, week, event, price, was_price, prev_price)
  select s.retailer_id, s.product_key, p_week, 'price_up', s.price, s.was_price, p.current_price
  from _snap s
  join products p on p.retailer_id = s.retailer_id and p.product_key = s.product_key
  where p.status = 'active' and s.price is not null and p.current_price is not null
    and s.price > p.current_price;
  get diagnostics v_up = row_count;

  insert into price_events (retailer_id, product_key, week, event, price, was_price, prev_price)
  select s.retailer_id, s.product_key, p_week, 'price_down', s.price, s.was_price, p.current_price
  from _snap s
  join products p on p.retailer_id = s.retailer_id and p.product_key = s.product_key
  where p.status = 'active' and s.price is not null and p.current_price is not null
    and s.price < p.current_price;
  get diagnostics v_down = row_count;

  -- Promotie gestart / beëindigd (doorstreepte prijs verschijnt/verdwijnt).
  insert into price_events (retailer_id, product_key, week, event, price, was_price, prev_price)
  select s.retailer_id, s.product_key, p_week, 'promo_start', s.price, s.was_price, p.current_price
  from _snap s
  join products p on p.retailer_id = s.retailer_id and p.product_key = s.product_key
  where p.status = 'active'
    and (s.was_price is not null and s.price is not null and s.was_price > s.price)
    and not (p.current_was_price is not null and p.current_price is not null
             and p.current_was_price > p.current_price);
  get diagnostics v_promo_start = row_count;

  insert into price_events (retailer_id, product_key, week, event, price, was_price, prev_price)
  select s.retailer_id, s.product_key, p_week, 'promo_end', s.price, s.was_price, p.current_price
  from _snap s
  join products p on p.retailer_id = s.retailer_id and p.product_key = s.product_key
  where p.status = 'active'
    and not (s.was_price is not null and s.price is not null and s.was_price > s.price)
    and (p.current_was_price is not null and p.current_price is not null
         and p.current_was_price > p.current_price);
  get diagnostics v_promo_end = row_count;

  -- Actuele stand bijwerken.
  insert into products (retailer_id, product_key, url, title, brand, category_raw,
                        audience, product_type, color, sizes, first_seen, last_seen,
                        status, current_price, current_was_price)
  select s.retailer_id, s.product_key, s.url, s.title, s.brand, s.category_raw,
         s.audience, s.product_type, s.color, s.sizes, p_week, p_week, 'active',
         s.price, s.was_price
  from _snap s
  on conflict (retailer_id, product_key) do update set
    url = excluded.url,
    title = excluded.title,
    brand = excluded.brand,
    category_raw = excluded.category_raw,
    audience = excluded.audience,
    product_type = excluded.product_type,
    last_seen = excluded.last_seen,
    status = 'active',
    color = excluded.color,
    sizes = excluded.sizes,
    current_price = excluded.current_price,
    current_was_price = excluded.current_was_price;

  -- Wekelijkse artikelfoto (artnr t/m URL) — idempotent per (bron, week).
  delete from weekly_articles where retailer_id = p_retailer and week = p_week;
  insert into weekly_articles (retailer_id, week, product_key, title, audience,
    product_type, category_raw, color, sizes, price, was_price, url)
  select s.retailer_id, p_week, s.product_key, s.title, s.audience,
         s.product_type, s.category_raw, s.color, s.sizes, s.price, s.was_price, s.url
  from _snap s;

  -- Verdwenen: actief maar niet in deze snapshot. Op de snapshot toetsen, niet
  -- op last_seen < p_week: een herdraai binnen dezelfde week liet anders de
  -- rijen van de eerdere poging actief staan (Action, week 32: 27 banners
  -- bleven naast de 24 echte artikelen staan en vervuilden elke poort erna).
  insert into price_events (retailer_id, product_key, week, event, prev_price)
  select p.retailer_id, p.product_key, p_week, 'gone', p.current_price
  from products p
  where p.retailer_id = p_retailer and p.status = 'active'
    and not exists (select 1 from _snap s where s.product_key = p.product_key);
  get diagnostics v_gone = row_count;

  update products p set status = 'gone'
  where p.retailer_id = p_retailer and p.status = 'active'
    and not exists (select 1 from _snap s where s.product_key = p.product_key);

  -- Weekaggregaten (huidige actieve stand + uitstroom van deze week).
  delete from weekly_stats where retailer_id = p_retailer and week = p_week;

  insert into weekly_stats (retailer_id, week, audience, product_type,
    active_count, new_count, gone_count,
    price_min, price_p25, price_median, price_p75, price_p90, price_avg,
    sale_share, avg_discount_pct)
  with snap as (
    select audience, product_type, current_price as price, current_was_price as was_price, first_seen
    from products
    where retailer_id = p_retailer and status = 'active'
  ), snap_g as (
    select audience, product_type,
      count(*)::int as active_count,
      (count(*) filter (where first_seen = p_week))::int as new_count,
      min(price) as price_min,
      percentile_cont(0.25) within group (order by price) as price_p25,
      percentile_cont(0.50) within group (order by price) as price_median,
      percentile_cont(0.75) within group (order by price) as price_p75,
      percentile_cont(0.90) within group (order by price) as price_p90,
      round(avg(price), 2) as price_avg,
      round(avg(case when was_price is not null and price is not null and was_price > price
                     then 1 else 0 end)::numeric, 4) as sale_share,
      round(avg(case when was_price is not null and price is not null and was_price > price
                     then (was_price - price) / was_price * 100 end)::numeric, 1) as avg_discount_pct
    from snap
    group by 1, 2
  ), gone_g as (
    select p.audience, p.product_type, count(*)::int as gone_count
    from price_events e
    join products p on p.retailer_id = e.retailer_id and p.product_key = e.product_key
    where e.retailer_id = p_retailer and e.week = p_week and e.event = 'gone'
    group by 1, 2
  )
  select p_retailer, p_week,
         coalesce(sg.audience, gg.audience),
         coalesce(sg.product_type, gg.product_type),
         coalesce(sg.active_count, 0),
         coalesce(sg.new_count, 0),
         coalesce(gg.gone_count, 0),
         sg.price_min, sg.price_p25, sg.price_median, sg.price_p75, sg.price_p90,
         sg.price_avg, sg.sale_share, sg.avg_discount_pct
  from snap_g sg
  full join gone_g gg using (audience, product_type);

  delete from staging_products where retailer_id = p_retailer;

  return jsonb_build_object(
    'products', v_total, 'new', v_new, 'back', v_back,
    'price_up', v_up, 'price_down', v_down,
    'promo_start', v_promo_start, 'promo_end', v_promo_end, 'gone', v_gone);
end;
$$;

revoke execute on function process_staging(text, date) from public, anon, authenticated;
