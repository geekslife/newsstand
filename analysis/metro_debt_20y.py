#!/usr/bin/env python3
"""Twenty-year sensitivity analysis for seven metropolitan jurisdictions.

The source series is the Ministry of the Interior and Safety's annual local
government debt table, republished by e-Nara Indicator. Values are year-end
balances in 100 million won and include lower-level governments within each
province/metropolitan city. This is intentionally kept separate from the
2015-2024 head-office-only core analysis used in the article.
"""

from __future__ import annotations

import csv
import itertools
import json
import math
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "metro-debt-2004-2024.csv"
CITIES = ["서울", "경기", "부산", "대구", "광주", "대전", "울산"]
T95_DF6 = 2.446912


def party(city: str, year: int) -> str:
    """Year-end officeholder's broad political camp: d, c, or v/ambiguous."""
    if city == "서울":
        return "c" if year <= 2010 or year >= 2021 else "d"
    if city == "경기":
        return "c" if year <= 2017 else "d"
    if city == "부산":
        if year <= 2017 or year >= 2021:
            return "c"
        if year <= 2019:
            return "d"
        return "v"  # 2020: mayor resigned in April; acting mayor thereafter.
    if city == "대구":
        return "c"
    if city == "광주":
        return "d"
    if city == "대전":
        if year == 2005:
            return "v"  # Yeom Hong-chul changed from GNP to Uri Party mid-term.
        if year <= 2013 or year >= 2022:
            return "c"
        return "d"
    if city == "울산":
        if year <= 2017 or year >= 2022:
            return "c"
        return "d"
    raise KeyError(city)


def load_panel() -> list[dict]:
    rows: list[dict] = []
    with DATA.open(encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            city = record["city"]
            balances = {int(k): float(v) for k, v in record.items() if k != "city"}
            for year in range(2005, 2025):
                current = balances[year]
                previous = balances[year - 1]
                rows.append(
                    {
                        "city": city,
                        "year": year,
                        "debt": current,
                        "growth_pct": (current / previous - 1.0) * 100.0,
                        "log_growth_pct": math.log(current / previous) * 100.0,
                        "party_now": party(city, year),
                        "party_lag": party(city, year - 1),
                    }
                )
    return rows


def select(rows: list[dict], start: int, end: int, attribution: str, excluded: set[int]) -> list[dict]:
    key = "party_now" if attribution == "current" else "party_lag"
    return [
        {**r, "party": r[key]}
        for r in rows
        if start <= r["year"] <= end and r["year"] not in excluded and r[key] in {"c", "d"}
    ]


def means(sample: list[dict], outcome: str = "growth_pct") -> dict:
    out: dict[str, float | int] = {"n": len(sample)}
    values = {}
    for p in ("d", "c"):
        vals = [r[outcome] for r in sample if r["party"] == p]
        values[p] = float(np.mean(vals))
        out[f"n_{p}"] = len(vals)
        out[f"mean_{p}"] = values[p]
        out[f"median_{p}"] = float(np.median(vals))
    out["gap_d_minus_c"] = values["d"] - values["c"]
    out["median_gap_d_minus_c"] = float(out["median_d"] - out["median_c"])
    return out


def design(sample: list[dict], outcome: str, year_fe: bool = True) -> tuple[np.ndarray, np.ndarray, list[str]]:
    cities = sorted({r["city"] for r in sample})
    years = sorted({r["year"] for r in sample})
    names = ["intercept", "democratic"]
    names += [f"city:{c}" for c in cities[1:]]
    if year_fe:
        names += [f"year:{y}" for y in years[1:]]

    matrix = []
    response = []
    for r in sample:
        row = [1.0, 1.0 if r["party"] == "d" else 0.0]
        row += [1.0 if r["city"] == c else 0.0 for c in cities[1:]]
        if year_fe:
            row += [1.0 if r["year"] == y else 0.0 for y in years[1:]]
        matrix.append(row)
        response.append(r[outcome])
    return np.asarray(matrix), np.asarray(response), names


def ols_cluster(sample: list[dict], outcome: str = "growth_pct", year_fe: bool = True) -> dict:
    x, y, names = design(sample, outcome, year_fe)
    groups = [r["city"] for r in sample]
    beta, se = fit_cluster_xy(x, y, groups)
    j = names.index("democratic")
    estimate = float(beta[j])
    std_error = float(se[j])
    return {
        "n": len(y),
        "k": x.shape[1],
        "estimate": estimate,
        "cluster_se": std_error,
        "ci95_t6": [estimate - T95_DF6 * std_error, estimate + T95_DF6 * std_error],
        "outcome": outcome,
        "city_fe": True,
        "year_fe": year_fe,
    }


def crisis_design(
    sample: list[dict],
    outcome: str,
    gfc_years: set[int],
    trend: bool = True,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Design for comparing two common crises with the political-camp estimate.

    Full year fixed effects cannot be included because the crisis indicators are
    common to all cities in the same year. City fixed effects and a linear time
    trend are therefore used to separate persistent place differences and the
    long-run trend from the two crisis periods.
    """
    cities = sorted({r["city"] for r in sample})
    names = ["intercept", "democratic", "gfc", "covid"]
    names += [f"city:{c}" for c in cities[1:]]
    if trend:
        names.append("linear_trend")

    matrix = []
    response = []
    for r in sample:
        row = [
            1.0,
            1.0 if r["party"] == "d" else 0.0,
            1.0 if r["year"] in gfc_years else 0.0,
            1.0 if r["year"] in {2020, 2021} else 0.0,
        ]
        row += [1.0 if r["city"] == c else 0.0 for c in cities[1:]]
        if trend:
            row.append(float(r["year"] - 2014))
        matrix.append(row)
        response.append(r[outcome])
    return np.asarray(matrix), np.asarray(response), names


def crisis_model(
    rows: list[dict],
    attribution: str,
    gfc_years: set[int],
    outcome: str = "growth_pct",
    trend: bool = True,
) -> dict:
    sample = select(rows, 2005, 2024, attribution, set())
    x, y, names = crisis_design(sample, outcome, gfc_years, trend)
    groups = [r["city"] for r in sample]
    beta, se = fit_cluster_xy(x, y, groups)
    estimates = {}
    for name in ("democratic", "gfc", "covid"):
        j = names.index(name)
        estimate = float(beta[j])
        std_error = float(se[j])
        estimates[name] = {
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
        "attribution": attribution,
        "gfc_years": sorted(gfc_years),
        "covid_years": [2020, 2021],
        "city_fe": True,
        "linear_trend": trend,
        "outcome": outcome,
        "estimates": estimates,
    }


def crisis_period_means(rows: list[dict]) -> dict:
    groups = {
        "ordinary": [r for r in rows if r["year"] not in {2009, 2010, 2020, 2021}],
        "gfc_2009_2010": [r for r in rows if r["year"] in {2009, 2010}],
        "covid_2020_2021": [r for r in rows if r["year"] in {2020, 2021}],
    }
    return {
        name: {
            "n": len(sample),
            "mean_growth_pct": float(np.mean([r["growth_pct"] for r in sample])),
            "median_growth_pct": float(np.median([r["growth_pct"] for r in sample])),
        }
        for name, sample in groups.items()
    }


def fit_cluster_xy(x: np.ndarray, y: np.ndarray, group_labels: list[str]) -> tuple[np.ndarray, np.ndarray]:
    xtx_inv = np.linalg.pinv(x.T @ x)
    beta = xtx_inv @ x.T @ y
    resid = y - x @ beta
    groups = sorted(set(group_labels))
    meat = np.zeros((x.shape[1], x.shape[1]))
    for group in groups:
        idx = np.asarray([i for i, label in enumerate(group_labels) if label == group])
        score = x[idx].T @ resid[idx]
        meat += np.outer(score, score)
    n, k, g = len(y), x.shape[1], len(groups)
    correction = (g / (g - 1.0)) * ((n - 1.0) / (n - k))
    cov = correction * xtx_inv @ meat @ xtx_inv
    se = np.sqrt(np.maximum(np.diag(cov), 0.0))
    return beta, se


def wild_cluster_p(sample: list[dict], outcome: str = "growth_pct") -> float:
    """Exact Rademacher wild-cluster bootstrap p-value for seven city clusters."""
    x, y, names = design(sample, outcome, True)
    labels = [r["city"] for r in sample]
    groups = sorted(set(labels))
    j = names.index("democratic")
    beta, se = fit_cluster_xy(x, y, labels)
    observed_t = beta[j] / se[j]

    x_null = np.delete(x, j, axis=1)
    beta_null = np.linalg.pinv(x_null.T @ x_null) @ x_null.T @ y
    fitted_null = x_null @ beta_null
    resid_null = y - fitted_null

    exceed = 0
    for signs in itertools.product((-1.0, 1.0), repeat=len(groups)):
        sign_by_group = dict(zip(groups, signs))
        weights = np.asarray([sign_by_group[label] for label in labels])
        y_star = fitted_null + resid_null * weights
        beta_star, se_star = fit_cluster_xy(x, y_star, labels)
        t_star = beta_star[j] / se_star[j]
        if abs(t_star) >= abs(observed_t) - 1e-12:
            exceed += 1
    return exceed / (2 ** len(groups))


def leave_one_city_out(sample: list[dict], outcome: str = "growth_pct") -> dict:
    estimates = {}
    for city in CITIES:
        reduced = [r for r in sample if r["city"] != city]
        estimates[city] = ols_cluster(reduced, outcome)["estimate"]
    return {
        "by_omitted_city": estimates,
        "range": [min(estimates.values()), max(estimates.values())],
    }


def result_block(rows: list[dict], start: int, end: int, attribution: str, excluded: set[int]) -> dict:
    sample = select(rows, start, end, attribution, excluded)
    arithmetic_model = ols_cluster(sample, "growth_pct")
    arithmetic_model["wild_cluster_p"] = wild_cluster_p(sample, "growth_pct")
    log_model = ols_cluster(sample, "log_growth_pct")
    log_model["wild_cluster_p"] = wild_cluster_p(sample, "log_growth_pct")
    return {
        "period": [start, end],
        "attribution": attribution,
        "excluded_years": sorted(excluded),
        "arithmetic_growth": means(sample, "growth_pct"),
        "log_growth": means(sample, "log_growth_pct"),
        "fe_year_arithmetic": arithmetic_model,
        "fe_year_log": log_model,
        "leave_one_city_out_arithmetic": leave_one_city_out(sample, "growth_pct"),
    }


def main() -> None:
    rows = load_panel()
    results = {
        "source": {
            "name": "행정안전부 지방채무현황 / e-나라지표 연도별 자치단체 채무현황",
            "url": "https://www.index.go.kr/unity/potal/main/EachDtlPageDetail.do?idx_cd=1046",
            "unit": "억원",
            "coverage": "시도별 합계(시군구 포함), 2004년 말 잔액부터 2024년 말 잔액",
        },
        "definitions": {
            "current": "채무가 변한 회계연도의 연말 단체장 계열에 귀속",
            "lagged": "전년도 연말 단체장 계열에 귀속(예산·집행 시차 민감도)",
            "ambiguous_exclusions": "부산 2020 권한대행, 대전 2005 임기 중 당적 변경은 해당 귀속에서 제외",
            "gfc_main": "글로벌 금융위기 대응이 결산 채무에 집중적으로 나타난 2009~2010년",
            "gfc_sensitivity": "충격 발생 연도까지 포함한 2008~2010년",
            "covid": "코로나19 대응이 집중된 2020~2021년",
        },
        "crisis_comparison": {
            "period_means": crisis_period_means(rows),
            "main_current": crisis_model(rows, "current", {2009, 2010}),
            "main_lagged": crisis_model(rows, "lagged", {2009, 2010}),
            "gfc_2008_2010_current": crisis_model(rows, "current", {2008, 2009, 2010}),
            "main_current_without_trend": crisis_model(rows, "current", {2009, 2010}, trend=False),
        },
        "analyses": {
            "full_current": result_block(rows, 2005, 2024, "current", set()),
            "full_lagged": result_block(rows, 2005, 2024, "lagged", set()),
            "non_covid_current": result_block(rows, 2005, 2024, "current", {2020, 2021}),
            "non_covid_lagged": result_block(rows, 2005, 2024, "lagged", {2020, 2021}),
            "pre_2015_current": result_block(rows, 2005, 2014, "current", set()),
            "pre_2015_lagged": result_block(rows, 2005, 2014, "lagged", set()),
            "pre_2015_exclude_gfc_current": result_block(rows, 2005, 2014, "current", {2009, 2010}),
            "pre_2015_exclude_gfc_lagged": result_block(rows, 2005, 2014, "lagged", {2009, 2010}),
            "post_2015_current": result_block(rows, 2015, 2024, "current", set()),
            "post_2015_lagged": result_block(rows, 2015, 2024, "lagged", set()),
            "post_2015_non_covid_current": result_block(rows, 2015, 2024, "current", {2020, 2021}),
            "post_2015_non_covid_lagged": result_block(rows, 2015, 2024, "lagged", {2020, 2021}),
            "exclude_gfc_and_covid_current": result_block(rows, 2005, 2024, "current", {2009, 2010, 2020, 2021}),
            "exclude_gfc_and_covid_lagged": result_block(rows, 2005, 2024, "lagged", {2009, 2010, 2020, 2021}),
        },
    }
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
