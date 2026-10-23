"""
Main / Baseline Streaming Engine ('spark_streaming'):
Spark Structured Streaming / Windowing for BR03 Emerging Issues Detection.
"""
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from config.pipeline_config import StorageConfig


def compute_emerging_issues_spark_window(spark: SparkSession, storage_cfg: StorageConfig) -> DataFrame:
    """
    Compute BR03 Emerging Issues using Spark SQL / Structured Windowing (3-day vs 14-day baseline).
    """
    silver_df = spark.read.parquet(storage_cfg.silver_posts_path)
    daily_issue_vol = (
        silver_df
        .filter(F.col("issue_category") != "Non-Defect / General Inquiry")
        .groupBy("feedback_date", "iphone_model", "feature_category", "issue_category")
        .agg(F.count("post_id").alias("daily_volume"))
        .withColumn("epoch_days", F.datediff(F.col("feedback_date"), F.lit("1970-01-01")))
    )
    w_curr = Window.partitionBy("iphone_model", "issue_category").orderBy("epoch_days").rangeBetween(-2, 0)
    w_base = Window.partitionBy("iphone_model", "issue_category").orderBy("epoch_days").rangeBetween(-16, -3)
    return (
        daily_issue_vol
        .withColumn("curr_3d_avg", F.round(F.avg("daily_volume").over(w_curr), 2))
        .withColumn("base_14d_avg", F.round(F.coalesce(F.avg("daily_volume").over(w_base), F.lit(0.0)), 2))
        .withColumn("base_14d_std", F.round(F.coalesce(F.stddev("daily_volume").over(w_base), F.lit(0.5)), 2))
        .withColumn(
            "growth_rate_pct",
            F.round(
                ((F.col("curr_3d_avg") - F.col("base_14d_avg")) / F.greatest(F.col("base_14d_avg"), F.lit(1.0))) * 100.0,
                2
            )
        )
        .withColumn(
            "z_score",
            F.round(
                (F.col("curr_3d_avg") - F.col("base_14d_avg")) / F.greatest(F.col("base_14d_std"), F.lit(0.5)),
                2
            )
        )
        .withColumn(
            "is_anomaly",
            (F.col("curr_3d_avg") >= 2.0) & ((F.col("growth_rate_pct") >= 150.0) | (F.col("z_score") >= 2.0))
        )
    )
