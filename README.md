# reddit-iphone-feedback-pipeline

A Data Engineering course project for collecting, processing, storing, enriching,
and preparing Reddit customer feedback about Apple iPhone for downstream analytics.
This initial monorepo is a scaffold; pipeline logic and datasets are not included.

## Data sources and architecture

Historical data comes from Academic Torrents / ArcticShift Reddit dumps.
Incremental data comes from the Reddit API through PRAW.

```text
Historical Reddit Dump -> Batch Ingestion -> Apache Spark -> Amazon S3 Data Lake
Reddit API -> PRAW -> Apache Kafka -> Spark Structured Streaming -> Amazon S3 Data Lake
S3 Gold Layer -> PostgreSQL / Amazon RDS for PostgreSQL -> Application Layer: TBD
```

## Current technology stack

- Python; pandas, pyarrow, and zstandard for data handling.
- PRAW for Reddit API access and boto3 for AWS access.
- Apache Kafka for messaging.
- Apache Spark / PySpark for batch processing and Spark Structured Streaming.
- Amazon S3 and Apache Parquet for lake storage.
- Python, Hugging Face, and regex/rule-based extraction for NLP enrichment.
- PostgreSQL / Amazon RDS for PostgreSQL, accessed with psycopg2.
- Docker Compose for local containerized development; Git/GitHub for version control.
- python-dotenv for local environment configuration.

Apache Flink may later be considered for streaming benchmarks. It is not configured.
Backend, frontend, visualization libraries, and application API design are **TBD**.
The `application/` directory is a documentation-only placeholder.

## Data lake

Bronze preserves raw or near-raw in-scope records, keeping posts and comments
separate. Silver deduplicates, handles missing values, normalizes timestamps and
relationships, cleans text, and adds `iphone_model`, `ios_version`, `feature`,
`issue_category`, `sentiment`, `feedback_type`, and `engagement_level`.
Gold prepares analytical outputs for the serving database.

See [data layers](docs/data/data_layers.md) for details.

## Repository structure

```text
reddit-iphone-feedback-pipeline/
    ingestion/historical/download/
    ingestion/historical/extract/
    ingestion/historical/profiling/
    ingestion/streaming/reddit/
    processing/batch/bronze_to_silver/
    processing/batch/enrichment/
    processing/batch/silver_to_gold/
    processing/streaming/
    nlp/sentiment/
    nlp/feature_detection/
    nlp/issue_classification/
    nlp/entity_extraction/
    serving/database/
    application/
    infrastructure/docker/
    infrastructure/aws/
    infrastructure/kafka/
    notebooks/
    tests/
    docs/architecture/
    docs/data/
    docs/evaluation/
    scripts/
    .env.example
    .gitignore
    docker-compose.yml
    requirements.txt
    README.md
```

Historical ingestion separates download, extraction, and profiling. Batch processing
separates Bronze-to-Silver, enrichment, and Silver-to-Gold stages. NLP directories
hold future enrichment modules; serving/database holds future database artifacts.
Infrastructure directories reserve Docker, AWS, and Kafka configuration. Notebooks,
tests, scripts, and evaluation directories are placeholders. Empty directories use
`.gitkeep` so they can be tracked by Git. Python package markers will be added when
importable modules exist.

## Business requirements

| ID | Requirement | Gold output |
| --- | --- | --- |
| BR01 | Customer Feedback Volume Monitoring | `feedback_volume` |
| BR02 | Product Issue Identification | `issue_summary` |
| BR03 | Emerging Issue Detection | `emerging_issues` |
| BR04 | Customer Sentiment Analysis | `sentiment_summary` |
| BR05 | Feature-level Feedback Analysis | `feature_feedback` |
| BR06 | High-impact Complaint Identification | `high_impact_complaints` |
| BR07 | Issue Trend Monitoring | `issue_trends` |
| BR08 | iPhone Model / iOS Version Comparison | `model_comparison` |

See [business requirements](docs/data/business_requirements.md).

## Development workflow

1. From this repository directory, create and activate a Python virtual environment:
   `python3 -m venv .venv` then `source .venv/bin/activate`.
2. Install the selected Python dependencies with `pip install -r requirements.txt`.
   Versions are intentionally unresolved; validate Python, Java, Spark, and library
   compatibility before running future jobs. PySpark needs a compatible Java runtime.
3. Copy `.env.example` to `.env` and replace placeholders locally. Never commit
   credentials or local data. Future Python entrypoints must explicitly load their
   configuration; no entrypoints exist yet.
4. Review the architecture and define the unresolved schemas, policies, versions,
   and local services before implementing pipeline stages.
5. Add focused validation under `tests/` as processing logic is implemented, and
   document profiling and evaluation results in the corresponding directories.
6. Review changes with Git when a repository is initialized by the developer.

`docker-compose.yml` contains an empty service map. It documents the intended
Compose entrypoint but cannot start a development stack until services are defined.
No containers, downloads, AWS resources, or database objects are created by setup.

See [architecture and unresolved decisions](docs/architecture/architecture.md).
