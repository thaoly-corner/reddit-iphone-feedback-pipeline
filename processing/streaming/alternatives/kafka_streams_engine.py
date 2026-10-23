"""
Alternative Stream Anomaly Engine ('kafka_streams'):
Kafka Streams KTable StateStore for BR03 Emerging Issues Detection.
"""
import pandas as pd
from config.pipeline_config import StorageConfig
from processing.streaming.alternatives.apache_flink_engine import run_streaming_emerging_issues_engine


def run_kafka_streams_emerging_issues(storage_cfg: StorageConfig) -> pd.DataFrame:
    """Execute Kafka Streams KTable StateStore engine for BR03."""
    return run_streaming_emerging_issues_engine(storage_cfg, stream_engine="kafka_streams")
