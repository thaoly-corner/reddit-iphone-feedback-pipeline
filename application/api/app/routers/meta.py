"""Filter vocabularies, freshness and cache control."""
from __future__ import annotations

from fastapi import APIRouter

from ..canonical import OTHER_IOS, OTHER_MODEL, ios_major, model_sort_key
from ..db import cache, query_df
from ..filters import reset_variant_cache, variants

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/filters")
def filter_vocabulary():
    rng = query_df("SELECT MIN(feedback_date) AS min_date, MAX(feedback_date) AS max_date FROM gold_feedback_volume")
    models_df = query_df("SELECT iphone_model, SUM(post_count) AS n FROM gold_sentiment_summary GROUP BY iphone_model")
    from ..canonical import canonical_model
    models_df["iphone_model"] = models_df["iphone_model"].map(canonical_model)
    models = models_df.groupby("iphone_model")["n"].sum().reset_index()
    models = models[models["iphone_model"] != OTHER_MODEL]
    models = sorted(models.itertuples(index=False), key=lambda r: model_sort_key(r.iphone_model))
    ios_df = query_df("SELECT ios_version, SUM(total_feedback) AS n FROM gold_model_comparison GROUP BY ios_version")
    from ..canonical import canonical_ios
    ios_df["ios_version"] = ios_df["ios_version"].map(canonical_ios)
    ios = ios_df.groupby("ios_version")["n"].sum().reset_index()
    ios = ios[ios["ios_version"] != OTHER_IOS]
    ios["major"] = ios["ios_version"].map(ios_major)
    majors = ios.groupby("major")["n"].sum().reset_index().sort_values("major")
    taxonomy = query_df(
        "SELECT feature_category, issue_category, mention_count FROM gold_feature_feedback ORDER BY feature_category, issue_category"
    )
    features: dict[str, list[dict]] = {}
    for r in taxonomy.itertuples(index=False):
        features.setdefault(r.feature_category, []).append({"issue": r.issue_category, "mentions": int(r.mention_count)})
    support = query_df("SELECT DISTINCT support_category FROM gold_support_demand ORDER BY 1")
    return {
        "data": {
            "date_range": {"min": str(rng.iloc[0, 0]), "max": str(rng.iloc[0, 1])},
            "models": [{"name": r.iphone_model, "posts": int(r.n)} for r in models],
            "ios_versions": sorted(
                [{"name": r.ios_version, "posts": int(r.n), "major": r.major} for r in ios.itertuples(index=False)],
                key=lambda d: d["name"],
            ),
            "ios_majors": [{"name": r.major, "posts": int(r.n)} for r in majors.itertuples(index=False)],
            "features": [{"name": k, "issues": v} for k, v in features.items()],
            "support_categories": support["support_category"].tolist(),
        }
    }


@router.get("/freshness")
def freshness():
    tables = [
        "gold_feedback_volume", "gold_issue_summary", "gold_emerging_issues", "gold_sentiment_summary",
        "gold_feature_feedback", "gold_high_impact_complaints", "gold_issue_trends", "gold_model_comparison",
        "gold_recurring_issues", "gold_support_demand",
    ]
    sql = " UNION ALL ".join(f"SELECT '{t}' AS t, COUNT(*) AS n FROM \"{t}\"" for t in tables)  # fixed allowlist, never user input
    counts = {r.t: int(r.n) for r in query_df(sql).itertuples(index=False)}
    latest = query_df("SELECT MAX(feedback_date) AS d FROM gold_feedback_volume")["d"].iloc[0]
    latest_alert = query_df("SELECT MAX(feedback_date) AS d FROM gold_emerging_issues WHERE is_anomaly")["d"].iloc[0]
    return {"data": {"latest_feedback_date": str(latest), "latest_alert_date": str(latest_alert), "row_counts": counts}}


@router.post("/refresh")
def refresh():
    cache.clear()
    reset_variant_cache()
    return {"data": {"cleared": True}}


@router.get("/variants")
def canonical_variants():
    """Exposes how raw Silver labels are folded, for the Data & Pipeline page."""
    return {"data": {"models": variants("model"), "ios": variants("ios")}}
