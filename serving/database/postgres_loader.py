"""
Unified Pluggable Serving Layer Loader & Query Router:
Ho tro nap Idempotent Upsert va phuc vu truy van tren ca 4 kien truc Schema:
- 'star'      : Kimball Star Schema (1-Hop Denormalized Dimensions)
- 'snowflake' : 3NF Normalized Hierarchical Sub-Dimensions
- 'galaxy'    : Fact Constellation (3 Fact Tables sharing Conformed Dimensions)
- 'obt'       : Flat One Big Table (Denormalized Wide Table)
Tren cac he quan tri: PostgreSQL (Supabase/Neon), SQLite Local hoac DuckDB BigLake.
"""
from pathlib import Path
from typing import Dict, Any
import pandas as pd
from sqlalchemy import create_engine, text

from config.pipeline_config import StorageConfig, DatabaseConfig, PipelineExecutionConfig


class UnifiedServingPipelineLoader:
    """Quan ly nap du lieu Luy dang (Idempotent Sync) tu Tang Gold vao Serving Layer theo Config."""

    def __init__(
        self,
        storage_cfg: StorageConfig,
        db_cfg: DatabaseConfig,
        exec_cfg: PipelineExecutionConfig = PipelineExecutionConfig()
    ):
        self.storage_cfg = storage_cfg
        self.db_cfg = db_cfg
        self.exec_cfg = exec_cfg
        self.is_sqlite = db_cfg.use_sqlite_fallback or (exec_cfg.serving_backend == "sqlite_local")
        self.engine = create_engine(db_cfg.sqlalchemy_url, pool_pre_ping=True)

    def initialize_schema(self) -> None:
        """Khoi tao bang va Index cho ca Star, Snowflake, Galaxy va OBT Schema."""
        if self.is_sqlite:
            self._init_sqlite_compatible_schema()
            return

        ddl_path = Path(__file__).parent / "schema_ddl.sql"
        ddl_content = ddl_path.read_text(encoding="utf-8")
        with self.engine.begin() as conn:
            for statement in ddl_content.split(";"):
                stmt = statement.strip()
                if stmt:
                    conn.execute(text(stmt))

    def _init_sqlite_compatible_schema(self) -> None:
        """Khoi tao DDL tuong thich SQLite & PostgreSQL cho Star, Snowflake, Galaxy va OBT."""
        stmts = [
            """CREATE TABLE IF NOT EXISTS dim_date (
                date_key INTEGER PRIMARY KEY, full_date TEXT NOT NULL UNIQUE,
                day_name TEXT NOT NULL, day_of_week INTEGER NOT NULL,
                day_of_month INTEGER NOT NULL, week_of_year INTEGER NOT NULL,
                month INTEGER NOT NULL, quarter INTEGER NOT NULL,
                year INTEGER NOT NULL, is_weekend INTEGER NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS dim_iphone_model (
                model_id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL UNIQUE, series TEXT NOT NULL, form_factor TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS dim_os_version (
                os_id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_name TEXT NOT NULL UNIQUE, major_release TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS dim_issue_category (
                issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                feature_name TEXT NOT NULL, issue_name TEXT NOT NULL,
                severity_tier TEXT DEFAULT 'MEDIUM',
                UNIQUE (feature_name, issue_name)
            )""",
            """CREATE TABLE IF NOT EXISTS fact_feedback_summary (
                summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_key INTEGER NOT NULL, model_id INTEGER NOT NULL,
                os_id INTEGER NOT NULL, issue_id INTEGER NOT NULL,
                total_posts INTEGER DEFAULT 0, total_comments INTEGER DEFAULT 0,
                positive_count INTEGER DEFAULT 0, neutral_count INTEGER DEFAULT 0,
                negative_count INTEGER DEFAULT 0, avg_sentiment_score REAL,
                avg_engagement_score REAL,
                UNIQUE (date_key, model_id, os_id, issue_id)
            )""",
            """CREATE TABLE IF NOT EXISTS fact_emerging_issues (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_key INTEGER NOT NULL, model_id INTEGER NOT NULL, issue_id INTEGER NOT NULL,
                current_3d_avg REAL NOT NULL, baseline_14d_avg REAL NOT NULL,
                growth_rate_pct REAL NOT NULL, z_score REAL NOT NULL, is_anomaly INTEGER NOT NULL,
                UNIQUE (date_key, model_id, issue_id)
            )""",
            """CREATE TABLE IF NOT EXISTS fact_high_impact_complaints (
                post_id TEXT PRIMARY KEY, date_key INTEGER NOT NULL,
                model_id INTEGER NOT NULL, os_id INTEGER NOT NULL, issue_id INTEGER NOT NULL,
                title TEXT NOT NULL, permalink TEXT NOT NULL,
                reddit_score INTEGER NOT NULL, num_comments INTEGER NOT NULL,
                engagement_score INTEGER NOT NULL, sentiment_score REAL NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS snow_dim_model_series (
                series_id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_name TEXT NOT NULL UNIQUE, release_generation INTEGER
            )""",
            """CREATE TABLE IF NOT EXISTS snow_dim_iphone_model (
                model_id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL UNIQUE, series_id INTEGER NOT NULL, form_factor TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS snow_dim_feature_group (
                feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
                feature_name TEXT NOT NULL UNIQUE, hardware_or_software TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS snow_dim_issue_category (
                issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                feature_id INTEGER NOT NULL, issue_name TEXT NOT NULL,
                severity_tier TEXT DEFAULT 'MEDIUM',
                UNIQUE (feature_id, issue_name)
            )""",
            """CREATE TABLE IF NOT EXISTS snow_fact_feedback_summary (
                summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_key INTEGER NOT NULL, model_id INTEGER NOT NULL,
                os_id INTEGER NOT NULL, issue_id INTEGER NOT NULL,
                total_posts INTEGER DEFAULT 0, total_comments INTEGER DEFAULT 0,
                negative_count INTEGER DEFAULT 0, avg_sentiment_score REAL,
                avg_engagement_score REAL,
                UNIQUE (date_key, model_id, os_id, issue_id)
            )""",
            """CREATE TABLE IF NOT EXISTS obt_feedback_wide (
                date_key INTEGER NOT NULL, full_date TEXT NOT NULL,
                model_name TEXT NOT NULL, series_name TEXT NOT NULL,
                os_version TEXT NOT NULL, feature_name TEXT NOT NULL,
                issue_name TEXT NOT NULL, total_posts INTEGER,
                total_comments INTEGER, negative_count INTEGER,
                avg_sentiment_score REAL, avg_engagement_score REAL,
                UNIQUE (date_key, model_name, os_version, feature_name, issue_name)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_ffs_date_model ON fact_feedback_summary(date_key, model_id)",
            "CREATE INDEX IF NOT EXISTS idx_snow_ffs_date_model ON snow_fact_feedback_summary(date_key, model_id)",
            "CREATE INDEX IF NOT EXISTS idx_fei_date_model ON fact_emerging_issues(date_key, model_id)"
        ]
        with self.engine.begin() as conn:
            for stmt in stmts:
                conn.execute(text(stmt))

    def sync_dimensions_and_facts(self) -> Dict[str, Any]:
        """Dong bo du lieu tu Gold Parquet vao cac bang cua Schema Paradigm duoc cau hinh."""
        gold_base = self.storage_cfg.gold_base_path
        df_summary = pd.read_parquet(f"{gold_base}/issue_summary")
        df_emerging = pd.read_parquet(f"{gold_base}/emerging_issues")
        df_complaints = pd.read_parquet(f"{gold_base}/high_impact_complaints")

        with self.engine.begin() as conn:
            unique_dates = pd.to_datetime(df_summary["feedback_date"].unique())
            for dt in unique_dates:
                date_key = int(dt.strftime("%Y%m%d"))
                conn.execute(
                    text("""
                        INSERT INTO dim_date (date_key, full_date, day_name, day_of_week, day_of_month, week_of_year, month, quarter, year, is_weekend)
                        VALUES (:dk, :fd, :dn, :dow, :dom, :woy, :m, :q, :y, :iw)
                        ON CONFLICT (date_key) DO NOTHING
                    """),
                    {
                        "dk": date_key, "fd": str(dt.date()), "dn": dt.strftime("%A"),
                        "dow": int(dt.dayofweek + 1), "dom": int(dt.day),
                        "woy": int(dt.isocalendar().week), "m": int(dt.month),
                        "q": int(dt.quarter), "y": int(dt.year),
                        "iw": (1 if dt.dayofweek >= 5 else 0) if self.is_sqlite else bool(dt.dayofweek >= 5)
                    }
                )

            for model_name in df_summary["iphone_model"].unique():
                series = " ".join(model_name.split()[:2]) if "iPhone" in model_name else "Other"
                form = "Pro Max" if "Pro Max" in model_name else ("Pro" if "Pro" in model_name else ("Plus" if "Plus" in model_name else "Standard"))
                conn.execute(
                    text("""
                        INSERT INTO dim_iphone_model (model_name, series, form_factor)
                        VALUES (:mn, :sr, :ff)
                        ON CONFLICT (model_name) DO NOTHING
                    """),
                    {"mn": model_name, "sr": series, "ff": form}
                )
                conn.execute(
                    text("""
                        INSERT INTO snow_dim_model_series (series_name, release_generation)
                        VALUES (:sr, 2026)
                        ON CONFLICT (series_name) DO NOTHING
                    """),
                    {"sr": series}
                )

            series_map = dict(conn.execute(text("SELECT series_name, series_id FROM snow_dim_model_series")).fetchall())
            for model_name in df_summary["iphone_model"].unique():
                series = " ".join(model_name.split()[:2]) if "iPhone" in model_name else "Other"
                form = "Pro Max" if "Pro Max" in model_name else ("Pro" if "Pro" in model_name else ("Plus" if "Plus" in model_name else "Standard"))
                conn.execute(
                    text("""
                        INSERT INTO snow_dim_iphone_model (model_name, series_id, form_factor)
                        VALUES (:mn, :sid, :ff)
                        ON CONFLICT (model_name) DO NOTHING
                    """),
                    {"mn": model_name, "sid": series_map[series], "ff": form}
                )

            for os_name in df_summary["ios_version"].unique():
                major = os_name.split(".")[0] if "." in os_name else os_name
                conn.execute(
                    text("""
                        INSERT INTO dim_os_version (version_name, major_release)
                        VALUES (:vn, :mr)
                        ON CONFLICT (version_name) DO NOTHING
                    """),
                    {"vn": os_name, "mr": major}
                )

            issue_pairs = df_summary[["feature_category", "issue_category"]].drop_duplicates()
            for _, row in issue_pairs.iterrows():
                sev = "CRITICAL" if any(k in row["issue_category"] for k in ["Bending", "Overheating", "Drain", "Freeze"]) else "MEDIUM"
                hw_sw = "SOFTWARE" if "OS" in row["feature_category"] else "HARDWARE"
                conn.execute(
                    text("""
                        INSERT INTO dim_issue_category (feature_name, issue_name, severity_tier)
                        VALUES (:fn, :inm, :sev)
                        ON CONFLICT (feature_name, issue_name) DO NOTHING
                    """),
                    {"fn": row["feature_category"], "inm": row["issue_category"], "sev": sev}
                )
                conn.execute(
                    text("""
                        INSERT INTO snow_dim_feature_group (feature_name, hardware_or_software)
                        VALUES (:fn, :hs)
                        ON CONFLICT (feature_name) DO NOTHING
                    """),
                    {"fn": row["feature_category"], "hs": hw_sw}
                )

            feat_map = dict(conn.execute(text("SELECT feature_name, feature_id FROM snow_dim_feature_group")).fetchall())
            for _, row in issue_pairs.iterrows():
                sev = "CRITICAL" if any(k in row["issue_category"] for k in ["Bending", "Overheating", "Drain", "Freeze"]) else "MEDIUM"
                conn.execute(
                    text("""
                        INSERT INTO snow_dim_issue_category (feature_id, issue_name, severity_tier)
                        VALUES (:fid, :inm, :sev)
                        ON CONFLICT (feature_id, issue_name) DO NOTHING
                    """),
                    {"fid": feat_map[row["feature_category"]], "inm": row["issue_category"], "sev": sev}
                )

            model_map = dict(conn.execute(text("SELECT model_name, model_id FROM dim_iphone_model")).fetchall())
            snow_model_map = dict(conn.execute(text("SELECT model_name, model_id FROM snow_dim_iphone_model")).fetchall())
            os_map = dict(conn.execute(text("SELECT version_name, os_id FROM dim_os_version")).fetchall())
            issue_map = {
                (r[0], r[1]): r[2]
                for r in conn.execute(text("SELECT feature_name, issue_name, issue_id FROM dim_issue_category")).fetchall()
            }
            snow_issue_map = {
                (r[0], r[1]): r[2]
                for r in conn.execute(text("""
                    SELECT fg.feature_name, ic.issue_name, ic.issue_id
                    FROM snow_dim_issue_category ic
                    JOIN snow_dim_feature_group fg ON ic.feature_id = fg.feature_id
                """)).fetchall()
            }

            summary_upserted = 0
            for _, r in df_summary.iterrows():
                dk = int(pd.to_datetime(r["feedback_date"]).strftime("%Y%m%d"))
                series_nm = " ".join(str(r["iphone_model"]).split()[:2]) if "iPhone" in str(r["iphone_model"]) else "Other"

                conn.execute(
                    text("""
                        INSERT INTO fact_feedback_summary (
                            date_key, model_id, os_id, issue_id,
                            total_posts, total_comments, positive_count, neutral_count, negative_count,
                            avg_sentiment_score, avg_engagement_score
                        ) VALUES (:dk, :mid, :oid, :iid, :tp, :tc, :pos, :neu, :neg, :sent, :eng)
                        ON CONFLICT (date_key, model_id, os_id, issue_id) DO UPDATE SET
                            total_posts = EXCLUDED.total_posts,
                            total_comments = EXCLUDED.total_comments,
                            positive_count = EXCLUDED.positive_count,
                            neutral_count = EXCLUDED.neutral_count,
                            negative_count = EXCLUDED.negative_count,
                            avg_sentiment_score = EXCLUDED.avg_sentiment_score,
                            avg_engagement_score = EXCLUDED.avg_engagement_score
                    """),
                    {
                        "dk": dk, "mid": model_map[r["iphone_model"]],
                        "oid": os_map[r["ios_version"]],
                        "iid": issue_map[(r["feature_category"], r["issue_category"])],
                        "tp": int(r["total_posts"]), "tc": int(r["total_comments"]),
                        "pos": int(r["positive_count"]), "neu": int(r["neutral_count"]),
                        "neg": int(r["negative_count"]), "sent": float(r["avg_sentiment_score"]),
                        "eng": float(r["avg_engagement_score"])
                    }
                )

                conn.execute(
                    text("""
                        INSERT INTO snow_fact_feedback_summary (
                            date_key, model_id, os_id, issue_id,
                            total_posts, total_comments, negative_count,
                            avg_sentiment_score, avg_engagement_score
                        ) VALUES (:dk, :mid, :oid, :iid, :tp, :tc, :neg, :sent, :eng)
                        ON CONFLICT (date_key, model_id, os_id, issue_id) DO UPDATE SET
                            total_posts = EXCLUDED.total_posts,
                            total_comments = EXCLUDED.total_comments,
                            negative_count = EXCLUDED.negative_count,
                            avg_sentiment_score = EXCLUDED.avg_sentiment_score,
                            avg_engagement_score = EXCLUDED.avg_engagement_score
                    """),
                    {
                        "dk": dk, "mid": snow_model_map[r["iphone_model"]],
                        "oid": os_map[r["ios_version"]],
                        "iid": snow_issue_map[(r["feature_category"], r["issue_category"])],
                        "tp": int(r["total_posts"]), "tc": int(r["total_comments"]),
                        "neg": int(r["negative_count"]), "sent": float(r["avg_sentiment_score"]),
                        "eng": float(r["avg_engagement_score"])
                    }
                )

                conn.execute(
                    text("""
                        INSERT INTO obt_feedback_wide (
                            date_key, full_date, model_name, series_name,
                            os_version, feature_name, issue_name,
                            total_posts, total_comments, negative_count,
                            avg_sentiment_score, avg_engagement_score
                        ) VALUES (:dk, :fd, :mn, :sr, :osv, :fn, :inm, :tp, :tc, :neg, :sent, :eng)
                        ON CONFLICT (date_key, model_name, os_version, feature_name, issue_name) DO UPDATE SET
                            total_posts = EXCLUDED.total_posts,
                            negative_count = EXCLUDED.negative_count
                    """),
                    {
                        "dk": dk, "fd": str(r["feedback_date"]), "mn": str(r["iphone_model"]),
                        "sr": series_nm, "osv": str(r["ios_version"]),
                        "fn": str(r["feature_category"]), "inm": str(r["issue_category"]),
                        "tp": int(r["total_posts"]), "tc": int(r["total_comments"]),
                        "neg": int(r["negative_count"]), "sent": float(r["avg_sentiment_score"]),
                        "eng": float(r["avg_engagement_score"])
                    }
                )
                summary_upserted += 1

            emerging_upserted = 0
            for _, r in df_emerging.iterrows():
                dk = int(pd.to_datetime(r["feedback_date"]).strftime("%Y%m%d"))
                conn.execute(
                    text("""
                        INSERT INTO fact_emerging_issues (
                            date_key, model_id, issue_id,
                            current_3d_avg, baseline_14d_avg, growth_rate_pct, z_score, is_anomaly
                        ) VALUES (:dk, :mid, :iid, :curr, :base, :gr, :zs, :anom)
                        ON CONFLICT (date_key, model_id, issue_id) DO UPDATE SET
                            current_3d_avg = EXCLUDED.current_3d_avg,
                            baseline_14d_avg = EXCLUDED.baseline_14d_avg,
                            growth_rate_pct = EXCLUDED.growth_rate_pct,
                            z_score = EXCLUDED.z_score,
                            is_anomaly = EXCLUDED.is_anomaly
                    """),
                    {
                        "dk": dk, "mid": model_map[r["iphone_model"]],
                        "iid": issue_map[(r["feature_category"], r["issue_category"])],
                        "curr": float(r["curr_3d_avg"]), "base": float(r["base_14d_avg"]),
                        "gr": float(r["growth_rate_pct"]), "zs": float(r["z_score"]),
                        "anom": (1 if bool(r["is_anomaly"]) else 0) if self.is_sqlite else bool(r["is_anomaly"])
                    }
                )
                emerging_upserted += 1

            complaints_upserted = 0
            for _, r in df_complaints.iterrows():
                dk = int(pd.to_datetime(r["feedback_date"]).strftime("%Y%m%d"))
                conn.execute(
                    text("""
                        INSERT INTO fact_high_impact_complaints (
                            post_id, date_key, model_id, os_id, issue_id,
                            title, permalink, reddit_score, num_comments, engagement_score, sentiment_score
                        ) VALUES (:pid, :dk, :mid, :oid, :iid, :ttl, :pl, :sc, :nc, :eng, :sent)
                        ON CONFLICT (post_id) DO UPDATE SET
                            reddit_score = EXCLUDED.reddit_score,
                            num_comments = EXCLUDED.num_comments,
                            engagement_score = EXCLUDED.engagement_score,
                            sentiment_score = EXCLUDED.sentiment_score
                    """),
                    {
                        "pid": str(r["post_id"]), "dk": dk,
                        "mid": model_map[r["iphone_model"]], "oid": os_map[r["ios_version"]],
                        "iid": issue_map[(r["feature_category"], r["issue_category"])],
                        "ttl": str(r["title"]), "pl": str(r["permalink"]),
                        "sc": int(r["reddit_score"]), "nc": int(r["num_comments"]),
                        "eng": int(r["engagement_score"]), "sent": float(r["sentiment_score"])
                    }
                )
                complaints_upserted += 1

        return {
            "active_schema_paradigm": self.exec_cfg.schema_paradigm,
            "serving_backend": self.exec_cfg.serving_backend,
            "fact_feedback_summary_rows": summary_upserted,
            "fact_emerging_issues_rows": emerging_upserted,
            "fact_high_impact_complaints_rows": complaints_upserted
        }

    def query_serving_mart(self) -> pd.DataFrame:
        """
        Thuc thi truy van phan tich da chieu tren Serving Layer dua theo
        schema_paradigm ('star', 'snowflake', 'galaxy', 'obt') trong PipelineExecutionConfig.
        """
        paradigm = self.exec_cfg.schema_paradigm
        if paradigm == "obt":
            sql = """
                SELECT series_name, feature_name, issue_name,
                       SUM(total_posts) AS total_posts,
                       SUM(negative_count) AS negative_count,
                       ROUND(AVG(avg_engagement_score), 2) AS avg_engagement
                FROM obt_feedback_wide
                GROUP BY series_name, feature_name, issue_name
                ORDER BY total_posts DESC
            """
        elif paradigm == "snowflake":
            sql = """
                SELECT s.series_name, fg.feature_name, i.issue_name,
                       SUM(f.total_posts) AS total_posts,
                       SUM(f.negative_count) AS negative_count,
                       ROUND(AVG(f.avg_engagement_score), 2) AS avg_engagement
                FROM snow_fact_feedback_summary f
                JOIN snow_dim_iphone_model m ON f.model_id = m.model_id
                JOIN snow_dim_model_series s ON m.series_id = s.series_id
                JOIN snow_dim_issue_category i ON f.issue_id = i.issue_id
                JOIN snow_dim_feature_group fg ON i.feature_id = fg.feature_id
                GROUP BY s.series_name, fg.feature_name, i.issue_name
                ORDER BY total_posts DESC
            """
        elif paradigm == "galaxy":
            sql = """
                SELECT m.series AS series_name, i.feature_name, i.issue_name,
                       SUM(f1.total_posts) AS total_posts,
                       SUM(f1.negative_count) AS negative_count,
                       MAX(COALESCE(f2.growth_rate_pct, 0.0)) AS peak_growth_pct,
                       MAX(COALESCE(f2.z_score, 0.0)) AS max_z_score
                FROM fact_feedback_summary f1
                LEFT JOIN fact_emerging_issues f2
                  ON f1.date_key = f2.date_key AND f1.model_id = f2.model_id AND f1.issue_id = f2.issue_id
                JOIN dim_iphone_model m ON f1.model_id = m.model_id
                JOIN dim_issue_category i ON f1.issue_id = i.issue_id
                GROUP BY m.series, i.feature_name, i.issue_name
                ORDER BY total_posts DESC
            """
        else:  # 'star'
            sql = """
                SELECT m.series AS series_name, i.feature_name, i.issue_name,
                       SUM(f.total_posts) AS total_posts,
                       SUM(f.negative_count) AS negative_count,
                       ROUND(AVG(f.avg_engagement_score), 2) AS avg_engagement
                FROM fact_feedback_summary f
                JOIN dim_iphone_model m ON f.model_id = m.model_id
                JOIN dim_issue_category i ON f.issue_id = i.issue_id
                GROUP BY m.series, i.feature_name, i.issue_name
                ORDER BY total_posts DESC
            """
        with self.engine.connect() as conn:
            return pd.read_sql(text(sql), conn)


StarSchemaServingLoader = UnifiedServingPipelineLoader
