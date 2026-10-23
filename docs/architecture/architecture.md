# Data Engineering Architecture (Medallion Lakehouse & Pluggable Alternative Engines)

```text
Historical Reddit Dump (Academic Torrents .zst)
    -> Streaming Zstd Decompression & Subreddit Filtering (ingestion/historical/extract/)
    -> Statistical Data Profiling (ingestion/historical/profiling/)
    -> Bronze Layer (Parquet Snappy + SHA-256 Checksum)
    -> Silver Layer Cleaning, Enrichment & NLP (processing/batch/bronze_to_silver/, enrichment/ & nlp/)
       [Main: PySpark + RoBERTa Pandas UDF | Alternatives: Lexicon UDF, Hadoop MapReduce RDD, DuckDB Vectorized]
    -> Gold Layer Data Marts BR01-BR08 (processing/batch/silver_to_gold/ & processing/streaming/)
       [Main Batch: Spark SQL Catalyst | Alternatives: Hadoop MapReduce RDD, DuckDB BigLake]
       [Main Stream (BR03): Apache Flink Stateful Window | Alternatives: Spark Structured Streaming, Kafka Streams]
    -> Serving Layer (serving/database/)
       [Main: PostgreSQL / SQLite Fallback with Galaxy Schema | Alternatives: DuckDB BigLake, Hive Metastore, Star/Snowflake/OBT Schemas]
```

## Pluggable Configuration (`config/pipeline_config.py`)

All pipeline stages are centrally orchestrated by `PipelineExecutionConfig`, `StorageConfig`, `DatabaseConfig`, and `DomainTaxonomyConfig` in `config/pipeline_config.py`:

- **Silver Engine (`silver_engine`)**: `"pyspark_roberta"` (default) | `"pyspark_lexicon"` | `"hadoop_mapreduce_silver"` | `"duckdb_vectorized_silver"`
- **Batch Gold Engine (`batch_gold_engine`)**: `"spark_sql"` (default) | `"hadoop_mapreduce"` | `"duckdb_biglake"`
- **Stream Anomaly Engine (`stream_engine`)**: `"apache_flink"` (default) | `"spark_streaming"` | `"kafka_streams"`
- **Serving Backend (`serving_backend`)**: `"postgres"` (default) | `"duckdb_biglake"` | `"hive_metastore"` | `"sqlite_local"`
- **Schema Paradigm (`schema_paradigm`)**: `"galaxy"` (default) | `"star"` | `"snowflake"` | `"obt"`
