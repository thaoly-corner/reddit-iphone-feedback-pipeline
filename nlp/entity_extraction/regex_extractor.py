"""
Entity Extraction for iPhone Model (iPhone 3 -> 17 Pro Max) and iOS Version (iOS 15 -> 28 Beta)
including Crosspost Text Recovery and Normalization.
"""
import json
import re
from typing import Tuple
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType

from config.pipeline_config import DomainTaxonomyConfig
from nlp.issue_classification.issue_classifier import classify_feature_and_issue


def extract_and_enrich_record(
    title: str,
    selftext: str,
    crosspost_json: str,
    taxonomy_cfg: DomainTaxonomyConfig
) -> Tuple[str, str, str, str, str, bool]:
    """
    Toan tu hop nhat ngu nghia Tang Silver:
    1. Khoi phuc van ban tu crosspost_parent_list neu selftext rong/bi go.
    2. Lam sach HTML entities, URL, Markdown.
    3. Trich xuat iPhone Model & iOS Version bang Regex the he dong.
    4. Anh xa Feature Category & Issue Taxonomy.
    """
    model_pattern = re.compile(taxonomy_cfg.iphone_model_regex)
    ios_pattern = re.compile(taxonomy_cfg.ios_version_regex)
    invalid_markers = {"[deleted]", "[removed]", ""}

    t_str = (title or "").strip()
    s_str = (selftext or "").strip()
    recovered_crosspost = False

    if s_str.lower() in invalid_markers and crosspost_json:
        try:
            cp_list = json.loads(crosspost_json) if isinstance(crosspost_json, str) else crosspost_json
            if isinstance(cp_list, list) and len(cp_list) > 0:
                parent_text = (cp_list[0].get("selftext") or "").strip()
                if parent_text.lower() not in invalid_markers:
                    s_str = parent_text
                    recovered_crosspost = True
        except Exception:
            pass

    is_body_valid = s_str.lower() not in invalid_markers
    raw_combined = f"{t_str}. {s_str}" if is_body_valid else t_str

    clean_txt = re.sub(r"https?://\S+|www\.\S+", " ", raw_combined)
    clean_txt = re.sub(r"(&amp;|&lt;|&gt;|~~|\*\*|__)", " ", clean_txt)
    clean_txt = re.sub(r"\s+", " ", clean_txt).strip()

    model_match = model_pattern.search(clean_txt)
    if model_match:
        raw_model = re.sub(r"\s+", " ", model_match.group(1)).strip().title()
        iphone_model = (
            raw_model
            .replace("Iphone", "iPhone")
            .replace("Se", "SE")
            .replace("Xr", "XR")
            .replace("Xs", "XS")
        )
    else:
        iphone_model = "Other / Unspecified"

    ios_match = ios_pattern.search(clean_txt)
    if ios_match:
        raw_ios = re.sub(r"\s+", " ", ios_match.group(1)).strip()
        parts = raw_ios.split(" ")
        ios_version = f"iOS {' '.join(parts[1:]).title()}" if len(parts) > 1 else "iOS Unspecified"
    else:
        ios_version = "iOS Unspecified"

    detected_feature, detected_issue = classify_feature_and_issue(clean_txt, taxonomy_cfg)

    return (clean_txt, iphone_model, ios_version, detected_feature, detected_issue, recovered_crosspost)


def create_text_recovery_and_taxonomy_udf(taxonomy_cfg: DomainTaxonomyConfig):
    """Dong goi ham extract_and_enrich_record thanh PySpark UDF."""
    def _udf_wrapper(title: str, selftext: str, crosspost_json: str):
        res = extract_and_enrich_record(title, selftext, crosspost_json, taxonomy_cfg)
        return (res[0], res[1], res[2], res[3], res[4], str(res[5]))

    return_schema = StructType([
        StructField("clean_text", StringType(), True),
        StructField("iphone_model", StringType(), True),
        StructField("ios_version", StringType(), True),
        StructField("feature_category", StringType(), True),
        StructField("issue_category", StringType(), True),
        StructField("crosspost_recovered", StringType(), True)
    ])
    return F.udf(_udf_wrapper, return_schema)
