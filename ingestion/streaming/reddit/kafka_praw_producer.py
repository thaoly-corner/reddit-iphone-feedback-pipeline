"""
Real-time Streaming Producer thu thap bai dang moi tu Reddit API (PRAW) hoac Replay Buffer day vao Apache Kafka.
"""
import json
import time
from typing import Iterable, Dict, Any, Optional


class RedditKafkaStreamingProducer:
    """Producer day su kien Reddit VoC vao Apache Kafka phuc vu Speed Layer & Benchmark."""

    def __init__(self, bootstrap_servers: str = "localhost:9092", topic: str = "reddit.posts.raw"):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self._producer = None

    def _init_kafka(self) -> None:
        if self._producer is None:
            from kafka import KafkaProducer
            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                key_serializer=lambda k: k.encode("utf-8"),
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
                acks="all",
                compression_type="snappy"
            )

    def publish_records(self, records: Iterable[Dict[str, Any]], rate_limit_per_sec: Optional[int] = None) -> int:
        """Day luong ban ghi vao Kafka topic voi khoa phan vung theo subreddit."""
        self._init_kafka()
        sent_count = 0
        start_ts = time.perf_counter()

        for record in records:
            sub_key = str(record.get("subreddit", "iphone")).lower()
            payload = dict(record)
            payload["_ingest_source"] = "reddit_api_kafka"
            payload["_event_emitted_epoch_ms"] = int(time.time() * 1000)
            self._producer.send(self.topic, key=sub_key, value=payload)
            sent_count += 1

            if rate_limit_per_sec and sent_count % rate_limit_per_sec == 0:
                elapsed = time.perf_counter() - start_ts
                if elapsed < 1.0:
                    time.sleep(1.0 - elapsed)
                start_ts = time.perf_counter()

        self._producer.flush()
        return sent_count
