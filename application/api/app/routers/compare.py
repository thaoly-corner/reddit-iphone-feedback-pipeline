"""BR08 - iPhone model / iOS version comparison (gold_model_comparison)."""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, Query

from ..canonical import OTHER_IOS, OTHER_MODEL, ios_major, model_sort_key
from ..db import query_df
from ..filters import Filters, add_canonical, envelope, get_filters

router = APIRouter(prefix="/compare", tags=["BR08 compare"])


def _load(f: Filters, include_general: bool = True) -> pd.DataFrame:
    where, params = f.where({"feature_category"})
    if not include_general:
        where = (where + " AND " if where else " WHERE ") + "feature_category <> 'General Discussion'"
    df = query_df(
        """SELECT iphone_model, ios_version, feature_category, total_feedback, avg_sentiment,
                  defect_complaint_rate_pct, avg_engagement FROM gold_model_comparison""" + where, params, f.stats,
    )
    df = add_canonical(df)
    df["ios_major"] = df["ios_version"].map(ios_major)
    df["neg"] = df["defect_complaint_rate_pct"] * df["total_feedback"] / 100
    df["w_sent"] = df["avg_sentiment"] * df["total_feedback"]
    df["w_eng"] = df["avg_engagement"] * df["total_feedback"]
    return df


def _agg(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    g = df.groupby(keys).agg(
        total_feedback=("total_feedback", "sum"), neg=("neg", "sum"), w_sent=("w_sent", "sum"), w_eng=("w_eng", "sum"),
    ).reset_index()
    g["avg_sentiment"] = (g["w_sent"] / g["total_feedback"]).round(4)
    g["negative_rate_pct"] = (g["neg"] / g["total_feedback"] * 100).round(2)
    g["avg_engagement"] = (g["w_eng"] / g["total_feedback"]).round(2)
    g["negative_count"] = g["neg"].round().astype(int)
    return g.drop(columns=["neg", "w_sent", "w_eng"])


def _shape(df: pd.DataFrame, key: str, selected: list[str]) -> dict:
    overall = _agg(df, [key])
    by_feature = _agg(df, [key, "feature_category"])
    features = sorted(by_feature["feature_category"].unique())
    entities = []
    for name in selected:
        o = overall[overall[key] == name]
        if o.empty:
            entities.append({"name": name, "total_feedback": 0, "features": []})
            continue
        o = o.iloc[0]
        fb = by_feature[by_feature[key] == name].set_index("feature_category").reindex(features)
        entities.append({
            "name": name, "total_feedback": int(o["total_feedback"]), "avg_sentiment": float(o["avg_sentiment"]),
            "negative_rate_pct": float(o["negative_rate_pct"]), "avg_engagement": float(o["avg_engagement"]),
            "features": [
                {
                    "feature_category": feat,
                    "total_feedback": 0 if pd.isna(r["total_feedback"]) else int(r["total_feedback"]),
                    "share_pct": 0.0 if pd.isna(r["total_feedback"]) else round(float(r["total_feedback"]) / float(o["total_feedback"]) * 100, 2),
                    "avg_sentiment": None if pd.isna(r["avg_sentiment"]) else float(r["avg_sentiment"]),
                    "negative_rate_pct": None if pd.isna(r["negative_rate_pct"]) else float(r["negative_rate_pct"]),
                    "avg_engagement": None if pd.isna(r["avg_engagement"]) else float(r["avg_engagement"]),
                }
                for feat, r in fb.iterrows()
            ],
        })
    return {"features": features, "entities": entities}


@router.get("/options")
def options(f: Filters = Depends(get_filters), min_feedback: int = Query(40, ge=1), include_general: bool = Query(True)):
    df = _load(f, include_general)
    m = _agg(df, ["iphone_model"])
    m = m[(m["iphone_model"] != OTHER_MODEL) & (m["total_feedback"] >= min_feedback)]
    m = m.iloc[sorted(range(len(m)), key=lambda i: model_sort_key(m.iloc[i]["iphone_model"]))]
    o = _agg(df, ["ios_major"])
    o = o[(o["ios_major"] != OTHER_IOS) & (o["total_feedback"] >= 10)].sort_values("ios_major")
    return envelope(
        [], f, models=m.to_dict(orient="records"), ios_majors=o.to_dict(orient="records"),
    )


@router.get("/models")
def models(models: str = Query(..., description="comma-separated canonical model names, 2-4"), f: Filters = Depends(get_filters), include_general: bool = Query(True)):
    selected = [m.strip() for m in models.split(",") if m.strip()][:4]
    df = _load(f, include_general)
    return envelope([_shape(df, "iphone_model", selected)], f)


@router.get("/ios")
def ios(versions: str = Query(..., description="comma-separated iOS majors, e.g. 'iOS 18,iOS 26'"), f: Filters = Depends(get_filters), include_general: bool = Query(True)):
    selected = [v.strip() for v in versions.split(",") if v.strip()][:4]
    df = _load(f, include_general)
    return envelope([_shape(df, "ios_major", selected)], f)


@router.get("/generations")
def generations(f: Filters = Depends(get_filters), min_feedback: int = Query(40, ge=1), include_general: bool = Query(True)):
    """One row per model for the overview scatter: volume vs negative rate, bubble = engagement."""
    df = _load(f, include_general)
    m = _agg(df, ["iphone_model"])
    m = m[(m["iphone_model"] != OTHER_MODEL) & (m["total_feedback"] >= min_feedback)]
    m = m.iloc[sorted(range(len(m)), key=lambda i: model_sort_key(m.iloc[i]["iphone_model"]))]
    return envelope(m, f)
