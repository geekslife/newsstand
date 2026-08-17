#!/usr/bin/env python3
"""Analyze a consistent 2005-2024 panel of seven metropolitan head offices."""

from __future__ import annotations

import csv
import itertools
import json
import math
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "metro-head-office-2004-2024.csv"
OUTPUT = ROOT / "data" / "metro-head-office-20y-results.json"
CITIES = ["서울", "경기", "부산", "대구", "광주", "대전", "울산"]
T95_DF6 = 2.446912


def party(city: str, year: int) -> str:
    """Year-end officeholder's broad political camp: d, c, or ambiguous."""
    if city == "서울":
        return "c" if year <= 2010 or year >= 2021 else "d"
    if city == "경기":
        return "c" if year <= 2017 else "d"
    if city == "부산":
        if year <= 2017 or year >= 2021:
            return "c"
        if year <= 2019:
            return "d"
        return "v"
    if city == "대구":
        return "c"
    if city == "광주":
        return "d"
    if city == "대전":
        if year == 2005:
            return "v"
        if year <= 2013 or year >= 2022:
            return "c"
        return "d"
    if city == "울산":
        if year <= 2017 or year >= 2022:
            return "c"
        return "d"
    raise KeyError(city)


def load_panel() -> list[dict]:
    raw = []
    with DATA.open(encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            raw.append(
                {
                    "city": record["city"],
                    "year": int(record["year"]),
                    **{
                        key: float(value)
                        for key, value in record.items()
                        if key not in {"city", "laf_cd", "year"}
                    },
                }
            )
    by_key = {(row["city"], row["year"]): row for row in raw}
    panel = []
    for city in CITIES:
        for year in range(2005, 2025):
            current = by_key[(city, year)]
            previous = by_key[(city, year - 1)]
            debt_growth = (current["debt_total_won"] / previous["debt_total_won"] - 1.0) * 100.0
            tax_growth = (current["local_tax_won"] / previous["local_tax_won"] - 1.0) * 100.0
            panel.append(
                {
                    **current,
                    "debt_growth_pct": debt_growth,
                    "debt_log_growth_pct": math.log(
                        current["debt_total_won"] / previous["debt_total_won"]
                    )
                    * 100.0,
                    "tax_growth_pct": tax_growth,
                    "tax_slowdown_pct": -tax_growth,
                    "debt_to_revenue_change_pp": current["debt_to_revenue_pct"]
                    - previous["debt_to_revenue_pct"],
                    "party_now": party(city, year),
                    "party_lag": party(city, year - 1),
                    "gfc": 1.0 if year in {2009, 2010} else 0.0,
                    "gfc_2008_2010": 1.0 if year in {2008, 2009, 2010} else 0.0,
                    "covid": 1.0 if year in {2020, 2021} else 0.0,
                }
            )

    for variable, standardized in (
        ("tax_slowdown_pct", "tax_slowdown_z"),
        ("capital_share_pct", "capital_share_z"),
    ):
        values = np.asarray([row[variable] for row in panel], dtype=float)
        mean = float(values.mean())
        sd = float(values.std(ddof=1))
        for row in panel:
            row[standardized] = (row[variable] - mean) / sd
    return panel


def fit_cluster_xy(
    x: np.ndarray, y: np.ndarray, groups: list[str]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    xtx_inv = np.linalg.pinv(x.T @ x)
    beta = xtx_inv @ x.T @ y
    residuals = y - x @ beta
    unique_groups = sorted(set(groups))
    meat = np.zeros((x.shape[1], x.shape[1]))
    for group in unique_groups:
        idx = np.asarray([i for i, label in enumerate(groups) if label == group])
        score = x[idx].T @ residuals[idx]
        meat += np.outer(score, score)
    n, k, g = len(y), x.shape[1], len(unique_groups)
    correction = (g / (g - 1.0)) * ((n - 1.0) / (n - k))
    covariance = correction * xtx_inv @ meat @ xtx_inv
    se = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    return beta, se, residuals, float(residuals @ residuals)


def design(
    sample: list[dict],
    predictors: list[str],
    outcome: str,
    *,
    city_fe: bool = True,
    year_fe: bool = False,
    trend: bool = False,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    cities = sorted({row["city"] for row in sample})
    years = sorted({row["year"] for row in sample})
    names = ["intercept", *predictors]
    if city_fe:
        names.extend(f"city:{city}" for city in cities[1:])
    if year_fe:
        names.extend(f"year:{year}" for year in years[1:])
    if trend:
        names.append("linear_trend")

    matrix = []
    response = []
    for row in sample:
        values = [1.0, *[float(row[predictor]) for predictor in predictors]]
        if city_fe:
            values.extend(1.0 if row["city"] == city else 0.0 for city in cities[1:])
        if year_fe:
            values.extend(1.0 if row["year"] == year else 0.0 for year in years[1:])
        if trend:
            values.append(float(row["year"] - 2014))
        matrix.append(values)
        response.append(row[outcome])
    return np.asarray(matrix), np.asarray(response), names


def model(
    sample: list[dict],
    predictors: list[str],
    outcome: str = "debt_growth_pct",
    *,
    city_fe: bool = True,
    year_fe: bool = False,
    trend: bool = False,
) -> dict:
    x, y, names = design(
        sample,
        predictors,
        outcome,
        city_fe=city_fe,
        year_fe=year_fe,
        trend=trend,
    )
    beta, se, _residuals, sse = fit_cluster_xy(x, y, [row["city"] for row in sample])
    estimates = {}
    for predictor in predictors:
        j = names.index(predictor)
        estimate = float(beta[j])
        std_error = float(se[j])
        estimates[predictor] = {
            "estimate": estimate,
            "cluster_se": std_error,
            "ci95_t6": [
                estimate - T95_DF6 * std_error,
                estimate + T95_DF6 * std_error,
            ],
        }
    return {
        "n": len(y),
        "k": x.shape[1],
        "outcome": outcome,
        "predictors": predictors,
        "city_fe": city_fe,
        "year_fe": year_fe,
        "linear_trend": trend,
        "sse": sse,
        "estimates": estimates,
    }


def select(panel: list[dict], attribution: str = "current") -> list[dict]:
    party_key = "party_now" if attribution == "current" else "party_lag"
    return [
        {**row, "democratic": 1.0 if row[party_key] == "d" else 0.0}
        for row in panel
        if row[party_key] in {"d", "c"}
    ]


def means(sample: list[dict], outcome: str = "debt_growth_pct") -> dict:
    democratic = [row[outcome] for row in sample if row["democratic"] == 1.0]
    conservative = [row[outcome] for row in sample if row["democratic"] == 0.0]
    return {
        "n": len(sample),
        "n_democratic": len(democratic),
        "n_conservative": len(conservative),
        "democratic_mean": float(np.mean(democratic)),
        "conservative_mean": float(np.mean(conservative)),
        "gap_democratic_minus_conservative": float(np.mean(democratic) - np.mean(conservative)),
        "democratic_median": float(np.median(democratic)),
        "conservative_median": float(np.median(conservative)),
    }


def period_means(panel: list[dict]) -> dict:
    groups = {
        "ordinary": [row for row in panel if not row["gfc"] and not row["covid"]],
        "gfc_2009_2010": [row for row in panel if row["gfc"]],
        "covid_2020_2021": [row for row in panel if row["covid"]],
    }
    return {
        name: {
            "n": len(rows),
            "mean_debt_growth_pct": float(np.mean([row["debt_growth_pct"] for row in rows])),
            "median_debt_growth_pct": float(np.median([row["debt_growth_pct"] for row in rows])),
        }
        for name, rows in groups.items()
    }


def incremental_sse(sample: list[dict], full_predictors: list[str], outcome: str) -> dict:
    full = model(sample, full_predictors, outcome, city_fe=True, trend=True)
    drops = {}
    for predictor in full_predictors:
        reduced_predictors = [item for item in full_predictors if item != predictor]
        reduced = model(sample, reduced_predictors, outcome, city_fe=True, trend=True)
        drops[predictor] = max(reduced["sse"] - full["sse"], 0.0)
    total = sum(drops.values())
    return {
        "sse_drop_if_added_last": drops,
        "share_of_summed_sse_drops_pct": {
            key: value / total * 100.0 if total else 0.0 for key, value in drops.items()
        },
        "note": "Correlated predictors make these order-free last-added shares descriptive, not causal.",
    }


def leave_one_city_out(
    sample: list[dict], predictors: list[str], outcome: str
) -> dict:
    coefficients = {predictor: {} for predictor in predictors}
    for city in CITIES:
        reduced = [row for row in sample if row["city"] != city]
        fitted = model(reduced, predictors, outcome, city_fe=True, trend=True)
        for predictor in predictors:
            coefficients[predictor][city] = fitted["estimates"][predictor]["estimate"]
    return {
        predictor: {
            "by_omitted_city": values,
            "range": [min(values.values()), max(values.values())],
        }
        for predictor, values in coefficients.items()
    }


def exact_wild_cluster_p_for_party(sample: list[dict], attribution: str) -> float:
    party_sample = select(sample, attribution)
    predictors = ["democratic"]
    x, y, names = design(
        party_sample, predictors, "debt_growth_pct", city_fe=True, year_fe=True
    )
    labels = [row["city"] for row in party_sample]
    groups = sorted(set(labels))
    j = names.index("democratic")
    beta, se, _residuals, _sse = fit_cluster_xy(x, y, labels)
    observed_t = beta[j] / se[j]

    x_null = np.delete(x, j, axis=1)
    beta_null = np.linalg.pinv(x_null.T @ x_null) @ x_null.T @ y
    fitted_null = x_null @ beta_null
    residuals_null = y - fitted_null
    exceed = 0
    for signs in itertools.product((-1.0, 1.0), repeat=len(groups)):
        sign_by_group = dict(zip(groups, signs))
        weights = np.asarray([sign_by_group[label] for label in labels])
        y_star = fitted_null + residuals_null * weights
        beta_star, se_star, _residuals, _sse = fit_cluster_xy(x, y_star, labels)
        t_star = beta_star[j] / se_star[j]
        if abs(t_star) >= abs(observed_t) - 1e-12:
            exceed += 1
    return exceed / (2 ** len(groups))


def main() -> None:
    panel = load_panel()
    current = select(panel, "current")
    lagged = select(panel, "lagged")
    drivers = ["gfc", "covid", "tax_slowdown_z", "capital_share_z", "democratic"]
    crises_and_party = ["gfc", "covid", "democratic"]

    results = {
        "source": {
            "name": "행정안전부 지방재정365 공개 API",
            "coverage": "7개 광역단체 본청, 2004~2024년 결산",
            "debt": f"{BASE_URL}/ACCAM",
            "revenue": f"{BASE_URL}/FIACRV",
            "expenditure": f"{BASE_URL}/SDSCF",
        },
        "definitions": {
            "analysis_years": "2005~2024 (2004 year-end balance is the growth base)",
            "debt": "회계별 지방채 잔액 네 계정의 합계",
            "revenue": "재원별 회계별 세입결산 순계합계",
            "local_tax": "재원별 회계별 세입결산 지방세수입 순계",
            "capital_outlay": "성질별 단체별 세출결산 4xxxx 항목 합계",
            "tax_slowdown_z": "지방세 증가율 하락 1표준편차",
            "capital_share_z": "성질별 분류 세출 중 자본지출 비중 상승 1표준편차",
            "gfc": "2009~2010",
            "covid": "2020~2021",
        },
        "scales": {
            "tax_slowdown_one_sd_pp": float(
                np.std([row["tax_slowdown_pct"] for row in panel], ddof=1)
            ),
            "capital_share_one_sd_pp": float(
                np.std([row["capital_share_pct"] for row in panel], ddof=1)
            ),
        },
        "descriptive": {
            "party_current": means(current),
            "party_lagged": means(lagged),
            "period_means": period_means(panel),
            "first_decade_current": means([row for row in current if row["year"] <= 2014]),
            "second_decade_current": means([row for row in current if row["year"] >= 2015]),
        },
        "models": {
            "crises_and_party_current": model(
                current, crises_and_party, city_fe=True, trend=True
            ),
            "crises_and_party_gfc_2008_2010": model(
                current,
                ["gfc_2008_2010", "covid", "democratic"],
                city_fe=True,
                trend=True,
            ),
            "drivers_current": model(current, drivers, city_fe=True, trend=True),
            "drivers_lagged": model(lagged, drivers, city_fe=True, trend=True),
            "drivers_log_growth_current": model(
                current,
                drivers,
                outcome="debt_log_growth_pct",
                city_fe=True,
                trend=True,
            ),
            "burden_change_current": model(
                current,
                drivers,
                outcome="debt_to_revenue_change_pp",
                city_fe=True,
                trend=True,
            ),
            "party_year_fe_current": model(
                current,
                ["democratic"],
                city_fe=True,
                year_fe=True,
            ),
            "party_year_fe_lagged": model(
                lagged,
                ["democratic"],
                city_fe=True,
                year_fe=True,
            ),
            "drivers_year_fe_current": model(
                current,
                ["tax_slowdown_z", "capital_share_z", "democratic"],
                city_fe=True,
                year_fe=True,
            ),
        },
        "diagnostics": {
            "incremental_sse_debt_growth": incremental_sse(
                current, drivers, "debt_growth_pct"
            ),
            "leave_one_city_out_debt_growth": leave_one_city_out(
                current, drivers, "debt_growth_pct"
            ),
            "wild_cluster_party_current_p": exact_wild_cluster_p_for_party(panel, "current"),
            "wild_cluster_party_lagged_p": exact_wild_cluster_p_for_party(panel, "lagged"),
        },
    }
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


BASE_URL = "https://www.lofin365.go.kr/lf/hub"


if __name__ == "__main__":
    main()
