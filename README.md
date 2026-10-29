# reddit-iphone-feedback-pipeline

End-to-end Data Engineering platform (CO5173) for collecting, processing, enriching, benchmarking, and serving customer feedback about Apple iPhone from Reddit using a **Medallion Lakehouse Architecture (Bronze -> Silver -> Gold -> Serving)** with pluggable **Main & Alternative Technologies**.

## Architecture & Pluggable Engine Matrix

Configured centrally in `config/pipeline_config.py` (`PipelineExecutionConfig`):

- **Ingestion (`ingestion/`)**:
  - **Historical Batch**: Torrent download (`ingestion/historical/download/`), streaming `.zst` decompression & Bronze Parquet generation (`ingestion/historical/extract/`), and statistical data profiling (`ingestion/historical/profiling/`).
  - **Real-time Streaming**: Reddit API (`PRAW`) producer publishing to Apache Kafka (`ingestion/streaming/reddit/`).
- **Silver Layer & NLP (`processing/batch/` & `nlp/`)**:
  - **Main Tech**: PySpark DataFrame deduplication (`processing/batch/bronze_to_silver/spark_cleaner.py`), Regex Entity & Issue Taxonomy extraction (`nlp/`), and Vectorized Arrow Pandas UDF with Hugging Face RoBERTa (`nlp/sentiment/roberta_sentiment.py`).
  - **Alternative Tech**: Distributed Rule/VADER-style Lexicon Pandas UDF (`nlp/sentiment/alternatives/lexicon_sentiment.py`), Hadoop MapReduce RDD (`processing/batch/bronze_to_silver/alternatives/hadoop_mapreduce_silver.py`), and DuckDB In-Process Vectorized SQL (`processing/batch/bronze_to_silver/alternatives/duckdb_vectorized_silver.py`).
- **Gold Layer (`processing/batch/silver_to_gold/` & `processing/streaming/`)**:
  - Generates 8 Gold Parquet Data Marts supporting **BR01 through BR08** (`gold_datamarts.py`).
  - **Main Batch Tech**: Spark SQL Catalyst Vectorized Engine (`spark_sql`).
  - **Alternative Batch Tech**: Hadoop MapReduce RDD (`alternatives/hadoop_mapreduce_gold.py`) and DuckDB BigLake Serverless SQL (`alternatives/duckdb_biglake_gold.py`).
  - **Main Stream Tech (BR03 Anomaly Detection)**: Apache Flink Stateful Sliding Window (`processing/streaming/alternatives/apache_flink_engine.py`).
  - **Alternative Stream Tech**: Spark Structured Streaming / Windowing (`processing/streaming/spark_structured_streaming.py`) and Kafka Streams KTable StateStore (`processing/streaming/alternatives/kafka_streams_engine.py`).
- **Serving Layer (`serving/database/`)**:
  - **Main Tech**: PostgreSQL (with SQLite local fallback) using **Galaxy / Fact Constellation Schema** (`galaxy`) in `postgres_loader.py` & `schema_ddl.sql`.
  - **Alternative Tech**: Hive Metastore Catalog (`serving/database/alternatives/hive_metastore_catalog.py`), DuckDB BigLake Serverless, and alternative schema paradigms: **Kimball Star (`star`)**, **3NF Snowflake (`snowflake`)**, and **Flat One Big Table (`obt`)**.
- **Evaluation & Testing (`tests/` & `docs/evaluation/`)**:
  - Multi-criteria empirical benchmark (`tests/pipeline_benchmark.py`) measuring Latency ($P_{50}/P_{95}/P_{99}$), Throughput (records/s), Storage Footprint (KB), and Peak RAM Memory (KB) across all 5 pipeline stages.

## Repository Structure (Zero Overlap)

```text
reddit-iphone-feedback-pipeline-main/
├── config/
│   ├── __init__.py
│   └── pipeline_config.py
├── ingestion/
│   ├── historical/
│   │   ├── download/
│   │   │   └── torrent_downloader.py
│   │   ├── extract/
│   │   │   └── bronze_zst_ingestor.py
│   │   └── profiling/
│   │       └── data_profiler.py
│   └── streaming/
│       └── reddit/
│           └── kafka_praw_producer.py
├── nlp/
│   ├── entity_extraction/
│   │   └── regex_extractor.py
│   ├── feature_detection/
│   │   └── feature_detector.py
│   ├── issue_classification/
│   │   └── issue_classifier.py
│   └── sentiment/
│       ├── roberta_sentiment.py
│       └── alternatives/
│           └── lexicon_sentiment.py
├── processing/
│   ├── batch/
│   │   ├── bronze_to_silver/
│   │   │   ├── spark_cleaner.py
│   │   │   └── alternatives/
│   │   │       ├── duckdb_vectorized_silver.py
│   │   │       └── hadoop_mapreduce_silver.py
│   │   ├── enrichment/
│   │   │   └── silver_enrichment.py
│   │   └── silver_to_gold/
│   │       ├── gold_datamarts.py
│   │       └── alternatives/
│   │           ├── duckdb_biglake_gold.py
│   │           └── hadoop_mapreduce_gold.py
│   └── streaming/
│       ├── spark_structured_streaming.py
│       └── alternatives/
│           ├── apache_flink_engine.py
│           └── kafka_streams_engine.py
├── serving/
│   └── database/
│       ├── postgres_loader.py
│       ├── schema_ddl.sql
│       └── alternatives/
│           └── hive_metastore_catalog.py
├── notebooks/
│   └── DE_project.ipynb
├── scripts/
│   └── run_pipeline.py
├── tests/
│   ├── pipeline_benchmark.py
│   └── test_pipeline.py
├── docs/
│   ├── architecture/architecture.md
│   ├── data/business_requirements.md
│   ├── data/data_layers.md
│   └── evaluation/benchmark_architecture_evaluation.md
├── application/
├── infrastructure/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Application (BrandVoice)

The web application that serves BR01–BR10 to end users lives in `application/` (FastAPI + React). See `application/README.md`; `docker compose up --build` starts it on http://localhost:8080 against the PostgreSQL serving layer configured in `.env`.

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the end-to-end pipeline via CLI:
   ```bash
   python -m scripts.run_pipeline --silver-engine pyspark_roberta --batch-gold-engine spark_sql --stream-engine apache_flink --serving-backend postgres --schema-paradigm galaxy
   ```
3. Or open `notebooks/DE_project.ipynb` in Google Colab / Jupyter and upload `reddit-iphone-feedback-pipeline-main.zip` to run the interactive Medallion Lakehouse pipeline and full empirical benchmark suite.
