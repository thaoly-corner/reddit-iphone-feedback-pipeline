"""SQLAlchemy engine + a tiny query helper returning pandas frames, with TTL cache and timing."""
from __future__ import annotations

import hashlib
import json
import time
from contextvars import ContextVar
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.sqlalchemy_url, pool_pre_ping=True, pool_size=5, max_overflow=5)
    return _engine


class _Cache:
    def __init__(self, ttl: int):
        self.ttl = ttl
        self._store: dict[str, tuple[float, pd.DataFrame, float]] = {}

    def get(self, key: str):
        hit = self._store.get(key)
        if hit and time.time() - hit[0] < self.ttl:
            return hit[1], hit[2], True
        return None

    def put(self, key: str, frame: pd.DataFrame, db_ms: float):
        self._store[key] = (time.time(), frame, db_ms)

    def clear(self):
        self._store.clear()


cache = _Cache(settings.cache_ttl_seconds)


class _Fanout:
    """Forwards counter increments to several QueryStats objects."""

    def __init__(self, *targets):
        self._targets = targets

    def _bump(self, name: str, value):
        for t in self._targets:
            setattr(t, name, getattr(t, name) + value)

    @property
    def db_ms(self):
        return self._targets[0].db_ms

    @db_ms.setter
    def db_ms(self, v):
        self._bump("db_ms", v - self._targets[0].db_ms)

    @property
    def queries(self):
        return self._targets[0].queries

    @queries.setter
    def queries(self, v):
        self._bump("queries", v - self._targets[0].queries)

    @property
    def cache_hits(self):
        return self._targets[0].cache_hits

    @cache_hits.setter
    def cache_hits(self, v):
        self._bump("cache_hits", v - self._targets[0].cache_hits)


class QueryStats:
    """Per-request accumulator (set by middleware) so endpoints can report DB time + cache hits."""

    def __init__(self):
        self.db_ms = 0.0
        self.queries = 0
        self.cache_hits = 0


current_stats: ContextVar[QueryStats | None] = ContextVar("current_stats", default=None)


def query_df(sql: str, params: dict[str, Any] | None = None, stats: QueryStats | None = None) -> pd.DataFrame:
    params = params or {}
    request_stats = current_stats.get()
    if stats is None:
        stats = request_stats
    elif request_stats is not None and stats is not request_stats:
        # endpoint-level Filters.stats and the request-level ledger both get the numbers
        stats = _Fanout(stats, request_stats)  # type: ignore[assignment]
    key = hashlib.sha1((sql + json.dumps(params, sort_keys=True, default=str)).encode()).hexdigest()
    hit = cache.get(key)
    if hit:
        frame, db_ms, _ = hit
        if stats:
            stats.cache_hits += 1
            stats.queries += 1
        return frame.copy()
    t0 = time.perf_counter()
    with get_engine().connect() as conn:
        frame = pd.read_sql(text(sql), conn, params=params)
    db_ms = (time.perf_counter() - t0) * 1000
    cache.put(key, frame, db_ms)
    if stats:
        stats.db_ms += db_ms
        stats.queries += 1
    return frame.copy()
