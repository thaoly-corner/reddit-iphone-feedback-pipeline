"""
Centralized Configuration, Pluggable Engine Selector & Domain Taxonomy (CO5173).
Default configuration is locked to the empirically proven optimal architecture:
- Silver Engine     : 'pyspark_roberta' (High-accuracy Context-aware Transformer NLP via Arrow Vectorized UDF)
- Batch Gold Engine : 'spark_sql' (2.52x faster than Hadoop MapReduce RDD, unified with Silver NLP)
- Stream Engine     : 'apache_flink' (95,935 ev/s, 0.0089ms latency, 134.78 KB bounded state memory)
- Serving Backend   : 'postgres' (8.05ms mean latency, 39.12 KB peak RAM, 88 KB compact storage)
- Schema Paradigm   : 'galaxy' (P99 = 5.48ms, supports multi-fact BR01-BR08 drill-across on Conformed Star Dims)
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast
from urllib.parse import quote, urlencode


def _env(name: str, default: str = "", legacy_name: str | None = None) -> str:
    """Read at config construction time, after the caller loads .env."""
    value = os.getenv(name)
    if value is None and legacy_name is not None:
        value = os.getenv(legacy_name)
    return default if value is None else value


def _env_bool(name: str, default: bool) -> bool:
    value = _env(name, str(default)).strip().lower()
    if value not in {"true", "false", "1", "0", "yes", "no"}:
        raise ValueError(f"{name} must be true or false")
    return value in {"true", "1", "yes"}


@dataclass(frozen=True)
class PipelineExecutionConfig:
    """
    Cau hinh dieu phoi kien truc Pluggable Pipeline xuyên suot:
    Silver Layer -> Gold Batch Layer -> Gold Stream Layer -> Serving Layer & Schema Paradigm.
    """
    silver_engine: Literal[
        "pyspark_roberta",
        "pyspark_lexicon",
        "hadoop_mapreduce_silver",
        "duckdb_vectorized_silver"
    ] = "pyspark_roberta"
    batch_gold_engine: Literal["spark_sql", "hadoop_mapreduce", "duckdb_biglake"] = "spark_sql"
    stream_engine: Literal["spark_streaming", "apache_flink", "kafka_streams"] = "apache_flink"
    serving_backend: Literal["postgres", "duckdb_biglake", "hive_metastore", "sqlite_local"] = "postgres"
    schema_paradigm: Literal["star", "snowflake", "galaxy", "obt"] = "galaxy"
    max_acceptable_p99_latency_ms: float = 50.0
    max_acceptable_memory_mb: float = 512.0


@dataclass(frozen=True)
class StorageConfig:
    """Quan ly duong dan Data Lakehouse (Ho tro Google Drive/Local hoac S3A/MinIO)."""
    project_root: Path = field(default_factory=lambda: Path(
        _env("HISTORICAL_WORK_DIR", "/content/drive/MyDrive/DE")
    ))
    raw_local_dir: Path = field(default_factory=lambda: Path(
        _env("RAW_DIR", "/content/drive/MyDrive/DE/raw")
    ))

    use_s3: bool = field(default_factory=lambda: _env_bool("USE_S3", True))
    s3_provider: Literal["aws", "minio"] = field(
        default_factory=lambda: cast(Literal["aws", "minio"], _env("S3_PROVIDER", "aws"))
    )

    # MinIO-specific settings.
    s3_endpoint: str = field(default_factory=lambda: _env("S3_ENDPOINT", "http://localhost:9000"))
    s3_access_key: str = field(default_factory=lambda: _env("S3_ACCESS_KEY", "minioadmin"), repr=False)
    s3_secret_key: str = field(default_factory=lambda: _env("S3_SECRET_KEY", "minioadmin"), repr=False)

    #AWS S3 settings (for production deployment on AWS S3)
    s3_bucket: str = field(default_factory=lambda: _env("S3_BUCKET", legacy_name="S3_BUCKET_NAME"))
    aws_region: str = field(default_factory=lambda: _env("AWS_DEFAULT_REGION").strip() or "ap-southeast-1")

    def __post_init__(self) -> None:
        if self.use_s3 and self.s3_provider not in {"aws", "minio"}:
            raise ValueError("S3_PROVIDER must be aws or minio")
        # Older callers supplied s3a://bucket rather than a bare bucket name.
        bucket = self.s3_bucket.strip().removeprefix("s3a://").removeprefix("s3://").strip("/")
        if bucket and "/" in bucket:
            raise ValueError("S3_BUCKET must contain a bucket name, not an object path")
        object.__setattr__(self, "s3_bucket", bucket)

    @property
    def filtered_dir(self) -> Path:
        return self.project_root / "filtered"

    @property
    def parquet_dir(self) -> Path:
        return self.project_root / "parquet"

    @property
    def profile_dir(self) -> Path:
        return self.project_root / "profiling"

    @property
    def bronze_posts_parquet(self) -> str:
        """Backward-compatible alias. Prefer bronze_posts_path."""
        return self.bronze_posts_path

    @property
    def bronze_posts_path(self) -> str:
        """
        Base Bronze path containing all monthly partitions.

        Example:
        s3a://bucket/bronze/posts/
            year=2026/month=05/
            year=2026/month=06/
            year=2026/month=07/
        """
        if self.use_s3:
            if not self.s3_bucket:
                raise ValueError("S3_BUCKET is required when use_s3=True")
            return (
                f"s3a://{self.s3_bucket}/bronze/posts"
            )

        return str(self.parquet_dir)

    @property
    def silver_posts_path(self) -> str:
        if self.use_s3:
            if not self.s3_bucket:
                raise ValueError("S3_BUCKET is required when use_s3=True")
            return (
                f"s3a://{self.s3_bucket}/silver/posts"
            )
        return str(self.project_root / "silver" / "posts")

    @property
    def gold_base_path(self) -> str:
        if self.use_s3:
            if not self.s3_bucket:
                raise ValueError(
                    "S3_BUCKET is required when use_s3=True"
                )
            return (
                f"s3a://{self.s3_bucket}/gold"
            )
        return str(self.project_root / "gold")

    @property
    def hive_warehouse_dir(self) -> str:
        return str(self.project_root / "spark_hive_warehouse")

    def ensure_local_dirs(self) -> None:
        for folder in [
            self.raw_local_dir,
            self.filtered_dir,
            self.parquet_dir,
            self.profile_dir,
            self.project_root / "silver",
            self.project_root / "gold",
            self.project_root / "spark_hive_warehouse",
        ]:
            folder.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class DatabaseConfig:
    """Cau hinh ket noi Serving Layer (PostgreSQL / Supabase / Neon / SQLite Fallback)."""
    host: str = field(default_factory=lambda: _env("DB_HOST", "localhost", "POSTGRES_HOST"))
    port: int = field(default_factory=lambda: int(_env("DB_PORT", "5432", "POSTGRES_PORT")))
    database: str = field(default_factory=lambda: _env("DB_NAME", "voc_analytics", "POSTGRES_DB"))
    user: str = field(default_factory=lambda: _env("DB_USER", legacy_name="POSTGRES_USER"))
    password: str = field(default_factory=lambda: _env("DB_PASSWORD", legacy_name="POSTGRES_PASSWORD"), repr=False)
    use_sqlite_fallback: bool = field(default_factory=lambda: _env_bool(
        "USE_SQLITE_FALLBACK", not bool(_env("DB_HOST", legacy_name="POSTGRES_HOST"))
    ))
    sqlite_path: str = field(default_factory=lambda: _env("SQLITE_PATH", "serving_voc_star.db"))
    sslmode: str = field(default_factory=lambda: _env("DB_SSLMODE"))

    def __post_init__(self) -> None:
        if not 1 <= self.port <= 65535:
            raise ValueError("DB_PORT must be between 1 and 65535")

    @property
    def jdbc_url(self) -> str:
        return f"jdbc:postgresql://{self.host}:{self.port}/{self.database}"

    @property
    def sqlalchemy_url(self) -> str:
        if self.use_sqlite_fallback:
            return f"sqlite:///{self.sqlite_path}"
        if not self.host or not self.user or not self.database:
            raise ValueError("DB_HOST, DB_USER and DB_NAME are required for PostgreSQL")
        url = (
            f"postgresql+psycopg2://{quote(self.user, safe='')}:{quote(self.password, safe='')}"
            f"@{self.host}:{self.port}/{quote(self.database, safe='')}"
        )
        return f"{url}?{urlencode({'sslmode': self.sslmode})}" if self.sslmode else url


@dataclass(frozen=True)
class DomainTaxonomyConfig:
    """
    Tu dien ngu nghia (Taxonomy) trich xuat dong may iPhone (3 -> 17 Pro Max),
    phien ban iOS (15 -> 28 Beta) va phan loai su co ky thuat.
    """
    iphone_model_regex: str = r"(?i)\b(iphone\s*(?:1[1-7]|[3-9]|x[rs]?|se)(?:\s*(?:pro\s*max|pro|plus|mini|air))?)\b"
    ios_version_regex: str = r"(?i)\b(ios\s*(?:1[5-9]|2[0-8])(?:\.\d+(?:\.\d+)?)?(?:\s*beta)?)\b"

    issue_taxonomy: dict[str, dict[str, list[str]]] = field(default_factory=lambda: {
        "Battery & Thermal": {
            "Rapid Battery Drain": ["battery drain", "drain fast", "battery life", "battery issue", "battery issues", "battery health", "tụt pin", "hao pin"],
            "Thermal Overheating": ["overheat", "overheating", "gets hot", "running hot", "warm", "thermal", "nóng máy"],
            "Charging Failure": ["slow charge", "won't charge", "not charging", "magsafe", "cable", "charging port", "charger"]
        },
        "Chassis & Build Quality": {
            "Structural Bending": ["bend", "bending", "bent", "bendgate", "bend gate", "frame warp", "cong máy"],
            "Back Cover & Seal Defect": ["back cover", "back glass", "slipped with paper", "ip rated", "loose glass"]
        },
        "Display & Touch": {
            "Screen Artifacts": ["green line", "green tint", "pink line", "flicker", "burn-in", "dead pixel", "liquid glass"],
            "Touch & Keyboard Lag": ["typo", "typos", "swipe typing", "swipe type", "touch unresponsive", "ghost touch", "keyboard lag"]
        },
        "Camera & Optics": {
            "Focus & Exposure Bug": ["focus point", "exposure", "blur", "blurry", "camera shake", "lens flare", "black screen", "camera app", "camera control"]
        },
        "Connectivity & Network": {
            "Wireless & Cellular Drop": ["wifi drop", "no service", "cellular", "bluetooth", "airdrop", "carplay", "sos only"]
        },
        "OS & System Software": {
            "UI Lag & System Freeze": ["lag", "lagging", "stutter", "freeze", "bootloop", "crash", "restarting"],
            "Search & Settings Bug": ["settings search", "search broke", "search still broke", "spotlight", "automatic translation", "system data", "storage", "icloud", "wallet"]
        }
    })

    support_taxonomy: dict[str, list[str]] = field(default_factory=lambda: {
        "Battery & Charging Support": [
            "battery",
            "battery drain",
            "battery health",
            "charging",
            "charger",
            "magsafe",
            "not charging",
            "slow charge",
        ],
        "Connectivity Support": [
            "wifi",
            "bluetooth",
            "airdrop",
            "cellular",
            "mobile data",
            "no service",
            "carplay",
            "hotspot",
        ],
        "Camera & Photos Support": [
            "camera",
            "photo",
            "photos",
            "video",
            "focus",
            "exposure",
            "lens",
        ],
        "Display & Touch Support": [
            "screen",
            "display",
            "touch",
            "keyboard",
            "brightness",
            "green line",
            "flicker",
        ],
        "iOS & Settings Support": [
            "ios",
            "settings",
            "update",
            "software update",
            "spotlight",
            "notification",
            "control center",
        ],
        "Storage & iCloud Support": [
            "storage",
            "icloud",
            "backup",
            "restore",
            "sync",
            "photos sync",
        ],
        "Data Transfer & Migration": [
            "transfer",
            "move data",
            "migration",
            "new iphone",
            "old iphone",
            "android",
            "quick start",
        ],
        "Account & Apple ID Support": [
            "apple id",
            "icloud account",
            "sign in",
            "login",
            "password",
            "account",
        ],
    })
