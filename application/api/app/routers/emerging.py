"""BR03 - Emerging issue detection (gold_emerging_issues, produced by the stateful sliding-window stream engine)."""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, Query

from ..canonical import OTHER_MODEL
from ..db import query_df
from ..filters import Filters, add_canonical, envelope, get_filters

router = APIRouter(prefix="/emerging", tags=["BR03 emerging"])
COLS = {"feedback_date", "iphone_model", "feature_category", "issue_category"}
RULE = {"min_curr_3d_avg": 2.0, "min_growth_pct": 150.0, "min_z_score": 2.0,
        "description": "curr_3d_avg >= 2 AND (growth_rate_pct >= 150 OR z_score >= 2); baseline = days t-16..t-3"}


def _load(f: Filters) -> pd.DataFrame:
    where, params = f.where(COLS)
    df = query_df(
        f"""SELECT feedback_date, iphone_model, feature_category, issue_category, daily_volume,
                   curr_3d_avg, base_14d_avg, base_14d_std, growth_rate_pct, z_score, is_anomaly
            FROM gold_emerging_issues{where}""", params, f.stats,
    )
    df = add_canonical(df)
    df["feedback_date"] = pd.to_datetime(df["feedback_date"])
    # folding raw model variants can create duplicate keys: keep the strongest signal per key
    df = df.sort_values(["z_score", "growth_rate_pct"], ascending=False)
    df = df.drop_duplicates(["feedback_date", "iphone_model", "feature_category", "issue_category"])
    return df


@router.get("/alerts")
def alerts(
    f: Filters = Depends(get_filters),
    min_curr: float = Query(RULE["min_curr_3d_avg"], ge=0),
    min_growth: float = Query(RULE["min_growth_pct"], ge=0),
    min_z: float = Query(RULE["min_z_score"], ge=0),
    exclude_unspecified: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
):
    """Alerts under the Gold rule by default; thresholds can be tightened or loosened by the analyst."""
    df = _load(f)
    mask = (df["curr_3d_avg"] >= min_curr) & ((df["growth_rate_pct"] >= min_growth) | (df["z_score"] >= min_z))
    out = df[mask].copy()
    if exclude_unspecified:
        out = out[out["iphone_model"] != OTHER_MODEL]
    out["severity"] = pd.cut(out["z_score"], [-1e9, 2, 3, 1e9], labels=["watch", "elevated", "critical"]).astype(str)
    out["matches_gold_rule"] = out["is_anomaly"].astype(bool)
    out = out.sort_values(["feedback_date", "z_score"], ascending=[False, False]).head(limit)
    by_issue = out.groupby("issue_category").size().sort_values(ascending=False)
    return envelope(
        out, f, rule=RULE, thresholds={"min_curr": min_curr, "min_growth": min_growth, "min_z": min_z},
        gold_rule_alerts=int(df["is_anomaly"].sum()), alerts_by_issue=[{"issue": k, "n": int(v)} for k, v in by_issue.items()],
    )


@router.get("/series")
def series(issue: str, model: str | None = None, f: Filters = Depends(get_filters)):
    """Daily volume vs 3-day current and 14-day baseline for one (model, issue) key; feeds small multiples."""
    f.issue = issue
    f.model = model
    df = _load(f)
    if model is None:
        # aggregate over models: sum daily volume, recompute window stats on the aggregate
        g = df.groupby("feedback_date")["daily_volume"].sum().sort_index()
        full = g.reindex(pd.date_range(g.index.min(), g.index.max()), fill_value=0)
        curr = full.rolling(3, min_periods=1).mean()
        base = full.shift(3).rolling(14, min_periods=1).mean().fillna(0)
        std = full.shift(3).rolling(14, min_periods=2).std().fillna(0.5).clip(lower=0.5)
        out = pd.DataFrame({
            "feedback_date": full.index, "daily_volume": full.values, "curr_3d_avg": curr.round(2).values,
            "base_14d_avg": base.round(2).values,
        })
        out["z_score"] = ((curr - base) / std).round(2).values
        out["growth_rate_pct"] = ((curr - base) / base.clip(lower=1) * 100).round(2).values
        out["is_anomaly"] = (curr >= 2) & ((out["growth_rate_pct"] >= 150) | (out["z_score"] >= 2))
        out["iphone_model"] = "All models"
    else:
        out = df.sort_values("feedback_date")[
            ["feedback_date", "iphone_model", "daily_volume", "curr_3d_avg", "base_14d_avg", "growth_rate_pct", "z_score", "is_anomaly"]
        ]
    return envelope(out, f, issue=issue, model=model or "All models")


@router.get("/heatmap")
def heatmap(f: Filters = Depends(get_filters)):
    """issue x date grid of z-scores (max across models) for the overview strip."""
    df = _load(f)
    g = df.groupby(["issue_category", "feedback_date"])["z_score"].max().reset_index()
    dates = sorted(g["feedback_date"].unique())
    rows = []
    for issue, grp in g.groupby("issue_category"):
        s = grp.set_index("feedback_date")["z_score"].reindex(dates)
        rows.append({"issue_category": issue, "z": [None if pd.isna(v) else float(v) for v in s],
                     "alerts": int((s >= 2).sum())})
    rows.sort(key=lambda r: -r["alerts"])
    return envelope(rows, f, dates=[d.strftime("%Y-%m-%d") for d in dates])
