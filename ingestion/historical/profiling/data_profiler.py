"""
Module Data Profiling tren tap du lieu Reddit da loc (Overview, Missing rate, Degradation, Distributions).
"""
from pathlib import Path
from typing import Any

import pandas as pd


def profile_filtered_posts(
    jsonl_path: Path | str,
    profile_dir: Path | str | None = None,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Any]:
    """
    Thuc hien phan tich thong ke (Data Profiling) tren tap du lieu da loc:
    - Overview (row_count, column_count, unique_posts, duplicate_ids, unique_authors)
    - Missing rate per column
    - Degradation rate ([deleted], [removed], empty selftext)
    - Numeric distributions & Posts per day

    Khi luu CSV, year va month bat buoc la so nguyen hop le. Bao cao duoc luu
    trong profile_dir/year=YYYY/month=MM/.
    """
    if profile_dir is not None:
        if type(year) is not int or not 1 <= year <= 9999:
            raise ValueError("year must be an integer between 1 and 9999")
        if type(month) is not int or not 1 <= month <= 12:
            raise ValueError("month must be an integer between 1 and 12")

    p_dir = None
    if profile_dir is not None:
        p_dir = Path(profile_dir) / f"year={year:04d}" / f"month={month:02d}"


    jsonl_path = Path(jsonl_path)

    if not jsonl_path.is_file():
        raise FileNotFoundError(
            f"Filtered JSONL not found: {jsonl_path}"
        )

    if jsonl_path.stat().st_size == 0:
        raise ValueError(
            f"Filtered JSONL is empty: {jsonl_path}"
        )
    df_posts = pd.read_json(jsonl_path, lines=True)
    overview = {
        "row_count": len(df_posts),
        "column_count": len(df_posts.columns),
        "unique_posts": int(df_posts["id"].nunique()) if "id" in df_posts.columns else None,
        "duplicate_ids": int(df_posts["id"].duplicated().sum()) if "id" in df_posts.columns else None,
        "unique_authors": int(df_posts["author"].nunique()) if "author" in df_posts.columns else None
    }

    missing_df = pd.DataFrame({
        "column": df_posts.columns,
        "missing_count": [int(df_posts[c].isna().sum()) for c in df_posts.columns],
        "missing_percent": [round(float(df_posts[c].isna().mean() * 100), 2) for c in df_posts.columns]
    }).sort_values("missing_percent", ascending=False)

    degradation_stats = {}
    if "selftext" in df_posts.columns:
        s_col = df_posts["selftext"].fillna("").astype(str)
        degradation_stats = {
            "deleted_count": int(s_col.eq("[deleted]").sum()),
            "removed_count": int(s_col.eq("[removed]").sum()),
            "empty_count": int(s_col.str.strip().eq("").sum()),
            "deleted_percent": round(float(s_col.eq("[deleted]").mean() * 100), 2),
            "removed_percent": round(float(s_col.eq("[removed]").mean() * 100), 2),
            "empty_percent": round(float(s_col.str.strip().eq("").mean() * 100), 2)
        }


    if "created_utc" in df_posts.columns:
        df_posts["created_datetime"] = pd.to_datetime(
            df_posts["created_utc"],
            unit="s",
            utc=True,
            errors="coerce"
        )

        df_posts["date"] = df_posts["created_datetime"].dt.date

        posts_per_day = (
            df_posts.groupby("date")
            .size()
            .reset_index(name="post_count")
        )
    else:
        posts_per_day = pd.DataFrame(
            columns=["date", "post_count"]
        )

    numeric_cols = [c for c in ["score", "num_comments", "upvote_ratio"] if c in df_posts.columns]
    numeric_profile = (
        df_posts[numeric_cols].describe().T
        if numeric_cols
        else pd.DataFrame()
    )

    length_cols = []

    if "title" in df_posts.columns:
        df_posts["title_length"] = (
            df_posts["title"]
            .fillna("")
            .astype(str)
            .str.len()
        )
        length_cols.append("title_length")

    if "selftext" in df_posts.columns:
        df_posts["selftext_length"] = (
            df_posts["selftext"]
            .fillna("")
            .astype(str)
            .str.len()
        )
        length_cols.append("selftext_length")

    length_profile = (
        df_posts[length_cols].describe().T
        if length_cols
        else pd.DataFrame()
    )

    if p_dir is not None:
        p_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([overview]).to_csv(p_dir / "posts_overview.csv", index=False)
        missing_df.to_csv(p_dir / "posts_missing.csv", index=False)
        numeric_profile.reset_index(
            names="metric"
        ).to_csv(
            p_dir / "posts_numeric.csv",
            index=False
        )
        posts_per_day.to_csv(p_dir / "posts_per_day.csv", index=False)
        length_profile.reset_index(
            names="field"
        ).to_csv(
            p_dir / "posts_length.csv",
            index=False
        )
        pd.DataFrame([degradation_stats]).to_csv(
            p_dir / "posts_degradation.csv",
            index=False
        )


    return {
        "overview": overview,
        "missing_df": missing_df,
        "degradation_stats": degradation_stats,
        "numeric_profile": numeric_profile,
        "length_profile": length_profile,
        "posts_per_day": posts_per_day
    }
