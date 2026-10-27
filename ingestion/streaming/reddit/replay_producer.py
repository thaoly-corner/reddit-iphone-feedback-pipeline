"""Replay real archived Reddit submissions into Kafka with bounded-memory reads."""
import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import io
import json
import logging
import os
from dotenv import load_dotenv
from pathlib import Path
import time
from collections.abc import Iterator

import zstandard

LOGGER = logging.getLogger(__name__)
POST_FIELDS = (
    "id", "created_utc", "title", "selftext", "author", "score",
    "num_comments", "upvote_ratio", "permalink", "subreddit",
    "crosspost_parent_list",
)


@dataclass
class ReplayMetrics:
    scanned: int = 0
    matched_subreddit: int = 0
    published: int = 0
    malformed_json: int = 0
    missing_id: int = 0
    publish_errors: int = 0
    elapsed_seconds: float = 0.0
    throughput_records_per_second: float = 0.0


def stream_archive(archive: str | Path, metrics: ReplayMetrics) -> Iterator[dict]:
    """Read JSONL incrementally; memory is bounded by the largest source line."""
    decompressor = zstandard.ZstdDecompressor(max_window_size=2**31)
    with open(archive, "rb") as source:
        with decompressor.stream_reader(source) as reader:
            # Decode whole lines, preserving characters split across decompression buffers.
            with io.BufferedReader(reader) as lines:
                for line in lines:
                    if not line.strip():
                        continue
                    metrics.scanned += 1
                    try:
                        record = json.loads(line)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        metrics.malformed_json += 1
                        continue
                    if not isinstance(record, dict):
                        metrics.malformed_json += 1
                        continue
                    yield record


def normalize_post(record: dict) -> dict:
    """Preserve source fields and include the downstream-required columns."""
    post = dict(record)
    for field in POST_FIELDS:
        post.setdefault(field, None)
    crosspost = post["crosspost_parent_list"]
    if isinstance(crosspost, (list, dict)):
        post["crosspost_parent_list"] = json.dumps(crosspost, ensure_ascii=False)
    return post


def build_envelope(post: dict) -> dict:
    return {
        "schema_version": 1,
        "entity_type": "post",
        "source": "archive_replay",
        "emitted_at_utc": datetime.now(timezone.utc).isoformat(),
        "data": post,
    }


class ReplayProducer:
    """Fixed-rate replay with one acknowledged send in flight; no exactly-once claim."""

    def __init__(
        self, bootstrap_servers: str = "localhost:9092", topic: str = "reddit.posts",
        rate_per_second: float = 1, *, producer=None,
        sleeper=time.sleep, clock=time.monotonic, delivery_timeout: float = 30,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.rate_per_second = rate_per_second
        self._producer = producer
        self._sleeper = sleeper
        self._clock = clock
        self.delivery_timeout = delivery_timeout

    def _get_producer(self):
        if self._producer is None:
            from kafka import KafkaProducer
            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                key_serializer=lambda key: key.encode("utf-8"),
                value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
                acks="all",
            )
        return self._producer

    def replay(self, archive: str | Path, limit: int | None = None) -> ReplayMetrics:
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative")
        metrics = ReplayMetrics()
        started = self._clock()
        producer = self._get_producer()
        next_send = None
        try:
            if limit != 0:
                records = stream_archive(archive, metrics)
                try:
                    for record in records:
                        if str(record.get("subreddit") or "").lower() != "iphone":
                            continue
                        metrics.matched_subreddit += 1
                        post_id = record.get("id")
                        if not isinstance(post_id, str) or not post_id.strip():
                            metrics.missing_id += 1
                            continue
                        if self.rate_per_second > 0 and next_send is not None:
                            delay = next_send - self._clock()
                            if delay > 0:
                                self._sleeper(delay)
                        if self.rate_per_second > 0:
                            next_send = self._clock() + 1 / self.rate_per_second
                        try:
                            producer.send(
                                self.topic, key=post_id,
                                value=build_envelope(normalize_post(record)),
                            ).get(timeout=self.delivery_timeout)
                        except Exception:
                            # Delivery timeouts can have an unknown broker outcome.
                            metrics.publish_errors += 1
                            LOGGER.warning("Publish failed or unconfirmed for post %s", post_id)
                            continue
                        metrics.published += 1
                        if limit is not None and metrics.published >= limit:
                            break
                finally:
                    records.close()
        finally:
            try:
                producer.flush(timeout=self.delivery_timeout)
            finally:
                metrics.elapsed_seconds = max(0.0, self._clock() - started)
                metrics.throughput_records_per_second = (
                    metrics.published / metrics.elapsed_seconds if metrics.elapsed_seconds else 0.0
                )
                LOGGER.info("Replay summary: %s", json.dumps(asdict(metrics)))
        return metrics


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--bootstrap-servers", default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"))
    parser.add_argument("--topic", default=os.getenv("KAFKA_TOPIC", "reddit.posts"))
    parser.add_argument("--rate", type=float, default=1)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    replay = ReplayProducer(args.bootstrap_servers, args.topic, args.rate)
    try:
        replay.replay(args.archive, args.limit)
    finally:
        if replay._producer is not None:
            replay._producer.close(timeout=replay.delivery_timeout)


if __name__ == "__main__":
    main()
