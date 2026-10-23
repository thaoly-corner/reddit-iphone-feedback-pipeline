"""
End-to-End CLI Entrypoint for the Reddit iPhone VoC Medallion Lakehouse Pipeline (CO5173).
Supports switching between Main Tech and Alternative Tech via CLI flags or PipelineExecutionConfig.
"""
import argparse
from pathlib import Path

from config.pipeline_config import (
    StorageConfig,
    DatabaseConfig,
    DomainTaxonomyConfig,
    PipelineExecutionConfig
)
from ingestion.historical.extract.bronze_zst_ingestor import build_bronze_parquet
from ingestion.historical.profiling.data_profiler import profile_filtered_posts
from processing.batch.bronze_to_silver.spark_cleaner import build_spark_session
from processing.batch.enrichment.silver_enrichment import run_silver_pipeline
from processing.batch.silver_to_gold.gold_datamarts import build_gold_datamarts
from serving.database.alternatives.hive_metastore_catalog import register_hive_metastore_tables
from serving.database.postgres_loader import UnifiedServingPipelineLoader


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Reddit iPhone VoC Medallion Pipeline")
    parser.add_argument(
        "--silver-engine",
        default="pyspark_roberta",
        choices=["pyspark_roberta", "pyspark_lexicon", "hadoop_mapreduce_silver", "duckdb_vectorized_silver"]
    )
    parser.add_argument(
        "--batch-gold-engine",
        default="spark_sql",
        choices=["spark_sql", "hadoop_mapreduce", "duckdb_biglake"]
    )
    parser.add_argument(
        "--stream-engine",
        default="apache_flink",
        choices=["spark_streaming", "apache_flink", "kafka_streams"]
    )
    parser.add_argument(
        "--serving-backend",
        default="postgres",
        choices=["postgres", "duckdb_biglake", "hive_metastore", "sqlite_local"]
    )
    parser.add_argument(
        "--schema-paradigm",
        default="galaxy",
        choices=["star", "snowflake", "galaxy", "obt"]
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    storage_cfg = StorageConfig()
    storage_cfg.ensure_local_dirs()
    taxonomy_cfg = DomainTaxonomyConfig()
    exec_cfg = PipelineExecutionConfig(
        silver_engine=args.silver_engine,
        batch_gold_engine=args.batch_gold_engine,
        stream_engine=args.stream_engine,
        serving_backend=args.serving_backend,
        schema_paradigm=args.schema_paradigm
    )

    print("Active PipelineExecutionConfig:", exec_cfg)

    if storage_cfg.posts_filtered_jsonl.exists() and not Path(storage_cfg.bronze_posts_parquet).exists():
        profile_filtered_posts(storage_cfg.posts_filtered_jsonl, storage_cfg.profile_dir)
        build_bronze_parquet(storage_cfg.posts_filtered_jsonl, storage_cfg.bronze_posts_parquet)

    spark = build_spark_session("Reddit_iPhone_VoC_Medallion_Pipeline", storage_cfg)
    silver_df = run_silver_pipeline(spark, storage_cfg, taxonomy_cfg, exec_cfg=exec_cfg)
    print(f"Silver layer completed ({silver_df.count()} records).")

    gold_marts = build_gold_datamarts(spark, storage_cfg, exec_cfg=exec_cfg)
    register_hive_metastore_tables(spark, storage_cfg.gold_base_path)
    print(f"Gold layer completed ({len(gold_marts)} data marts exported).")

    db_cfg = DatabaseConfig()
    loader = UnifiedServingPipelineLoader(storage_cfg, db_cfg, exec_cfg=exec_cfg)
    loader.initialize_schema()
    sync_stats = loader.sync_dimensions_and_facts()
    print("Serving layer synchronization completed:", sync_stats)


if __name__ == "__main__":
    main()
