# Data Engineering architecture

```text
Historical Reddit Dump (Academic Torrents)
    -> Batch Ingestion
    -> Apache Spark
    -> Amazon S3 Data Lake

Reddit API
    -> PRAW
    -> Apache Kafka
    -> Spark Structured Streaming
    -> Amazon S3 Data Lake

S3 Gold Layer
    -> PostgreSQL / Amazon RDS for PostgreSQL
    -> Application Layer: TBD
```

## Selected components

Python is the main language. Amazon S3 stores Bronze, Silver, and Gold data in
Apache Parquet. Apache Spark / PySpark handles batch processing and Spark
Structured Streaming handles incremental processing. Python, Hugging Face
(`transformers` and `torch`), and regex/rule-based extraction provide NLP enrichment.
PostgreSQL / Amazon RDS for PostgreSQL provides serving storage. Docker Compose
supports local containerized development; Git/GitHub supports version control.

Apache Flink is only a possible later streaming alternative for benchmarking;
it is not configured or required by this scaffold.

## Application Layer: TBD

Backend, frontend, and visualization technologies are unresolved. No application
framework, visualization library, or application service is configured.

## Open implementation decisions

- Data scope: subreddits, date ranges, languages, and iPhone relevance rules.
- Historical dump selection, download method, and incremental collection cadence.
- Kafka topics, record keys, partitions, retention, and producer integration.
- Spark, Python, Java, container image, and dependency versions and compatibility.
- S3 bucket layout, partitions, schemas, schema evolution, and retention.
- Deduplication keys, missing-value policy, late-data handling, watermarks,
  checkpoints, replay behavior, and delivery guarantees.
- NLP model selection, labels, extraction rules, evaluation, and thresholds.
- Gold aggregation windows, metric definitions, and PostgreSQL schema/load strategy.
- Local service definitions, AWS resource provisioning, region, and access roles.
- Collection access requirements, data handling policy, and operational monitoring.
- Backend, frontend, visualization, and application API design.

