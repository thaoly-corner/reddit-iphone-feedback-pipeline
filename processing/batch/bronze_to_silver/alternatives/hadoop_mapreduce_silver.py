"""
Alternative Bronze-to-Silver Engine 1 ('hadoop_mapreduce_silver'):
Hadoop MapReduce Paradigm on Spark RDD (map key=id -> reduceByKey deduplication -> flatMap enrichment).
"""
import math
import pandas as pd
from pyspark.sql import SparkSession, DataFrame

from config.pipeline_config import StorageConfig, DomainTaxonomyConfig
from nlp.entity_extraction.regex_extractor import extract_and_enrich_record
from nlp.sentiment.alternatives.lexicon_sentiment import score_lexicon_sentiment


def run_silver_via_hadoop_mapreduce(
    spark: SparkSession,
    storage_cfg: StorageConfig,
    taxonomy_cfg: DomainTaxonomyConfig,
    write_output: bool = True
) -> DataFrame:
    """
    Xay dung Tang Silver bang mo hinh Hadoop MapReduce tren Spark RDD
    (map key=id -> reduceByKey deduplication -> flatMap regex & lexicon enrichment).
    """
    bronze_df = spark.read.parquet(storage_cfg.bronze_posts_parquet)
    has_cp = "crosspost_parent_list" in bronze_df.columns
    select_cols = ["id", "author", "title", "selftext", "score", "num_comments", "upvote_ratio", "permalink", "subreddit", "created_utc"]
    if has_cp:
        select_cols.append("crosspost_parent_list")

    rdd = bronze_df.select(*select_cols).rdd

    def map_by_id(row):
        row_dict = row.asDict()
        pid = row_dict.get("id")
        ts = int(row_dict.get("created_utc") or 0)
        return (pid, (ts, row_dict))

    def enrich_partition(record_tuple):
        pid, (ts, r) = record_tuple
        if not pid:
            return []
        title = str(r.get("title") or "")
        if "[ removed by moderator ]" in title.lower():
            return []
        selftext = str(r.get("selftext") or "")
        cp_json = str(r.get("crosspost_parent_list") or "") if has_cp else ""

        clean_txt, model_nm, ios_ver, feat_cat, iss_cat, cp_rec = extract_and_enrich_record(
            title, selftext, cp_json, taxonomy_cfg
        )
        if len(clean_txt) < 5:
            return []

        sent_lbl, sent_sc = score_lexicon_sentiment(clean_txt)
        sc = int(r.get("score") or 0)
        nc = int(r.get("num_comments") or 0)
        ur = float(r.get("upvote_ratio") or 0.5)
        eng = sc + 2 * nc
        imp = round(math.log1p(max(0, eng)) * (0.5 + 0.5 * ur), 4)
        dt = pd.to_datetime(ts, unit="s", utc=True)

        return [{
            "post_id": str(pid),
            "author": str(r.get("author") or "[unknown]"),
            "title": title,
            "clean_text": clean_txt,
            "iphone_model": model_nm,
            "ios_version": ios_ver,
            "feature_category": feat_cat,
            "issue_category": iss_cat,
            "crosspost_recovered": str(cp_rec),
            "reddit_score": sc,
            "num_comments": nc,
            "upvote_ratio": ur,
            "permalink": str(r.get("permalink") or ""),
            "subreddit": str(r.get("subreddit") or "iphone"),
            "created_utc": ts,
            "sentiment": sent_lbl,
            "sentiment_score": float(sent_sc),
            "engagement_score": eng,
            "impact_index": float(imp),
            "created_datetime": dt.to_pydatetime(),
            "feedback_date": dt.date(),
            "feedback_year": int(dt.year),
            "feedback_month": int(dt.month)
        }]

    enriched_rows = (
        rdd.filter(lambda r: r["id"] is not None)
        .map(map_by_id)
        .reduceByKey(lambda a, b: a if a[0] >= b[0] else b)
        .flatMap(enrich_partition)
        .collect()
    )

    silver_sdf = spark.createDataFrame(pd.DataFrame(enriched_rows))
    if write_output:
        (
            silver_sdf.write
            .mode("overwrite")
            .partitionBy("feedback_year", "feedback_month")
            .parquet(storage_cfg.silver_posts_path)
        )
    return silver_sdf
