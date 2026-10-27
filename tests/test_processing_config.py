"""Storage and database configuration checks; no Spark or external services."""

from pathlib import Path

import pytest
from dotenv import load_dotenv

from config.pipeline_config import DatabaseConfig, StorageConfig
from config.spark_storage import build_s3a_options, detect_hadoop_version


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "USE_S3", "S3_PROVIDER", "S3_BUCKET", "S3_BUCKET_NAME", "S3_ENDPOINT",
        "S3_ACCESS_KEY", "S3_SECRET_KEY", "AWS_DEFAULT_REGION", "RAW_DIR", "HISTORICAL_WORK_DIR",
        "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_SSLMODE",
        "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD",
        "USE_SQLITE_FALLBACK", "SQLITE_PATH",
    ):
        monkeypatch.delenv(name, raising=False)


def test_env_is_read_after_import(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(f"USE_S3=false\nHISTORICAL_WORK_DIR={tmp_path}\nRAW_DIR={tmp_path}/raw\n")
    # The classes were imported before this dotenv load.
    with pytest.MonkeyPatch.context() as patch:
        for name in ("USE_S3", "HISTORICAL_WORK_DIR", "RAW_DIR"):
            patch.setenv(name, "")
            patch.delenv(name, raising=False)
        load_dotenv(env)
        cfg = StorageConfig()
        assert not cfg.use_s3
        assert cfg.project_root == tmp_path
        assert cfg.raw_local_dir == tmp_path / "raw"
        assert cfg.bronze_posts_path == str(tmp_path / "parquet")
        assert cfg.bronze_posts_parquet == cfg.bronze_posts_path


@pytest.mark.parametrize("bucket", ["test-bucket", "s3://test-bucket", "s3a://test-bucket/"])
def test_multi_month_paths_and_legacy_alias(bucket: str) -> None:
    cfg = StorageConfig(use_s3=True, s3_bucket=bucket)
    assert cfg.bronze_posts_path == "s3a://test-bucket/bronze/posts"
    assert cfg.bronze_posts_parquet == cfg.bronze_posts_path
    assert cfg.silver_posts_path == "s3a://test-bucket/silver/posts"
    assert cfg.gold_base_path == "s3a://test-bucket/gold"


def test_anonymous_aws_options() -> None:
    cfg = StorageConfig(use_s3=True, s3_bucket="test-bucket")
    options = build_s3a_options(cfg, "3.5.0")
    assert "hadoop-aws:3.5.0" in options["spark.jars.packages"]
    assert "aws-java-sdk" not in options["spark.jars.packages"]
    assert options["spark.hadoop.fs.s3a.aws.credentials.provider"].endswith("AnonymousAWSCredentialsProvider")
    assert "spark.hadoop.fs.s3a.access.key" not in options
    assert "localhost" not in options["spark.hadoop.fs.s3a.endpoint"]


def test_minio_options() -> None:
    cfg = StorageConfig(use_s3=True, s3_provider="minio", s3_bucket="test-lake",
                        s3_endpoint="http://minio:9000", s3_access_key="test-key", s3_secret_key="test-secret")
    options = build_s3a_options(cfg, "3.3.4")
    assert options["spark.hadoop.fs.s3a.aws.credentials.provider"].endswith("SimpleAWSCredentialsProvider")
    assert options["spark.hadoop.fs.s3a.endpoint"] == "http://minio:9000"
    assert options["spark.hadoop.fs.s3a.path.style.access"] == "true"
    assert options["spark.hadoop.fs.s3a.connection.ssl.enabled"] == "false"
    assert options["spark.hadoop.fs.s3a.access.key"] == "test-key"


def test_local_needs_no_s3_configuration() -> None:
    assert build_s3a_options(StorageConfig(use_s3=False), "unused") == {}


def test_hadoop_jar_detection_and_mismatch(tmp_path: Path) -> None:
    (tmp_path / "hadoop-client-api-3.5.0.jar").touch()
    assert detect_hadoop_version(tmp_path) == "3.5.0"
    (tmp_path / "hadoop-aws-3.3.4.jar").touch()
    with pytest.raises(RuntimeError, match="does not match"):
        detect_hadoop_version(tmp_path)


def test_unknown_hadoop_version_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="Cannot determine"):
        detect_hadoop_version(tmp_path)


def test_postgres_environment_and_password_escaping(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in {"DB_HOST": "db.example.invalid", "DB_USER": "user@course",
                       "DB_PASSWORD": "p@ss:/word", "DB_NAME": "feedback", "DB_SSLMODE": "require"}.items():
        monkeypatch.setenv(key, value)
    cfg = DatabaseConfig()
    assert not cfg.use_sqlite_fallback
    assert cfg.sqlalchemy_url == (
        "postgresql+psycopg2://user%40course:p%40ss%3A%2Fword@db.example.invalid:5432/feedback?sslmode=require"
    )
    assert "p@ss" not in repr(cfg)


def test_legacy_postgres_variables_and_primary_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "legacy.invalid")
    monkeypatch.setenv("POSTGRES_USER", "legacy-user")
    assert DatabaseConfig().host == "legacy.invalid"
    monkeypatch.setenv("DB_HOST", "primary.invalid")
    assert DatabaseConfig().host == "primary.invalid"


def test_sqlite_development_fallback() -> None:
    cfg = DatabaseConfig()
    assert cfg.use_sqlite_fallback
    assert cfg.sqlalchemy_url.startswith("sqlite:///")


def test_postgres_missing_user_fails_without_connection() -> None:
    with pytest.raises(ValueError, match="DB_USER"):
        _ = DatabaseConfig(use_sqlite_fallback=False).sqlalchemy_url
