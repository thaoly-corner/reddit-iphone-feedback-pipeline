"""Evidence endpoints for the Data & Pipeline page: lineage, correctness checks, benchmark, API latency."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from ..config import REPO_ROOT
from ..db import query_df
from ..latency import latency_report

router = APIRouter(prefix="/pipeline", tags=["evaluation"])

BR_MATRIX = [
    {"id": "BR01", "name": "Customer feedback volume monitoring", "users": ["Product Manager", "CX Analyst"],
     "mart": "gold_feedback_volume", "endpoints": ["/volume/daily", "/volume/weekly", "/volume/summary", "/volume/peaks"], "page": "/overview"},
    {"id": "BR02", "name": "Product issue identification", "users": ["Product Manager"],
     "mart": "gold_issue_summary", "endpoints": ["/issues/ranking", "/issues/detail"], "page": "/issues"},
    {"id": "BR03", "name": "Emerging issue detection", "users": ["Product Manager", "CX Analyst"],
     "mart": "gold_emerging_issues", "endpoints": ["/emerging/alerts", "/emerging/series", "/emerging/heatmap"], "page": "/emerging"},
    {"id": "BR04", "name": "Customer sentiment analysis", "users": ["Brand Manager", "CX Analyst"],
     "mart": "gold_sentiment_summary", "endpoints": ["/sentiment/timeline", "/sentiment/by-issue", "/sentiment/by-model"], "page": "/sentiment"},
    {"id": "BR05", "name": "Feature-level feedback analysis", "users": ["Product Manager"],
     "mart": "gold_feature_feedback", "endpoints": ["/features/matrix"], "page": "/features"},
    {"id": "BR06", "name": "High-impact complaint identification", "users": ["Brand Manager", "CX Analyst"],
     "mart": "gold_high_impact_complaints", "endpoints": ["/complaints"], "page": "/complaints"},
    {"id": "BR07", "name": "Issue trend monitoring", "users": ["Product Manager"],
     "mart": "gold_issue_trends", "endpoints": ["/issues/trends"], "page": "/issues"},
    {"id": "BR08", "name": "iPhone model / iOS version comparison", "users": ["Product Manager", "Marketing Analyst"],
     "mart": "gold_model_comparison", "endpoints": ["/compare/models", "/compare/ios", "/compare/options"], "page": "/compare"},
    {"id": "BR09", "name": "Recurring issue monitoring", "users": ["Product Manager", "CX Analyst"],
     "mart": "gold_recurring_issues", "endpoints": ["/recurring"], "page": "/support"},
    {"id": "BR10", "name": "Support demand analysis", "users": ["CX Analyst", "Marketing Analyst"],
     "mart": "gold_support_demand", "endpoints": ["/support/demand"], "page": "/support"},
]

LINEAGE = [
    {"stage": "Source", "tech": "Academic Torrents Reddit dump (.zst) + Reddit API (PRAW)", "artifact": "RS_2026-05..07.zst, r/iphone"},
    {"stage": "Bronze", "tech": "zstandard streaming filter, Parquet Snappy, SHA-256", "artifact": "s3://<bucket>/bronze/posts/year=2026/month=05..07"},
    {"stage": "Silver", "tech": "PySpark + RoBERTa (cardiffnlp/twitter-roberta-base-sentiment-latest) Arrow pandas UDF, regex entities, taxonomy", "artifact": "s3://<bucket>/silver/posts (partitioned by year/month)"},
    {"stage": "Gold", "tech": "Spark SQL Catalyst (batch) + stateful sliding-window stream engine (BR03)", "artifact": "s3://<bucket>/gold/<mart> x10"},
    {"stage": "Serving", "tech": "AWS RDS PostgreSQL 18, galaxy schema + gold_* snapshots (SQLAlchemy idempotent sync)", "artifact": "voc_analytics.public.gold_*"},
    {"stage": "Application", "tech": "FastAPI (parameterised SQL, TTL cache, canonical labels) + React/ECharts", "artifact": "BrandVoice"},
]

# Numbers reported by the team's benchmark suite (tests/pipeline_benchmark.py); overridden by
# docs/evaluation/benchmark_results.json when that file exists.
BENCHMARK_FALLBACK = {
    "source": "config/pipeline_config.py docstring (team benchmark run on Colab)",
    "batch_gold": [{"engine": "spark_sql", "note": "main; 2.52x faster than Hadoop MapReduce RDD"},
                   {"engine": "hadoop_mapreduce", "note": "alternative"}, {"engine": "duckdb_biglake", "note": "alternative"}],
    "stream": [{"engine": "apache_flink (stateful window sim)", "throughput_ev_s": 95935, "latency_ms": 0.0089, "state_kb": 134.78},
               {"engine": "spark_streaming", "note": "alternative"}, {"engine": "kafka_streams", "note": "alternative"}],
    "serving": [{"backend": "postgres", "mean_latency_ms": 8.05, "peak_ram_kb": 39.12, "storage_kb": 88},
                {"backend": "sqlite_local", "note": "alternative"}, {"backend": "duckdb_biglake", "note": "alternative"}, {"backend": "hive_metastore", "note": "alternative"}],
    "schema": [{"paradigm": "galaxy", "p99_ms": 5.48, "note": "main"}, {"paradigm": "star"}, {"paradigm": "snowflake"}, {"paradigm": "obt"}],
}


@router.get("/evidence")
def evidence():
    checks = []
    counts = {
        "feedback_volume.total_posts": "SELECT SUM(total_posts) AS n FROM gold_feedback_volume",
        "issue_summary.total_posts": "SELECT SUM(total_posts) AS n FROM gold_issue_summary",
        "sentiment_summary.post_count": "SELECT SUM(post_count) AS n FROM gold_sentiment_summary",
        "feature_feedback.mention_count": "SELECT SUM(mention_count) AS n FROM gold_feature_feedback",
        "model_comparison.total_feedback": "SELECT SUM(total_feedback) AS n FROM gold_model_comparison",
        "issue_trends.weekly_volume": "SELECT SUM(weekly_volume) AS n FROM gold_issue_trends",
        "issue_summary.sentiment_parts": "SELECT SUM(positive_count + neutral_count + negative_count) AS n FROM gold_issue_summary",
    }
    values = {k: int(query_df(sql)["n"].iloc[0]) for k, sql in counts.items()}
    ref = values["issue_summary.total_posts"]
    for k, v in values.items():
        checks.append({"check": f"{k} == issue_summary.total_posts", "expected": ref, "actual": v, "passed": v == ref})
    galaxy = int(query_df("SELECT SUM(total_posts) AS n FROM fact_feedback_summary")["n"].iloc[0])
    checks.append({"check": "fact_feedback_summary (galaxy) == gold_issue_summary", "expected": ref, "actual": galaxy, "passed": galaxy == ref})
    dup = int(query_df(
        """SELECT COUNT(*) AS n FROM (SELECT feedback_date, iphone_model, ios_version, feature_category, issue_category
           FROM gold_issue_summary GROUP BY 1,2,3,4,5 HAVING COUNT(*) > 1) d"""
    )["n"].iloc[0])
    checks.append({"check": "gold_issue_summary grain is unique", "expected": 0, "actual": dup, "passed": dup == 0})
    neg_bad = int(query_df("SELECT COUNT(*) AS n FROM gold_high_impact_complaints WHERE sentiment_score > 0")["n"].iloc[0])
    checks.append({"check": "high_impact_complaints all negative (sentiment_score <= 0)", "expected": 0, "actual": neg_bad, "passed": neg_bad == 0})
    emerging_rule = int(query_df(
        """SELECT COUNT(*) AS n FROM gold_emerging_issues
           WHERE is_anomaly <> (curr_3d_avg >= 2 AND (growth_rate_pct >= 150 OR z_score >= 2))"""
    )["n"].iloc[0])
    checks.append({"check": "emerging is_anomaly matches documented rule", "expected": 0, "actual": emerging_rule, "passed": emerging_rule == 0})
    dates = query_df("SELECT MIN(feedback_date) AS lo, MAX(feedback_date) AS hi, COUNT(DISTINCT feedback_date) AS d FROM gold_feedback_volume").iloc[0]
    expected_days = (dates["hi"] - dates["lo"]).days + 1
    checks.append({"check": "no missing days in feedback_volume", "expected": expected_days, "actual": int(dates["d"]), "passed": int(dates["d"]) == expected_days})

    quality = {
        "raw_model_labels": int(query_df("SELECT COUNT(DISTINCT iphone_model) AS n FROM gold_issue_summary")["n"].iloc[0]),
        "raw_ios_labels": int(query_df("SELECT COUNT(DISTINCT ios_version) AS n FROM gold_issue_summary")["n"].iloc[0]),
        "unspecified_model_share_pct": round(float(query_df(
            "SELECT SUM(CASE WHEN iphone_model = 'Other / Unspecified' THEN total_posts ELSE 0 END) * 100.0 / SUM(total_posts) AS p FROM gold_issue_summary"
        )["p"].iloc[0]), 2),
        "unspecified_ios_share_pct": round(float(query_df(
            "SELECT SUM(CASE WHEN ios_version = 'iOS Unspecified' THEN total_posts ELSE 0 END) * 100.0 / SUM(total_posts) AS p FROM gold_issue_summary"
        )["p"].iloc[0]), 2),
        "non_defect_share_pct": round(float(query_df(
            "SELECT SUM(CASE WHEN issue_category = 'Non-Defect / General Inquiry' THEN total_posts ELSE 0 END) * 100.0 / SUM(total_posts) AS p FROM gold_issue_summary"
        )["p"].iloc[0]), 2),
        "non_defect_in_high_impact": int(query_df(
            "SELECT COUNT(*) AS n FROM gold_high_impact_complaints WHERE issue_category = 'Non-Defect / General Inquiry'"
        )["n"].iloc[0]),
    }
    from ..filters import variants
    quality["canonical_model_labels"] = len(variants("model"))
    quality["canonical_ios_labels"] = len(variants("ios"))

    bench_path = REPO_ROOT / "docs" / "evaluation" / "benchmark_results.json"
    benchmark = json.loads(bench_path.read_text(encoding="utf-8")) if bench_path.exists() else BENCHMARK_FALLBACK
    return {"data": {
        "checks": checks, "passed": sum(c["passed"] for c in checks), "total_checks": len(checks),
        "quality": quality, "lineage": LINEAGE, "br_matrix": BR_MATRIX, "benchmark": benchmark,
        "config": {"silver_engine": "pyspark_roberta", "batch_gold_engine": "spark_sql", "stream_engine": "apache_flink",
                   "serving_backend": "postgres", "schema_paradigm": "galaxy"},
    }}


@router.get("/latency")
def latency():
    return {"data": latency_report()}
