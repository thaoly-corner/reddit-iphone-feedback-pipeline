"""
Alternative Serving & Lakehouse Catalog Backend ('hive_metastore'):
Registers all 8 Gold Parquet Data Marts into Apache Hive Metastore / Spark Catalog (`voc_lakehouse_db`).
"""
from pathlib import Path
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import SparkSession


def register_hive_metastore_tables(spark: 'SparkSession', gold_base_path: str) -> List[str]:
    """Dang ky 8 Gold Parquet Marts vao Apache Hive Metastore / Spark Catalog."""
    spark.sql("CREATE DATABASE IF NOT EXISTS voc_lakehouse_db")
    spark.sql("USE voc_lakehouse_db")

    mart_names = [
        "feedback_volume", "issue_summary", "emerging_issues", "sentiment_summary",
        "feature_feedback", "high_impact_complaints", "issue_trends", "model_comparison"
    ]
    registered = []
    for mart in mart_names:
        mart_path = f"{gold_base_path}/{mart}"
        if Path(mart_path).exists():
            df = spark.read.parquet(mart_path)
            df.createOrReplaceTempView(f"hive_{mart}")
            registered.append(f"voc_lakehouse_db.hive_{mart}")
    return registered
