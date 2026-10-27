"""Build S3A settings without starting Spark or contacting object storage."""

import re
from pathlib import Path

from config.pipeline_config import StorageConfig


def detect_hadoop_version(jars_dir: Path) -> str:
    """Use the installed Spark distribution's Hadoop version, never a fixed guess."""
    versions = set()
    for path in jars_dir.glob("hadoop-*.jar"):
        match = re.fullmatch(r"hadoop-(?:client-api|common)-(.+)\.jar", path.name)
        if match:
            versions.add(match.group(1))
    if len(versions) != 1:
        raise RuntimeError(
            f"Cannot determine one Hadoop version from {jars_dir}: {sorted(versions)}. "
            "Use a Spark distribution with matching Hadoop and hadoop-aws JARs."
        )
    version = versions.pop()
    for path in jars_dir.glob("hadoop-aws-*.jar"):
        if path.name != f"hadoop-aws-{version}.jar":
            raise RuntimeError(f"{path.name} does not match Hadoop {version}")
    return version


def build_s3a_options(storage_cfg: StorageConfig, hadoop_version: str) -> dict[str, str]:
    """Let hadoop-aws's Maven dependencies select its matching AWS SDK bundle."""
    if not storage_cfg.use_s3:
        return {}
    if not storage_cfg.s3_bucket:
        raise ValueError("S3_BUCKET is required when use_s3=True")
    options = {
        "spark.jars.packages": (
            f"org.apache.hadoop:hadoop-aws:{hadoop_version},org.postgresql:postgresql:42.7.3"
        ),
        "spark.hadoop.fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",
    }
    if storage_cfg.s3_provider == "aws":
        options.update({
            "spark.hadoop.fs.s3a.aws.credentials.provider": "org.apache.hadoop.fs.s3a.AnonymousAWSCredentialsProvider",
            "spark.hadoop.fs.s3a.endpoint.region": storage_cfg.aws_region,
            "spark.hadoop.fs.s3a.endpoint": f"s3.{storage_cfg.aws_region}.amazonaws.com",
            "spark.hadoop.fs.s3a.path.style.access": "false",
            "spark.hadoop.fs.s3a.connection.ssl.enabled": "true",
        })
    elif storage_cfg.s3_provider == "minio":
        if not storage_cfg.s3_endpoint or not storage_cfg.s3_access_key or not storage_cfg.s3_secret_key:
            raise ValueError("MinIO requires S3_ENDPOINT, S3_ACCESS_KEY and S3_SECRET_KEY")
        options.update({
            "spark.hadoop.fs.s3a.aws.credentials.provider": "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
            "spark.hadoop.fs.s3a.endpoint": storage_cfg.s3_endpoint,
            "spark.hadoop.fs.s3a.access.key": storage_cfg.s3_access_key,
            "spark.hadoop.fs.s3a.secret.key": storage_cfg.s3_secret_key,
            "spark.hadoop.fs.s3a.path.style.access": "true",
            "spark.hadoop.fs.s3a.connection.ssl.enabled": str(storage_cfg.s3_endpoint.startswith("https://")).lower(),
        })
    else:
        raise ValueError("S3_PROVIDER must be aws or minio")
    return options
