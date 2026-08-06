"""Supabase-koppeling via de PostgREST REST-API (bewust zonder zware SDK)."""
from __future__ import annotations

from datetime import date

import requests

from .config import env


class DbError(RuntimeError):
    pass


class Db:
    PAGE = 1000  # Supabase geeft max 1000 rijen per request

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

    def get_all(self, path: str, params: dict) -> list[dict]:
        """Alle rijen ophalen, gepagineerd voorbij de 1000-rijenlimiet."""
        rows: list[dict] = []
        offset = 0
        while True:
            headers = {"Range-Unit": "items", "Range": f"{offset}-{offset + self.PAGE - 1}"}
            resp = self._check(self.session.get(f"{self.rest}/{path}", params=params,
                                                headers=headers, timeout=60))
            batch = resp.json()
            rows.extend(batch)
            if len(batch) < self.PAGE:
                return rows
            offset += self.PAGE

    # -- schrijven (wekelijkse job) ------------------------------------
    def ensure_retailers(self, cfgs) -> None:
        payload = [{"id": c.id, "name": c.name, "website": c.base,
                    "segment": c.segment, "enabled": c.enabled} for c in cfgs]
        self._check(self.session.post(
            f"{self.rest}/retailers", json=payload, timeout=60,
            params={"on_conflict": "id"},
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"}))

    def replace_staging(self, retailer_id: str, rows: list[dict]) -> None:
        self._check(self.session.delete(
            f"{self.rest}/staging_products",
            params={"retailer_id": f"eq.{retailer_id}"}, timeout=60))
        for i in range(0, len(rows), 500):
            self._check(self.session.post(
                f"{self.rest}/staging_products", json=rows[i:i + 500], timeout=120,
                headers={"Prefer": "return=minimal"}))

    def process_week(self, retailer_id: str, week: date) -> dict:
        resp = self._check(self.session.post(
            f"{self.rest}/rpc/process_staging", timeout=300,
            json={"p_retailer": retailer_id, "p_week": week.isoformat()}))
        return resp.json()

    def log_run(self, retailer_id: str, week: date, strategy: str,
                products_found: int, status: str, note: str = "") -> None:
        self._check(self.session.post(
            f"{self.rest}/scrape_runs", timeout=60,
            json={"retailer_id": retailer_id, "week": week.isoformat(),
                  "strategy": strategy, "products_found": products_found,
                  "status": status, "note": note[:800]},
            headers={"Prefer": "return=minimal"}))

    # -- lezen (rapport & drempelbewaking) -----------------------------
    def active_count(self, retailer_id: str) -> int:
        resp = self._check(self.session.get(
            f"{self.rest}/products", timeout=60,
            params={"retailer_id": f"eq.{retailer_id}", "status": "eq.active",
                    "select": "product_key", "limit": "1"},
            headers={"Prefer": "count=exact", "Range": "0-0", "Range-Unit": "items"}))
        content_range = resp.headers.get("Content-Range", "/0")
        total = content_range.rsplit("/", 1)[-1]
        return int(total) if total.isdigit() else 0

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
