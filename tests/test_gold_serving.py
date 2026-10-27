"""Exercise loader code with a mocked SQLAlchemy boundary, never a real DB."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, Mock

import pytest

from config.gold_marts import GOLD_MART_NAMES
from config.pipeline_config import DatabaseConfig, PipelineExecutionConfig, StorageConfig


@pytest.fixture
def adapter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    # SQLAlchemy may be absent locally; it is a declared Colab runtime dependency.
    sqlalchemy = ModuleType("sqlalchemy")
    sqlalchemy.create_engine = Mock(return_value=MagicMock())
    sqlalchemy.text = lambda sql: sql
    monkeypatch.setitem(sys.modules, "sqlalchemy", sqlalchemy)
    path = Path(__file__).resolve().parents[1] / "serving/database/postgres_loader.py"
    spec = importlib.util.spec_from_file_location("mocked_gold_loader", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    loader = module.UnifiedServingPipelineLoader(
        StorageConfig(use_s3=False, project_root=tmp_path),
        DatabaseConfig(use_sqlite_fallback=True, sqlite_path=":memory:"),
    )
    return loader


def test_all_ten_gold_tables_refreshed_and_counted(adapter, monkeypatch: pytest.MonkeyPatch) -> None:
    frame = MagicMock()
    frame.__len__.return_value = 2
    reader = Mock(return_value=frame)
    monkeypatch.setattr(adapter, "_read_gold_mart", reader)
    conn = adapter.engine.begin.return_value.__enter__.return_value
    conn.execute.return_value.scalar_one.return_value = 2
    counts = adapter.sync_gold_marts(spark=Mock())
    assert counts == {f"gold_{name}": 2 for name in GOLD_MART_NAMES}
    assert [call.args[0] for call in frame.to_sql.call_args_list] == list(counts)
    assert all(call.kwargs["if_exists"] == "replace" for call in frame.to_sql.call_args_list)


def test_serving_rejects_unregistered_table_names(adapter) -> None:
    with pytest.raises(ValueError, match="registered"):
        adapter.sync_gold_marts(mart_names=["issue_summary; DROP TABLE users"])
    adapter.engine.begin.assert_not_called()


def test_serving_row_count_mismatch_raises(adapter, monkeypatch: pytest.MonkeyPatch) -> None:
    frame = MagicMock()
    frame.__len__.return_value = 2
    monkeypatch.setattr(adapter, "_read_gold_mart", Mock(return_value=frame))
    adapter.engine.begin.return_value.__enter__.return_value.execute.return_value.scalar_one.return_value = 1
    with pytest.raises(RuntimeError, match="row count mismatch"):
        adapter.sync_gold_marts(mart_names=["support_demand"])


def test_s3_reads_use_configured_spark_session(adapter) -> None:
    adapter.storage_cfg = StorageConfig(use_s3=True, s3_bucket="test-bucket")
    with pytest.raises(ValueError, match="spark="):
        adapter._read_gold_mart("support_demand")
    spark = MagicMock()
    result = adapter._read_gold_mart("support_demand", spark)
    spark.read.parquet.assert_called_once_with("s3a://test-bucket/gold/support_demand")
    assert result is spark.read.parquet.return_value.toPandas.return_value


def test_postgres_legacy_obt_table_initialized(adapter) -> None:
    adapter.is_sqlite = False
    adapter.initialize_schema()
    statements = adapter.engine.begin.return_value.__enter__.return_value.execute.call_args_list
    assert any("CREATE TABLE IF NOT EXISTS obt_feedback_wide" in call.args[0] for call in statements)


def test_explicit_sqlite_backend_overrides_postgres_url(adapter) -> None:
    db_cfg = DatabaseConfig(host="db.invalid", user="test", use_sqlite_fallback=False, sqlite_path=":memory:")
    loader = type(adapter)(
        adapter.storage_cfg, db_cfg, PipelineExecutionConfig(serving_backend="sqlite_local"),
    )
    assert loader.is_sqlite
    assert loader.db_cfg.sqlalchemy_url == "sqlite:///:memory:"
