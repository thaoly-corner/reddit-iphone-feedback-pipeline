"""
Tang Gold: Dieu phoi Pluggable Engine (Spark SQL Catalyst | Hadoop MapReduce | DuckDB BigLake
& Apache Flink | Kafka Streams | Spark Streaming) theo PipelineExecutionConfig.
"""
from typing import Dict, Optional
import warnings
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from config.pipeline_config import StorageConfig, PipelineExecutionConfig
from processing.batch.silver_to_gold.alternatives.hadoop_mapreduce_gold import build_gold_issue_summary_mapreduce
from processing.batch.silver_to_gold.alternatives.duckdb_biglake_gold import build_gold_issue_summary_duckdb
from processing.streaming.spark_structured_streaming import compute_emerging_issues_spark_window
from processing.streaming.alternatives.apache_flink_engine import run_streaming_emerging_issues_engine
from processing.batch.silver_to_gold.gold_queries import RECURRING_ISSUES_SQL, SUPPORT_DEMAND_SQL


def build_recurring_issues_mart(silver_df: DataFrame) -> DataFrame:
    """Issue x month; recurring means present in >= 2 distinct monthly periods.

    active_period_count is the total observed months for the issue across the
    dataset. recurrence_count counts repeat months after the first (N - 1).
    """
    silver_df.createOrReplaceTempView("_voc_recurring_input")
    return silver_df.sparkSession.sql(RECURRING_ISSUES_SQL)


def build_support_demand_mart(silver_df: DataFrame) -> DataFrame:
    """Monthly question demand by support category, model and iOS version.

    For category/month totals, sum question_count; roll up averages using
    question_count as weight. Legacy alternative Silver engines are not
    classified here: they receive an empty mart with the same schema.
    """
    if not {"is_question", "support_category"}.issubset(silver_df.columns):
        warnings.warn(
            "Silver has no support enrichment; support_demand will be empty. "
            "Use the main PySpark Silver pipeline to populate it.",
            UserWarning,
            stacklevel=2,
        )
        silver_df = (
            silver_df.limit(0)
            .withColumn("is_question", F.lit(False))
            .withColumn("support_category", F.lit(None).cast("string"))
        )
    silver_df.createOrReplaceTempView("_voc_support_input")
    return silver_df.sparkSession.sql(SUPPORT_DEMAND_SQL)


def build_gold_datamarts(
    spark: SparkSession,
    storage_cfg: StorageConfig,
    exec_cfg: Optional[PipelineExecutionConfig] = None
) -> Dict[str, DataFrame]:
    """
    Preserve BR01 -> BR08 and add recurring issues and support demand marts.
    Tu dong chuyen doi Engine tinh toan theo PipelineExecutionConfig.
    """
    if exec_cfg is None:
        exec_cfg = PipelineExecutionConfig()

    silver_df = spark.read.parquet(storage_cfg.silver_posts_path).cache()
    gold_base = storage_cfg.gold_base_path
    marts: Dict[str, DataFrame] = {}

    # BR01: Feedback Volume Over Time
    br01_df = (
        silver_df
        .groupBy(
            "feedback_date",
            F.date_trunc("week", F.col("feedback_date")).cast("date").alias("feedback_week"),
            "subreddit"
        )
        .agg(
            F.count("post_id").alias("total_posts"),
            F.sum("num_comments").alias("total_comments"),
            F.sum(F.lit(1) + F.col("num_comments")).alias("total_discussion_units"),
            F.round(F.avg("engagement_score"), 2).alias("avg_engagement_score")
        )
        .orderBy("feedback_date")
    )
    br01_df.write.mode("overwrite").parquet(f"{gold_base}/feedback_volume")
    marts["feedback_volume"] = br01_df

    # BR02: Issue Summary & Daily Core Grain (Pluggable Batch Engine)
    if exec_cfg.batch_gold_engine == "hadoop_mapreduce":
        build_gold_issue_summary_mapreduce(spark, storage_cfg)
        br02_df = spark.read.parquet(f"{gold_base}/issue_summary")
    elif exec_cfg.batch_gold_engine == "duckdb_biglake":
        build_gold_issue_summary_duckdb(storage_cfg)
        br02_df = spark.read.parquet(f"{gold_base}/issue_summary")
    else:
        br02_df = (
            silver_df
            .groupBy("feedback_date", "iphone_model", "ios_version", "feature_category", "issue_category")
            .agg(
                F.count("post_id").alias("total_posts"),
                F.sum("num_comments").alias("total_comments"),
                F.sum(F.when(F.col("sentiment") == "POSITIVE", 1).otherwise(0)).alias("positive_count"),
                F.sum(F.when(F.col("sentiment") == "NEUTRAL", 1).otherwise(0)).alias("neutral_count"),
                F.sum(F.when(F.col("sentiment") == "NEGATIVE", 1).otherwise(0)).alias("negative_count"),
                F.round(F.avg("sentiment_score"), 4).alias("avg_sentiment_score"),
                F.round(F.avg("engagement_score"), 2).alias("avg_engagement_score")
            )
        )
        br02_df.write.mode("overwrite").parquet(f"{gold_base}/issue_summary")
    marts["issue_summary"] = br02_df

    # BR03: Emerging Issues Detection (Pluggable Stream / Window Engine)
    if exec_cfg.stream_engine in ("apache_flink", "kafka_streams"):
        run_streaming_emerging_issues_engine(storage_cfg, stream_engine=exec_cfg.stream_engine, spark=spark)
        br03_df = spark.read.parquet(f"{gold_base}/emerging_issues")
    else:
        br03_df = compute_emerging_issues_spark_window(spark, storage_cfg)
        br03_df.write.mode("overwrite").parquet(f"{gold_base}/emerging_issues")
    marts["emerging_issues"] = br03_df

    # BR04: Sentiment Distribution Summary
    br04_df = (
        silver_df
        .groupBy("feedback_date", "iphone_model", "sentiment")
        .agg(
            F.count("post_id").alias("post_count"),
            F.round(F.avg("sentiment_score"), 4).alias("mean_sentiment_score")
        )
    )
    br04_df.write.mode("overwrite").parquet(f"{gold_base}/sentiment_summary")
    marts["sentiment_summary"] = br04_df

    # BR05: Feature Feedback Matrix
    br05_df = (
        silver_df
        .groupBy("feature_category", "issue_category")
        .agg(
            F.count("post_id").alias("mention_count"),
            F.sum(F.when(F.col("sentiment") == "NEGATIVE", 1).otherwise(0)).alias("negative_mentions"),
            F.sum(F.when(F.col("sentiment") == "POSITIVE", 1).otherwise(0)).alias("positive_mentions"),
            F.round(
                F.sum(F.when(F.col("sentiment") == "NEGATIVE", 1).otherwise(0)) * 100.0 / F.count("post_id"),
                2
            ).alias("negative_ratio_pct"),
            F.round(F.avg("engagement_score"), 2).alias("avg_engagement")
        )
        .orderBy(F.col("mention_count").desc())
    )
    br05_df.write.mode("overwrite").parquet(f"{gold_base}/feature_feedback")
    marts["feature_feedback"] = br05_df

    # BR06: High-Impact Negative Complaints
    br06_df = (
        silver_df
        .filter(F.col("sentiment") == "NEGATIVE")
        .select(
            "post_id", "feedback_date", "iphone_model", "ios_version",
            "feature_category", "issue_category", "title", "permalink",
            "reddit_score", "num_comments", "engagement_score", "impact_index", "sentiment_score"
        )
        .orderBy(F.col("engagement_score").desc())
        .limit(500)
    )
    br06_df.write.mode("overwrite").parquet(f"{gold_base}/high_impact_complaints")
    marts["high_impact_complaints"] = br06_df

    # BR07: Weekly Issue Growth Trends (WoW)
    weekly_issues = (
        silver_df
        .withColumn("week_start", F.date_trunc("week", F.col("feedback_date")).cast("date"))
        .groupBy("week_start", "feature_category", "issue_category")
        .agg(F.count("post_id").alias("weekly_volume"))
    )
    w_lag = Window.partitionBy("feature_category", "issue_category").orderBy("week_start")
    br07_df = (
        weekly_issues
        .withColumn("prev_week_volume", F.lag("weekly_volume", 1).over(w_lag))
        .withColumn(
            "wow_growth_pct",
            F.when(
                F.col("prev_week_volume").isNotNull() & (F.col("prev_week_volume") > 0),
                F.round(((F.col("weekly_volume") - F.col("prev_week_volume")) * 100.0) / F.col("prev_week_volume"), 2)
            ).otherwise(F.lit(0.0))
        )
    )
    br07_df.write.mode("overwrite").parquet(f"{gold_base}/issue_trends")
    marts["issue_trends"] = br07_df

    # BR08: Model & OS Version Multi-dimensional Comparison
    br08_df = (
        silver_df
        .groupBy("iphone_model", "ios_version", "feature_category")
        .agg(
            F.count("post_id").alias("total_feedback"),
            F.round(F.avg("sentiment_score"), 4).alias("avg_sentiment"),
            F.round(
                F.sum(F.when(F.col("sentiment") == "NEGATIVE", 1).otherwise(0)) * 100.0 / F.count("post_id"),
                2
            ).alias("defect_complaint_rate_pct"),
            F.round(F.avg("engagement_score"), 2).alias("avg_engagement")
        )
    )
    br08_df.write.mode("overwrite").parquet(f"{gold_base}/model_comparison")
    marts["model_comparison"] = br08_df

    marts["recurring_issues"] = build_recurring_issues_mart(silver_df)
    marts["support_demand"] = build_support_demand_mart(silver_df)
    for name in ("recurring_issues", "support_demand"):
        marts[name].write.mode("overwrite").parquet(f"{gold_base}/{name}")

    silver_df.unpersist()
    return marts
