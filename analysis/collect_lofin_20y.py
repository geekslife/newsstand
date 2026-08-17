#!/usr/bin/env python3
"""Collect a consistent 2004-2024 head-office panel from MOIS LOFIN APIs.

The public sample access returns five rows per page but permits pagination and
local-government filters.  This collector therefore requests one metropolitan
head office at a time, retains the returned rows for audit, and writes a compact
city-year panel used by the article analysis.

Amounts returned by LOFIN are won.  The debt balance is the sum of the four
account columns in the "회계별 지방채 잔액" dataset.  Net revenue and local-tax
revenue come from the "재원별 회계별 세입결산" dataset.  Capital outlays are the
4xxxx economic-classification rows in the "성질별 단체별 세출결산" dataset.
"""

from __future__ import annotations

import concurrent.futures
import csv
import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
PANEL_PATH = DATA_DIR / "metro-head-office-2004-2024.csv"
RAW_PATH = DATA_DIR / "metro-head-office-2004-2024-raw.json"

BASE = "https://www.lofin365.go.kr/lf/hub"
PAGE_SIZE = 5
YEARS = range(2004, 2025)
CITIES = {
    "서울": "1100000",
    "경기": "4100000",
    "부산": "2600000",
    "대구": "2700000",
    "광주": "2900000",
    "대전": "3000000",
    "울산": "3100000",
}
SERVICES = {
    "debt": "ACCAM",
    "revenue": "FIACRV",
    "expenditure": "SDSCF",
}


def fetch_page(service: str, year: int, city_code: str, page: int = 1) -> dict:
    params = urllib.parse.urlencode(
        {
            "fyr": year,
            "laf_cd": city_code,
            "Type": "json",
            "pIndex": page,
            "pSize": PAGE_SIZE,
        }
    )
    url = f"{BASE}/{service}?{params}"
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "middl-news-research/1.0"})
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if service not in payload:
                raise RuntimeError(f"LOFIN returned no {service} payload for {year}/{city_code}: {payload}")
            blocks = payload[service]
            count = int(blocks[0]["head"][0]["list_total_count"])
            rows = blocks[1].get("row", []) if len(blocks) > 1 else []
            return {"url": url, "count": count, "rows": rows}
        except Exception as exc:  # pragma: no cover - network retry path
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"failed after retries: {url}") from last_error


def fetch_task(task: tuple[str, int, str, int]) -> tuple[tuple[str, int, str, int], dict]:
    service, year, city_code, page = task
    return task, fetch_page(service, year, city_code, page)


def collect_pages() -> dict[tuple[str, int, str], list[dict]]:
    initial_tasks = [
        (service, year, city_code, 1)
        for service in SERVICES.values()
        for year in YEARS
        for city_code in CITIES.values()
    ]
    first_pages: dict[tuple[str, int, str, int], dict] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        for task, result in executor.map(fetch_task, initial_tasks):
            first_pages[task] = result

    remaining_tasks = []
    for (service, year, city_code, _page), result in first_pages.items():
        page_count = math.ceil(result["count"] / PAGE_SIZE)
        remaining_tasks.extend(
            (service, year, city_code, page) for page in range(2, page_count + 1)
        )

    other_pages: dict[tuple[str, int, str, int], dict] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        for task, result in executor.map(fetch_task, remaining_tasks):
            other_pages[task] = result

    pages = {**first_pages, **other_pages}
    grouped: dict[tuple[str, int, str], list[dict]] = {}
    for service in SERVICES.values():
        for year in YEARS:
            for city_code in CITIES.values():
                key = (service, year, city_code)
                count = first_pages[(service, year, city_code, 1)]["count"]
                page_count = math.ceil(count / PAGE_SIZE)
                rows = []
                for page in range(1, page_count + 1):
                    rows.extend(pages[(service, year, city_code, page)]["rows"])
                if len(rows) != count:
                    raise RuntimeError(
                        f"row-count mismatch for {service}/{year}/{city_code}: {len(rows)} != {count}"
                    )
                grouped[key] = rows
    return grouped


def one(rows: list[dict], predicate, label: str) -> dict:
    matches = [row for row in rows if predicate(row)]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {label} row; found {len(matches)}")
    return matches[0]


def build_panel(grouped: dict[tuple[str, int, str], list[dict]]) -> list[dict]:
    panel = []
    for city, city_code in CITIES.items():
        for year in YEARS:
            debt_rows = grouped[(SERVICES["debt"], year, city_code)]
            revenue_rows = grouped[(SERVICES["revenue"], year, city_code)]
            expenditure_rows = grouped[(SERVICES["expenditure"], year, city_code)]

            debt = one(debt_rows, lambda row: row["laf_cd"] == city_code, "debt")
            revenue_total = one(
                revenue_rows,
                lambda row: row.get("armk_cd") == "00000",
                "revenue total",
            )
            local_tax_rows = [
                row for row in revenue_rows if row.get("armk_cd") in {"10000", "11000"}
            ]
            local_tax = next(
                (row for row in local_tax_rows if row.get("armk_cd") == "10000"),
                local_tax_rows[0] if local_tax_rows else None,
            )
            if local_tax is None:
                raise RuntimeError(f"no local-tax row for {city}/{year}")

            debt_accounts = [int(debt[f"lgfd_ramt_amt{i}"]) for i in range(1, 5)]
            expenditure = sum(int(row["bdg_prsm_cash_amt"]) for row in expenditure_rows)
            capital = sum(
                int(row["bdg_prsm_cash_amt"])
                for row in expenditure_rows
                if str(row.get("aemk_grp_cd", "")).startswith("4")
            )
            debt_total = sum(debt_accounts)
            revenue_net = int(revenue_total["prsm_amt"])
            tax_revenue = int(local_tax["prsm_amt"])

            panel.append(
                {
                    "city": city,
                    "laf_cd": city_code,
                    "year": year,
                    "debt_general_won": debt_accounts[0],
                    "debt_other_special_won": debt_accounts[1],
                    "debt_public_enterprise_won": debt_accounts[2],
                    "debt_fund_won": debt_accounts[3],
                    "debt_total_won": debt_total,
                    "revenue_net_won": revenue_net,
                    "local_tax_won": tax_revenue,
                    "classified_expenditure_won": expenditure,
                    "capital_outlay_won": capital,
                    "debt_to_revenue_pct": debt_total / revenue_net * 100.0,
                    "capital_share_pct": capital / expenditure * 100.0,
                }
            )
    return panel


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    grouped = collect_pages()
    panel = build_panel(grouped)

    raw = {
        "source": "Ministry of the Interior and Safety, Local Finance 365 open API",
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "services": SERVICES,
        "page_size": PAGE_SIZE,
        "rows": [
            {
                "service": service,
                "year": year,
                "laf_cd": city_code,
                "data": rows,
            }
            for (service, year, city_code), rows in sorted(grouped.items())
        ],
    }
    RAW_PATH.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    with PANEL_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(panel[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(panel)

    print(f"wrote {len(panel)} city-years to {PANEL_PATH}")
    print(f"wrote auditable API rows to {RAW_PATH}")


if __name__ == "__main__":
    main()
