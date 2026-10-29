"""BR02 - Product issue identification and BR07 - Issue trend monitoring."""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, Query

from ..canonical import NON_DEFECT, ios_major, model_sort_key
from ..db import query_df
from ..filters import Filters, add_canonical, envelope, get_filters

router = APIRouter(prefix="/issues", tags=["BR02 issues", "BR07 trends"])
SUMMARY_COLS = {"feedback_date", "iphone_model", "ios_version", "feature_category", "issue_category"}


def _summary(f: Filters, extra_cols: str = "") -> pd.DataFrame:
    where, params = f.where(SUMMARY_COLS)
    return query_df(
        f"""SELECT feedback_date, iphone_model, ios_version, feature_category, issue_category,
                   total_posts, total_comments, positive_count, neutral_count, negative_count,
                   avg_sentiment_score, avg_engagement_score
            FROM gold_issue_summary{where}""", params, f.stats,
    )


def _agg(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    df = df.copy()
    df["w_sent"] = df["avg_sentiment_score"] * df["total_posts"]
    df["w_eng"] = df["avg_engagement_score"] * df["total_posts"]
    g = df.groupby(keys).agg(
        total_posts=("total_posts", "sum"), total_comments=("total_comments", "sum"),
        positive_count=("positive_count", "sum"), neutral_count=("neutral_count", "sum"),
        negative_count=("negative_count", "sum"), w_sent=("w_sent", "sum"), w_eng=("w_eng", "sum"),
    ).reset_index()
    g["avg_sentiment_score"] = (g["w_sent"] / g["total_posts"]).round(4)
    g["avg_engagement_score"] = (g["w_eng"] / g["total_posts"]).round(2)
    g["negative_ratio_pct"] = (g["negative_count"] / g["total_posts"] * 100).round(2)
    return g.drop(columns=["w_sent", "w_eng"])


@router.get("/ranking")
def ranking(f: Filters = Depends(get_filters), include_general: bool = Query(False)):
    """Issues ranked by mentions with share of all feedback, sentiment mix, engagement and a weekly sparkline."""
    df = _summary(f)
    if df.empty:
        return envelope([], f)
    total_all = int(df["total_posts"].sum())
    defect_total = int(df.loc[df["issue_category"] != NON_DEFECT, "total_posts"].sum())
    if not include_general:
        df = df[df["issue_category"] != NON_DEFECT]
    rank = _agg(df, ["feature_category", "issue_category"])
    rank["share_of_all_pct"] = (rank["total_posts"] / total_all * 100).round(2)
    rank["share_of_defects_pct"] = (rank["total_posts"] / max(defect_total, 1) * 100).round(2)
    rank = rank.sort_values("total_posts", ascending=False)
    rank["rank"] = range(1, len(rank) + 1)

    df["feedback_date"] = pd.to_datetime(df["feedback_date"])
    df["week_start"] = df["feedback_date"] - pd.to_timedelta(df["feedback_date"].dt.weekday, unit="D")
    weekly = df.groupby(["issue_category", "week_start"])["total_posts"].sum().reset_index()
    weeks = sorted(weekly["week_start"].unique())
    spark = {
        issue: [int(x) for x in grp.set_index("week_start")["total_posts"].reindex(weeks, fill_value=0)]
        for issue, grp in weekly.groupby("issue_category")
    }
    rows = []
    for r in rank.to_dict(orient="records"):
        s = spark.get(r["issue_category"], [])
        r["weekly"] = s
        r["last_week_delta_pct"] = round((s[-1] - s[-2]) / s[-2] * 100, 1) if len(s) >= 2 and s[-2] else None
        rows.append(r)
    return envelope(rows, f, total_feedback=total_all, defect_feedback=defect_total,
                    weeks=[w.strftime("%Y-%m-%d") for w in weeks])


@router.get("/trends")
def trends(f: Filters = Depends(get_filters), include_general: bool = Query(False)):
    """BR07: weekly volume and week-over-week growth straight from gold_issue_trends."""
    where, params = f.where({"week_start", "feature_category", "issue_category"}, date_col="week_start")
    df = query_df(
        f"""SELECT week_start, feature_category, issue_category, weekly_volume, prev_week_volume, wow_growth_pct
            FROM gold_issue_trends{where} ORDER BY week_start, issue_category""", params, f.stats,
    )
    if not include_general:
        df = df[df["issue_category"] != NON_DEFECT]
    df["week_start"] = pd.to_datetime(df["week_start"])
    # month-over-month style slope: linear regression of weekly_volume per issue
    slopes = {}
    for issue, grp in df.groupby("issue_category"):
        y = grp["weekly_volume"].astype(float).values
        if len(y) >= 3:
            x = pd.Series(range(len(y)))
            slopes[issue] = round(float(((x - x.mean()) * (y - y.mean())).sum() / ((x - x.mean()) ** 2).sum()), 3)
        else:
            slopes[issue] = None
    weeks = sorted(df["week_start"].unique())
    # week with full 7 days? dataset starts Mon 2026-04-27 and ends Fri 2026-07-31 -> flag partial edges
    series = []
    for issue, grp in df.groupby("issue_category"):
        s = grp.set_index("week_start").reindex(weeks)
        series.append({
            "issue_category": issue, "feature_category": grp["feature_category"].iloc[0],
            "weekly_volume": [None if pd.isna(v) else int(v) for v in s["weekly_volume"]],
            "wow_growth_pct": [None if pd.isna(v) else float(v) for v in s["wow_growth_pct"]],
            "total": int(grp["weekly_volume"].sum()), "slope_per_week": slopes[issue],
            "latest_wow_pct": None if pd.isna(grp["wow_growth_pct"].iloc[-1]) else float(grp["wow_growth_pct"].iloc[-1]),
        })
    series.sort(key=lambda d: -d["total"])
    return envelope(series, f, weeks=[w.strftime("%Y-%m-%d") for w in weeks])


@router.get("/detail")
def detail(f: Filters = Depends(get_filters)):
    """Drill-down for one issue (`issue` filter required): daily series, breakdown by model and by iOS major."""
    if not f.issue:
        return envelope([], f, error="issue query parameter is required")
    issue = f.issue
    df = add_canonical(_summary(f))
    if df.empty:
        return envelope([], f)
    daily = _agg(df, ["feedback_date"]).sort_values("feedback_date")
    daily["feedback_date"] = pd.to_datetime(daily["feedback_date"]).dt.strftime("%Y-%m-%d")
    by_model = _agg(df, ["iphone_model"]).sort_values("total_posts", ascending=False)
    by_model = by_model.head(12)
    by_model = by_model.iloc[sorted(range(len(by_model)), key=lambda i: model_sort_key(by_model.iloc[i]["iphone_model"]))]
    df["ios_major"] = df["ios_version"].map(ios_major)
    by_ios = _agg(df, ["ios_major"]).sort_values("total_posts", ascending=False)
    total = _agg(df.assign(k=1), ["k"]).iloc[0]
    return envelope(
        [{
            "issue_category": issue, "feature_category": df["feature_category"].iloc[0],
            "totals": {k: (float(v) if isinstance(v, float) else int(v)) for k, v in total.drop("k").items()},
            "daily": daily.to_dict(orient="records"),
            "by_model": by_model.to_dict(orient="records"),
            "by_ios": by_ios.to_dict(orient="records"),
        }], f,
    )
