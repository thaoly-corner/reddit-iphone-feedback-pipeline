# Bronze / Silver / Gold data layers

All three layers target Amazon S3 with Apache Parquet storage. Bucket names,
physical paths, partitions, schemas, and retention policies remain unresolved.

## Bronze

Store raw or near-raw Reddit records within the selected project scope. Preserve
source fields as much as practical. Keep posts and comments separately and retain
source identifiers needed for traceability and later relationship normalization.
Both historical and incremental ingestion feed the lake through their respective
Spark processing paths.

## Silver

Remove duplicate records, handle missing values, normalize timestamps, clean text,
and normalize post-comment relationships. Specific policies are TBD.

Enrich records with these planned attributes:

- `iphone_model`
- `ios_version`
- `feature`
- `issue_category`
- `sentiment`
- `feedback_type`
- `engagement_level`

Use Python, Hugging Face, and regex/rule-based extraction. Model choices, field
types, taxonomies, confidence handling, and evaluation criteria remain TBD.

## Gold

Prepare the following analytical outputs for loading into PostgreSQL / Amazon RDS
for PostgreSQL and subsequent use by the application layer (TBD):

| Output | Business requirement |
| --- | --- |
| `feedback_volume` | BR01 |
| `issue_summary` | BR02 |
| `emerging_issues` | BR03 |
| `sentiment_summary` | BR04 |
| `feature_feedback` | BR05 |
| `high_impact_complaints` | BR06 |
| `issue_trends` | BR07 |
| `model_comparison` | BR08 |

These are planned data products, not implemented tables. Aggregation windows,
dimensions, thresholds, refresh cadence, and serving schemas are unresolved.
