"""Settings for the BrandVoice API. Reads DB_* from the repository .env (same keys as the pipeline)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlencode

from dotenv import load_dotenv

_HERE = Path(__file__).resolve()
# application/api/app/config.py -> repo root is 3 levels up
REPO_ROOT = _HERE.parents[3]

for candidate in (_HERE.parents[1] / ".env", REPO_ROOT / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=False)
        break


def _env(name: str, default: str = "", legacy: str | None = None) -> str:
    v = os.getenv(name)
    if v is None and legacy:
        v = os.getenv(legacy)
    return default if v is None else v


@dataclass(frozen=True)
class Settings:
    db_host: str = _env("DB_HOST", "localhost", "POSTGRES_HOST")
    db_port: int = int(_env("DB_PORT", "5432", "POSTGRES_PORT"))
    db_name: str = _env("DB_NAME", "voc_analytics", "POSTGRES_DB")
    db_user: str = _env("DB_USER", "", "POSTGRES_USER")
    db_password: str = _env("DB_PASSWORD", "", "POSTGRES_PASSWORD")
    db_sslmode: str = _env("DB_SSLMODE", "require")
    use_sqlite: bool = _env("USE_SQLITE_FALLBACK", "false").lower() in {"1", "true", "yes"}
    sqlite_path: str = _env("SQLITE_PATH", "serving_voc_star.db")
    cache_ttl_seconds: int = int(_env("API_CACHE_TTL", "300"))
    cors_origins: str = _env("API_CORS_ORIGINS", "http://localhost:5173,http://localhost:8080")

    @property
    def sqlalchemy_url(self) -> str:
        if self.use_sqlite:
            return f"sqlite:///{self.sqlite_path}"
        url = (
            f"postgresql+psycopg2://{quote(self.db_user, safe='')}:{quote(self.db_password, safe='')}"
            f"@{self.db_host}:{self.db_port}/{quote(self.db_name, safe='')}"
        )
        return f"{url}?{urlencode({'sslmode': self.db_sslmode})}" if self.db_sslmode else url


settings = Settings()
