"""BR01 - Customer feedback volume monitoring (gold_feedback_volume, gold_issue_summary when sliced)."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd
from fastapi import APIRouter, Depends, Query

from ..db import query_df
from ..filters import Filters, envelope, get_filters

router = APIRouter(prefix="/volume", tags=["BR01 volume"])

VOLUME_COLS = {"feedback_date"}
SUMMARY_COLS = {"feedback_date", "iphone_model", "ios_version", "feature_category", "issue_category"}


def _is_sliced(f: Filters) -> bool:
    return any([f.model, f.ios, f.feature, f.issue, not f.include_non_defect])


def _daily(f: Filters) -> tuple[pd.DataFrame, str]:
    """Daily volume. Uses the BR01 mart unless entity filters force a slice of gold_issue_summary."""
    if _is_sliced(f):
        where, params = f.where(SUMMARY_COLS)
        df = query_df(
            f"""SELECT feedback_date, SUM(total_posts) AS total_posts, SUM(total_comments) AS total_comments,
                       SUM(total_posts + total_comments) AS total_discussion_units,
                       SUM(avg_engagement_score * total_posts) / NULLIF(SUM(total_posts), 0) AS avg_engagement_score
                FROM gold_issue_summary{where} GROUP BY feedback_date ORDER BY feedback_date""",
            params, f.stats,
        )
        return df, "gold_issue_summary"
    where, params = f.where(VOLUME_COLS)
    df = query_df(
        f"""SELECT feedback_date, feedback_week, SUM(total_posts) AS total_posts, SUM(total_comments) AS total_comments,
                   SUM(total_discussion_units) AS total_discussion_units,
                   SUM(avg_engagement_score * total_posts) / NULLIF(SUM(total_posts), 0) AS avg_engagement_score
            FROM gold_feedback_volume{where} GROUP BY feedback_date, feedback_week ORDER BY feedback_date""",
        params, f.stats,
    )
    return df, "gold_feedback_volume"


@router.get("/daily")
def daily(f: Filters = Depends(get_filters)):
    df, source = _daily(f)
    df["feedback_date"] = pd.to_datetime(df["feedback_date"])
    df["rolling_7d_posts"] = df["total_posts"].rolling(7, min_periods=1).mean().round(1)
    df["avg_engagement_score"] = df["avg_engagement_score"].astype(float).round(2)
    return envelope(df, f, source=source)


@router.get("/weekly")
def weekly(f: Filters = Depends(get_filters)):
    df, source = _daily(f)
    df["feedback_date"] = pd.to_datetime(df["feedback_date"])
    df["week_start"] = df["feedback_date"] - pd.to_timedelta(df["feedback_date"].dt.weekday, unit="D")
    g = df.groupby("week_start").agg(
        total_posts=("total_posts", "sum"), total_comments=("total_comments", "sum"),
        total_discussion_units=("total_discussion_units", "sum"), days=("feedback_date", "count"),
    ).reset_index()
    g["prev_week_posts"] = g["total_posts"].shift(1)
    g["wow_growth_pct"] = ((g["total_posts"] - g["prev_week_posts"]) / g["prev_week_posts"] * 100).round(2)
    g["is_partial"] = g["days"] < 7
    return envelope(g, f, source=source)


@router.get("/summary")
def summary(f: Filters = Depends(get_filters)):
    """KPIs for the selected range plus delta against the preceding window of equal length."""
    cur, source = _daily(f)
    cur["feedback_date"] = pd.to_datetime(cur["feedback_date"])
    if cur.empty:
        return envelope([], f, source=source)
    start, end = cur["feedback_date"].min(), cur["feedback_date"].max()
    span = (end - start).days + 1
    prev_f = Filters(
        (start - timedelta(days=span)).date(), (start - timedelta(days=1)).date(),
        f.model, f.ios, f.feature, f.issue, f.include_non_defect, f.stats,
    )
    prev, _ = _daily(prev_f)

    def kpis(d: pd.DataFrame) -> dict:
        if d.empty:
            return {"posts": 0, "comments": 0, "discussion_units": 0, "avg_engagement": None, "days": 0, "posts_per_day": 0}
        posts = int(d["total_posts"].sum())
        return {
            "posts": posts, "comments": int(d["total_comments"].sum()),
            "discussion_units": int(d["total_discussion_units"].sum()),
            "avg_engagement": round(float((d["avg_engagement_score"].astype(float) * d["total_posts"]).sum() / posts), 2) if posts else None,
            "days": int(len(d)), "posts_per_day": round(posts / len(d), 1),
        }

    c, p = kpis(cur), kpis(prev)

    def delta(k):
        if not p.get(k) or c.get(k) is None:
            return None
        return round((c[k] - p[k]) / p[k] * 100, 1)

    peak = cur.loc[cur["total_discussion_units"].idxmax()]
    return envelope(
        [{
            "current": c, "previous": p,
            "delta_pct": {k: delta(k) for k in ("posts", "comments", "discussion_units", "avg_engagement", "posts_per_day")},
            "range": {"from": start.strftime("%Y-%m-%d"), "to": end.strftime("%Y-%m-%d"), "days": span},
            "peak_day": {"date": peak["feedback_date"].strftime("%Y-%m-%d"), "discussion_units": int(peak["total_discussion_units"])},
        }],
        f, source=source,
    )


@router.get("/peaks")
def peaks(f: Filters = Depends(get_filters), limit: int = Query(8, ge=1, le=31)):
    """Days with the most discussion, each with the highest-engagement negative post of that day."""
    df, source = _daily(f)
    top = df.nlargest(limit, "total_discussion_units").copy()
    top["feedback_date"] = pd.to_datetime(top["feedback_date"])
    where, params = f.where({"feedback_date", "iphone_model", "ios_version", "feature_category", "issue_category"})
    posts = query_df(
        f"""SELECT feedback_date, title, permalink, issue_category, iphone_model, engagement_score
            FROM gold_high_impact_complaints{where} ORDER BY engagement_score DESC""", params, f.stats,
    )
    posts["feedback_date"] = pd.to_datetime(posts["feedback_date"])
    best = posts.drop_duplicates("feedback_date").set_index("feedback_date")
    rows = []
    for r in top.itertuples(index=False):
        b = best.loc[r.feedback_date] if r.feedback_date in best.index else None
        rows.append({
            "feedback_date": r.feedback_date.strftime("%Y-%m-%d"), "total_posts": int(r.total_posts),
            "total_comments": int(r.total_comments), "total_discussion_units": int(r.total_discussion_units),
            "weekday": r.feedback_date.strftime("%a"),
            "top_post": None if b is None else {
                "title": b["title"], "permalink": b["permalink"], "issue_category": b["issue_category"],
                "engagement_score": int(b["engagement_score"]),
            },
        })
    return envelope(rows, f, source=source)
