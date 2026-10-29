"""BR04 - Customer sentiment analysis (gold_sentiment_summary, gold_issue_summary)."""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, Query

from ..canonical import NON_DEFECT, OTHER_MODEL, model_sort_key
from ..db import query_df
from ..filters import Filters, add_canonical, envelope, get_filters

router = APIRouter(prefix="/sentiment", tags=["BR04 sentiment"])
SENTS = ["POSITIVE", "NEUTRAL", "NEGATIVE"]


def _pivot(df: pd.DataFrame, key: str) -> pd.DataFrame:
    p = df.pivot_table(index=key, columns="sentiment", values="post_count", aggfunc="sum", fill_value=0)
    for s in SENTS:
        if s not in p.columns:
            p[s] = 0
    p = p[SENTS].reset_index()
    p.columns = [key, "positive", "neutral", "negative"]
    p["total"] = p[["positive", "neutral", "negative"]].sum(axis=1)
    p["net_sentiment_pct"] = ((p["positive"] - p["negative"]) / p["total"] * 100).round(2)
    p["negative_pct"] = (p["negative"] / p["total"] * 100).round(2)
    p["positive_pct"] = (p["positive"] / p["total"] * 100).round(2)
    return p


def _from_sentiment_summary(f: Filters) -> pd.DataFrame:
    where, params = f.where({"feedback_date", "iphone_model"})
    df = query_df(
        f"""SELECT feedback_date, iphone_model, sentiment, post_count, mean_sentiment_score
            FROM gold_sentiment_summary{where}""", params, f.stats,
    )
    df["feedback_date"] = pd.to_datetime(df["feedback_date"])
    return add_canonical(df)


def _from_issue_summary(f: Filters) -> pd.DataFrame:
    where, params = f.where({"feedback_date", "iphone_model", "ios_version", "feature_category", "issue_category"})
    df = query_df(
        f"""SELECT feedback_date, iphone_model, ios_version, feature_category, issue_category,
                   positive_count, neutral_count, negative_count, avg_sentiment_score, total_posts
            FROM gold_issue_summary{where}""", params, f.stats,
    )
    df["feedback_date"] = pd.to_datetime(df["feedback_date"])
    return add_canonical(df)


def _long(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """issue_summary wide counts -> long (sentiment, post_count)."""
    parts = []
    for s, c in (("POSITIVE", "positive_count"), ("NEUTRAL", "neutral_count"), ("NEGATIVE", "negative_count")):
        p = df[keys + [c]].rename(columns={c: "post_count"})
        p["sentiment"] = s
        parts.append(p)
    return pd.concat(parts, ignore_index=True)


@router.get("/timeline")
def timeline(f: Filters = Depends(get_filters), granularity: str = Query("day", pattern="^(day|week)$")):
    sliced = any([f.ios, f.feature, f.issue, not f.include_non_defect])
    if sliced:
        df = _long(_from_issue_summary(f), ["feedback_date"])
        source = "gold_issue_summary"
    else:
        df = _from_sentiment_summary(f)
        source = "gold_sentiment_summary"
    if df.empty:
        return envelope([], f, source=source)
    if granularity == "week":
        df["feedback_date"] = df["feedback_date"] - pd.to_timedelta(df["feedback_date"].dt.weekday, unit="D")
    p = _pivot(df, "feedback_date").sort_values("feedback_date")
    p["net_7d"] = p["net_sentiment_pct"].rolling(7 if granularity == "day" else 1, min_periods=1).mean().round(2)
    overall = {
        "positive": int(p["positive"].sum()), "neutral": int(p["neutral"].sum()), "negative": int(p["negative"].sum()),
    }
    tot = sum(overall.values())
    overall["net_sentiment_pct"] = round((overall["positive"] - overall["negative"]) / tot * 100, 2) if tot else None
    overall["negative_pct"] = round(overall["negative"] / tot * 100, 2) if tot else None
    return envelope(p, f, source=source, overall=overall, granularity=granularity)


@router.get("/by-issue")
def by_issue(f: Filters = Depends(get_filters), include_general: bool = Query(True)):
    df = _from_issue_summary(f)
    if not include_general:
        df = df[df["issue_category"] != NON_DEFECT]
    if df.empty:
        return envelope([], f)
    df["w"] = df["avg_sentiment_score"] * df["total_posts"]
    long = _long(df, ["feature_category", "issue_category"])
    p = _pivot(long.assign(key=long["feature_category"] + "||" + long["issue_category"]), "key")
    p[["feature_category", "issue_category"]] = p["key"].str.split(r"\|\|", expand=True, regex=True)
    mean = df.groupby(["feature_category", "issue_category"]).apply(lambda g: g["w"].sum() / g["total_posts"].sum(), include_groups=False)
    p["mean_sentiment_score"] = p.apply(lambda r: round(float(mean.loc[(r["feature_category"], r["issue_category"])]), 4), axis=1)
    p = p.drop(columns=["key"]).sort_values("total", ascending=False)
    return envelope(p, f)


@router.get("/by-model")
def by_model(f: Filters = Depends(get_filters), min_posts: int = Query(30, ge=1), include_unspecified: bool = Query(False)):
    sliced = any([f.ios, f.feature, f.issue, not f.include_non_defect])
    if sliced:
        df = _long(_from_issue_summary(f), ["iphone_model"])
    else:
        df = _from_sentiment_summary(f)
    if df.empty:
        return envelope([], f)
    p = _pivot(df, "iphone_model")
    if "mean_sentiment_score" in df.columns:
        w = df.assign(w=df["mean_sentiment_score"] * df["post_count"]).groupby("iphone_model").agg(w=("w", "sum"), n=("post_count", "sum"))
        p["mean_sentiment_score"] = p["iphone_model"].map((w["w"] / w["n"]).round(4))
    p = p[p["total"] >= min_posts]
    if not include_unspecified:
        p = p[p["iphone_model"] != OTHER_MODEL]
    p = p.iloc[sorted(range(len(p)), key=lambda i: model_sort_key(p.iloc[i]["iphone_model"]))]
    return envelope(p, f, min_posts=min_posts)
