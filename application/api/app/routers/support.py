"""BR09 - Recurring issues (gold_recurring_issues) and BR10 - Support demand (gold_support_demand)."""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, Query

from ..canonical import OTHER_MODEL, model_sort_key
from ..db import query_df
from ..filters import Filters, add_canonical, envelope, get_filters

router = APIRouter(tags=["BR09 recurring", "BR10 support"])


@router.get("/recurring")
def recurring(f: Filters = Depends(get_filters)):
    where, params = f.where({"issue_category"})
    df = query_df(
        f"""SELECT issue_category, feedback_year, feedback_month, issue_count, active_period_count,
                   recurrence_count, is_recurring FROM gold_recurring_issues{where}
            ORDER BY issue_category, feedback_year, feedback_month""", params, f.stats,
    )
    if df.empty:
        return envelope([], f)
    df["period"] = df["feedback_year"].astype(str) + "-" + df["feedback_month"].astype(str).str.zfill(2)
    periods = sorted(df["period"].unique())
    rows = []
    for issue, grp in df.groupby("issue_category"):
        s = grp.set_index("period")["issue_count"].reindex(periods)
        counts = [None if pd.isna(v) else int(v) for v in s]
        present = [c for c in counts if c is not None]
        rows.append({
            "issue_category": issue, "counts": counts, "total": int(sum(present)),
            "active_period_count": int(grp["active_period_count"].iloc[0]),
            "recurrence_count": int(grp["recurrence_count"].iloc[0]),
            "is_recurring": bool(grp["is_recurring"].iloc[0]),
            "mean_per_period": round(sum(present) / len(present), 1) if present else None,
            "max_period": periods[counts.index(max(present))] if present else None,
            "volatility_pct": round(float(pd.Series(present).std(ddof=0) / (sum(present) / len(present)) * 100), 1) if len(present) > 1 and sum(present) else None,
        })
    rows.sort(key=lambda r: -r["total"])
    return envelope(rows, f, periods=periods)


@router.get("/support/demand")
def support_demand(f: Filters = Depends(get_filters), top_models: int = Query(8, ge=1, le=20)):
    where, params = f.where({"iphone_model", "ios_version"})
    df = query_df(
        f"""SELECT support_category, feedback_year, feedback_month, iphone_model, ios_version, question_count,
                   avg_sentiment_score, avg_reddit_score, avg_num_comments, avg_engagement_score
            FROM gold_support_demand{where}""", params, f.stats,
    )
    if df.empty:
        return envelope([], f)
    df = add_canonical(df)
    df["period"] = df["feedback_year"].astype(str) + "-" + df["feedback_month"].astype(str).str.zfill(2)
    df["w_sent"] = df["avg_sentiment_score"].fillna(0) * df["question_count"]
    df["w_eng"] = df["avg_engagement_score"].fillna(0) * df["question_count"]
    periods = sorted(df["period"].unique())
    total_q = int(df["question_count"].sum())

    def agg(keys):
        g = df.groupby(keys).agg(question_count=("question_count", "sum"), w_sent=("w_sent", "sum"), w_eng=("w_eng", "sum")).reset_index()
        g["avg_sentiment_score"] = (g["w_sent"] / g["question_count"]).round(4)
        g["avg_engagement_score"] = (g["w_eng"] / g["question_count"]).round(2)
        return g.drop(columns=["w_sent", "w_eng"])

    cat = agg(["support_category"]).sort_values("question_count", ascending=False)
    cat["share_pct"] = (cat["question_count"] / total_q * 100).round(2)
    cat_period = agg(["support_category", "period"])
    cats = []
    for c in cat.itertuples(index=False):
        s = cat_period[cat_period["support_category"] == c.support_category].set_index("period")["question_count"].reindex(periods, fill_value=0)
        vals = [int(v) for v in s]
        cats.append({
            "support_category": c.support_category, "question_count": int(c.question_count), "share_pct": float(c.share_pct),
            "avg_sentiment_score": float(c.avg_sentiment_score), "avg_engagement_score": float(c.avg_engagement_score),
            "by_period": vals, "period_delta_pct": round((vals[-1] - vals[-2]) / vals[-2] * 100, 1) if len(vals) >= 2 and vals[-2] else None,
        })
    m = agg(["iphone_model"])
    m = m[m["iphone_model"] != OTHER_MODEL].nlargest(top_models, "question_count")
    m = m.iloc[sorted(range(len(m)), key=lambda i: model_sort_key(m.iloc[i]["iphone_model"]))]
    mc = agg(["iphone_model", "support_category"])
    model_rows = []
    for r in m.itertuples(index=False):
        sub = mc[mc["iphone_model"] == r.iphone_model].sort_values("question_count", ascending=False)
        model_rows.append({
            "iphone_model": r.iphone_model, "question_count": int(r.question_count),
            "top_category": sub.iloc[0]["support_category"] if not sub.empty else None,
            "categories": {row.support_category: int(row.question_count) for row in sub.itertuples(index=False)},
        })
    per = agg(["period"]).set_index("period").reindex(periods, fill_value=0)
    return envelope(
        cats, f, periods=periods, total_questions=total_q,
        by_period=[int(v) for v in per["question_count"]], by_model=model_rows,
        unspecified_model_questions=int(df.loc[df["iphone_model"] == OTHER_MODEL, "question_count"].sum()),
    )
