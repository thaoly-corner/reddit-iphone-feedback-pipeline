"""
Module Thu nap va Xay dung Tang Bronze (Streaming Zstandard Decompression -> Parquet Snappy).
"""
import hashlib
import io
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pandas as pd
import zstandard as zstd


def stream_zst_json(path: Path | str) -> Iterator[dict[str, Any]]:
    """
    Doc file .zst chua NDJSON/JSONL theo streaming bang thu vien zstandard (window size = 2^31).
    Yield tung JSON object ma khong can giai nen toan bo tep tin ra o dia.
    """
    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    if path.stat().st_size == 0:
        raise ValueError(f"File is empty: {path}")

    
    dctx = zstd.ZstdDecompressor(max_window_size=2**31)
    with open(path, "rb") as compressed_file,\
        dctx.stream_reader(compressed_file) as reader,\
            io.TextIOWrapper(reader, encoding="utf-8", errors="replace") as text_stream:
        for line in text_stream:
            line = line.strip()

            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e} | Line: {line[:100]}...")
                continue


def extract_subreddit(
    input_path: Path | str,
    output_path: Path | str,
    subreddit: str = "iphone",
    progress_every: int = 1_000_000
) -> dict[str, int]:
    """
    Doc truc tiep stream cua du lieu Reddit goc (.zst) va loc ghi lai cac ban ghi
    thuoc ve mot subreddit cu the (mac dinh la 'iphone') vao file JSONL dich.
    """
    if not Path(input_path).is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if Path(input_path).stat().st_size == 0:
        raise ValueError(f"Input file is empty: {input_path}")

    if progress_every <= 0:
        raise ValueError("progress_every must be a positive integer")
    
    total = 0
    matched = 0
    missing_subreddit = 0
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as out:
        for record in stream_zst_json(input_path):
            total += 1
            sub = record.get("subreddit")
            if sub is None:
                missing_subreddit += 1
                continue
            if str(sub).strip().lower() == subreddit.lower():
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                matched += 1
            if total % progress_every == 0:
                print(f"Processed: {total:,} | Matched r/{subreddit}: {matched:,}")

    print("\n===== EXTRACTION COMPLETED =====")
    print(f"Total records: {total:,}")
    print(f"Matched r/{subreddit}: {matched:,}")
    print(f"Missing subreddit: {missing_subreddit:,}")
    if total > 0:
        print("Match rate:", round(matched / total * 100, 6), "%")

    return {
        "total_records": total,
        "matched_records": matched,
        "missing_subreddit": missing_subreddit
    }


def preview_jsonl(path: Path | str, n: int = 3) -> None:
    """Doc nhanh n ban ghi dau tien cua mot tep tin JSONL."""
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= n:
                break
            record = json.loads(line)
            print(json.dumps(record, indent=2, ensure_ascii=False))
            print("-" * 100)


def serialize_nested(value: Any) -> Any:
    """Tuan tu hoa cau truc long nhau (dict/list) sang chuoi JSON string de ghi xuong Parquet."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def sha256_file(path: Path | str, chunk_size: int = 1024 * 1024) -> str:
    """Tinh ma bam SHA256 cua tep tin dich de xac thuc tinh toan ven."""
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


def build_bronze_parquet(
    jsonl_path: Path | str,
    parquet_path: Path | str,
    ingest_source: str = "reddit_academic_torrents",
    ingest_period: str | None = None,
    ingest_scope: str = "r/iphone"
) -> dict[str, Any]:
    """
    Chuyen doi file JSONL da loc sang dinh dang Bronze Parquet (Snappy compression),
    tuan tu hoa cac cot nested JSON va bo sung Audit Metadata + kiem dinh SHA-256.
    """
    if not Path(jsonl_path).is_file():
        raise FileNotFoundError(f"JSONL file not found: {jsonl_path}")

    if Path(jsonl_path).stat().st_size == 0:
        raise ValueError(f"JSONL file is empty: {jsonl_path}")
    
    if ingest_period is None:
        raise ValueError("ingest_period is required, e.g. '2026-01'")

    jsonl_path = Path(jsonl_path)
    parquet_path = Path(parquet_path)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)

    bronze_posts = pd.read_json(jsonl_path, lines=True)

    if "id" not in bronze_posts.columns:
        raise ValueError("Bronze source does not contain required field: id")

    missing_id_count = int(bronze_posts["id"].isna().sum())
    duplicate_id_count = int(bronze_posts["id"].duplicated().sum())

    nested_columns: list[str] = []
    for column in bronze_posts.columns:
        has_nested = bronze_posts[column].apply(lambda x: isinstance(x, (dict, list))).any()
        if has_nested:
            nested_columns.append(column)
            bronze_posts[column] = bronze_posts[column].apply(serialize_nested)

    bronze_posts["_ingest_source"] = ingest_source
    bronze_posts["_ingest_period"] = ingest_period
    bronze_posts["_ingest_scope"] = ingest_scope
    bronze_posts["_ingested_at_utc"] = pd.Timestamp.now(tz="UTC")

    bronze_posts.to_parquet(
        parquet_path,
        engine="pyarrow",
        index=False,
        compression="snappy"
    )

    bronze_check = pd.read_parquet(parquet_path)
    expected_subreddit = (
        ingest_scope
        .strip()
        .removeprefix("r/")
        .lower()
    )
    if len(bronze_check) != len(bronze_posts):
        raise RuntimeError(
            "Row count mismatch after Parquet write"
        )
    if not (
        bronze_check["subreddit"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq(expected_subreddit)
        .all()
    ):
        raise RuntimeError(
            "Subreddit scope mismatch after Parquet write"
        )

    json_size_mb = jsonl_path.stat().st_size / (1024 ** 2)
    parquet_size_mb = parquet_path.stat().st_size / (1024 ** 2)
    compression_ratio = (1.0 - (parquet_size_mb / json_size_mb)) * 100.0 if json_size_mb > 0 else 0.0
    checksum = sha256_file(parquet_path)

    return {
        "rows": len(bronze_check),
        "columns": len(bronze_check.columns),
        "nested_columns": nested_columns,
        "json_size_mb": round(json_size_mb, 2),
        "parquet_size_mb": round(parquet_size_mb, 2),
        "compression_saving_pct": round(compression_ratio, 2),
        "sha256": checksum,
        "missing_id_count": missing_id_count,
        "duplicate_id_count": duplicate_id_count
    }
