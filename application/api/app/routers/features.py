"""BR05 - Feature-level feedback analysis (gold_feature_feedback; sliced via gold_issue_summary)."""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, Query

from ..canonical import NON_DEFECT
from ..db import query_df
from ..filters import Filters, envelope, get_filters

router = APIRouter(prefix="/features", tags=["BR05 features"])


def _matrix(f: Filters) -> tuple[pd.DataFrame, str]:
    sliced = any([f.date_from, f.date_to, f.model, f.ios])
    if not sliced:
        where, params = f.where({"feature_category", "issue_category"})
        df = query_df(
            f"""SELECT feature_category, issue_category, mention_count, negative_mentions, positive_mentions,
                       negative_ratio_pct, avg_engagement FROM gold_feature_feedback{where}""", params, f.stats,
        )
        return df, "gold_feature_feedback"
    where, params = f.where({"feedback_date", "iphone_model", "ios_version", "feature_category", "issue_category"})
    df = query_df(
        f"""SELECT feature_category, issue_category, SUM(total_posts) AS mention_count,
                   SUM(negative_count) AS negative_mentions, SUM(positive_count) AS positive_mentions,
                   ROUND((SUM(negative_count) * 100.0 / NULLIF(SUM(total_posts), 0))::numeric, 2) AS negative_ratio_pct,
                   ROUND((SUM(avg_engagement_score * total_posts) / NULLIF(SUM(total_posts), 0))::numeric, 2) AS avg_engagement
            FROM gold_issue_summary{where} GROUP BY feature_category, issue_category""", params, f.stats,
    )
    return df, "gold_issue_summary"


@router.get("/matrix")
def matrix(f: Filters = Depends(get_filters), include_general: bool = Query(False)):
    df, source = _matrix(f)
    if not include_general:
        df = df[df["issue_category"] != NON_DEFECT]
    if df.empty:
        return envelope([], f, source=source)
    df = df.astype({"mention_count": int, "negative_mentions": int, "positive_mentions": int})
    df["neutral_mentions"] = df["mention_count"] - df["negative_mentions"] - df["positive_mentions"]
    df["negative_ratio_pct"] = df["negative_ratio_pct"].astype(float)
    df["avg_engagement"] = df["avg_engagement"].astype(float)
    df["complaint_load"] = (df["negative_mentions"] * df["avg_engagement"]).round(1)  # mentions weighted by reach
    total = int(df["mention_count"].sum())
    df["share_pct"] = (df["mention_count"] / total * 100).round(2)
    feat = df.groupby("feature_category").agg(
        mention_count=("mention_count", "sum"), negative_mentions=("negative_mentions", "sum"),
        positive_mentions=("positive_mentions", "sum"), complaint_load=("complaint_load", "sum"),
    ).reset_index()
    feat["negative_ratio_pct"] = (feat["negative_mentions"] / feat["mention_count"] * 100).round(2)
    feat["positive_ratio_pct"] = (feat["positive_mentions"] / feat["mention_count"] * 100).round(2)
    feat = feat.sort_values("mention_count", ascending=False)
    cells = df.sort_values(["feature_category", "mention_count"], ascending=[True, False])
    return envelope(
        cells, f, source=source, features=feat.to_dict(orient="records"), total_mentions=total,
    )
