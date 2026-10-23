# Bronze / Silver / Gold / Serving Data Layers

## Bronze Layer (`ingestion/historical/`)

- Streams `.zst` Reddit archives using `zstandard` (`max_window_size=2**31`) without full disk decompression (`ingestion/historical/extract/bronze_zst_ingestor.py`).
- Filters in-scope records (`r/iphone`), runs statistical profiling (`ingestion/historical/profiling/data_profiler.py`), serializes nested JSON structures, adds audit metadata (`_ingest_source`, `_ingest_period`, `_ingest_scope`, `_ingested_at_utc`), and writes Snappy-compressed Parquet verified by SHA-256 checksums.

## Silver Layer (`processing/batch/bronze_to_silver/`, `processing/batch/enrichment/`, `nlp/`)

- Deduplicates posts by `id` (retaining latest `created_utc`), recovers missing/removed `selftext` from `crosspost_parent_list`, strips URLs/HTML/Markdown, and filters moderator-removed posts.
- Enriches records with:
  - `iphone_model` (Regex extraction: iPhone 3G through iPhone 17 Pro Max)
  - `ios_version` (Regex extraction: iOS 15 through iOS 28 Beta)
  - `feature_category` & `issue_category` (6 feature groups, 11 technical defect categories)
  - `sentiment` & `sentiment_score` (Hugging Face `cardiffnlp/twitter-roberta-base-sentiment-latest` via PySpark Arrow Pandas UDF, with rule-based Lexicon fallback)
  - `engagement_score` (`score + 2 * num_comments`) & `impact_index`

## Gold Layer (`processing/batch/silver_to_gold/` & `processing/streaming/`)

Builds 8 business requirement data marts in Parquet and registers them in the Hive Lakehouse Catalog (`voc_lakehouse_db`):

| Output Mart | Business Requirement | Description |
| --- | --- | --- |
| `feedback_volume` | BR01 | Daily & weekly post/comment volume and discussion units |
| `issue_summary` | BR02 | Daily multi-dimensional aggregation by model, iOS, feature, and issue |
| `emerging_issues` | BR03 | 3-day sliding window vs. 14-day historical baseline growth rate & Z-score anomaly detection |
| `sentiment_summary` | BR04 | Sentiment breakdown and mean sentiment score by date and iPhone model |
| `feature_feedback` | BR05 | Mention volume, positive/negative counts, negative ratio %, and engagement per feature/issue |
| `high_impact_complaints` | BR06 | Top 500 high-engagement negative complaints ranked by engagement and impact index |
| `issue_trends` | BR07 | Weekly issue volume and Week-over-Week (`wow_growth_pct`) trend monitoring |
| `model_comparison` | BR08 | Cross-model and iOS version comparison of feedback count, sentiment, and defect complaint rate |

## Serving Layer (`serving/database/`)

- Idempotent upsert synchronization (`UnifiedServingPipelineLoader`) from Gold Parquet marts into PostgreSQL (or local SQLite fallback) supporting 4 schema paradigms (`galaxy`, `star`, `snowflake`, `obt`).
