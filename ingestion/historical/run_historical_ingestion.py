"""Run one monthly job with python -m ingestion.historical.run_historical_ingestion."""

import argparse
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, overload

from boto3 import client
from botocore import UNSIGNED
from botocore.client import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from ingestion.historical.download.torrent_downloader import (
    build_archive_filename,
    download_reddit_archive,
)
from ingestion.historical.extract.bronze_zst_ingestor import (
    build_bronze_parquet,
    extract_subreddit,
)
from ingestion.historical.profiling.data_profiler import profile_filtered_posts


@dataclass(frozen=True)
class HistoricalIngestionConfig:
    year: int
    month: int
    data_type: str
    subreddit: str
    torrent_dir: Path
    raw_dir: Path
    work_dir: Path | None
    bucket: str | None
    region: str
    upload_s3: bool
    delete_filtered_jsonl: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest one month of historical Reddit data")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--data-type", choices=["submissions", "comments"], default="submissions")
    parser.add_argument("--subreddit", default="iphone")
    parser.add_argument("--torrent-dir", help="Overrides TORRENT_DIR")
    parser.add_argument("--raw-dir", help="Overrides RAW_DIR")
    parser.add_argument("--work-dir", help="Overrides HISTORICAL_WORK_DIR; required for submissions")
    parser.add_argument("--bucket", help="Overrides S3_BUCKET; needed for S3 upload")
    parser.add_argument("--region", help="Overrides AWS_DEFAULT_REGION; defaults to ap-southeast-1")
    parser.add_argument("--upload-s3", action="store_true", help="Upload submissions Bronze Parquet to S3")
    parser.add_argument(
        "--delete-filtered-jsonl", action="store_true",
        help="Delete filtered submissions after Bronze creation and any requested upload succeed",
    )
    return parser


@overload
def _setting(value: str | None, env_name: str, flag: str, *, required: Literal[True] = True) -> str: ...


@overload
def _setting(value: str | None, env_name: str, flag: str, *, required: Literal[False]) -> str | None: ...


def _setting(value: str | None, env_name: str, flag: str, *, required: bool = True) -> str | None:
    resolved = value if value is not None else os.getenv(env_name)
    if resolved is not None and resolved.strip():
        return resolved.strip()
    if required:
        raise ValueError(f"Missing {env_name}: pass {flag} or set {env_name} in environment/.env")
    return None


def resolve_config(args: argparse.Namespace) -> HistoricalIngestionConfig:
    """Resolve CLI > environment/.env and validate before starting a download."""
    build_archive_filename(args.year, args.month, args.data_type)
    subreddit = args.subreddit.strip().lower()
    subreddit = subreddit.removeprefix("r/")
    if not re.fullmatch(r"[a-z0-9_-]+", subreddit):
        raise ValueError("subreddit must be a nonempty Reddit community name, e.g. iphone")

    torrent_dir = _setting(args.torrent_dir, "TORRENT_DIR", "--torrent-dir")
    raw_dir = _setting(args.raw_dir, "RAW_DIR", "--raw-dir")
    work_dir = _setting(
        args.work_dir, "HISTORICAL_WORK_DIR", "--work-dir",
        required=args.data_type == "submissions",
    )
    torrent_path = Path(torrent_dir).expanduser()

    # Comments jobs only download; upload and cleanup options apply to submissions.
    if args.data_type == "comments":
        if args.upload_s3:
            raise ValueError(
                "--upload-s3 is currently supported only for submissions"
            )

        if args.delete_filtered_jsonl:
            raise ValueError(
                "--delete-filtered-jsonl only applies to submissions"
            )
    upload_s3 = args.upload_s3
    bucket = _setting(args.bucket, "S3_BUCKET", "--bucket", required=upload_s3)
    region = _setting(args.region, "AWS_DEFAULT_REGION", "--region", required=False) or "ap-southeast-1"

    return HistoricalIngestionConfig(
        year=args.year,
        month=args.month,
        data_type=args.data_type,
        subreddit=subreddit,
        torrent_dir=torrent_path.expanduser(),
        raw_dir=Path(raw_dir).expanduser(),
        work_dir=Path(work_dir).expanduser() if work_dir else None,
        bucket=bucket,
        region=region,
        upload_s3=upload_s3,
        delete_filtered_jsonl=args.delete_filtered_jsonl,
    )


def upload_bronze_to_s3(local_path: Path | str, bucket: str, key: str, region: str) -> str:
    """Upload anonymously; a denied HEAD does not invalidate a successful upload."""
    local_path = Path(local_path)
    if not local_path.is_file():
        raise FileNotFoundError(f"Bronze Parquet not found: {local_path}")

    s3 = client("s3", region_name=region, config=Config(signature_version=UNSIGNED))
    s3.upload_file(str(local_path), bucket, key)
    try:
        s3.head_object(Bucket=bucket, Key=key)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") not in {"403", "AccessDenied", "Forbidden"}:
            raise
        print(f"Warning: uploaded s3://{bucket}/{key}, but anonymous HeadObject is not allowed")
    return f"s3://{bucket}/{key}"


def run_historical_ingestion(config: HistoricalIngestionConfig) -> Path:
    """Download comments, or filter/profile/build and optionally upload submissions."""
    archive_path = download_reddit_archive(
        torrent_dir=config.torrent_dir,
        output_dir=config.raw_dir,
        year=config.year,
        month=config.month,
        data_type=config.data_type,
    )
    if config.data_type == "comments":
        print(f"Downloaded comments: {archive_path}")
        return archive_path

    if config.work_dir is None:
        raise ValueError("HISTORICAL_WORK_DIR is required for submissions")
    partition = Path(f"year={config.year:04d}") / f"month={config.month:02d}"
    stem = f"{config.subreddit}_posts_{config.year:04d}_{config.month:02d}"
    filtered_path = config.work_dir / "filtered" / partition / f"{stem}.jsonl"
    parquet_path = config.work_dir / "parquet" / partition / f"{stem}.parquet"

    extraction = extract_subreddit(
        input_path=archive_path, output_path=filtered_path, subreddit=config.subreddit,
    )
    if extraction["matched_records"] == 0:
        raise ValueError(
            f"No records matched r/{config.subreddit} for {config.year:04d}-{config.month:02d}"
        )
    profile_filtered_posts(
        jsonl_path=filtered_path,
        profile_dir=config.work_dir / "profiling",
        year=config.year,
        month=config.month,
    )
    build_bronze_parquet(
        jsonl_path=filtered_path,
        parquet_path=parquet_path,
        ingest_source="reddit_academic_torrents",
        ingest_period=f"{config.year:04d}-{config.month:02d}",
        ingest_scope=f"r/{config.subreddit}",
    )
    if not parquet_path.is_file():
        raise FileNotFoundError(f"Bronze builder did not create Parquet: {parquet_path}")
    print(f"Bronze Parquet: {parquet_path}")

    if config.upload_s3:
        if config.bucket is None:
            raise ValueError("S3 bucket and region are required for upload")
        key = f"bronze/posts/{partition.as_posix()}/{parquet_path.name}"
        uploaded_uri = upload_bronze_to_s3(parquet_path, config.bucket, key, config.region)
        print(f"Uploaded Bronze Parquet: {uploaded_uri}")
    if config.delete_filtered_jsonl:
        filtered_path.unlink()
        print(f"Deleted filtered JSONL: {filtered_path}")
    return parquet_path


def main(argv: Sequence[str] | None = None) -> Path:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = resolve_config(args)
    except ValueError as error:
        parser.error(str(error))
    return run_historical_ingestion(config)


if __name__ == "__main__":
    main()
