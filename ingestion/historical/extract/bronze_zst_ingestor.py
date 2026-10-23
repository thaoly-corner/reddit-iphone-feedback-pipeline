"""
Module Thu nap va Xay dung Tang Bronze (Streaming Zstandard Decompression -> Parquet Snappy).
"""
from pathlib import Path
from typing import Dict, Iterator, Any, List
import json
import hashlib
import pandas as pd
import zstandard as zstd


def stream_zst_json(path: Path | str, chunk_size: int = 1024 * 1024) -> Iterator[Dict[str, Any]]:
    """
    Doc file .zst chua NDJSON/JSONL theo streaming bang thu vien zstandard (window size = 2^31).
    Yield tung JSON object ma khong can giai nen toan bo tep tin ra o dia.
    """
    dctx = zstd.ZstdDecompressor(max_window_size=2**31)
    with open(path, "rb") as compressed_file:
        with dctx.stream_reader(compressed_file) as reader:
            buffer = ""
            while True:
                chunk = reader.read(chunk_size)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")
                lines = buffer.split("\n")
                buffer = lines.pop()
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
            if buffer.strip():
                try:
                    yield json.loads(buffer)
                except json.JSONDecodeError:
                    pass


def extract_subreddit(
    input_path: Path | str,
    output_path: Path | str,
    subreddit: str = "iphone",
    progress_every: int = 1_000_000
) -> Dict[str, int]:
    """
    Doc truc tiep stream cua du lieu Reddit goc (.zst) va loc ghi lai cac ban ghi
    thuoc ve mot subreddit cu the (mac dinh la 'iphone') vao file JSONL dich.
    """
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
    ingest_period: str = "2026-07",
    ingest_scope: str = "r/iphone"
) -> Dict[str, Any]:
    """
    Chuyen doi file JSONL da loc sang dinh dang Bronze Parquet (Snappy compression),
    tuan tu hoa cac cot nested JSON va bo sung Audit Metadata + kiem dinh SHA-256.
    """
    jsonl_path = Path(jsonl_path)
    parquet_path = Path(parquet_path)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)

    bronze_posts = pd.read_json(jsonl_path, lines=True)

    nested_columns: List[str] = []
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
    assert len(bronze_check) == len(bronze_posts), "Row count mismatch after Parquet write!"
    assert bronze_check["id"].duplicated().sum() == 0, "Duplicate IDs detected in Bronze Parquet!"
    assert bronze_check["subreddit"].str.lower().eq(ingest_scope.replace("r/", "").lower()).all(), "Subreddit scope mismatch!"

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
        "sha256": checksum
    }
