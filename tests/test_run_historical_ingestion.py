"""Runner tests with mocked ingestion functions and S3; no external services."""

from pathlib import Path
from unittest.mock import Mock, call

import pytest
from botocore import UNSIGNED
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from ingestion.historical import run_historical_ingestion as runner


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "TORRENT_DIR", "RAW_DIR", "HISTORICAL_WORK_DIR", "S3_BUCKET", "AWS_DEFAULT_REGION",
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(runner, "load_dotenv", Mock())


@pytest.fixture
def cli_args(tmp_path: Path) -> list[str]:
    return [
        "--year", "2026", "--month", "1",
        "--torrent-dir", str(tmp_path / "torrents"),
        "--raw-dir", str(tmp_path / "raw"),
        "--work-dir", str(tmp_path / "work"),
    ]


@pytest.fixture
def stages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Mock:
    stages = Mock()
    stages.download.return_value = tmp_path / "raw" / "RS_2026-01.zst"

    def extract(**kwargs: object) -> dict[str, int]:
        path = kwargs["output_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"id": "a", "subreddit": "iphone"}\n')
        return {"matched_records": 1}

    def build(**kwargs: object) -> dict[str, int]:
        path = kwargs["parquet_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"mock parquet")
        return {"rows": 1}

    stages.extract.side_effect = extract
    stages.bronze.side_effect = build
    for function, mock in (
        ("download_reddit_archive", stages.download),
        ("extract_subreddit", stages.extract),
        ("profile_filtered_posts", stages.profile),
        ("build_bronze_parquet", stages.bronze),
        ("upload_bronze_to_s3", stages.upload),
    ):
        monkeypatch.setattr(runner, function, mock)
    return stages


def test_cli_overrides_environment(cli_args: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("TORRENT_DIR", "RAW_DIR", "HISTORICAL_WORK_DIR"):
        monkeypatch.setenv(name, f"/environment/{name.lower()}")
    monkeypatch.setenv("S3_BUCKET", "environment-bucket")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "environment-region")

    config = runner.resolve_config(runner.build_parser().parse_args(
        cli_args + ["--bucket", "cli-bucket", "--region", "cli-region", "--upload-s3"]
    ))

    assert config.torrent_dir == Path(cli_args[5])
    assert config.raw_dir == Path(cli_args[7])
    assert config.work_dir == Path(cli_args[9])
    assert config.bucket == "cli-bucket"
    assert config.region == "cli-region"


def test_environment_used_when_cli_options_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TORRENT_DIR", "/env/torrents")
    monkeypatch.setenv("RAW_DIR", "/env/raw")
    monkeypatch.setenv("HISTORICAL_WORK_DIR", "/env/work")
    monkeypatch.setenv("S3_BUCKET", "env-bucket")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "env-region")
    config = runner.resolve_config(runner.build_parser().parse_args(
        ["--year", "2026", "--month", "1", "--upload-s3"]
    ))
    assert (config.torrent_dir, config.raw_dir, config.work_dir) == (
        Path("/env/torrents"), Path("/env/raw"), Path("/env/work"),
    )
    assert config.bucket == "env-bucket"
    assert config.region == "env-region"


def test_main_loads_dotenv_before_resolving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "TORRENT_DIR=/dotenv/torrents\nRAW_DIR=/dotenv/raw\nHISTORICAL_WORK_DIR=/dotenv/work\n"
    )
    loader = Mock(side_effect=lambda: load_dotenv(dotenv_path))
    run = Mock(return_value=tmp_path / "result.parquet")
    monkeypatch.setattr(runner, "load_dotenv", loader)
    monkeypatch.setattr(runner, "run_historical_ingestion", run)
    result = runner.main(["--year", "2026", "--month", "1", "--raw-dir", "/cli/raw"])
    loader.assert_called_once_with()
    config = run.call_args.args[0]
    assert config.torrent_dir == Path("/dotenv/torrents")
    assert config.raw_dir == Path("/cli/raw")
    assert config.work_dir == Path("/dotenv/work")
    assert result == tmp_path / "result.parquet"


@pytest.mark.parametrize(
    ("options", "missing"),
    [
        ([], "TORRENT_DIR"),
        (["--torrent-dir", "/torrents"], "RAW_DIR"),
        (["--torrent-dir", "/torrents", "--raw-dir", "/raw"], "HISTORICAL_WORK_DIR"),
    ],
)
def test_missing_local_configuration(options: list[str], missing: str) -> None:
    args = runner.build_parser().parse_args(["--year", "2026", "--month", "1"] + options)
    with pytest.raises(ValueError, match=missing):
        runner.resolve_config(args)


@pytest.mark.parametrize(("flag", "value"), [("--year", "0"), ("--year", "10000"), ("--month", "0"), ("--month", "13")])
def test_invalid_date_fails_before_download(
    cli_args: list[str], stages: Mock, flag: str, value: str,
) -> None:
    args = runner.build_parser().parse_args(cli_args + [flag, value])
    with pytest.raises(ValueError, match=flag.removeprefix("--")):
        runner.resolve_config(args)
    stages.download.assert_not_called()


def test_submissions_flow_and_upload_skipped(
    cli_args: list[str], tmp_path: Path, stages: Mock,
) -> None:
    result = runner.main(cli_args)
    partition = Path("year=2026/month=01")
    filtered = tmp_path / "work/filtered" / partition / "iphone_posts_2026_01.jsonl"
    parquet = tmp_path / "work/parquet" / partition / "iphone_posts_2026_01.parquet"
    assert result == parquet
    assert filtered.is_file()
    assert stages.mock_calls == [
        call.download(torrent_dir=tmp_path / "torrents", output_dir=tmp_path / "raw",
                      year=2026, month=1, data_type="submissions"),
        call.extract(input_path=stages.download.return_value, output_path=filtered, subreddit="iphone"),
        call.profile(jsonl_path=filtered, profile_dir=tmp_path / "work/profiling", year=2026, month=1),
        call.bronze(jsonl_path=filtered, parquet_path=parquet,
                    ingest_source="reddit_academic_torrents", ingest_period="2026-01", ingest_scope="r/iphone"),
    ]
    stages.upload.assert_not_called()


def test_zero_matches_stops_processing(cli_args: list[str], stages: Mock) -> None:
    stages.extract.side_effect = None
    stages.extract.return_value = {"matched_records": 0}
    with pytest.raises(ValueError, match="No records matched r/iphone for 2026-01"):
        runner.main(cli_args)
    stages.profile.assert_not_called()
    stages.bronze.assert_not_called()
    stages.upload.assert_not_called()


def test_bucket_required_only_for_upload(cli_args: list[str]) -> None:
    parser = runner.build_parser()
    assert runner.resolve_config(parser.parse_args(cli_args)).bucket is None
    with pytest.raises(ValueError, match="S3_BUCKET"):
        runner.resolve_config(parser.parse_args(cli_args + ["--upload-s3"]))


@pytest.mark.parametrize("env_region", [None, "", "   "])
def test_default_region_for_upload(
    cli_args: list[str], monkeypatch: pytest.MonkeyPatch, env_region: str | None,
) -> None:
    if env_region is not None:
        monkeypatch.setenv("AWS_DEFAULT_REGION", env_region)
    config = runner.resolve_config(runner.build_parser().parse_args(
        cli_args + ["--upload-s3", "--bucket", "test-bucket"]
    ))
    assert config.region == "ap-southeast-1"


@pytest.mark.parametrize(
    ("value", "expected"),
    [("R/iPhone", "iphone"), (" r/Apple-Test ", "apple-test"), ("APPLE_TEST", "apple_test")],
)
def test_subreddit_normalization(cli_args: list[str], value: str, expected: str) -> None:
    config = runner.resolve_config(runner.build_parser().parse_args(
        cli_args + ["--subreddit", value]
    ))
    assert config.subreddit == expected


@pytest.mark.parametrize("value", ["", "R/", "../iphone", "r/iphone/extra", "iphone test"])
def test_invalid_subreddit(cli_args: list[str], value: str) -> None:
    with pytest.raises(ValueError, match="subreddit"):
        runner.resolve_config(runner.build_parser().parse_args(
            cli_args + ["--subreddit", value]
        ))


def test_upload_key_and_cleanup(cli_args: list[str], tmp_path: Path, stages: Mock) -> None:
    result = runner.main(cli_args + [
        "--upload-s3", "--bucket", "test-bucket", "--region", "ap-southeast-1",
        "--delete-filtered-jsonl", "--subreddit", "R/Apple",
    ])
    assert result.name == "apple_posts_2026_01.parquet"
    stages.upload.assert_called_once_with(
        result, "test-bucket", "bronze/posts/year=2026/month=01/apple_posts_2026_01.parquet", "ap-southeast-1",
    )
    assert stages.bronze.call_args.kwargs["ingest_scope"] == "r/apple"
    assert not (tmp_path / "work/filtered/year=2026/month=01/apple_posts_2026_01.jsonl").exists()


@pytest.mark.parametrize("failure_stage", ["bronze", "upload"])
def test_failure_preserves_filtered_jsonl(
    cli_args: list[str], tmp_path: Path, stages: Mock, failure_stage: str,
) -> None:
    getattr(stages, failure_stage).side_effect = RuntimeError("stage failed")
    with pytest.raises(RuntimeError, match="stage failed"):
        runner.main(cli_args + [
            "--upload-s3", "--bucket", "test-bucket", "--region", "ap-southeast-1",
            "--delete-filtered-jsonl",
        ])
    assert (tmp_path / "work/filtered/year=2026/month=01/iphone_posts_2026_01.jsonl").is_file()


def test_unsigned_s3_upload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    local = tmp_path / "bronze.parquet"
    local.touch()
    factory = Mock()
    monkeypatch.setattr(runner, "client", factory)
    uri = runner.upload_bronze_to_s3(local, "test-bucket", "bronze/posts/file.parquet", "ap-southeast-1")
    assert factory.call_args.args == ("s3",)
    assert set(factory.call_args.kwargs) == {"region_name", "config"}
    assert factory.call_args.kwargs["region_name"] == "ap-southeast-1"
    assert factory.call_args.kwargs["config"].signature_version is UNSIGNED
    assert factory.return_value.mock_calls == [
        call.upload_file(str(local), "test-bucket", "bronze/posts/file.parquet"),
        call.head_object(Bucket="test-bucket", Key="bronze/posts/file.parquet"),
    ]
    assert uri == "s3://test-bucket/bronze/posts/file.parquet"


def test_s3_rejects_missing_local_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    factory = Mock()
    monkeypatch.setattr(runner, "client", factory)
    with pytest.raises(FileNotFoundError, match="Bronze Parquet not found"):
        runner.upload_bronze_to_s3(tmp_path / "missing.parquet", "bucket", "key", "region")
    factory.assert_not_called()


@pytest.mark.parametrize("code", ["403", "AccessDenied", "Forbidden", "404", "InternalError"])
def test_s3_head_permission_warning_or_unexpected_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], code: str,
) -> None:
    local = tmp_path / "bronze.parquet"
    local.touch()
    s3 = Mock()
    s3.head_object.side_effect = ClientError({"Error": {"Code": code}}, "HeadObject")
    monkeypatch.setattr(runner, "client", Mock(return_value=s3))
    if code in {"403", "AccessDenied", "Forbidden"}:
        runner.upload_bronze_to_s3(local, "bucket", "key", "region")
        assert "Warning:" in capsys.readouterr().out
    else:
        with pytest.raises(ClientError):
            runner.upload_bronze_to_s3(local, "bucket", "key", "region")
    s3.upload_file.assert_called_once()


def test_s3_upload_failure_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    local = tmp_path / "bronze.parquet"
    local.touch()
    s3 = Mock()
    s3.upload_file.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject")
    monkeypatch.setattr(runner, "client", Mock(return_value=s3))
    with pytest.raises(ClientError):
        runner.upload_bronze_to_s3(local, "bucket", "key", "region")
    s3.head_object.assert_not_called()
