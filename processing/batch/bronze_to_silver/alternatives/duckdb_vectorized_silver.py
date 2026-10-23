"""
Alternative Bronze-to-Silver Engine 2 ('duckdb_vectorized_silver'):
DuckDB In-Process Columnar SQL Deduplication + Vectorized Python Batch Enrichment.
"""
from pathlib import Path
import numpy as np
import pandas as pd

from config.pipeline_config import StorageConfig, DomainTaxonomyConfig
from nlp.entity_extraction.regex_extractor import extract_and_enrich_record
from nlp.sentiment.alternatives.lexicon_sentiment import score_lexicon_sentiment


def run_silver_via_duckdb_vectorized(
    storage_cfg: StorageConfig,
    taxonomy_cfg: DomainTaxonomyConfig,
    write_output: bool = True
) -> pd.DataFrame:
    """
    Xay dung Tang Silver bang DuckDB In-Process Columnar SQL
    ket hop Vectorized Python Batch Enrichment (Khong can khoi tao Spark JVM).
    """
    import duckdb
    con = duckdb.connect()
    bronze_path = storage_cfg.bronze_posts_parquet

    dedup_pdf = con.execute(f"""
        SELECT * EXCLUDE (_rn)
        FROM (
            SELECT
                id AS post_id,
                COALESCE(author, '[unknown]') AS author,
                COALESCE(title, '') AS title,
                COALESCE(selftext, '') AS selftext,
                COALESCE(CAST(crosspost_parent_list AS VARCHAR), '') AS crosspost_parent_list,
                COALESCE(CAST(score AS INTEGER), 0) AS reddit_score,
                COALESCE(CAST(num_comments AS INTEGER), 0) AS num_comments,
                COALESCE(CAST(upvote_ratio AS DOUBLE), 0.5) AS upvote_ratio,
                COALESCE(permalink, '') AS permalink,
                COALESCE(subreddit, 'iphone') AS subreddit,
                CAST(created_utc AS BIGINT) AS created_utc,
                ROW_NUMBER() OVER (PARTITION BY id ORDER BY created_utc DESC) AS _rn
            FROM read_parquet('{bronze_path}')
            WHERE id IS NOT NULL
        )
        WHERE _rn = 1
          AND LOWER(title) NOT LIKE '%[ removed by moderator ]%'
    """).df()
    con.close()

    clean_texts, models, ios_vers, feat_cats, iss_cats, cp_recs, sents, sent_scores = (
        [], [], [], [], [], [], [], []
    )

    for row in dedup_pdf.itertuples(index=False):
        c_txt, m_nm, i_ver, f_cat, i_cat, cp_r = extract_and_enrich_record(
            row.title, row.selftext, row.crosspost_parent_list, taxonomy_cfg
        )
        lbl, sc = score_lexicon_sentiment(c_txt)
        clean_texts.append(c_txt)
        models.append(m_nm)
        ios_vers.append(i_ver)
        feat_cats.append(f_cat)
        iss_cats.append(i_cat)
        cp_recs.append(str(cp_r))
        sents.append(lbl)
        sent_scores.append(sc)

    dedup_pdf["clean_text"] = clean_texts
    dedup_pdf["iphone_model"] = models
    dedup_pdf["ios_version"] = ios_vers
    dedup_pdf["feature_category"] = feat_cats
    dedup_pdf["issue_category"] = iss_cats
    dedup_pdf["crosspost_recovered"] = cp_recs
    dedup_pdf["sentiment"] = sents
    dedup_pdf["sentiment_score"] = sent_scores

    dedup_pdf = dedup_pdf[dedup_pdf["clean_text"].str.len() >= 5].drop(columns=["selftext", "crosspost_parent_list"]).copy()
    dedup_pdf["engagement_score"] = dedup_pdf["reddit_score"] + 2 * dedup_pdf["num_comments"]
    dedup_pdf["impact_index"] = (
        np.log1p(np.maximum(0, dedup_pdf["engagement_score"])) * (0.5 + 0.5 * dedup_pdf["upvote_ratio"])
    ).round(4)
    dt_series = pd.to_datetime(dedup_pdf["created_utc"], unit="s", utc=True)
    dedup_pdf["created_datetime"] = dt_series
    dedup_pdf["feedback_date"] = dt_series.dt.date
    dedup_pdf["feedback_year"] = dt_series.dt.year
    dedup_pdf["feedback_month"] = dt_series.dt.month

    if write_output:
        out_root = Path(storage_cfg.silver_posts_path)
        out_root.mkdir(parents=True, exist_ok=True)
        dedup_pdf.to_parquet(
            out_root,
            engine="pyarrow",
            index=False,
            compression="snappy",
            partition_cols=["feedback_year", "feedback_month"]
        )
    return dedup_pdf
