"""
End-to-End CLI Entrypoint for the Reddit iPhone VoC Medallion Lakehouse Pipeline (CO5173).
Supports switching between Main Tech and Alternative Tech via CLI flags or PipelineExecutionConfig.
"""
import argparse
from collections.abc import Sequence

from dotenv import load_dotenv

from config.pipeline_config import (
    DatabaseConfig,
    DomainTaxonomyConfig,
    PipelineExecutionConfig,
    StorageConfig,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Reddit iPhone VoC Medallion Pipeline")
    defaults = PipelineExecutionConfig()
    parser.add_argument(
        "--stage", choices=["all", "silver", "gold", "serving"], default="all",
        help="Process existing Bronze; historical download/creation uses its own runner",
    )
    parser.add_argument(
        "--silver-engine",
        default=defaults.silver_engine,
        choices=["pyspark_roberta", "pyspark_lexicon", "hadoop_mapreduce_silver", "duckdb_vectorized_silver"]
    )
    parser.add_argument(
        "--batch-gold-engine",
        default=defaults.batch_gold_engine,
        choices=["spark_sql", "hadoop_mapreduce", "duckdb_biglake"]
    )
    parser.add_argument(
        "--stream-engine",
        default=defaults.stream_engine,
        choices=["spark_streaming", "apache_flink", "kafka_streams"]
    )
    parser.add_argument(
        "--serving-backend",
        default=defaults.serving_backend,
        choices=["postgres", "duckdb_biglake", "hive_metastore", "sqlite_local"]
    )
    parser.add_argument(
        "--schema-paradigm",
        default=defaults.schema_paradigm,
        choices=["star", "snowflake", "galaxy", "obt"]
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    load_dotenv()
    args = parse_args(argv)
    # Runtime imports allow --help and CLI tests without Spark/model/DB dependencies.
    from processing.batch.bronze_to_silver.spark_cleaner import build_spark_session

    storage_cfg = StorageConfig()
    exec_cfg = PipelineExecutionConfig(
        silver_engine=args.silver_engine,
        batch_gold_engine=args.batch_gold_engine,
        stream_engine=args.stream_engine,
        serving_backend=args.serving_backend,
        schema_paradigm=args.schema_paradigm
    )

    print("Active PipelineExecutionConfig:", exec_cfg)

    spark = build_spark_session("Reddit_iPhone_VoC_Medallion_Pipeline", storage_cfg)
    try:
        if args.stage in {"all", "silver"}:
            from processing.batch.enrichment.silver_enrichment import run_silver_pipeline

            run_silver_pipeline(spark, storage_cfg, DomainTaxonomyConfig(), exec_cfg=exec_cfg)
            # Count the persisted result without re-running sentiment inference.
            count = spark.read.parquet(storage_cfg.silver_posts_path).count()
            print(f"Silver layer completed ({count} records).")

        if args.stage in {"all", "gold"}:
            from processing.batch.silver_to_gold.gold_datamarts import build_gold_datamarts

            gold_marts = build_gold_datamarts(spark, storage_cfg, exec_cfg=exec_cfg)
            print(f"Gold layer completed ({len(gold_marts)} data marts exported).")

        if args.stage in {"all", "serving"}:
            if exec_cfg.serving_backend == "hive_metastore":
                from serving.database.alternatives.hive_metastore_catalog import register_hive_metastore_tables

                print("Registered Gold views:", register_hive_metastore_tables(spark, storage_cfg.gold_base_path))
            else:
                from serving.database.postgres_loader import UnifiedServingPipelineLoader

                loader = UnifiedServingPipelineLoader(storage_cfg, DatabaseConfig(), exec_cfg=exec_cfg)
                try:
                    loader.initialize_schema()
                    sync_stats = loader.sync_dimensions_and_facts(spark=spark)
                    print("Legacy serving facts:", sync_stats)
                    print("Gold serving tables:", loader.sync_gold_marts(spark=spark))
                finally:
                    loader.engine.dispose()
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
