"""
Centralized Configuration, Pluggable Engine Selector & Domain Taxonomy (CO5173).
Default configuration is locked to the empirically proven optimal architecture:
- Silver Engine     : 'pyspark_roberta' (High-accuracy Context-aware Transformer NLP via Arrow Vectorized UDF)
- Batch Gold Engine : 'spark_sql' (2.52x faster than Hadoop MapReduce RDD, unified with Silver NLP)
- Stream Engine     : 'apache_flink' (95,935 ev/s, 0.0089ms latency, 134.78 KB bounded state memory)
- Serving Backend   : 'postgres' (8.05ms mean latency, 39.12 KB peak RAM, 88 KB compact storage)
- Schema Paradigm   : 'galaxy' (P99 = 5.48ms, supports multi-fact BR01-BR08 drill-across on Conformed Star Dims)
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal


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
    project_root: Path = Path("/content/drive/MyDrive/DE")
    raw_local_dir: Path = Path("/content/reddit_2026_07")
    use_s3: bool = False
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "s3a://reddit-lake"

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
    def posts_filtered_jsonl(self) -> Path:
        return self.filtered_dir / "iphone_posts_2026_07.jsonl"

    @property
    def bronze_posts_parquet(self) -> str:
        if self.use_s3:
            return f"{self.s3_bucket}/bronze/posts/iphone_posts_2026_07.parquet"
        return str(self.parquet_dir / "iphone_posts_2026_07.parquet")

    @property
    def silver_posts_path(self) -> str:
        if self.use_s3:
            return f"{self.s3_bucket}/silver/posts"
        return str(self.project_root / "silver" / "posts")

    @property
    def gold_base_path(self) -> str:
        if self.use_s3:
            return f"{self.s3_bucket}/gold"
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
    host: str = "localhost"
    port: int = 5432
    database: str = "voc_analytics"
    user: str = "postgres"
    password: str = "postgres"
    use_sqlite_fallback: bool = True
    sqlite_path: str = "/content/drive/MyDrive/DE/serving_voc_star.db"

    @property
    def jdbc_url(self) -> str:
        return f"jdbc:postgresql://{self.host}:{self.port}/{self.database}"

    @property
    def sqlalchemy_url(self) -> str:
        if self.use_sqlite_fallback:
            return f"sqlite:///{self.sqlite_path}"
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass(frozen=True)
class DomainTaxonomyConfig:
    """
    Tu dien ngu nghia (Taxonomy) trich xuat dong may iPhone (3 -> 17 Pro Max),
    phien ban iOS (15 -> 28 Beta) va phan loai su co ky thuat.
    """
    iphone_model_regex: str = r"(?i)\b(iphone\s*(?:1[1-7]|[3-9]|x[rs]?|se)(?:\s*(?:pro\s*max|pro|plus|mini|air))?)\b"
    ios_version_regex: str = r"(?i)\b(ios\s*(?:1[5-9]|2[0-8])(?:\.\d+(?:\.\d+)?)?(?:\s*beta)?)\b"

    issue_taxonomy: Dict[str, Dict[str, List[str]]] = field(default_factory=lambda: {
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