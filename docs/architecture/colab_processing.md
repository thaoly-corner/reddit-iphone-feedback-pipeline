# Colab processing: Bronze → Silver → Gold → serving

The historical runner owns download, filtering, profiling and Bronze creation.
The processing runner reads all monthly partitions below `bronze/posts`, rebuilds
Silver, writes Gold, and refreshes PostgreSQL/RDS serving copies. S3 Gold remains
the canonical analytical data. Run the following commands later in Colab, from
the repository root; they have not been executed against cloud services locally.

## Install and configure

```python
%pip install -r requirements.txt
```

Restart the Colab runtime after installation, particularly if it already imported
pandas or created Spark. The requirements constrain pandas below 3 because the
installed Spark build warns about pandas 3 support. Keep `.env` in the repository
root (it is Git-ignored). Copy `.env.example` and fill these values:

```dotenv
USE_S3=true
S3_PROVIDER=aws
S3_BUCKET=<your-bucket>
AWS_DEFAULT_REGION=ap-southeast-1
HISTORICAL_WORK_DIR=<your-local-or-mounted-Drive-workdir>
RAW_DIR=<your-local-or-mounted-Drive-raw-dir>
TORRENT_DIR=<your-torrent-directory>

DB_HOST=<your-PostgreSQL-or-RDS-host>
DB_PORT=5432
DB_NAME=voc_analytics
DB_USER=<your-database-user>
DB_PASSWORD=<your-database-password>
DB_SSLMODE=require
USE_SQLITE_FALLBACK=false
```

For processing, `S3_BUCKET` and PostgreSQL connection values are required; the
historical path variables are needed by historical ingestion or local storage.
`AWS_DEFAULT_REGION` defaults to `ap-southeast-1`. No AWS access key or secret
is needed for the current anonymous AWS S3 mode. The bucket must permit the
list/read/write/delete operations required by Spark overwrite jobs; an unsigned
historical upload succeeding does not establish these processing permissions.

For local data, use `USE_S3=false` and `HISTORICAL_WORK_DIR`; for local serving,
set `USE_SQLITE_FALLBACK=true` and `SQLITE_PATH` to a writable file. Supplying a
DB host selects PostgreSQL by default if the SQLite flag is absent. With no DB
host or flag, the legacy SQLite development fallback remains available.
`POSTGRES_HOST/PORT/DB/USER/PASSWORD` remain fallback aliases for the new `DB_*`
names, with `DB_*` taking precedence. Passwords with URL punctuation are escaped.

For MinIO, keep `USE_S3=true`, set `S3_PROVIDER=minio`, a bare `S3_BUCKET`, and
`S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`. Spark uses path-style access and
`SimpleAWSCredentialsProvider`; AWS uses `AnonymousAWSCredentialsProvider`.

Spark detects its Hadoop version from the installed distribution's JARs and
requests the identical `hadoop-aws` version. Maven resolves the matching AWS SDK;
the code does not independently pin an SDK bundle. This follows the
[Hadoop S3A dependency compatibility guidance](https://hadoop.apache.org/docs/current/hadoop-aws/tools/hadoop-aws/troubleshooting_s3a.html).
The first S3-enabled session may download these Maven artifacts. Start a fresh
Colab runtime if a previous Spark session was created without S3A dependencies.
Vendor Spark distributions without standard Hadoop JAR names need their own
matching preinstalled connector; the helper fails clearly instead of guessing.

## Run stages

Each command loads `.env` before constructing configuration. None recreates
Bronze. Run these Colab cells in order:

```python
!python -m scripts.run_pipeline --stage silver --silver-engine pyspark_roberta
```

```python
!python -m scripts.run_pipeline --stage gold --batch-gold-engine spark_sql --stream-engine apache_flink
```

```python
!python -m scripts.run_pipeline --stage serving --serving-backend postgres
```

Or execute all stages in one process:

```python
!python -m scripts.run_pipeline --stage all --silver-engine pyspark_roberta --batch-gold-engine spark_sql --stream-engine apache_flink --serving-backend postgres --schema-paradigm galaxy
```

The CLI takes its defaults directly from `PipelineExecutionConfig`:
`pyspark_roberta`, `spark_sql`, `apache_flink`, `postgres`, `galaxy`.
BR03 uses the existing stateful sliding-window implementation selected by
`apache_flink`; the configured Spark session handles Parquet I/O for local,
AWS and MinIO storage. Its algorithm and benchmark timing code are retained.
The current `apache_flink` implementation is a Python/deque algorithm under the
repository's benchmark label; it does not submit a job to a PyFlink runtime.
The existing
RoBERTa UDF may fall back to lexicon if model initialization fails; the runtime
must be able to download/cache the model for actual RoBERTa inference.

## Outputs and compatibility

`bronze_posts_path` points at the whole Bronze dataset;
`bronze_posts_parquet` remains its compatibility alias. Local Bronze lives under
`HISTORICAL_WORK_DIR/parquet/year=YYYY/month=MM`. Silver still deduplicates and
writes with full overwrite partitioned by `feedback_year`, `feedback_month`.
Its existing NLP, sentiment, engagement and support fields remain intact.

All eight original Gold paths remain. New output schemas are:

| Mart | Columns |
| --- | --- |
| `recurring_issues` | `issue_category` string, `feedback_year` int, `feedback_month` int, `issue_count` long, `active_period_count` long, `recurrence_count` long, `is_recurring` boolean |
| `support_demand` | `support_category` string, `feedback_year` int, `feedback_month` int, `iphone_model` string, `ios_version` string, `question_count` long, `avg_sentiment_score` double, `avg_reddit_score` double, `avg_num_comments` double, `avg_engagement_score` double |

Recurrence counts distinct year/month periods across the complete dataset, not
consecutive months. `recurrence_count = active_period_count - 1`; two or more
active months set `is_recurring=true`. General-inquiry and undated records are
excluded. Support demand includes only `is_question=true`. Sum `question_count`
to roll up category/month/model/iOS totals; use count-weighted averages when
rolling up the averages (assuming populated input measures).

The DuckDB and Hadoop MapReduce Silver algorithms and benchmark suite remain.
DuckDB local reads use a recursive Parquet glob for the multi-month root. These
alternatives do not add support classification; Gold writes an empty
`support_demand` with a warning when those fields are absent. Use main PySpark
Silver for measured support demand. DuckDB-based alternative storage paths
have not been extended to use anonymous AWS/MinIO credentials; benchmark locally.
Support enrichment is not added to benchmark timing.

The SQLAlchemy loader retains legacy dimension/fact tables and adds snapshots
`gold_<mart_name>` for all ten marts. Table names come from a fixed allowlist.
Each snapshot is replaced transactionally and its row count checked; the DB user
needs permission to create/drop these snapshot tables. The legacy facts retain
their existing upsert behavior. When reading S3/MinIO, both loaders receive the
configured Spark session, so pandas never needs to interpret an `s3a://` URI.
Gold aggregates are collected to the driver for SQLAlchemy writes; this is
intended for the course-project dataset, not unlimited-sized marts.
`StarSchemaServingLoader` and existing querying APIs remain available.

## Runtime smoke checks (Colab only)

Run these only after configuring the environment. They read data and may connect
to cloud storage/DB. These checks were not executed locally.

```python
from dotenv import load_dotenv
load_dotenv()
from config.pipeline_config import StorageConfig, DatabaseConfig
from config.gold_marts import GOLD_MART_NAMES
from processing.batch.bronze_to_silver.spark_cleaner import build_spark_session
from pyspark.sql import functions as F

cfg = StorageConfig()
spark = build_spark_session("Historical-processing-smoke", cfg)
bronze = spark.read.parquet(cfg.bronze_posts_path)
assert bronze.count() > 0 and "id" in bronze.columns
if {"year", "month"}.issubset(bronze.columns):
    print("Bronze monthly partitions:", bronze.select("year", "month").distinct().count())
else:
    print("Bronze ingest periods:", bronze.select("_ingest_period").distinct().count())
silver = spark.read.parquet(cfg.silver_posts_path)
assert silver.count() == silver.select("post_id").distinct().count()
assert silver.filter("post_id IS NULL OR feedback_year IS NULL OR feedback_month IS NULL").count() == 0
assert silver.schema["is_question"].dataType.simpleString() == "boolean"
assert silver.filter("NOT is_question AND support_category IS NOT NULL").count() == 0
assert silver.filter("is_question AND support_category IS NULL").count() == 0
assert silver.filter("sentiment IS NULL OR sentiment_score IS NULL").count() == 0
for name in GOLD_MART_NAMES:
    print(name, spark.read.parquet(f"{cfg.gold_base_path}/{name}").count())
demand_count = spark.read.parquet(f"{cfg.gold_base_path}/support_demand").agg(
    F.coalesce(F.sum("question_count"), F.lit(0))
).first()[0]
assert demand_count == silver.filter("is_question").count()
spark.stop()
```

After the serving stage, verify snapshots with read-only SQLAlchemy queries:

```python
from sqlalchemy import create_engine, inspect, text
engine = create_engine(DatabaseConfig().sqlalchemy_url)
tables = set(inspect(engine).get_table_names())
with engine.connect() as conn:
    for name in GOLD_MART_NAMES:
        table = f"gold_{name}"  # fixed allowlist, never user input
        assert table in tables
        print(table, conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar_one())
engine.dispose()
```

Some new marts may legitimately contain zero rows (e.g. no support questions).
Compare these counts with the preceding Gold counts. Actual Spark SQL execution,
model inference, Maven downloads, S3 permissions and RDS access remain Colab
validation steps. Local checks cover Python syntax, configuration, aggregation SQL
semantics in SQLite and mocked orchestration/serving boundaries only.
