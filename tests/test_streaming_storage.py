"""Check BR03 storage routing with a mocked Spark session and tiny pandas input."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pandas as pd
import pytest

from config.pipeline_config import StorageConfig
from processing.streaming.alternatives.apache_flink_engine import (
    EMERGING_ISSUES_SCHEMA,
    run_streaming_emerging_issues_engine,
)


@pytest.fixture
def silver_posts() -> pd.DataFrame:
    return pd.DataFrame([
        {"post_id": pid, "feedback_date": day, "iphone_model": "iPhone 16",
         "feature_category": "Battery & Thermal", "issue_category": issue}
        for pid, day, issue in [
            ("a", date(2026, 1, 1), "Battery Drain"),
            ("b", date(2026, 1, 1), "Battery Drain"),
            ("c", date(2026, 1, 4), "Battery Drain"),
            ("d", date(2026, 1, 4), "Non-Defect / General Inquiry"),
        ]
    ])


@pytest.mark.parametrize("provider", ["local", "aws", "minio"])
def test_stateful_window_uses_spark_only_for_storage(
    tmp_path: Path, silver_posts: pd.DataFrame, provider: str,
) -> None:
    cfg = StorageConfig(
        use_s3=provider != "local", s3_provider="minio" if provider == "minio" else "aws",
        s3_bucket="test-bucket", project_root=tmp_path,
    )
    spark = MagicMock()
    spark.read.parquet.return_value.select.return_value.toPandas.return_value = silver_posts
    result = run_streaming_emerging_issues_engine(cfg, spark=spark)
    spark.read.parquet.assert_called_once_with(cfg.silver_posts_path)
    assert len(result) == 2
    first, second = result.sort_values("feedback_date").to_dict("records")
    assert first["daily_volume"] == first["curr_3d_avg"] == 2
    assert first["is_anomaly"]
    assert second["curr_3d_avg"] == 1
    assert second["base_14d_avg"] == 2
    assert second["z_score"] == -2
    assert not second["is_anomaly"]
    assert spark.createDataFrame.call_args.kwargs["schema"] == EMERGING_ISSUES_SCHEMA
    spark.createDataFrame.return_value.write.mode.assert_called_once_with("overwrite")
    spark.createDataFrame.return_value.write.mode.return_value.parquet.assert_called_once_with(
        f"{cfg.gold_base_path}/emerging_issues"
    )


def test_empty_result_overwrites_old_mart_with_explicit_schema(silver_posts: pd.DataFrame) -> None:
    spark = MagicMock()
    spark.read.parquet.return_value.select.return_value.toPandas.return_value = silver_posts.iloc[:0]
    cfg = StorageConfig(use_s3=True, s3_bucket="test-bucket")
    result = run_streaming_emerging_issues_engine(cfg, spark=spark)
    assert result.empty
    spark.createDataFrame.assert_called_once_with([], schema=EMERGING_ISSUES_SCHEMA)
    spark.createDataFrame.return_value.write.mode.return_value.parquet.assert_called_once()


def test_cloud_storage_requires_configured_spark(monkeypatch: pytest.MonkeyPatch) -> None:
    read = Mock()
    monkeypatch.setattr(pd, "read_parquet", read)
    with pytest.raises(ValueError, match="spark="):
        run_streaming_emerging_issues_engine(StorageConfig(use_s3=True, s3_bucket="test-bucket"))
    read.assert_not_called()


def test_legacy_local_call_still_works(
    tmp_path: Path, silver_posts: pd.DataFrame, monkeypatch: pytest.MonkeyPatch,
) -> None:
    read = Mock(return_value=silver_posts)
    write = Mock()
    monkeypatch.setattr(pd, "read_parquet", read)
    monkeypatch.setattr(pd.DataFrame, "to_parquet", write)
    cfg = StorageConfig(use_s3=False, project_root=tmp_path)
    result = run_streaming_emerging_issues_engine(cfg)
    assert len(result) == 2
    read.assert_called_once()
    write.assert_called_once()
