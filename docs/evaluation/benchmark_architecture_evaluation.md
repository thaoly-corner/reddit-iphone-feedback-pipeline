# Multi-Criteria Empirical Benchmark & Alternative Technology Evaluation (CO5173)

This document summarizes the empirical benchmark framework implemented in
`tests/pipeline_benchmark.py` and the alternative engine modules across `nlp/`, `processing/`, and `serving/`.

## Pluggable Architecture Matrix (`config/pipeline_config.py`)

| Pipeline Stage | Main Production Choice | Alternative Technologies Integrated in Folder Tree | Key Metrics Evaluated |
| --- | --- | --- | --- |
| **0. Silver Enrichment & NLP** (`silver_engine`) | `pyspark_roberta` (`nlp/sentiment/roberta_sentiment.py`) | `pyspark_lexicon` (`nlp/sentiment/alternatives/lexicon_sentiment.py`), `hadoop_mapreduce_silver` (`processing/batch/bronze_to_silver/alternatives/hadoop_mapreduce_silver.py`), `duckdb_vectorized_silver` (`processing/batch/bronze_to_silver/alternatives/duckdb_vectorized_silver.py`) | Execution Latency (ms), Throughput (rec/s), Driver Peak Memory (KB), NLP Semantic Depth |
| **1. Batch Gold Processing** (`batch_gold_engine`) | `spark_sql` (`processing/batch/silver_to_gold/gold_datamarts.py`) | `hadoop_mapreduce` (`processing/batch/silver_to_gold/alternatives/hadoop_mapreduce_gold.py`), `duckdb_biglake` (`processing/batch/silver_to_gold/alternatives/duckdb_biglake_gold.py`) | Execution Latency (ms), Driver Peak Memory (KB), Output Groups |
| **2. Stream Anomaly Engine (BR03)** (`stream_engine`) | `apache_flink` (`processing/streaming/alternatives/apache_flink_engine.py`) | `spark_streaming` (`processing/streaming/spark_structured_streaming.py`), `kafka_streams` (`processing/streaming/alternatives/kafka_streams_engine.py`) | Throughput (events/sec), Latency (Mean / P95 / P99 ms), Peak State Memory (KB) |
| **3. Serving Data Management** (`serving_backend`) | `postgres` (`serving/database/postgres_loader.py`) | `duckdb_biglake`, `hive_metastore` (`serving/database/alternatives/hive_metastore_catalog.py`), `sqlite_local` | Storage Footprint (KB), Peak Memory (KB), Query Latency (Mean / P50 / P95 / P99 ms) |
| **4. Dimensional Schema Paradigm** (`schema_paradigm`) | `galaxy` (`serving/database/schema_ddl.sql`) | `star` (Kimball Star), `snowflake` (3NF Hierarchy), `obt` (Flat One Big Table) | Join Count, Normalization Level, Storage Footprint (KB), Peak Memory (KB), Query Latency (P50 / P95 / P99 ms) |
