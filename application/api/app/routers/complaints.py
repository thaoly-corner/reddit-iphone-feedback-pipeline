"""BR06 - High-impact complaint identification (gold_high_impact_complaints)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..db import query_df
from ..filters import Filters, add_canonical, envelope, get_filters

router = APIRouter(prefix="/complaints", tags=["BR06 complaints"])
COLS = {"feedback_date", "iphone_model", "ios_version", "feature_category", "issue_category"}
SORTS = {
    "impact": "impact_index DESC, engagement_score DESC", "engagement": "engagement_score DESC",
    "score": "reddit_score DESC", "comments": "num_comments DESC", "recent": "feedback_date DESC, engagement_score DESC",
    "sentiment": "sentiment_score ASC",
}


@router.get("")
def complaints(
    f: Filters = Depends(get_filters),
    sort: str = Query("impact", pattern="^(impact|engagement|score|comments|recent|sentiment)$"),
    q: str | None = Query(None, max_length=120, description="case-insensitive title search"),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    where, params = f.where(COLS)
    if q:
        where = (where + " AND " if where else " WHERE ") + "title ILIKE :q"
        params["q"] = f"%{q}%"
    total = int(query_df(f"SELECT COUNT(*) AS n FROM gold_high_impact_complaints{where}", params, f.stats)["n"].iloc[0])
    agg = query_df(
        f"""SELECT COALESCE(SUM(engagement_score), 0) AS reach, COALESCE(AVG(impact_index), 0) AS avg_impact,
                   COALESCE(MAX(impact_index), 0) AS max_impact FROM gold_high_impact_complaints{where}""", params, f.stats,
    ).iloc[0]
    df = query_df(
        f"""SELECT post_id, feedback_date, iphone_model, ios_version, feature_category, issue_category, title,
                   permalink, reddit_score, num_comments, engagement_score, impact_index, sentiment_score
            FROM gold_high_impact_complaints{where} ORDER BY {SORTS[sort]} LIMIT :limit OFFSET :offset""",
        {**params, "limit": limit, "offset": offset}, f.stats,
    )
    df = add_canonical(df)
    df["reddit_url"] = "https://www.reddit.com" + df["permalink"]
    by_issue = query_df(
        f"""SELECT issue_category, COUNT(*) AS n, SUM(engagement_score) AS reach
            FROM gold_high_impact_complaints{where} GROUP BY issue_category ORDER BY reach DESC""", params, f.stats,
    )
    return envelope(
        df, f, total=total, limit=limit, offset=offset, sort=sort,
        summary={"reach": int(agg["reach"]), "avg_impact": round(float(agg["avg_impact"]), 3), "max_impact": round(float(agg["max_impact"]), 3)},
        by_issue=[{"issue": r.issue_category, "n": int(r.n), "reach": int(r.reach)} for r in by_issue.itertuples(index=False)],
    )
