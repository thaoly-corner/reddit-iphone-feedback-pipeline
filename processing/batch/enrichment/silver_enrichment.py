"""
Unified Silver Layer Pipeline Router & Benchmark Suite:
Orchestrates Bronze-to-Silver cleaning, NLP entity/issue extraction, sentiment analysis,
and benchmarks all 4 Silver engines ('pyspark_roberta', 'pyspark_lexicon',
'hadoop_mapreduce_silver', 'duckdb_vectorized_silver').
"""
import time
import tracemalloc
from typing import Any

import pandas as pd
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.column import Column
from pyspark.sql.types import FloatType, IntegerType, StringType

from config.pipeline_config import (
    DomainTaxonomyConfig,
    PipelineExecutionConfig,
    StorageConfig,
)
from nlp.entity_extraction.regex_extractor import create_text_recovery_and_taxonomy_udf
from nlp.sentiment.alternatives.lexicon_sentiment import lexicon_sentiment_pandas_udf
from nlp.sentiment.roberta_sentiment import transformer_sentiment_udf
from processing.batch.bronze_to_silver.alternatives.duckdb_vectorized_silver import (
    run_silver_via_duckdb_vectorized,
)
from processing.batch.bronze_to_silver.alternatives.hadoop_mapreduce_silver import (
    run_silver_via_hadoop_mapreduce,
)
from processing.batch.bronze_to_silver.spark_cleaner import (
    # build_spark_session,
    deduplicate_bronze_posts,
)

QUESTION_PATTERN = (
    r"(?i)"
    r"(\?|"
    r"\bhow do i\b|"
    r"\bhow can i\b|"
    r"\bhow to\b|"
    r"\bwhy is\b|"
    r"\bwhy does\b|"
    r"\bwhy won't\b|"
    r"\bcan anyone\b|"
    r"\bdoes anyone\b|"
    r"\banyone know\b|"
    r"\bneed help\b|"
    r"\bplease help\b)"
)

def build_support_category_expr(
    taxonomy_cfg: DomainTaxonomyConfig
) -> Column:
    support_category_expr = None

    for category, keywords in taxonomy_cfg.support_taxonomy.items():
        category_condition = None

        for keyword in keywords:
            condition = F.lower(
                F.col("clean_text")
            ).contains(keyword.lower())

            category_condition = (
                condition
                if category_condition is None
                else category_condition | condition
            )

        # Empty keyword lists should behave like an empty taxonomy, not F.when(None).
        if category_condition is None:
            continue

        if support_category_expr is None:
            support_category_expr = F.when(
                category_condition,
                F.lit(category),
            )
        else:
            support_category_expr = support_category_expr.when(
                category_condition,
                F.lit(category),
            )
    if support_category_expr is None:
        return F.lit("Other Support")
    return support_category_expr.otherwise(
        F.lit("Other Support")
    )


def run_silver_pipeline(
    spark: SparkSession,
    storage_cfg: StorageConfig,
    taxonomy_cfg: DomainTaxonomyConfig,
    exec_cfg: PipelineExecutionConfig | None = None
) -> DataFrame:
    """
    Thuc thi day du Pipeline Tang Silver (Bronze Parquet -> Silver Partitioned Parquet)
    dua tren cong nghe `silver_engine` duoc chon trong PipelineExecutionConfig.
    """
    if exec_cfg is None:
        exec_cfg = PipelineExecutionConfig()

    engine_choice = exec_cfg.silver_engine

    if engine_choice == "hadoop_mapreduce_silver":
        return run_silver_via_hadoop_mapreduce(spark, storage_cfg, taxonomy_cfg, write_output=True)

    if engine_choice == "duckdb_vectorized_silver":
        run_silver_via_duckdb_vectorized(storage_cfg, taxonomy_cfg, write_output=True)
        return spark.read.parquet(storage_cfg.silver_posts_path)

    # Default PySpark DataFrame Pipeline ('pyspark_roberta' or 'pyspark_lexicon')
    bronze_df = spark.read.parquet(storage_cfg.bronze_posts_path)
    dedup_df = deduplicate_bronze_posts(bronze_df)

    extraction_udf = create_text_recovery_and_taxonomy_udf(taxonomy_cfg)
    enriched_df = dedup_df.withColumn(
        "_extracted",
        extraction_udf(
            F.col("title").cast(StringType()),
            F.col("selftext").cast(StringType()),
            F.col("crosspost_parent_list").cast(StringType())
        )
    ).select(
        F.col("id").alias("post_id"),
        F.coalesce(F.col("author"), F.lit("[unknown]")).alias("author"),
        F.coalesce(F.col("title"), F.lit("")).alias("title"),
        F.col("_extracted.clean_text").alias("clean_text"),
        F.col("_extracted.iphone_model").alias("iphone_model"),
        F.col("_extracted.ios_version").alias("ios_version"),
        F.col("_extracted.feature_category").alias("feature_category"),
        F.col("_extracted.issue_category").alias("issue_category"),
        F.col("_extracted.crosspost_recovered").alias("crosspost_recovered"),
        F.coalesce(F.col("score"), F.lit(0)).cast(IntegerType()).alias("reddit_score"),
        F.coalesce(F.col("num_comments"), F.lit(0)).cast(IntegerType()).alias("num_comments"),
        F.coalesce(F.col("upvote_ratio"), F.lit(0.5)).cast(FloatType()).alias("upvote_ratio"),
        F.coalesce(F.col("permalink"), F.lit("")).alias("permalink"),
        F.coalesce(F.col("subreddit"), F.lit("iphone")).alias("subreddit"),
        F.col("created_utc").cast("long").alias("created_utc")
    )

    filtered_silver_df = enriched_df.filter(
        (F.length(F.col("clean_text")) >= 5) &
        (~F.lower(F.col("title")).contains("[ removed by moderator ]"))
    )

    chosen_sentiment_udf = (
        lexicon_sentiment_pandas_udf
        if engine_choice == "pyspark_lexicon"
        else transformer_sentiment_udf
    )

    with_sentiment_df = (
        filtered_silver_df
        .withColumn("_sent", chosen_sentiment_udf(F.col("clean_text")))
        .withColumn("sentiment", F.col("_sent.sentiment"))
        .withColumn("sentiment_score", F.col("_sent.sentiment_score"))
        .drop("_sent")
    )


    support_category_expr = build_support_category_expr(taxonomy_cfg)

    with_support_df = (
        with_sentiment_df
        .withColumn(
            "is_question",
            F.col("clean_text").rlike(QUESTION_PATTERN)
        )
        .withColumn(
            "support_category",
            F.when(
                F.col("is_question"),
                support_category_expr
            ).otherwise(F.lit(None).cast(StringType()))
        )
    )

    final_silver_df = (
        with_support_df
        .withColumn("engagement_score", F.col("reddit_score") + (F.lit(2) * F.col("num_comments")))
        .withColumn(
            "impact_index",
            F.round(
                F.log1p(F.greatest(F.lit(0), F.col("engagement_score"))) *
                (F.lit(0.5) + F.lit(0.5) * F.col("upvote_ratio")),
                4
            )
        )
        .withColumn("created_datetime", F.to_timestamp(F.from_unixtime(F.col("created_utc"))))
        .withColumn("feedback_date", F.to_date(F.col("created_datetime")))
        .withColumn("feedback_year", F.year(F.col("feedback_date")))
        .withColumn("feedback_month", F.month(F.col("feedback_date")))
    )

    (
        final_silver_df.write
        .mode("overwrite")
        .partitionBy("feedback_year", "feedback_month")
        .parquet(storage_cfg.silver_posts_path)
    )

    return final_silver_df


def benchmark_silver_enrichment_engines(
    spark: SparkSession,
    storage_cfg: StorageConfig,
    taxonomy_cfg: DomainTaxonomyConfig,
    sample_limit: int = 500
) -> pd.DataFrame:
    """
    Thuc nghiem doi chuan 4 cong nghe Tang Silver (Bronze -> Silver Enrichment & NLP Benchmark).
    """
    bronze_df = (
        spark.read
        .parquet(storage_cfg.bronze_posts_path)
        .limit(sample_limit)
        .cache()
    )
    n_rows = bronze_df.count()
    extraction_udf = create_text_recovery_and_taxonomy_udf(taxonomy_cfg)

    results: list[dict[str, Any]] = []

    # 1. DuckDB In-Process SQL + Vectorized Python Lexicon
    tracemalloc.start()
    t0 = time.perf_counter()
    pdf_duck = run_silver_via_duckdb_vectorized(storage_cfg, taxonomy_cfg, write_output=False)
    duck_ms = (time.perf_counter() - t0) * 1000.0
    _, duck_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    results.append({
        "Silver_Engine_Architecture": "1_DuckDB_Vectorized_Silver (In-Process SQL + Rule Lexicon)",
        "Config_Key": "duckdb_vectorized_silver",
        "Records_Processed": len(pdf_duck),
        "Execution_Latency_ms": round(duck_ms, 2),
        "Throughput_rec_per_sec": round(len(pdf_duck) / max(duck_ms / 1000.0, 1e-6), 1),
        "Driver_Peak_Memory_KB": round(duck_mem / 1024.0, 2),
        "NLP_Semantic_Capability": "Lexicon Keyword Polarity (Fast, No Context)"
    })

    # 2. Hadoop MapReduce RDD Silver (map -> reduceByKey -> flatMap)
    tracemalloc.start()
    t1 = time.perf_counter()
    sdf_mr = run_silver_via_hadoop_mapreduce(spark, storage_cfg, taxonomy_cfg, write_output=False)
    mr_cnt = sdf_mr.count()
    mr_ms = (time.perf_counter() - t1) * 1000.0
    _, mr_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    results.append({
        "Silver_Engine_Architecture": "2_Hadoop_MapReduce_RDD_Silver (RDD Key-Value + Lexicon)",
        "Config_Key": "hadoop_mapreduce_silver",
        "Records_Processed": mr_cnt,
        "Execution_Latency_ms": round(mr_ms, 2),
        "Throughput_rec_per_sec": round(mr_cnt / max(mr_ms / 1000.0, 1e-6), 1),
        "Driver_Peak_Memory_KB": round(mr_mem / 1024.0, 2),
        "NLP_Semantic_Capability": "Lexicon Keyword Polarity (High Serialization Cost)"
    })

    # 3. PySpark DataFrame + Arrow Pandas UDF (Fast Lexicon)
    tracemalloc.start()
    t2 = time.perf_counter()
    df_lex = (
        bronze_df
        .withColumn("_ext", extraction_udf(F.col("title").cast(StringType()), F.col("selftext").cast(StringType()), F.lit("")))
        .withColumn("_sent", lexicon_sentiment_pandas_udf(F.col("_ext.clean_text")))
    )
    _ = df_lex.select("_sent.sentiment").collect()
    lex_ms = (time.perf_counter() - t2) * 1000.0
    _, lex_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    results.append({
        "Silver_Engine_Architecture": "3_PySpark_Arrow_Lexicon_UDF (Distributed Vectorized Lexicon)",
        "Config_Key": "pyspark_lexicon",
        "Records_Processed": n_rows,
        "Execution_Latency_ms": round(lex_ms, 2),
        "Throughput_rec_per_sec": round(n_rows / max(lex_ms / 1000.0, 1e-6), 1),
        "Driver_Peak_Memory_KB": round(lex_mem / 1024.0, 2),
        "NLP_Semantic_Capability": "Negation-Aware Lexicon (Distributed CPU)"
    })

    # 4. PySpark DataFrame + Arrow Pandas UDF (Transformer RoBERTa - Production Choice)
    tracemalloc.start()
    t3 = time.perf_counter()
    df_rob = (
        bronze_df
        .withColumn("_ext", extraction_udf(F.col("title").cast(StringType()), F.col("selftext").cast(StringType()), F.lit("")))
        .withColumn("_sent", transformer_sentiment_udf(F.col("_ext.clean_text")))
    )
    _ = df_rob.select("_sent.sentiment").collect()
    rob_ms = (time.perf_counter() - t3) * 1000.0
    _, rob_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    results.append({
        "Silver_Engine_Architecture": "4_PySpark_Arrow_RoBERTa_Transformer (Production Deep NLP)",
        "Config_Key": "pyspark_roberta",
        "Records_Processed": n_rows,
        "Execution_Latency_ms": round(rob_ms, 2),
        "Throughput_rec_per_sec": round(n_rows / max(rob_ms / 1000.0, 1e-6), 1),
        "Driver_Peak_Memory_KB": round(rob_mem / 1024.0, 2),
        "NLP_Semantic_Capability": "Deep Transformer Self-Attention (Sarcasm & Context Aware)"
    })

    bronze_df.unpersist()
    return pd.DataFrame(results)
