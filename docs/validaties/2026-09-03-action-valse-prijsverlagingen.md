# Schoning: 20 valse price_down-events Action, week 2026-08-31

*Datum ingreep: 3 september 2026 · uitgevoerd door Claude in overleg met de
sessie-opdracht "onderzoek en corrigeer" (Action-ondertelling).*

## Wat er gebeurde

Op 3-09 is Action tweemaal binnen een uur herverwerkt voor dezelfde week
(2026-08-31):

1. **Run 33749013351** (na PR #29, meetherstel sessie-wering): eerste
   volledige meting — maar met de maat-als-prijs-fout: twintig
   maillots-artikelen kregen hun kledingmaat als prijs (€38/42/46/50 en
   kinderlengte €170), doordat de kale-integer-variant van de
   getal-vóór-€-prijsmatch de maat vóór het €-teken las ("Maten 40 - 42
   € 0,84/st") én het €-teken verbruikte.
2. **Run 33751998957** (na PR #30, decimalen-eis): zelfde week opnieuw,
   nu met echte prijzen (€1,89–4,95).

`process_staging` logde het verschil tussen die twee runs als twintig
`price_down`-events — bijvoorbeeld "thermopanty van €170,00 naar €2,49"
(−98%). Die "vorige prijzen" hebben **nooit op action.com gestaan** en de
twee metingen zaten binnen één uur op dezelfde weekfoto: dit zijn
herdraai-artefacten, geen marktmutaties. Ze zouden weekrapport §grootste
prijsverlagingen en de artikel-tijdlijnen in het dashboard vervuilen.

## Ingreep

```sql
delete from price_events
where retailer_id = 'action' and week = '2026-08-31'
  and event = 'price_down' and prev_price >= 38;
```

Verder niets: `weekly_articles` en `weekly_stats` waren door run
33751998957 al correct; new/back/gone-events zijn echte week-op-week-
mutaties en blijven staan.

## Omkeren

De verwijderde rijen exact (retailer_id='action', week='2026-08-31',
event='price_down', was_price null):

| product_key | price | prev_price |
|---|---:|---:|
| e34944902a713961 | 2.49 | 170.00 |
| 2860233845f130fe | 2.89 | 50.00 |
| 410bf4f9a7ec746c | 4.79 | 50.00 |
| 5044532a181abd1c | 3.49 | 50.00 |
| 5df88b6e729c79e8 | 2.99 | 50.00 |
| 5e18ee2215ac6fb9 | 1.89 | 50.00 |
| b4ff3cc3dc674050 | 2.99 | 50.00 |
| c17f114d801edeb0 | 4.49 | 50.00 |
| c308804d08b17671 | 1.89 | 50.00 |
| c7efffcce159096e | 4.95 | 50.00 |
| f14dbc7a025863a0 | 3.49 | 50.00 |
| 1bfa28acfbfbaf42 | 1.89 | 46.00 |
| a84cc2b097d93b62 | 2.89 | 46.00 |
| df4d21714e8d3aee | 1.89 | 46.00 |
| 5469f01126c82767 | 2.89 | 42.00 |
| c1151c959aa29c93 | 1.89 | 42.00 |
| dacba9ddb09888bc | 1.89 | 42.00 |
| 235c04de662721a5 | 1.89 | 38.00 |
| 65f67e44f17087ee | 1.89 | 38.00 |
| e5fd1ff6da1ccb4b | 2.89 | 38.00 |

Terugzetten kan met een insert van precies deze rijen; de prev_price is
dan wél weer de aantoonbaar nooit-getoonde maatwaarde.

## Verband

- PR #29 — meetherstel sessie-wering (24 → 222 artikelen).
- PR #30 — maat vóór €-teken telt niet meer als prijs.
- Weekrapport 2026-W36 is na deze schoning opnieuw gegenereerd.
