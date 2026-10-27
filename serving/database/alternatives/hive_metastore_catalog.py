"""
Alternative Serving & Lakehouse Catalog Backend ('hive_metastore'):
Registers all 8 Gold Parquet Data Marts into Apache Hive Metastore / Spark Catalog (`voc_lakehouse_db`).
"""
from pathlib import Path
from typing import List, TYPE_CHECKING
from collections.abc import Sequence

from config.gold_marts import GOLD_MART_NAMES

if TYPE_CHECKING:
    from pyspark.sql import SparkSession


def register_hive_metastore_tables(
    spark: 'SparkSession', gold_base_path: str,
    mart_names: Sequence[str] = GOLD_MART_NAMES,
) -> List[str]:
    """Register existing and new marts as Spark catalog temporary views."""
    if not set(mart_names).issubset(GOLD_MART_NAMES):
        raise ValueError("Unknown Gold mart name")
    spark.sql("CREATE DATABASE IF NOT EXISTS voc_lakehouse_db")
    spark.sql("USE voc_lakehouse_db")

    registered = []
    for mart in mart_names:
        mart_path = f"{gold_base_path}/{mart}"
        if gold_base_path.startswith(("s3a://", "s3://")):
            hadoop_path = spark._jvm.org.apache.hadoop.fs.Path(mart_path)
            exists = hadoop_path.getFileSystem(spark._jsc.hadoopConfiguration()).exists(hadoop_path)
        else:
            exists = Path(mart_path).exists()
        if exists:
            df = spark.read.parquet(mart_path)
            df.createOrReplaceTempView(f"hive_{mart}")
            registered.append(f"voc_lakehouse_db.hive_{mart}")
    return registered
