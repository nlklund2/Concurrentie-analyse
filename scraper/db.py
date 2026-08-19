"""Supabase-koppeling via de PostgREST REST-API (bewust zonder zware SDK)."""
from __future__ import annotations

import time
from datetime import date

import requests

from .config import env


class DbError(RuntimeError):
    pass


class Db:
    PAGE = 1000       # Supabase geeft max 1000 rijen per request
    POGINGEN = 3      # herkansingen bij netwerkhapering of 5xx/429
    WACHT = (2, 6)    # seconden tussen de pogingen

    def __init__(self):
        url = env("SUPABASE_URL", required=True).rstrip("/")
        key = env("SUPABASE_SERVICE_ROLE_KEY", required=True)
        self.rest = f"{url}/rest/v1"
        self.session = requests.Session()
        self.session.headers.update({
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        })

    def _check(self, resp: requests.Response) -> requests.Response:
        if resp.status_code >= 400:
            raise DbError(f"Supabase {resp.status_code}: {resp.text[:500]}")
        return resp

    def _req(self, method: str, path: str, *, pogingen: int = POGINGEN,
             **kw) -> requests.Response:
        """Eén REST-aanroep, met herkansing bij een hapering.

        Een netwerkstoring van een paar seconden mag een bron geen hele week
        kosten: in week 32 verloor C&A 28 al gescrapete artikelen aan één
        read-timeout van 60 s. Alleen 5xx/429 en verbindingsfouten worden
        herkanst — een 4xx is een echte fout en komt meteen naar boven.
        """
        laatste = ""
        for poging in range(pogingen):
            try:
                resp = self.session.request(method, f"{self.rest}/{path}", **kw)
            except (requests.Timeout, requests.ConnectionError) as e:
                laatste = f"{type(e).__name__}: {str(e)[:200]}"
            else:
                if resp.status_code < 500 and resp.status_code != 429:
                    return self._check(resp)
                laatste = f"Supabase {resp.status_code}: {resp.text[:300]}"
            if poging < pogingen - 1:
                time.sleep(self.WACHT[min(poging, len(self.WACHT) - 1)])
        raise DbError(f"{laatste} (na {pogingen} pogingen)")

    def get_all(self, path: str, params: dict) -> list[dict]:
        """Alle rijen ophalen, gepagineerd voorbij de 1000-rijenlimiet."""
        rows: list[dict] = []
        offset = 0
        while True:
            headers = {"Range-Unit": "items", "Range": f"{offset}-{offset + self.PAGE - 1}"}
            resp = self._req("GET", path, params=params, headers=headers, timeout=60)
            batch = resp.json()
            rows.extend(batch)
            if len(batch) < self.PAGE:
                return rows
            offset += self.PAGE

    # -- schrijven (wekelijkse job) ------------------------------------
    def ensure_retailers(self, cfgs) -> None:
        payload = [{"id": c.id, "name": c.name, "website": c.base,
                    "segment": c.segment, "enabled": c.enabled} for c in cfgs]
        self._req("POST", "retailers", json=payload, timeout=60,
                  params={"on_conflict": "id"},
                  headers={"Prefer": "resolution=merge-duplicates,return=minimal"})

    # Kolommen die pas na een migratie bestaan. Draait de weekrun vóór de
    # migratie, dan mag dat geen hele week kosten: de kolom wordt dan
    # weggelaten en de run gaat door (alleen de nieuwe cijfers blijven leeg).
    NA_MIGRATIE = ("pack_size",)

    def _zonder_nieuwe_kolommen(self, rows: list[dict], melding: str) -> list[dict] | None:
        """Rijen zonder de nog niet gemigreerde kolommen, of None als dat niet speelt."""
        if not rows:
            return None
        ontbreekt = [k for k in self.NA_MIGRATIE
                     if k in rows[0] and (f"'{k}'" in melding or f'"{k}"' in melding)]
        if not ontbreekt:
            return None
        print(f"  ! staging mist kolom(men) {', '.join(ontbreekt)} — "
              "draai sql/migratie_prijs_per_stuk.sql; deze week zonder die velden")
        return [{k: v for k, v in r.items() if k not in ontbreekt} for r in rows]

    def replace_staging(self, retailer_id: str, rows: list[dict]) -> None:
        """Leegmaken en vullen als één geheel.

        De herkansing begint weer bij de delete: een half geslaagde insert zou
        anders dubbele sleutels in staging achterlaten, en daar loopt de
        upsert in process_staging op vast.
        """
        poging = 0
        while True:
            try:
                self._req("DELETE", "staging_products", pogingen=1, timeout=60,
                          params={"retailer_id": f"eq.{retailer_id}"})
                for i in range(0, len(rows), 500):
                    self._req("POST", "staging_products", pogingen=1,
                              json=rows[i:i + 500], timeout=120,
                              headers={"Prefer": "return=minimal"})
                return
            except DbError as e:
                # Ontbrekende migratiekolom: opnieuw zónder die velden, en dat
                # kost geen herkansing — het is geen hapering maar een schema
                # dat nog moet worden bijgewerkt.
                uitgekleed = self._zonder_nieuwe_kolommen(rows, str(e))
                if uitgekleed is not None:
                    rows = uitgekleed
                    continue
                poging += 1
                if poging >= self.POGINGEN:
                    raise
                time.sleep(self.WACHT[min(poging - 1, len(self.WACHT) - 1)])

    def process_week(self, retailer_id: str, week: date) -> dict:
        # process_staging is idempotent per (bron, week) — herkansen is veilig
        resp = self._req("POST", "rpc/process_staging", timeout=300,
                         json={"p_retailer": retailer_id, "p_week": week.isoformat()})
        return resp.json()

    def log_run(self, retailer_id: str, week: date, strategy: str,
                products_found: int, status: str, note: str = "") -> None:
        self._req("POST", "scrape_runs", timeout=60,
                  json={"retailer_id": retailer_id, "week": week.isoformat(),
                        "strategy": strategy, "products_found": products_found,
                        "status": status, "note": note[:800]},
                  headers={"Prefer": "return=minimal"})

    # -- lezen (rapport & drempelbewaking) -----------------------------
    def last_ok_count(self, retailer_id: str) -> int:
        """De artikelstand van de laatste goedgekeurde run — de eerlijke
        vergelijkingsbasis voor de <50%-poort. active_count bleek vervuilbaar:
        een herdraai binnen dezelfde week laat oude rijen actief staan, en
        Action bleef daardoor elke week op '24 < 50% van 51' steken terwijl
        24 al twee runs lang de echte, goedgekeurde stand was."""
        rows = self._req("GET", "scrape_runs?select=products_found"
                                f"&retailer_id=eq.{retailer_id}&status=eq.ok"
                                "&order=run_at.desc&limit=1", timeout=30).json()
        return int(rows[0]["products_found"]) if rows else 0

    def active_count(self, retailer_id: str) -> int:
        resp = self._req(
            "GET", "products", timeout=60,
            params={"retailer_id": f"eq.{retailer_id}", "status": "eq.active",
                    "select": "product_key", "limit": "1"},
            headers={"Prefer": "count=exact", "Range": "0-0", "Range-Unit": "items"})
        content_range = resp.headers.get("Content-Range", "/0")
        total = content_range.rsplit("/", 1)[-1]
        return int(total) if total.isdigit() else 0

    def product_keys(self, retailer_id: str) -> set[str]:
        """Bekende artikelsleutels van een bron (voor 'nieuwe eerst' bij verrijking)."""
        rows = self.get_all("products", {"retailer_id": f"eq.{retailer_id}",
                                         "select": "product_key"})
        return {r["product_key"] for r in rows}

    def weeks(self) -> list[date]:
        rows = self.get_all("v_weeks", {"select": "week", "order": "week.desc"})
        return [date.fromisoformat(r["week"]) for r in rows]

    def retailers(self) -> dict[str, dict]:
        rows = self.get_all("retailers", {"select": "*"})
        return {r["id"]: r for r in rows}

    def weekly_stats(self, week: date) -> list[dict]:
        return self.get_all("weekly_stats", {"week": f"eq.{week.isoformat()}", "select": "*"})

    def week_totals(self, week: date) -> dict[str, dict]:
        rows = self.get_all("v_retailer_week_totals",
                            {"week": f"eq.{week.isoformat()}", "select": "*"})
        return {r["retailer_id"]: r for r in rows}

    def runs(self, week: date) -> list[dict]:
        return self.get_all("scrape_runs", {"week": f"eq.{week.isoformat()}",
                                            "select": "*", "order": "run_at.desc"})

    def events(self, week: date, kinds: list[str]) -> list[dict]:
        return self.get_all("price_events", {
            "week": f"eq.{week.isoformat()}",
            "event": f"in.({','.join(kinds)})",
            "select": "retailer_id,product_key,event,price,was_price,prev_price"})

    def products_by_keys(self, retailer_id: str, keys: list[str]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for i in range(0, len(keys), 100):
            chunk = ",".join(f'"{k}"' for k in keys[i:i + 100])
            rows = self.get_all("products", {
                "retailer_id": f"eq.{retailer_id}",
                "product_key": f"in.({chunk})",
                "select": "product_key,title,url,audience,product_type"})
            out.update({r["product_key"]: r for r in rows})
        return out
