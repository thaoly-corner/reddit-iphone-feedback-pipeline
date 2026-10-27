"""
Main Bronze-to-Silver Engine: SparkSession Initialization and PySpark Window Deduplication.
"""
import os
from pathlib import Path

import pyspark
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType
from pyspark.sql.window import Window

from config.pipeline_config import StorageConfig
from config.spark_storage import build_s3a_options, detect_hadoop_version


def build_spark_session(app_name: str, storage_cfg: StorageConfig) -> SparkSession:
    """Khoi tao SparkSession toi uu hoa Apache Arrow Vectorized Execution."""
    builder = (
        SparkSession.builder
        .appName(app_name)
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .config("spark.sql.execution.arrow.maxRecordsPerBatch", "256")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        .config("spark.sql.session.timeZone", "UTC")
    )
    if storage_cfg.use_s3:
        spark_home = Path(os.getenv("SPARK_HOME") or Path(pyspark.__file__).parent)
        hadoop_version = detect_hadoop_version(spark_home / "jars")
        for key, value in build_s3a_options(storage_cfg, hadoop_version).items():
            builder = builder.config(key, value)
    return builder.getOrCreate()


def deduplicate_bronze_posts(bronze_df: DataFrame) -> DataFrame:
    """Deduplicate Bronze posts by `id` ordering by `created_utc` DESC."""
    window_dedup = Window.partitionBy("id").orderBy(F.col("created_utc").desc())
    dedup_df = (
        bronze_df
        .filter(F.col("id").isNotNull())
        .withColumn("_rn", F.row_number().over(window_dedup))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )
    if "crosspost_parent_list" not in dedup_df.columns:
        dedup_df = dedup_df.withColumn("crosspost_parent_list", F.lit(None).cast(StringType()))
    return dedup_df
