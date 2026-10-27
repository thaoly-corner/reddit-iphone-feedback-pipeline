"""Mock all runtime stages so tests need no Spark, model or database runtime."""

import sys
from types import ModuleType
from unittest.mock import MagicMock, Mock

import pytest

from config.gold_marts import GOLD_MART_NAMES
from scripts import run_pipeline


@pytest.fixture
def stages(monkeypatch: pytest.MonkeyPatch):
    stages = Mock()
    stages.spark = MagicMock()
    stages.build_spark.return_value = stages.spark
    stages.gold.return_value = dict.fromkeys(GOLD_MART_NAMES)
    stages.loader.return_value.engine = MagicMock()
    for path, attr, function in (
        ("processing.batch.bronze_to_silver.spark_cleaner", "build_spark_session", stages.build_spark),
        ("processing.batch.enrichment.silver_enrichment", "run_silver_pipeline", stages.silver),
        ("processing.batch.silver_to_gold.gold_datamarts", "build_gold_datamarts", stages.gold),
        ("serving.database.postgres_loader", "UnifiedServingPipelineLoader", stages.loader),
    ):
        module = ModuleType(path)
        setattr(module, attr, function)
        monkeypatch.setitem(sys.modules, path, module)
    monkeypatch.setenv("USE_S3", "false")
    monkeypatch.setattr(run_pipeline, "load_dotenv", Mock())
    return stages


def test_default_production_options() -> None:
    args = run_pipeline.parse_args([])
    assert args.stage == "all"
    assert args.silver_engine == "pyspark_roberta"
    assert args.batch_gold_engine == "spark_sql"
    assert args.stream_engine == "apache_flink"
    assert args.serving_backend == "postgres"
    assert args.schema_paradigm == "galaxy"


@pytest.mark.parametrize("stage", ["silver", "gold", "serving", "all"])
def test_stages_are_independent_and_use_existing_bronze(stages, stage: str) -> None:
    run_pipeline.main(["--stage", stage])
    assert stages.silver.call_count == (stage in {"silver", "all"})
    assert stages.gold.call_count == (stage in {"gold", "all"})
    assert stages.loader.call_count == (stage in {"serving", "all"})
    if stage in {"serving", "all"}:
        loader = stages.loader.return_value
        loader.sync_dimensions_and_facts.assert_called_once_with(spark=stages.spark)
        loader.sync_gold_marts.assert_called_once_with(spark=stages.spark)
        loader.engine.dispose.assert_called_once()
    if stage in {"gold", "all"}:
        assert stages.gold.call_args.kwargs["exec_cfg"].stream_engine == "apache_flink"
    stages.spark.stop.assert_called_once()


def test_failure_stops_spark(stages) -> None:
    stages.gold.side_effect = RuntimeError("Gold failed")
    with pytest.raises(RuntimeError, match="Gold failed"):
        run_pipeline.main(["--stage", "gold"])
    stages.spark.stop.assert_called_once()
    stages.loader.assert_not_called()
