"""
Alternative Batch Gold Engine 2 ('duckdb_biglake'):
DuckDB Serverless SQL Engine (BigLake Paradigm) over Silver Parquet partitions.
"""
from pathlib import Path
import pandas as pd

from config.pipeline_config import StorageConfig


def build_gold_issue_summary_duckdb(storage_cfg: StorageConfig) -> pd.DataFrame:
    """
    Xay dung bang Gold `issue_summary` bang DuckDB Serverless Engine (BigLake Paradigm)
    khi PipelineExecutionConfig.batch_gold_engine == 'duckdb_biglake'.
    """
    import duckdb
    con = duckdb.connect()
    silver_glob = f"{storage_cfg.silver_posts_path}/**/*.parquet"
    pdf = con.execute(f"""
        SELECT
            CAST(feedback_date AS DATE) AS feedback_date,
            iphone_model,
            ios_version,
            feature_category,
            issue_category,
            COUNT(post_id) AS total_posts,
            SUM(num_comments) AS total_comments,
            SUM(CASE WHEN sentiment = 'POSITIVE' THEN 1 ELSE 0 END) AS positive_count,
            SUM(CASE WHEN sentiment = 'NEUTRAL' THEN 1 ELSE 0 END) AS neutral_count,
            SUM(CASE WHEN sentiment = 'NEGATIVE' THEN 1 ELSE 0 END) AS negative_count,
            ROUND(AVG(sentiment_score), 4) AS avg_sentiment_score,
            ROUND(AVG(engagement_score), 2) AS avg_engagement_score
        FROM read_parquet('{silver_glob}')
        GROUP BY feedback_date, iphone_model, ios_version, feature_category, issue_category
    """).df()
    con.close()

    out_dir = Path(f"{storage_cfg.gold_base_path}/issue_summary")
    out_dir.mkdir(parents=True, exist_ok=True)
    for old_f in out_dir.glob("*.parquet"):
        old_f.unlink()
    pdf.to_parquet(out_dir / "part-00000-duckdb.parquet", index=False, compression="snappy")
    return pdf
