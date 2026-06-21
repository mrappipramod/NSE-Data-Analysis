"""
exporter.py
===========
Converts screener results into a clean, stable JSON schema designed to be
consumed by external sites/apps (e.g. a separate technical-analysis website
combining this fundamental data into a techno-fundamental view).

Design goals for the schema:
- Stable field names (won't silently rename things between runs)
- Keyed by symbol for O(1) lookup by an external consumer
- Includes a top-level `generated_at` timestamp so consumers can judge freshness
  and a `schema_version` so breaking changes can be detected programmatically
- Numbers are plain JSON numbers (not numpy types, which aren't JSON-serializable)
- Includes both the raw metrics AND the derived score/rating, so an external
  technical-analysis site can either trust this app's scoring or recompute its
  own combined score from the raw ratios
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

SCHEMA_VERSION = "1.0"


def _clean_value(v):
    """Convert numpy/pandas scalar types to native Python types; NaN/inf -> None."""
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        v = float(v)
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return round(v, 4)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if pd.isna(v) if not isinstance(v, (list, dict)) else False:
        return None
    return v


def build_export_payload(df: pd.DataFrame, deep_data: dict, universe_label: str) -> dict:
    """
    Builds the full export dict (ready for json.dump) from the screener's
    session_state-equivalent inputs: the ranked DataFrame and the per-symbol
    deep_data dict (info/trends/dcf/graham/result) produced in app/main.py.
    """
    stocks = {}

    for _, row in df.iterrows():
        symbol = row["Symbol"]
        d = deep_data.get(symbol, {})
        result = d.get("result", {})
        trends = d.get("trends", {})
        dcf = d.get("dcf", {})
        graham = d.get("graham", {})
        blended = d.get("blended", {})

        stocks[symbol] = {
            "symbol": symbol,
            "company_name": _clean_value(row.get("Company")),
            "sector": _clean_value(row.get("Sector")),
            "industry": _clean_value(row.get("Industry")),
            "price": _clean_value(row.get("Price")),

            "ratios": {
                "pe": _clean_value(row.get("PE")),
                "pb": _clean_value(row.get("PB")),
                "roe_pct": _clean_value(row.get("ROE %")),
                "debt_to_equity": _clean_value(row.get("Debt/Equity")),
                "profit_margin_pct": _clean_value(row.get("Profit Margin %")),
            },

            "growth": {
                "revenue_cagr_pct": _clean_value(row.get("Revenue CAGR %")),
                "net_income_cagr_pct": _clean_value(row.get("Net Income CAGR %")),
                "margin_trend": _clean_value(row.get("Margin Trend")),
                "revenue_growth_consistency_pct": _clean_value(trends.get("revenue_growth_consistency")),
                "years_of_data": _clean_value(trends.get("years_available")),
            },

            "valuation": {
                "dcf_fair_value": _clean_value(dcf.get("fair_value_per_share")),
                "graham_number": _clean_value(graham.get("graham_value")),
                "blended_fair_value": _clean_value(row.get("Blended Fair Value")),
                "estimated_upside_pct": _clean_value(row.get("Est. Upside %")),
                "valuation_models_used": _clean_value(row.get("Valuation Models Used")),
            },

            "fundamental_score": {
                "total": _clean_value(row.get("Score")),
                "rating": _clean_value(row.get("Rating")),
                "pillars": {
                    "valuation": _clean_value(row.get("Valuation Pillar")),
                    "profitability": _clean_value(row.get("Profitability Pillar")),
                    "stability": _clean_value(row.get("Stability Pillar")),
                    "growth": _clean_value(row.get("Growth Pillar")),
                    "valuation_upside": _clean_value(row.get("Upside Pillar")),
                },
                "key_notes": result.get("notes", [])[:6] if result else [],
            },
        }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "universe": universe_label,
        "stock_count": len(stocks),
        "data_source": "yfinance (Yahoo Finance, unofficial)",
        "disclaimer": (
            "Fundamental research data only, not investment advice. Scores and fair-value "
            "estimates are model outputs from limited public data. See README for methodology."
        ),
        "stocks": stocks,
    }
    return payload


def write_export(df: pd.DataFrame, deep_data: dict, universe_label: str,
                  output_path: str | Path = "data/exports/latest.json") -> Path:
    """
    Writes the JSON export to disk. Also writes a timestamped copy alongside
    `latest.json` (e.g. `2026-06-21.json`) so history is preserved if you want
    to track how scores evolve day over day.
    """
    payload = build_export_payload(df, deep_data, universe_label)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    dated_path = output_path.parent / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    with open(dated_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return output_path


def write_export_csv(df: pd.DataFrame, output_path: str | Path = "data/exports/latest.csv") -> Path:
    """
    Flat CSV alternative for consumers that prefer tabular data over nested JSON
    (e.g. quick spreadsheet imports, or simple scripts that don't want to parse JSON).
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path
