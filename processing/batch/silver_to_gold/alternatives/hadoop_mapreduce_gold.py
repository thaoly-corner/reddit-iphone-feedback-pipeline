"""
Alternative Batch Gold Engine 1 ('hadoop_mapreduce'):
Hadoop MapReduce RDD Aggregation for Gold `issue_summary` and Batch Processing Engine Benchmark.
"""
import time
import tracemalloc
from pathlib import Path
from typing import TYPE_CHECKING
import pandas as pd

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

from config.pipeline_config import StorageConfig


def build_gold_issue_summary_mapreduce(spark: 'SparkSession', storage_cfg: StorageConfig) -> pd.DataFrame:
    """
    Xay dung bang Gold `issue_summary` bang mo hinh Hadoop MapReduce (Spark RDD map -> reduceByKey)
    va ghi truc tiep xuong Gold Parquet khi PipelineExecutionConfig.batch_gold_engine == 'hadoop_mapreduce'.
    """
    silver_df = spark.read.parquet(storage_cfg.silver_posts_path).select(
        "feedback_date", "iphone_model", "ios_version",
        "feature_category", "issue_category", "num_comments",
        "sentiment", "sentiment_score", "engagement_score"
    )
    rdd = silver_df.rdd

    def map_record(row):
        key = (
            str(row["feedback_date"]),
            str(row["iphone_model"] or "Other / Unspecified"),
            str(row["ios_version"] or "iOS Unspecified"),
            str(row["feature_category"] or "General Discussion"),
            str(row["issue_category"] or "Non-Defect / General Inquiry")
        )
        sent = str(row["sentiment"] or "NEUTRAL")
        pos = 1 if sent == "POSITIVE" else 0
        neu = 1 if sent == "NEUTRAL" else 0
        neg = 1 if sent == "NEGATIVE" else 0
        val = (
            1,
            int(row["num_comments"] or 0),
            pos,
            neu,
            neg,
            float(row["sentiment_score"] or 0.0),
            float(row["engagement_score"] or 0.0)
        )
        return (key, val)

    reduced = (
        rdd.map(map_record)
        .reduceByKey(lambda a, b: (
            a[0] + b[0], a[1] + b[1], a[2] + b[2],
            a[3] + b[3], a[4] + b[4], a[5] + b[5], a[6] + b[6]
        ))
        .collect()
    )

    rows = []
    for k, v in reduced:
        cnt = max(v[0], 1)
        rows.append({
            "feedback_date": pd.to_datetime(k[0]).date(),
            "iphone_model": k[1],
            "ios_version": k[2],
            "feature_category": k[3],
            "issue_category": k[4],
            "total_posts": v[0],
            "total_comments": v[1],
            "positive_count": v[2],
            "neutral_count": v[3],
            "negative_count": v[4],
            "avg_sentiment_score": round(v[5] / cnt, 4),
            "avg_engagement_score": round(v[6] / cnt, 2)
        })

    pdf = pd.DataFrame(rows)
    out_dir = Path(f"{storage_cfg.gold_base_path}/issue_summary")
    out_dir.mkdir(parents=True, exist_ok=True)
    for old_f in out_dir.glob("*.parquet"):
        old_f.unlink()
    pdf.to_parquet(out_dir / "part-00000-mapreduce.parquet", index=False, compression="snappy")
    return pdf


def run_mapreduce_word_and_issue_count(spark: 'SparkSession', silver_parquet_path: str) -> pd.DataFrame:
    """
    Doi chuan Batch Processing Engines (Latency + Peak Memory KB):
    1. Hadoop MapReduce Paradigm (Spark RDD map -> reduceByKey)
    2. Spark SQL Catalyst DataFrame Engine
    3. DuckDB Serverless Vectorized Engine
    """
    from pyspark.sql import functions as F

    silver_df = spark.read.parquet(silver_parquet_path).select(
        "iphone_model", "issue_category", "engagement_score", "sentiment"
    ).cache()
    _ = silver_df.count()

    # 1. Hadoop MapReduce RDD
    tracemalloc.start()
    t0 = time.perf_counter()
    rdd = silver_df.rdd
    mapped_rdd = rdd.map(
        lambda row: (
            (row["iphone_model"] or "Unknown", row["issue_category"] or "Unknown"),
            (1, 1 if row["sentiment"] == "NEGATIVE" else 0, int(row["engagement_score"] or 0))
        )
    )
    reduced_rdd = mapped_rdd.reduceByKey(lambda a, b: (a[0] + b[0], a[1] + b[1], a[2] + b[2]))
    res_mr = reduced_rdd.collect()
    mr_ms = (time.perf_counter() - t0) * 1000.0
    _, mr_peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # 2. Spark SQL DataFrame (Catalyst + Tungsten)
    tracemalloc.start()
    t1 = time.perf_counter()
    res_df = (
        silver_df.groupBy("iphone_model", "issue_category")
        .agg(
            F.count("*").alias("post_count"),
            F.sum(F.when(F.col("sentiment") == "NEGATIVE", 1).otherwise(0)).alias("neg_count"),
            F.sum("engagement_score").alias("engagement_sum")
        )
        .collect()
    )
    df_ms = (time.perf_counter() - t1) * 1000.0
    _, df_peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # 3. DuckDB Serverless Engine
    duck_ms = 0.0
    duck_peak_bytes = 0
    try:
        import duckdb
        con = duckdb.connect()
        tracemalloc.start()
        t2 = time.perf_counter()
        _ = con.execute(f"""
            SELECT iphone_model, issue_category, COUNT(*),
                   SUM(CASE WHEN sentiment='NEGATIVE' THEN 1 ELSE 0 END),
                   SUM(engagement_score)
            FROM read_parquet('{silver_parquet_path}/**/*.parquet')
            GROUP BY iphone_model, issue_category
        """).fetchall()
        duck_ms = (time.perf_counter() - t2) * 1000.0
        _, duck_peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        con.close()
    except Exception:
        pass

    silver_df.unpersist()

    rows = [
        {
            "Batch_Processing_Engine": "1_Hadoop_MapReduce_RDD (Python Lambda Serialization)",
            "Config_Key": "hadoop_mapreduce",
            "Output_Groups": len(res_mr),
            "Execution_Latency_ms": round(mr_ms, 2),
            "Driver_Peak_Memory_KB": round(mr_peak_bytes / 1024.0, 2)
        },
        {
            "Batch_Processing_Engine": "2_Spark_SQL_Catalyst_DataFrame (JVM Vectorized Tungsten)",
            "Config_Key": "spark_sql",
            "Output_Groups": len(res_df),
            "Execution_Latency_ms": round(df_ms, 2),
            "Driver_Peak_Memory_KB": round(df_peak_bytes / 1024.0, 2)
        }
    ]
    if duck_ms > 0:
        rows.append({
            "Batch_Processing_Engine": "3_DuckDB_BigLake_Serverless (In-Process C++ Vectorized)",
            "Config_Key": "duckdb_biglake",
            "Output_Groups": len(res_df),
            "Execution_Latency_ms": round(duck_ms, 2),
            "Driver_Peak_Memory_KB": round(duck_peak_bytes / 1024.0, 2)
        })
    return pd.DataFrame(rows)
