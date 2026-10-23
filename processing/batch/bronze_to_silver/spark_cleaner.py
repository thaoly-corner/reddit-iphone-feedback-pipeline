"""
Main Bronze-to-Silver Engine: SparkSession Initialization and PySpark Window Deduplication.
"""
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StringType
from pyspark.sql.window import Window

from config.pipeline_config import StorageConfig


def build_spark_session(app_name: str, storage_cfg: StorageConfig) -> SparkSession:
    """Khoi tao SparkSession toi uu hoa Apache Arrow Vectorized Execution."""
    builder = (
        SparkSession.builder
        .appName(app_name)
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .config("spark.sql.execution.arrow.maxRecordsPerBatch", "256")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
    )
    if storage_cfg.use_s3:
        builder = (
            builder
            .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.3.4,org.postgresql:postgresql:42.7.3")
            .config("spark.hadoop.fs.s3a.endpoint", storage_cfg.s3_endpoint)
            .config("spark.hadoop.fs.s3a.access.key", storage_cfg.s3_access_key)
            .config("spark.hadoop.fs.s3a.secret.key", storage_cfg.s3_secret_key)
            .config("spark.hadoop.fs.s3a.path.style.access", "true")
            .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        )
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
