"""Shared query-parameter filters and WHERE-clause builder for the gold_* tables."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd
from fastapi import Query

from .canonical import canonical_ios, canonical_model
from .db import QueryStats, query_df

_variant_cache: dict[str, dict[str, list[str]]] = {}


def variants(kind: str) -> dict[str, list[str]]:
    """canonical label -> list of raw labels present in serving tables (built once, cached)."""
    if kind in _variant_cache:
        return _variant_cache[kind]
    if kind == "model":
        sql = """SELECT DISTINCT iphone_model AS v FROM gold_issue_summary
                 UNION SELECT DISTINCT iphone_model FROM gold_sentiment_summary
                 UNION SELECT DISTINCT iphone_model FROM gold_model_comparison
                 UNION SELECT DISTINCT iphone_model FROM gold_support_demand"""
        fn = canonical_model
    else:
        sql = """SELECT DISTINCT ios_version AS v FROM gold_issue_summary
                 UNION SELECT DISTINCT ios_version FROM gold_model_comparison
                 UNION SELECT DISTINCT ios_version FROM gold_support_demand"""
        fn = canonical_ios
    out: dict[str, list[str]] = {}
    for raw in query_df(sql)["v"].dropna():
        out.setdefault(fn(raw), []).append(raw)
    _variant_cache[kind] = out
    return out


def reset_variant_cache() -> None:
    _variant_cache.clear()


@dataclass
class Filters:
    date_from: date | None = None
    date_to: date | None = None
    model: str | None = None
    ios: str | None = None
    feature: str | None = None
    issue: str | None = None
    include_non_defect: bool = True
    stats: QueryStats = field(default_factory=QueryStats)

    def applied(self) -> dict[str, Any]:
        d = {
            "date_from": self.date_from, "date_to": self.date_to, "model": self.model, "ios": self.ios,
            "feature": self.feature, "issue": self.issue, "include_non_defect": self.include_non_defect,
        }
        return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in d.items() if v not in (None, True)}

    def where(self, columns: set[str], date_col: str = "feedback_date") -> tuple[str, dict[str, Any]]:
        """Build a WHERE clause using only the filters whose column exists in `columns`."""
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if date_col in columns:
            if self.date_from:
                clauses.append(f"{date_col} >= :date_from")
                params["date_from"] = self.date_from
            if self.date_to:
                clauses.append(f"{date_col} <= :date_to")
                params["date_to"] = self.date_to
        if self.model and "iphone_model" in columns:
            raw_names = variants("model").get(self.model, [self.model])
            keys = []
            for i, v in enumerate(raw_names):
                keys.append(f":m{i}")
                params[f"m{i}"] = v
            clauses.append(f"iphone_model IN ({', '.join(keys)})")
        if self.ios and "ios_version" in columns:
            raw_names = variants("ios").get(self.ios, [self.ios])
            keys = []
            for i, v in enumerate(raw_names):
                keys.append(f":o{i}")
                params[f"o{i}"] = v
            clauses.append(f"ios_version IN ({', '.join(keys)})")
        if self.feature and "feature_category" in columns:
            clauses.append("feature_category = :feature")
            params["feature"] = self.feature
        if self.issue and "issue_category" in columns:
            clauses.append("issue_category = :issue")
            params["issue"] = self.issue
        if not self.include_non_defect and "issue_category" in columns:
            clauses.append("issue_category <> 'Non-Defect / General Inquiry'")
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def get_filters(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    model: str | None = Query(None, description="Canonical iPhone model, e.g. 'iPhone 15 Pro'"),
    ios: str | None = Query(None, description="Canonical iOS version, e.g. 'iOS 26' or 'iOS 26.4.1'"),
    feature: str | None = Query(None),
    issue: str | None = Query(None),
    include_non_defect: bool = Query(True),
) -> Filters:
    return Filters(date_from, date_to, model, ios, feature, issue, include_non_defect)


def add_canonical(frame: pd.DataFrame) -> pd.DataFrame:
    if "iphone_model" in frame.columns:
        frame["iphone_model"] = frame["iphone_model"].map(canonical_model)
    if "ios_version" in frame.columns:
        frame["ios_version"] = frame["ios_version"].map(canonical_ios)
    return frame


def records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """JSON-safe records: NaN -> None, dates -> ISO strings."""
    out = frame.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%d")
        elif out[c].dtype == object:
            out[c] = out[c].map(lambda v: v.isoformat() if hasattr(v, "isoformat") else v)
    out = out.astype(object).where(pd.notnull(out), None)
    return out.to_dict(orient="records")


def envelope(frame_or_list, filters: Filters | None = None, **meta) -> dict[str, Any]:
    data = records(frame_or_list) if isinstance(frame_or_list, pd.DataFrame) else frame_or_list
    m: dict[str, Any] = {"total": len(data), **meta}
    if filters is not None:
        m["filters_applied"] = filters.applied()
        m["db_ms"] = round(filters.stats.db_ms, 2)
        m["queries"] = filters.stats.queries
        m["cache_hits"] = filters.stats.cache_hits
    return {"data": data, "meta": m}
